import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    CandidateMatchingError,
    MATCHING_VERSION,
    MatchingInput,
    deterministic_match_run_id,
    match_claim_candidate,
    matching_input_fingerprint,
    rank_candidate_matches,
)
from dichiarazioni_pubbliche.proposition_clustering import PropositionInput  # noqa: E402


def item(
    member_type,
    member_id,
    text,
    *,
    content_id="content:x",
    provenance_key=None,
    claim_type="HISTORICAL_CLAIM",
    temporal_scope=None,
    entities=(),
):
    return MatchingInput(
        proposition=PropositionInput(
            member_type=member_type,
            member_id=member_id,
            content_id=content_id,
            normalized_text=text,
            provenance_key=provenance_key,
            entity_keys=tuple(entities),
        ),
        claim_type=claim_type,
        temporal_scope=temporal_scope or {},
    )


class CandidateMatchingTests(unittest.TestCase):
    def test_duplicate_ranks_ahead_of_related(self):
        candidate = item(
            "CLAIM_CANDIDATE",
            "candidate:a",
            "L'impronta 33 non conteneva sangue.",
            content_id="content:a",
            provenance_key="passage:a",
            entities=("topic:impronta33",),
        )
        duplicate = item(
            "CLAIM_CANDIDATE",
            "candidate:b",
            "L'impronta 33 non conteneva sangue.",
            content_id="content:a",
            provenance_key="passage:a",
            entities=("topic:impronta33",),
        )
        related = item(
            "ATOMIC_CLAIM",
            "claim:c",
            "Nell'impronta 33 furono osservate sei o sette minuzie.",
            content_id="content:c",
            entities=("topic:impronta33",),
        )
        results = rank_candidate_matches(candidate, [related, duplicate])
        self.assertEqual(results[0].match.match_class, "DUPLICATE_EXTRACTION")
        self.assertEqual(results[0].disposition, "PROPOSE_CLUSTER")
        self.assertEqual(results[-1].match.match_class, "RELATED")

    def test_uncertain_is_held_and_never_creates_cluster(self):
        candidate = item("CLAIM_CANDIDATE", "candidate:a", "alpha beta gamma delta")
        target = item("ATOMIC_CLAIM", "claim:b", "alpha beta theta lambda")
        result = rank_candidate_matches(candidate, [target])[0]
        self.assertEqual(result.match.match_class, "UNCERTAIN")
        self.assertEqual(result.disposition, "HOLD")
        self.assertIsNone(result.cluster_id)

    def test_matching_fingerprint_is_target_order_independent_and_versioned(self):
        candidate = item("CLAIM_CANDIDATE", "candidate:a", "Il valore è 10.")
        left = item("ATOMIC_CLAIM", "claim:a", "Il valore è 10.")
        right = item("ATOMIC_CLAIM", "claim:b", "Il valore era 11.")
        first = matching_input_fingerprint(candidate, [left, right])
        second = matching_input_fingerprint(candidate, [right, left])
        self.assertEqual(first, second)
        run_id = deterministic_match_run_id("candidate:a", first)
        self.assertTrue(run_id.startswith("candidate-match-run:"))
        self.assertEqual(MATCHING_VERSION, "candidate-matching-v1")

    def test_structured_type_and_time_features_are_inspectable(self):
        candidate = item(
            "CLAIM_CANDIDATE",
            "candidate:a",
            "Il tasso era 10.",
            claim_type="NUMERIC_STATISTIC",
            temporal_scope={"reference_period": "2026-07"},
        )
        target = item(
            "ATOMIC_CLAIM",
            "claim:a",
            "Il tasso era 10.",
            claim_type="NUMERIC_STATISTIC",
            temporal_scope={"reference_period": "2026-07"},
        )
        result = rank_candidate_matches(candidate, [target])[0]
        codes = {feature["code"] for feature in result.supporting_features}
        self.assertIn("SAME_CLAIM_TYPE", codes)
        self.assertIn("SAME_TEMPORAL_SCOPE", codes)

    def test_identical_text_with_conflicting_reference_period_cannot_propose_cluster(self):
        candidate = item(
            "CLAIM_CANDIDATE", "candidate:period", "Il tasso era 10.",
            claim_type="NUMERIC_STATISTIC", temporal_scope={"reference_period": "2025"},
        )
        target = item(
            "ATOMIC_CLAIM", "claim:period", "Il tasso era 10.",
            claim_type="NUMERIC_STATISTIC", temporal_scope={"reference_period": "2026"},
        )
        result = rank_candidate_matches(candidate, [target])[0]
        self.assertEqual(result.match.match_class, "SAME_PROPOSITION")
        self.assertEqual(result.disposition, "HOLD")
        self.assertIsNone(result.cluster_id)
        self.assertIn("TEMPORAL_SCOPE_DIFFERS", {feature["code"] for feature in result.contradicting_features})

    def test_duplicate_selector_with_conflicting_claim_type_cannot_propose_cluster(self):
        candidate = item(
            "CLAIM_CANDIDATE", "candidate:type", "La verifica è conclusa.",
            provenance_key="passage:1", claim_type="LEGAL_STATUS",
        )
        target = item(
            "CLAIM_CANDIDATE", "candidate:type:other", "La verifica è conclusa.",
            provenance_key="passage:1", claim_type="HISTORICAL_CLAIM",
        )
        result = rank_candidate_matches(candidate, [target])[0]
        self.assertEqual(result.match.match_class, "DUPLICATE_EXTRACTION")
        self.assertEqual(result.disposition, "HOLD")
        self.assertIsNone(result.cluster_id)
        self.assertIn("CLAIM_TYPE_MISMATCH", {feature["code"] for feature in result.contradicting_features})

    def test_fingerprint_records_new_disposition_policy(self):
        candidate = item("CLAIM_CANDIDATE", "candidate:policy", "Un dato misurato.")
        target = item("ATOMIC_CLAIM", "claim:policy", "Un dato misurato.")
        import dataclasses
        import hashlib
        import json
        old_payload = {
            "matching_version": MATCHING_VERSION,
            "candidate": dataclasses.asdict(candidate),
            "targets": [dataclasses.asdict(target)],
        }
        old_digest = hashlib.sha256(json.dumps(
            old_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        self.assertNotEqual(old_digest, matching_input_fingerprint(candidate, [target]))

    def test_matching_execution_persists_hold_without_creating_cluster(self):
        candidate = item(
            "CLAIM_CANDIDATE", "candidate:held", "Il valore è 10.",
            temporal_scope={"reference_period": "2025"},
        )
        target = item(
            "ATOMIC_CLAIM", "claim:held", "Il valore è 10.",
            temporal_scope={"reference_period": "2026"},
        )

        class Store:
            def __init__(self):
                self.persisted = None
                self.clusters = []

            def load_candidate(self, claim_candidate_id):
                return candidate

            def load_targets(self, claim_candidate_id, *, limit):
                return (target,)

            def get_run(self, run_id):
                return None

            def insert_cluster_proposal(self, *, candidate, result):
                self.clusters.append(result)

            def persist_run(self, **kwargs):
                self.persisted = kwargs

        store = Store()
        receipt = match_claim_candidate(claim_candidate_id="candidate:held", store=store)
        self.assertEqual(receipt.result_count, 1)
        self.assertEqual(receipt.results[0].disposition, "HOLD")
        self.assertEqual(store.clusters, [])
        self.assertEqual(store.persisted["results"], receipt.results)

    def test_blocked_or_mismatched_persisted_run_cannot_masquerade_as_replay(self):
        candidate = item("CLAIM_CANDIDATE", "candidate:replay", "Un dato misurato.")

        class Store:
            def __init__(self, status, candidate_id="candidate:replay"):
                self.status = status
                self.candidate_id = candidate_id

            def load_candidate(self, claim_candidate_id):
                return candidate

            def load_targets(self, claim_candidate_id, *, limit):
                return ()

            def get_run(self, run_id):
                return {
                    "status": self.status,
                    "claim_candidate_id": self.candidate_id,
                    "input_fingerprint": matching_input_fingerprint(candidate, ()),
                    "result_count": 0,
                }

            def load_results(self, run_id):
                raise AssertionError("Must fail before loading results")

        for status, candidate_id in (("BLOCKED", "candidate:replay"),
                                     ("COMPLETED", "candidate:other")):
            with self.subTest(status=status, candidate_id=candidate_id):
                with self.assertRaisesRegex(CandidateMatchingError, "REPLAY_AUTHORITY_MISMATCH"):
                    match_claim_candidate(
                        claim_candidate_id="candidate:replay",
                        store=Store(status, candidate_id),
                    )

    def test_replay_rejects_result_target_or_rank_tampering_even_if_count_matches(self):
        candidate = item("CLAIM_CANDIDATE", "candidate:replay", "Un dato misurato.")
        target = item("ATOMIC_CLAIM", "claim:expected", "Un dato misurato.")

        class Store:
            def __init__(self, result):
                self.result = result

            def load_candidate(self, claim_candidate_id):
                return candidate

            def load_targets(self, claim_candidate_id, *, limit):
                return (target,)

            def get_run(self, run_id):
                return {
                    "status": "COMPLETED", "claim_candidate_id": "candidate:replay",
                    "input_fingerprint": matching_input_fingerprint(candidate, (target,)),
                    "result_count": 1,
                }

            def load_results(self, run_id):
                return (self.result,)

        for row in (
            {"target_type": "ATOMIC_CLAIM", "target_id": "claim:other", "rank": 1},
            {"target_type": "ATOMIC_CLAIM", "target_id": "claim:expected", "rank": 2},
        ):
            with self.subTest(row=row):
                with self.assertRaisesRegex(CandidateMatchingError, "REPLAY_RESULTS_MISMATCH"):
                    match_claim_candidate(claim_candidate_id="candidate:replay", store=Store(row))


if __name__ == "__main__":
    unittest.main()
