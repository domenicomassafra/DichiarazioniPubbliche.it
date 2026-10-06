"""DP-508 callable abuse guard for an already validated public-intake fingerprint.

The guard owns no HTTP surface and derives no network identity.  The caller supplies an
already pseudonymous bucket key, an atomic rate store, an explicit clock, and the launch
posture.  Raw IP/source identifiers, request bodies, URLs, and identities are never
accepted by this module and therefore cannot enter its receipts or rate-store state.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Protocol

from dichiarazioni_pubbliche.policy.intake_policy import (
    INTAKE_POLICY_VERSION,
    IntakeDisposition,
    IntakeRejectionReason,
    IntakeValidationResult,
)


INTAKE_ABUSE_GUARD_VERSION = "public-intake-abuse-v1"
MAX_BUCKET_KEY_CHARS = 71  # ``bucket:`` + one lowercase SHA-256 hex digest
MAX_PRIVATE_LOG_RECEIPT_BYTES = 640
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_PSEUDONYMOUS_BUCKET = re.compile(r"^bucket:[0-9a-f]{64}$")
MAX_RATE_WINDOW_SECONDS = 86_400
MAX_DUPLICATE_CAPACITY = 4_096
MAX_DUPLICATE_LIMIT = 10_000
MAX_RATE_COUNT = 1_000_000


class IntakeGuardState(StrEnum):
    ALLOWED_PRIVATE = "ALLOWED_PRIVATE"
    RATE_LIMITED = "RATE_LIMITED"
    QUARANTINED = "QUARANTINED"
    REPLAY = "REPLAY"
    BLOCKED = "BLOCKED"


class IntakeSpamReason(StrEnum):
    OK = "OK"
    PROFILE_MISSING = "PROFILE_MISSING"
    PUBLIC_INTAKE_DISABLED = "PUBLIC_INTAKE_DISABLED"
    RATE_STORE_MISSING = "RATE_STORE_MISSING"
    CLOCK_MISSING = "CLOCK_MISSING"
    CLOCK_INVALID = "CLOCK_INVALID"
    BUCKET_KEY_INVALID = "BUCKET_KEY_INVALID"
    FINGERPRINT_INVALID = "FINGERPRINT_INVALID"
    POLICY_REJECTED = "POLICY_REJECTED"
    RATE_STORE_ERROR = "RATE_STORE_ERROR"
    SPAM_BUCKET_RATE_LIMIT = "SPAM_BUCKET_RATE_LIMIT"
    SPAM_GLOBAL_QUOTA_EXCEEDED = "SPAM_GLOBAL_QUOTA_EXCEEDED"
    SPAM_DUPLICATE_REPLAY = "SPAM_DUPLICATE_REPLAY"
    SPAM_DUPLICATE_BURST = "SPAM_DUPLICATE_BURST"
    SPAM_RESERVED_FIELD_SIGNAL = "SPAM_RESERVED_FIELD_SIGNAL"
    SPAM_PII_QUARANTINE = "SPAM_PII_QUARANTINE"
    SPAM_POLICY_QUARANTINE = "SPAM_POLICY_QUARANTINE"


class RateStoreStatus(StrEnum):
    RESERVED = "RESERVED"
    REPLAY = "REPLAY"
    BUCKET_LIMIT = "BUCKET_LIMIT"
    GLOBAL_QUOTA = "GLOBAL_QUOTA"
    DUPLICATE_BURST = "DUPLICATE_BURST"


@dataclass(frozen=True)
class IntakeAbuseProfile:
    """Caller-owned rate/duplicate policy. Defaults are deliberately unusable."""

    configured: bool = False
    window_seconds: int = 0
    bucket_limit: int = 0
    global_quota: int = 0
    duplicate_window_seconds: int = 0
    duplicate_limit: int = 0
    duplicate_capacity: int = 0

    def valid(self) -> bool:
        return (
            self.configured
            and 0 < self.window_seconds <= MAX_RATE_WINDOW_SECONDS
            and 0 < self.bucket_limit <= MAX_RATE_COUNT
            and 0 < self.global_quota <= MAX_RATE_COUNT
            and 0 < self.duplicate_window_seconds <= MAX_RATE_WINDOW_SECONDS
            and 0 < self.duplicate_limit <= MAX_DUPLICATE_LIMIT
            and 0 < self.duplicate_capacity <= MAX_DUPLICATE_CAPACITY
        )


@dataclass(frozen=True)
class RateStoreRequest:
    bucket_key: str
    fingerprint: str
    now_epoch: int
    window_seconds: int
    bucket_limit: int
    global_quota: int
    duplicate_window_seconds: int
    duplicate_limit: int
    duplicate_capacity: int


@dataclass(frozen=True)
class RateStoreResult:
    status: RateStoreStatus


class IntakeRateStore(Protocol):
    def reserve(self, request: RateStoreRequest) -> RateStoreResult: ...


@dataclass
class _FingerprintRecord:
    last_seen_epoch: int
    replay_count: int = 0


class InMemoryIntakeRateStore:
    """Bounded atomic local rate store for tests/callable runtime use.

    Bucket keys are hashed before retention.  Fingerprints are already DP-302 SHA-256
    identities.  Old windows and expired duplicate records are discarded under one lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._window_id: int | None = None
        self._bucket_counts: dict[str, int] = {}
        self._global_count = 0
        self._fingerprints: dict[str, _FingerprintRecord] = {}

    @staticmethod
    def _bucket_digest(bucket_key: str) -> str:
        return hashlib.sha256(bucket_key.encode("utf-8")).hexdigest()

    def _reset_window_if_needed(self, window_id: int) -> None:
        if self._window_id != window_id:
            self._window_id = window_id
            self._bucket_counts.clear()
            self._global_count = 0

    def _prune_duplicates(self, *, now_epoch: int, ttl: int) -> None:
        expired = [
            fingerprint
            for fingerprint, record in self._fingerprints.items()
            if now_epoch - record.last_seen_epoch >= ttl
        ]
        for fingerprint in expired:
            del self._fingerprints[fingerprint]

    def _bound_duplicates(self, capacity: int) -> None:
        while len(self._fingerprints) > capacity:
            victim = min(
                self._fingerprints,
                key=lambda fingerprint: (
                    self._fingerprints[fingerprint].last_seen_epoch,
                    fingerprint,
                ),
            )
            del self._fingerprints[victim]

    def reserve(self, request: RateStoreRequest) -> RateStoreResult:
        window_id = request.now_epoch // request.window_seconds
        bucket_digest = self._bucket_digest(request.bucket_key)
        with self._lock:
            self._reset_window_if_needed(window_id)
            self._prune_duplicates(
                now_epoch=request.now_epoch,
                ttl=request.duplicate_window_seconds,
            )

            if self._global_count >= request.global_quota:
                return RateStoreResult(RateStoreStatus.GLOBAL_QUOTA)
            if self._bucket_counts.get(bucket_digest, 0) >= request.bucket_limit:
                return RateStoreResult(RateStoreStatus.BUCKET_LIMIT)

            self._global_count += 1
            self._bucket_counts[bucket_digest] = self._bucket_counts.get(bucket_digest, 0) + 1

            existing = self._fingerprints.get(request.fingerprint)
            if existing is not None:
                existing.replay_count += 1
                existing.last_seen_epoch = request.now_epoch
                if existing.replay_count > request.duplicate_limit:
                    return RateStoreResult(RateStoreStatus.DUPLICATE_BURST)
                return RateStoreResult(RateStoreStatus.REPLAY)

            self._fingerprints[request.fingerprint] = _FingerprintRecord(
                last_seen_epoch=request.now_epoch
            )
            self._bound_duplicates(request.duplicate_capacity)
            return RateStoreResult(RateStoreStatus.RESERVED)

    @property
    def retained_fingerprint_count(self) -> int:
        with self._lock:
            return len(self._fingerprints)


