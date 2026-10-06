"""DP-233 bridge for reviewed amendments of official parliamentary records.

The seam is intentionally pure. It composes the existing DP-233 official-record
normalizer with canonical DP-511 source revalidation/hold and DONE DP-227
supersession/reanalysis contracts. It neither persists work nor changes publication
state. DP-305 excerpt rights remain an independent prerequisite and are never inferred
from an official-source label or an amendment review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.parliamentary_official_adapter import (
    ParliamentaryOfficialRecord,
    normalize_parliamentary_official_record,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (
    ExcerptDecision,
    ExcerptRequest,
    decide_excerpt,
)
from dichiarazioni_pubbliche.source_revalidation import (
    RevalidationDecision,
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (
    SourceRevalidationHoldRequest,
    build_source_revalidation_hold_request,
)
from dichiarazioni_pubbliche.supersession_reanalysis import (
    ReviewedSupersessionReanalysisRequest,
    build_reviewed_supersession_reanalysis_request,
)


PARLIAMENTARY_AMENDMENT_REVALIDATION_VERSION = (
    "parliamentary-amendment-revalidation-v1"
)


class ParliamentaryAmendmentError(ValueError):
    pass


@dataclass(frozen=True)
class ParliamentaryAmendmentRevalidation:
    statement_id: str
    previous_record_id: str
    current_record_id: str
    previous_transcript_version: str
    current_transcript_version: str
    previous_transcript_sha256: str
    current_transcript_sha256: str
    previous_valid_from: str
    previous_valid_until: str | None
    current_valid_from: str
    current_valid_until: str | None
    revalidation: RevalidationDecision
    hold_request: SourceRevalidationHoldRequest
    reanalysis_request: ReviewedSupersessionReanalysisRequest
    excerpt_decision: ExcerptDecision | None
    public_excerpt_prerequisite_satisfied: bool
    version: str = PARLIAMENTARY_AMENDMENT_REVALIDATION_VERSION


def _record(value: ParliamentaryOfficialRecord | Mapping[str, object]) -> ParliamentaryOfficialRecord:
    if isinstance(value, ParliamentaryOfficialRecord):
        return value
    if not isinstance(value, Mapping):
        raise ParliamentaryAmendmentError("PARLIAMENTARY_AMENDMENT_RECORD_INVALID")
    try:
        return normalize_parliamentary_official_record(value)
    except ValueError as exc:
        raise ParliamentaryAmendmentError(str(exc)) from exc


def _aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ParliamentaryAmendmentError(
            f"PARLIAMENTARY_AMENDMENT_{field}_TZ_REQUIRED"
        )
    return value


def _amendment_snapshots(
    *,
    previous: ParliamentaryOfficialRecord | Mapping[str, object],
    current: ParliamentaryOfficialRecord | Mapping[str, object],
    previous_observed_at: datetime,
    current_observed_at: datetime,
) -> tuple[
    ParliamentaryOfficialRecord,
    ParliamentaryOfficialRecord,
    SourceSnapshot,
    SourceSnapshot,
]:
    old = _record(previous)
    new = _record(current)
    old_observed = _aware(previous_observed_at, "PREVIOUS_OBSERVED_AT")
    new_observed = _aware(current_observed_at, "CURRENT_OBSERVED_AT")

    if old.statement_id != new.statement_id:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_STATEMENT_ID_MISMATCH"
        )
    if old.session.chamber != new.session.chamber:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_CHAMBER_MISMATCH"
        )
    if old.session.sitting_id != new.session.sitting_id:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_SITTING_MISMATCH"
        )
    if old.speaker.speaker_id != new.speaker.speaker_id:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_SPEAKER_MISMATCH"
        )
    if old.transcript.source_version == new.transcript.source_version:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_NEW_SOURCE_VERSION_REQUIRED"
        )

    previous_snapshot = SourceSnapshot(
        source_id=old.statement_id,
        observed_at=old_observed,
        availability="AVAILABLE",
        content_sha256=old.transcript.transcript_sha256,
        source_version=old.transcript.source_version,
        etag=None,
        canonical_url=old.transcript.source_url,
        rights_status="UNKNOWN",
        metadata={"parliamentary_record_id": old.record_id},
    )
    current_snapshot = SourceSnapshot(
        source_id=new.statement_id,
        observed_at=new_observed,
        availability="AVAILABLE",
        content_sha256=new.transcript.transcript_sha256,
        source_version=new.transcript.source_version,
        etag=None,
        canonical_url=new.transcript.source_url,
        supersedes_version=old.transcript.source_version,
        rights_status="UNKNOWN",
        metadata={"parliamentary_record_id": new.record_id},
    )
    return old, new, previous_snapshot, current_snapshot


def evaluate_parliamentary_amendment(
    *,
    previous: ParliamentaryOfficialRecord | Mapping[str, object],
    current: ParliamentaryOfficialRecord | Mapping[str, object],
    previous_observed_at: datetime,
    current_observed_at: datetime,
    as_of: date,
) -> RevalidationDecision:
    """Return the exact DP-511 decision that must be reviewed before reanalysis."""

    _, _, previous_snapshot, current_snapshot = _amendment_snapshots(
        previous=previous,
        current=current,
        previous_observed_at=previous_observed_at,
        current_observed_at=current_observed_at,
    )
    return evaluate_reobservation(
        previous_snapshot,
        current_snapshot,
        as_of=as_of,
        load_bearing_for_quote=True,
        load_bearing_for_speaker=True,
        load_bearing_for_evidence=True,
    )


def build_reviewed_parliamentary_amendment(
    *,
    previous: ParliamentaryOfficialRecord | Mapping[str, object],
    current: ParliamentaryOfficialRecord | Mapping[str, object],
    previous_observed_at: datetime,
    current_observed_at: datetime,
    as_of: date,
    provider_id: str,
    review_event_id: str,
    review_action: str,
    reviewed_entity_ref: str | None,
    previous_valid_from: str,
    previous_valid_until: str | None,
    current_valid_from: str,
    current_valid_until: str | None,
    affected_claim_ids: Iterable[str],
    affected_finding_ids: Iterable[str] = (),
    excerpt_request: ExcerptRequest | None = None,
) -> ParliamentaryAmendmentRevalidation:
    """Compose one reviewed amendment into DP-511 hold + DP-227 reanalysis input.

    `reviewed_entity_ref` must be the exact DP-511 event key. Passing ``None`` is
    permitted only to make the fail-closed mismatch explicit in the canonical DP-227
    builder; this bridge never invents review approval or a review target.

    DP-305 is evaluated only when an explicit `ExcerptRequest` is supplied. Absence of
    that request means the public-excerpt prerequisite is unsatisfied, not implicitly
    cleared.
    """

    old, new, previous_snapshot, current_snapshot = _amendment_snapshots(
        previous=previous,
        current=current,
        previous_observed_at=previous_observed_at,
        current_observed_at=current_observed_at,
    )
    decision = evaluate_reobservation(
        previous_snapshot,
        current_snapshot,
        as_of=as_of,
        load_bearing_for_quote=True,
        load_bearing_for_speaker=True,
        load_bearing_for_evidence=True,
    )
    hold_request = build_source_revalidation_hold_request(
        decision=decision,
        previous=previous_snapshot,
        current=current_snapshot,
        provider_id=provider_id,
    )
    if hold_request is None:
        raise ParliamentaryAmendmentError(
            "PARLIAMENTARY_AMENDMENT_TARGETED_HOLD_REQUIRED"
        )
    reanalysis = build_reviewed_supersession_reanalysis_request(
        decision=decision,
        previous=previous_snapshot,
        current=current_snapshot,
        review_event_id=review_event_id,
        review_action=review_action,
        reviewed_entity_ref=(reviewed_entity_ref or ""),
        previous_valid_from=previous_valid_from,
        previous_valid_until=previous_valid_until,
        current_valid_from=current_valid_from,
        current_valid_until=current_valid_until,
        affected_claim_ids=affected_claim_ids,
        affected_finding_ids=affected_finding_ids,
    )

    excerpt_decision = decide_excerpt(excerpt_request) if excerpt_request is not None else None
    return ParliamentaryAmendmentRevalidation(
        statement_id=old.statement_id,
        previous_record_id=old.record_id,
        current_record_id=new.record_id,
        previous_transcript_version=reanalysis.previous.version_id,
        current_transcript_version=reanalysis.current.version_id,
        previous_transcript_sha256=reanalysis.previous.content_sha256,
        current_transcript_sha256=reanalysis.current.content_sha256,
        previous_valid_from=reanalysis.previous.valid_from,
        previous_valid_until=reanalysis.previous.valid_until,
        current_valid_from=reanalysis.current.valid_from,
        current_valid_until=reanalysis.current.valid_until,
        revalidation=decision,
        hold_request=hold_request,
        reanalysis_request=reanalysis,
        excerpt_decision=excerpt_decision,
        public_excerpt_prerequisite_satisfied=(
            excerpt_decision.allowed if excerpt_decision is not None else False
        ),
    )


__all__ = [
    "PARLIAMENTARY_AMENDMENT_REVALIDATION_VERSION",
    "ParliamentaryAmendmentError",
    "ParliamentaryAmendmentRevalidation",
    "build_reviewed_parliamentary_amendment",
    "evaluate_parliamentary_amendment",
]
