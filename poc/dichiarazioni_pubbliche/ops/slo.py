"""Operational SLOs for Dichiarazioni Pubbliche (DP-504).

Pure policy: an SLO is a (metric, objective, window) triple plus a pure
predicate that maps observed measurements to a status. There is no clock, no
database, and no network here. ``health_digest`` supplies measurements; this
module decides whether they breach.

The design constraint that shaped this module: an SLO that cannot be computed
from data the digest *already* collects would be an SLO nobody checks. Every
objective below is therefore expressed over a field that
``build_health_digest`` already emits, and ``required_measurements`` names the
exact digest key that must be present for the objective to be computable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


# Statuses, worst last. ``UNKNOWN`` is a first-class status, not an error: it
# means the measurement was unavailable, and the operator action is "check the
# collector", not "ignore the page".
SLO_STATUSES = ("OK", "AT_RISK", "BREACH", "UNKNOWN")

# How an SLO is computed, so the taxonomy can name a real operator action.
SLO_KINDS = (
    "AVAILABILITY",  # 1 - breach_seconds / window_seconds
    "FRESHNESS",     # age of the newest public projection artifact
    "LATENCY",       # age of the oldest unfinished job
    "DRAIN",         # 1 - oldest_queued / drain_objective_seconds
    "EXHAUSTION",    # fraction of a hard budget ceiling consumed
)


@dataclass(frozen=True)
class Slo:
    id: str
    title: str
    kind: str
    objective: str
    target: float
    window_seconds: int
    comparison: str  # "at_most" | "at_least"
    required_measurements: tuple[str, ...]
    action: str
    rationale: str

    def evaluate(self, measured: float | None) -> str:
        """Return one of SLO_STATUSES for a measured value.

        ``None`` (measurement unavailable) is UNKNOWN, never OK. This is the
        fail-closed property: an unreadable metric must not be reported as
        healthy.
        """
        if measured is None:
            return "UNKNOWN"
        try:
            value = float(measured)
        except (TypeError, ValueError):
            return "UNKNOWN"
        if self.comparison == "at_most":
            if value > self.target:
                return "BREACH"
            if value > self.target * 0.75:
                return "AT_RISK"
            return "OK"
        if self.comparison == "at_least":
            if value < self.target:
                return "BREACH"
            if value < min(1.0, self.target + (1.0 - self.target) * 0.25):
                return "AT_RISK"
            return "OK"
        return "UNKNOWN"


# The SLO set. Targets are deliberately conservative for a single-host,
# low-volume, Italy-first system: an SLO that is easy to breach trains the
# operator to ignore breaches, which is worse than having no SLO at all.
SLOS: tuple[Slo, ...] = (
    Slo(
        id="SLO-PUBLIC-AVAILABILITY",
        title="Public projection read path is available and serving",
        kind="AVAILABILITY",
        objective="99.5% of a rolling 24h",
        target=0.995,
        window_seconds=86_400,
        comparison="at_least",
        required_measurements=("projection_health",),
        action="Check dichiarazioni-pubbliche-web.service and the projection bundle directory.",
        rationale=(
            "The public product must remain usable even when every LLM provider "
            "is offline; availability is therefore a static-bundle property, not "
            "a live-compute property."
        ),
    ),
    Slo(
        id="SLO-PUBLIC-FRESHNESS",
        title="Public projection reflects accepted work within one day",
        kind="FRESHNESS",
        objective="<= 24h since the last successful projection build",
        target=86_400.0,
        window_seconds=86_400,
        comparison="at_most",
        required_measurements=("projection_generated_at_age_seconds",),
        action=(
            "Check the projection build step and BLOCKED counts. Do NOT lower a "
            "gate to make freshness look better."
        ),
        rationale=(
            "Freshness is reported, never forced: a blocked provider must show "
            "as stale public data, not as a silently missing dossier."
        ),
    ),
    Slo(
        id="SLO-QUEUE-OLDEST-QUEUED",
        title="No job sits queued for more than 6 hours",
        kind="LATENCY",
        objective="<= 6h for the oldest QUEUED job",
        target=21_600.0,
        window_seconds=21_600,
        comparison="at_most",
        required_measurements=("queue_oldest_queued_seconds",),
        action=(
            "Check worker timer state, then check whether jobs are DEFERRED by "
            "budget or BLOCKED by a provider."
        ),
        rationale=(
            "A queue that never drains is the primary unattended-failure mode; "
            "six hours is chosen so an operator sees it within one business day."
        ),
    ),
    Slo(
        id="SLO-QUEUE-DRAIN",
        title="Worker drains the ready queue within one timer interval",
        kind="DRAIN",
        objective="1 - oldest_queued/120s >= 0.5",
        target=0.5,
        window_seconds=120,
        comparison="at_least",
        required_measurements=("queue_drain_ratio",),
        action="Check worker service exit status and WorkerRunSummary counters.",
        rationale="The worker timer runs every ~2 minutes; a slower drain means "
        "work is accumulating faster than one pass can handle it.",
    ),
    Slo(
        id="SLO-COST-GLOBAL-DAILY",
        title="Global daily provider spend stays under 60% of the hard cap",
        kind="EXHAUSTION",
        objective="<= 0.60 * max_cost_usd_per_day",
        target=0.6,
        window_seconds=86_400,
        comparison="at_most",
        required_measurements=("estimated_cost_usd_today",),
        action=(
            "If BREACH: read the budget circuit breaker. Work is DEFERRED, not "
            "dropped; raise the cap only as a deliberate, documented decision."
        ),
        rationale=(
            "Spending at 100% of the cap means the pipeline is one job away from "
            "silently deferring everything else; the operational budget is set "
            "below the hard ceiling so the circuit breaker is never a surprise."
        ),
    ),
    Slo(
        id="SLO-COST-SOURCE-DAILY",
        title="Per-source daily spend stays under 60% of the hard cap",
        kind="EXHAUSTION",
        objective="<= 0.60 * max_cost_usd_per_source_day",
        target=0.6,
        window_seconds=86_400,
        comparison="at_most",
        required_measurements=("provider_receipts_today",),
        action="Identify the source from the receipts table; pause that source.",
        rationale="A single misbehaving source must not be able to consume the "
        "entire global allowance.",
    ),
)


def get_slo(slo_id: str) -> Slo:
    for slo in SLOS:
        if slo.id == slo_id:
            return slo
    raise KeyError(slo_id)


def evaluate(measured: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Evaluate every SLO against a flat measurement mapping.

    Keys are the SLO ``required_measurements`` names. A missing key yields
    UNKNOWN for that SLO and does not affect the others.
    """
    results = []
    for slo in SLOS:
        values = [measured.get(key) for key in slo.required_measurements]
        usable = [v for v in values if v is not None]
        value = usable[0] if len(usable) == len(values) and usable else None
        results.append(
            {
                "id": slo.id,
                "title": slo.title,
                "kind": slo.kind,
                "objective": slo.objective,
                "status": slo.evaluate(value),
                "measured": value,
                "target": slo.target,
                "window_seconds": slo.window_seconds,
                "action": slo.action,
            }
        )
    return tuple(results)


