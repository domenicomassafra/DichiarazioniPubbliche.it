import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_plan import (  # noqa: E402
    compile_research_assignments,
    discovery_manifest_from_assignments,
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

    def test_ready_assignments_compile_into_existing_discovery_manifest(self):
        assignments = compile_research_assignments(
            need(),
            lane_adapters={
                "OFFICIAL_STRUCTURED": ["istat"],
                "EXISTING_FACT_CHECK": ["google-factcheck"],
            },
            max_results=8,
            max_results_per_host=2,
            cost_cap_usd=Decimal("0.10"),
        )
        manifest = discovery_manifest_from_assignments(
            assignments,
            collection_id="collection:1",
            lane_source_families={
                "OFFICIAL_STRUCTURED": ["official_structured"],
                "EXISTING_FACT_CHECK": ["fact_check"],
            },
        )
        self.assertEqual(manifest.coverage_need_ids, ("coverage-need:1",))
        self.assertEqual(manifest.max_results, 16)
        self.assertEqual(manifest.max_results_per_host, 2)
        self.assertEqual(manifest.cost_cap_usd, Decimal("0.20"))
        self.assertEqual(
            [query.adapter_ids for query in manifest.queries],
            [("istat",), ("google-factcheck",)],
        )
        self.assertEqual(
            [query.metadata["lane"] for query in manifest.queries],
            ["OFFICIAL_STRUCTURED", "EXISTING_FACT_CHECK"],
        )

    def test_manifest_compiler_refuses_blocked_assignment_instead_of_fallback(self):
        assignments = compile_research_assignments(
            need(),
            lane_adapters={"OFFICIAL_STRUCTURED": ["istat"]},
        )
        with self.assertRaisesRegex(
            ValueError,
            "RESEARCH_PLAN_BLOCKED_ASSIGNMENT_REFUSED",
        ):
            discovery_manifest_from_assignments(
                assignments,
                collection_id="collection:1",
                lane_source_families={
                    "OFFICIAL_STRUCTURED": ["official_structured"],
                    "EXISTING_FACT_CHECK": ["fact_check"],
                },
            )

    def test_manifest_compiler_never_expands_adapter_or_result_budget(self):
        assignments = compile_research_assignments(
            need(need_type="OFFICIAL_RECORD"),
            lane_adapters={
                "OFFICIAL_STRUCTURED": ["istat"],
                "EXISTING_FACT_CHECK": ["factcheck"],
            },
            max_results=5,
            max_results_per_host=1,
            cost_cap_usd=Decimal("0.05"),
        )
        manifest = discovery_manifest_from_assignments(
            assignments,
            collection_id="collection:1",
            lane_source_families={
                "OFFICIAL_STRUCTURED": ["official_structured"],
                "EXISTING_FACT_CHECK": ["fact_check"],
            },
        )
        for assignment, query in zip(assignments, manifest.queries):
            self.assertEqual(query.adapter_ids, assignment.adapter_ids)
            self.assertEqual(query.max_results, assignment.max_results)
        self.assertEqual(manifest.max_results, 10)
        self.assertEqual(manifest.cost_cap_usd, Decimal("0.10"))

    def test_manifest_compiler_requires_explicit_lane_source_family(self):
        assignments = compile_research_assignments(
            need(need_type="PRIMARY_SOURCE", required_roles=["FIRST_PARTY_STATEMENT"]),
            lane_adapters={
                "PRIMARY_SOURCE": ["web-primary"],
                "EXISTING_FACT_CHECK": ["factcheck"],
            },
        )
        with self.assertRaisesRegex(ValueError, "RESEARCH_PLAN_SOURCE_FAMILY_REQUIRED"):
            discovery_manifest_from_assignments(
                assignments,
                collection_id="collection:1",
                lane_source_families={
                    "EXISTING_FACT_CHECK": ["fact_check"],
                },
            )

    def test_model_query_suggestion_can_only_narrow_permissions(self):
        assignments = compile_research_assignments(
            need(need_type="OFFICIAL_RECORD"),
            lane_adapters={
                "OFFICIAL_STRUCTURED": ["istat", "eurostat"],
                "EXISTING_FACT_CHECK": ["factcheck"],
            },
            max_results=5,
            max_results_per_host=1,
            cost_cap_usd=Decimal("0.05"),
        )
        official = next(row for row in assignments if row.lane == "OFFICIAL_STRUCTURED")
        families = {
            "OFFICIAL_STRUCTURED": ["istat-family", "eurostat-family"],
            "EXISTING_FACT_CHECK": ["fact-check-family"],
        }
        manifest = discovery_manifest_from_assignments(
            assignments,
            collection_id="collection:1",
            lane_source_families=families,
            query_suggestions={
                official.assignment_id: {
                    "query": "employment rate Italy Q2 2026 official table",
                    "adapter_ids": ["istat"],
                    "source_families": ["istat-family"],
                }
            },
        )
        query = next(row for row in manifest.queries if row.id == official.assignment_id)
        self.assertEqual(query.query_text, "employment rate Italy Q2 2026 official table")
        self.assertEqual(query.adapter_ids, ("istat",))
        self.assertEqual(query.source_families, ("istat-family",))
        self.assertEqual(query.max_results, official.max_results)
        self.assertEqual(manifest.max_results_per_host, 1)
        self.assertEqual(manifest.cost_cap_usd, Decimal("0.10"))
        self.assertEqual(query.metadata["query_source"], "MODEL_SUGGESTION")

        for expansion in (
            {"query": "q", "adapter_ids": ["web-anywhere"]},
            {"query": "q", "source_families": ["unapproved-family"]},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "RESEARCH_PLAN_QUERY_SUGGESTION_PERMISSION_EXPANSION",
            ):
                discovery_manifest_from_assignments(
                    assignments,
                    collection_id="collection:1",
                    lane_source_families=families,
                    query_suggestions={official.assignment_id: expansion},
                )

        with self.assertRaisesRegex(
            ValueError,
            "RESEARCH_PLAN_QUERY_SUGGESTION_FIELDS_INVALID",
        ):
            discovery_manifest_from_assignments(
                assignments,
                collection_id="collection:1",
                lane_source_families=families,
                query_suggestions={
                    official.assignment_id: {"query": "q", "max_results": 500}
                },
            )


if __name__ == "__main__":
    unittest.main()
