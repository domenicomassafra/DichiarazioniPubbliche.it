"""DP-244: bounded private source-coverage inventory and version-delta contract.

No fetch, source enumeration, scheduler, publication, or completeness estimate.
Callers independently authenticate rights, source lineage and receipt hashes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


VERSION = "source-coverage-catalog-v1"
STATES = frozenset({"UNKNOWN", "NOT_COVERED", "PARTIAL", "STALE", "CURRENT_WITHIN_OBSERVED_SCOPE"})
RESULTS = frozenset({"UNCHANGED", "CHANGED", "UNAVAILABLE", "RIGHTS_BLOCKED", "OUTAGE", "NOT_FOUND"})
SHA = frozenset("0123456789abcdef")


def _present(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise ValueError("COVERAGE_" + field + "_INVALID")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or not set(value) <= SHA:
        raise ValueError("COVERAGE_HASH_INVALID")
    return value


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("COVERAGE_AWARE_TIME_REQUIRED")
    return value.astimezone(timezone.utc)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class CoverageUnit:
    unit_id: str
    source_family: str
    source_id: str
    collection_id: str
    language: str
    source_format: str
    expected_content_class: str
    interval_start: datetime
    interval_end: datetime
    mode: str
    policy_version: str
    max_staleness_seconds: int
    version: str = VERSION

    def __post_init__(self) -> None:
        for field in ("unit_id", "source_family", "source_id", "collection_id", "language", "source_format", "expected_content_class", "policy_version"):
            _present(getattr(self, field), field.upper())
        if self.mode not in {"HISTORICAL_BACKFILL", "INCREMENTAL_SUBSCRIPTION"} or self.version != VERSION:
            raise ValueError("COVERAGE_MODE_INVALID")
        if _aware(self.interval_end) <= _aware(self.interval_start):
            raise ValueError("COVERAGE_INTERVAL_INVALID")
        if type(self.max_staleness_seconds) is not int or not 1 <= self.max_staleness_seconds <= 365 * 86400:
            raise ValueError("COVERAGE_MAX_STALENESS_INVALID")


@dataclass(frozen=True)
class CoverageObservation:
    attempt_id: str
    source_id: str
    policy_version: str
    attempted_at: datetime
    status: str
    source_version: str | None = None
    content_sha256: str | None = None
    observation_receipt_id: str | None = None
    enumerated_scope_review_id: str | None = None
    enumeration_complete_within_scope: bool = False
    rights_status: str = "UNKNOWN"

    def __post_init__(self) -> None:
        for key in ("attempt_id", "source_id", "policy_version"):
            _present(getattr(self, key), key.upper())
        _aware(self.attempted_at)
        if self.status not in RESULTS or self.rights_status not in {"CLEARED", "UNKNOWN", "EXPIRED", "REVOKED", "DENIED"}:
            raise ValueError("COVERAGE_OBSERVATION_STATUS_INVALID")
        if type(self.enumeration_complete_within_scope) is not bool:
            raise ValueError("COVERAGE_ENUMERATION_INVALID")
        if self.content_sha256 is not None:
            _sha(self.content_sha256)
        if self.status in {"UNCHANGED", "CHANGED"}:
            _present(self.source_version, "VERSION")
            _sha(self.content_sha256)
            _present(self.observation_receipt_id, "OBSERVATION_RECEIPT")
        if self.enumeration_complete_within_scope:
            if self.status not in {"UNCHANGED", "CHANGED"} or self.rights_status != "CLEARED":
                raise ValueError("COVERAGE_UNREVIEWED_COMPLETENESS")
            _present(self.enumerated_scope_review_id, "SCOPE_REVIEW")


@dataclass(frozen=True)
class SourceCoverageDecision:
    unit_id: str
    source_family: str
    source_id: str
    mode: str
    state: str
    reason_code: str
    observed_source_version: str | None
    observed_sha256: str | None
    last_attempted_at: str | None
    last_successful_observed_at: str | None
    expected_content_class: str
    interval_start: str
    interval_end: str
    observation_fingerprint: str
    delta_proposal: str  # NONE, REVIEW_CHANGED_SOURCE, REVIEW_COVERAGE_GAP
    dispatch_authorized: bool = False


def build_source_coverage(
    unit: CoverageUnit,
    observations: tuple[CoverageObservation, ...],
    *,
    now: datetime,
    baseline_sha256: str | None = None,
    rights_ready: bool = False,
    budget_ready: bool = False,
    capability_ready: bool = False,
) -> SourceCoverageDecision:
    """Read-only reconciliation; proposals never schedule fetch/work."""
    if not isinstance(unit, CoverageUnit) or not isinstance(observations, tuple) or len(observations) > 128:
        raise ValueError("COVERAGE_INPUT_UNBOUNDED")
    stamp = _aware(now)
    if baseline_sha256 is not None:
        _sha(baseline_sha256)
    by_id: dict[str, CoverageObservation] = {}
    for record in observations:
        if not isinstance(record, CoverageObservation):
            raise ValueError("COVERAGE_OBSERVATION_INVALID")
        if record.source_id != unit.source_id or record.policy_version != unit.policy_version:
            raise ValueError("COVERAGE_MIXED_SCOPE")
        if _aware(record.attempted_at) > stamp:
            raise ValueError("COVERAGE_FUTURE_OBSERVATION")
        old = by_id.get(record.attempt_id)
        if old is not None and old != record:
            raise ValueError("COVERAGE_REPLAY_CONFLICT")
        by_id[record.attempt_id] = record
    rows = sorted(by_id.values(), key=lambda row: (_aware(row.attempted_at), row.attempt_id))
    latest = rows[-1] if rows else None
    successes = [row for row in rows if row.status in {"UNCHANGED", "CHANGED"} and row.rights_status == "CLEARED"]
    last_success = successes[-1] if successes else None
    state, reason, delta = "NOT_COVERED", "COVERAGE_NO_OBSERVATION", "REVIEW_COVERAGE_GAP"
    if latest is not None:
        if latest.rights_status != "CLEARED" or not rights_ready:
            state, reason, delta = "UNKNOWN", "COVERAGE_RIGHTS_UNKNOWN_OR_BLOCKED", "NONE"
        elif latest.status in {"UNAVAILABLE", "OUTAGE", "NOT_FOUND", "RIGHTS_BLOCKED"}:
            state, reason, delta = "STALE" if last_success else "UNKNOWN", "COVERAGE_RECENT_ATTEMPT_UNVERIFIED", "NONE"
        elif last_success is None:
            state, reason, delta = "UNKNOWN", "COVERAGE_NO_AUTHORIZED_SUCCESS", "NONE"
        elif stamp - _aware(last_success.attempted_at) > timedelta(seconds=unit.max_staleness_seconds):
            state, reason, delta = "STALE", "COVERAGE_SUCCESS_TOO_OLD", "REVIEW_COVERAGE_GAP"
        elif not last_success.enumeration_complete_within_scope:
            state, reason, delta = "PARTIAL", "COVERAGE_SCOPE_NOT_EXHAUSTIVELY_REVIEWED", "REVIEW_COVERAGE_GAP"
        else:
            state, reason, delta = "CURRENT_WITHIN_OBSERVED_SCOPE", "COVERAGE_ENUMERATION_ATTESTED_WITHIN_SCOPE", "NONE"
        if last_success and baseline_sha256 and last_success.content_sha256 != baseline_sha256:
            # A newly observed source is not proof that all derived claims,
            # quotations or cached public readers were re-reviewed.
            state = "STALE"
            delta = "REVIEW_CHANGED_SOURCE" if (rights_ready and budget_ready and capability_ready) else "NONE"
            reason = ("COVERAGE_CHANGED_SOURCE_REANALYSIS_PENDING" if delta == "REVIEW_CHANGED_SOURCE"
                      else "COVERAGE_CHANGE_CHILD_GATES_NOT_READY")
    material = {
        "unit": (unit.unit_id, unit.source_id, unit.source_family,
                 unit.collection_id, unit.language, unit.source_format,
                 unit.expected_content_class, unit.mode, unit.policy_version,
                 _aware(unit.interval_start).isoformat(), _aware(unit.interval_end).isoformat()),
        "rows": [(row.attempt_id, row.status, row.content_sha256, row.source_version,
                  _aware(row.attempted_at).isoformat(), row.enumeration_complete_within_scope,
                  row.enumerated_scope_review_id, row.rights_status) for row in rows],
        "baseline": baseline_sha256, "now": stamp.isoformat(), "version": VERSION,
    }
    return SourceCoverageDecision(
        unit.unit_id, unit.source_family, unit.source_id, unit.mode,
        state, reason,
        last_success.source_version if last_success else None,
        last_success.content_sha256 if last_success else None,
        _aware(latest.attempted_at).isoformat() if latest else None,
        _aware(last_success.attempted_at).isoformat() if last_success else None,
        unit.expected_content_class, _aware(unit.interval_start).isoformat(),
        _aware(unit.interval_end).isoformat(), _fingerprint(material), delta, False,
    )


def public_freshness_descriptor(decision: SourceCoverageDecision, *,
                                public_scope_review_id: str | None) -> dict[str, str] | None:
    """No Person/Topic/private source lists/counts. Explicit opt-in to sharing.

    This does not attest a particular public release/cached variant.
    """
    if not public_scope_review_id or decision.state != "CURRENT_WITHIN_OBSERVED_SCOPE":
        return None
    return {
        "status": "CURRENT_WITHIN_OBSERVED_SCOPE",
        "source_family": decision.source_family,
        "scope_start": decision.interval_start,
        "scope_end": decision.interval_end,
        "observed_at": decision.last_successful_observed_at or "",
        "coverage_limit": "Solo fonti/intervallo osservati; corpus complessivo non garantito",
    }
