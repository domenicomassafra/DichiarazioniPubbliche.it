from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.research_plan import ResearchAssignment


RESEARCH_EXECUTION_RECONCILIATION_VERSION = "research-execution-reconciliation-v1"
ATTEMPT_STATUSES = frozenset({"HEALTHY", "FAILED", "BLOCKED"})


class CoverageNeedExecutionStore(Protocol):
    def record_coverage_need_attempt(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        actor_ref: str = "system",
        reason: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def block_coverage_need(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        blocker_code: str,
        actor_ref: str = "system",
        reason: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class ResearchAssignmentAttemptReceipt:
    assignment_id: str
    run_id: str
    status: str
    error_category: str | None = None
    version: str = RESEARCH_EXECUTION_RECONCILIATION_VERSION

    def __post_init__(self) -> None:
        if not str(self.assignment_id or "").strip():
            raise ValueError("RESEARCH_EXECUTION_ASSIGNMENT_ID_REQUIRED")
        if not str(self.run_id or "").strip():
            raise ValueError("RESEARCH_EXECUTION_RUN_ID_REQUIRED")
        if self.status not in ATTEMPT_STATUSES:
            raise ValueError("RESEARCH_EXECUTION_STATUS_INVALID")


@dataclass(frozen=True)
class ResearchExecutionReconciliation:
    assignment_id: str
    coverage_need_id: str
    run_id: str
    attempt_status: str
    coverage_need_state: str
    action: str
    blocker_code: str | None
    version: str = RESEARCH_EXECUTION_RECONCILIATION_VERSION


def reconcile_research_assignment_attempt(
    *,
    assignment: ResearchAssignment,
    receipt: ResearchAssignmentAttemptReceipt,
    store: CoverageNeedExecutionStore,
    event_id: str,
    actor_ref: str = "research-discovery",
) -> ResearchExecutionReconciliation:
    """Persist one DP-209 attempt outcome back onto its exact Coverage Need.

    A provider-blocked attempt becomes an explicit terminal Coverage Need blocker.
    Healthy/failed attempts consume one bounded attempt but never satisfy the need: only
    separately approved evidence can do that. The event metadata binds the persisted
    transition to the research assignment and run without storing provider bodies.
    """

    if assignment.status != "READY":
        raise ValueError("RESEARCH_EXECUTION_BLOCKED_ASSIGNMENT_REFUSED")
    if receipt.assignment_id != assignment.assignment_id:
        raise ValueError("RESEARCH_EXECUTION_ASSIGNMENT_BINDING_MISMATCH")
    event = str(event_id or "").strip()
    if not event:
        raise ValueError("RESEARCH_EXECUTION_EVENT_ID_REQUIRED")

    metadata = {
        "research_assignment_id": assignment.assignment_id,
        "research_run_id": receipt.run_id,
        "lane": assignment.lane,
        "attempt_status": receipt.status,
        "error_category": receipt.error_category,
        "reconciliation_version": RESEARCH_EXECUTION_RECONCILIATION_VERSION,
    }
    reason = f"research assignment {assignment.assignment_id} run {receipt.run_id}: {receipt.status}"

    if receipt.status == "BLOCKED":
        blocker = "RESEARCH_PROVIDER_BLOCKED"
        state = store.block_coverage_need(
            coverage_need_id=assignment.coverage_need_id,
            event_id=event,
            blocker_code=blocker,
            actor_ref=actor_ref,
            reason=reason,
            metadata=metadata,
        )
        return ResearchExecutionReconciliation(
            assignment_id=assignment.assignment_id,
            coverage_need_id=assignment.coverage_need_id,
            run_id=receipt.run_id,
            attempt_status=receipt.status,
            coverage_need_state=state,
            action="BLOCK",
            blocker_code=blocker,
        )

    persisted = store.record_coverage_need_attempt(
        coverage_need_id=assignment.coverage_need_id,
        event_id=event,
        actor_ref=actor_ref,
        reason=reason,
        metadata=metadata,
    )
    state = str(persisted.get("status") or "")
    return ResearchExecutionReconciliation(
        assignment_id=assignment.assignment_id,
        coverage_need_id=assignment.coverage_need_id,
        run_id=receipt.run_id,
        attempt_status=receipt.status,
        coverage_need_state=state,
        action="RECORD_ATTEMPT",
        blocker_code=("MAX_ATTEMPTS_REACHED" if state == "BLOCKED" else None),
    )


__all__ = [
    "ATTEMPT_STATUSES",
    "RESEARCH_EXECUTION_RECONCILIATION_VERSION",
    "ResearchAssignmentAttemptReceipt",
    "ResearchExecutionReconciliation",
    "reconcile_research_assignment_attempt",
]
