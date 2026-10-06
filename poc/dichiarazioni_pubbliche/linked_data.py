from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from dichiarazioni_pubbliche.public_schema import validate_public_bundle


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
    "projection_triples",
    "public_resource_uri",
    "topic_public_uri",
]
