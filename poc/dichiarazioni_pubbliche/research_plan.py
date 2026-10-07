from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.coverage_needs import CoverageNeedSpec
from dichiarazioni_pubbliche.research_discovery import (
    MAX_COST_USD,
    MAX_QUERY_RESULTS,
    MAX_TOTAL_RESULTS,
    DiscoveryManifest,
    load_discovery_manifest,
)


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


def discovery_manifest_from_assignments(
    assignments: Sequence[ResearchAssignment],
    *,
    collection_id: str,
    lane_source_families: Mapping[str, Sequence[str]],
    query_suggestions: Mapping[str, Mapping[str, Any]] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    seeds: Sequence[Mapping[str, str]] = (),
) -> DiscoveryManifest:
    """Compile bounded donor-style assignments into the existing DP-209 manifest.

    This is intentionally a one-way narrowing adapter: it may not add adapters, increase
    per-query result limits, invent source families, or execute BLOCKED assignments. Optional
    model/query suggestions may replace query text or narrow adapters/source families, but can
    never widen those permissions or alter host/result/cost caps.
    Coverage-need retries remain outside the manifest and continue to be owned by the
    existing Coverage Need state machine.
    """

    rows = tuple(assignments)
    if not rows:
        raise ValueError("RESEARCH_PLAN_ASSIGNMENTS_REQUIRED")
    if any(row.status != "READY" for row in rows):
        raise ValueError("RESEARCH_PLAN_BLOCKED_ASSIGNMENT_REFUSED")
    if len({row.coverage_need_id for row in rows}) > 64:
        raise ValueError("RESEARCH_PLAN_TOO_MANY_COVERAGE_NEEDS")
    collection = str(collection_id or "").strip()
    if not collection:
        raise ValueError("RESEARCH_PLAN_COLLECTION_REQUIRED")

    queries: list[dict[str, Any]] = []
    manifest_families: list[str] = []
    suggestion_identity: list[dict[str, Any]] = []
    total_results = 0
    total_cost = Decimal("0")
    per_host_caps: list[int] = []
    suggestions = dict(query_suggestions or {})
    consumed_suggestions: set[str] = set()

    for ordinal, row in enumerate(rows):
        families = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in lane_source_families.get(row.lane, ())
                if str(value).strip()
            )
        )
        if not families:
            raise ValueError(f"RESEARCH_PLAN_SOURCE_FAMILY_REQUIRED:{row.lane}")
        query_text = row.question
        adapter_ids = row.adapter_ids
        selected_families = families
        suggestion = suggestions.get(row.assignment_id)
        if suggestion is not None:
            consumed_suggestions.add(row.assignment_id)
            if not isinstance(suggestion, Mapping):
                raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_INVALID")
            allowed_fields = {"query", "adapter_ids", "source_families"}
            if set(suggestion) - allowed_fields:
                raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_FIELDS_INVALID")
            query_text = str(suggestion.get("query") or "").strip()
            if not query_text or len(query_text.encode("utf-8")) > 2048:
                raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_TEXT_INVALID")
            if "adapter_ids" in suggestion:
                requested_adapters = tuple(
                    dict.fromkeys(
                        str(value).strip()
                        for value in suggestion.get("adapter_ids") or ()
                        if str(value).strip()
                    )
                )
                if not requested_adapters or not set(requested_adapters).issubset(row.adapter_ids):
                    raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_PERMISSION_EXPANSION")
                adapter_ids = requested_adapters
            if "source_families" in suggestion:
                requested_families = tuple(
                    dict.fromkeys(
                        str(value).strip()
                        for value in suggestion.get("source_families") or ()
                        if str(value).strip()
                    )
                )
                if not requested_families or not set(requested_families).issubset(families):
                    raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_PERMISSION_EXPANSION")
                selected_families = requested_families
            suggestion_identity.append(
                {
                    "assignment_id": row.assignment_id,
                    "query": query_text,
                    "adapter_ids": list(adapter_ids),
                    "source_families": list(selected_families),
                }
            )
        if row.max_results > MAX_QUERY_RESULTS:
            raise ValueError("RESEARCH_PLAN_QUERY_RESULT_CAP_EXCEEDED")
        total_results += row.max_results
        total_cost += row.cost_cap_usd
        per_host_caps.append(row.max_results_per_host)
        manifest_families.extend(selected_families)
        queries.append(
            {
                "id": row.assignment_id,
                "query": query_text,
                "source_families": list(selected_families),
                "adapter_ids": list(adapter_ids),
                "max_results": row.max_results,
                "metadata": {
                    "research_assignment_id": row.assignment_id,
                    "coverage_need_id": row.coverage_need_id,
                    "lane": row.lane,
                    "plan_version": row.plan_version,
                    "remaining_attempts": row.max_queries,
                    "authority_scope": dict(row.authority_scope),
                    "temporal_constraints": dict(row.temporal_constraints),
                    "stop_conditions": list(row.stop_conditions),
                    "ordinal": ordinal,
                    "query_source": "MODEL_SUGGESTION" if suggestion is not None else "COVERAGE_NEED",
                },
            }
        )

    unknown_suggestions = set(suggestions) - consumed_suggestions
    if unknown_suggestions:
        raise ValueError("RESEARCH_PLAN_QUERY_SUGGESTION_ASSIGNMENT_UNKNOWN")

    if total_results > MAX_TOTAL_RESULTS:
        raise ValueError("RESEARCH_PLAN_MANIFEST_RESULT_CAP_EXCEEDED")
    if total_cost > MAX_COST_USD:
        raise ValueError("RESEARCH_PLAN_MANIFEST_COST_CAP_EXCEEDED")
    max_per_host = min(per_host_caps)
    max_per_host = min(max_per_host, total_results)
    coverage_need_ids = tuple(dict.fromkeys(row.coverage_need_id for row in rows))
    identity_material = {
        "collection_id": collection,
        "assignment_ids": [row.assignment_id for row in rows],
        "coverage_need_ids": list(coverage_need_ids),
        "date_from": date_from,
        "date_to": date_to,
        "version": RESEARCH_PLAN_VERSION,
    }
    if suggestion_identity:
        identity_material["query_suggestions"] = suggestion_identity
    manifest_id = "research-plan-manifest:" + hashlib.sha256(
        _stable_json(identity_material).encode("utf-8")
    ).hexdigest()
    raw = {
        "schema_version": 1,
        "id": manifest_id,
        "collection_id": collection,
        "date_window": {"from": date_from, "to": date_to},
        "limits": {
            "max_results": total_results,
            "max_results_per_host": max_per_host,
            "cost_cap_usd": str(total_cost),
        },
        "seeds": [dict(seed) for seed in seeds],
        "source_families": list(dict.fromkeys(manifest_families)),
        "coverage_need_ids": list(coverage_need_ids),
        "queries": queries,
        "metadata": {
            "compiled_from": RESEARCH_PLAN_VERSION,
            "assignment_count": len(rows),
        },
    }
    return load_discovery_manifest(raw)


__all__ = [
    "LANES",
    "RESEARCH_PLAN_VERSION",
    "ResearchAssignment",
    "compile_research_assignments",
    "discovery_manifest_from_assignments",
    "lanes_for_need",
]
