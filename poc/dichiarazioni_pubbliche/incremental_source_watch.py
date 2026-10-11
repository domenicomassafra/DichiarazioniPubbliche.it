"""DP-515 opt-in, pure incremental source-watch admission and HTTP reconciliation.

The caller owns authorized acquisition, content hashing and atomic persistence.
Nothing here fetches, schedules, reserves funds, enqueues or publishes. Child
records are *proposals*: a future adapter must compare-and-swap the state and
admit the child in the same durable transaction before dispatching work.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


WATCH_VERSION = "incremental-source-watch-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_FIELD = 256
_MAX_RETRY_AFTER_SECONDS = 7 * 86400


@dataclass(frozen=True)
class WatchPolicy:
    source_id: str
    locator_id: str
    source_family: str
    corpus_id: str
    corpus_cutoff: str
    policy_revision: str
    enabled: bool = False
    max_children: int = 1
    base_backoff_seconds: int = 60
    max_backoff_seconds: int = 3600
    circuit_after_failures: int = 3
    version: str = WATCH_VERSION


@dataclass(frozen=True)
class WatchState:
    source_id: str
    policy_fingerprint: str | None = None
    revision: int = 0
    etag: str | None = None
    last_modified: str | None = None
    content_sha256: str | None = None
    source_version: str | None = None
    last_attempted_at: datetime | None = None
    last_successful_observed_at: datetime | None = None
    last_attempt_id: str | None = None
    consecutive_failures: int = 0
    retry_not_before: datetime | None = None


@dataclass(frozen=True)
class WatchReadiness:
    """External gate readback scoped to this source/policy/corpus.

    Receipt strings are references, not proof of clearance. The adapter must
    authenticate rights, capability and DP-514 cost-cap receipts at admission.
    """

    source_id: str
    policy_fingerprint: str
    corpus_id: str
    rights_status: str = "UNKNOWN"
    rights_receipt: str | None = None
    capability_status: str = "UNKNOWN"
    capability_receipt: str | None = None
    budget_status: str = "UNKNOWN"
    budget_receipt: str | None = None
    remaining_children: int = 0


@dataclass(frozen=True)
class WatchPlan:
    allowed: bool
    reason: str
    source_id: str
    policy_fingerprint: str
    state_revision: int
    state_fingerprint: str
    attempt_id: str
    attempted_at: datetime
    conditional_headers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class WatchObservation:
    observed_at: datetime
    status_code: int | None
    content_sha256: str | None = None
    source_version: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    transport_error: str | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class WatchChildProposal:
    work_key: str
    stage: str
    source_id: str
    locator_id: str
    source_family: str
    corpus_id: str
    corpus_cutoff: str
    policy_fingerprint: str
    previous_source_version: str | None
    observed_source_version: str
    observed_sha256: str


@dataclass(frozen=True)
class WatchDecision:
    disposition: str
    reason: str
    expected_revision: int
    next_state: WatchState
    children: tuple[WatchChildProposal, ...] = ()
    # This flag asks the DP-511/DP-510 owner to assess a changed/blocked source.
    # It is never an automatic publication or an authorized hold event.
    needs_source_review: bool = False


def _require_label(value: str, name: str) -> str:
    if (not isinstance(value, str) or not 0 < len(value.strip()) <= _MAX_FIELD
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError(f"WATCH_{name}_INVALID")
    return value


def _utc(value: datetime | None, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"WATCH_{name}_TZ_REQUIRED")
    return value.astimezone(timezone.utc)


def _sha(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("WATCH_SHA256_INVALID")
    return value


def _validator(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    _require_label(value, name)
    if name == "ETAG":
        if not re.fullmatch(r'(?:W/)? "[^"]*"', value, flags=re.X):
            raise ValueError("WATCH_ETAG_INVALID")
    else:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError, OverflowError) as exc:
            raise ValueError("WATCH_LAST_MODIFIED_INVALID") from exc
        if parsed.tzinfo is None:
            raise ValueError("WATCH_LAST_MODIFIED_INVALID")
    return value


def _hash(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=lambda t: _utc(t, "FINGERPRINT_TIME").isoformat(),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def policy_fingerprint(policy: WatchPolicy) -> str:
    if policy.version != WATCH_VERSION:
        raise ValueError("WATCH_POLICY_VERSION_UNSUPPORTED")
    for field in ("source_id", "locator_id", "source_family", "corpus_id", "corpus_cutoff", "policy_revision"):
        _require_label(getattr(policy, field), field.upper())
    if type(policy.enabled) is not bool or type(policy.max_children) is not int or policy.max_children != 1:
        raise ValueError("WATCH_CHILD_LIMIT_INVALID")
    if (type(policy.base_backoff_seconds) is not int or type(policy.max_backoff_seconds) is not int
            or not 1 <= policy.base_backoff_seconds <= policy.max_backoff_seconds <= 86400):
        raise ValueError("WATCH_BACKOFF_POLICY_INVALID")
    if type(policy.circuit_after_failures) is not int or not 1 <= policy.circuit_after_failures <= 32:
        raise ValueError("WATCH_CIRCUIT_POLICY_INVALID")
    return _hash(asdict(policy))


def _state_fingerprint(state: WatchState) -> str:
    return _hash(asdict(state))


def _validate_state(policy: WatchPolicy, state: WatchState, fingerprint: str) -> None:
    if state.source_id != policy.source_id:
        raise ValueError("WATCH_SOURCE_SCOPE_MISMATCH")
    if state.policy_fingerprint is not None and state.policy_fingerprint != fingerprint:
        raise ValueError("WATCH_POLICY_SCOPE_MISMATCH")
    if type(state.revision) is not int or state.revision < 0:
        raise ValueError("WATCH_STATE_REVISION_INVALID")
    if type(state.consecutive_failures) is not int or not 0 <= state.consecutive_failures <= 100000:
        raise ValueError("WATCH_FAILURE_COUNTER_INVALID")
    _sha(state.content_sha256)
    _validator(state.etag, "ETAG")
    _validator(state.last_modified, "LAST_MODIFIED")
    for field in ("last_attempted_at", "last_successful_observed_at", "retry_not_before"):
        _utc(getattr(state, field), field.upper())
    for field in ("source_version", "last_attempt_id"):
        if getattr(state, field) is not None:
            _require_label(getattr(state, field), field.upper())
    if state.source_version is not None and state.content_sha256 is None:
        raise ValueError("WATCH_VERSION_WITHOUT_HASH")
    if state.policy_fingerprint is None and any((
        state.revision != 0, state.content_sha256 is not None,
        state.source_version is not None, state.etag is not None,
        state.last_modified is not None, state.last_attempt_id is not None,
        state.last_attempted_at is not None, state.last_successful_observed_at is not None,
        state.consecutive_failures != 0, state.retry_not_before is not None,
    )):
        raise ValueError("WATCH_UNSCOPED_HISTORY_INVALID")
    if state.last_attempted_at is None and state.last_attempt_id is not None:
        raise ValueError("WATCH_ATTEMPT_STATE_INVALID")


def _gate_reason(policy: WatchPolicy, gates: WatchReadiness, fingerprint: str) -> str | None:
    if (gates.source_id != policy.source_id or gates.policy_fingerprint != fingerprint
            or gates.corpus_id != policy.corpus_id):
        return "GATE_SCOPE_MISMATCH"
    for status, receipt, name in (
        (gates.rights_status, gates.rights_receipt, "RIGHTS"),
        (gates.capability_status, gates.capability_receipt, "CAPABILITY"),
        (gates.budget_status, gates.budget_receipt, "BUDGET"),
    ):
        if status != "READY" or not isinstance(receipt, str) or not receipt.strip():
            return f"{name}_NOT_READY"
        try:
            _require_label(receipt, f"{name}_RECEIPT")
        except ValueError:
            return f"{name}_RECEIPT_INVALID"
    if type(gates.remaining_children) is not int or gates.remaining_children < policy.max_children:
        return "CAP_EXHAUSTED"
    return None


def plan_watch_poll(
    policy: WatchPolicy,
    state: WatchState,
    gates: WatchReadiness,
    *,
    attempt_id: str,
    attempted_at: datetime,
) -> WatchPlan:
    """Prepare conditional headers; disallow unconfigured or unready attempts."""
    fingerprint = policy_fingerprint(policy)
    # Turning the switch off is always safe, even if the former active policy
    # fingerprint differs. Re-enabling still requires explicit scope admission.
    _validate_state(
        policy, state,
        fingerprint if policy.enabled else (state.policy_fingerprint or fingerprint),
    )
    _require_label(attempt_id, "ATTEMPT_ID")
    at = _utc(attempted_at, "ATTEMPTED_AT")
    assert at is not None
    reason = "CHECK_READY"
    if not policy.enabled:
        reason = "WATCH_DISABLED"
    elif state.last_attempt_id == attempt_id:
        reason = "ATTEMPT_ALREADY_RECORDED"
    elif state.last_attempted_at is not None and at <= _utc(state.last_attempted_at, "LAST_ATTEMPT"):
        reason = "ATTEMPT_OUT_OF_ORDER"
    elif (state.last_successful_observed_at is not None
          and at <= _utc(state.last_successful_observed_at, "LAST_SUCCESS")):
        reason = "ATTEMPT_OUT_OF_ORDER"
    elif state.retry_not_before is not None and at < _utc(state.retry_not_before, "RETRY"):
        reason = "SOURCE_BACKOFF"
    else:
        reason = _gate_reason(policy, gates, fingerprint) or reason
    headers: tuple[tuple[str, str], ...] = ()
    if reason == "CHECK_READY":
        headers = tuple(
            (name, value)
            for name, value in (("If-None-Match", state.etag), ("If-Modified-Since", state.last_modified))
            if value is not None and state.content_sha256 is not None
        )
    return WatchPlan(
        reason == "CHECK_READY", reason, policy.source_id, fingerprint, state.revision,
        _state_fingerprint(state), attempt_id, at, headers,
    )


def _with_attempt(
    state: WatchState, plan: WatchPlan, fingerprint: str, *,
    observed_at: datetime | None = None, failures: int | None = None,
    retry_not_before: datetime | None = None,
) -> WatchState:
    return replace(
        state, revision=state.revision + 1, policy_fingerprint=fingerprint,
        last_attempt_id=plan.attempt_id, last_attempted_at=plan.attempted_at,
        last_successful_observed_at=observed_at or state.last_successful_observed_at,
        consecutive_failures=0 if failures is None else failures,
        retry_not_before=retry_not_before,
    )


def _backoff(policy: WatchPolicy, attempt_id: str, failures: int, at: datetime,
             retry_after_seconds: int | None = None) -> datetime:
    base = min(policy.max_backoff_seconds, policy.base_backoff_seconds * (2 ** min(failures - 1, 20)))
    if failures >= policy.circuit_after_failures:
        base = max(base, min(policy.max_backoff_seconds,
                             policy.base_backoff_seconds * (2 ** min(policy.circuit_after_failures, 20))))
    # Deterministic, bounded jitter: idempotent replay cannot alter the retry time.
    jitter = int(_hash((policy.source_id, attempt_id, failures))[:8], 16) % (min(base // 10, 60) + 1)
    seconds = min(policy.max_backoff_seconds, base + jitter)
    if retry_after_seconds is not None:
        seconds = max(seconds, retry_after_seconds)
    return at + timedelta(seconds=seconds)


def reconcile_watch_observation(
    policy: WatchPolicy,
    state: WatchState,
    gates: WatchReadiness,
    plan: WatchPlan,
    observation: WatchObservation,
) -> WatchDecision:
    """Reconcile a *supplied* HTTP result. No unobserved success is ever inferred."""
    fingerprint = policy_fingerprint(policy)
    _validate_state(policy, state, fingerprint)
    if (not plan.allowed or plan.reason != "CHECK_READY" or plan.source_id != policy.source_id
            or plan.policy_fingerprint != fingerprint or plan.state_revision != state.revision
            or plan.state_fingerprint != _state_fingerprint(state)
            or plan.conditional_headers != tuple(
                (name, value)
                for name, value in (("If-None-Match", state.etag),
                                    ("If-Modified-Since", state.last_modified))
                if value is not None and state.content_sha256 is not None
            )):
        raise ValueError("WATCH_PLAN_STALE_OR_UNAUTHORIZED")
    try:
        _require_label(plan.attempt_id, "ATTEMPT_ID")
        attempt_at = _utc(plan.attempted_at, "ATTEMPTED_AT")
    except ValueError as exc:
        raise ValueError("WATCH_PLAN_STALE_OR_UNAUTHORIZED") from exc
    if (attempt_at is None or plan.attempt_id == state.last_attempt_id
            or (state.last_attempted_at is not None
                and attempt_at <= _utc(state.last_attempted_at, "LAST_ATTEMPT"))
            or (state.last_successful_observed_at is not None
                and attempt_at <= _utc(state.last_successful_observed_at, "LAST_SUCCESS"))
            or (state.retry_not_before is not None
                and attempt_at < _utc(state.retry_not_before, "RETRY"))):
        raise ValueError("WATCH_PLAN_STALE_OR_UNAUTHORIZED")
    at = _utc(observation.observed_at, "OBSERVED_AT")
    assert at is not None
    if at < attempt_at or (state.last_successful_observed_at is not None
                                and at < _utc(state.last_successful_observed_at, "LAST_SUCCESS")):
        raise ValueError("WATCH_OBSERVATION_TIME_INVALID")

    def failed(reason: str, retry_after: int | None = None) -> WatchDecision:
        failures = state.consecutive_failures + 1
        updated = _with_attempt(
            state, plan, fingerprint, failures=failures,
            retry_not_before=_backoff(policy, plan.attempt_id, failures, at, retry_after),
        )
        return WatchDecision("UNAVAILABLE", reason, state.revision, updated)

    gate_reason = _gate_reason(policy, gates, fingerprint)
    if not policy.enabled or gate_reason is not None:
        # The old validators/version remain so a denied change cannot be lost.
        return WatchDecision(
            "BLOCKED", "WATCH_DISABLED" if not policy.enabled else gate_reason,
            state.revision, _with_attempt(state, plan, fingerprint, failures=state.consecutive_failures),
        )
    if observation.retry_after_seconds is not None:
        if (type(observation.retry_after_seconds) is not int
                or not 0 <= observation.retry_after_seconds <= _MAX_RETRY_AFTER_SECONDS):
            return failed("RETRY_AFTER_INVALID", _MAX_RETRY_AFTER_SECONDS)
    if observation.status_code in (429, 503):
        return failed(f"HTTP_{observation.status_code}", observation.retry_after_seconds)
    if observation.status_code is None:
        if observation.transport_error not in {"TIMEOUT", "NETWORK_ERROR"}:
            return failed("UNVERIFIED_TRANSPORT_ERROR")
        return failed(observation.transport_error)
    if type(observation.status_code) is not int or observation.status_code not in (200, 304):
        return failed("UNSUPPORTED_HTTP_STATUS")
    if observation.transport_error is not None or observation.retry_after_seconds is not None:
        return failed("CONFLICTING_HTTP_OUTCOME")
    try:
        digest = _sha(observation.content_sha256)
        etag = _validator(observation.etag, "ETAG")
        modified = _validator(observation.last_modified, "LAST_MODIFIED")
        version = (_require_label(observation.source_version, "SOURCE_VERSION")
                   if observation.source_version is not None else None)
    except ValueError:
        return failed("MALFORMED_OBSERVATION")

    if observation.status_code == 304:
        if (not plan.conditional_headers or state.content_sha256 is None
                or digest is not None or (version is not None and version != state.source_version)
                or (etag is not None and etag != state.etag)
                or (modified is not None and modified != state.last_modified)):
            return failed("INVALID_CONDITIONAL_304")
        updated = replace(
            _with_attempt(state, plan, fingerprint, observed_at=at),
            etag=state.etag, last_modified=state.last_modified,
        )
        return WatchDecision("UNCHANGED", "HTTP_304", state.revision, updated)

    if digest is None:
        return failed("UNVERIFIED_200")
    # An upstream representation without an explicit version retains the
    # previously admitted version when the independently checked bytes match.
    version = version or (
        state.source_version if state.content_sha256 == digest and state.source_version
        else f"sha256:{digest}"
    )
    if state.etag is not None and etag == state.etag and digest != state.content_sha256:
        return failed("ETAG_CONTENT_CONFLICT")
    changed = (
        state.content_sha256 != digest
        or (state.source_version is not None and state.source_version != version)
    )
    updated = replace(
        _with_attempt(state, plan, fingerprint, observed_at=at),
        content_sha256=digest, source_version=version,
        etag=etag, last_modified=modified,
    )
    if not changed:
        return WatchDecision("UNCHANGED", "HTTP_200_SAME_CONTENT", state.revision, updated)
    proposal = WatchChildProposal(
        work_key="watch-child:" + _hash((
            WATCH_VERSION, policy.source_id, policy.locator_id, fingerprint,
            policy.corpus_id, policy.corpus_cutoff, version, digest, "SOURCE_REVALIDATION_REVIEW",
        )),
        stage="SOURCE_REVALIDATION_REVIEW",
        source_id=policy.source_id, locator_id=policy.locator_id,
        source_family=policy.source_family, corpus_id=policy.corpus_id,
        corpus_cutoff=policy.corpus_cutoff, policy_fingerprint=fingerprint,
        previous_source_version=state.source_version,
        observed_source_version=version, observed_sha256=digest,
    )
    return WatchDecision(
        "CHANGED", "SOURCE_VERSION_OR_CONTENT_CHANGED", state.revision,
        updated, (proposal,), needs_source_review=True,
    )


__all__ = [
    "WATCH_VERSION", "WatchPolicy", "WatchState", "WatchReadiness", "WatchPlan",
    "WatchObservation", "WatchChildProposal", "WatchDecision",
    "policy_fingerprint", "plan_watch_poll", "reconcile_watch_observation",
]
