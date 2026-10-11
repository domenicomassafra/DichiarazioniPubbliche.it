"""Isolated DP-436 v3 consumer parity gate for *already approved* projections.

This pure, explicit opt-in check validates the current API, JSON-LD and N-Triples
serializers against the same bounded public Statement snapshot. It never grants
publication rights, creates a live endpoint or reads private source material.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from dichiarazioni_pubbliche.linked_data import (
    DP,
    PROV,
    RDF,
    SCHEMA,
    projection_statement_v3_jsonld,
    projection_statement_v3_ntriples,
    public_resource_uri,
)
from dichiarazioni_pubbliche.public_api import (
    PublicApiError,
    list_public_statements_v3,
)
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
)


class PublicV3ConsumerParityError(ValueError):
    """Projection or consumer mismatch. Deliberately excludes private inputs."""


def _canonical(value: Any) -> bytes:
    """Strict JSON comparison rejects bool/int substitution and extra keys."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _same(actual: Any, expected: Any, *, surface: str) -> None:
    try:
        equal = _canonical(actual) == _canonical(expected)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise PublicV3ConsumerParityError(
            f"DP-436 {surface}: malformed serialization"
        ) from exc
    if not equal:
        raise PublicV3ConsumerParityError(
            f"DP-436 {surface}: source/version/format mismatch"
        )


def _expected_api(record: dict[str, Any]) -> dict[str, Any]:
    derived: dict[str, dict[str, Any] | None] = {}
    for kind in ("summary", "translation"):
        value = record[kind]
        if value is None:
            derived[kind] = None
            continue
        representation = {
            "wording_type": value["wording_type"],
            "text": value["text"],
            "source_quote_sha256": value["source_quote_sha256"],
        }
        if kind == "translation":
            representation.update(
                {
                    "language": value["language"],
                    "source_language": value["source_language"],
                }
            )
        derived[kind] = representation
    return {
        "statement_id": record["statement_id"],
        "version_id": record["version_id"],
        "statement_date": record["statement_date"],
        "person": {"id": record["person_id"], "name": record["speaker_name"]},
        "source": {
            "content_id": record["content_id"],
            "title": record["source_title"],
            "url": record["source_url"],
            "version_id": record["source_version"],
            "sha256": record["source_sha256"],
            "kind": record["source_kind"],
        },
        "original": {
            "wording_type": "VERBATIM_ORIGINAL",
            "text": record["original_text"],
            "language": record["language"],
            "quote_sha256": record["quote_sha256"],
            "locator": record["locator"],
        },
        "speech_act": record["speech_act"],
        "endorsed": record["endorsed"],
        "finding_id": record["finding_id"],
        **derived,
    }


def _expected_jsonld(record: dict[str, Any]) -> dict[str, Any]:
    statement_uri = public_resource_uri("statement", record["statement_id"])
    person = {"@id": public_resource_uri("person", record["person_id"])}
    original = {
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
        "dp:locator": record["locator"],
        "dp:speechAct": record["speech_act"],
        "dp:endorsed": record["endorsed"],
        "dp:recordedSpeaker": person,
        "isPartOf": {
            "@id": public_resource_uri("content", record["content_id"]),
            "@type": "CreativeWork",
            "name": record["source_title"],
            "url": record["source_url"],
        },
    }
    if record["endorsed"]:
        original["author"] = person
    if record["finding_id"] is not None:
        original["subjectOf"] = {
            "@id": public_resource_uri("finding", record["finding_id"]),
        }
    parts = []
    for kind in ("summary", "translation"):
        value = record[kind]
        if value is None:
            continue
        part = {
            "@id": public_resource_uri(
                "representation", f"{record['version_id']}:{kind}"
            ),
            "@type": "CreativeWork",
            "text": value["text"],
            "dp:wordingType": kind.upper(),
            "dp:sourceQuoteSha256": record["quote_sha256"],
            "isBasedOn": {"@id": statement_uri},
        }
        if kind == "translation":
            part["inLanguage"] = value["language"]
            part["dp:sourceLanguage"] = record["language"]
        parts.append(part)
    if parts:
        original["hasPart"] = parts
    return original


