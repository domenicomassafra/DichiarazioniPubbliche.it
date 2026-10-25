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
from datetime import date, datetime, timedelta, timezone
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


@dataclass(frozen=True)
class WatchCoverageSnapshot:
    """Private operator readback of one source's admitted policy and latest state.

    The caller must load an authorized, transactionally committed state and an
    authenticated current gate; this read model cannot certify external receipts.
    """

    policy: WatchPolicy
    state: WatchState
    readiness: WatchReadiness | None = None


@dataclass(frozen=True)
class WatchCommittedAttempt:
    """Private persisted attempt with enough lineage for independent replay.

    Planning and reconciliation gates differ if rights/budget/capability changed
    during a request. Cost is measured externally; None is *unknown*, not free.
    """

    source_id: str
    previous_state: WatchState
    planning_readiness: WatchReadiness
    reconciliation_readiness: WatchReadiness
    plan: WatchPlan
    observation: WatchObservation
    decision: WatchDecision
    measured_cost_micro_eur: int | None = None


@dataclass(frozen=True)
class WatchDailySourceHealth:
    source_id: str
    source_family: str
    corpus_id: str
    corpus_cutoff: str
    watch_status: str
    blocker_reason: str | None
    last_attempted_at: datetime | None
    last_successful_observed_at: datetime | None
    retry_not_before: datetime | None
    consecutive_failures: int
    last_disposition: str | None
    known_gaps: tuple[str, ...]
    daily_attempts: int
    daily_new: int
    daily_modified: int
    daily_unchanged: int
    daily_unavailable: int
    daily_blocked: int
    daily_rate_limited: int
    daily_metered_cost_micro_eur: int
    daily_unknown_cost_attempts: int


@dataclass(frozen=True)
class WatchDailyHealthDigest:
    """Daily private coverage/attempt projection; never a public freshness claim."""

    day: date
    through_at: datetime
    sources: tuple[WatchDailySourceHealth, ...]
    watched_sources: int
    unwatched_sources: int
    attempts: int
    new: int
    modified: int
    unchanged: int
    unavailable: int
    blocked: int
    rate_limited: int
    metered_cost_micro_eur: int
    unknown_cost_attempts: int


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


def _last_modified_after(value: str | None, observed_at: datetime) -> bool:
    """A future source validator cannot attest a previously observed version."""
    return bool(
        value is not None
        and parsedate_to_datetime(value).astimezone(timezone.utc) > observed_at
    )


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
    if (state.last_successful_observed_at is not None
            and _last_modified_after(
                state.last_modified,
                _utc(state.last_successful_observed_at, "LAST_SUCCESS"),
            )):
        raise ValueError("WATCH_LAST_MODIFIED_AFTER_OBSERVATION")
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
    if policy.enabled and _last_modified_after(state.last_modified, at):
        raise ValueError("WATCH_LAST_MODIFIED_AFTER_OBSERVATION")
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
            or _last_modified_after(state.last_modified, attempt_at)
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

    if _last_modified_after(modified, at):
        return failed("LAST_MODIFIED_IN_FUTURE")

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
    # Retain admitted version for matching bytes without an explicit version.
    version = version or (
        state.source_version if state.content_sha256 == digest and state.source_version
        else f"sha256:{digest}"
    )
    if state.etag is not None and etag == state.etag and digest != state.content_sha256:
        return replace(failed("ETAG_CONTENT_CONFLICT"), needs_source_review=True)
    changed = (
        state.content_sha256 != digest
        or (state.source_version is not None and state.source_version != version)
    )
    if (changed and modified is not None and state.last_modified is not None
            and parsedate_to_datetime(modified) < parsedate_to_datetime(state.last_modified)):
        # A changed body/version carrying an older HTTP validator may be a
        # stale cached representation. Do not replace the confirmed source
        # head or record successful freshness until the anomaly is resolved.
        return replace(failed("LAST_MODIFIED_REGRESSED"), needs_source_review=True)
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