@dataclass(frozen=True)
class IntakeGuardReceipt:
    state: IntakeGuardState
    reason: IntakeSpamReason
    decision_time: str
    signal_count: int = 0

    @property
    def private_log_receipt(self) -> dict[str, object]:
        return {
            "guard_version": INTAKE_ABUSE_GUARD_VERSION,
            "policy_version": INTAKE_POLICY_VERSION,
            "state": self.state.value,
            "reason": self.reason.value,
            "decision_time": self.decision_time,
            "signal_count": self.signal_count,
        }

    def is_bounded(self) -> bool:
        encoded = json.dumps(
            self.private_log_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return len(encoded) <= MAX_PRIVATE_LOG_RECEIPT_BYTES


def _receipt(
    state: IntakeGuardState,
    reason: IntakeSpamReason,
    decision_time: str,
    *,
    signal_count: int = 0,
) -> IntakeGuardReceipt:
    return IntakeGuardReceipt(
        state=state,
        reason=reason,
        decision_time=decision_time,
        signal_count=max(0, min(int(signal_count), 99)),
    )


def _clock_value(clock: Callable[[], datetime]) -> tuple[datetime, str] | None:
    try:
        current = clock()
    except Exception:  # noqa: BLE001 - fail closed without reflecting clock details
        return None
    if not isinstance(current, datetime) or current.tzinfo is None:
        return None
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    return current, current.isoformat().replace("+00:00", "Z")


def _valid_bucket_key(bucket_key: object) -> str | None:
    if not isinstance(bucket_key, str):
        return None
    normalized = bucket_key.strip()
    if len(normalized) > MAX_BUCKET_KEY_CHARS:
        return None
    if not _PSEUDONYMOUS_BUCKET.fullmatch(normalized):
        return None
    return normalized


def guard_validated_intake(
    validation: IntakeValidationResult,
    *,
    pseudonymous_bucket_key: object,
    profile: IntakeAbuseProfile | None,
    rate_store: IntakeRateStore | None,
    clock: Callable[[], datetime] | None,
    launch_profile_enabled: bool = False,
) -> IntakeGuardReceipt:
    """Apply DP-508 abuse controls to DP-302 validation metadata only.

    The caller owns the launch switch, rate-store lifetime, clock, and pseudonymization of
    any source/network identity.  This function accepts none of the corresponding raw data.
    """

    if profile is None or not profile.valid():
        return _receipt(IntakeGuardState.BLOCKED, IntakeSpamReason.PROFILE_MISSING, "")
    if not launch_profile_enabled:
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.PUBLIC_INTAKE_DISABLED,
            "",
        )
    if rate_store is None:
        return _receipt(IntakeGuardState.BLOCKED, IntakeSpamReason.RATE_STORE_MISSING, "")
    if clock is None:
        return _receipt(IntakeGuardState.BLOCKED, IntakeSpamReason.CLOCK_MISSING, "")

    clock_value = _clock_value(clock)
    if clock_value is None:
        return _receipt(IntakeGuardState.BLOCKED, IntakeSpamReason.CLOCK_INVALID, "")
    current, decision_time = clock_value

    bucket_key = _valid_bucket_key(pseudonymous_bucket_key)
    if bucket_key is None:
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.BUCKET_KEY_INVALID,
            decision_time,
        )

    if validation.reason is IntakeRejectionReason.UNKNOWN_FIELD:
        return _receipt(
            IntakeGuardState.QUARANTINED,
            IntakeSpamReason.SPAM_RESERVED_FIELD_SIGNAL,
            decision_time,
            signal_count=1,
        )

    if validation.disposition is IntakeDisposition.REJECTED:
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.POLICY_REJECTED,
            decision_time,
        )

    fingerprint = str(validation.source_hash or "").strip()
    if not _SHA256_HEX.fullmatch(fingerprint):
        if validation.disposition is IntakeDisposition.QUARANTINED:
            return _receipt(
                IntakeGuardState.QUARANTINED,
                IntakeSpamReason.SPAM_POLICY_QUARANTINE,
                decision_time,
                signal_count=len(validation.quarantine_signals) or 1,
            )
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.FINGERPRINT_INVALID,
            decision_time,
        )

    try:
        rate = rate_store.reserve(
            RateStoreRequest(
                bucket_key=bucket_key,
                fingerprint=fingerprint,
                now_epoch=int(current.timestamp()),
                window_seconds=profile.window_seconds,
                bucket_limit=profile.bucket_limit,
                global_quota=profile.global_quota,
                duplicate_window_seconds=profile.duplicate_window_seconds,
                duplicate_limit=profile.duplicate_limit,
                duplicate_capacity=profile.duplicate_capacity,
            )
        )
    except Exception:  # noqa: BLE001 - fail closed and do not reflect private store detail
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.RATE_STORE_ERROR,
            decision_time,
        )
    if not isinstance(rate, RateStoreResult):
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.RATE_STORE_ERROR,
            decision_time,
        )

    if rate.status is RateStoreStatus.GLOBAL_QUOTA:
        return _receipt(
            IntakeGuardState.RATE_LIMITED,
            IntakeSpamReason.SPAM_GLOBAL_QUOTA_EXCEEDED,
            decision_time,
        )
    if rate.status is RateStoreStatus.BUCKET_LIMIT:
        return _receipt(
            IntakeGuardState.RATE_LIMITED,
            IntakeSpamReason.SPAM_BUCKET_RATE_LIMIT,
            decision_time,
        )
    if rate.status is RateStoreStatus.DUPLICATE_BURST:
        return _receipt(
            IntakeGuardState.RATE_LIMITED,
            IntakeSpamReason.SPAM_DUPLICATE_BURST,
            decision_time,
        )
    if rate.status is RateStoreStatus.REPLAY:
        return _receipt(
            IntakeGuardState.REPLAY,
            IntakeSpamReason.SPAM_DUPLICATE_REPLAY,
            decision_time,
        )
    if rate.status is not RateStoreStatus.RESERVED:
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.RATE_STORE_ERROR,
            decision_time,
        )

    if validation.disposition is IntakeDisposition.QUARANTINED:
        pii_signal = any(
            signal
            in {
                "contact_disclosure_candidate",
                "numeric_identifier_candidate",
                "submitter_contact_candidate",
            }
            for signal in validation.quarantine_signals
        )
        return _receipt(
            IntakeGuardState.QUARANTINED,
            (
                IntakeSpamReason.SPAM_PII_QUARANTINE
                if pii_signal
                else IntakeSpamReason.SPAM_POLICY_QUARANTINE
            ),
            decision_time,
            signal_count=len(validation.quarantine_signals) or 1,
        )

    if validation.disposition is not IntakeDisposition.ACCEPTED_PRIVATE:
        return _receipt(
            IntakeGuardState.BLOCKED,
            IntakeSpamReason.POLICY_REJECTED,
            decision_time,
        )

    return _receipt(IntakeGuardState.ALLOWED_PRIVATE, IntakeSpamReason.OK, decision_time)


__all__ = [
    "INTAKE_ABUSE_GUARD_VERSION",
    "MAX_BUCKET_KEY_CHARS",
    "MAX_DUPLICATE_CAPACITY",
    "MAX_PRIVATE_LOG_RECEIPT_BYTES",
    "MAX_RATE_COUNT",
    "MAX_RATE_WINDOW_SECONDS",
    "InMemoryIntakeRateStore",
    "IntakeAbuseProfile",
    "IntakeGuardReceipt",
    "IntakeGuardState",
    "IntakeRateStore",
    "IntakeSpamReason",
    "RateStoreRequest",
    "RateStoreResult",
    "RateStoreStatus",
    "guard_validated_intake",
]