def _rdf_literal(value: object) -> str:
    raw = str(value)
    escaped = "".join(
        {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}.get(
            char,
            f"\\u{ord(char):04X}" if ord(char) < 32 or ord(char) == 127 else char,
        )
        for char in raw
    )
    return f'"{escaped}"'


def _rdf_statement(subject: str, predicate: str, obj: str, *, iri: bool = False) -> str:
    return f"<{subject}> <{predicate}> {f'<{obj}>' if iri else _rdf_literal(obj)} ."


def _verify_rdf_contract(bundle: dict[str, Any], ntriples: str) -> None:
    """Check critical triples independently of the linked-data serializer."""
    lines = ntriples.splitlines()
    if not lines or len(lines) != len(set(lines)) or lines != sorted(lines):
        raise PublicV3ConsumerParityError(
            "DP-436 RDF: noncanonical or duplicate triples"
        )
    line_set = set(lines)

    def require(subject: str, predicate: str, obj: str, *, iri: bool = False) -> None:
        if _rdf_statement(subject, predicate, obj, iri=iri) not in line_set:
            raise PublicV3ConsumerParityError(
                "DP-436 RDF: missing binding or source wording"
            )

    dataset_uri = public_resource_uri("dataset", bundle["dataset_sha256"])
    require(dataset_uri, DP + "projectionFingerprint", bundle["dataset_sha256"])
    require(dataset_uri, SCHEMA + "version", bundle["schema_version"])
    expected_quotes = set()
    for record in bundle["statements"]:
        uri = public_resource_uri("statement", record["statement_id"])
        expected_quotes.add(
            _rdf_statement(uri, RDF + "type", SCHEMA + "Quotation", iri=True)
        )
        require(dataset_uri, SCHEMA + "hasPart", uri, iri=True)
        require(uri, SCHEMA + "identifier", record["statement_id"])
        require(uri, SCHEMA + "version", record["version_id"])
        require(uri, SCHEMA + "text", record["original_text"])
        require(uri, SCHEMA + "inLanguage", record["language"])
        require(uri, DP + "wordingType", "VERBATIM_ORIGINAL")
        require(uri, DP + "quoteSha256", record["quote_sha256"])
        require(uri, DP + "sourceSha256", record["source_sha256"])
        require(uri, DP + "sourceVersion", record["source_version"])
        require(uri, DP + "sourceKind", record["source_kind"])
        require(
            uri,
            DP + "recordedSpeaker",
            public_resource_uri("person", record["person_id"]),
            iri=True,
        )
        require(
            uri,
            SCHEMA + "isPartOf",
            public_resource_uri("content", record["content_id"]),
            iri=True,
        )
        for field, predicate in (
            ("start_char", "startChar"),
            ("end_char", "endChar"),
            ("segment_id", "segmentId"),
            ("start_ms", "startMs"),
            ("end_ms", "endMs"),
        ):
            if field in record["locator"]:
                require(uri, DP + predicate, record["locator"][field])
        for kind in ("summary", "translation"):
            derived = record[kind]
            if derived is None:
                continue
            derived_uri = public_resource_uri(
                "representation", f"{record['version_id']}:{kind}"
            )
            require(uri, SCHEMA + "hasPart", derived_uri, iri=True)
            require(derived_uri, RDF + "type", SCHEMA + "CreativeWork", iri=True)
            require(derived_uri, DP + "wordingType", kind.upper())
            require(derived_uri, SCHEMA + "text", derived["text"])
            require(derived_uri, DP + "sourceQuoteSha256", record["quote_sha256"])
            require(derived_uri, PROV + "wasDerivedFrom", uri, iri=True)
            if kind == "translation":
                require(derived_uri, SCHEMA + "inLanguage", derived["language"])
                require(derived_uri, DP + "sourceLanguage", record["language"])
    rdf_quotes = {
        line
        for line in lines
        if line.endswith(f"<{SCHEMA}Quotation> .") and f" <{RDF}type> " in line
    }
    if rdf_quotes != expected_quotes:
        raise PublicV3ConsumerParityError(
            "DP-436 RDF: unexpected quoted representation"
        )


