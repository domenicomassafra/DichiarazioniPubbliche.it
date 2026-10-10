"""Cost budget policy for Dichiarazioni Pubbliche (DP-506).

A pure, total cost model plus a fail-closed preflight decision. The runtime
worker and scheduler already enforce three caps (``max_cost_usd_per_job``,
``max_cost_usd_per_source_day``, ``max_cost_usd_per_day``); this module makes
that policy explicit, testable in isolation, and shared by both so the two
daemons cannot drift apart.

The central invariant is the fail-closed one: an estimate that cannot be
computed with confidence must NOT be treated as zero. Treating an unknown cost
as free is exactly how a budget "cannot explode" guarantee becomes a budget
that explodes. So :func:`estimate_cost_usd` returns ``None`` for anything
unpriced, and :func:`preflight` denies every paid lane whose estimate is
``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo


# --- Unit economics --------------------------------------------------------
#
# These are *policy inputs*, not market facts. The documented ASR price
# (USD 0.04/audio-hour) was verified upstream on 2026-09-22; claim extraction
# is priced from the operator-configured ceiling, because the actual route
# cost is an operator decision, not a constant. Changing a number here changes
# an operational expectation, so each rate carries the provenance of its value.

USD_PER_AUDIO_HOUR = 0.04
USD_PER_EVIDENCE_REQUEST = 0.0  # evidence retrieval is free, metered by rate limit

RATE_PROVENANCE: Mapping[str, str] = {
    "USD_PER_AUDIO_HOUR": (
        "https://console.groq.com/docs/speech-to-text, verified 2026-09-22; "
        "policy input, not a permanent guarantee"
    ),
    "USD_PER_EVIDENCE_REQUEST": "official evidence retrieval is free; rate-limited instead",
}

# Hard ceilings. These are circuit breakers, not spending targets.
DEFAULT_MAX_COST_USD_PER_JOB = 0.25
DEFAULT_MAX_COST_USD_PER_SOURCE_DAY = 1.0
DEFAULT_MAX_COST_USD_PER_DAY = 5.0

# A lane is only allowed to spend if its unit rate is known. Unknown rate ==
# blocked, not free.
PAID_OPERATIONS = ("AUDIO_TRANSCRIPTION", "CLAIM_EXTRACT")

ZERO_COST_OPERATIONS = (
    "TRANSCRIPT_CAPTION",
    "EVIDENCE_FETCH_URL",
    "EVIDENCE_QUERY_OFFICIAL",
    "PUBLIC_PROJECTION_BUILD",
)


@dataclass(frozen=True)
class CostSnapshot:
    global_day_usd: float
    source_day_usd: float


@dataclass(frozen=True)
class BudgetPolicy:
    max_cost_usd_per_job: float = DEFAULT_MAX_COST_USD_PER_JOB
    max_cost_usd_per_source_day: float = DEFAULT_MAX_COST_USD_PER_SOURCE_DAY
    max_cost_usd_per_day: float = DEFAULT_MAX_COST_USD_PER_DAY

    def remaining_global_usd(self, snapshot: CostSnapshot) -> float:
        return max(0.0, self.max_cost_usd_per_day - snapshot.global_day_usd)

    def remaining_source_usd(self, snapshot: CostSnapshot) -> float:
        return max(0.0, self.max_cost_usd_per_source_day - snapshot.source_day_usd)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    estimate_usd: float | None
    policy: BudgetPolicy
    snapshot: CostSnapshot

    @property
    def blocks(self) -> bool:
        """True when the decision must surface as an explicit blocked/deferred state."""
        return not self.allowed


def estimate_cost_usd(
    operation: str,
    *,
    input_seconds: float | None = None,
    input_bytes: int | None = None,
    request_count: int = 1,
    max_usd_per_1k_total_tokens: float | None = None,
    total_tokens: int | None = None,
) -> float | None:
    """Best-effort pre-execution cost estimate.

    Returns ``None`` -- meaning *unpriced*, i.e. the caller must block -- when
    the operation has a real marginal cost and the inputs needed to price it
    are missing. It never guesses.
    """
    op = str(operation or "").strip()

    if op in ZERO_COST_OPERATIONS:
        return 0.0

    if op == "AUDIO_TRANSCRIPTION":
        if input_seconds is None or input_seconds < 0:
            return None
        return round((float(input_seconds) / 3600.0) * USD_PER_AUDIO_HOUR, 6)

    if op == "CLAIM_EXTRACT":
        if max_usd_per_1k_total_tokens is None or max_usd_per_1k_total_tokens < 0:
            return None
        if total_tokens is None or total_tokens < 0:
            return None
        return round((float(total_tokens) / 1000.0) * float(max_usd_per_1k_total_tokens), 6)

    if op in PAID_OPERATIONS:
        return None

    # An unknown operation is not free. This is the fail-closed default.
    return None


def preflight(
    policy: BudgetPolicy,
    snapshot: CostSnapshot,
    estimate_usd: float | None,
    *,
    operation: str = "",
) -> BudgetDecision:
    """Decide whether a paid lane may run. Deny by default.

    Every deny path returns a machine-readable reason so the worker can map it
    to ``DEFERRED`` (budget exhaustion: temporary, will resume) or ``BLOCKED``
    (unpriced/missing cost model: needs an operator decision). Conflating those
    two is a real operational bug: a budget cap should not page anyone.
    """
    if estimate_usd is None or str(operation or "") == "":
        return BudgetDecision(False, "COST_MODEL_MISSING", None, policy, snapshot)

    try:
        estimate = float(estimate_usd)
    except (TypeError, ValueError):
        return BudgetDecision(False, "COST_MODEL_MISSING", None, policy, snapshot)

    if estimate < 0:
        return BudgetDecision(False, "COST_ESTIMATE_INVALID", None, policy, snapshot)

    if estimate > policy.max_cost_usd_per_job:
        return BudgetDecision(
            False, "JOB_COST_CAP_REACHED", estimate, policy, snapshot
        )

    if estimate == 0:
        return BudgetDecision(True, "ALLOWED_ZERO_COST", 0.0, policy, snapshot)

    if snapshot.global_day_usd + estimate > policy.max_cost_usd_per_day:
        return BudgetDecision(
            False, "GLOBAL_DAILY_BUDGET_REACHED", estimate, policy, snapshot
        )

    if snapshot.source_day_usd + estimate > policy.max_cost_usd_per_source_day:
        return BudgetDecision(
            False, "SOURCE_DAILY_BUDGET_REACHED", estimate, policy, snapshot
        )

    return BudgetDecision(True, "ALLOWED", estimate, policy, snapshot)


def classify_decision_reason(reason: str) -> str:
    """Map a deny reason onto the job state the runtime should record.

    ``DEFER`` reasons are temporary and self-healing (budget exhaustion, rate
    limit). ``BLOCK`` reasons need an operator decision. ``ALLOW`` is the
    success path. Anything unrecognised is treated as BLOCK, because an
    unknown reason must not be silently treated as permission to spend.
    """
    value = str(reason or "")
    if value.startswith("ALLOWED"):
        return "ALLOW"
    if value in {"GLOBAL_DAILY_BUDGET_REACHED", "SOURCE_DAILY_BUDGET_REACHED", "JOB_COST_CAP_REACHED"}:
        return "DEFER"
    if value in {"COST_MODEL_MISSING", "COST_ESTIMATE_INVALID"}:
        return "BLOCK"
    return "BLOCK"


def remaining_budget_report(
    policy: BudgetPolicy, snapshot: CostSnapshot
) -> dict[str, Any]:
    """Operator-facing budget picture for the digest."""
    return {
        "global_day_usd": round(snapshot.global_day_usd, 6),
        "global_cap_usd": policy.max_cost_usd_per_day,
        "global_remaining_usd": round(policy.remaining_global_usd(snapshot), 6),
        "source_day_usd": round(snapshot.source_day_usd, 6),
        "source_cap_usd": policy.max_cost_usd_per_source_day,
        "source_remaining_usd": round(policy.remaining_source_usd(snapshot), 6),
        "per_job_cap_usd": policy.max_cost_usd_per_job,
        "rates": {
            "usd_per_audio_hour": USD_PER_AUDIO_HOUR,
            "usd_per_evidence_request": USD_PER_EVIDENCE_REQUEST,
        },
        "rate_provenance": dict(RATE_PROVENANCE),
    }


def validate_cost_policy(
    policy: BudgetPolicy = BudgetPolicy(),
) -> tuple[str, ...]:
    """Structural self-check; empty tuple means the budget policy is coherent."""
    defects: list[str] = []
    for name, value in (
        ("max_cost_usd_per_job", policy.max_cost_usd_per_job),
        ("max_cost_usd_per_source_day", policy.max_cost_usd_per_source_day),
        ("max_cost_usd_per_day", policy.max_cost_usd_per_day),
    ):
        if value < 0:
            defects.append(f"negative_cap:{name}")
    if policy.max_cost_usd_per_source_day > policy.max_cost_usd_per_day:
        defects.append("source_cap_exceeds_global_cap")
    if policy.max_cost_usd_per_job > policy.max_cost_usd_per_day:
        defects.append("job_cap_exceeds_global_cap")
    if USD_PER_AUDIO_HOUR < 0:
        defects.append("negative_rate:usd_per_audio_hour")
    overlap = set(PAID_OPERATIONS) & set(ZERO_COST_OPERATIONS)
    if overlap:
        defects.append(f"operation_class_conflict:{sorted(overlap)}")
    return tuple(defects)


# --- DP-514: isolated monthly reservation proposal -------------------------
#
# This contract is intentionally not called by any live scheduler or worker.
# A snapshot/revision check in Python is NOT an atomic concurrent reservation.
# A future owning persistence layer must commit the proposal by a single
# transactional compare-and-swap (period, policy_version, revision, fingerprint)
# and recheck the USD job/source/day caps and provider quotas in the same
# transaction before admitting the corresponding job. On CAS failure it must
# reread and preflight again. Until then, dispatch_authorized is always False.
#
# EUR 10 is a *tentative* owner planning target, never an enabled default.
# All FX values are explicit caller-supplied observations: no guessed market
# rates, bundled-plan entitlements or local energy costs enter cash balances.

_EUR_MICRO = Decimal("0.000001")
_MAX_DECIMAL = Decimal("1000000000")
_MAX_MONTH_RESERVATIONS = 4096
_MONTH_ZONES = {"UTC", "Europe/Rome"}
_MONTH_PATTERN = re.compile(r"^([0-9]{4})-(0[1-9]|1[0-2])@(UTC|Europe/Rome)$")


def _monthly_decimal(value: Decimal | str | int, *, field: str, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValueError(f"{field}_INVALID")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}_INVALID") from None
    if not amount.is_finite() or amount < 0 or amount > _MAX_DECIMAL:
        raise ValueError(f"{field}_INVALID")
    if positive and amount == 0:
        raise ValueError(f"{field}_INVALID")
    return amount


def _aware_time(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("MONTHLY_AWARE_TIME_REQUIRED")
    return at.astimezone(timezone.utc)


def monthly_period(at: datetime, timezone_name: str) -> str:
    """Explicit accounting month; provider quota/billing resets are separate."""
    if timezone_name not in _MONTH_ZONES:
        raise ValueError("MONTHLY_TIMEZONE_UNSUPPORTED")
    moment = _aware_time(at).astimezone(ZoneInfo(timezone_name))
    return f"{moment:%Y-%m}@{timezone_name}"


@dataclass(frozen=True)
class MonthlyEurPolicy:
    """Opt-in planning constraint. Never modifies DP-506's existing USD limits."""

    version: str
    cap_eur: Decimal
    enabled: bool = False
    timezone_name: str = "Europe/Rome"
    max_fx_age_seconds: int = 86400

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("MONTHLY_POLICY_VERSION_REQUIRED")
        if not isinstance(self.enabled, bool):
            raise ValueError("MONTHLY_POLICY_ENABLED_INVALID")
        if self.timezone_name not in _MONTH_ZONES:
            raise ValueError("MONTHLY_TIMEZONE_UNSUPPORTED")
        if isinstance(self.max_fx_age_seconds, bool) or (
            not isinstance(self.max_fx_age_seconds, int)
            or not 0 < self.max_fx_age_seconds <= 86400
        ):
            raise ValueError("MONTHLY_FX_MAX_AGE_INVALID")
        object.__setattr__(
            self, "cap_eur", _monthly_decimal(self.cap_eur, field="MONTHLY_CAP", positive=True)
        )


