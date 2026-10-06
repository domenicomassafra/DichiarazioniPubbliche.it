import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    ProceduralStatus,
    RiskClass,
    classify_high_risk,
    evaluate_high_risk_candidate,
)


def evaluate(**overrides):
    values = dict(
        source_text="La procura comunica che Mario Rossi è indagato.",
        normalized_text="Mario Rossi è indagato.",
        legal_status_claim=True,
        identity_resolved=True,
        privacy_allows=True,
        official_record_approved=True,
        jurisdiction_match=True,
        effective_time_match=True,
        human_review_approved=True,
        dual_control_approved=True,
        qualified_policy_accepted=True,
        policy_decision_ref="decision:dp307:legal-status-v1",
    )
    values.update(overrides)
    return evaluate_high_risk_candidate(**values)


class HighRiskAssertionTests(unittest.TestCase):
    def test_procedural_terms_remain_distinct(self):
        fixtures = {
            "è indagato": ProceduralStatus.INVESTIGATED,
            "è imputato": ProceduralStatus.CHARGED,
            "è processato": ProceduralStatus.PROSECUTED,
            "è condannato": ProceduralStatus.CONVICTED,
            "è assolto": ProceduralStatus.ACQUITTED,
            "caso archiviato": ProceduralStatus.DISMISSED,
        }
        for text, expected in fixtures.items():
            with self.subTest(text=text):
                signals = classify_high_risk(
                    source_text=text, normalized_text=text, legal_status_claim=True
                )
                self.assertEqual(signals.procedural_statuses, (expected,))

    def test_no_signal_is_standard_review_not_safety_certification(self):
        decision = evaluate_high_risk_candidate(
            source_text="Il bilancio è stato pubblicato.",
            normalized_text="Il bilancio è stato pubblicato.",
            identity_resolved=True,
            privacy_allows=True,
            official_record_approved=False,
            jurisdiction_match=False,
            effective_time_match=False,
            human_review_approved=False,
            dual_control_approved=False,
            qualified_policy_accepted=False,
        )
        self.assertEqual(decision.disposition, "STANDARD_REVIEW")
        self.assertFalse(decision.publication_allowed)
        self.assertIn("NOT_A_SAFETY_CERTIFICATION", decision.reason_codes[0])

    def test_legal_status_needs_official_record_scope_and_time(self):
        for field, code in (
            ("official_record_approved", "HOLD_HIGH_RISK_OFFICIAL_RECORD_REQUIRED"),
            ("jurisdiction_match", "HOLD_HIGH_RISK_JURISDICTION_MISMATCH"),
            ("effective_time_match", "HOLD_HIGH_RISK_EFFECTIVE_TIME_MISMATCH"),
        ):
            with self.subTest(field=field):
                decision = evaluate(**{field: False})
                self.assertFalse(decision.publication_allowed)
                self.assertIn(code, decision.reason_codes)

    def test_allegation_framing_cannot_be_normalized_into_product_fact(self):
        decision = evaluate(
            source_text="Secondo la procura, Rossi avrebbe commesso una frode.",
            normalized_text="Rossi ha commesso una frode.",
            legal_status_claim=False,
        )
        self.assertFalse(decision.publication_allowed)
        self.assertIn("HOLD_HIGH_RISK_ALLEGATION_FRAMING_LOST", decision.reason_codes)

    def test_wrong_person_and_privacy_hold_are_additive(self):
        decision = evaluate(
            identity_sensitive=True,
            sensitive_private=True,
            identity_resolved=False,
            privacy_allows=False,
        )
        self.assertIn(RiskClass.IDENTITY_SENSITIVE_ACCUSATION, decision.signals.risk_classes)
        self.assertIn(RiskClass.SENSITIVE_PRIVATE, decision.signals.risk_classes)
        self.assertIn("HOLD_HIGH_RISK_IDENTITY_UNRESOLVED", decision.reason_codes)
        self.assertIn("HOLD_HIGH_RISK_PRIVACY", decision.reason_codes)

    def test_minor_or_victim_marker_can_only_escalate(self):
        decision = evaluate(
            legal_status_claim=False,
            source_text="Una persona minorenne è coinvolta.",
            normalized_text="Una persona minorenne è coinvolta.",
            minor_victim_private_person=True,
            privacy_allows=False,
        )
        self.assertIn(RiskClass.MINOR_VICTIM_PRIVATE_PERSON, decision.signals.risk_classes)
        self.assertFalse(decision.publication_allowed)

    def test_qualified_policy_and_dual_control_are_mandatory_for_high_risk(self):
        missing_policy = evaluate(qualified_policy_accepted=False, policy_decision_ref=None)
        self.assertIn("HOLD_HIGH_RISK_QUALIFIED_POLICY_REQUIRED", missing_policy.reason_codes)
        self.assertIsNone(missing_policy.policy_decision_ref)
        missing_review = evaluate(human_review_approved=False)
        self.assertIn("HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED", missing_review.reason_codes)
        missing_dual = evaluate(dual_control_approved=False)
        self.assertIn("HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED", missing_dual.reason_codes)

    def test_conflicting_procedural_terms_fail_closed(self):
        decision = evaluate(
            source_text="Il testo lo descrive prima come indagato e poi condannato.",
            normalized_text="Rossi è condannato.",
        )
        self.assertIn("HOLD_HIGH_RISK_PROCEDURAL_STATUS_CONFLICT", decision.reason_codes)

    def test_only_fully_gated_candidate_becomes_eligible_high_risk(self):
        decision = evaluate()
        self.assertTrue(decision.publication_allowed)
        self.assertEqual(decision.disposition, "ELIGIBLE_HIGH_RISK")
        self.assertEqual(decision.policy_decision_ref, "decision:dp307:legal-status-v1")
        self.assertFalse(hasattr(decision, "score"))


if __name__ == "__main__":
    unittest.main()
