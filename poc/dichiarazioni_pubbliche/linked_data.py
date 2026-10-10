from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    PublicSchemaValidationError,
    validate_public_bundle,
)


LINKED_DATA_VERSION = "linked-data-v1"
PUBLIC_BASE_URL = "https://dichiarazionipubbliche.it"
SCHEMA = "https://schema.org/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PROV = "http://www.w3.org/ns/prov#"
DP = PUBLIC_BASE_URL + "/vocab#"

RESOURCE_KINDS = frozenset(
    {
        "dataset",
        "person",
        "organization",
        "statement",
        "occurrence",
        "representation",
        "finding",
        "content",
        "topic",
        "evidence",
        "correction",
    }
)


def public_resource_uri(kind: str, identifier: str) -> str:
    resource_kind = str(kind or "").strip().lower()
    resource_id = str(identifier or "").strip()
    if resource_kind not in RESOURCE_KINDS:
        raise ValueError("LINKED_DATA_RESOURCE_KIND_INVALID")
    if not resource_id:
        raise ValueError("LINKED_DATA_RESOURCE_ID_REQUIRED")
    return f"{PUBLIC_BASE_URL}/id/{resource_kind}/{quote(resource_id, safe='')}"


def topic_public_uri(slug: str) -> str:
    value = str(slug or "").strip()
    if not value:
        raise ValueError("LINKED_DATA_TOPIC_SLUG_REQUIRED")
    return f"{PUBLIC_BASE_URL}/temi/{quote(value, safe='-')}/"


def _uri(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("LINKED_DATA_URI_INVALID")
    return f"<{raw}>"


def _literal(value: Any) -> str:
    text = str(value if value is not None else "")
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


@dataclass(frozen=True, order=True)
class Triple:
    subject: str
    predicate: str
    object: str

    def ntriples(self) -> str:
        return f"{self.subject} {self.predicate} {self.object} ."


def _add_uri(triples: set[Triple], subject: str, predicate: str, obj: str) -> None:
    triples.add(Triple(_uri(subject), _uri(predicate), _uri(obj)))


def _add_literal(triples: set[Triple], subject: str, predicate: str, value: Any) -> None:
    if value is None or str(value).strip() == "":
        return
    triples.add(Triple(_uri(subject), _uri(predicate), _literal(value)))


def _validate_statement_v3_source_url(value: object) -> str:
    """Guard the IRI and JSON-LD link against syntax injection beyond v3 schema."""
    if (
        not isinstance(value, str)
        or value != value.strip()
        or any(ord(char) <= 32 or ord(char) == 127 or char in '<>"\\^\x60{}|' for char in value)
    ):
        raise PublicSchemaValidationError("Statement source URL unsafe for linked data")
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
        ):
            raise PublicSchemaValidationError("Statement source URL is not approved HTTPS")
    except ValueError as exc:
        raise PublicSchemaValidationError("Statement source URL invalid") from exc
    return value


def _statement_v3_bundle(
    payload: dict[str, Any], *, allow_statement_v3: bool,
) -> dict[str, Any]:
    """Only explicitly admitted, fully validated Statement v3 is consumable."""
    if not allow_statement_v3:
        raise PublicSchemaValidationError("Statement v3 linked data requires explicit opt-in")
    if not isinstance(payload, dict) or payload.get("schema_version") != PUBLIC_STATEMENT_SCHEMA_VERSION:
        raise PublicSchemaValidationError("Statement v3 linked data schema incompatible")
    bundle = validate_public_bundle(payload, allow_statement_v3=True)
    for record in bundle["statements"]:
        _validate_statement_v3_source_url(record["source_url"])
    return bundle


def _add_v3_literal(triples: set[Triple], subject: str, predicate: str, value: Any) -> None:
    """N-Triples escaping for authorized source text, without changing v2 bytes."""
    if value is None or str(value).strip() == "":
        return
    raw = str(value)
    escaped = "".join(
        {
            "\\": "\\\\",
            '"': '\\"',
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
        }.get(char, f"\\u{ord(char):04X}" if ord(char) < 32 or ord(char) == 127 else char)
        for char in raw
    )
    triples.add(Triple(_uri(subject), _uri(predicate), f'"{escaped}"'))


