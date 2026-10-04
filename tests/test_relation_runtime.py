import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.relation_runtime import (  # noqa: E402
    RelationCandidateType,
    StructuredClaimRelationInput,
    classify_relation,
)


def claim(
    claim_id,
    date,
    *,
    proposition=None,
    topic="vehicle-tax",
    stance=None,
    start=None,
    end=None,
    continuity=False,
):
    return StructuredClaimRelationInput(
        claim_id,
        date,
        proposition,
        topic,
        stance,
        start,
        end,
        continuity,
    )


class RelationRuntimeTests(unittest.TestCase):
    def test_related_topic_is_not_contradiction(self):
        prior = claim("a", "2016-01-01", proposition="criticize-announcement", stance="criticize")
        later = claim("b", "2026-01-01", proposition="abolish-tax", stance="support")
        result = classify_relation(prior, later)
        self.assertEqual(result.relation_type, RelationCandidateType.RELATED_TOPIC)

    def test_opposite_stance_nonoverlapping_time_is_position_change_candidate(self):
        prior = claim("a", "2024-01-01", proposition="p", stance="support")
        later = claim("b", "2026-01-01", proposition="p", stance="oppose")
        result = classify_relation(prior, later)
        self.assertEqual(
            result.relation_type,
            RelationCandidateType.POSITION_CHANGE_CANDIDATE,
        )

    def test_opposite_stance_same_scope_is_contradiction_candidate(self):
        prior = claim(
            "a",
            "2026-01-01",
            proposition="p",
            stance="support",
            start="2026-01-01",
            end="2026-12-31",
        )
        later = claim(
            "b",
            "2026-02-01",
            proposition="p",
            stance="oppose",
            start="2026-01-01",
            end="2026-12-31",
        )
        result = classify_relation(prior, later)
        self.assertEqual(
            result.relation_type,
            RelationCandidateType.CONTRADICTION_CANDIDATE,
        )

    def test_retrospective_continuity_can_create_contradiction_candidate(self):
        prior = claim("a", "2024-01-01", proposition="p", stance="support")
        later = claim(
            "b",
            "2026-01-01",
            proposition="p",
            stance="oppose",
            continuity=True,
        )
        result = classify_relation(prior, later)
        self.assertEqual(
            result.relation_type,
            RelationCandidateType.CONTRADICTION_CANDIDATE,
        )

    def test_missing_proposition_never_becomes_contradiction(self):
        result = classify_relation(
            claim("a", "2024-01-01", proposition=None, stance="support"),
            claim("b", "2026-01-01", proposition=None, stance="oppose"),
        )
        self.assertEqual(result.relation_type, RelationCandidateType.RELATED_TOPIC)


if __name__ == "__main__":
    unittest.main()
