from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.domain_vocabulary import (
    CLAIM_TYPE_VERSION,
    ClaimType,
)


INSERT_ATOMIC_CLAIMS_SQL_V1 = (
    """
WITH input AS (
    SELECT *
    FROM jsonb_to_recordset({quoted}::jsonb) AS x(
        id text,
        content_id text,
        normalized_claim text,
        claim_type text,
        claim_type_version text,
        temporal_scope jsonb,
        check_worthy boolean,
        extraction_model text,
        extraction_version text,
        metadata jsonb,
        segment_ids jsonb
    )
),
inserted AS (
    INSERT INTO atomic_claim (
        id,
        content_id,
        normalized_claim,
        claim_type,
        claim_type_version,
        temporal_scope,
        check_worthy,
        extraction_model,
        extraction_version,
        metadata
    )
    SELECT
        id,
        content_id,
        normalized_claim,
        claim_type,
        '"""
    + CLAIM_TYPE_VERSION
    + """',
        COALESCE(temporal_scope, '{}'::jsonb),
        COALESCE(check_worthy, true),
        extraction_model,
        extraction_version,
        COALESCE(metadata, '{}'::jsonb)
    FROM input
    ON CONFLICT (id) DO NOTHING
    RETURNING id
),
replayed AS (
    SELECT claim.id
    FROM atomic_claim claim
    JOIN input ON input.id = claim.id
    WHERE claim.content_id = input.content_id
      AND claim.normalized_claim = input.normalized_claim
      AND claim.claim_type = input.claim_type
      AND claim.claim_type_version = '"""
    + CLAIM_TYPE_VERSION
    + """'
      AND claim.temporal_scope = COALESCE(input.temporal_scope, '{}'::jsonb)
      AND claim.check_worthy = COALESCE(input.check_worthy, true)
      AND claim.extraction_model IS NOT DISTINCT FROM input.extraction_model
      AND claim.extraction_version IS NOT DISTINCT FROM input.extraction_version
      AND claim.metadata = COALESCE(input.metadata, '{}'::jsonb)
),
replayed_only AS (
    SELECT id
    FROM replayed
    WHERE id NOT IN (SELECT id FROM inserted)
),
rejected AS (
    SELECT input.id
    FROM input
    LEFT JOIN inserted ON inserted.id = input.id
    LEFT JOIN replayed ON replayed.id = input.id
    WHERE inserted.id IS NULL AND replayed.id IS NULL
    RETURNING id
),
blocked AS (
    SELECT CASE WHEN count(*) > 0 THEN 1 ELSE 0 END AS has_rejected
    FROM input
),
linked AS (
    INSERT INTO claim_segment (claim_id, segment_id)
    SELECT
        input.id,
        segment.value
    FROM input
    JOIN inserted ON inserted.id = input.id
    CROSS JOIN LATERAL jsonb_array_elements_text(
        COALESCE(input.segment_ids, '[]'::jsonb)
    ) AS segment(value)
    JOIN canonical_transcript_segment canonical
        ON canonical.id = segment.value
        AND canonical.content_id = input.content_id
    ON CONFLICT DO NOTHING
    RETURNING claim_id
)
SELECT CASE
    WHEN (SELECT has_rejected FROM blocked) = 1 THEN 0
    ELSE (SELECT count(*) FROM replayed_only)::text
END;
"""
).strip()



CLAIM_COUNT_SQL_V1 = """
SELECT count(*)::text
FROM atomic_claim
WHERE content_id = :'content_id';
""".strip()



CLAIM_CONTEXT_SQL_V1 = """
SELECT COALESCE(json_build_object(
    'claim_id', claim.id,
    'content_id', claim.content_id,
    'normalized_claim', claim.normalized_claim,
    'claim_type', claim.claim_type,
    'temporal_scope', claim.temporal_scope,
    'metadata', claim.metadata,
    'statement_date', COALESCE(
        NULLIF(claim.temporal_scope->>'statement_date', ''),
        ''
    )
)::text, '')
FROM atomic_claim claim
JOIN content_item content ON content.id = claim.content_id
WHERE claim.id = :'claim_id';
""".strip()



NON_FACTUAL_CLAIM_TYPES = frozenset(
    {"RHETORICAL_GENERALIZATION", "VALUE_JUDGMENT"}
)

ALLOWED_ATOMIC_CLAIM_FIELDS = frozenset(
    {
        "id",
        "claim_id",
        "content_id",
        "normalized_claim",
        "claim_type",
        "claim_type_version",
        "temporal_scope",
        "check_worthy",
        "extraction_model",
        "extraction_version",
        "metadata",
        "segment_ids",
        "source_segment_ids",
        "source_text_provenance_ids",
    }
)

REQUIRED_ATOMIC_CLAIM_FIELDS = frozenset(
    {
        "id",
        "content_id",
        "normalized_claim",
        "claim_type",
        "segment_ids",
    }
)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ATOMIC_CLAIM_{field_name.upper()}_REQUIRED")
    return value.strip()


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"ATOMIC_CLAIM_{field_name.upper()}_INVALID")
    stripped = value.strip()
    return stripped if stripped else None


