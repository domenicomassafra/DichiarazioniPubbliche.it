"""DP-319 bounded private investigation-attempt lifecycle.

Consume an existing reviewed research-plan assignment, never make up a URL or
query and never execute one. External source, rights, cost and actor authority
must be checked again by the future durable worker before every request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from dichiarazioni_pubbliche.research_plan import ResearchAssignment


VERSION = "investigation-attempt-v1"
QUESTIONS = frozenset({
    "ORIGINAL_SOURCE", "SPEAKER", "FULL_CONTEXT", "CHRONOLOGY",
    "PRIMARY_EVIDENCE", "SOURCE_RIGHTS", "SOURCE_VERSION", "JURISDICTION",
})
OBSERVATIONS = frozenset({
    "REVIEWED_SOURCE_CANDIDATE", "NO_MATCH", "OUTAGE", "RIGHTS_BLOCKED",
    "COST_BLOCKED", "SOURCE_INCONCLUSIVE", "CAPABILITY_BLOCKED",
})


def _id(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or "\x00" in value:
        raise ValueError("INVESTIGATION_ID_INVALID")
    return value


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


@dataclass(frozen=True)
class InvestigationSpec:
    need_id: str
    material_fingerprint: str
    question_kind: str
    question: str
    source_family: str
    max_attempts: int
    cost_cap_usd: Decimal
    rights_status: str = "UNKNOWN"
    version: str = VERSION

    def __post_init__(self) -> None:
        for value in (self.need_id, self.material_fingerprint, self.question, self.source_family):
            _id(value)
        if self.version != VERSION or self.question_kind not in QUESTIONS:
            raise ValueError("INVESTIGATION_KIND_INVALID")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 10:
            raise ValueError("INVESTIGATION_ATTEMPTS_INVALID")
        if self.rights_status not in {"CLEARED", "UNKNOWN", "EXPIRED", "REVOKED", "DENIED"}:
            raise ValueError("INVESTIGATION_RIGHTS_INVALID")
        if not isinstance(self.cost_cap_usd, Decimal) or not self.cost_cap_usd.is_finite() or self.cost_cap_usd < 0:
            raise ValueError("INVESTIGATION_COST_INVALID")


@dataclass(frozen=True)
class InvestigationObservation:
    attempt_id: str
    material_fingerprint: str
    assignment_id: str
    lane: str
    result: str
    lineage_id: str | None
    source_version: str | None
    source_sha256: str | None
    review_event_id: str | None
    spent_usd: Decimal

    def __post_init__(self) -> None:
        for value in (self.attempt_id, self.material_fingerprint, self.assignment_id, self.lane):
            _id(value)
        if self.result not in OBSERVATIONS:
            raise ValueError("INVESTIGATION_RESULT_INVALID")
        if not isinstance(self.spent_usd, Decimal) or not self.spent_usd.is_finite() or self.spent_usd < 0:
            raise ValueError("INVESTIGATION_COST_INVALID")
        if self.result == "REVIEWED_SOURCE_CANDIDATE":
            for value in (self.lineage_id, self.source_version, self.source_sha256, self.review_event_id):
                _id(value)
            if len(self.source_sha256 or "") != 64 or any(ch not in "0123456789abcdef" for ch in self.source_sha256 or ""):
                raise ValueError("INVESTIGATION_SOURCE_HASH_INVALID")
        elif self.review_event_id is not None:
            raise ValueError("INVESTIGATION_UNREVIEWED_RECEIPT")


@dataclass(frozen=True)
class InvestigationDecision:
    status: str
    reason_code: str
    plan_fingerprint: str
    proposed_attempt_id: str | None
    assignment_id: str | None
    prior_attempt_count: int
    remaining_attempts: int
    spent_usd: Decimal
    independent_reviewed_lineages: int
    publication_authority: bool = False
    coverage: tuple[InvestigationLaneCoverage, ...] = ()


@dataclass(frozen=True)
class InvestigationLaneCoverage:
    """Read-only coverage derived from the exact plan and terminal receipts."""

    lane: str
    status: str
    reason_code: str
    assignment_ids: tuple[str, ...]
    completed_attempt_ids: tuple[str, ...]
    max_queries: int
    max_results: int
    max_results_per_host: int
    cost_cap_usd: Decimal
    stop_conditions: tuple[str, ...]
    source_lineages: tuple[str, ...]
    independent_lineages: int


_COVERAGE_LANES = {
    "ORIGINAL": frozenset({"PRIMARY_SOURCE", "ORIGINAL_MEDIA"}),
    "FULL_CONTEXT": frozenset({"ARCHIVE_HISTORY"}),
    "OFFICIAL": frozenset({"OFFICIAL_STRUCTURED"}),
    "INDEPENDENT": frozenset({"INDEPENDENT_REPORTING"}),
}


def _executable(assignment: ResearchAssignment) -> bool:
    return (
        assignment.status == "READY"
        and bool(assignment.adapter_ids)
        and bool(assignment.stop_conditions)
        and assignment.max_queries >= 1
        and assignment.max_results >= 1
        and 1 <= assignment.max_results_per_host <= assignment.max_results
    )


def _coverage(
    assignments: tuple[ResearchAssignment, ...],
    observations: tuple[InvestigationObservation, ...],
) -> tuple[InvestigationLaneCoverage, ...]:
    """Never treat a missing lane, a refusal or a mirror as completed checking."""
    completed = {row.assignment_id: row for row in observations}
    result = []
    for stage, accepted_lanes in _COVERAGE_LANES.items():
        planned = tuple(row for row in assignments if row.lane in accepted_lanes)
        seen = tuple(completed[row.assignment_id] for row in planned if row.assignment_id in completed)
        candidates = {row.lineage_id for row in seen if row.result == "REVIEWED_SOURCE_CANDIDATE"}
        # The planner receives opaque lineage strings, hashes and review IDs.
        # Even distinct values cannot prove an outlet did not copy another:
        # only independently verified origin/dependency evidence could do so.
        independent = 0
        if not planned:
            status, reason = "NOT_CHECKED", "INVESTIGATION_NO_AUTHORIZED_ASSIGNMENT"
        elif any(row.status == "BLOCKED" for row in planned):
            status, reason = "WAIT_EXTERNAL", "INVESTIGATION_LANE_BLOCKED"
        elif any(row.result in {"OUTAGE", "RIGHTS_BLOCKED", "COST_BLOCKED", "CAPABILITY_BLOCKED"} for row in seen):
            status, reason = "WAIT_EXTERNAL", "INVESTIGATION_LANE_EXTERNAL_FAILURE"
        elif candidates:
            if stage == "INDEPENDENT":
                status, reason = (
                    "DEPENDENT_OR_UNCORROBORATED", "INVESTIGATION_ORIGIN_INDEPENDENCE_UNPROVED"
                )
            else:
                status, reason = "SOURCE_CANDIDATE", "INVESTIGATION_SOURCE_ONLY"
        elif len(seen) == len(planned):
            status, reason = "CHECKED_INSUFFICIENT", "INVESTIGATION_LANE_CHECKED_NO_CANDIDATE"
        elif seen:
            status, reason = "PARTIALLY_CHECKED", "INVESTIGATION_LANE_UNFINISHED"
        else:
            status, reason = "NOT_CHECKED", "INVESTIGATION_LANE_NOT_ATTEMPTED"
        result.append(InvestigationLaneCoverage(
            stage, status, reason,
            tuple(row.assignment_id for row in planned),
            tuple(row.attempt_id for row in seen),
            sum(row.max_queries for row in planned if row.status == "READY"),
            sum(row.max_results for row in planned if row.status == "READY"),
            min((row.max_results_per_host for row in planned if row.status == "READY"), default=0),
            sum((row.cost_cap_usd for row in planned if row.status == "READY"), Decimal("0")),
            tuple(dict.fromkeys(stop for row in planned for stop in row.stop_conditions)),
            tuple(sorted(candidates)), independent,
        ))
    return tuple(result)


def propose_investigation(
    *,
    spec: InvestigationSpec,
    assignments: Iterable[ResearchAssignment],
    observations: Iterable[InvestigationObservation],
    budget_ready: bool,
    capability_ready: bool,
) -> InvestigationDecision:
    """Pure idempotent plan for one action, not an executor or review event."""
    assignments = tuple(assignments)
    records = tuple(observations)
    if len(assignments) > 16 or len(records) > 64:
        raise ValueError("INVESTIGATION_INPUT_UNBOUNDED")
    if type(budget_ready) is not bool or type(capability_ready) is not bool:
        raise ValueError("INVESTIGATION_READINESS_INVALID")
    active = [row for row in assignments if row.coverage_need_id == spec.need_id]
    ids = [row.assignment_id for row in active]
    if len(ids) != len(set(ids)):
        raise ValueError("INVESTIGATION_DUPLICATE_ASSIGNMENTS")
    active_by_id = {row.assignment_id: row for row in active}
    plan_fp = _hash({
        "need": spec.need_id, "fingerprint": spec.material_fingerprint,
        "question": spec.question_kind, "question_text": spec.question,
        "family": spec.source_family, "max_attempts": spec.max_attempts,
        "cost_cap_usd": str(spec.cost_cap_usd), "rights_status": spec.rights_status,
        "assignments": [dict(
            id=row.assignment_id, lane=row.lane, plan_version=row.plan_version,
            question=row.question, adapters=list(row.adapter_ids),
            stop=list(row.stop_conditions), status=row.status,
            blockers=list(row.blockers),
            max_queries=row.max_queries, max_results=row.max_results,
            max_results_per_host=row.max_results_per_host,
            temporal_constraints=row.temporal_constraints,
            authority_scope=row.authority_scope,
            cost_cap=str(row.cost_cap_usd),
        ) for row in sorted(active, key=lambda row: row.assignment_id)],
        "version": VERSION,
    })
    completed = {}
    for record in records:
        if record.material_fingerprint != spec.material_fingerprint:
            # A source/proposition version change must reopen under a new
            # exact scope, never relabel old historical receipts as current.
            continue
        assigned = active_by_id.get(record.assignment_id)
        if assigned is None or record.lane != assigned.lane:
            raise ValueError("INVESTIGATION_OBSERVATION_FOREIGN_ASSIGNMENT")
        if record.spent_usd > assigned.cost_cap_usd:
            # The overall envelope cannot legitimize a receipt that breached
            # the narrower limit of the actual assigned attempt.
            raise ValueError("INVESTIGATION_ASSIGNMENT_COST_EXCEEDED")
        expected_id = "investigation-attempt:" + _hash({
            "plan": plan_fp, "assignment": record.assignment_id,
            "material": spec.material_fingerprint,
        })
        if record.attempt_id != expected_id:
            raise ValueError("INVESTIGATION_OBSERVATION_UNBOUND_ATTEMPT")
        if not _executable(assigned):
            # First preserve the original plan identity error, then refuse
            # a self-hashed receipt for work which could never be reserved.
            raise ValueError("INVESTIGATION_OBSERVATION_UNAUTHORIZED_ASSIGNMENT")
        old = completed.get(record.attempt_id)
        if old is not None and old != record:
            raise ValueError("INVESTIGATION_ATTEMPT_REPLAY_CONFLICT")
        completed[record.attempt_id] = record
    attempts = tuple(completed.values())
    spent = sum((row.spent_usd for row in attempts), Decimal("0"))
    lineages = {row.lineage_id for row in attempts if row.result == "REVIEWED_SOURCE_CANDIDATE"}
    coverage = _coverage(tuple(active), attempts)

    def decision(status: str, reason: str, attempt: str | None = None, assignment: str | None = None) -> InvestigationDecision:
        return InvestigationDecision(
            status, reason, plan_fp, attempt, assignment, len(attempts),
            max(0, spec.max_attempts - len(attempts)), spent, len(lineages), False,
            coverage,
        )

    if spec.rights_status != "CLEARED":
        return decision("WAIT_EXTERNAL", "INVESTIGATION_RIGHTS_NOT_CLEARED")
    if not budget_ready or spent > spec.cost_cap_usd:
        return decision("WAIT_EXTERNAL", "INVESTIGATION_COST_CAP_OR_RECEIPT_MISSING")
    if not capability_ready:
        return decision("WAIT_EXTERNAL", "INVESTIGATION_CAPABILITY_NOT_READY")
    if lineages:
        # Even a reviewed original locator is an evidence candidate, not a
        # fact verification or legal permission to quote it publicly.
        return decision("RESOLVED_PRIVATE_CANDIDATE", "INVESTIGATION_SOURCE_CANDIDATE_REVIEWED")
    if any(row.result in {"RIGHTS_BLOCKED", "COST_BLOCKED", "CAPABILITY_BLOCKED"} for row in attempts):
        return decision("WAIT_EXTERNAL", "INVESTIGATION_EXTERNAL_GATE_BLOCKED")
    if any(row.result == "OUTAGE" for row in attempts):
        return decision("WAIT_EXTERNAL", "INVESTIGATION_PROVIDER_OUTAGE")
    if len(attempts) >= spec.max_attempts:
        return decision("EXHAUSTED", "INVESTIGATION_ATTEMPT_CAP")

    for assignment in sorted(active, key=lambda value: (value.lane, value.assignment_id)):
        if not _executable(assignment):
            continue
        attempt_id = "investigation-attempt:" + _hash({
            "plan": plan_fp, "assignment": assignment.assignment_id,
            "material": spec.material_fingerprint,
        })
        if attempt_id in completed:
            continue
        if assignment.cost_cap_usd > spec.cost_cap_usd - spent:
            continue
        return decision("READY_PRIVATE_PROPOSAL", "INVESTIGATION_RESEARCH_PLAN_READY", attempt_id, assignment.assignment_id)
    if attempts:
        return decision("CHECKED_INSUFFICIENT", "INVESTIGATION_NO_REVIEWED_ORIGINAL")
    return decision("WAIT_EXTERNAL", "INVESTIGATION_NO_AUTHORIZED_PLAN")