@dataclass(frozen=True)
class MonthlyFxQuote:
    """Explicit EUR per USD quote. Source trust is the caller's responsibility."""

    rate_eur_per_usd: Decimal
    reference: str
    source: str
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "rate_eur_per_usd",
            _monthly_decimal(self.rate_eur_per_usd, field="MONTHLY_FX", positive=True),
        )
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise ValueError("MONTHLY_FX_REFERENCE_REQUIRED")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("MONTHLY_FX_SOURCE_REQUIRED")
        _aware_time(self.observed_at)


@dataclass(frozen=True)
class MonthlyReservation:
    attempt_id: str
    operation: str
    upper_bound_usd: Decimal
    held_eur: Decimal
    fx_reference: str
    fx_source: str
    fx_rate_eur_per_usd: Decimal
    fx_observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
            raise ValueError("MONTHLY_ATTEMPT_ID_REQUIRED")
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("MONTHLY_OPERATION_REQUIRED")
        for name in ("upper_bound_usd", "held_eur"):
            object.__setattr__(
                self, name, _monthly_decimal(getattr(self, name), field=f"MONTHLY_{name.upper()}", positive=True)
            )
        if not isinstance(self.fx_reference, str) or not self.fx_reference.strip():
            raise ValueError("MONTHLY_FX_REFERENCE_REQUIRED")
        if not isinstance(self.fx_source, str) or not self.fx_source.strip():
            raise ValueError("MONTHLY_FX_SOURCE_REQUIRED")
        object.__setattr__(
            self, "fx_rate_eur_per_usd",
            _monthly_decimal(self.fx_rate_eur_per_usd, field="MONTHLY_FX", positive=True),
        )
        _aware_time(self.fx_observed_at)


