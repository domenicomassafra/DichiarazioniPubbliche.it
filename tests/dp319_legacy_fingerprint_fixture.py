"""Historical DP-319 v1 planner fingerprint fixture used by upgrade tests."""

from dataclasses import replace

from dichiarazioni_pubbliche.investigation_attempts_store_v1 import _hash
from dichiarazioni_pubbliche.investigation_attempts_v1 import (
    propose_investigation as current_propose_investigation,
)


def legacy_v1_propose_investigation(**kwargs):
    """Exact pre-PR14 planner fingerprint material, on the real SQLite writer.

    The original proposal hash did NOT include rights_status, assignment
    question/host/status/blockers/temporal/authority. Retain a self-contained
    format fixture: CI must not depend on historical Git refs being present.
    """
    scope = kwargs["spec"]
    active = sorted(
        (row for row in kwargs["assignments"] if row.coverage_need_id == scope.need_id),
        key=lambda row: row.assignment_id,
    )
    old_fp = _hash({
        "need": scope.need_id, "fingerprint": scope.material_fingerprint,
        "question": scope.question_kind, "question_text": scope.question,
        "family": scope.source_family, "max_attempts": scope.max_attempts,
        "cost_cap_usd": str(scope.cost_cap_usd),
        "assignments": [dict(
            id=row.assignment_id, lane=row.lane, plan_version=row.plan_version,
            adapters=list(row.adapter_ids), stop=list(row.stop_conditions),
            max_queries=row.max_queries, max_results=row.max_results,
            cost_cap=str(row.cost_cap_usd),
        ) for row in active],
        "version": "investigation-attempt-v1",
    })
    # A prior v1 receipt is legitimate only for the v1 proposal. Translate
    # its ID solely while driving today's decision logic in this test fixture.
    # Actual persisted IDs/events remain byte-for-byte old-v1 records.
    modern = current_propose_investigation(
        **{**kwargs, "observations": ()},
    )
    def old_attempt_for(assignment_id):
        return "investigation-attempt:" + _hash({
            "plan": old_fp, "assignment": assignment_id,
            "material": scope.material_fingerprint,
        })
    def new_attempt_for(assignment_id):
        return "investigation-attempt:" + _hash({
            "plan": modern.plan_fingerprint, "assignment": assignment_id,
            "material": scope.material_fingerprint,
        })
    normalized = []
    for record in kwargs["observations"]:
        if record.attempt_id != old_attempt_for(record.assignment_id):
            raise ValueError("INVESTIGATION_OBSERVATION_UNBOUND_ATTEMPT")
        normalized.append(replace(
            record, attempt_id=new_attempt_for(record.assignment_id),
        ))
    old = current_propose_investigation(
        **{**kwargs, "observations": tuple(normalized)},
    )
    return replace(
        old,
        plan_fingerprint=old_fp,
        proposed_attempt_id=(
            "investigation-attempt:" + _hash({
                "plan": old_fp, "assignment": old.assignment_id,
                "material": scope.material_fingerprint,
            })
            if old.proposed_attempt_id is not None else None
        ),
    )
