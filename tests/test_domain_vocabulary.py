import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    CLAIM_TYPE_VERSION,
    FINDING_PUBLICATION_STATUS_VERSION,
    RELATION_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    ClaimType,
    EvaluationOutcome,
    FindingPublicationStatus,
    RelationCandidateType,
    VerificationAssessment,
)


class DomainVocabularyTests(unittest.TestCase):
    def test_each_versioned_layer_has_a_closed_distinct_meaning(self):
        self.assertEqual(CLAIM_TYPE_VERSION, "atomic-claim-v1")
        self.assertEqual(
            VERIFICATION_ASSESSMENT_VERSION, "deterministic-verification-v2"
        )
        self.assertEqual(
            FINDING_PUBLICATION_STATUS_VERSION, "finding-publication-v1"
        )
        self.assertEqual(RELATION_VERSION, "claim-relation-v1")
        self.assertNotIn(
            EvaluationOutcome.NO_CONTRADICTION_ESTABLISHED,
            VerificationAssessment,
        )
        self.assertNotIn(
            VerificationAssessment.SUPPORTED,
            FindingPublicationStatus,
        )
        self.assertNotIn(
            RelationCandidateType.CONTRADICTION_CANDIDATE,
            VerificationAssessment,
        )

    def test_unsupported_nuanced_labels_remain_outside_runtime_contract(self):
        unsupported = {
            "PARTIALLY_SUPPORTED",
            "MISQUOTE",
            "PROMISE_BROKEN",
            "DELIBERATE_FALSEHOOD",
            "PUBLISH_WITH_LIMITATIONS",
            "REJECTED_AS_FALSE",
        }
        emitted = {
            value
            for vocabulary in (
                ClaimType,
                VerificationAssessment,
                FindingPublicationStatus,
                RelationCandidateType,
            )
            for value in vocabulary
        }
        self.assertTrue(unsupported.isdisjoint(emitted))

    def test_public_claim_review_rating_is_non_numeric_and_assessment_only(self):
        from dichiarazioni_pubbliche.domain_vocabulary import VerificationAssessment

        for assessment in VerificationAssessment:
            if assessment in {
                VerificationAssessment.INSUFFICIENT_EVIDENCE,
                VerificationAssessment.UNRESOLVED,
            }:
                continue
            rating = {
                "@type": "Rating",
                "alternateName": assessment.value,
            }
            self.assertNotIn("ratingValue", rating)
            self.assertNotIn("bestRating", rating)
            self.assertNotIn("worstRating", rating)


if __name__ == "__main__":
    unittest.main()