def projection_statement_v3_triples(
    payload: dict[str, Any], *, allow_statement_v3: bool = False,
) -> tuple[Triple, ...]:
    """A separate Statement-only graph. Legacy dossiers never provide quote text."""
    bundle = _statement_v3_bundle(payload, allow_statement_v3=allow_statement_v3)
    triples: set[Triple] = set()
    dataset_uri = public_resource_uri("dataset", bundle["dataset_sha256"])
    _add_uri(triples, dataset_uri, RDF + "type", SCHEMA + "Dataset")
    _add_v3_literal(triples, dataset_uri, SCHEMA + "version", bundle["schema_version"])
    _add_v3_literal(triples, dataset_uri, SCHEMA + "dateModified", bundle["generated_at"])
    _add_v3_literal(triples, dataset_uri, DP + "projectionFingerprint", bundle["dataset_sha256"])
    _add_v3_literal(triples, dataset_uri, DP + "linkedDataVersion", "linked-data-statement-v3-opt-in")
    for record in sorted(bundle["statements"], key=lambda s: (s["statement_id"], s["version_id"])):
        statement_uri = public_resource_uri("statement", record["statement_id"])
        person_uri = public_resource_uri("person", record["person_id"])
        content_uri = public_resource_uri("content", record["content_id"])
        _add_uri(triples, dataset_uri, SCHEMA + "hasPart", statement_uri)
        _add_uri(triples, statement_uri, RDF + "type", SCHEMA + "Quotation")
        _add_v3_literal(triples, statement_uri, SCHEMA + "identifier", record["statement_id"])
        _add_v3_literal(triples, statement_uri, SCHEMA + "version", record["version_id"])
        _add_v3_literal(triples, statement_uri, SCHEMA + "text", record["original_text"])
        _add_v3_literal(triples, statement_uri, SCHEMA + "inLanguage", record["language"])
        _add_v3_literal(triples, statement_uri, SCHEMA + "dateCreated", record["statement_date"])
        _add_v3_literal(triples, statement_uri, DP + "wordingType", "VERBATIM_ORIGINAL")
        _add_v3_literal(triples, statement_uri, DP + "quoteSha256", record["quote_sha256"])
        _add_v3_literal(triples, statement_uri, DP + "sourceSha256", record["source_sha256"])
        _add_v3_literal(triples, statement_uri, DP + "sourceVersion", record["source_version"])
        _add_v3_literal(triples, statement_uri, DP + "sourceKind", record["source_kind"])
        _add_v3_literal(triples, statement_uri, DP + "speechAct", record["speech_act"])
        _add_v3_literal(triples, statement_uri, DP + "endorsed", str(record["endorsed"]).lower())
        _add_uri(triples, statement_uri, DP + "recordedSpeaker", person_uri)
        if record["endorsed"]:
            _add_uri(triples, statement_uri, SCHEMA + "author", person_uri)
        _add_uri(triples, statement_uri, SCHEMA + "isPartOf", content_uri)
        _add_v3_literal(triples, content_uri, SCHEMA + "name", record["source_title"])
        _add_uri(triples, content_uri, SCHEMA + "url", record["source_url"])
        for locator_field, locator_value in record["locator"].items():
            _add_v3_literal(
                triples, statement_uri,
                DP + {
                    "start_char": "startChar", "end_char": "endChar",
                    "segment_id": "segmentId", "start_ms": "startMs", "end_ms": "endMs",
                }[locator_field], locator_value,
            )
        if record["finding_id"] is not None:
            _add_uri(
                triples, statement_uri, SCHEMA + "subjectOf",
                public_resource_uri("finding", record["finding_id"]),
            )
        for kind in ("summary", "translation"):
            derived = record[kind]
            if derived is None:
                continue
            uri = public_resource_uri("representation", f'{record["version_id"]}:{kind}')
            _add_uri(triples, statement_uri, SCHEMA + "hasPart", uri)
            _add_uri(triples, uri, RDF + "type", SCHEMA + "CreativeWork")
            _add_v3_literal(triples, uri, DP + "wordingType", derived["wording_type"])
            _add_v3_literal(triples, uri, SCHEMA + "text", derived["text"])
            _add_uri(triples, uri, PROV + "wasDerivedFrom", statement_uri)
            _add_v3_literal(triples, uri, DP + "sourceQuoteSha256", derived["source_quote_sha256"])
            if kind == "translation":
                _add_v3_literal(triples, uri, SCHEMA + "inLanguage", derived["language"])
                _add_v3_literal(triples, uri, DP + "sourceLanguage", derived["source_language"])
    return tuple(sorted(triples))


