import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    MATCHING_VERSION,
    MatchingInput,
    deterministic_match_run_id,
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


if __name__ == "__main__":
    unittest.main()
