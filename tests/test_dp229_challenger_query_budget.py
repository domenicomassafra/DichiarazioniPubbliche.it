"""DP-229: the challenger bridge must not authorize excess DP-209 queries."""
from __future__ import annotations

import unittest
from decimal import Decimal

from dichiarazioni_pubbliche.challenger_research import compile_challenger_research_request
from dichiarazioni_pubbliche.claim_research_plan import compile_claim_research_plan
from dichiarazioni_pubbliche.research_discovery import MAX_QUERIES
from tests.test_challenger_research import need, ADAPTERS


class ChallengerQueryBudgetTests(unittest.TestCase):
    def _plan(self, attempts):
        row = need("need:synthetic", "Find strongest counterevidence")
        row["max_attempts"] = attempts
        return compile_claim_research_plan(
            claim_id="claim:fixture", claim_type="NUMERIC_STATISTIC",
            coverage_needs=[row], lane_adapters=ADAPTERS,
            include_challenger=True, per_assignment_cost_cap_usd=Decimal("0"),
        )

    def test_unbounded_attempt_count_is_blocked_before_discovery(self):
        plan = self._plan(1_000_000)
        self.assertEqual(plan.status, "READY")
        request = compile_challenger_research_request(plan)
        self.assertEqual(request.status, "BLOCKED")
        self.assertIn("CHALLENGER_QUERY_BUDGET_EXCEEDED", request.blockers)
        self.assertGreater(request.max_queries, MAX_QUERIES)

    def test_budget_at_limit_stays_ready_and_narrow_limit_blocks(self):
        plan = self._plan(MAX_QUERIES)
        self.assertEqual(compile_challenger_research_request(plan).status, "READY")
        narrowed = compile_challenger_research_request(plan, max_total_queries=8)
        self.assertEqual(narrowed.status, "BLOCKED")
        self.assertIn("CHALLENGER_QUERY_BUDGET_EXCEEDED", narrowed.blockers)

    def test_request_must_not_raise_discovery_upper_bound(self):
        with self.assertRaisesRegex(ValueError, "CHALLENGER_RESEARCH_QUERY_CAP_INVALID"):
            compile_challenger_research_request(self._plan(1), max_total_queries=MAX_QUERIES + 1)


if __name__ == "__main__":
    unittest.main()
