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

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import re
import sqlite3
from pathlib import Path
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


# SQLite below is an *isolated persistence/concurrency proof* for DP-514.
# It is not connected to the PostgreSQL queue, its daily USD ledger, or the
# independent owner policy authority. Committed reservations cannot dispatch.


def _monthly_policy_sha256(policy: MonthlyEurPolicy) -> str:
    payload = {
        "version": policy.version,
        "cap_eur": str(policy.cap_eur),
        "enabled": policy.enabled,
        "timezone_name": policy.timezone_name,
        "max_fx_age_seconds": policy.max_fx_age_seconds,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _encode_monthly_state(state: MonthlyBudgetState) -> str:
    return json.dumps(asdict(state), default=str, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


def _decode_monthly_state(raw: str, fingerprint: str) -> MonthlyBudgetState:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "period", "policy_version", "revision", "settled_eur",
            "reservations", "unknown_liability",
        } or not isinstance(payload["reservations"], list):
            raise ValueError("invalid monthly state shape")
        reservations = []
        for item in payload["reservations"]:
            if not isinstance(item, dict) or set(item) != {
                "attempt_id", "operation", "upper_bound_usd", "held_eur",
                "fx_reference", "fx_source", "fx_rate_eur_per_usd", "fx_observed_at",
            }:
                raise ValueError("invalid monthly reservation shape")
            reservations.append(MonthlyReservation(
                attempt_id=item["attempt_id"], operation=item["operation"],
                upper_bound_usd=item["upper_bound_usd"], held_eur=item["held_eur"],
                fx_reference=item["fx_reference"], fx_source=item["fx_source"],
                fx_rate_eur_per_usd=item["fx_rate_eur_per_usd"],
                fx_observed_at=datetime.fromisoformat(item["fx_observed_at"]),
            ))
        state = MonthlyBudgetState(
            period=payload["period"], policy_version=payload["policy_version"],
            revision=payload["revision"], settled_eur=payload["settled_eur"],
            reservations=tuple(reservations),
            unknown_liability=payload["unknown_liability"],
        )
        if state.fingerprint() != fingerprint:
            raise ValueError("monthly state fingerprint mismatch")
        return state
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE") from exc


@dataclass(frozen=True)
class SQLiteMonthlyReservationResult:
    committed: bool
    reason: str
    state: MonthlyBudgetState | None = None
    dispatch_authorized: bool = False


_MONTH_OBSERVATION_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:.-]{0,127}\Z", re.ASCII)
_MONTH_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


@dataclass(frozen=True)
class MonthlySettlementObservation:
    """Untrusted, caller-reported private cost/unknown observation.

    Supplying source reference/hash never attests an invoice or refunds spend.
    No raw provider receipt, credential, account identity or text is stored.
    """

    observation_id: str
    attempt_id: str
    operation: str
    status: str  # REPORTED_UNVERIFIED | UNKNOWN
    reported_cost_usd: Decimal | None
    source_reference: str | None
    source_sha256: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        for field in ("observation_id", "attempt_id", "operation"):
            ref = getattr(self, field)
            if not isinstance(ref, str) or not _MONTH_OBSERVATION_REF.fullmatch(ref):
                raise ValueError("MONTHLY_OBSERVATION_REFERENCE_INVALID")
        _aware_time(self.observed_at)
        if self.status == "UNKNOWN":
            if any(value is not None for value in (
                self.reported_cost_usd, self.source_reference, self.source_sha256
            )):
                raise ValueError("MONTHLY_UNKNOWN_OBSERVATION_MUST_NOT_PRICE")
        elif self.status == "REPORTED_UNVERIFIED":
            object.__setattr__(self, "reported_cost_usd", _monthly_decimal(
                self.reported_cost_usd, field="MONTHLY_OBSERVATION_COST",
            ))
            if (not isinstance(self.source_reference, str)
                    or not _MONTH_OBSERVATION_REF.fullmatch(self.source_reference)
                    or not isinstance(self.source_sha256, str)
                    or not _MONTH_SHA256.fullmatch(self.source_sha256)):
                raise ValueError("MONTHLY_OBSERVATION_SOURCE_INVALID")
        else:
            raise ValueError("MONTHLY_OBSERVATION_STATUS_INVALID")


