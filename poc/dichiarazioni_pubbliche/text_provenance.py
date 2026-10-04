from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


TEXT_PROVENANCE_VERSION = "text-source-provenance-v1"
ALLOWED_SELECTOR_TYPES = frozenset({"TEXT_QUOTE_HASH", "TEXT_POSITION_HASH"})
ALLOWED_ATTRIBUTION_METHODS = frozenset(
    {"SOURCE_BYLINE", "SOURCE_QUOTE", "ACCOUNT_OWNER", "OFFICIAL_RECORD", "MANUAL_REVIEW"}
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(value: str, field: str, *, optional: bool = False) -> str | None:
    normalized = str(value or "").strip().lower()
    if optional and not normalized:
        return None
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"TEXT_PROVENANCE_{field.upper()}_INVALID")
    return normalized


def deterministic_text_provenance_id(
    *,
    claim_id: str,
    content_id: str,
    person_id: str,
    selector_type: str,
    quote_sha256: str,
    start_char: int | None = None,
    end_char: int | None = None,
) -> str:
    material = {
        "claim_id": str(claim_id).strip(),
        "content_id": str(content_id).strip(),
        "person_id": str(person_id).strip(),
        "selector_type": selector_type,
        "quote_sha256": _sha256(quote_sha256, "quote_sha256"),
        "start_char": start_char,
        "end_char": end_char,
        "version": TEXT_PROVENANCE_VERSION,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return "text-provenance:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class TextProvenanceCandidate:
    candidate_id: str
    claim_id: str
    content_id: str
    person_id: str
    selector_type: str
    quote_sha256: str
    source_sha256: str | None
    start_char: int | None
    end_char: int | None
    attribution_method: str
    attribution_version: str
    source_ref: dict[str, Any]


def make_text_provenance_candidate(
    *,
    claim_id: str,
    content_id: str,
    person_id: str,
    selector_type: str,
    quote_sha256: str,
    source_sha256: str | None = None,
    start_char: int | None = None,
    end_char: int | None = None,
    attribution_method: str,
    source_ref: dict[str, Any] | None = None,
) -> TextProvenanceCandidate:
    for field, value in (
        ("claim_id", claim_id),
        ("content_id", content_id),
        ("person_id", person_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TEXT_PROVENANCE_{field.upper()}_REQUIRED")
    if selector_type not in ALLOWED_SELECTOR_TYPES:
        raise ValueError("TEXT_PROVENANCE_SELECTOR_TYPE_INVALID")
    if attribution_method not in ALLOWED_ATTRIBUTION_METHODS:
        raise ValueError("TEXT_PROVENANCE_ATTRIBUTION_METHOD_INVALID")
    quote_hash = _sha256(quote_sha256, "quote_sha256")
    source_hash = _sha256(source_sha256 or "", "source_sha256", optional=True)
    if (start_char is None) != (end_char is None):
        raise ValueError("TEXT_PROVENANCE_POSITION_PAIR_REQUIRED")
    if start_char is not None:
        if start_char < 0 or end_char is None or end_char <= start_char:
            raise ValueError("TEXT_PROVENANCE_POSITION_INVALID")
    if selector_type == "TEXT_POSITION_HASH" and start_char is None:
        raise ValueError("TEXT_PROVENANCE_POSITION_REQUIRED")
    ref = dict(source_ref or {})
    candidate_id = deterministic_text_provenance_id(
        claim_id=claim_id,
        content_id=content_id,
        person_id=person_id,
        selector_type=selector_type,
        quote_sha256=quote_hash or "",
        start_char=start_char,
        end_char=end_char,
    )
    return TextProvenanceCandidate(
        candidate_id=candidate_id,
        claim_id=claim_id.strip(),
        content_id=content_id.strip(),
        person_id=person_id.strip(),
        selector_type=selector_type,
        quote_sha256=quote_hash or "",
        source_sha256=source_hash,
        start_char=start_char,
        end_char=end_char,
        attribution_method=attribution_method,
        attribution_version=TEXT_PROVENANCE_VERSION,
        source_ref=ref,
    )


__all__ = [
    "ALLOWED_ATTRIBUTION_METHODS",
    "ALLOWED_SELECTOR_TYPES",
    "TEXT_PROVENANCE_VERSION",
    "TextProvenanceCandidate",
    "deterministic_text_provenance_id",
    "make_text_provenance_candidate",
]
