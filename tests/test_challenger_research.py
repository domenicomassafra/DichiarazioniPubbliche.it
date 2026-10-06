from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenger_research import (  # noqa: E402
    compile_challenger_research_request,
)
from dichiarazioni_pubbliche.claim_research_plan import (  # noqa: E402
    compile_claim_research_plan,
)


def need(need_id: str, question: str):
    return {
        "id": need_id,
        "need_type": "OFFICIAL_RECORD",
        "requirement_kind": "AUTHORITY_SCOPE",
        "requirement_fingerprint": "fp:" + need_id,
        "question": question,
        "required_roles": ["OFFICIAL_STATISTICS"],
        "authority_scope": {},
        "temporal_constraints": {},
        "max_attempts": 2,
        "attempt_count": 0,
    }


ADAPTERS = {
    "OFFICIAL_STRUCTURED": ["istat"],
    "EXISTING_FACT_CHECK": ["factcheck"],
    "CHALLENGER": ["challenger-search"],
}


class ChallengerResearchTests(unittest.TestCase):
    def _plan(self, *, challenger=True, needs=None, cost="0.10"):
        return compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=needs or [need("need:a", "Check the strongest countercase source.")],
            lane_adapters=ADAPTERS,
            include_challenger=challenger,
            per_assignment_cost_cap_usd=Decimal(cost),
            max_total_cost_usd=Decimal("5"),
            max_total_results=200,
        )

    def test_explicit_challenger_assignments_compile_to_bounded_request(self):
        plan = self._plan()
        request = compile_challenger_research_request(plan)
        self.assertEqual(request.status, "READY")
        self.assertEqual(len(request.assignment_ids), 1)
        self.assertEqual(request.adapter_ids, ("challenger-search",))
        self.assertEqual(request.max_results, 10)
        self.assertEqual(request.cost_cap_usd, Decimal("0.10"))

    def test_request_identity_is_deterministic(self):
        left = compile_challenger_research_request(self._plan())
        right = compile_challenger_research_request(self._plan())
        self.assertEqual(left.request_id, right.request_id)

    def test_challenger_cannot_be_invented_when_plan_did_not_opt_in(self):
        request = compile_challenger_research_request(self._plan(challenger=False))
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CHALLENGER_NOT_ENABLED", request.blockers)
        self.assertIn("CHALLENGER_ASSIGNMENT_MISSING", request.blockers)
        self.assertEqual(request.assignment_ids, ())

    def test_question_is_copied_exactly_not_generated(self):
        question = "Exact Coverage Need question: seek a qualifying contrary record."
        request = compile_challenger_research_request(
            self._plan(needs=[need("need:a", question)])
        )
        self.assertEqual(request.questions, (question,))

    def test_request_has_no_counterevidence_or_verdict_authority(self):
        request = compile_challenger_research_request(self._plan())
        fields = set(request.__dataclass_fields__)
        self.assertTrue(
            {
                "evidence_id",
                "evidence_ids",
                "assessment",
                "verification_assessment",
                "finding_id",
                "publication_status",
                "verdict",
            }.isdisjoint(fields)
        )

    def test_challenger_assignment_cap_fails_closed(self):
        plan = self._plan(
            needs=[
                need("need:a", "Question A"),
                need("need:b", "Question B"),
            ]
        )
        request = compile_challenger_research_request(plan, max_assignments=1)
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CHALLENGER_ASSIGNMENT_CAP_EXCEEDED", request.blockers)

    def test_challenger_result_budget_fails_closed(self):
        request = compile_challenger_research_request(
            self._plan(),
            max_total_results=9,
        )
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CHALLENGER_RESULT_BUDGET_EXCEEDED", request.blockers)

    def test_challenger_cost_budget_fails_closed(self):
        request = compile_challenger_research_request(
            self._plan(cost="0.30"),
            max_total_cost_usd=Decimal("0.20"),
        )
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CHALLENGER_COST_BUDGET_EXCEEDED", request.blockers)

    def test_blocked_claim_plan_cannot_emit_ready_challenger_request(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="VALUE_JUDGMENT",
            coverage_needs=[need("need:a", "Question")],
            lane_adapters=ADAPTERS,
            include_challenger=True,
        )
        request = compile_challenger_research_request(plan)
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CLAIM_RESEARCH_PLAN_NOT_READY", request.blockers)


if __name__ == "__main__":
    unittest.main()
