"""Regression: the third auditor's returned model must match its exact issuer ID."""

from dataclasses import replace
import unittest

from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from dichiarazioni_pubbliche.autonomous_publication import (
    AutonomousProofPacket, candidate_fingerprint,
)
from tests.test_autonomous_operations import (
    Capture, Challenge, Journal, NOW, Reviewer, Surface, fixture_execution_witness,
)


class ThirdModelReceiptIdentityTests(unittest.TestCase):
    def test_auditor_cannot_return_noncanonical_alias_of_its_canonical_model(self):
        class WrongReceiptModel(Reviewer):
            def review(self, item, evidence_sha256):
                signed = super().review(item, evidence_sha256)
                return replace(signed, model_id=" ANTIGRAVITY/GEMINI-2.5-PRO ")

        capture = Capture()
        first = Reviewer("agent:first", "antigravity/gemini-3.8-flash-tiered")
        second = Reviewer("agent:independent", "antigravity/gemini-3-flash")
        third = WrongReceiptModel("agent:nightly", "antigravity/gemini-2.5-pro")
        surface = Surface()
        operations = AutonomousOperations(
            capture=capture, challenge=Challenge(), first=first, second=second,
            public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        self.assertEqual(
            operations.evaluate_and_apply("finding:413", now=NOW).disposition,
            "PUBLISH",
        )
        fingerprint = candidate_fingerprint(capture.item)
        packet = AutonomousProofPacket(
            capture.item, first.review(capture.item, fingerprint),
            second.review(capture.item, fingerprint),
        )
        result = operations.audit_and_apply(packet, third, now=NOW)
        self.assertEqual(result.disposition, "AUDIT_HOLD")
        self.assertEqual(result.reason_codes, ("THIRD_REVIEW_FAILED",))
        self.assertEqual(third.calls, 1)
        self.assertFalse(surface.visible)


if __name__ == "__main__":
    unittest.main()
