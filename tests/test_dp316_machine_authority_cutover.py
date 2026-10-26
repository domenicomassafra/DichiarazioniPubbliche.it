from __future__ import annotations

import unittest

from dichiarazioni_pubbliche.machine_authority_cutover_v1 import (
    VERSION,
    evaluate_machine_authority_cutover,
)
from dichiarazioni_pubbliche.machine_authority_signed_v1 import SignedAuthorityVerdict
from dichiarazioni_pubbliche.publication_eligibility import (
    PUBLICATION_ELIGIBILITY_VERSION,
    PublicationEligibilityResult,
)
from dichiarazioni_pubbliche.publication_review_control import ReviewRiskClass
from dichiarazioni_pubbliche.production_projection_revalidation import (
    ProductionProjectionRevalidator,
)


class MachineAuthorityCutoverTests(unittest.TestCase):
    def setUp(self):
        self.record_id = "claim:fixture"
        self.record_version = "record-v3"
        self.machine_policy_version = "dp316-policy-fixture-v1"
        self.legacy = PublicationEligibilityResult(
            disposition="ELIGIBLE_FOR_PROJECTION_REVALIDATION",
            blockers=(),
            safety_binding_sha256="a" * 64,
            high_risk_binding_sha256="b" * 64,
            review_policy_version="dp310-review-v1",
            review_risk_class=ReviewRiskClass.LEGAL,
            counted_review_event_ids=("review:primary", "review:independent"),
            binding_sha256="c" * 64,
            profile_version=PUBLICATION_ELIGIBILITY_VERSION,
            record_id=self.record_id,
            record_version=self.record_version,
        )
        self.machine = SignedAuthorityVerdict(
            "PRIVATE_SIGNATURE_VERIFIED", (), True, True,
            self.record_id, self.record_version, "d" * 64,
            self.machine_policy_version,
        )

    def evaluate(self, **changes):
        arguments = {
            "mode": "LEGACY_ONLY",
            "record_id": self.record_id,
            "record_version": self.record_version,
            "legacy_result": self.legacy,
            "machine_result": self.machine,
            "machine_policy_version": self.machine_policy_version,
        }
        arguments.update(changes)
        return evaluate_machine_authority_cutover(**arguments)

    def test_production_revalidator_defaults_to_legacy_only_without_machine_loader(self):
        revalidator = ProductionProjectionRevalidator(
            None, reviewer_authority_root=None,
        )
        self.assertEqual(revalidator._machine_authority_gate.mode, "LEGACY_ONLY")
        self.assertIsNone(revalidator._machine_authority_gate.verifier)

    def test_legacy_mode_preserves_the_existing_eligible_path_and_ignores_machine(self):
        result = self.evaluate()
        self.assertEqual(result.version, VERSION)
        self.assertEqual(result.disposition, "LEGACY_ELIGIBLE")
        self.assertEqual(result.selected_path, "LEGACY")
        self.assertFalse(result.publication_authority)

    def test_dual_read_is_shadow_only_and_never_changes_the_legacy_path(self):
        result = self.evaluate(mode="DUAL_READ")
        self.assertEqual(result.disposition, "LEGACY_ELIGIBLE_SHADOW_HOLD")
        self.assertEqual(result.selected_path, "LEGACY")
        self.assertIn("DP316_MACHINE_SIGNOFF_UNAVAILABLE", result.reason_codes)
        self.assertFalse(result.publication_authority)

    def test_missing_machine_receipt_is_a_shadow_hold_not_a_legacy_block(self):
        result = self.evaluate(mode="DUAL_READ", machine_result=None)
        self.assertEqual(result.disposition, "LEGACY_ELIGIBLE_SHADOW_HOLD")
        self.assertEqual(result.selected_path, "LEGACY")
        self.assertFalse(result.publication_authority)

    def test_machine_signoff_cannot_be_set_by_constructing_a_verdict(self):
        forged = SignedAuthorityVerdict(
            "MACHINE_SIGNED", (), True, True,
            self.record_id, self.record_version, "d" * 64,
            self.machine_policy_version,
        )
        self.assertFalse(forged.machine_signoff)
        self.assertFalse(forged.publication_authority)

    def test_machine_only_never_falls_back_to_a_legacy_review_event(self):
        result = self.evaluate(mode="MACHINE_V1")
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.selected_path, "NONE")
        self.assertIn("DP316_MACHINE_SIGNOFF_UNAVAILABLE", result.reason_codes)
        self.assertFalse(result.publication_authority)

    def test_explicit_rollback_selects_only_the_legacy_path(self):
        result = self.evaluate(
            mode="LEGACY_ONLY",
            rollback_from_mode="MACHINE_V1",
            rollback_ref="rollback:issue-494-v1",
        )
        self.assertEqual(result.disposition, "LEGACY_ROLLBACK_ELIGIBLE")
        self.assertEqual(result.selected_path, "LEGACY")
        self.assertEqual(result.rollback_ref, "rollback:issue-494-v1")
        self.assertFalse(result.publication_authority)

    def test_record_version_or_policy_mismatch_holds_machine_path(self):
        stale_record = SignedAuthorityVerdict(
            "PRIVATE_SIGNATURE_VERIFIED", (), True, True,
            self.record_id, "record-v2", "d" * 64,
            self.machine_policy_version,
        )
        result = self.evaluate(mode="MACHINE_V1", machine_result=stale_record)
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.selected_path, "NONE")

        stale_policy = SignedAuthorityVerdict(
            "PRIVATE_SIGNATURE_VERIFIED", (), True, True,
            self.record_id, self.record_version, "d" * 64,
            "dp316-policy-stale",
        )
        result = self.evaluate(mode="DUAL_READ", machine_result=stale_policy)
        self.assertEqual(result.disposition, "LEGACY_ELIGIBLE_SHADOW_HOLD")
        self.assertEqual(result.selected_path, "LEGACY")

    def test_invalid_mode_and_unbound_legacy_result_hold(self):
        result = self.evaluate(mode="AUTO_PROMOTE")
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.selected_path, "NONE")
        result = self.evaluate(mode=[])
        self.assertEqual(result.disposition, "HOLD")
        result = self.evaluate(rollback_from_mode=[])
        self.assertEqual(result.disposition, "HOLD")

        result = self.evaluate(
            legacy_result=PublicationEligibilityResult(
                disposition="ELIGIBLE_FOR_PROJECTION_REVALIDATION",
                blockers=(),
                safety_binding_sha256="a" * 64,
                high_risk_binding_sha256="b" * 64,
                review_policy_version="dp310-review-v1",
                review_risk_class=ReviewRiskClass.LEGAL,
                counted_review_event_ids=("review:primary",),
                binding_sha256="c" * 64,
                record_id="claim:other",
                record_version=self.record_version,
            )
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.selected_path, "NONE")


if __name__ == "__main__":
    unittest.main()
