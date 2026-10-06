"""DP-228 claim-specific compiler over existing Coverage Need research assignments.

This module deliberately does not execute discovery and does not synthesize evidence or
queries.  It only compiles already-materialized Coverage Needs through the existing
``research_plan`` assignment compiler, then applies claim-level safety and budget caps.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.claim_contract import NON_FACTUAL_CLAIM_TYPES
from dichiarazioni_pubbliche.coverage_needs import CoverageNeedSpec
from dichiarazioni_pubbliche.domain_vocabulary import ClaimType, InferenceRiskClass
from dichiarazioni_pubbliche.research_plan import (
    LANES,
    RESEARCH_PLAN_VERSION,
    ResearchAssignment,
    compile_research_assignments,
)


CLAIM_RESEARCH_PLAN_VERSION = "claim-research-plan-v1"
DEFAULT_MAX_ASSIGNMENTS = 16
DEFAULT_MAX_UNIQUE_LANES = 8
DEFAULT_MAX_TOTAL_RESULTS = 80
DEFAULT_MAX_TOTAL_COST_USD = Decimal("2.00")

# These claim types assert motive/intent directly. The product constitution forbids
# treating contradiction/research as proof of intent, so automated research planning
# for them remains fail-closed rather than pretending a specialist lane makes them safe.
INTENT_RISK_CLAIM_TYPES = frozenset(
    {ClaimType.GROUP_MOTIVE, ClaimType.MOTIVE_ATTRIBUTION}
)


@dataclass(frozen=True)
class ClaimResearchPlan:
    plan_id: str
    claim_id: str
    claim_type: str
    risk_class: str
    status: str
    assignments: tuple[ResearchAssignment, ...]
    blockers: tuple[str, ...]
    total_results: int
    total_cost_usd: Decimal
    exhausted_need_count: int
    challenger_enabled: bool
    version: str = CLAIM_RESEARCH_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED", "COMPLETE"}:
            raise ValueError("CLAIM_RESEARCH_PLAN_STATUS_INVALID")
        if self.status == "READY" and not self.assignments:
            raise ValueError("CLAIM_RESEARCH_PLAN_READY_WITHOUT_ASSIGNMENTS")
        if self.status == "BLOCKED" and not self.blockers:
            raise ValueError("CLAIM_RESEARCH_PLAN_BLOCKER_REQUIRED")
        if self.status != "READY" and self.assignments:
            raise ValueError("CLAIM_RESEARCH_PLAN_NON_READY_HAS_ASSIGNMENTS")
        if self.total_results < 0 or self.total_cost_usd < 0:
            raise ValueError("CLAIM_RESEARCH_PLAN_BUDGET_INVALID")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _need_mapping(need: CoverageNeedSpec | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(need, CoverageNeedSpec):
        return {
            "id": need.id,
            "collection_id": need.collection_id,
            "atomic_claim_id": need.atomic_claim_id,
            "claim_candidate_id": need.claim_candidate_id,
            "source_intelligence_assessment_id": need.source_intelligence_assessment_id,
            "need_type": need.need_type,
            "requirement_kind": need.requirement_kind,
            "requirement_fingerprint": need.requirement_fingerprint,
            "question": need.question,
            "required_roles": list(need.required_roles),
            "authority_scope": dict(need.authority_scope),
            "temporal_constraints": dict(need.temporal_constraints),
            "independence_requirement": need.independence_requirement,
            "max_attempts": need.max_attempts,
            "attempt_count": 0,
            "metadata": dict(need.metadata),
        }
    return dict(need)


def _plan_id(material: Mapping[str, Any]) -> str:
    return "claim-research-plan:" + hashlib.sha256(
        _stable_json(material).encode("utf-8")
    ).hexdigest()


def _blocked_plan(
    *,
    claim_id: str,
    claim_type: str,
    risk_class: str,
    blockers: Sequence[str],
    exhausted_need_count: int,
    challenger_enabled: bool,
    identity_needs: Sequence[str],
) -> ClaimResearchPlan:
    normalized_blockers = tuple(dict.fromkeys(str(item) for item in blockers if str(item)))
    material = {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "risk_class": risk_class,
        "status": "BLOCKED",
        "blockers": list(normalized_blockers),
        "need_ids": list(identity_needs),
        "challenger_enabled": bool(challenger_enabled),
        "research_plan_version": RESEARCH_PLAN_VERSION,
        "version": CLAIM_RESEARCH_PLAN_VERSION,
    }
    return ClaimResearchPlan(
        plan_id=_plan_id(material),
        claim_id=claim_id,
        claim_type=claim_type,
        risk_class=risk_class,
        status="BLOCKED",
        assignments=(),
        blockers=normalized_blockers,
        total_results=0,
        total_cost_usd=Decimal("0"),
        exhausted_need_count=exhausted_need_count,
        challenger_enabled=bool(challenger_enabled),
    )


def compile_claim_research_plan(
    *,
    claim_id: str,
    claim_type: str | ClaimType,
    coverage_needs: Sequence[CoverageNeedSpec | Mapping[str, Any]],
    lane_adapters: Mapping[str, Sequence[str]],
    risk_class: str | InferenceRiskClass = InferenceRiskClass.STANDARD,
    include_challenger: bool = False,
    max_assignments: int = DEFAULT_MAX_ASSIGNMENTS,
    max_unique_lanes: int = DEFAULT_MAX_UNIQUE_LANES,
    max_total_results: int = DEFAULT_MAX_TOTAL_RESULTS,
    max_total_cost_usd: Decimal | str | float = DEFAULT_MAX_TOTAL_COST_USD,
    per_assignment_max_results: int = 10,
    per_assignment_max_results_per_host: int = 3,
    per_assignment_cost_cap_usd: Decimal | str | float = Decimal("0"),
) -> ClaimResearchPlan:
    """Compile bounded research lanes for one claim from explicit Coverage Needs.

    No evidence/query text is created here: every assignment question comes directly
    from the Coverage Need and every adapter comes from ``lane_adapters``.  Global cap
    violations block the whole executable plan rather than silently dropping work.
    """

    claim = str(claim_id or "").strip()
    if not claim:
        raise ValueError("CLAIM_RESEARCH_PLAN_CLAIM_ID_REQUIRED")
    try:
        kind = ClaimType(claim_type)
    except ValueError:
        return _blocked_plan(
            claim_id=claim,
            claim_type=str(claim_type),
            risk_class=str(risk_class),
            blockers=("CLAIM_TYPE_UNSUPPORTED",),
            exhausted_need_count=0,
            challenger_enabled=include_challenger,
            identity_needs=(),
        )
    try:
        resolved_risk = InferenceRiskClass(risk_class)
    except ValueError:
        resolved_risk = None

    need_rows = tuple(sorted((_need_mapping(item) for item in coverage_needs), key=lambda row: str(row.get("id") or "")))
    need_ids = tuple(str(row.get("id") or "") for row in need_rows)
    if any(not need_id.strip() for need_id in need_ids):
        raise ValueError("CLAIM_RESEARCH_PLAN_NEED_ID_REQUIRED")
    if len(set(need_ids)) != len(need_ids):
        raise ValueError("CLAIM_RESEARCH_PLAN_DUPLICATE_NEED_ID")

    exhausted = sum(
        1
        for row in need_rows
        if max(0, int(row.get("max_attempts") or 0) - int(row.get("attempt_count") or 0)) == 0
    )
    blockers: list[str] = []
    if kind in NON_FACTUAL_CLAIM_TYPES:
        blockers.append("CLAIM_TYPE_NON_FACTUAL")
    if kind in INTENT_RISK_CLAIM_TYPES:
        blockers.append("CLAIM_TYPE_INTENT_RISK")
    if resolved_risk is None:
        blockers.append("RISK_CLASS_UNSUPPORTED")
    elif resolved_risk is not InferenceRiskClass.STANDARD:
        blockers.append("HIGH_RISK_REQUIRES_MANUAL_REVIEW")

    if not 1 <= int(max_assignments) <= 64:
        raise ValueError("CLAIM_RESEARCH_PLAN_ASSIGNMENT_CAP_INVALID")
    if not 1 <= int(max_unique_lanes) <= len(LANES):
        raise ValueError("CLAIM_RESEARCH_PLAN_LANE_CAP_INVALID")
    if not 1 <= int(max_total_results) <= 1000:
        raise ValueError("CLAIM_RESEARCH_PLAN_RESULT_CAP_INVALID")
    try:
        total_cost_limit = Decimal(str(max_total_cost_usd))
    except InvalidOperation as exc:
        raise ValueError("CLAIM_RESEARCH_PLAN_COST_CAP_INVALID") from exc
    if total_cost_limit < 0:
        raise ValueError("CLAIM_RESEARCH_PLAN_COST_CAP_INVALID")

    if blockers:
        return _blocked_plan(
            claim_id=claim,
            claim_type=kind.value,
            risk_class=(resolved_risk.value if resolved_risk is not None else str(risk_class)),
            blockers=blockers,
            exhausted_need_count=exhausted,
            challenger_enabled=include_challenger,
            identity_needs=need_ids,
        )

    assignments: list[ResearchAssignment] = []
    for row in need_rows:
        compiled = compile_research_assignments(
            row,
            lane_adapters=lane_adapters,
            include_challenger=include_challenger,
            max_results=per_assignment_max_results,
            max_results_per_host=per_assignment_max_results_per_host,
            cost_cap_usd=per_assignment_cost_cap_usd,
        )
        assignments.extend(compiled)

    assignments.sort(key=lambda row: (row.coverage_need_id, row.lane, row.assignment_id))
    if not assignments:
        material = {
            "claim_id": claim,
            "claim_type": kind.value,
            "risk_class": resolved_risk.value,
            "status": "COMPLETE",
            "need_ids": list(need_ids),
            "challenger_enabled": bool(include_challenger),
            "version": CLAIM_RESEARCH_PLAN_VERSION,
        }
        return ClaimResearchPlan(
            plan_id=_plan_id(material),
            claim_id=claim,
            claim_type=kind.value,
            risk_class=resolved_risk.value,
            status="COMPLETE",
            assignments=(),
            blockers=(),
            total_results=0,
            total_cost_usd=Decimal("0"),
            exhausted_need_count=exhausted,
            challenger_enabled=bool(include_challenger),
        )

    unique_lanes = {row.lane for row in assignments}
    total_results = sum(row.max_results for row in assignments)
    total_cost = sum((row.cost_cap_usd for row in assignments), Decimal("0"))
    if len(assignments) > int(max_assignments):
        blockers.append("ASSIGNMENT_CAP_EXCEEDED")
    if len(unique_lanes) > int(max_unique_lanes):
        blockers.append("LANE_CAP_EXCEEDED")
    if total_results > int(max_total_results):
        blockers.append("RESULT_BUDGET_EXCEEDED")
    if total_cost > total_cost_limit:
        blockers.append("COST_BUDGET_EXCEEDED")
    if any(row.status != "READY" for row in assignments):
        blockers.append("ASSIGNMENT_BLOCKED")

    if blockers:
        return _blocked_plan(
            claim_id=claim,
            claim_type=kind.value,
            risk_class=resolved_risk.value,
            blockers=blockers,
            exhausted_need_count=exhausted,
            challenger_enabled=include_challenger,
            identity_needs=need_ids,
        )

    identity = {
        "claim_id": claim,
        "claim_type": kind.value,
        "risk_class": resolved_risk.value,
        "assignment_ids": [row.assignment_id for row in assignments],
        "challenger_enabled": bool(include_challenger),
        "max_assignments": int(max_assignments),
        "max_unique_lanes": int(max_unique_lanes),
        "max_total_results": int(max_total_results),
        "max_total_cost_usd": str(total_cost_limit),
        "version": CLAIM_RESEARCH_PLAN_VERSION,
    }
    return ClaimResearchPlan(
        plan_id=_plan_id(identity),
        claim_id=claim,
        claim_type=kind.value,
        risk_class=resolved_risk.value,
        status="READY",
        assignments=tuple(assignments),
        blockers=(),
        total_results=total_results,
        total_cost_usd=total_cost,
        exhausted_need_count=exhausted,
        challenger_enabled=bool(include_challenger),
    )


__all__ = [
    "CLAIM_RESEARCH_PLAN_VERSION",
    "DEFAULT_MAX_ASSIGNMENTS",
    "DEFAULT_MAX_TOTAL_COST_USD",
    "DEFAULT_MAX_TOTAL_RESULTS",
    "DEFAULT_MAX_UNIQUE_LANES",
    "INTENT_RISK_CLAIM_TYPES",
    "ClaimResearchPlan",
    "compile_claim_research_plan",
]