@dataclass(frozen=True)
class MonthlySettlementReceipt:
    """Write-once SQLite receipt; amount is provisional, not billed authority."""

    period: str
    observation: MonthlySettlementObservation
    status: str  # PROVISIONAL_HELD | UNKNOWN_HELD | OVER_BOUND_HELD
    held_eur: Decimal
    provisional_eur: Decimal | None
    fx_reference: str
    state_revision: int
    previous_state_sha256: str
    resulting_state_sha256: str
    invoice_attested: bool = False
    dispatch_authorized: bool = False


def _settlement_receipt_json(receipt: MonthlySettlementReceipt) -> str:
    return json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, default=str)


def _settlement_receipt_sha256(receipt: MonthlySettlementReceipt) -> str:
    return hashlib.sha256(_settlement_receipt_json(receipt).encode("ascii")).hexdigest()


def _loaded_settlement_receipt(raw: str, fingerprint: str) -> MonthlySettlementReceipt:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "period", "observation", "status", "held_eur", "provisional_eur",
            "fx_reference", "state_revision", "previous_state_sha256",
            "resulting_state_sha256", "invoice_attested", "dispatch_authorized",
        }:
            raise ValueError("invalid receipt shape")
        data = payload["observation"]
        if not isinstance(data, dict) or set(data) != {
            "observation_id", "attempt_id", "operation", "status",
            "reported_cost_usd", "source_reference", "source_sha256", "observed_at",
        }:
            raise ValueError("invalid observation shape")
        observation = MonthlySettlementObservation(
            **{**data, "observed_at": datetime.fromisoformat(data["observed_at"])}
        )
        receipt = MonthlySettlementReceipt(
            period=payload["period"], observation=observation,
            status=payload["status"],
            held_eur=_monthly_decimal(payload["held_eur"], field="MONTHLY_HELD"),
            provisional_eur=(None if payload["provisional_eur"] is None else
                             _monthly_decimal(payload["provisional_eur"], field="MONTHLY_PROVISIONAL")),
            fx_reference=payload["fx_reference"], state_revision=payload["state_revision"],
            previous_state_sha256=payload["previous_state_sha256"],
            resulting_state_sha256=payload["resulting_state_sha256"],
            invoice_attested=payload["invoice_attested"],
            dispatch_authorized=payload["dispatch_authorized"],
        )
        if (receipt.status not in {"PROVISIONAL_HELD", "UNKNOWN_HELD", "OVER_BOUND_HELD"}
                or receipt.invoice_attested is not False
                or receipt.dispatch_authorized is not False
                or type(receipt.state_revision) is not int or receipt.state_revision < 1
                or not isinstance(receipt.fx_reference, str) or not receipt.fx_reference
                or not all(isinstance(sha, str) and _MONTH_SHA256.fullmatch(sha)
                           for sha in (receipt.previous_state_sha256,
                                       receipt.resulting_state_sha256))
                or (receipt.status == "UNKNOWN_HELD") != (observation.status == "UNKNOWN")
                or (receipt.provisional_eur is None) != (observation.status == "UNKNOWN")
                or not _MONTH_PATTERN.fullmatch(receipt.period)
                or _settlement_receipt_sha256(receipt) != fingerprint):
            raise ValueError("receipt integrity mismatch")
        return receipt
    except (TypeError, ValueError, KeyError, OverflowError, InvalidOperation) as exc:
        raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE") from exc


@dataclass(frozen=True)
class SQLiteMonthlySettlementResult:
    committed: bool
    reason: str
    receipt: MonthlySettlementReceipt | None = None
    dispatch_authorized: bool = False
    invoice_attested: bool = False


@dataclass(frozen=True)
class SQLiteMonthlyReconciliationReport:
    period: str
    observed_attempts: int
    provisional_observed_eur: Decimal
    held_total_eur: Decimal
    settled_eur: Decimal
    unknown_attempts: int
    over_bound_attempts: int
    unknown_liability: bool
    authoritative_billed_eur: None = None
    invoice_attested: bool = False
    dispatch_authorized: bool = False