def projection_statement_v3_ntriples(
    payload: dict[str, Any], *, allow_statement_v3: bool = False,
) -> str:
    triples = projection_statement_v3_triples(payload, allow_statement_v3=allow_statement_v3)
    return "\n".join(triple.ntriples() for triple in triples) + ("\n" if triples else "")


def projection_statement_v3_jsonld(
    payload: dict[str, Any], *, allow_statement_v3: bool = False,
) -> dict[str, Any]:
    """Typed JSON-LD: only original is a Quotation; derived text is CreativeWork."""
    bundle = _statement_v3_bundle(payload, allow_statement_v3=allow_statement_v3)
    dataset_uri = public_resource_uri("dataset", bundle["dataset_sha256"])
    graph: list[dict[str, Any]] = [{
        "@id": dataset_uri,
        "@type": "Dataset",
        "version": bundle["schema_version"],
        "dateModified": bundle["generated_at"],
        "dp:projectionFingerprint": bundle["dataset_sha256"],
    }]
    for record in sorted(bundle["statements"], key=lambda s: (s["statement_id"], s["version_id"])):
        statement_uri = public_resource_uri("statement", record["statement_id"])
        speaker = {"@id": public_resource_uri("person", record["person_id"])}
        original: dict[str, Any] = {
            "@id": statement_uri,
            "@type": "Quotation",
            "identifier": record["statement_id"],
            "version": record["version_id"],
            "text": record["original_text"],
            "inLanguage": record["language"],
            "dateCreated": record["statement_date"],
            "dp:wordingType": "VERBATIM_ORIGINAL",
            "dp:quoteSha256": record["quote_sha256"],
            "dp:sourceSha256": record["source_sha256"],
            "dp:sourceVersion": record["source_version"],
            "dp:sourceKind": record["source_kind"],
            "dp:locator": dict(record["locator"]),
            "dp:speechAct": record["speech_act"],
            "dp:endorsed": record["endorsed"],
            "dp:recordedSpeaker": speaker,
            "isPartOf": {
                "@id": public_resource_uri("content", record["content_id"]),
                "@type": "CreativeWork",
                "name": record["source_title"],
                "url": record["source_url"],
            },
        }
        if record["endorsed"]:
            original["author"] = speaker
        if record["finding_id"] is not None:
            original["subjectOf"] = {"@id": public_resource_uri("finding", record["finding_id"])}
        derived_parts: list[dict[str, Any]] = []
        for kind in ("summary", "translation"):
            derived = record[kind]
            if derived is None:
                continue
            part: dict[str, Any] = {
                "@id": public_resource_uri("representation", f'{record["version_id"]}:{kind}'),
                "@type": "CreativeWork",
                "text": derived["text"],
                "dp:wordingType": derived["wording_type"],
                "dp:sourceQuoteSha256": derived["source_quote_sha256"],
                "isBasedOn": {"@id": statement_uri},
            }
            if kind == "translation":
                part["inLanguage"] = derived["language"]
                part["dp:sourceLanguage"] = derived["source_language"]
            derived_parts.append(part)
        if derived_parts:
            original["hasPart"] = derived_parts
        graph.append(original)
    return {
        "@context": {"@vocab": SCHEMA, "dp": DP},
        "@graph": graph,
    }


