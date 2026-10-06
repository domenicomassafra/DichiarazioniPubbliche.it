"""DP-229 bounded bridge from DP-228 challenger assignments to research requests.

The request contains only planner-provided questions and permissions. It never contains
counterevidence, a truth vote, a verification assessment, or a Finding decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from dichiarazioni_pubbliche.claim_research_plan import ClaimResearchPlan


CHALLENGER_RESEARCH_VERSION = "challenger-research-v1"
DEFAULT_MAX_CHALLENGER_ASSIGNMENTS = 8
DEFAULT_MAX_CHALLENGER_RESULTS = 40
DEFAULT_MAX_CHALLENGER_COST_USD = Decimal("1.00")


@dataclass(frozen=True)
class ChallengerResearchRequest:
    request_id: str
    claim_id: str
    status: str
    assignment_ids: tuple[str, ...]
    questions: tuple[str, ...]
    adapter_ids: tuple[str, ...]
    max_queries: int
    max_results: int
    max_results_per_host: int
    cost_cap_usd: Decimal
    stop_conditions: tuple[str, ...]
    blockers: tuple[str, ...]
    version: str = CHALLENGER_RESEARCH_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED"}:
            raise ValueError("CHALLENGER_RESEARCH_STATUS_INVALID")
        if self.status == "READY" and not self.assignment_ids:
            raise ValueError("CHALLENGER_RESEARCH_READY_WITHOUT_ASSIGNMENT")
        if self.status == "BLOCKED" and not self.blockers:
            raise ValueError("CHALLENGER_RESEARCH_BLOCKER_REQUIRED")
        if self.max_queries < 0 or self.max_results < 0 or self.max_results_per_host < 0:
            raise ValueError("CHALLENGER_RESEARCH_LIMIT_INVALID")
        if self.cost_cap_usd < 0:
            raise ValueError("CHALLENGER_RESEARCH_COST_INVALID")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _request_id(material: Mapping[str, Any]) -> str:
    return "challenger-research:" + hashlib.sha256(
        _stable_json(material).encode("utf-8")
    ).hexdigest()


def compile_challenger_research_request(
    plan: ClaimResearchPlan,
    *,
    max_assignments: int = DEFAULT_MAX_CHALLENGER_ASSIGNMENTS,
    max_total_results: int = DEFAULT_MAX_CHALLENGER_RESULTS,
    max_total_cost_usd: Decimal | str | float = DEFAULT_MAX_CHALLENGER_COST_USD,
) -> ChallengerResearchRequest:
    """Narrow a READY claim plan to its explicit CHALLENGER assignments only.

    The function never manufactures a challenger lane. If the DP-228 plan did not opt
    into one, the request is BLOCKED. Questions, adapters and stop conditions are copied
    from the assignments and only narrowed/aggregated.
    """

    claim_id = str(plan.claim_id or "").strip()
    if not claim_id:
        raise ValueError("CHALLENGER_RESEARCH_CLAIM_ID_REQUIRED")
    if not 1 <= int(max_assignments) <= 32:
        raise ValueError("CHALLENGER_RESEARCH_ASSIGNMENT_CAP_INVALID")
    if not 1 <= int(max_total_results) <= 500:
        raise ValueError("CHALLENGER_RESEARCH_RESULT_CAP_INVALID")
    cost_limit = Decimal(str(max_total_cost_usd))
    if cost_limit < 0:
        raise ValueError("CHALLENGER_RESEARCH_COST_CAP_INVALID")

    challenger_rows = tuple(row for row in plan.assignments if row.lane == "CHALLENGER")
    blockers: list[str] = []
    if plan.status != "READY":
        blockers.append("CLAIM_RESEARCH_PLAN_NOT_READY")
    if not plan.challenger_enabled:
        blockers.append("CHALLENGER_NOT_ENABLED")
    if not challenger_rows:
        blockers.append("CHALLENGER_ASSIGNMENT_MISSING")
    if any(row.status != "READY" for row in challenger_rows):
        blockers.append("CHALLENGER_ASSIGNMENT_BLOCKED")

    total_results = sum(row.max_results for row in challenger_rows)
    total_cost = sum((row.cost_cap_usd for row in challenger_rows), Decimal("0"))
    if len(challenger_rows) > int(max_assignments):
        blockers.append("CHALLENGER_ASSIGNMENT_CAP_EXCEEDED")
    if total_results > int(max_total_results):
        blockers.append("CHALLENGER_RESULT_BUDGET_EXCEEDED")
    if total_cost > cost_limit:
        blockers.append("CHALLENGER_COST_BUDGET_EXCEEDED")

    assignment_ids = tuple(row.assignment_id for row in challenger_rows)
    questions = tuple(row.question for row in challenger_rows)
    adapter_ids = tuple(
        dict.fromkeys(adapter for row in challenger_rows for adapter in row.adapter_ids)
    )
    max_queries = sum(row.max_queries for row in challenger_rows)
    max_per_host = min(
        (row.max_results_per_host for row in challenger_rows),
        default=0,
    )
    stop_conditions = tuple(
        dict.fromkeys(condition for row in challenger_rows for condition in row.stop_conditions)
    )
    normalized_blockers = tuple(dict.fromkeys(blockers))
    status = "BLOCKED" if normalized_blockers else "READY"
    material = {
        "claim_id": claim_id,
        "claim_research_plan_id": plan.plan_id,
        "assignment_ids": list(assignment_ids),
        "questions": list(questions),
        "adapter_ids": list(adapter_ids),
        "max_queries": max_queries,
        "max_results": total_results,
        "max_results_per_host": max_per_host,
        "cost_cap_usd": str(total_cost),
        "stop_conditions": list(stop_conditions),
        "status": status,
        "blockers": list(normalized_blockers),
        "version": CHALLENGER_RESEARCH_VERSION,
    }
    return ChallengerResearchRequest(
        request_id=_request_id(material),
        claim_id=claim_id,
        status=status,
        assignment_ids=assignment_ids,
        questions=questions,
        adapter_ids=adapter_ids,
        max_queries=max_queries,
        max_results=total_results,
        max_results_per_host=max_per_host,
        cost_cap_usd=total_cost,
        stop_conditions=stop_conditions,
        blockers=normalized_blockers,
    )


__all__ = [
    "CHALLENGER_RESEARCH_VERSION",
    "DEFAULT_MAX_CHALLENGER_ASSIGNMENTS",
    "DEFAULT_MAX_CHALLENGER_COST_USD",
    "DEFAULT_MAX_CHALLENGER_RESULTS",
    "ChallengerResearchRequest",
    "compile_challenger_research_request",
]
