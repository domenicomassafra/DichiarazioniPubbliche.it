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
    @staticmethod
    def _inputs(**overrides):
        return {
            "target_type": "ATOMIC_CLAIM", "target_id": "claim:valid:0001",
            "source_intelligence_assessment_id": "assessment:valid",
            "candidates": [{"requirement_kind": "MIN_INDEPENDENT_LINEAGES",
                            "reason": "INDEPENDENT_LINEAGES_REQUIRED",
                            "independence_requirement": 2}],
        } | overrides

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

    def test_materialization_refuses_max_attempts_coercion_and_out_of_bounds(self):
        for invalid in (True, False, 0, -1, 11, 3.9, "3", None, 2**63):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "COVERAGE_NEED_MAX_ATTEMPTS_INVALID"
            ):
                materialize_coverage_need_specs(**self._inputs(max_attempts=invalid))
        for value in (1, 3, 10):
            with self.subTest(valid=value):
                self.assertEqual(materialize_coverage_need_specs(
                    **self._inputs(max_attempts=value)
                )[0].max_attempts, value)

    def test_independence_requirement_rejects_coercion_and_unbounded_values(self):
        for invalid in (True, False, 0, -4, 2.4, "2", "-1", 2**31):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "COVERAGE_NEED_INDEPENDENCE_INVALID"
            ):
                materialize_coverage_need_specs(**self._inputs(candidates=[{
                    "requirement_kind": "MIN_INDEPENDENT_LINEAGES",
                    "independence_requirement": invalid,
                }]))
        valid = materialize_coverage_need_specs(**self._inputs())[0]
        self.assertEqual(valid.independence_requirement, 2)
        self.assertIn("at least 2", valid.question)

    def test_duplicate_semantic_candidates_collapse_per_collection_scope(self):
        canonical = {
            "requirement_kind": "ROLE_ANY", "reason": "REQUIRED_PRIMARY",
            "required_roles": ["PRIMARY_RECORD"],
        }
        repeated_role = canonical | {"required_roles": ["PRIMARY_RECORD", "PRIMARY_RECORD"]}
        params = self._inputs(
            candidates=[canonical, dict(canonical), repeated_role],
            collection_ids=("collection:a", "collection:a", "collection:b"),
        )
        specs = materialize_coverage_need_specs(**params)
        self.assertEqual(len(specs), 2)
        self.assertEqual({s.collection_id for s in specs}, {"collection:a", "collection:b"})
        self.assertEqual(len({s.id for s in specs}), 2)
        self.assertTrue(all(s.required_roles == ("PRIMARY_RECORD",) for s in specs))

    def test_malformed_scope_candidate_and_roles_never_materialize(self):
        for change in (
            {"target_id": ""},
            {"target_id": None},
            {"target_type": ["ATOMIC_CLAIM"]},
            {"collection_ids": ("",)},
            {"collection_ids": (None, "collection:a")},
            {"candidates": [None]},
            {"candidates": [{"requirement_kind": "UNKNOWN_KIND"}]},
            {"candidates": [{"requirement_kind": "ROLE_ANY", "required_roles": "PRIMARY_RECORD"}]},
            {"candidates": [{"requirement_kind": "ROLE_ANY", "required_roles": [False]}]},
            {"candidates": [{"requirement_kind": "ROLE_ANY", "authority_scope": ["wrong"]}]},
            {"candidates": [{"requirement_kind": "ROLE_ANY", "temporal_constraints": ["wrong"]}]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                materialize_coverage_need_specs(**self._inputs(**change))
        # Existing opaque IDs must remain intact; the scope guard does not
        # impose a new naming convention on old persisted identifiers.
        spec = materialize_coverage_need_specs(**self._inputs(
            target_id="legacy arbitrary claim ID", collection_ids=("old collection ID",),
        ))[0]
        self.assertEqual(spec.atomic_claim_id, "legacy arbitrary claim ID")
        self.assertEqual(spec.collection_id, "old collection ID")

    def test_discovery_hint_blocks_exhausted_or_corrupt_attempt_bounds(self):
        base = {
            "id": "coverage-need:one", "status": "SEARCHING",
            "question": "Which original source is missing?", "need_type": "PRIMARY_SOURCE",
            "required_roles": ["PRIMARY_RECORD"], "authority_scope": {},
            "temporal_constraints": {}, "max_attempts": 3, "attempt_count": 1,
        }
        self.assertEqual(discovery_hint_for_need(base)["remaining_attempts"], 2)
        for change in (
            {"attempt_count": 3}, {"attempt_count": 4},
            {"attempt_count": -1}, {"attempt_count": True},
            {"attempt_count": "1"}, {"max_attempts": False},
            {"max_attempts": 11}, {"max_attempts": -1},
            {"max_attempts": "3"}, {"required_roles": "PRIMARY_RECORD"},
            {"authority_scope": ["wrong"]}, {"temporal_constraints": ["wrong"]},
            {"id": ""}, {"question": ""}, {"need_type": ["PRIMARY_SOURCE"]},
            {"independence_requirement": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                discovery_hint_for_need(base | change)


if __name__ == "__main__":
    unittest.main()
