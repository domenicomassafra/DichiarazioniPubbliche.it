"""DP-301 — intentionality policy tests.

The product invariant under test (PRODUCT.md, non-negotiable):

    No inference that a contradiction proves deception or malicious intent.
    A position change is not automatically a lie.
    A false factual claim is not automatically a deliberate falsehood.

These tests are the machine-checkable form of that invariant. They must fail if
anyone adds an intent-bearing public label, a person score, or a relation->intent
mapping.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    FindingPublicationStatus,
    RelationCandidateType,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.policy.intent_policy import (  # noqa: E402
    ASSESSMENT_TO_INTENT,
    INTENT_POLICY_VERSION,
    AssessmentIntent,
    PUBLIC_ASSESSMENTS,
    PUBLIC_INTENT_PROHIBITED_TERMS,
    PublishabilityBlocker,
    PublishabilityInput,
    assert_no_intent_member,
    assess_publishability,
    classify_text_intent_risk,
    find_prohibited_intent_term,
    find_prohibited_person_score_term,
    is_descriptive_only_relation,
    is_person_score_free,
    normalize_label,
    relation_to_assessment,
    scan_public_label,
)
from dichiarazioni_pubbliche.policy.intent_policy import IntentTextRisk  # noqa: E402
from dichiarazioni_pubbliche.relation_policy import (  # noqa: E402
    PROHIBITED_INTENT_TERMS,
)


def _complete(**overrides) -> PublishabilityInput:
    """A minimal fully-satisfying publishability input, overridable per test."""
    base = {
        "assessment": VerificationAssessment.FACTUALLY_FALSE,
        "has_approved_review_event": True,
        "verification_rule_version": "deterministic-verification-v2",
        "statement_cutoff": "2026-01-15T00:00:00Z",
        "approved_evidence_ids": ("ev-1",),
        "approved_observation_ids": ("ob-1",),
    }
    base.update(overrides)
    return PublishabilityInput(**base)


class IntentVocabularyTests(unittest.TestCase):
    def test_policy_version_is_pinned(self):
        self.assertEqual(INTENT_POLICY_VERSION, "intentionality-policy-v1")

    def test_no_public_enum_member_carries_intent_or_person_score_language(self):
        # Fails at import if violated; re-assert here so the failure is legible.
        assert_no_intent_member()
        for vocabulary in (
            AssessmentIntent,
            VerificationAssessment,
            FindingPublicationStatus,
            RelationCandidateType,
        ):
            for member in vocabulary:
                self.assertIsNone(
                    scan_public_label(member.value),
                    f"{vocabulary.__name__}.{member.name} carries prohibited language",
                )

    def test_intent_vocabulary_contains_no_lying_or_motive_member(self):
        emitted = {m.value for m in AssessmentIntent}
        for forbidden in (
            "LIE",
            "LYING",
            "DECEIVED",
            "DECEIPTION",
            "DISHONEST",
            "DELIBERATE",
            "BAD_FAITH",
            "MOTIVE",
            "KNOWLEDGE",
            "INTENT",
            "MENS_REA",
        ):
            self.assertNotIn(forbidden, emitted)

    def test_every_assessment_maps_to_a_claim_level_intent(self):
        # The map is total over the assessment enum, and every target is
        # claim-level (i.e. one of the four AssessmentIntent members).
        for assessment in VerificationAssessment:
            self.assertIn(assessment, ASSESSMENT_TO_INTENT)
            self.assertIn(ASSESSMENT_TO_INTENT[assessment], set(AssessmentIntent))

    def test_policy_inherits_the_existing_relation_prohibited_terms(self):
        # DP-301 asks us to extend the existing vocabulary guard pattern rather
        # than invent a parallel one: the policy term set must be a strict
        # superset of relation_policy's set.
        self.assertTrue(PROHIBITED_INTENT_TERMS.issubset(PUBLIC_INTENT_PROHIBITED_TERMS))


class HardRuleTests(unittest.TestCase):
    """The single most important tests in the repository."""

    def test_contradiction_relation_never_yields_an_intent_or_assessment(self):
        self.assertIsNone(
            relation_to_assessment(RelationCandidateType.CONTRADICTION_CANDIDATE)
        )

    def test_position_change_relation_never_yields_an_intent_or_assessment(self):
        self.assertIsNone(
            relation_to_assessment(RelationCandidateType.POSITION_CHANGE_CANDIDATE)
        )

    def test_every_relation_is_descriptive_only_and_never_maps_to_intent(self):
        for relation in RelationCandidateType:
            self.assertIsNone(relation_to_assessment(relation))
        self.assertTrue(
            is_descriptive_only_relation(RelationCandidateType.CONTRADICTION_CANDIDATE)
        )

    def test_relation_to_assessment_rejects_unknown_relation_without_inventing_one(self):
        self.assertIsNone(relation_to_assessment("MADE_UP_RELATION"))

    def test_factually_false_assessment_is_not_rendered_as_intent(self):
        # FACTUALLY_FALSE is legal as a claim-level label. What is illegal is a
        # public LABEL that re-frames it as intentionality.
        decision = assess_publishability(_complete())
        self.assertTrue(decision.publishable)
        # The allowed public wording stays claim-level.
        self.assertIsNone(
            scan_public_label(
                ASSESSMENT_TO_INTENT[VerificationAssessment.FACTUALLY_FALSE].value
            )
        )
        self.assertEqual(
            ASSESSMENT_TO_INTENT[VerificationAssessment.FACTUALLY_FALSE],
            AssessmentIntent.CONTRADICTED_BY_EVIDENCE,
        )


class ProhibitedTermDetectionTests(unittest.TestCase):
    def test_detects_english_intent_terms_in_various_casings_and_separators(self):
        for label in (
            "LIE",
            "lies",
            "lying",
            "intent",
            "intentional",
            "deliberate",
            "deception",
            "dishonest",
            "bad faith",
            "bad_faith",
            "motive",
            "mens rea",
            "deliberate_falsehood",
        ):
            with self.subTest(label=label):
                self.assertIsNotNone(find_prohibited_intent_term(label), label)

    def test_detects_italian_intent_terms(self):
        for label in (
            "bugiardo",
            "bugiarda",
            "menzogna",
            "menzogne",
            "dolo",
            "mala fede",
            "disonesto",
            "inganno",
            "intenzionale",
        ):
            with self.subTest(label=label):
                self.assertIsNotNone(find_prohibited_intent_term(label), label)

    def test_detects_accents_and_case_variants(self):
        for label in ("Menzogna", "BUGIARDO", "Malafede", "INTENZIONALITÀ"):
            with self.subTest(label=label):
                self.assertIsNotNone(find_prohibited_intent_term(label), label)

    def test_invisible_format_characters_cannot_hide_intent_or_person_scores(self):
        # These zero-width/bidi controls are invisible to readers, but previously
        # split a forbidden token so the public-label gate silently accepted it.
        for label in ("men\u200bzogna", "bu\u00adgiardo", "diso\u200cnesto", "intenzion\u200dalmente"):
            with self.subTest(intent=repr(label)):
                self.assertEqual(scan_public_label(label), "INTENT_LANGUAGE_IN_LABEL")
        for label in ("affida\u200bbilita", "reliab\u2060ility", "perso\u200bnRanking"):
            with self.subTest(person_score=repr(label)):
                self.assertEqual(scan_public_label(label), "PERSON_SCORE_LANGUAGE_IN_LABEL")

    def test_clean_claim_level_labels_are_not_flagged(self):
        for label in (
            "SUPPORTED",
            "FACTUALLY_FALSE",
            "OUTDATED_DATA",
            "CONTRADICTED_BY_EVIDENCE",
            "a claim was not supported by the approved evidence",
        ):
            with self.subTest(label=label):
                self.assertIsNone(find_prohibited_intent_term(label), label)

    def test_person_score_terms_are_detected_separately(self):
        self.assertIsNotNone(find_prohibited_person_score_term("reliability_score"))
        self.assertIsNotNone(find_prohibited_person_score_term("personRanking"))
        self.assertIsNotNone(find_prohibited_person_score_term("attendibilita"))
        self.assertIsNone(find_prohibited_person_score_term("claim_id"))

    def test_normalize_label_is_deterministic_and_accent_free(self):
        self.assertEqual(normalize_label("BugiardO_disonest"), "bugiardo disonest")
        self.assertEqual(normalize_label("  Bad_Faith  "), "bad faith")

    def test_person_score_free_mapping_check(self):
        self.assertTrue(is_person_score_free({"assessment": "FACTUALLY_FALSE"}))
        self.assertFalse(is_person_score_free({"assessment": "X", "trust_score": 5}))


class UntrustedTextClassificationTests(unittest.TestCase):
    def test_intent_language_in_submitted_text_is_prohibited_not_published(self):
        result = classify_text_intent_risk("The official has lied about the numbers.")
        self.assertIs(result.disposition, IntentTextRisk.PROHIBITED_LABEL)

    def test_italian_intent_language_is_prohibited(self):
        result = classify_text_intent_risk("Il funzionario e bugiardo.")
        self.assertIs(result.disposition, IntentTextRisk.PROHIBITED_LABEL)

    def test_reported_accusation_with_denial_is_held_not_prohibited(self):
        # A submission that *reports* an accusation is a different risk. It is
        # still not a public label, but it is a human-review hold.
        result = classify_text_intent_risk(
            "They accuse him of lying; I deny that and provide the record."
        )
        self.assertIs(result.disposition, IntentTextRisk.HOLD_FOR_REVIEW)

    def test_neutral_text_is_allowed(self):
        result = classify_text_intent_risk(
            "On 3 March 2026 the statement said 12,000; the register shows 11,800."
        )
        self.assertIs(result.disposition, IntentTextRisk.ALLOWED)

    def test_empty_text_is_allowed(self):
        self.assertIs(classify_text_intent_risk("").disposition, IntentTextRisk.ALLOWED)
        self.assertIs(classify_text_intent_risk(None).disposition, IntentTextRisk.ALLOWED)


class PublishabilityTests(unittest.TestCase):
    def test_complete_evidence_contract_publishes(self):
        decision = assess_publishability(_complete())
        self.assertTrue(decision.publishable)
        self.assertEqual(decision.reason, PublishabilityBlocker.OK.value)

    def test_missing_approved_review_event_blocks(self):
        decision = assess_publishability(_complete(has_approved_review_event=False))
        self.assertFalse(decision.publishable)
        self.assertIn(
            PublishabilityBlocker.NO_APPROVED_REVIEW_EVENT, decision.blockers
        )

    def test_missing_verification_rule_version_blocks(self):
        decision = assess_publishability(_complete(verification_rule_version=""))
        self.assertIn(
            PublishabilityBlocker.NO_VERIFICATION_RULE_VERSION, decision.blockers
        )

    def test_missing_statement_cutoff_blocks(self):
        decision = assess_publishability(_complete(statement_cutoff=None))
        self.assertIn(PublishabilityBlocker.NO_STATEMENT_CUTOFF, decision.blockers)

    def test_missing_approved_evidence_or_observations_blocks(self):
        self.assertIn(
            PublishabilityBlocker.NO_APPROVED_EVIDENCE,
            assess_publishability(_complete(approved_evidence_ids=())).blockers,
        )
        self.assertIn(
            PublishabilityBlocker.NO_APPROVED_OBSERVATIONS,
            assess_publishability(_complete(approved_observation_ids=())).blockers,
        )

    def test_stale_review_blocks(self):
        decision = assess_publishability(_complete(review_is_stale=True))
        self.assertIn(PublishabilityBlocker.STALE_REVIEW, decision.blockers)

    def test_future_evidence_is_refused_unless_evaluating_a_later_outcome(self):
        refused = assess_publishability(_complete(uses_future_evidence=True))
        self.assertIn(PublishabilityBlocker.FUTURE_EVIDENCE_USED, refused.blockers)

        allowed = assess_publishability(
            _complete(uses_future_evidence=True, evaluates_later_outcome=True)
        )
        self.assertTrue(allowed.publishable)

    def test_non_publishable_assessment_is_never_public(self):
        for assessment in (
            VerificationAssessment.INSUFFICIENT_EVIDENCE,
            VerificationAssessment.UNRESOLVED,
        ):
            with self.subTest(assessment=assessment):
                decision = assess_publishability(_complete(assessment=assessment))
                self.assertFalse(decision.publishable)
                self.assertIn(
                    PublishabilityBlocker.NON_PUBLISHABLE_ASSESSMENT,
                    decision.blockers,
                )

    def test_unknown_assessment_fails_closed(self):
        decision = assess_publishability(_complete(assessment="SOMETHING_ELSE"))
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.blockers[0], PublishabilityBlocker.UNKNOWN_ASSESSMENT)

    def test_intent_language_in_a_public_label_blocks_even_when_evidence_is_complete(self):
        decision = assess_publishability(_complete(public_label="proved a deliberate lie"))
        self.assertFalse(decision.publishable)
        self.assertIn(PublishabilityBlocker.INTENT_LANGUAGE_IN_LABEL, decision.blockers)

    def test_missing_limitations_blocks(self):
        decision = assess_publishability(_complete(limitations_present=False))
        self.assertIn(PublishabilityBlocker.LIMITATIONS_MISSING, decision.blockers)

    def test_public_assessments_are_a_closed_subset(self):
        self.assertTrue(PUBLIC_ASSESSMENTS.issubset(set(VerificationAssessment)))
        self.assertNotIn(VerificationAssessment.UNRESOLVED, PUBLIC_ASSESSMENTS)


if __name__ == "__main__":
    unittest.main()