@dataclass(frozen=True)
class AtomicClaimRecord:
    id: str
    content_id: str
    normalized_claim: str
    claim_type: str
    segment_ids: tuple[str, ...]
    claim_type_version: str = CLAIM_TYPE_VERSION
    temporal_scope: dict[str, Any] = field(default_factory=dict)
    check_worthy: bool = True
    extraction_model: str | None = None
    extraction_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_str(self.id, "id")
        _required_str(self.content_id, "content_id")
        _required_str(self.normalized_claim, "normalized_claim")
        if self.claim_type_version != CLAIM_TYPE_VERSION:
            raise ValueError(
                f"ATOMIC_CLAIM_TYPE_VERSION_MISMATCH: expected '{CLAIM_TYPE_VERSION}', got '{self.claim_type_version}'"
            )
        try:
            ClaimType(self.claim_type)
        except ValueError as exc:
            raise ValueError(
                f"ATOMIC_CLAIM_TYPE_INVALID: '{self.claim_type}' is not a valid ClaimType"
            ) from exc
        if not isinstance(self.check_worthy, bool):
            raise ValueError("ATOMIC_CLAIM_CHECK_WORTHY_INVALID: check_worthy must be boolean")
        if self.claim_type in NON_FACTUAL_CLAIM_TYPES and self.check_worthy:
            raise ValueError(
                "ATOMIC_CLAIM_NON_FACTUAL_NOT_CHECK_WORTHY: non-factual claim types cannot be check_worthy"
            )
        if not self.segment_ids or not isinstance(self.segment_ids, tuple):
            raise ValueError("ATOMIC_CLAIM_SEGMENT_PROVENANCE_REQUIRED")
        for seg in self.segment_ids:
            if not isinstance(seg, str) or not seg.strip():
                raise ValueError("ATOMIC_CLAIM_SEGMENT_PROVENANCE_REQUIRED")
        if not isinstance(self.temporal_scope, Mapping):
            raise ValueError("ATOMIC_CLAIM_TEMPORAL_SCOPE_INVALID: must be a mapping")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("ATOMIC_CLAIM_METADATA_INVALID: must be a mapping")

    @property
    def claim_id(self) -> str:
        return self.id

    @property
    def source_segment_ids(self) -> tuple[str, ...]:
        return self.segment_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content_id": self.content_id,
            "normalized_claim": self.normalized_claim,
            "claim_type": self.claim_type,
            "claim_type_version": self.claim_type_version,
            "temporal_scope": dict(self.temporal_scope),
            "check_worthy": self.check_worthy,
            "extraction_model": self.extraction_model,
            "extraction_version": self.extraction_version,
            "metadata": dict(self.metadata),
            "segment_ids": list(self.segment_ids),
        }


