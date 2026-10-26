"""DP-236 optional source-artifact/use guard over existing reviewed rights records.

This does not issue permissions or authorize public excerpts. The old operator
capture guard continues to operate unchanged for callers not opting in.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.rights_registry import (
    MAX_POLICY_CODES,
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

SOURCE_USE_CONTRACT_VERSION = "source-family-use-v1"
PRIVATE_SOURCE_USES = frozenset({
    "DISCOVER_METADATA", "FETCH", "STORE_BODY", "PARSE_TEXT", "PARSE_OCR",
    "TRANSLATE", "ASR_MEDIA", "ARCHIVE", "PLAYBACK", "EXTRACT_CANDIDATES",
})
PUBLIC_SOURCE_USE = "EXCERPT_PUBLIC"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MACHINE_CODE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,127}$")


class SourceUseBlocked(PrivateCaptureAuthorizationBlocked):
    """Stable operator code, without source/legal data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SourceUseDecision:
    use: str
    status: str
    reason_code: str
    action_code: str
    record_id: str | None = None
    decision_fingerprint: str | None = None

    @property
    def permitted(self) -> bool:
        return self.status == "PERMITTED"


def _aware(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _fingerprint(record: PrivateRightsRecord, use: str) -> str:
    material = {
        "contract": SOURCE_USE_CONTRACT_VERSION,
        "record_id": record.id,
        "subject_fingerprint": record.subject_fingerprint,
        "record_version": record.record_version,
        "policy_version": record.policy_version,
        "rights_status": record.rights_status,
        "rights_receipt_ref": record.rights_receipt_ref,
        "reviewer_ref": record.reviewer_ref,
        "reviewed_at": record.reviewed_at,
        "expires_at": record.expires_at,
        "permitted_uses": sorted(record.permitted_uses),
        "attribution_requirements": sorted(record.attribution_requirements),
        "use": use,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def evaluate_source_use(
    record: PrivateRightsRecord | None,
    *,
    subject: RightsSubject,
    rights_record_id: str,
    policy_version: str,
    use: str,
    now: datetime,
) -> SourceUseDecision:
    """Inspect one use of an exact current private-rights subject, without I/O."""
    if use not in PRIVATE_SOURCE_USES and use != PUBLIC_SOURCE_USE:
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_UNKNOWN", "CHECK_USE_CONTRACT")
    if use == PUBLIC_SOURCE_USE:
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_PUBLIC_POLICY_REQUIRED", "DP305_EXCERPT_REVIEW")
    if record is None:
        return SourceUseDecision(use, "UNRESOLVED", "SOURCE_USE_RECORD_MISSING", "OBTAIN_SOURCE_REVIEW")
    if (
        not isinstance(rights_record_id, str) or not rights_record_id.strip()
        or record.id != rights_record_id or record.version_state != "CURRENT"
    ):
        return SourceUseDecision(use, "REVOKED", "SOURCE_USE_RECORD_NOT_CURRENT", "REFRESH_SOURCE_REVIEW")
    if (
        record.record_version != PRIVATE_RIGHTS_RECORD_VERSION
        or record.record_visibility != "PRIVATE"
        or not isinstance(record.permitted_uses, tuple)
        or any(not isinstance(item, str) for item in record.permitted_uses)
        or not isinstance(record.attribution_requirements, tuple)
        or len(record.attribution_requirements) > MAX_POLICY_CODES
        or any(
            not isinstance(item, str) or not _MACHINE_CODE.fullmatch(item)
            for item in record.attribution_requirements
        )
    ):
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_RECORD_CONTRACT_INVALID", "REVIEW_RECORD_CONTRACT")
    try:
        exact_fingerprint = rights_subject_fingerprint(subject)
    except (TypeError, ValueError, AttributeError):
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_SUBJECT_INVALID", "CHECK_ARTIFACT_BINDING")
    if (
        record.subject_fingerprint != exact_fingerprint
        or record.source_family != subject.source_family
        or record.locator_kind != subject.locator_kind
        or record.locator_value != subject.locator_value
        or record.content_id != subject.content_id
        or record.evidence_id != subject.evidence_id
        or record.transcript_segment_id != subject.transcript_segment_id
        or record.canonical_segment_id != subject.canonical_segment_id
        or record.passage_id != subject.passage_id
    ):
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_ARTIFACT_MISMATCH", "CHECK_ARTIFACT_BINDING")
    if record.policy_version != policy_version or not policy_version:
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_POLICY_MISMATCH", "REVIEW_POLICY_VERSION")
    if record.rights_status == "REVOKED":
        return SourceUseDecision(use, "REVOKED", "SOURCE_USE_REVOKED", "REQUEST_NEW_REVIEW")
    if record.rights_status == "EXPIRED":
        return SourceUseDecision(use, "EXPIRED", "SOURCE_USE_EXPIRED", "RENEW_SOURCE_REVIEW")
    if record.rights_status != "CLEARED":
        return SourceUseDecision(use, "UNRESOLVED", "SOURCE_USE_NOT_CLEARED", "RESOLVE_SOURCE_RIGHTS")
    reviewed = _aware(record.reviewed_at)
    expiry = _aware(record.expires_at) if record.expires_at is not None else None
    # A non-DB current reader can return an unnormalized record. Mirror the
    # rights registry's receipt/reviewer contract at the operation boundary:
    # truthy whitespace or non-text values are not evidence of review.
    receipt = record.rights_receipt_ref
    reviewer = record.reviewer_ref
    if (
        not isinstance(receipt, str) or not 0 < len(receipt) <= 512
        or any(char.isspace() or char == "\x00" for char in receipt)
        or not isinstance(reviewer, str) or not 0 < len(reviewer.strip()) <= 256
        or "\x00" in reviewer
        or reviewed is None or reviewed > now
        or (record.expires_at is not None and expiry is None)
    ):
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_REVIEW_INVALID", "REVIEW_SOURCE_RECEIPT")
    if expiry is None:
        return SourceUseDecision(use, "UNRESOLVED", "SOURCE_USE_EXPIRY_REQUIRED", "SET_REVIEW_EXPIRY")
    if expiry is not None and expiry <= now:
        return SourceUseDecision(use, "EXPIRED", "SOURCE_USE_EXPIRED", "RENEW_SOURCE_REVIEW")
    if use not in record.permitted_uses:
        return SourceUseDecision(use, "DENIED", "SOURCE_USE_NOT_PERMITTED", "REVIEW_SPECIFIC_USE")
    return SourceUseDecision(
        use, "PERMITTED", "SOURCE_USE_PERMITTED", "NONE",
        record.id, _fingerprint(record, use),
    )


class SourceFamilyUseGuard:
    """Re-read a current record at each stage and optionally pin captured bytes."""

    def __init__(
        self,
        *,
        read_current: Callable[[RightsSubject], PrivateRightsRecord | None],
        subject: RightsSubject,
        rights_record_id: str,
        policy_version: str,
        expected_sha256: str | None = None,
        expected_media_type: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if (
            subject.locator_kind != "URL" or not subject.content_id
            or not subject.source_family or not subject.locator_value
            or any((
                subject.evidence_id, subject.passage_id,
                subject.canonical_segment_id, subject.transcript_segment_id,
            ))
        ):
            raise SourceUseBlocked("SOURCE_USE_CAPTURE_SUBJECT_INVALID")
        if expected_sha256 is not None and not _SHA256.fullmatch(expected_sha256):
            raise SourceUseBlocked("SOURCE_USE_HASH_PIN_INVALID")
        if expected_media_type is not None and (
            not isinstance(expected_media_type, str)
            or not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", expected_media_type)
        ):
            raise SourceUseBlocked("SOURCE_USE_MEDIA_PIN_INVALID")
        self.read_current = read_current
        self.subject = subject
        self.rights_record_id = rights_record_id
        self.policy_version = policy_version
        self.expected_sha256 = expected_sha256
        self.expected_media_type = expected_media_type
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def bind_capture(self, *, content_id: str, url: str) -> None:
        if content_id != self.subject.content_id or url != self.subject.locator_value:
            raise SourceUseBlocked("SOURCE_USE_CAPTURE_TARGET_MISMATCH")

    def bind_fetched(self, *, final_url: str) -> None:
        # Safe redirects alone say nothing about permissions on a different
        # artifact. The new locator needs its own reviewed rights subject.
        if final_url != self.subject.locator_value:
            raise SourceUseBlocked("SOURCE_USE_FINAL_ARTIFACT_MISMATCH")

    def require(
        self,
        use: str,
        *,
        content_sha256: str | None = None,
        media_type: str | None = None,
    ) -> SourceUseDecision:
        if self.expected_sha256 is not None and content_sha256 is not None:
            if content_sha256 != self.expected_sha256:
                raise SourceUseBlocked("SOURCE_USE_CAPTURE_HASH_MISMATCH")
        if self.expected_media_type is not None and media_type is not None:
            if media_type.split(";", 1)[0].strip().lower() != self.expected_media_type:
                raise SourceUseBlocked("SOURCE_USE_MEDIA_TYPE_MISMATCH")
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise SourceUseBlocked("SOURCE_USE_CLOCK_INVALID")
        try:
            record = self.read_current(self.subject)
        except Exception:
            raise SourceUseBlocked("SOURCE_USE_READ_UNAVAILABLE") from None
        decision = evaluate_source_use(
            record,
            subject=self.subject,
            rights_record_id=self.rights_record_id,
            policy_version=self.policy_version,
            use=use,
            now=now.astimezone(timezone.utc),
        )
        if not decision.permitted:
            raise SourceUseBlocked(decision.reason_code)
        return decision


__all__ = [
    "PRIVATE_SOURCE_USES", "PUBLIC_SOURCE_USE", "SOURCE_USE_CONTRACT_VERSION",
    "SourceFamilyUseGuard", "SourceUseBlocked", "SourceUseDecision", "evaluate_source_use",
]
