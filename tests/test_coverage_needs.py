import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.coverage_needs import (  # noqa: E402
    coverage_need_params,
    discovery_hint_for_need,
    materialize_coverage_need_specs,
)


class CoverageNeedTests(unittest.TestCase):
    def test_missing_official_role_becomes_open_official_record_need(self):
        specs = materialize_coverage_need_specs(
            target_type="ATOMIC_CLAIM",
            target_id="claim:a",
            source_intelligence_assessment_id="assessment:a",
            candidates=[
                {
                    "requirement_kind": "ROLE_ANY",
                    "reason": "AUTHENTIC_LEGAL_TEXT_REQUIRED",
                    "required_roles": ["AUTHENTIC_LEGAL_TEXT"],
                }
            ],
        )
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].need_type, "OFFICIAL_RECORD")
        self.assertEqual(specs[0].atomic_claim_id, "claim:a")
        self.assertIsNone(specs[0].collection_id)
        self.assertEqual(len(specs[0].requirement_fingerprint), 64)

    def test_collection_scope_is_part_of_identity_and_replay_stable(self):
        kwargs = dict(
            target_type="ATOMIC_CLAIM",
            target_id="claim:a",
            source_intelligence_assessment_id="assessment:a",
            candidates=[
                {
                    "requirement_kind": "MIN_INDEPENDENT_LINEAGES",
                    "reason": "INDEPENDENT_LINEAGE_REQUIRED",
                    "independence_requirement": 2,
                }
            ],
            collection_ids=("collection:a", "collection:b"),
        )
        first = materialize_coverage_need_specs(**kwargs)
        second = materialize_coverage_need_specs(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(len({row.id for row in first}), 2)
        self.assertEqual({row.need_type for row in first}, {"INDEPENDENT_SOURCE"})

    def test_params_have_deterministic_event_ids(self):
        spec = materialize_coverage_need_specs(
            target_type="CLAIM_CANDIDATE",
            target_id="candidate:a",
            source_intelligence_assessment_id="assessment:a",
            candidates=[
                {
                    "requirement_kind": "TEMPORAL_CUTOFF",
                    "reason": "TEMPORAL_APPLICABILITY_REQUIRED",
                    "temporal_constraints": {"not_after": "2026-01-01"},
                }
            ],
        )[0]
        left = coverage_need_params(spec)
        right = coverage_need_params(spec)
        self.assertEqual(left["created_event_id"], right["created_event_id"])
        self.assertEqual(spec.need_type, "TEMPORAL_GAP")

    def test_discovery_hint_refuses_terminal_need(self):
        with self.assertRaisesRegex(ValueError, "COVERAGE_NEED_NOT_SEARCHABLE"):
            discovery_hint_for_need(
                {
                    "id": "need:a",
                    "status": "SATISFIED",
                    "max_attempts": 3,
                    "attempt_count": 1,
                }
            )


if __name__ == "__main__":
    unittest.main()
