import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_plan import (  # noqa: E402
    compile_research_assignments,
    lanes_for_need,
)


def need(**overrides):
    base = {
        "id": "coverage-need:1",
        "question": "Find the applicable official statistic.",
        "need_type": "OFFICIAL_RECORD",
        "required_roles": ["OFFICIAL_STATISTICS"],
        "authority_scope": {"jurisdiction": "IT"},
        "temporal_constraints": {"reference_period": "2026-Q2"},
        "max_attempts": 3,
        "attempt_count": 0,
    }
    base.update(overrides)
    return base


class ResearchPlanTests(unittest.TestCase):
    def test_official_need_routes_to_official_and_existing_check_lanes(self):
        self.assertEqual(
            lanes_for_need(need()),
            ("OFFICIAL_STRUCTURED", "EXISTING_FACT_CHECK"),
        )

    def test_primary_need_keeps_primary_lane(self):
        lanes = lanes_for_need(
            need(
                need_type="PRIMARY_SOURCE",
                required_roles=["FIRST_PARTY_STATEMENT"],
            )
        )
        self.assertEqual(lanes[0], "PRIMARY_SOURCE")

    def test_compile_is_deterministic_and_bounded(self):
        adapters = {
            "OFFICIAL_STRUCTURED": ["istat"],
            "EXISTING_FACT_CHECK": ["claimreview-index"],
        }
        first = compile_research_assignments(
            need(attempt_count=1),
            lane_adapters=adapters,
            max_results=8,
            max_results_per_host=2,
            cost_cap_usd=Decimal("0.25"),
        )
        second = compile_research_assignments(
            need(attempt_count=1),
            lane_adapters=adapters,
            max_results=8,
            max_results_per_host=2,
            cost_cap_usd=Decimal("0.25"),
        )
        self.assertEqual(first, second)
        self.assertEqual({row.max_queries for row in first}, {2})
        self.assertEqual({row.max_results for row in first}, {8})

    def test_missing_adapter_is_explicitly_blocked(self):
        rows = compile_research_assignments(
            need(),
            lane_adapters={"OFFICIAL_STRUCTURED": ["istat"]},
        )
        existing = [row for row in rows if row.lane == "EXISTING_FACT_CHECK"][0]
        self.assertEqual(existing.status, "BLOCKED")
        self.assertEqual(existing.blockers, ("NO_CONFIGURED_ADAPTER_FOR_LANE",))

    def test_exhausted_need_produces_no_new_assignments(self):
        rows = compile_research_assignments(
            need(max_attempts=3, attempt_count=3),
            lane_adapters={"OFFICIAL_STRUCTURED": ["istat"]},
        )
        self.assertEqual(rows, ())

    def test_challenger_is_explicit_opt_in_lane(self):
        adapters = {
            "OFFICIAL_STRUCTURED": ["istat"],
            "EXISTING_FACT_CHECK": ["claimreview-index"],
            "CHALLENGER": ["independent-web"],
        }
        without = compile_research_assignments(need(), lane_adapters=adapters)
        with_challenger = compile_research_assignments(
            need(),
            lane_adapters=adapters,
            include_challenger=True,
        )
        self.assertNotIn("CHALLENGER", {row.lane for row in without})
        self.assertIn("CHALLENGER", {row.lane for row in with_challenger})


if __name__ == "__main__":
    unittest.main()
