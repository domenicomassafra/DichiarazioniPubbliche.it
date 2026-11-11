"""Exact-model subscription policy tests for DP-413 operations."""

import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from dichiarazioni_pubbliche.autonomous_publication import (
    AutonomousProofPacket, candidate_fingerprint,
)
from tests.test_autonomous_operations import (
    Capture, Challenge, Journal, NOW, Reviewer, Surface, fixture_execution_witness,
)
from tests.test_autonomous_publication import candidate

class SubscriptionOperationsTests(unittest.TestCase):

    def test_same_approved_model_holds_before_any_provider_calls(self):
        from dichiarazioni_pubbliche.autonomous_publication import APPROVED_REVIEW_MODELS
        approved = next(iter(APPROVED_REVIEW_MODELS))
        first = Reviewer("agent:first", approved)
        second = Reviewer("agent:independent", approved)
        surface, journal = Surface(), Journal()
        ops = AutonomousOperations(
            capture=Capture(replace(candidate(), uncertainty_reasons=("CONFLICT",))),
            challenge=Challenge(), first=first, second=second,
            public_surface=surface, journal=journal,
        )
        result = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", result.reason_codes)
        self.assertEqual((first.calls, second.calls), (0, 0))
        self.assertFalse(surface.visible)

    def test_owner_gemini_38_only_and_uncertain_records_hold_before_calls(self):
        from dichiarazioni_pubbliche.autonomous_publication import APPROVED_REVIEW_MODELS

        primary_model = "antigravity/gemini-3.8-flash-tiered"
        second_model = "antigravity/gemini-3-flash"
        audit_model = "antigravity/gemini-2.5-pro"
        self.assertEqual(
            APPROVED_REVIEW_MODELS, frozenset({primary_model})
        )
        capture, challenge = Capture(), Challenge()
        first = Reviewer("agent:first", primary_model)
        second = Reviewer("agent:independent", second_model)
        auditor = Reviewer("agent:nightly", audit_model)
        surface = Surface()
        ops = AutonomousOperations(
            capture=capture, challenge=challenge, first=first, second=second,
            public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        receipt = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(receipt.disposition, "PUBLISH")
        self.assertEqual((first.calls, second.calls), (1, 0))
        capture.item = replace(capture.item, uncertainty_reasons=("UNRESOLVED",))
        hold = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(hold.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", hold.reason_codes)
        self.assertEqual((first.calls, second.calls, auditor.calls), (1, 0, 0))
        self.assertFalse(surface.visible)

    def test_invalid_models_hold_before_provider_calls(self):
        for unapproved in (
            "antigravity/gemini-3-flash",
            "antigravity/gemini-2.5-pro",
            "antigravity/gemini-3.8-flash-low",
            "antigravity/gemini-3.8-flash-medium",
            "antigravity/gemini-3.8-flash-high",
            "antigravity/gemini-3.7-flash",
            "antigravity/gemini-3.1-pro",
            "openrouter/gemini-3-flash",
            "kilocode/google/gemini-2.5-pro",
            "antigravity/gemini-3-flash-preview",
            " ANTIGRAVITY/GEMINI-3-FLASH ",
            "antigravity/gemini-3-flash ",
            "ANTIGRAVITY/GEMINI-2.5-PRO",
            "\tantigravity/gemini-2.5-pro",
        ):
            with self.subTest(unapproved=unapproved):
                first = Reviewer("agent:first", "antigravity/gemini-3.8-flash-tiered")
                second = Reviewer("agent:independent", unapproved)
                ops = AutonomousOperations(
                    capture=Capture(replace(candidate(), uncertainty_reasons=("CONFLICT",))),
                    challenge=Challenge(), first=first, second=second,
                    public_surface=Surface(), journal=Journal(),
                )
                result = ops.evaluate_and_apply("finding:413", now=NOW)
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn("INDEPENDENT_REVIEW", result.reason_codes)
                self.assertEqual((first.calls, second.calls), (0, 0))

    def test_third_audit_model_alias_withdraws_without_calling_provider(self):
        capture = Capture()
        first = Reviewer("agent:first", "antigravity/gemini-3.8-flash-tiered")
        second = Reviewer("agent:independent", "antigravity/gemini-3-flash")
        auditor = Reviewer("agent:nightly", " ANTIGRAVITY/GEMINI-2.5-PRO ")
        surface = Surface()
        ops = AutonomousOperations(
            capture=capture, challenge=Challenge(), first=first, second=second,
            public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        self.assertEqual(
            ops.evaluate_and_apply("finding:413", now=NOW).disposition, "PUBLISH"
        )
        fingerprint = candidate_fingerprint(capture.item)
        packet = AutonomousProofPacket(
            capture.item, first.review(capture.item, fingerprint),
            second.review(capture.item, fingerprint),
        )
        result = ops.audit_and_apply(packet, auditor, now=NOW)
        self.assertEqual(result.disposition, "AUDIT_HOLD")
        self.assertEqual(result.reason_codes, ("THIRD_REVIEW_FAILED",))
        self.assertEqual(auditor.calls, 0)
        self.assertFalse(surface.visible)

    def test_fake_second_provider_holds_before_any_provider_calls(self):
        first = Reviewer("agent:first", "antigravity/gemini-3.8-flash-tiered")
        second = Reviewer("agent:independent", "local:unapproved-model")
        ops = AutonomousOperations(
            capture=Capture(replace(candidate(), uncertainty_reasons=("CONFLICT",))),
            challenge=Challenge(), first=first, second=second,
            public_surface=Surface(), journal=Journal(),
        )
        result = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", result.reason_codes)
        self.assertEqual((first.calls, second.calls), (0, 0))
if __name__ == "__main__":
    unittest.main()
