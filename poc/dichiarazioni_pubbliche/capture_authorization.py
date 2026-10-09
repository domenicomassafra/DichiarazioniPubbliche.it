"""Operator-only, fail-closed rights gate for private Content Capture.

An ingestion-relevance permit establishes privacy relevance, NOT processing
rights. A persisted, current, specifically bound private rights record with a
reviewed permission to capture must independently authorize operator fetches.
This module does not authorize public excerpts, verification or publication.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Mapping, Any

from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.rights_registry import (
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
)


PRIVATE_CAPTURE_USE = "RESEARCH_CAPTURE_PRIVATE"


class PrivateCaptureAuthorizationBlocked(RuntimeError):
    """A stable error code, never a rights receipt or source body."""


def require_private_capture_rights(
    record: PrivateRightsRecord | None,
    *,
    rights_record_id: str,
    content_id: str,
    canonical_url: str,
    source_family: str,
    now: datetime | None = None,
) -> None:
    if record is None:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_MISSING")
    if record.id != rights_record_id or record.version_state != "CURRENT":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_NOT_CURRENT")
    if record.record_version != PRIVATE_RIGHTS_RECORD_VERSION or record.record_visibility != "PRIVATE":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_CONTRACT_INVALID")
    if (
        record.content_id != content_id
        or record.source_family != source_family
        or record.locator_kind != "URL"
        or record.evidence_id is not None
        or record.passage_id is not None
        or record.transcript_segment_id is not None
        or record.canonical_segment_id is not None
    ):
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_SCOPE_MISMATCH")
    try:
        expected = canonical_content_url(canonical_url)
        actual = canonical_content_url(record.locator_value)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_URL_INVALID") from exc
    if actual != expected:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_URL_MISMATCH")
    if record.rights_status != "CLEARED":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_NOT_CLEARED")
    if PRIVATE_CAPTURE_USE not in record.permitted_uses:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_USE_NOT_PERMITTED")
    if not record.rights_receipt_ref or not record.reviewer_ref or not record.reviewed_at:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_REVIEW_INCOMPLETE")
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("PRIVATE_CAPTURE_CLOCK_NOT_AWARE")
    try:
        reviewed = datetime.fromisoformat(record.reviewed_at.replace("Z", "+00:00"))
        expires = (
            datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
            if record.expires_at else None
        )
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_DATE_INVALID") from exc
    if reviewed.tzinfo is None or reviewed > reference_time:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_REVIEW_DATE_INVALID")
    if expires is not None and (expires.tzinfo is None or expires <= reference_time):
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_EXPIRED")


def require_operator_capture_content(
    state: Mapping[str, Any] | None,
    *,
    content_id: str,
    canonical_url: str,
) -> None:
    """Independent content/collection gate; no paused research pilot is bypassed."""
    if not state or state.get("id") != content_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_MISSING")
    try:
        actual_url = canonical_content_url(state.get("canonical_url"))
        expected_url = canonical_content_url(canonical_url)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_URL_INVALID") from exc
    if actual_url != expected_url:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_URL_MISMATCH")
    if state.get("rights_status") != "CLEARED":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_RIGHTS_NOT_CLEARED")
    inactive = state.get("inactive_collection_count")
    forbidden = state.get("forbidden_membership_count")
    # These are PostgreSQL COUNT(*) aggregates. A missing/malformed field is
    # unknown safety state, never evidence of zero blocking memberships.
    if (type(inactive) is not int or inactive < 0
            or type(forbidden) is not int or forbidden < 0):
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_SAFETY_COUNTS_INVALID")
    if inactive:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_COLLECTION_NOT_ACTIVE")
    if forbidden:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_COLLECTION_CAPTURE_FORBIDDEN")


def private_capture_rights_guard(
    *,
    read_current: Callable[[RightsSubject], PrivateRightsRecord | None],
    rights_record_id: str,
    content_id: str,
    canonical_url: str,
    source_family: str,
    read_content_state: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> Callable[[], None]:
    """Re-read the exact rights subject at each acquisition/persistence boundary."""
    subject = RightsSubject(
        source_family=source_family,
        locator_kind="URL",
        locator_value=canonical_url,
        content_id=content_id,
    )

    def check() -> None:
        if read_content_state is not None:
            require_operator_capture_content(
                read_content_state(content_id),
                content_id=content_id,
                canonical_url=canonical_url,
            )
        require_private_capture_rights(
            read_current(subject),
            rights_record_id=rights_record_id,
            content_id=content_id,
            canonical_url=canonical_url,
            source_family=source_family,
        )

    return check
