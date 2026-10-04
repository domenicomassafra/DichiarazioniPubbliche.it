from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dichiarazioni_pubbliche.domain_vocabulary import ClaimType


NON_FACTUAL_CLAIM_TYPES = frozenset(
    {ClaimType.RHETORICAL_GENERALIZATION, ClaimType.VALUE_JUDGMENT}
)


@dataclass(frozen=True)
class TemporalScope:
    statement_date: str | None
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(frozen=True)
class AtomicClaimV1:
    claim_id: str
    content_id: str
    normalized_claim: str
    claim_type: ClaimType
    temporal_scope: TemporalScope
    check_worthy: bool
    source_segment_ids: tuple[str, ...]
    source_text_provenance_ids: tuple[str, ...]
    metadata: dict[str, Any]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"CLAIM_{field.upper()}_REQUIRED")
    return value.strip()


def _iso_date(value: Any, field: str) -> str:
    value = _required_text(value, field)
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"CLAIM_{field.upper()}_INVALID")
    if not (value[:4].isdigit() and value[5:7].isdigit() and value[8:].isdigit()):
        raise ValueError(f"CLAIM_{field.upper()}_INVALID")
    return value


def _optional_date(value: Any, field: str) -> str | None:
    return None if value is None else _iso_date(value, field)


def validate_atomic_claim(
    *,
    claim_id: str,
    content_id: str,
    normalized_claim: str,
    claim_type: str | ClaimType,
    statement_date: str | None,
    valid_from: str | None = None,
    valid_until: str | None = None,
    check_worthy: bool,
    source_segment_ids: tuple[str, ...] = (),
    source_text_provenance_ids: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> AtomicClaimV1:
    claim_id = _required_text(claim_id, "id")
    if not claim_id.startswith("claim:"):
        raise ValueError("CLAIM_ID_INVALID")
    content_id = _required_text(content_id, "content_id")
    normalized_claim = _required_text(normalized_claim, "normalized_claim")
    if len(normalized_claim) > 4000:
        raise ValueError("CLAIM_NORMALIZED_CLAIM_TOO_LONG")
    try:
        kind = ClaimType(claim_type)
    except ValueError as exc:
        raise ValueError("CLAIM_TYPE_UNKNOWN") from exc
    if not isinstance(check_worthy, bool):
        raise ValueError("CLAIM_CHECK_WORTHY_INVALID")
    if kind in NON_FACTUAL_CLAIM_TYPES and check_worthy:
        raise ValueError("CLAIM_NON_FACTUAL_NOT_CHECK_WORTHY")
    invalid_segments = any(
        not isinstance(segment_id, str) or not segment_id.strip()
        for segment_id in source_segment_ids
    )
    invalid_text_provenance = any(
        not isinstance(provenance_id, str) or not provenance_id.strip()
        for provenance_id in source_text_provenance_ids
    )
    if invalid_segments or invalid_text_provenance:
        raise ValueError("CLAIM_PROVENANCE_INVALID")
    if not source_segment_ids and not source_text_provenance_ids:
        raise ValueError("CLAIM_SEGMENT_PROVENANCE_REQUIRED")
    statement = (
        _iso_date(statement_date, "statement_date")
        if statement_date is not None
        else None
    )
    start = _optional_date(valid_from, "valid_from")
    end = _optional_date(valid_until, "valid_until")
    if start and end and start > end:
        raise ValueError("CLAIM_TEMPORAL_SCOPE_INVALID")
    if start and statement and start > statement:
        raise ValueError("CLAIM_VALID_FROM_AFTER_STATEMENT")
    if end and statement and end < statement:
        raise ValueError("CLAIM_VALID_UNTIL_BEFORE_STATEMENT")
    return AtomicClaimV1(
        claim_id=claim_id,
        content_id=content_id,
        normalized_claim=normalized_claim,
        claim_type=kind,
        temporal_scope=TemporalScope(statement, start, end),
        check_worthy=check_worthy,
        source_segment_ids=tuple(sorted(set(source_segment_ids))),
        source_text_provenance_ids=tuple(sorted(set(source_text_provenance_ids))),
        metadata=dict(metadata or {}),
    )
