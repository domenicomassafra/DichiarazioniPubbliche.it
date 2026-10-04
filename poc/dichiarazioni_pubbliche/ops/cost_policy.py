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

from dataclasses import dataclass
from typing import Any, Mapping


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
