from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_research_plan import (  # noqa: E402
    compile_claim_research_plan,
)
from dichiarazioni_pubbliche.domain_vocabulary import InferenceRiskClass  # noqa: E402


def need(
    need_id: str,
    *,
    need_type: str = "OFFICIAL_RECORD",
    question: str | None = None,
    roles=(),
    max_attempts=3,
    attempt_count=0,
):
    return {
        "id": need_id,
        "need_type": need_type,
        "requirement_kind": "AUTHORITY_SCOPE",
        "requirement_fingerprint": "fp:" + need_id,
        "question": question or f"Coverage question for {need_id}",
        "required_roles": list(roles),
        "authority_scope": {"country": "IT"},
        "temporal_constraints": {"not_after": "2026-10-05"},
        "max_attempts": max_attempts,
        "attempt_count": attempt_count,
    }


ADAPTERS = {
    "PRIMARY_SOURCE": ["official-site"],
    "OFFICIAL_STRUCTURED": ["istat"],
    "INDEPENDENT_REPORTING": ["news-search"],
    "EXISTING_FACT_CHECK": ["factcheck-search"],
    "ACADEMIC_EXPERT": ["scholar-search"],
    "ORIGINAL_MEDIA": ["media-search"],
    "ARCHIVE_HISTORY": ["archive-search"],
    "CHALLENGER": ["challenger-search"],
}


class ClaimResearchPlanTests(unittest.TestCase):
    def test_compiles_deterministically_independent_of_need_order(self):
        left = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:b"), need("need:a", need_type="INDEPENDENT_SOURCE")],
            lane_adapters=ADAPTERS,
        )
        right = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a", need_type="INDEPENDENT_SOURCE"), need("need:b")],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(left.status, "READY")
        self.assertEqual(left.plan_id, right.plan_id)
        self.assertEqual(
            [row.assignment_id for row in left.assignments],
            [row.assignment_id for row in right.assignments],
        )

    def test_questions_are_reused_from_coverage_needs_not_invented(self):
        question = "Find the official table for the exact reference period."
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a", question=question)],
            lane_adapters=ADAPTERS,
        )
        self.assertTrue(plan.assignments)
        self.assertEqual({row.question for row in plan.assignments}, {question})

    def test_challenger_is_explicit_opt_in(self):
        base = dict(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
        )
        without = compile_claim_research_plan(**base)
        with_lane = compile_claim_research_plan(**base, include_challenger=True)
        self.assertNotIn("CHALLENGER", {row.lane for row in without.assignments})
        self.assertIn("CHALLENGER", {row.lane for row in with_lane.assignments})

    def test_assignment_cap_blocks_entire_executable_plan(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a"), need("need:b")],
            lane_adapters=ADAPTERS,
            max_assignments=2,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("ASSIGNMENT_CAP_EXCEEDED", plan.blockers)
        self.assertEqual(plan.assignments, ())

    def test_unique_lane_cap_blocks_entire_executable_plan(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a", need_type="OFFICIAL_RECORD")],
            lane_adapters=ADAPTERS,
            include_challenger=True,
            max_unique_lanes=2,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("LANE_CAP_EXCEEDED", plan.blockers)

    def test_result_budget_blocks_without_truncating_silently(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
            per_assignment_max_results=10,
            max_total_results=19,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("RESULT_BUDGET_EXCEEDED", plan.blockers)
        self.assertEqual(plan.assignments, ())

    def test_cost_budget_blocks_without_rebudgeting(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
            per_assignment_cost_cap_usd=Decimal("0.11"),
            max_total_cost_usd=Decimal("0.20"),
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("COST_BUDGET_EXCEEDED", plan.blockers)
        self.assertEqual(plan.assignments, ())

    def test_missing_lane_adapter_blocks_claim_plan_no_fallback(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters={"OFFICIAL_STRUCTURED": ["istat"]},
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("ASSIGNMENT_BLOCKED", plan.blockers)
        self.assertEqual(plan.assignments, ())

    def test_exhausted_needs_do_not_create_assignments(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a", max_attempts=2, attempt_count=2)],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(plan.status, "COMPLETE")
        self.assertEqual(plan.assignments, ())
        self.assertEqual(plan.exhausted_need_count, 1)

    def test_unknown_claim_type_fails_closed(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="MADE_UP_CLAIM_TYPE",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertEqual(plan.blockers, ("CLAIM_TYPE_UNSUPPORTED",))
        self.assertEqual(plan.assignments, ())

    def test_non_factual_claim_type_fails_closed(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="VALUE_JUDGMENT",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("CLAIM_TYPE_NON_FACTUAL", plan.blockers)

    def test_intent_risk_claim_type_fails_closed(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="MOTIVE_ATTRIBUTION",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertIn("CLAIM_TYPE_INTENT_RISK", plan.blockers)

    def test_high_risk_class_fails_closed(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
            risk_class=InferenceRiskClass.SENSITIVE_PERSON,
        )
        self.assertEqual(plan.status, "BLOCKED")
        self.assertEqual(plan.assignments, ())
        self.assertIn("HIGH_RISK_REQUIRES_MANUAL_REVIEW", plan.blockers)

    def test_adapter_permissions_are_not_expanded(self):
        adapters = {
            "OFFICIAL_STRUCTURED": ["istat-only"],
            "EXISTING_FACT_CHECK": ["factcheck-only"],
        }
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=adapters,
        )
        self.assertEqual(plan.status, "READY")
        by_lane = {row.lane: row.adapter_ids for row in plan.assignments}
        self.assertEqual(by_lane["OFFICIAL_STRUCTURED"], ("istat-only",))
        self.assertEqual(by_lane["EXISTING_FACT_CHECK"], ("factcheck-only",))

    def test_compiled_plan_has_no_evidence_review_verification_or_publication_authority(self):
        plan = compile_claim_research_plan(
            claim_id="claim:a",
            claim_type="NUMERIC_STATISTIC",
            coverage_needs=[need("need:a")],
            lane_adapters=ADAPTERS,
        )
        self.assertEqual(plan.status, "READY")
        assignment_fields = set(plan.assignments[0].__dataclass_fields__)
        self.assertTrue(
            {
                "approved",
                "evidence_approved",
                "verification_assessment",
                "publication_status",
                "publish",
            }.isdisjoint(assignment_fields)
        )


if __name__ == "__main__":
    unittest.main()