def verify_public_v3_consumer_parity(
    bundle: dict[str, Any],
    *,
    allow_statement_v3: bool = False,
    api_payload: dict[str, Any] | None = None,
    jsonld_payload: dict[str, Any] | None = None,
    ntriples_payload: str | None = None,
) -> dict[str, Any]:
    """Fail closed on any mismatch among a single v3 projection and its three readers.

    Optional caller-supplied artifacts are checked verbatim; omitted ones come
    from the existing pure serializers. The returned metadata is a local test
    receipt, **never** a publication or legal-rights authorization.
    """
    if not allow_statement_v3 or not isinstance(bundle, dict):
        raise PublicV3ConsumerParityError(
            "DP-436 requires explicit Statement v3 opt-in"
        )
    if bundle.get("schema_version") != PUBLIC_STATEMENT_SCHEMA_VERSION:
        raise PublicV3ConsumerParityError("DP-436 incompatible public schema version")
    try:
        validate_public_bundle(bundle, allow_statement_v3=True)
        if projection_dataset_sha256(bundle) != bundle["dataset_sha256"]:
            raise PublicV3ConsumerParityError("DP-436 stale dataset fingerprint")
        if api_payload is None:
            api_payload = list_public_statements_v3(bundle, allow_statement_v3=True)
        if jsonld_payload is None:
            jsonld_payload = projection_statement_v3_jsonld(
                bundle, allow_statement_v3=True
            )
        if ntriples_payload is None:
            ntriples_payload = projection_statement_v3_ntriples(
                bundle, allow_statement_v3=True
            )

        ordered = sorted(
            bundle["statements"],
            key=lambda row: (row["statement_id"], row["version_id"]),
        )
        expected_api = {
            "meta": {
                "public_schema_version": bundle["schema_version"],
                "dataset_sha256": bundle["dataset_sha256"],
                "generated_at": bundle["generated_at"],
                "count": len(ordered),
            },
            "data": [_expected_api(row) for row in ordered],
        }
        _same(api_payload, expected_api, surface="API")
        expected_jsonld = {
            "@context": {"@vocab": SCHEMA, "dp": DP},
            "@graph": [
                {
                    "@id": public_resource_uri("dataset", bundle["dataset_sha256"]),
                    "@type": "Dataset",
                    "version": bundle["schema_version"],
                    "dateModified": bundle["generated_at"],
                    "dp:projectionFingerprint": bundle["dataset_sha256"],
                },
                *[_expected_jsonld(row) for row in ordered],
            ],
        }
        _same(jsonld_payload, expected_jsonld, surface="JSON-LD")
        if type(ntriples_payload) is not str:
            raise PublicV3ConsumerParityError("DP-436 RDF: invalid payload")
        if ntriples_payload != projection_statement_v3_ntriples(
            bundle, allow_statement_v3=True
        ):
            raise PublicV3ConsumerParityError("DP-436 RDF: stale or unexpected triples")
        _verify_rdf_contract(bundle, ntriples_payload)
        return {
            "public_schema_version": bundle["schema_version"],
            "dataset_sha256": bundle["dataset_sha256"],
            "statement_count": len(ordered),
            "statement_versions": [
                {
                    "statement_id": row["statement_id"],
                    "version_id": row["version_id"],
                    "quote_sha256": hashlib.sha256(
                        row["original_text"].encode("utf-8")
                    ).hexdigest(),
                    "source_sha256": row["source_sha256"],
                }
                for row in ordered
            ],
        }
    except (PublicSchemaValidationError, PublicApiError, KeyError, TypeError) as exc:
        raise PublicV3ConsumerParityError(
            "DP-436 source/consumer validation unavailable"
        ) from exc


__all__ = ["PublicV3ConsumerParityError", "verify_public_v3_consumer_parity"]
