from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.coverage_needs import CoverageNeedSpec


RESEARCH_PLAN_VERSION = "research-plan-v1"
LANES = frozenset(
    {
        "PRIMARY_SOURCE",
        "OFFICIAL_STRUCTURED",
        "INDEPENDENT_REPORTING",
        "EXISTING_FACT_CHECK",
        "ACADEMIC_EXPERT",
        "ORIGINAL_MEDIA",
        "ARCHIVE_HISTORY",
        "CHALLENGER",
    }
)


@dataclass(frozen=True)
class ResearchAssignment:
    assignment_id: str
    coverage_need_id: str
    lane: str
    question: str
    adapter_ids: tuple[str, ...]
    max_queries: int
    max_results: int
    max_results_per_host: int
    cost_cap_usd: Decimal
    temporal_constraints: dict[str, Any]
    authority_scope: dict[str, Any]
    stop_conditions: tuple[str, ...]
    status: str = "READY"
    blockers: tuple[str, ...] = ()
    plan_version: str = RESEARCH_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.lane not in LANES:
            raise ValueError("RESEARCH_LANE_INVALID")
        if self.status not in {"READY", "BLOCKED"}:
            raise ValueError("RESEARCH_ASSIGNMENT_STATUS_INVALID")
        if self.max_queries < 0 or self.max_results < 0 or self.max_results_per_host < 0:
            raise ValueError("RESEARCH_ASSIGNMENT_LIMIT_INVALID")
        if self.cost_cap_usd < 0:
            raise ValueError("RESEARCH_ASSIGNMENT_COST_INVALID")
        if self.status == "READY" and not self.adapter_ids:
            raise ValueError("RESEARCH_ASSIGNMENT_READY_WITHOUT_ADAPTER")
        if self.status == "BLOCKED" and not self.blockers:
            raise ValueError("RESEARCH_ASSIGNMENT_BLOCK_REASON_REQUIRED")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _assignment_id(payload: Mapping[str, Any]) -> str:
    return "research-assignment:" + hashlib.sha256(
        _stable_json(payload).encode("utf-8")
    ).hexdigest()


def _need_mapping(need: CoverageNeedSpec | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(need, CoverageNeedSpec):
        return asdict(need)
    return dict(need)


def lanes_for_need(need: CoverageNeedSpec | Mapping[str, Any]) -> tuple[str, ...]:
    row = _need_mapping(need)
    need_type = str(row.get("need_type") or "OTHER")
    roles = {str(value) for value in row.get("required_roles") or ()}

    lanes: list[str] = []
    if need_type in {"PRIMARY_SOURCE", "ATTRIBUTION_GAP"}:
        lanes.append("PRIMARY_SOURCE")
    if need_type == "ORIGINAL_MEDIA":
        lanes.append("ORIGINAL_MEDIA")
    if need_type == "OFFICIAL_RECORD" or roles & {
        "OFFICIAL_STATISTICS",
        "AUTHENTIC_LEGAL_TEXT",
        "OFFICIAL_PROCEDURAL_RECORD",
    }:
        lanes.append("OFFICIAL_STRUCTURED")
    if need_type == "INDEPENDENT_SOURCE":
        lanes.append("INDEPENDENT_REPORTING")
    if need_type == "EARLIER_VERSION":
        lanes.append("ARCHIVE_HISTORY")
    if need_type == "TEMPORAL_GAP":
        if roles & {
            "OFFICIAL_STATISTICS",
            "AUTHENTIC_LEGAL_TEXT",
            "OFFICIAL_PROCEDURAL_RECORD",
            "PRIMARY_RECORD",
        }:
            lanes.append("OFFICIAL_STRUCTURED")
        else:
            lanes.append("ARCHIVE_HISTORY")
    if roles & {"EXPERT_SYNTHESIS"}:
        lanes.append("ACADEMIC_EXPERT")

    # Existing checks are useful as a cheap navigation/context lane when a factual
    # requirement remains open. They never replace the primary/official lane.
    if need_type not in {"OTHER"}:
        lanes.append("EXISTING_FACT_CHECK")

    return tuple(dict.fromkeys(lanes))


def compile_research_assignments(
    need: CoverageNeedSpec | Mapping[str, Any],
    *,
    lane_adapters: Mapping[str, Sequence[str]],
    include_challenger: bool = False,
    max_results: int = 10,
    max_results_per_host: int = 3,
    cost_cap_usd: Decimal | str | float = Decimal("0"),
) -> tuple[ResearchAssignment, ...]:
    row = _need_mapping(need)
    need_id = str(row.get("id") or "").strip()
    question = str(row.get("question") or "").strip()
    if not need_id:
        raise ValueError("RESEARCH_PLAN_NEED_ID_REQUIRED")
    if not question:
        raise ValueError("RESEARCH_PLAN_QUESTION_REQUIRED")
    remaining_attempts = max(
        0,
        int(row.get("max_attempts") or 0) - int(row.get("attempt_count") or 0),
    )
    if remaining_attempts == 0:
        return ()
    if not 1 <= int(max_results) <= 100:
        raise ValueError("RESEARCH_PLAN_MAX_RESULTS_INVALID")
    if not 1 <= int(max_results_per_host) <= int(max_results):
        raise ValueError("RESEARCH_PLAN_HOST_LIMIT_INVALID")
    cost = Decimal(str(cost_cap_usd))
    if cost < 0:
        raise ValueError("RESEARCH_PLAN_COST_INVALID")

    lanes = list(lanes_for_need(row))
    if include_challenger:
        lanes.append("CHALLENGER")
    lanes = list(dict.fromkeys(lanes))
    if not lanes:
        return ()

    assignments: list[ResearchAssignment] = []
    for lane in lanes:
        adapters = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in lane_adapters.get(lane, ())
                if str(value).strip()
            )
        )
        status = "READY" if adapters else "BLOCKED"
        blockers = () if adapters else ("NO_CONFIGURED_ADAPTER_FOR_LANE",)
        payload = {
            "coverage_need_id": need_id,
            "lane": lane,
            "question": question,
            "adapter_ids": adapters,
            "max_queries": remaining_attempts,
            "max_results": int(max_results),
            "max_results_per_host": int(max_results_per_host),
            "cost_cap_usd": str(cost),
            "temporal_constraints": dict(row.get("temporal_constraints") or {}),
            "authority_scope": dict(row.get("authority_scope") or {}),
            "plan_version": RESEARCH_PLAN_VERSION,
        }
        assignments.append(
            ResearchAssignment(
                assignment_id=_assignment_id(payload),
                coverage_need_id=need_id,
                lane=lane,
                question=question,
                adapter_ids=adapters,
                max_queries=remaining_attempts,
                max_results=int(max_results),
                max_results_per_host=int(max_results_per_host),
                cost_cap_usd=cost,
                temporal_constraints=payload["temporal_constraints"],
                authority_scope=payload["authority_scope"],
                stop_conditions=(
                    "REQUIREMENT_SATISFIED",
                    "MAX_ATTEMPTS_REACHED",
                    "COST_CAP_REACHED",
                    "RESULT_LIMIT_REACHED",
                    "PROVIDER_BLOCKED",
                ),
                status=status,
                blockers=blockers,
            )
        )
    return tuple(assignments)


__all__ = [
    "LANES",
    "RESEARCH_PLAN_VERSION",
    "ResearchAssignment",
    "compile_research_assignments",
    "lanes_for_need",
]