def build_private_watch_daily_digest(
    *,
    day: date,
    as_of: datetime,
    snapshots: tuple[WatchCoverageSnapshot, ...],
    committed_attempts: tuple[WatchCommittedAttempt, ...],
) -> WatchDailyHealthDigest:
    """Project a bounded private UTC-day digest from *committed* readbacks.

    Replays each observation and verifies the full in-day source-state chain
    through the latest snapshot. Missing/duplicated entries fail closed instead
    of making a source look healthy. The adapter must authenticate DB snapshots,
    rights/capability/budget and actual metered costs before calling this pure
    function; passing a forged in-memory readback is not a durable proof.
    """
    if type(day) is not date or not isinstance(snapshots, tuple) or not isinstance(committed_attempts, tuple):
        raise ValueError("DAILY_WATCH_INPUT_INVALID")
    through = _utc(as_of, "DIGEST_AS_OF")
    if through is None or day > through.date():
        raise ValueError("DAILY_WATCH_AS_OF_INVALID")
    if len(snapshots) > 500 or len(committed_attempts) > 5000:
        raise ValueError("DAILY_WATCH_BOUND_EXCEEDED")

    coverage: dict[str, WatchCoverageSnapshot] = {}
    for snapshot in snapshots:
        p, s = snapshot.policy, snapshot.state
        fingerprint = policy_fingerprint(p)
        _validate_state(p, s, fingerprint if p.enabled else (s.policy_fingerprint or fingerprint))
        if p.source_id in coverage:
            raise ValueError("DAILY_WATCH_DUPLICATE_SOURCE")
        for recorded in (s.last_attempted_at, s.last_successful_observed_at):
            if recorded is not None and _utc(recorded, "DIGEST_STATE_TIME") > through:
                raise ValueError("DAILY_WATCH_FUTURE_STATE")
        if s.last_attempted_at is not None and _utc(s.last_attempted_at, "LAST_ATTEMPT").date() > day:
            raise ValueError("DAILY_WATCH_SNAPSHOT_OUTSIDE_DAY")
        if snapshot.readiness is not None and (
            snapshot.readiness.source_id != p.source_id
            or snapshot.readiness.corpus_id != p.corpus_id
            or snapshot.readiness.policy_fingerprint != fingerprint
        ):
            raise ValueError("DAILY_WATCH_GATE_SCOPE_MISMATCH")
        coverage[p.source_id] = snapshot

    counters = (
        "attempts", "new", "modified", "unchanged", "unavailable", "blocked",
        "rate_limited", "metered_cost_micro_eur", "unknown_cost_attempts",
    )
    totals = {key: 0 for key in counters}
    by_source: dict[str, list[WatchCommittedAttempt]] = {source_id: [] for source_id in coverage}
    seen_attempts: set[tuple[str, str]] = set()
    for entry in committed_attempts:
        snapshot = coverage.get(entry.source_id)
        if snapshot is None:
            raise ValueError("DAILY_WATCH_UNKNOWN_SOURCE")
        if entry.plan.source_id != entry.source_id or entry.previous_state.source_id != entry.source_id:
            raise ValueError("DAILY_WATCH_SOURCE_MISMATCH")
        if not isinstance(entry.plan.attempted_at, datetime) or entry.plan.attempted_at.tzinfo is None:
            raise ValueError("DAILY_WATCH_ATTEMPT_TIME_INVALID")
        attempted = _utc(entry.plan.attempted_at, "DIGEST_ATTEMPTED_AT")
        if attempted.date() != day:
            raise ValueError("DAILY_WATCH_OUTSIDE_DAY")
        if attempted > through or _utc(entry.observation.observed_at, "DIGEST_OBSERVED_AT") > through:
            raise ValueError("DAILY_WATCH_FUTURE_RECEIPT")
        key = (entry.source_id, entry.plan.attempt_id)
        if key in seen_attempts:
            raise ValueError("DAILY_WATCH_DUPLICATE_ATTEMPT")
        seen_attempts.add(key)
        cost = entry.measured_cost_micro_eur
        if cost is not None and (type(cost) is not int or not 0 <= cost <= 10**12):
            raise ValueError("DAILY_WATCH_COST_INVALID")
        try:
            replanned = plan_watch_poll(
                snapshot.policy, entry.previous_state, entry.planning_readiness,
                attempt_id=entry.plan.attempt_id, attempted_at=entry.plan.attempted_at,
            )
            if not replanned.allowed or replanned != entry.plan:
                raise ValueError("replayed plan differs")
            replayed = reconcile_watch_observation(
                snapshot.policy, entry.previous_state,
                entry.reconciliation_readiness, entry.plan, entry.observation,
            )
            if replayed != entry.decision:
                raise ValueError("replayed decision differs")
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("DAILY_WATCH_INVALID_RECEIPT") from exc
        by_source[entry.source_id].append(entry)

    source_rows: list[WatchDailySourceHealth] = []
    watched = 0
    for source_id, snapshot in sorted(coverage.items()):
        policy, state = snapshot.policy, snapshot.state
        attempts = sorted(by_source[source_id], key=lambda e: e.plan.attempted_at)
        latest_disposition: str | None = None
        count = {key: 0 for key in counters}
        current: WatchState | None = None
        for entry in attempts:
            if current is None:
                previous_attempt = entry.previous_state.last_attempted_at
                if previous_attempt is not None and _utc(previous_attempt, "PREVIOUS_ATTEMPT").date() >= day:
                    raise ValueError("DAILY_WATCH_UNACCOUNTED_ATTEMPT")
            elif entry.previous_state != current:
                raise ValueError("DAILY_WATCH_CHAIN_MISMATCH")
            current = entry.decision.next_state
            latest_disposition = entry.decision.disposition
            count["attempts"] += 1
            disposition = entry.decision.disposition
            if disposition == "CHANGED":
                if entry.previous_state.content_sha256 is None:
                    count["new"] += 1
                else:
                    count["modified"] += 1
            elif disposition == "UNCHANGED":
                count["unchanged"] += 1
            elif disposition == "UNAVAILABLE":
                count["unavailable"] += 1
            elif disposition == "BLOCKED":
                count["blocked"] += 1
            if disposition == "UNAVAILABLE" and entry.observation.status_code == 429:
                count["rate_limited"] += 1
            if entry.measured_cost_micro_eur is None:
                count["unknown_cost_attempts"] += 1
            else:
                count["metered_cost_micro_eur"] += entry.measured_cost_micro_eur
        if current is not None and current != state:
            raise ValueError("DAILY_WATCH_SNAPSHOT_MISMATCH")
        if current is None and (state.last_attempted_at is not None
                                and day <= _utc(state.last_attempted_at, "LAST_ATTEMPT").date()):
            raise ValueError("DAILY_WATCH_UNACCOUNTED_ATTEMPT")

        fingerprint = policy_fingerprint(policy)
        reason = (_gate_reason(policy, snapshot.readiness, fingerprint)
                  if snapshot.readiness is not None else "GATE_READBACK_MISSING")
        watch_status = "NOT_WATCHED" if not policy.enabled else ("BLOCKED" if reason else "WATCHED")
        watched += int(policy.enabled)
        gaps = ["CORPUS_CUTOFF_LIMITED"]
        if not policy.enabled:
            gaps.append("NOT_WATCHED")
        elif reason is not None:
            if reason.startswith("RIGHTS_"):
                gaps.append("RIGHTS_BLOCKED")
            elif reason.startswith("CAPABILITY_"):
                gaps.append("CAPABILITY_BLOCKED")
            elif reason.startswith("BUDGET_") or reason == "CAP_EXHAUSTED":
                gaps.append("BUDGET_BLOCKED")
            else:
                gaps.append("READINESS_UNKNOWN")
        if state.last_successful_observed_at is None:
            gaps.append("NO_SUCCESSFUL_OBSERVATION")
        if state.retry_not_before is not None and _utc(state.retry_not_before, "RETRY") > through:
            gaps.append("SOURCE_BACKOFF")
        if state.consecutive_failures:
            gaps.append("SOURCE_FAILURES_RECORDED")
        if latest_disposition == "UNAVAILABLE":
            gaps.append("SOURCE_UNAVAILABLE")
        source_rows.append(WatchDailySourceHealth(
            source_id, policy.source_family, policy.corpus_id, policy.corpus_cutoff,
            watch_status, "WATCH_DISABLED" if not policy.enabled else reason,
            state.last_attempted_at, state.last_successful_observed_at,
            state.retry_not_before, state.consecutive_failures,
            latest_disposition, tuple(gaps),
            *(count[key] for key in counters),
        ))
        for key in counters:
            totals[key] += count[key]

    return WatchDailyHealthDigest(
        day, through, tuple(source_rows), watched, len(source_rows) - watched,
        *(totals[key] for key in counters),
    )


__all__ = [
    "WATCH_VERSION", "WatchPolicy", "WatchState", "WatchReadiness", "WatchPlan",
    "WatchObservation", "WatchChildProposal", "WatchDecision",
    "policy_fingerprint", "plan_watch_poll", "reconcile_watch_observation",
    "WatchCoverageSnapshot", "WatchCommittedAttempt", "WatchDailySourceHealth",
    "WatchDailyHealthDigest", "build_private_watch_daily_digest",
]
