import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_candidate_review import inspect_candidate_match_run  # noqa: E402
from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    MATCHING_VERSION,
    deterministic_match_result_id,
    deterministic_match_run_id,
)

F = "a" * 64
CANDIDATE_ID = "candidate:1"
RUN_ID = deterministic_match_run_id(CANDIDATE_ID, F)
TARGET_ID = "claim:2"
RESULT_ID = deterministic_match_result_id(RUN_ID, "ATOMIC_CLAIM", TARGET_ID)


class Store:
    def __init__(self):
        self.run = {
            "id": RUN_ID,
            "claim_candidate_id": CANDIDATE_ID,
            "matching_version": MATCHING_VERSION,
            "input_fingerprint": F,
            "status": "COMPLETED",
            "result_count": 1,
        }
        self.results = ({
            "id": RESULT_ID, "rank": 1, "target_id": TARGET_ID,
            "target_type": "ATOMIC_CLAIM", "match_class": "UNCERTAIN",
            "matching_version": MATCHING_VERSION, "status": "CANDIDATE",
            "disposition": "HOLD", "method": "LEXICAL_TRIGRAM", "lexical_score": 0.99,
            "proposition_cluster_id": None,
            "supporting_features": [
                {"code": "AMBIGUOUS_LEXICAL_OVERLAP", "score": 0.5},
                {"code": "SAME_CLAIM_TYPE", "value": "SECRET"},
            ],
            "contradicting_features": [{"code": "TEMPORAL_SCOPE_DIFFERS", "value": "PRIVATE"}],
            "private_transcript": "DO NOT EXPOSE",
        },)

    def get_run(self, run_id):
        return self.run

    def load_results(self, run_id):
        return self.results