def normalize_atomic_claim_record(data: Any) -> AtomicClaimRecord:
    if isinstance(data, AtomicClaimRecord):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    elif not isinstance(data, Mapping):
        raise ValueError(
            f"ATOMIC_CLAIM_RECORD_INVALID_TYPE: expected Mapping or AtomicClaimRecord, got {type(data).__name__}"
        )

    unknown = set(data.keys()) - ALLOWED_ATOMIC_CLAIM_FIELDS
    if unknown:
        raise ValueError(
            f"ATOMIC_CLAIM_RECORD_UNKNOWN_FIELDS: unexpected key(s) {sorted(unknown)}"
        )

    # Normalize aliases: claim_id -> id, source_segment_ids -> segment_ids.
    # Text provenance is a sibling persistence edge and is not inserted by this
    # transcript-oriented repository. An empty field is accepted when this record
    # originated from the shared AtomicClaim contract.
    raw_dict = dict(data)
    if "id" not in raw_dict and "claim_id" in raw_dict:
        raw_dict["id"] = raw_dict["claim_id"]
    if "segment_ids" not in raw_dict and "source_segment_ids" in raw_dict:
        raw_dict["segment_ids"] = raw_dict["source_segment_ids"]
    text_provenance_ids = raw_dict.pop("source_text_provenance_ids", ())
    if text_provenance_ids and not raw_dict.get("segment_ids"):
        raise ValueError(
            "ATOMIC_CLAIM_TEXT_PROVENANCE_SEPARATE_PERSISTENCE_REQUIRED"
        )

    missing = REQUIRED_ATOMIC_CLAIM_FIELDS - set(raw_dict.keys())
    if missing:
        raise ValueError(
            f"ATOMIC_CLAIM_RECORD_MISSING_FIELDS: missing required key(s) {sorted(missing)}"
        )

    claim_id = _required_str(raw_dict["id"], "id")
    content_id = _required_str(raw_dict["content_id"], "content_id")
    normalized_claim = _required_str(raw_dict["normalized_claim"], "normalized_claim")

    claim_type_raw = raw_dict["claim_type"]
    if isinstance(claim_type_raw, ClaimType):
        claim_type = claim_type_raw.value
    else:
        try:
            claim_type = ClaimType(str(claim_type_raw)).value
        except ValueError as exc:
            raise ValueError(
                f"ATOMIC_CLAIM_TYPE_INVALID: '{claim_type_raw}' is not a valid ClaimType"
            ) from exc

    claim_type_version = raw_dict.get("claim_type_version", CLAIM_TYPE_VERSION)
    if claim_type_version != CLAIM_TYPE_VERSION:
        raise ValueError(
            f"ATOMIC_CLAIM_TYPE_VERSION_MISMATCH: expected '{CLAIM_TYPE_VERSION}', got '{claim_type_version}'"
        )

    temporal_scope_raw = raw_dict.get("temporal_scope")
    if temporal_scope_raw is None:
        temporal_scope = {}
    elif isinstance(temporal_scope_raw, Mapping):
        temporal_scope = dict(temporal_scope_raw)
    elif hasattr(temporal_scope_raw, "__dataclass_fields__"):
        temporal_scope = asdict(temporal_scope_raw)
    else:
        raise ValueError("ATOMIC_CLAIM_TEMPORAL_SCOPE_INVALID: must be a mapping")

    check_worthy_raw = raw_dict.get("check_worthy", True)
    if not isinstance(check_worthy_raw, bool):
        raise ValueError("ATOMIC_CLAIM_CHECK_WORTHY_INVALID: check_worthy must be boolean")
    check_worthy = bool(check_worthy_raw)

    if claim_type in NON_FACTUAL_CLAIM_TYPES and check_worthy:
        raise ValueError(
            "ATOMIC_CLAIM_NON_FACTUAL_NOT_CHECK_WORTHY: non-factual claim types cannot be check_worthy"
        )

    extraction_model = _optional_str(raw_dict.get("extraction_model"), "extraction_model")
    extraction_version = _optional_str(raw_dict.get("extraction_version"), "extraction_version")

    metadata_raw = raw_dict.get("metadata")
    if metadata_raw is None:
        metadata = {}
    elif isinstance(metadata_raw, Mapping):
        metadata = dict(metadata_raw)
    else:
        raise ValueError("ATOMIC_CLAIM_METADATA_INVALID: must be a mapping")

    segment_ids_raw = raw_dict["segment_ids"]
    if not isinstance(segment_ids_raw, (list, tuple)):
        raise ValueError("ATOMIC_CLAIM_SEGMENT_IDS_INVALID: must be a list or tuple")
    items = []
    for s in segment_ids_raw:
        if not isinstance(s, str) or not s.strip():
            raise ValueError("ATOMIC_CLAIM_SEGMENT_PROVENANCE_REQUIRED")
        items.append(s.strip())
    if not items:
        raise ValueError("ATOMIC_CLAIM_SEGMENT_PROVENANCE_REQUIRED")
    segment_ids = tuple(items)

    return AtomicClaimRecord(
        id=claim_id,
        content_id=content_id,
        normalized_claim=normalized_claim,
        claim_type=claim_type,
        segment_ids=segment_ids,
        claim_type_version=claim_type_version,
        temporal_scope=temporal_scope,
        check_worthy=check_worthy,
        extraction_model=extraction_model,
        extraction_version=extraction_version,
        metadata=metadata,
    )




def render_insert_atomic_claims_sql(quoted_payload: str) -> str:
    return INSERT_ATOMIC_CLAIMS_SQL_V1.replace("{quoted}", quoted_payload)


def claims_to_json_payload(
    claims: Sequence[AtomicClaimRecord | Mapping[str, Any]],
) -> str:
    normalized = [normalize_atomic_claim_record(c).to_dict() for c in claims]
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


# Compatibility aliases retained by the module's public export surface.
ATOMIC_CLAIMS_INSERT_STATEMENT_V1 = INSERT_ATOMIC_CLAIMS_SQL_V1
CLAIM_CONTEXT_SQL = CLAIM_CONTEXT_SQL_V1
CLAIM_COUNT_SQL = CLAIM_COUNT_SQL_V1
INSERT_ATOMIC_CLAIMS_SQL = INSERT_ATOMIC_CLAIMS_SQL_V1


__all__ = [
    "ALLOWED_ATOMIC_CLAIM_FIELDS",
    "ATOMIC_CLAIMS_INSERT_STATEMENT_V1",
    "AtomicClaimRecord",
    "CLAIM_CONTEXT_SQL",
    "CLAIM_CONTEXT_SQL_V1",
    "CLAIM_COUNT_SQL",
    "CLAIM_COUNT_SQL_V1",
    "CLAIM_TYPE_VERSION",
    "INSERT_ATOMIC_CLAIMS_SQL",
    "INSERT_ATOMIC_CLAIMS_SQL_V1",
    "NON_FACTUAL_CLAIM_TYPES",
    "REQUIRED_ATOMIC_CLAIM_FIELDS",
    "claims_to_json_payload",
    "normalize_atomic_claim_record",
    "render_insert_atomic_claims_sql",
]
