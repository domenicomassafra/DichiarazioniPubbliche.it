from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    RelationCandidateType,
)
from dichiarazioni_pubbliche.relation_policy import (  # noqa: E402
    ALLOWED_RELATION_CANDIDATE_STATUSES,
    ALLOWED_RELATION_TYPES,
    PROHIBITED_INTENT_TERMS,
    RELATION_PUBLICATION_POLICY_VERSION,
    RelationCandidateStatus,
    RelationPublicationEligibility,
    RelationPublicationInput,
    evaluate_relation_publication_eligibility,
)


class RelationPolicyTests(unittest.TestCase):
    def test_version_and_vocabularies_are_exposed(self):
        self.assertEqual(RELATION_PUBLICATION_POLICY_VERSION, "relation-publication-v1")
        self.assertIn("CANDIDATE", ALLOWED_RELATION_CANDIDATE_STATUSES)
        self.assertIn("APPROVED", ALLOWED_RELATION_CANDIDATE_STATUSES)
        self.assertIn("REJECTED", ALLOWED_RELATION_CANDIDATE_STATUSES)
        self.assertIn("SUPERSEDED", ALLOWED_RELATION_CANDIDATE_STATUSES)
        # Invariant: PUBLISHED is strictly prohibited as a storable relation candidate status
        self.assertNotIn("PUBLISHED", ALLOWED_RELATION_CANDIDATE_STATUSES)
        self.assertIn("CONTRADICTION_CANDIDATE", ALLOWED_RELATION_TYPES)
        self.assertIn("SAME_PROPOSITION", ALLOWED_RELATION_TYPES)

    # Acceptance criterion 1: candidate and published relation states are distinct
    def test_candidate_and_published_relation_states_are_distinct(self):
        # A relation with status CANDIDATE is never PUBLIC_ELIGIBLE, even if review and findings exist
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.SAME_PROPOSITION,
            relation_status=RelationCandidateStatus.CANDIDATE,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
        )
        self.assertEqual(result, RelationPublicationEligibility.CANDIDATE)
        self.assertNotEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

        # Storable states and computed publication eligibility are distinct types/enums
        self.assertNotIn(
            "PUBLIC_ELIGIBLE",
            ALLOWED_RELATION_CANDIDATE_STATUSES,
        )

    # Acceptance criterion 2: relation publication requires explicit review provenance
    def test_relation_publication_requires_explicit_review_provenance(self):
        # APPROVED storable status without approved review event remains non-publishable (CANDIDATE)
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.SAME_PROPOSITION,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=False,
            has_proposition_keys=True,
        )
        self.assertEqual(result, RelationPublicationEligibility.CANDIDATE)
        self.assertNotEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

    # Acceptance criterion 3: statement-time/context compatibility is checked
    def test_statement_time_and_context_compatibility_checked(self):
        # When statement-time/context is incompatible, relation is rejected from publication
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
            statement_context_compatible=False,
        )
        self.assertEqual(result, RelationPublicationEligibility.REJECTED)
        self.assertNotEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

    # Acceptance criterion 4: contradiction never implies deliberate falsehood (no intent encoding)
    def test_contradiction_never_implies_deliberate_falsehood_no_intent_fields(self):
        # Policy rejects any intent or deception encoding attempts
        with self.assertRaises(ValueError) as ctx:
            evaluate_relation_publication_eligibility(
                relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
                relation_status=RelationCandidateStatus.APPROVED,
                both_claims_have_published_finding=True,
                has_approved_review_event=True,
                has_proposition_keys=True,
                intent="deliberate",  # Prohibited!
            )
        self.assertIn("INTENT_ENCODING_PROHIBITED", str(ctx.exception))

        for term in PROHIBITED_INTENT_TERMS:
            with self.assertRaises(ValueError):
                evaluate_relation_publication_eligibility(
                    relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
                    relation_status=RelationCandidateStatus.APPROVED,
                    both_claims_have_published_finding=True,
                    has_approved_review_event=True,
                    has_proposition_keys=True,
                    **{term: True},
                )

        # RelationPublicationInput also structurally prohibits intent fields
        input_obj = RelationPublicationInput(
            relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
        )
        self.assertFalse(hasattr(input_obj, "intent"))
        self.assertFalse(hasattr(input_obj, "deliberate_falsehood"))
        self.assertFalse(hasattr(input_obj, "bad_faith"))

    # Acceptance criterion 5: public projection omits stale relation reviews fail-closed
    def test_public_projection_omits_stale_relation_reviews_fail_closed(self):
        # When review is stale, publication decision fails closed (returns CANDIDATE, never PUBLIC_ELIGIBLE)
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.SAME_PROPOSITION,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
            review_is_stale=True,
        )
        self.assertEqual(result, RelationPublicationEligibility.CANDIDATE)
        self.assertNotEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

    def test_unpublished_finding_is_never_public_eligible(self):
        # A relation referencing an unpublished finding remains CANDIDATE
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.SAME_PROPOSITION,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=False,
            has_approved_review_event=True,
            has_proposition_keys=True,
        )
        self.assertEqual(result, RelationPublicationEligibility.CANDIDATE)

    def test_missing_proposition_keys_never_becomes_contradiction(self):
        # A contradiction candidate missing proposition keys is REJECTED
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=False,
        )
        self.assertEqual(result, RelationPublicationEligibility.REJECTED)

    def test_approved_published_proposition_keys_yields_public_eligible(self):
        # Happy path: approved status + approved review + published findings + proposition keys
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
            statement_context_compatible=True,
            review_is_stale=False,
        )
        self.assertEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

    def test_unapproved_correction_blocks_public_eligibility(self):
        # When a correction is involved and unapproved, relation is not public eligible
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.POSITION_CHANGE_CANDIDATE,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
            correction_involved=True,
            correction_approved=False,
        )
        self.assertEqual(result, RelationPublicationEligibility.CANDIDATE)

    def test_dataclass_input_identical_to_kwargs(self):
        input_obj = RelationPublicationInput(
            relation_type=RelationCandidateType.SAME_PROPOSITION,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
        )
        result = evaluate_relation_publication_eligibility(input_obj)
        self.assertEqual(result, RelationPublicationEligibility.PUBLIC_ELIGIBLE)

    def test_invalid_status_or_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            evaluate_relation_publication_eligibility(
                relation_type="INVALID_TYPE",
                relation_status=RelationCandidateStatus.APPROVED,
                both_claims_have_published_finding=True,
                has_approved_review_event=True,
                has_proposition_keys=True,
            )

        with self.assertRaises(ValueError):
            evaluate_relation_publication_eligibility(
                relation_type=RelationCandidateType.SAME_PROPOSITION,
                relation_status="INVALID_STATUS",
                both_claims_have_published_finding=True,
                has_approved_review_event=True,
                has_proposition_keys=True,
            )

    def test_no_relation_type_is_rejected(self):
        result = evaluate_relation_publication_eligibility(
            relation_type=RelationCandidateType.NO_RELATION,
            relation_status=RelationCandidateStatus.APPROVED,
            both_claims_have_published_finding=True,
            has_approved_review_event=True,
            has_proposition_keys=True,
        )
        self.assertEqual(result, RelationPublicationEligibility.REJECTED)


if __name__ == "__main__":
    unittest.main()
