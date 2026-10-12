"""DP-314 independent missing-jurisdiction and unsupported-class regressions.

All records are controlled offline evidence declarations, not trusted sources.
"""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementClaim,
    RequirementEvidence,
    preflight_verification_requirements,
)


class GeneralVerificationRequirementsWaveCloseTests(unittest.TestCase):
    def setUp(self):
        self.claim = RequirementClaim(
            claim_id="claim:law-status",
            claim_kind="DOCUMENTARY_LEGAL_STATUS",
            statement_date="2025-06-01",
            jurisdiction_ref="jurisdiction:it",
            proposition_sha256="a" * 64,
            policy_version="policy:2025:v1",
            review_cutoff_date="2025-07-01",
            run_state="COMPLETED",
        )
        self.legal_record = RequirementEvidence(
            evidence_id="evidence:legal-record",
            evidence_sha256="b" * 64,
            primary_root_ref="root:legal-gazette",
            source_family_ref="family:legal-gazette",
            locator_ref="locator:law-123",
            evidence_role="PRIMARY_LEGAL_RECORD",
            published_date="2025-05-15",
            jurisdiction_ref="jurisdiction:it",
            stance="SUPPORT",
            source_use_status="APPROVED",
            evidence_review_status="APPROVED",
        )

    def test_legal_claim_without_jurisdiction_cannot_be_checkable_with_foreign_record(self):
        # The recorded statement lacks a jurisdiction: a French gazette cannot
        # establish that an unspecified legal regime has the alleged rule.
        claim = replace(self.claim, jurisdiction_ref=None)
        french_law = replace(self.legal_record, jurisdiction_ref="jurisdiction:fr")
        result = preflight_verification_requirements(claim, (french_law,))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("LEGAL_JURISDICTION_UNSPECIFIED", result.reason_codes)
        self.assertEqual(result.eligible_evidence_ids, ())
        self.assertIsNone(result.verdict)

    def test_legal_claim_without_jurisdiction_cannot_use_unspecified_record_scope(self):
        claim = replace(self.claim, jurisdiction_ref=None)
        unspecific_law = replace(self.legal_record, jurisdiction_ref=None)
        result = preflight_verification_requirements(claim, (unspecific_law,))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("LEGAL_JURISDICTION_UNSPECIFIED", result.reason_codes)

    def test_specific_legal_claim_with_matching_jurisdiction_retains_private_preflight(self):
        result = preflight_verification_requirements(self.claim, (self.legal_record,))
        self.assertEqual(result.state, "CHECKABLE_PENDING")
        self.assertEqual(result.eligible_evidence_ids, (self.legal_record.evidence_id,))
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.finding_authority)

    def test_unimplemented_claim_class_is_explicitly_unavailable_even_before_run(self):
        unsupported = replace(self.claim, claim_kind="CAUSAL_ASSERTION", run_state="NOT_STARTED")
        result = preflight_verification_requirements(unsupported, ())
        self.assertEqual(result.state, "NOT_CHECKABLE_PROFILE_UNAVAILABLE")
        self.assertIsNone(result.verdict)
        self.assertFalse(result.publication_authority)

    def test_unimplemented_claim_cannot_label_approved_rows_eligible(self):
        unsupported = replace(self.claim, claim_kind="CAUSAL_ASSERTION")
        result = preflight_verification_requirements(
            unsupported, (self.legal_record,)
        )
        self.assertEqual(result.state, "NOT_CHECKABLE_PROFILE_UNAVAILABLE")
        self.assertEqual(result.eligible_evidence_ids, ())
        self.assertEqual(result.excluded_evidence_ids, (self.legal_record.evidence_id,))
        self.assertIn("PROFILE_UNAVAILABLE", result.reason_codes)

    def test_supported_not_started_class_remains_not_checked(self):
        claim = replace(self.claim, run_state="NOT_STARTED")
        result = preflight_verification_requirements(claim, ())
        self.assertEqual(result.state, "NOT_CHECKED")

    def test_non_factual_opinion_preserves_distinct_state_without_evidence_eligibility(self):
        non_factual = replace(self.claim, claim_kind="NON_FACTUAL")
        result = preflight_verification_requirements(
            non_factual, (self.legal_record,)
        )
        self.assertEqual(result.state, "NON_FACTUAL")
        self.assertEqual(result.eligible_evidence_ids, ())
        self.assertIn("NON_FACTUAL_EVIDENCE_NOT_APPLICABLE", result.reason_codes)

    def test_non_factual_untouched_run_keeps_no_completed_check_state(self):
        result = preflight_verification_requirements(
            replace(self.claim, claim_kind="NON_FACTUAL", run_state="NOT_STARTED"), ()
        )
        self.assertEqual(result.state, "NOT_CHECKED")


if __name__ == "__main__":
    unittest.main()