def worst_status(results: Sequence[Mapping[str, Any]]) -> str:
    """Roll individual statuses up into one.

    UNKNOWN is ranked above AT_RISK but below BREACH: a metric we cannot read
    is a monitoring problem we must act on, but it is not a product outage.
    """
    order = {"OK": 0, "AT_RISK": 1, "UNKNOWN": 2, "BREACH": 3}
    worst = "OK"
    for row in results:
        status = str(row.get("status"))
        if order.get(status, 99) > order[worst]:
            worst = status
    return worst


def pageable(results: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """SLO ids that should raise an operator page, in register order.

    Only BREACH pages. AT_RISK and UNKNOWN are visible in the digest and in the
    daily review, but paging on them is exactly how a digest becomes noise that
    an operator learns to dismiss.
    """
    return tuple(
        str(row["id"]) for row in results if str(row.get("status")) == "BREACH"
    )


def validate_slos(slos: tuple[Slo, ...] = SLOS) -> tuple[str, ...]:
    """Structural self-check; empty tuple means the SLO set is coherent."""
    defects: list[str] = []
    seen: set[str] = set()
    for slo in slos:
        if slo.id in seen:
            defects.append(f"duplicate_id:{slo.id}")
        seen.add(slo.id)
        if slo.kind not in SLO_KINDS:
            defects.append(f"{slo.id}:unknown_kind:{slo.kind}")
        if slo.comparison not in {"at_most", "at_least"}:
            defects.append(f"{slo.id}:unknown_comparison:{slo.comparison}")
        if slo.window_seconds <= 0:
            defects.append(f"{slo.id}:non_positive_window")
        if slo.comparison == "at_most" and slo.target <= 0:
            defects.append(f"{slo.id}:non_positive_target")
        if slo.comparison == "at_least" and not 0 < slo.target <= 1:
            defects.append(f"{slo.id}:ratio_target_out_of_range")
        if not slo.action:
            defects.append(f"{slo.id}:no_action")
        if not slo.rationale:
            defects.append(f"{slo.id}:no_rationale")
        if not slo.required_measurements:
            defects.append(f"{slo.id}:no_measurements")
    return tuple(defects)