class SQLiteMonthlyReservationStore:
    """Disposable database proof: serialized cross-connection EUR reservations.

    Every reservation reads/preflights/commits under SQLite's BEGIN IMMEDIATE
    writer transaction. A caller must explicitly bootstrap its synthetic month.
    Neither successful persistence nor a supplied policy attests real invoices,
    USD daily totals, provider quotas, or permission to spend.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=FULL")
        except sqlite3.Error:
            conn.close()
            raise
        return conn

    def initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_budget_state (
                    period TEXT PRIMARY KEY,
                    policy_sha256 TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 0),
                    state_sha256 TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_reconciliation_receipt (
                    period TEXT NOT NULL,
                    attempt_id TEXT NOT NULL UNIQUE,
                    observation_id TEXT NOT NULL UNIQUE,
                    receipt_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    PRIMARY KEY (period, attempt_id)
                )
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS monthly_reconciliation_receipt_no_update
                BEFORE UPDATE ON monthly_reconciliation_receipt
                BEGIN SELECT RAISE(ABORT, 'monthly reconciliation is immutable'); END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS monthly_reconciliation_receipt_no_delete
                BEFORE DELETE ON monthly_reconciliation_receipt
                BEGIN SELECT RAISE(ABORT, 'monthly reconciliation is immutable'); END
            """)
            # A queue job attempt identifies one paid operation, not one
            # accounting period. A repeated attempt after the Rome month flips
            # must not mint a second hold with a fresh empty month. Backfill
            # existing isolated ledgers atomically at the additive upgrade.
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_global_attempt (
                    attempt_id TEXT PRIMARY KEY, period TEXT NOT NULL,
                    operation TEXT NOT NULL, upper_bound_usd TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS monthly_global_attempt_no_update
                BEFORE UPDATE ON monthly_global_attempt
                BEGIN SELECT RAISE(ABORT, 'monthly attempt scope is immutable'); END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS monthly_global_attempt_no_delete
                BEFORE DELETE ON monthly_global_attempt
                BEGIN SELECT RAISE(ABORT, 'monthly attempt scope is immutable'); END
            """)
            expected: dict[str, tuple[str, str, str]] = {}
            for period, revision, sha, raw in conn.execute(
                "SELECT period,revision,state_sha256,state_json FROM monthly_budget_state"
            ):
                state = self._loaded_state((revision, sha, raw))
                if state.period != period:
                    raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
                for item in state.reservations:
                    value = (period, item.operation, str(item.upper_bound_usd))
                    if item.attempt_id in expected and expected[item.attempt_id] != value:
                        raise ValueError("MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT")
                    expected[item.attempt_id] = value
            for attempt_id, value in expected.items():
                conn.execute("""
                    INSERT OR IGNORE INTO monthly_global_attempt
                        (attempt_id,period,operation,upper_bound_usd)
                    VALUES (?,?,?,?)
                """, (attempt_id, *value))
            stored = dict((row[0], tuple(row[1:])) for row in conn.execute(
                "SELECT attempt_id,period,operation,upper_bound_usd FROM monthly_global_attempt"
            ))
            if stored != expected:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def bootstrap(self, policy: MonthlyEurPolicy, state: MonthlyBudgetState) -> bool:
        """Seed a synthetic empty month once; never reset an occupied month."""
        if (not policy.enabled or state.policy_version != policy.version
                or not state.period.endswith("@" + policy.timezone_name)
                or state.revision != 0 or state.settled_eur != 0
                or state.reservations or state.unknown_liability):
            raise ValueError("MONTHLY_BOOTSTRAP_REQUIRES_EMPTY_SYNTHETIC_PERIOD")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute("""
                INSERT INTO monthly_budget_state (
                    period, policy_sha256, revision, state_sha256, state_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(period) DO NOTHING
            """, (state.period, _monthly_policy_sha256(policy), 0,
                  state.fingerprint(), _encode_monthly_state(state)))
            conn.commit()
            return result.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _loaded_state(row: tuple[object, ...]) -> MonthlyBudgetState:
        revision, fingerprint, raw = row
        if not isinstance(revision, int) or not isinstance(fingerprint, str) or not isinstance(raw, str):
            raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
        state = _decode_monthly_state(raw, fingerprint)
        if state.revision != revision:
            raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
        return state

    def read(self, period: str) -> MonthlyBudgetState:
        conn = self._connect()
        try:
            row = conn.execute("""
                SELECT revision, state_sha256, state_json
                FROM monthly_budget_state WHERE period = ?
            """, (period,)).fetchone()
            if row is None:
                raise ValueError("MONTHLY_PERIOD_NOT_BOOTSTRAPPED")
            state = self._loaded_state(row)
            if state.period != period:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            return state
        finally:
            conn.close()

    def reserve(
        self, *, policy: MonthlyEurPolicy, attempt_id: str, operation: str,
        upper_bound_usd: Decimal | None, billing_basis: str,
        at: datetime, fx_quote: MonthlyFxQuote | None,
        legacy_policy: BudgetPolicy, legacy_snapshot: CostSnapshot,
    ) -> SQLiteMonthlyReservationResult:
        """Atomic synthetic month reservation; never a provider-dispatch permit."""
        if not policy.enabled:
            return SQLiteMonthlyReservationResult(False, "MONTHLY_POLICY_DISABLED")
        try:
            period = monthly_period(at, policy.timezone_name)
        except ValueError:
            return SQLiteMonthlyReservationResult(False, "MONTHLY_TIME_INVALID")
        try:
            conn = self._connect()
        except sqlite3.Error:
            return SQLiteMonthlyReservationResult(False, "MONTHLY_STORAGE_UNAVAILABLE")
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""
                SELECT policy_sha256, revision, state_sha256, state_json
                FROM monthly_budget_state WHERE period = ?
            """, (period,)).fetchone()
            if row is None:
                return SQLiteMonthlyReservationResult(False, "MONTHLY_PERIOD_NOT_BOOTSTRAPPED")
            policy_sha, revision, old_sha, state_json = row
            if policy_sha != _monthly_policy_sha256(policy):
                return SQLiteMonthlyReservationResult(False, "MONTHLY_STORED_POLICY_MISMATCH")
            state = self._loaded_state((revision, old_sha, state_json))
            if state.period != period or state.policy_version != policy.version:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            prior_attempt = conn.execute("""
                SELECT period,operation,upper_bound_usd
                FROM monthly_global_attempt WHERE attempt_id = ?
            """, (attempt_id,)).fetchone()
            if prior_attempt is not None:
                if prior_attempt[0] != period:
                    return SQLiteMonthlyReservationResult(
                        False, "MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT", state,
                    )
                if not any(
                    item.attempt_id == attempt_id and item.operation == prior_attempt[1]
                    and str(item.upper_bound_usd) == prior_attempt[2]
                    for item in state.reservations
                ):
                    raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            # Unresolved invoices and over-limit observations cannot disappear
            # just because a *new* month has an empty reservations array.
            # Do not infer refund/clearance from a calendar rollover.
            for old_period, old_revision, old_sha, old_json in conn.execute("""
                SELECT period,revision,state_sha256,state_json
                FROM monthly_budget_state WHERE period < ?
                ORDER BY period
            """, (period,)):
                if not old_period.endswith("@" + policy.timezone_name):
                    continue
                previous = self._loaded_state((old_revision, old_sha, old_json))
                if previous.period != old_period:
                    raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
                if previous.unknown_liability:
                    return SQLiteMonthlyReservationResult(
                        False, "MONTHLY_PREVIOUS_PERIOD_UNRESOLVED", state,
                    )
            proposal = monthly_budget_preflight(
                policy=policy, state=state, attempt_id=attempt_id,
                operation=operation, upper_bound_usd=upper_bound_usd,
                billing_basis=billing_basis, at=at, fx_quote=fx_quote,
                legacy_policy=legacy_policy, legacy_snapshot=legacy_snapshot,
                expected_revision=state.revision,
            )
            if not proposal.eligible or proposal.proposed_state is None:
                return SQLiteMonthlyReservationResult(False, proposal.reason, state)
            next_state = proposal.proposed_state
            new_attempt = next_state.reservations[-1]
            conn.execute("""
                INSERT INTO monthly_global_attempt
                    (attempt_id,period,operation,upper_bound_usd)
                VALUES (?,?,?,?)
            """, (new_attempt.attempt_id, period, new_attempt.operation,
                  str(new_attempt.upper_bound_usd)))
            updated = conn.execute("""
                UPDATE monthly_budget_state
                SET revision = ?, state_sha256 = ?, state_json = ?
                WHERE period = ? AND policy_sha256 = ?
                  AND revision = ? AND state_sha256 = ?
            """, (next_state.revision, next_state.fingerprint(),
                  _encode_monthly_state(next_state), period, policy_sha,
                  proposal.expected_revision, proposal.expected_state_sha256))
            if updated.rowcount != 1:
                return SQLiteMonthlyReservationResult(False, "MONTHLY_STORAGE_CAS_CONFLICT")
            conn.commit()
            return SQLiteMonthlyReservationResult(True, "MONTHLY_RESERVATION_COMMITTED", next_state)
        except sqlite3.Error:
            return SQLiteMonthlyReservationResult(False, "MONTHLY_STORAGE_UNAVAILABLE")
        except ValueError:
            return SQLiteMonthlyReservationResult(False, "MONTHLY_STORAGE_INTEGRITY_FAILURE")
        finally:
            if conn.in_transaction:
                conn.rollback()
            conn.close()

    def reconcile(
        self, *, policy: MonthlyEurPolicy, period: str,
        observation: MonthlySettlementObservation,
    ) -> SQLiteMonthlySettlementResult:
        """Atomically record one untrusted, immutable attempt observation.

        The pinned reservation FX rate gives a *provisional* comparison only.
        The full held EUR reservation remains charged against the cap, even
        when a caller says usage was lower or zero. UNKNOWN/over-bound freezes
        future reservations; nothing creates a paid-dispatch/refund authority.
        ``period`` is explicit so a late observation targets its original month.
        """
        def deny(reason: str) -> SQLiteMonthlySettlementResult:
            return SQLiteMonthlySettlementResult(False, reason)

        if not policy.enabled:
            return deny("MONTHLY_POLICY_DISABLED")
        if (not isinstance(period, str) or not _MONTH_PATTERN.fullmatch(period)
                or not period.endswith("@" + policy.timezone_name)):
            return deny("MONTHLY_PERIOD_INVALID")
        if not isinstance(observation, MonthlySettlementObservation):
            return deny("MONTHLY_OBSERVATION_INVALID")
        try:
            conn = self._connect()
        except sqlite3.Error:
            return deny("MONTHLY_STORAGE_UNAVAILABLE")
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""
                SELECT policy_sha256, revision, state_sha256, state_json
                FROM monthly_budget_state WHERE period = ?
            """, (period,)).fetchone()
            if row is None:
                return deny("MONTHLY_PERIOD_NOT_BOOTSTRAPPED")
            policy_sha, revision, old_sha, raw_state = row
            if policy_sha != _monthly_policy_sha256(policy):
                return deny("MONTHLY_STORED_POLICY_MISMATCH")
            state = self._loaded_state((revision, old_sha, raw_state))
            if state.period != period or state.policy_version != policy.version:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            previous = conn.execute("""
                SELECT period, observation_id, receipt_sha256, receipt_json
                FROM monthly_reconciliation_receipt WHERE attempt_id = ?
            """, (observation.attempt_id,)).fetchone()
            if previous is not None:
                prior_period, prior_id, prior_sha, prior_raw = previous
                receipt = _loaded_settlement_receipt(prior_raw, prior_sha)
                if (prior_period != receipt.period
                        or prior_id != receipt.observation.observation_id
                        or receipt.observation.attempt_id != observation.attempt_id):
                    raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
                if prior_period != period:
                    return deny("MONTHLY_OBSERVATION_SCOPE_CONFLICT")
                if receipt.observation != observation:
                    return deny("MONTHLY_OBSERVATION_CONFLICT")
                return SQLiteMonthlySettlementResult(
                    False, "MONTHLY_OBSERVATION_ALREADY_RECORDED", receipt,
                )
            other_id = conn.execute("""
                SELECT attempt_id FROM monthly_reconciliation_receipt
                WHERE observation_id = ?
            """, (observation.observation_id,)).fetchone()
            if other_id is not None:
                return deny("MONTHLY_OBSERVATION_ID_CONFLICT")
            reserved = next((item for item in state.reservations
                             if item.attempt_id == observation.attempt_id), None)
            if reserved is None:
                return deny("MONTHLY_RESERVATION_NOT_FOUND")
            if reserved.operation != observation.operation:
                return deny("MONTHLY_ATTEMPT_ID_CONFLICT")
            if observation.status == "UNKNOWN":
                status = "UNKNOWN_HELD"
                provisional_eur = None
            else:
                provisional_eur = (
                    observation.reported_cost_usd * reserved.fx_rate_eur_per_usd
                ).quantize(_EUR_MICRO, rounding=ROUND_CEILING)
                if provisional_eur > _MAX_DECIMAL:
                    return deny("MONTHLY_OBSERVATION_FX_AMOUNT_INVALID")
                status = ("OVER_BOUND_HELD" if (
                    observation.reported_cost_usd > reserved.upper_bound_usd
                    or provisional_eur > reserved.held_eur
                ) else "PROVISIONAL_HELD")
            next_state = replace(
                state, revision=state.revision + 1,
                unknown_liability=(state.unknown_liability
                                   or status in {"UNKNOWN_HELD", "OVER_BOUND_HELD"}),
            )
            receipt = MonthlySettlementReceipt(
                period=period, observation=observation, status=status,
                held_eur=reserved.held_eur, provisional_eur=provisional_eur,
                fx_reference=reserved.fx_reference,
                state_revision=next_state.revision,
                previous_state_sha256=old_sha,
                resulting_state_sha256=next_state.fingerprint(),
            )
            # One SQLite write transaction covers both the versioned state CAS
            # and the immutable observation. Failure rolls both back.
            updated = conn.execute("""
                UPDATE monthly_budget_state
                SET revision = ?, state_sha256 = ?, state_json = ?
                WHERE period = ? AND policy_sha256 = ?
                  AND revision = ? AND state_sha256 = ?
            """, (next_state.revision, next_state.fingerprint(),
                  _encode_monthly_state(next_state), period, policy_sha,
                  state.revision, old_sha))
            if updated.rowcount != 1:
                return deny("MONTHLY_STORAGE_CAS_CONFLICT")
            conn.execute("""
                INSERT INTO monthly_reconciliation_receipt (
                    period, attempt_id, observation_id, receipt_sha256, receipt_json
                ) VALUES (?, ?, ?, ?, ?)
            """, (period, observation.attempt_id, observation.observation_id,
                  _settlement_receipt_sha256(receipt),
                  _settlement_receipt_json(receipt)))
            conn.commit()
            return SQLiteMonthlySettlementResult(
                True, "MONTHLY_OBSERVATION_RECORDED", receipt,
            )
        except (ValueError, InvalidOperation, ArithmeticError):
            return deny("MONTHLY_STORAGE_INTEGRITY_FAILURE")
        except sqlite3.Error:
            return deny("MONTHLY_STORAGE_UNAVAILABLE")
        finally:
            if conn.in_transaction:
                conn.rollback()
            conn.close()

    def reconciliation_report(self, period: str) -> SQLiteMonthlyReconciliationReport:
        """Read one consistent private snapshot; never infer a provider bill."""
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            row = conn.execute("""
                SELECT revision, state_sha256, state_json FROM monthly_budget_state
                WHERE period = ?
            """, (period,)).fetchone()
            if row is None:
                raise ValueError("MONTHLY_PERIOD_NOT_BOOTSTRAPPED")
            state = self._loaded_state(row)
            if state.period != period:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            raw_receipts = conn.execute("""
                SELECT attempt_id, observation_id, receipt_sha256, receipt_json
                FROM monthly_reconciliation_receipt
                WHERE period = ? ORDER BY attempt_id
            """, (period,)).fetchall()
            reservations = {item.attempt_id: item for item in state.reservations}
            known_total = Decimal("0")
            unknown = over_bound = 0
            if state.revision != len(reservations) + len(raw_receipts):
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            for attempt_id, observation_id, fingerprint, raw in raw_receipts:
                receipt = _loaded_settlement_receipt(raw, fingerprint)
                reserved = reservations.get(attempt_id)
                if (receipt.period != period or reserved is None
                        or receipt.observation.attempt_id != attempt_id
                        or receipt.observation.observation_id != observation_id
                        or receipt.observation.operation != reserved.operation
                        or receipt.held_eur != reserved.held_eur
                        or receipt.fx_reference != reserved.fx_reference
                        or receipt.state_revision > state.revision):
                    raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
                if receipt.status == "UNKNOWN_HELD":
                    unknown += 1
                else:
                    expected_eur = (
                        receipt.observation.reported_cost_usd * reserved.fx_rate_eur_per_usd
                    ).quantize(_EUR_MICRO, rounding=ROUND_CEILING)
                    expected_status = ("OVER_BOUND_HELD" if (
                        receipt.observation.reported_cost_usd > reserved.upper_bound_usd
                        or expected_eur > reserved.held_eur
                    ) else "PROVISIONAL_HELD")
                    if (receipt.provisional_eur != expected_eur
                            or receipt.status != expected_status):
                        raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
                    known_total += expected_eur
                    over_bound += receipt.status == "OVER_BOUND_HELD"
            if (unknown or over_bound) and not state.unknown_liability:
                raise ValueError("MONTHLY_STORAGE_INTEGRITY_FAILURE")
            conn.commit()
            return SQLiteMonthlyReconciliationReport(
                period=period, observed_attempts=len(raw_receipts),
                provisional_observed_eur=known_total,
                held_total_eur=state.held_total_eur,
                settled_eur=state.settled_eur,
                unknown_attempts=unknown, over_bound_attempts=over_bound,
                unknown_liability=state.unknown_liability,
            )
        finally:
            if conn.in_transaction:
                conn.rollback()
            conn.close()
