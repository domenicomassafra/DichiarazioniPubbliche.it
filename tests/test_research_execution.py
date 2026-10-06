from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_execution import (  # noqa: E402
    ResearchAssignmentAttemptReceipt,
    reconcile_research_assignment_attempt,
)
from dichiarazioni_pubbliche.research_plan import ResearchAssignment  # noqa: E402


def assignment(*, status="READY", blockers=()):
    return ResearchAssignment(
        assignment_id="research-assignment:a",
        coverage_need_id="coverage:a",
        lane="OFFICIAL_STRUCTURED",
        question="Find the exact official table.",
        adapter_ids=("istat",) if status == "READY" else (),
        max_queries=2,
        max_results=10,
        max_results_per_host=3,
        cost_cap_usd=Decimal("0"),
        temporal_constraints={"not_after": "2026-10-05"},
        authority_scope={"country": "IT"},
        stop_conditions=("PROVIDER_BLOCKED",),
        status=status,
        blockers=blockers,
    )


class FakeStore:
    def __init__(self, attempt_state="SEARCHING"):
        self.attempt_state = attempt_state
        self.attempts = []
        self.blocks = []

    def record_coverage_need_attempt(self, **kwargs):
        self.attempts.append(kwargs)
        return {"status": self.attempt_state, "attempt_count": 1, "searchable": True}

    def block_coverage_need(self, **kwargs):
        self.blocks.append(kwargs)
        return "BLOCKED"


class ResearchExecutionTests(unittest.TestCase):
    def test_provider_blocked_attempt_persists_explicit_coverage_need_block(self):
        store = FakeStore()
        result = reconcile_research_assignment_attempt(
            assignment=assignment(),
            receipt=ResearchAssignmentAttemptReceipt(
                assignment_id="research-assignment:a",
                run_id="discovery-run:a",
                status="BLOCKED",
                error_category="PROVIDER_UNAVAILABLE",
            ),
            store=store,
            event_id="coverage-event:a",
        )
        self.assertEqual(result.coverage_need_state, "BLOCKED")
        self.assertEqual(result.blocker_code, "RESEARCH_PROVIDER_BLOCKED")
        self.assertFalse(store.attempts)
        self.assertEqual(store.blocks[0]["coverage_need_id"], "coverage:a")
        self.assertEqual(
            store.blocks[0]["metadata"]["research_assignment_id"],
            "research-assignment:a",
        )
        self.assertEqual(store.blocks[0]["metadata"]["research_run_id"], "discovery-run:a")

    def test_failed_attempt_remains_explicit_and_retryable_until_attempt_budget_exhausts(self):
        store = FakeStore(attempt_state="SEARCHING")
        result = reconcile_research_assignment_attempt(
            assignment=assignment(),
            receipt=ResearchAssignmentAttemptReceipt(
                assignment_id="research-assignment:a",
                run_id="discovery-run:b",
                status="FAILED",
                error_category="PROVIDER_ERROR",
            ),
            store=store,
            event_id="coverage-event:b",
        )
        self.assertEqual(result.action, "RECORD_ATTEMPT")
        self.assertEqual(result.coverage_need_state, "SEARCHING")
        self.assertIsNone(result.blocker_code)
        self.assertEqual(len(store.attempts), 1)
        self.assertFalse(store.blocks)

    def test_healthy_discovery_attempt_never_auto_satisfies_coverage_need(self):
        store = FakeStore(attempt_state="SEARCHING")
        result = reconcile_research_assignment_attempt(
            assignment=assignment(),
            receipt=ResearchAssignmentAttemptReceipt(
                assignment_id="research-assignment:a",
                run_id="discovery-run:c",
                status="HEALTHY",
            ),
            store=store,
            event_id="coverage-event:c",
        )
        self.assertEqual(result.coverage_need_state, "SEARCHING")
        self.assertFalse(store.blocks)
        self.assertEqual(len(store.attempts), 1)

    def test_assignment_binding_mismatch_and_blocked_plan_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ASSIGNMENT_BINDING_MISMATCH"):
            reconcile_research_assignment_attempt(
                assignment=assignment(),
                receipt=ResearchAssignmentAttemptReceipt(
                    assignment_id="research-assignment:other",
                    run_id="discovery-run:a",
                    status="FAILED",
                ),
                store=FakeStore(),
                event_id="coverage-event:a",
            )
        with self.assertRaisesRegex(ValueError, "BLOCKED_ASSIGNMENT_REFUSED"):
            reconcile_research_assignment_attempt(
                assignment=assignment(
                    status="BLOCKED", blockers=("NO_CONFIGURED_ADAPTER_FOR_LANE",)
                ),
                receipt=ResearchAssignmentAttemptReceipt(
                    assignment_id="research-assignment:a",
                    run_id="discovery-run:a",
                    status="FAILED",
                ),
                store=FakeStore(),
                event_id="coverage-event:a",
            )


if __name__ == "__main__":
    unittest.main()
