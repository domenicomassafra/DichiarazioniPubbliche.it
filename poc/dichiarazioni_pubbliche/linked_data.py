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
