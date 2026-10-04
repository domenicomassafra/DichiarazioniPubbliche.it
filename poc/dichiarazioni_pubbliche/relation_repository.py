from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from dichiarazioni_pubbliche.domain_vocabulary import (
    RELATION_VERSION,
    RelationCandidateType,
)


INSERT_RELATION_CANDIDATE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO claim_relation_candidate (
        id, subject_claim_id, object_claim_id, relation_type,
        relation_version, status, confidence, rationale_codes,
        metadata
    ) VALUES (
        :'id', :'subject_claim_id', :'object_claim_id',
        :'relation_type', :'relation_version', :'status',
        NULLIF(:'confidence','')::numeric,
        :'rationale_codes'::jsonb, :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
)
SELECT EXISTS(SELECT 1 FROM inserted)::text;
""".strip()


ALLOWED_RELATION_CANDIDATE_STATUSES = frozenset({"CANDIDATE"})

FORBIDDEN_PUBLISHED_STATUSES = frozenset(
    {"PUBLISH", "PUBLISHED", "APPROVED", "VERIFIED", "ACTIVE"}
)

ALLOWED_RELATION_CANDIDATE_FIELDS = frozenset(
    {
        "id",
        "subject_claim_id",
        "object_claim_id",
        "relation_type",
        "relation_version",
        "status",
        "confidence",
        "rationale_codes",
        "metadata",
    }
)

REQUIRED_RELATION_CANDIDATE_FIELDS = frozenset(
    {
        "id",
        "subject_claim_id",
        "object_claim_id",
        "relation_type",
    }
)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RELATION_{field_name.upper()}_REQUIRED")
    return value.strip()


@dataclass(frozen=True)
class RelationCandidateRecord:
    id: str
    subject_claim_id: str
    object_claim_id: str
    relation_type: str
    relation_version: str = RELATION_VERSION
    status: str = "CANDIDATE"
    confidence: float | None = None
    rationale_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.subject_claim_id == self.object_claim_id:
            raise ValueError("RELATION_SELF_REFUSED")
        if self.relation_version != RELATION_VERSION:
            raise ValueError(
                f"RELATION_VERSION_MISMATCH: expected '{RELATION_VERSION}', got '{self.relation_version}'"
            )
        try:
            RelationCandidateType(self.relation_type)
        except ValueError as exc:
            raise ValueError(
                f"RELATION_TYPE_INVALID: '{self.relation_type}' is not a valid RelationCandidateType"
            ) from exc
        if self.status != "CANDIDATE":
            raise ValueError(
                f"RELATION_STATUS_INVALID: relation candidates are only ever persisted as candidates, cannot set '{self.status}'"
            )
        if self.confidence is not None:
            conf = float(self.confidence)
            if not 0.0 <= conf <= 1.0:
                raise ValueError(
                    f"RELATION_CONFIDENCE_OUT_OF_RANGE: confidence must be in [0.0, 1.0], got {conf}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_claim_id": self.subject_claim_id,
            "object_claim_id": self.object_claim_id,
            "relation_type": self.relation_type,
            "relation_version": self.relation_version,
            "status": self.status,
            "confidence": self.confidence,
            "rationale_codes": list(self.rationale_codes),
            "metadata": dict(self.metadata or {}),
        }


def normalize_relation_candidate_record(data: Any) -> RelationCandidateRecord:
    if isinstance(data, RelationCandidateRecord):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    elif not isinstance(data, Mapping):
        raise ValueError(
            f"RELATION_RECORD_INVALID_TYPE: expected Mapping or RelationCandidateRecord, got {type(data).__name__}"
        )

    unknown = set(data.keys()) - ALLOWED_RELATION_CANDIDATE_FIELDS
    if unknown:
        raise ValueError(
            f"RELATION_RECORD_UNKNOWN_FIELDS: unexpected key(s) {sorted(unknown)}"
        )

    missing = REQUIRED_RELATION_CANDIDATE_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"RELATION_RECORD_MISSING_FIELDS: missing required key(s) {sorted(missing)}"
        )

    cand_id = _required_str(data["id"], "id")
    subject_claim_id = _required_str(
        data["subject_claim_id"], "subject_claim_id"
    )
    object_claim_id = _required_str(data["object_claim_id"], "object_claim_id")
    if subject_claim_id == object_claim_id:
        raise ValueError("RELATION_SELF_REFUSED")

    rel_type_raw = data["relation_type"]
    try:
        if isinstance(rel_type_raw, RelationCandidateType):
            relation_type = rel_type_raw.value
        else:
            relation_type = RelationCandidateType(str(rel_type_raw)).value
    except ValueError as exc:
        raise ValueError(
            f"RELATION_TYPE_INVALID: '{rel_type_raw}' is not a valid RelationCandidateType"
        ) from exc

    relation_version = data.get("relation_version", RELATION_VERSION)
    if relation_version != RELATION_VERSION:
        raise ValueError(
            f"RELATION_VERSION_MISMATCH: expected '{RELATION_VERSION}', got '{relation_version}'"
        )

    status_raw = data.get("status")
    if status_raw is None or status_raw == "":
        status = "CANDIDATE"
    else:
        status_str = str(status_raw).strip()
        if status_str != "CANDIDATE":
            raise ValueError(
                f"RELATION_STATUS_INVALID: relation candidates are only ever persisted as candidates, cannot set '{status_str}'"
            )
        status = status_str

    conf_raw = data.get("confidence")
    confidence: float | None = None
    if conf_raw is not None and conf_raw != "":
        try:
            confidence = float(conf_raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"RELATION_CONFIDENCE_INVALID: '{conf_raw}' cannot be converted to float"
            ) from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                f"RELATION_CONFIDENCE_OUT_OF_RANGE: confidence must be in [0.0, 1.0], got {confidence}"
            )

    rationale_raw = data.get("rationale_codes", ())
    if not isinstance(rationale_raw, (list, tuple, set, frozenset)):
        raise ValueError(
            "RELATION_RATIONALE_CODES_INVALID: expected iterable of strings"
        )
    rationale_codes = tuple(str(code) for code in rationale_raw)

    metadata_raw = data.get("metadata", {})
    if metadata_raw is None:
        metadata: dict[str, Any] = {}
    elif isinstance(metadata_raw, Mapping):
        metadata = dict(metadata_raw)
    else:
        raise ValueError("RELATION_METADATA_INVALID: expected mapping or None")

    return RelationCandidateRecord(
        id=cand_id,
        subject_claim_id=subject_claim_id,
        object_claim_id=object_claim_id,
        relation_type=relation_type,
        relation_version=relation_version,
        status=status,
        confidence=confidence,
        rationale_codes=rationale_codes,
        metadata=metadata,
    )




def relation_candidate_to_sql_parameters(
    record: RelationCandidateRecord | Mapping[str, Any],
) -> dict[str, Any]:
    norm = normalize_relation_candidate_record(record)
    return {
        "id": norm.id,
        "subject_claim_id": norm.subject_claim_id,
        "object_claim_id": norm.object_claim_id,
        "relation_type": norm.relation_type,
        "relation_version": norm.relation_version,
        "status": norm.status,
        "confidence": "" if norm.confidence is None else str(norm.confidence),
        "rationale_codes": json.dumps(
            list(norm.rationale_codes),
            separators=(",", ":"),
        ),
        "metadata": json.dumps(
            norm.metadata or {},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


# Compatibility aliases retained by the module's public export surface.
RELATION_CANDIDATE_INSERT_STATEMENT_V1 = INSERT_RELATION_CANDIDATE_SQL_V1
normalize_relation_candidate = normalize_relation_candidate_record


__all__ = [
    "ALLOWED_RELATION_CANDIDATE_FIELDS",
    "ALLOWED_RELATION_CANDIDATE_STATUSES",
    "FORBIDDEN_PUBLISHED_STATUSES",
    "INSERT_RELATION_CANDIDATE_SQL_V1",
    "RELATION_CANDIDATE_INSERT_STATEMENT_V1",
    "REQUIRED_RELATION_CANDIDATE_FIELDS",
    "RelationCandidateRecord",
    "normalize_relation_candidate",
    "normalize_relation_candidate_record",
    "relation_candidate_to_sql_parameters",
]