class StudioCandidateReviewTests(unittest.TestCase):
    def test_classifier_generated_primary_feature_signatures_are_admitted(self):
        valid_cases = (
            ("DUPLICATE_EXTRACTION", "SOURCE_SELECTOR_OVERLAP",
             ["SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT"], [], "PROPOSE_CLUSTER"),
            ("SAME_PROPOSITION", "EXACT_NORMALIZED",
             ["EXACT_NORMALIZED_TEXT"], [], "PROPOSE_CLUSTER"),
            ("SAME_PROPOSITION", "LEXICAL_TRIGRAM",
             ["HIGH_LEXICAL_OVERLAP", "SHARED_ENTITIES"], [], "PROPOSE_CLUSTER"),
            ("SAME_PROPOSITION", "LEXICAL_TRIGRAM",
             ["HIGH_LEXICAL_OVERLAP", "SHARED_TOPICS"], [], "PROPOSE_CLUSTER"),
            ("RELATED", "LEXICAL_TRIGRAM",
             ["RELATED_LEXICAL_OR_ENTITY_CONTEXT"], [], "NO_CLUSTER"),
            ("DIFFERENT", "LEXICAL_TRIGRAM",
             [], ["LOW_LEXICAL_NO_SHARED_CONTEXT"], "NO_CLUSTER"),
            ("UNCERTAIN", "LEXICAL_TRIGRAM",
             ["AMBIGUOUS_LEXICAL_OVERLAP"], [], "HOLD"),
        )
        for kind, method, supports, contradicts, disposition in valid_cases:
            with self.subTest(match_class=kind, method=method):
                store = Store()
                store.results[0].update({
                    "match_class": kind, "method": method,
                    "supporting_features": [{"code": code} for code in supports],
                    "contradicting_features": [{"code": code} for code in contradicts],
                    "disposition": disposition,
                    "proposition_cluster_id": (
                        "proposition-cluster:valid"
                        if disposition == "PROPOSE_CLUSTER" else None
                    ),
                })
                result = inspect_candidate_match_run(
                    store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID,
                )
                self.assertEqual(result["results"][0]["match_class"], kind)
                self.assertFalse(result["results"][0]["promotion_enabled"])

    def test_persisted_match_class_requires_canonical_explanatory_features(self):
        # DP-212's classifier always persists class/method-specific evidence.
        # A class + plausible method alone cannot substantiate its meaning.
        invalid_cases = (
            {"supporting_features": [{"code": "SAME_CLAIM_TYPE"}]},
            {"supporting_features": [
                {"code": "AMBIGUOUS_LEXICAL_OVERLAP"},
                {"code": "AMBIGUOUS_LEXICAL_OVERLAP"},
            ]},
            {"match_class": "RELATED", "method": "LEXICAL_TRIGRAM",
             "disposition": "NO_CLUSTER", "contradicting_features": [],
             "supporting_features": [{"code": "SAME_CLAIM_TYPE"}]},
            {"match_class": "DIFFERENT", "method": "LEXICAL_TRIGRAM",
             "disposition": "NO_CLUSTER", "contradicting_features": [],
             "supporting_features": []},
            {"match_class": "SAME_PROPOSITION", "method": "EXACT_NORMALIZED",
             "disposition": "PROPOSE_CLUSTER",
             "proposition_cluster_id": "proposition-cluster:valid",
             "contradicting_features": [],
             "supporting_features": [{"code": "SAME_CLAIM_TYPE"}]},
            {"match_class": "SAME_PROPOSITION", "method": "LEXICAL_TRIGRAM",
             "disposition": "PROPOSE_CLUSTER",
             "proposition_cluster_id": "proposition-cluster:valid",
             "contradicting_features": [],
             "supporting_features": [{"code": "HIGH_LEXICAL_OVERLAP"}]},
            {"match_class": "DUPLICATE_EXTRACTION", "method": "SOURCE_SELECTOR_OVERLAP",
             "disposition": "PROPOSE_CLUSTER",
             "proposition_cluster_id": "proposition-cluster:valid",
             "contradicting_features": [],
             "supporting_features": [{"code": "EXACT_NORMALIZED_TEXT"}]},
            {"supporting_features": [
                {"code": "AMBIGUOUS_LEXICAL_OVERLAP"},
                {"code": "SAME_CLAIM_TYPE"},
            ], "contradicting_features": [{"code": "CLAIM_TYPE_MISMATCH"}]},
        )
        for updates in invalid_cases:
            with self.subTest(updates=updates):
                store = Store()
                store.results[0].update(updates)
                with self.assertRaisesRegex(ValueError, 'FEATURE_SEMANTICS_INVALID'):
                    inspect_candidate_match_run(
                        store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID,
                    )

    def test_persisted_matching_versions_and_result_status_are_not_inferred(self):
        for field, invalid in (("matching_version", None), ("matching_version", "candidate-matching-v0")):
            store = Store()
            store.run[field] = invalid
            with self.subTest(run=invalid), self.assertRaisesRegex(ValueError, "RUN_VERSION_INVALID"):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        for field, invalid in (("matching_version", None), ("matching_version", "candidate-matching-v0"), ("status", None), ("status", "REJECTED")):
            store = Store()
            store.results[0][field] = invalid
            with self.subTest(result=invalid, field=field), self.assertRaisesRegex(ValueError, "RESULT_(VERSION|STATUS)_INVALID"):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_persisted_run_is_read_only_and_does_not_expose_raw_data(self):
        result = inspect_candidate_match_run(Store(), run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        self.assertEqual(result["currentness"], "UNVERIFIED")
        self.assertFalse(result["review_authority"])
        self.assertFalse(result["publication_authority"])
        self.assertEqual(result["matching_version"], MATCHING_VERSION)
        self.assertEqual(result["results"][0]["matching_method"], "LEXICAL_TRIGRAM")
        self.assertEqual(result["results"][0]["match_class"], "UNCERTAIN")
        self.assertEqual(result["results"][0]["suggested_disposition"], "HOLD")
        self.assertFalse(result["results"][0]["promotion_enabled"])
        encoded = json.dumps(result)
        for forbidden in ("PRIVATE", "SECRET", "DO NOT EXPOSE", "lexical_score", "0.99"):
            self.assertNotIn(forbidden, encoded)

    def test_unsigned_bounded_count_and_versioned_run_binding(self):
        for invalid in (-1, True, 1.0, 31, "1"):
            store = Store()
            store.run["result_count"] = invalid
            with self.subTest(count=invalid), self.assertRaisesRegex(ValueError, "COUNT_INVALID"):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        store = Store()
        store.run["input_fingerprint"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "RUN_BINDING_MISMATCH"):
            inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_stale_or_mismatched_run_fails_closed(self):
        cases = [
            ("claim_candidate_id", "candidate:wrong"),
            ("status", "FAILED"),
            ("result_count", 2),
            ("input_fingerprint", "invalid"),
        ]
        for key, value in cases:
            store = Store()
            store.run[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        store = Store()
        store.results[0]["disposition"] = "PROPOSE_CLUSTER"
        with self.assertRaises(ValueError):
            inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_untrusted_feature_code_is_rejected(self):
        store = Store()
        store.results[0]["supporting_features"] = [{"code": "<script>"}]
        with self.assertRaisesRegex(ValueError, "FEATURE_CODE_INVALID"):
            inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_cross_run_result_or_retargeted_id_is_rejected(self):
        for field, value in (
            ("id", deterministic_match_result_id("candidate-match-run:foreign", "ATOMIC_CLAIM", TARGET_ID)),
            ("target_id", "claim:other"),
        ):
            store = Store()
            store.results[0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "RESULT_BINDING"):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_rank_requires_integer_not_boolean_or_float(self):
        for invalid in (True, 1.0):
            store = Store()
            store.results[0]["rank"] = invalid
            with self.subTest(rank=invalid), self.assertRaisesRegex(ValueError, "RESULT_ORDER"):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_structured_scope_conflict_is_hold_even_for_same_proposition(self):
        store = Store()
        row = store.results[0]
        row["match_class"] = "SAME_PROPOSITION"
        row["method"] = "EXACT_NORMALIZED"
        row["disposition"] = "HOLD"
        row["supporting_features"] = [{"code": "EXACT_NORMALIZED_TEXT"}]
        row["contradicting_features"] = [{"code": "TEMPORAL_SCOPE_DIFFERS", "candidate": {"reference_period": "2025"}, "target": {"reference_period": "2026"}}]
        inspected = inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        self.assertEqual(inspected["results"][0]["suggested_disposition"], "HOLD")
        self.assertEqual(inspected["results"][0]["contradicting_feature_codes"], ("TEMPORAL_SCOPE_DIFFERS",))
        row["disposition"] = "PROPOSE_CLUSTER"
        row["proposition_cluster_id"] = "cluster:wrong"
        with self.assertRaisesRegex(ValueError, "MATCH_CLASS_INVALID"):
            inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_unknown_feature_code_or_algorithm_fails_closed(self):
        for field, value in (
            ("method", "PRIVATE_MODEL"),
            ("supporting_features", [{"code": "PRIVATE_TRANSCRIPT_FRAGMENT"}]),
        ):
            store = Store()
            store.results[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)

    def test_matching_proposal_requires_cluster_and_typed_method(self):
        store = Store()
        row = store.results[0]
        row["match_class"] = "SAME_PROPOSITION"
        row["method"] = "EXACT_NORMALIZED"
        row["disposition"] = "PROPOSE_CLUSTER"
        row["supporting_features"] = [{"code": "EXACT_NORMALIZED_TEXT"}]
        row["contradicting_features"] = []
        row["proposition_cluster_id"] = "proposition-cluster:valid"
        receipt = inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)
        self.assertEqual(receipt["results"][0]["suggested_disposition"], "PROPOSE_CLUSTER")
        self.assertFalse(receipt["results"][0]["promotion_enabled"])
        row["proposition_cluster_id"] = None
        with self.assertRaisesRegex(ValueError, "MATCH_CLASS_INVALID"):
            inspect_candidate_match_run(store, run_id=RUN_ID, claim_candidate_id=CANDIDATE_ID)


if __name__ == "__main__":
    unittest.main()
