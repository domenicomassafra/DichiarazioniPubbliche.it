import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_candidate_review import inspect_candidate_match_run  # noqa: E402

F = "a" * 64


class Store:
    def __init__(self):
        self.run = {
            "id": "candidate-match-run:1",
            "claim_candidate_id": "candidate:1",
            "input_fingerprint": F,
            "status": "COMPLETED",
            "result_count": 1,
        }
        self.results = ({
            "id": "match:1", "rank": 1, "target_id": "claim:2",
            "target_type": "ATOMIC_CLAIM", "match_class": "UNCERTAIN",
            "disposition": "HOLD", "lexical_score": 0.99,
            "supporting_features": [{"code": "SAME_CLAIM_TYPE", "value": "SECRET"}],
            "contradicting_features": [{"code": "TEMPORAL_SCOPE_DIFFERS", "value": "PRIVATE"}],
            "private_transcript": "DO NOT EXPOSE",
        },)

    def get_run(self, run_id):
        return self.run

    def load_results(self, run_id):
        return self.results


class StudioCandidateReviewTests(unittest.TestCase):
    def test_persisted_run_is_read_only_and_does_not_expose_raw_data(self):
        result = inspect_candidate_match_run(Store(), run_id="candidate-match-run:1", claim_candidate_id="candidate:1")
        self.assertEqual(result["currentness"], "UNVERIFIED")
        self.assertFalse(result["review_authority"])
        self.assertFalse(result["publication_authority"])
        self.assertEqual(result["results"][0]["match_class"], "UNCERTAIN")
        self.assertEqual(result["results"][0]["suggested_disposition"], "HOLD")
        self.assertFalse(result["results"][0]["promotion_enabled"])
        encoded = json.dumps(result)
        for forbidden in ("PRIVATE", "SECRET", "DO NOT EXPOSE", "lexical_score", "0.99"):
            self.assertNotIn(forbidden, encoded)

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
                inspect_candidate_match_run(store, run_id="candidate-match-run:1", claim_candidate_id="candidate:1")
        store = Store()
        store.results[0]["disposition"] = "PROPOSE_CLUSTER"
        with self.assertRaises(ValueError):
            inspect_candidate_match_run(store, run_id="candidate-match-run:1", claim_candidate_id="candidate:1")

    def test_untrusted_feature_code_is_rejected(self):
        store = Store()
        store.results[0]["supporting_features"] = [{"code": "<script>"}]
        with self.assertRaisesRegex(ValueError, "FEATURE_CODE_INVALID"):
            inspect_candidate_match_run(store, run_id="candidate-match-run:1", claim_candidate_id="candidate:1")


if __name__ == "__main__":
    unittest.main()
