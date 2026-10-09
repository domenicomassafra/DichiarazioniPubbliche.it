"""DP-233 synthetic/offline source-family execution seam.

This module deliberately stops before network/provider execution, database persistence,
verification, or publication.  It composes already-fetched Camera/Senato records through
the DP-233 normalizer, the amended-record DP-511/DP-227 bridge, and DP-305 rights policy.

The seam is fixture-only by construction so a local execution receipt cannot be mistaken
for a production source-family approval or a live-provider run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.parliamentary_amendment_revalidation import (
    ParliamentaryAmendmentRevalidation,
    build_reviewed_parliamentary_amendment,
)
from dichiarazioni_pubbliche.parliamentary_official_adapter import (
    ParliamentaryOfficialRecord,
    normalize_parliamentary_official_records,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (
    ExcerptDecision,
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
)


PARLIAMENTARY_SOURCE_FAMILY_EXECUTION_VERSION = (
    "parliamentary-source-family-execution-v1"
)

_SOURCE_FAMILIES = {
    "CAMERA_OFFICIAL": "CAMERA",
    "SENATO_OFFICIAL": "SENATO",
}


class ParliamentarySourceFamilyExecutionError(ValueError):
    pass


@dataclass(frozen=True)
class ParliamentarySourceFamilyManifest:
    execution_ref: str
    source_family: str
    chamber: str
    rights_status: RightsStatus | str = RightsStatus.UNKNOWN
    fixture_only: bool = True


@dataclass(frozen=True)
class ReviewedAmendmentInput:
    provider_id: str
    review_event_id: str
    review_action: str
    reviewed_entity_ref: str
    previous_observed_at: datetime
    current_observed_at: datetime
    as_of: date
    previous_valid_from: str
    previous_valid_until: str | None
    current_valid_from: str
    current_valid_until: str | None
    affected_claim_ids: tuple[str, ...]
    affected_finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParliamentarySourceFamilyRecordReceipt:
    statement_id: str
    record_id: str
    provenance_id: str
    source_version: str
    source_content_sha256: str
    state: str
    rights_status: str
    excerpt_disposition: str
    excerpt_reason_codes: tuple[str, ...]
    public_excerpt_prerequisite_satisfied: bool
    supersession_event_key: str | None = None
    hold_request_id: str | None = None
    reanalysis_request_id: str | None = None


@dataclass(frozen=True)
class ParliamentarySourceFamilyExecutionReceipt:
    execution_id: str
    execution_ref: str
    source_family: str
    chamber: str
    fixture_only: bool
    record_count: int
    new_record_count: int
    replay_record_count: int
    amended_record_count: int
    records: tuple[ParliamentarySourceFamilyRecordReceipt, ...]
    receipt_sha256: str = ""
    version: str = PARLIAMENTARY_SOURCE_FAMILY_EXECUTION_VERSION


def _text(value: object, field: str, *, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text:
        raise ParliamentarySourceFamilyExecutionError(
            f"PARLIAMENTARY_SOURCE_FAMILY_{field}_REQUIRED"
        )
    if len(text) > maximum or "\x00" in text:
        raise ParliamentarySourceFamilyExecutionError(
            f"PARLIAMENTARY_SOURCE_FAMILY_{field}_INVALID"
        )
    return text


def _rights(value: RightsStatus | str) -> RightsStatus:
    try:
        return value if isinstance(value, RightsStatus) else RightsStatus(str(value))
    except ValueError as exc:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_RIGHTS_STATUS_INVALID"
        ) from exc


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _normalized_records(
    rows: Iterable[Mapping[str, object]],
) -> tuple[ParliamentaryOfficialRecord, ...]:
    try:
        return normalize_parliamentary_official_records(rows)
    except ValueError as exc:
        raise ParliamentarySourceFamilyExecutionError(str(exc)) from exc


def _manifest(
    value: ParliamentarySourceFamilyManifest,
) -> tuple[str, str, str, RightsStatus]:
    execution_ref = _text(value.execution_ref, "EXECUTION_REF")
    source_family = _text(value.source_family, "SOURCE_FAMILY", maximum=64).upper()
    chamber = _text(value.chamber, "CHAMBER", maximum=16).upper()
    if not value.fixture_only:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_FIXTURE_ONLY_REQUIRED"
        )
    expected_chamber = _SOURCE_FAMILIES.get(source_family)
    if expected_chamber is None:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_UNSUPPORTED"
        )
    if chamber != expected_chamber:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_CHAMBER_MISMATCH"
        )
    return execution_ref, source_family, chamber, _rights(value.rights_status)


def _records_by_statement(
    rows: tuple[ParliamentaryOfficialRecord, ...],
    *,
    chamber: str,
) -> dict[str, ParliamentaryOfficialRecord]:
    output: dict[str, ParliamentaryOfficialRecord] = {}
    for row in rows:
        if row.session.chamber != chamber:
            raise ParliamentarySourceFamilyExecutionError(
                "PARLIAMENTARY_SOURCE_FAMILY_RECORD_CHAMBER_MISMATCH"
            )
        output[row.statement_id] = row
    return output


def _bind_excerpt_request(
    record: ParliamentaryOfficialRecord,
    request: ExcerptRequest,
    *,
    rights_status: RightsStatus,
) -> ExcerptRequest:
    expected = {
        "source_url": record.transcript.source_url,
        "content_id": record.record_id,
        "segment_id": record.statement_id,
        "transcript_variant_id": record.transcript.source_version,
        "source_content_sha256": record.transcript.transcript_sha256,
        "observed_source_sha256": record.transcript.transcript_sha256,
    }
    for field, expected_value in expected.items():
        actual = getattr(request, field)
        if str(actual or "").strip() != expected_value:
            raise ParliamentarySourceFamilyExecutionError(
                f"PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_{field.upper()}_MISMATCH"
            )
    # The source hash and statement ID bind provenance, not the caller's quote
    # text. Require a nonempty, literal contiguous slice of this statement's
    # official transcript span; do not casefold or normalize whitespace.
    excerpt = request.excerpt_text
    if (
        not isinstance(excerpt, str)
        or not excerpt.strip()
        or excerpt not in record.transcript.statement_text
    ):
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_TEXT_MISMATCH"
        )
    if record.video is not None:
        expected_start = record.video.start_ms / 1000
        expected_end = record.video.end_ms / 1000
        if (
            request.timestamp_start_seconds != expected_start
            or request.timestamp_end_seconds != expected_end
        ):
            raise ParliamentarySourceFamilyExecutionError(
                "PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_VIDEO_RANGE_MISMATCH"
            )
    return replace(request, rights_status=rights_status)


def _excerpt_result(
    *,
    record: ParliamentaryOfficialRecord,
    rights_status: RightsStatus,
    request: ExcerptRequest | None,
) -> tuple[ExcerptDecision | None, str, tuple[str, ...], bool]:
    if request is None:
        return None, "NOT_REQUESTED", ("RIGHTS_NOT_CLEARED",), False
    bound = _bind_excerpt_request(record, request, rights_status=rights_status)
    decision = decide_excerpt(bound)
    return (
        decision,
        decision.disposition.value,
        tuple(code.value for code in decision.codes),
        decision.allowed,
    )


def execute_parliamentary_source_family_fixture(
    *,
    manifest: ParliamentarySourceFamilyManifest,
    current_records: Iterable[Mapping[str, object]],
    previous_records: Iterable[Mapping[str, object]] = (),
    reviewed_amendments: Mapping[str, ReviewedAmendmentInput] | None = None,
    excerpt_requests: Mapping[str, ExcerptRequest] | None = None,
) -> ParliamentarySourceFamilyExecutionReceipt:
    """Execute a deterministic Camera/Senato fixture batch with no external I/O.

    Exact duplicate current rows dedupe through the canonical DP-233 normalizer.  If a
    previously-seen statement changes material, an explicit reviewed amendment input is
    mandatory and the existing DP-511/DP-227 bridge owns supersession, hold and reanalysis
    semantics.  Rights come from the source-family manifest and override caller excerpt
    requests, so a request cannot upgrade UNKNOWN/BLOCKED rights to CLEARED.
    """

    execution_ref, source_family, chamber, rights_status = _manifest(manifest)
    current = _normalized_records(current_records)
    previous = _normalized_records(previous_records)
    current_by_statement = _records_by_statement(current, chamber=chamber)
    previous_by_statement = _records_by_statement(previous, chamber=chamber)
    amendment_inputs = dict(reviewed_amendments or {})
    requests = dict(excerpt_requests or {})

    unknown_amendment_ids = set(amendment_inputs) - set(current_by_statement)
    if unknown_amendment_ids:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_AMENDMENT_INPUT_ORPHAN"
        )
    unknown_request_ids = set(requests) - set(current_by_statement)
    if unknown_request_ids:
        raise ParliamentarySourceFamilyExecutionError(
            "PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_REQUEST_ORPHAN"
        )

    receipts: list[ParliamentarySourceFamilyRecordReceipt] = []
    new_count = 0
    replay_count = 0
    amended_count = 0

    for statement_id in sorted(current_by_statement):
        row = current_by_statement[statement_id]
        old = previous_by_statement.get(statement_id)
        amendment: ParliamentaryAmendmentRevalidation | None = None
        state: str
        if old is None:
            if statement_id in amendment_inputs:
                raise ParliamentarySourceFamilyExecutionError(
                    "PARLIAMENTARY_SOURCE_FAMILY_AMENDMENT_WITHOUT_PREVIOUS"
                )
            state = "NEW"
            new_count += 1
        elif old.record_id == row.record_id:
            if statement_id in amendment_inputs:
                raise ParliamentarySourceFamilyExecutionError(
                    "PARLIAMENTARY_SOURCE_FAMILY_AMENDMENT_FOR_EXACT_REPLAY"
                )
            state = "REPLAY"
            replay_count += 1
        else:
            review = amendment_inputs.get(statement_id)
            if review is None:
                raise ParliamentarySourceFamilyExecutionError(
                    "PARLIAMENTARY_SOURCE_FAMILY_AMENDMENT_REVIEW_REQUIRED"
                )
            excerpt_request = requests.get(statement_id)
            bound_excerpt = (
                _bind_excerpt_request(row, excerpt_request, rights_status=rights_status)
                if excerpt_request is not None
                else None
            )
            amendment = build_reviewed_parliamentary_amendment(
                previous=old,
                current=row,
                previous_observed_at=review.previous_observed_at,
                current_observed_at=review.current_observed_at,
                as_of=review.as_of,
                provider_id=review.provider_id,
                review_event_id=review.review_event_id,
                review_action=review.review_action,
                reviewed_entity_ref=review.reviewed_entity_ref,
                previous_valid_from=review.previous_valid_from,
                previous_valid_until=review.previous_valid_until,
                current_valid_from=review.current_valid_from,
                current_valid_until=review.current_valid_until,
                affected_claim_ids=review.affected_claim_ids,
                affected_finding_ids=review.affected_finding_ids,
                excerpt_request=bound_excerpt,
            )
            state = "AMENDED"
            amended_count += 1

        excerpt_decision, excerpt_disposition, excerpt_codes, excerpt_ready = _excerpt_result(
            record=row,
            rights_status=rights_status,
            request=requests.get(statement_id),
        )
        if amendment is not None and amendment.excerpt_decision is not None:
            if amendment.excerpt_decision != excerpt_decision:
                raise ParliamentarySourceFamilyExecutionError(
                    "PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_DECISION_MISMATCH"
                )
            if amendment.public_excerpt_prerequisite_satisfied != excerpt_ready:
                raise ParliamentarySourceFamilyExecutionError(
                    "PARLIAMENTARY_SOURCE_FAMILY_EXCERPT_READINESS_MISMATCH"
                )

        receipts.append(
            ParliamentarySourceFamilyRecordReceipt(
                statement_id=row.statement_id,
                record_id=row.record_id,
                provenance_id=row.provenance_id,
                source_version=row.transcript.source_version,
                source_content_sha256=row.transcript.transcript_sha256,
                state=state,
                rights_status=rights_status.value,
                excerpt_disposition=excerpt_disposition,
                excerpt_reason_codes=excerpt_codes,
                public_excerpt_prerequisite_satisfied=excerpt_ready,
                supersession_event_key=(
                    amendment.revalidation.event_key if amendment is not None else None
                ),
                hold_request_id=(
                    amendment.hold_request.request_id if amendment is not None else None
                ),
                reanalysis_request_id=(
                    amendment.reanalysis_request.request_id
                    if amendment is not None
                    else None
                ),
            )
        )

    material = {
        "version": PARLIAMENTARY_SOURCE_FAMILY_EXECUTION_VERSION,
        "execution_ref": execution_ref,
        "source_family": source_family,
        "chamber": chamber,
        "fixture_only": True,
        "record_receipts": [asdict(row) for row in receipts],
    }
    execution_id = "parliamentary-source-family:" + _digest(material)
    receipt = ParliamentarySourceFamilyExecutionReceipt(
        execution_id=execution_id,
        execution_ref=execution_ref,
        source_family=source_family,
        chamber=chamber,
        fixture_only=True,
        record_count=len(receipts),
        new_record_count=new_count,
        replay_record_count=replay_count,
        amended_record_count=amended_count,
        records=tuple(receipts),
    )
    return replace(receipt, receipt_sha256=_digest(asdict(receipt)))


__all__ = [
    "PARLIAMENTARY_SOURCE_FAMILY_EXECUTION_VERSION",
    "ParliamentarySourceFamilyExecutionError",
    "ParliamentarySourceFamilyExecutionReceipt",
    "ParliamentarySourceFamilyManifest",
    "ParliamentarySourceFamilyRecordReceipt",
    "ReviewedAmendmentInput",
    "execute_parliamentary_source_family_fixture",
]