def projection_triples(payload: dict[str, Any]) -> tuple[Triple, ...]:
    bundle = validate_public_bundle(payload)
    triples: set[Triple] = set()
    dataset_uri = public_resource_uri("dataset", bundle["dataset_sha256"])

    _add_uri(triples, dataset_uri, RDF + "type", SCHEMA + "Dataset")
    _add_literal(triples, dataset_uri, SCHEMA + "version", bundle["schema_version"])
    _add_literal(triples, dataset_uri, SCHEMA + "dateModified", bundle["generated_at"])
    _add_literal(triples, dataset_uri, DP + "projectionFingerprint", bundle["dataset_sha256"])
    _add_literal(triples, dataset_uri, DP + "linkedDataVersion", LINKED_DATA_VERSION)

    # DP-434: Content is independently publishable from Finding. Emit reviewed
    # first-class Content before dossier-derived relations so a zero-finding
    # Content remains discoverable in RDF without inventing a Statement.
    for content in bundle.get("contents") or []:
        content_uri = public_resource_uri("content", content["content_id"])
        _add_uri(triples, dataset_uri, SCHEMA + "hasPart", content_uri)
        _add_uri(triples, content_uri, RDF + "type", SCHEMA + "CreativeWork")
        _add_literal(triples, content_uri, SCHEMA + "identifier", content["content_id"])
        _add_literal(triples, content_uri, SCHEMA + "name", content["title"])
        _add_literal(triples, content_uri, SCHEMA + "datePublished", content.get("published_at"))
        _add_uri(triples, content_uri, SCHEMA + "url", content["url"])
        _add_literal(triples, content_uri, DP + "contentKind", content["content_kind"])
        _add_literal(triples, content_uri, DP + "durationMs", content.get("duration_ms"))
        _add_literal(
            triples,
            content_uri,
            DP + "publicationVersion",
            content["publication_version"],
        )
        media_url = content.get("public_media_url")
        if media_url:
            _add_uri(triples, content_uri, SCHEMA + "contentUrl", media_url)
            _add_literal(
                triples,
                content_uri,
                DP + "mediaPolicyVersion",
                content.get("media_policy_version"),
            )

    for dossier in bundle.get("dossiers") or []:
        finding_uri = public_resource_uri("finding", dossier["finding_id"])
        statement_uri = public_resource_uri("statement", dossier["claim_id"])
        person_uri = public_resource_uri("person", dossier["speaker"]["id"])
        content_uri = public_resource_uri("content", dossier["source"]["content_id"])

        _add_uri(triples, dataset_uri, SCHEMA + "hasPart", finding_uri)

        _add_uri(triples, finding_uri, RDF + "type", SCHEMA + "ClaimReview")
        _add_uri(triples, finding_uri, SCHEMA + "itemReviewed", statement_uri)
        _add_literal(triples, finding_uri, SCHEMA + "claimReviewed", dossier.get("claim"))
        _add_literal(
            triples,
            finding_uri,
            SCHEMA + "datePublished",
            dossier["finding"].get("published_at"),
        )
        _add_literal(
            triples,
            finding_uri,
            DP + "assessment",
            dossier["finding"].get("assessment"),
        )
        _add_literal(
            triples,
            finding_uri,
            DP + "publicationStatus",
            dossier["finding"].get("publication_status"),
        )
        _add_literal(
            triples,
            finding_uri,
            DP + "policyVersion",
            dossier["finding"].get("policy_version"),
        )

        supersedes = dossier["finding"].get("supersedes_id")
        if supersedes:
            _add_uri(
                triples,
                finding_uri,
                PROV + "wasRevisionOf",
                public_resource_uri("finding", supersedes),
            )

        _add_uri(triples, statement_uri, RDF + "type", SCHEMA + "Claim")
        _add_literal(triples, statement_uri, SCHEMA + "text", dossier.get("claim"))
        _add_uri(triples, statement_uri, SCHEMA + "author", person_uri)
        _add_uri(triples, statement_uri, SCHEMA + "appearance", content_uri)
        wording = dossier.get("wording")
        if isinstance(wording, dict):
            source_wording = wording.get("source_occurrence") or {}
            normalized_wording = wording.get("normalized_claim") or {}
            occurrence_id = str(source_wording.get("occurrence_id") or "").strip()
            if occurrence_id:
                occurrence_uri = public_resource_uri("occurrence", occurrence_id)
                _add_uri(triples, statement_uri, PROV + "wasDerivedFrom", occurrence_uri)
                _add_uri(triples, occurrence_uri, RDF + "type", DP + "SourceOccurrence")
                _add_literal(
                    triples,
                    occurrence_uri,
                    DP + "wordingType",
                    source_wording.get("wording_type"),
                )
                _add_literal(
                    triples,
                    occurrence_uri,
                    DP + "representationRole",
                    source_wording.get("representation_role"),
                )
                _add_literal(
                    triples,
                    occurrence_uri,
                    DP + "directQuoteEligible",
                    str(bool(source_wording.get("direct_quote_eligible"))).lower(),
                )
                _add_literal(
                    triples,
                    occurrence_uri,
                    DP + "textSha256",
                    source_wording.get("text_sha256"),
                )
                _add_literal(
                    triples,
                    occurrence_uri,
                    SCHEMA + "inLanguage",
                    source_wording.get("language"),
                )
                public_provenance = wording.get("public_provenance") or {}
                for segment_id in public_provenance.get("segment_ids") or []:
                    _add_literal(
                        triples,
                        occurrence_uri,
                        DP + "sourceSegmentId",
                        segment_id,
                    )
                for provenance_id in public_provenance.get("text_provenance_ids") or []:
                    _add_literal(
                        triples,
                        occurrence_uri,
                        DP + "sourceTextProvenanceId",
                        provenance_id,
                    )

                _add_literal(
                    triples,
                    statement_uri,
                    DP + "wordingContractVersion",
                    wording.get("version"),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    DP + "wordingType",
                    normalized_wording.get("wording_type"),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    DP + "representationRole",
                    normalized_wording.get("representation_role"),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    DP + "directQuoteEligible",
                    str(bool(normalized_wording.get("direct_quote_eligible"))).lower(),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    DP + "sourceWordingType",
                    normalized_wording.get("source_wording_type"),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    DP + "textSha256",
                    normalized_wording.get("text_sha256"),
                )
                _add_literal(
                    triples,
                    statement_uri,
                    SCHEMA + "inLanguage",
                    normalized_wording.get("language"),
                )

                for representation in wording.get("representations") or []:
                    representation_hash = str(
                        representation.get("text_sha256") or ""
                    ).strip()
                    if not representation_hash:
                        continue
                    representation_uri = public_resource_uri(
                        "representation",
                        f"{dossier['claim_id']}:{representation_hash}",
                    )
                    _add_uri(
                        triples,
                        statement_uri,
                        DP + "hasRepresentation",
                        representation_uri,
                    )
                    _add_uri(
                        triples,
                        representation_uri,
                        RDF + "type",
                        DP + "WordingRepresentation",
                    )
                    _add_uri(
                        triples,
                        representation_uri,
                        PROV + "wasDerivedFrom",
                        occurrence_uri,
                    )
                    for predicate, value in (
                        ("wordingType", representation.get("wording_type")),
                        ("representationRole", representation.get("representation_role")),
                        ("textSha256", representation_hash),
                        ("sourceWordingType", representation.get("source_wording_type")),
                        ("sourceLanguage", representation.get("source_language")),
                        ("reviewState", representation.get("review_state")),
                        ("derivationMethod", representation.get("derivation_method")),
                        ("derivationVersion", representation.get("derivation_version")),
                    ):
                        _add_literal(
                            triples,
                            representation_uri,
                            DP + predicate,
                            value,
                        )
                    _add_literal(
                        triples,
                        representation_uri,
                        DP + "directQuoteEligible",
                        str(bool(representation.get("direct_quote_eligible"))).lower(),
                    )
                    _add_literal(
                        triples,
                        representation_uri,
                        SCHEMA + "inLanguage",
                        representation.get("language"),
                    )
                    for signal_code in representation.get("signal_codes") or []:
                        _add_literal(
                            triples,
                            representation_uri,
                            DP + "signalCode",
                            signal_code,
                        )

        _add_uri(triples, person_uri, RDF + "type", SCHEMA + "Person")
        _add_literal(
            triples,
            person_uri,
            SCHEMA + "name",
            dossier["speaker"].get("name") or dossier["speaker"]["id"],
        )
        for role in dossier["speaker"].get("public_roles") or []:
            organization_id = role.get("organization_id")
            if not organization_id:
                continue
            organization_uri = public_resource_uri("organization", organization_id)
            _add_uri(triples, person_uri, SCHEMA + "worksFor", organization_uri)
            _add_uri(triples, organization_uri, RDF + "type", SCHEMA + "Organization")
            _add_literal(
                triples,
                organization_uri,
                SCHEMA + "name",
                role.get("organization_name") or organization_id,
            )

        _add_uri(triples, content_uri, RDF + "type", SCHEMA + "CreativeWork")
        _add_literal(triples, content_uri, SCHEMA + "name", dossier["source"].get("title"))
        _add_literal(
            triples,
            content_uri,
            SCHEMA + "datePublished",
            dossier["source"].get("published_at"),
        )
        source_url = dossier["source"].get("url")
        if source_url:
            _add_uri(triples, content_uri, SCHEMA + "url", source_url)

        for evidence in dossier.get("evidence") or []:
            evidence_uri = public_resource_uri("evidence", evidence["id"])
            _add_uri(triples, finding_uri, SCHEMA + "citation", evidence_uri)
            _add_uri(triples, evidence_uri, RDF + "type", SCHEMA + "CreativeWork")
            _add_uri(triples, evidence_uri, SCHEMA + "url", evidence["url"])
            _add_literal(
                triples,
                evidence_uri,
                SCHEMA + "publisher",
                evidence.get("publisher"),
            )
            _add_literal(
                triples,
                evidence_uri,
                SCHEMA + "datePublished",
                evidence.get("publication_date"),
            )
            _add_literal(
                triples,
                evidence_uri,
                DP + "evidenceRelation",
                evidence.get("relation"),
            )
            _add_literal(
                triples,
                evidence_uri,
                DP + "referencePeriod",
                evidence.get("reference_period"),
            )

        for correction in dossier.get("corrections") or []:
            correction_uri = public_resource_uri("correction", correction["id"])
            _add_uri(triples, correction_uri, RDF + "type", SCHEMA + "CorrectionComment")
            _add_uri(triples, correction_uri, SCHEMA + "about", finding_uri)
            _add_literal(triples, correction_uri, SCHEMA + "text", correction.get("reason"))
            _add_literal(
                triples,
                correction_uri,
                SCHEMA + "dateCreated",
                correction.get("created_at"),
            )
            previous = correction.get("previous_finding_id")
            if previous:
                _add_uri(
                    triples,
                    finding_uri,
                    PROV + "wasRevisionOf",
                    public_resource_uri("finding", previous),
                )

    finding_to_statement = {
        dossier["finding_id"]: public_resource_uri("statement", dossier["claim_id"])
        for dossier in bundle.get("dossiers") or []
    }
    for topic in bundle.get("topics") or []:
        topic_uri = topic_public_uri(topic["slug"])
        _add_uri(triples, dataset_uri, SCHEMA + "about", topic_uri)
        _add_uri(triples, topic_uri, RDF + "type", SCHEMA + "Thing")
        _add_literal(triples, topic_uri, SCHEMA + "identifier", topic["topic_id"])
        _add_literal(triples, topic_uri, SCHEMA + "name", topic["canonical_name"])
        _add_literal(triples, topic_uri, SCHEMA + "description", topic.get("scope_text"))
        _add_literal(triples, topic_uri, DP + "entityVersion", topic["entity_version"])
        for membership in topic.get("memberships") or []:
            statement_uri = public_resource_uri("statement", membership["claim_id"])
            _add_uri(triples, topic_uri, SCHEMA + "about", statement_uri)
            for finding_id in membership["finding_ids"]:
                mapped = finding_to_statement.get(finding_id)
                if mapped == statement_uri:
                    _add_uri(
                        triples,
                        public_resource_uri("finding", finding_id),
                        SCHEMA + "about",
                        topic_uri,
                    )

    return tuple(sorted(triples))


def projection_ntriples(payload: dict[str, Any]) -> str:
    triples = projection_triples(payload)
    return "\n".join(triple.ntriples() for triple in triples) + ("\n" if triples else "")


def projection_linked_data_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = projection_ntriples(payload).encode("utf-8")
    return {
        "linked_data_version": LINKED_DATA_VERSION,
        "public_schema_version": payload["schema_version"],
        "projection_fingerprint": payload["dataset_sha256"],
        "ntriples_sha256": hashlib.sha256(encoded).hexdigest(),
        "byte_count": len(encoded),
        "triple_count": len(projection_triples(payload)),
    }


__all__ = [
    "DP",
    "LINKED_DATA_VERSION",
    "PROV",
    "PUBLIC_BASE_URL",
    "RDF",
    "RESOURCE_KINDS",
    "SCHEMA",
    "Triple",
    "projection_linked_data_receipt",
    "projection_ntriples",
    "projection_statement_v3_jsonld",
    "projection_statement_v3_ntriples",
    "projection_statement_v3_triples",
    "projection_triples",
    "public_resource_uri",
    "topic_public_uri",
]