@dataclass(frozen=True)
class MonthlyBudgetState:
    """One entire accounting period. Caller must use durable atomic storage."""

    period: str
    policy_version: str
    revision: int
    settled_eur: Decimal = Decimal("0")
    reservations: tuple[MonthlyReservation, ...] = ()
    unknown_liability: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.period, str) or _MONTH_PATTERN.fullmatch(self.period) is None:
            raise ValueError("MONTHLY_PERIOD_INVALID")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("MONTHLY_POLICY_VERSION_REQUIRED")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError("MONTHLY_REVISION_INVALID")
        if not isinstance(self.unknown_liability, bool):
            raise ValueError("MONTHLY_UNKNOWN_LIABILITY_INVALID")
        object.__setattr__(
            self, "settled_eur", _monthly_decimal(self.settled_eur, field="MONTHLY_SETTLED")
        )
        if not isinstance(self.reservations, tuple) or any(
            not isinstance(row, MonthlyReservation) for row in self.reservations
        ):
            raise ValueError("MONTHLY_RESERVATIONS_INVALID")
        if len({row.attempt_id for row in self.reservations}) != len(self.reservations):
            raise ValueError("MONTHLY_DUPLICATE_RESERVATION_ID")
        if len(self.reservations) > _MAX_MONTH_RESERVATIONS:
            raise ValueError("MONTHLY_RESERVATION_LIMIT_REACHED")

    @property
    def held_total_eur(self) -> Decimal:
        return sum((row.held_eur for row in self.reservations), Decimal("0"))

    @property
    def committed_total_eur(self) -> Decimal:
        return self.settled_eur + self.held_total_eur

    def fingerprint(self) -> str:
        """Compare this AND revision in the eventual atomic database update."""
        payload = {
            "period": self.period,
            "policy_version": self.policy_version,
            "revision": self.revision,
            "settled_eur": str(self.settled_eur),
            "unknown_liability": self.unknown_liability,
            "reservations": [
                {
                    "attempt_id": item.attempt_id,
                    "operation": item.operation,
                    "upper_bound_usd": str(item.upper_bound_usd),
                    "held_eur": str(item.held_eur),
                    "fx_reference": item.fx_reference,
                    "fx_source": item.fx_source,
                    "fx_rate_eur_per_usd": str(item.fx_rate_eur_per_usd),
                    "fx_observed_at": _aware_time(item.fx_observed_at).isoformat(),
                }
                for item in self.reservations
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class MonthlyReservationDecision:
    eligible: bool
    reason: str
    expected_revision: int
    expected_state_sha256: str
    proposed_state: MonthlyBudgetState | None = None
    # Explicitly a PLAN, never permission to call a provider or enqueue a job.
    dispatch_authorized: bool = False


def monthly_budget_preflight(
    *,
    policy: MonthlyEurPolicy,
    state: MonthlyBudgetState,
    attempt_id: str,
    operation: str,
    upper_bound_usd: Decimal | None,
    billing_basis: str,
    at: datetime,
    fx_quote: MonthlyFxQuote | None,
    legacy_policy: BudgetPolicy,
    legacy_snapshot: CostSnapshot,
    expected_revision: int,
) -> MonthlyReservationDecision:
    """Pure candidate CAS state; never independently authorizes paid dispatch.

    Uses ESTIMATED_ONLY positive USD *upper bounds*, plus caller-provided fresh
    FX, to reserve a conservatively rounded EUR amount. A valid plan must be
    installed via one external atomic CAS across all competing workers. No
    scheduler consumes this function in DP-514's source-only first increment.
    """
    fingerprint = state.fingerprint()

    def deny(reason: str) -> MonthlyReservationDecision:
        return MonthlyReservationDecision(False, reason, state.revision, fingerprint)

    if not policy.enabled:
        return deny("MONTHLY_POLICY_DISABLED")
    try:
        period = monthly_period(at, policy.timezone_name)
    except ValueError:
        return deny("MONTHLY_TIME_INVALID")
    if policy.version != state.policy_version:
        return deny("MONTHLY_POLICY_VERSION_MISMATCH")
    if state.period != period:
        return deny("MONTHLY_PERIOD_MISMATCH")
    if expected_revision != state.revision:
        return deny("MONTHLY_STATE_REVISION_STALE")
    if state.unknown_liability:
        return deny("MONTHLY_UNKNOWN_LIABILITY")
    if not isinstance(attempt_id, str) or not attempt_id.strip():
        return deny("MONTHLY_ATTEMPT_ID_REQUIRED")
    if not isinstance(operation, str) or not operation.strip():
        return deny("MONTHLY_OPERATION_REQUIRED")
    if billing_basis != "ESTIMATED_ONLY":
        # Measured historical bills, opaque plans and unverified "zero" calls
        # cannot substitute for a bound on this future paid attempt.
        return deny("MONTHLY_BILLING_BASIS_UNPRICED")
    try:
        amount = _monthly_decimal(upper_bound_usd, field="MONTHLY_UPPER_BOUND", positive=True)
    except ValueError:
        return deny("MONTHLY_COST_UNKNOWN_OR_INVALID")
    existing = next((row for row in state.reservations if row.attempt_id == attempt_id), None)
    if existing is not None:
        if existing.operation == operation and existing.upper_bound_usd == amount:
            return deny("MONTHLY_RESERVATION_ALREADY_RECORDED")
        return deny("MONTHLY_ATTEMPT_ID_CONFLICT")
    if len(state.reservations) >= _MAX_MONTH_RESERVATIONS:
        return deny("MONTHLY_RESERVATION_LIMIT_REACHED")

    # Retain all three existing USD guards. The real dispatcher will need to
    # recheck their snapshots atomically alongside the monthly reservation.
    legacy = preflight(
        legacy_policy, legacy_snapshot,
        float(amount.quantize(_EUR_MICRO, rounding=ROUND_CEILING)),
        operation=operation,
    )
    if not legacy.allowed:
        return deny(legacy.reason)
    if fx_quote is None:
        return deny("MONTHLY_FX_REQUIRED")
    moment = _aware_time(at)
    observed = _aware_time(fx_quote.observed_at)
    if observed > moment:
        return deny("MONTHLY_FX_FROM_FUTURE")
    if moment - observed > timedelta(seconds=policy.max_fx_age_seconds):
        return deny("MONTHLY_FX_STALE")
    try:
        held = (amount * fx_quote.rate_eur_per_usd).quantize(
            _EUR_MICRO, rounding=ROUND_CEILING
        )
    except InvalidOperation:
        return deny("MONTHLY_FX_AMOUNT_INVALID")
    if held <= 0 or held > _MAX_DECIMAL:
        return deny("MONTHLY_FX_AMOUNT_INVALID")
    if state.committed_total_eur + held > policy.cap_eur:
        return deny("MONTHLY_CAP_REACHED")

    proposal = replace(
        state,
        revision=state.revision + 1,
        reservations=state.reservations + (
            MonthlyReservation(
                attempt_id=attempt_id, operation=operation,
                upper_bound_usd=amount, held_eur=held,
                fx_reference=fx_quote.reference, fx_source=fx_quote.source,
                fx_rate_eur_per_usd=fx_quote.rate_eur_per_usd,
                fx_observed_at=fx_quote.observed_at,
            ),
        ),
    )
    return MonthlyReservationDecision(
        True, "MONTHLY_RESERVATION_PROPOSED", state.revision, fingerprint, proposal
    )
