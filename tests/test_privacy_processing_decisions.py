"""DP-304 release decisions: no presumed basis, period or sensitive clearance."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.privacy_processing_decisions import (  # noqa: E402
    PROCESSING_FAMILIES,
    evaluate_processing_decisions,
    repository_processing_decisions,
)
from dichiarazioni_pubbliche.launch_preflight import (  # noqa: E402
    CONDITIONAL_SURFACE_TICKETS,
    REQUIRED_LEGAL_QUESTIONS,
    REQUIRED_RELEASE_ARTIFACTS,
    REQUIRED_TICKETS,
    evaluate_launch_preflight,
)

REGISTER = ROOT / "docs/policy/privacy-processing-decisions-v1.json"


class ProcessingDecisionsTests(unittest.TestCase):
    def setUp(self):
        self.register = json.loads(REGISTER.read_text(encoding="utf-8"))

    def test_real_register_holds_six_processing_families(self):
        blockers = repository_processing_decisions(ROOT)
        self.assertEqual(set(self.register["families"]), set(PROCESSING_FAMILIES))
        self.assertEqual(len(blockers), len(PROCESSING_FAMILIES) - 1)
        self.assertIn("PRIVACY_PURPOSE_NOT_APPROVED:PUBLIC_STATEMENTS", blockers)
        self.assertIn("PRIVACY_PURPOSE_NOT_APPROVED:BACKUPS", blockers)
        self.assertNotIn("PRIVACY_PURPOSE_NOT_APPROVED:OPTIONAL_ACCOUNTS", blockers)

    def test_incomplete_or_tampered_register_denied(self):
        for mutation, expected in (
            (lambda r: r["families"].pop("BACKUPS"), "PRIVACY_FAMILY_COVERAGE_INVALID"),
            (lambda r: r["families"]["PUBLIC_STATEMENTS"].update(purpose="OTHER"), "PRIVACY_FAMILY_SCHEMA_INVALID:PUBLIC_STATEMENTS"),
            (lambda r: r["special_handling"].update(minors_victims="ALLOW"), "PRIVACY_SPECIAL_HANDLING_NOT_FAIL_CLOSED"),
        ):
            with self.subTest(expected=expected):
                tampered = copy.deepcopy(self.register)
                mutation(tampered)
                self.assertIn(expected, evaluate_processing_decisions(tampered))

    def test_false_approval_requires_basis_receipts_and_owner_date(self):
        row = self.register["families"]["PUBLIC_STATEMENTS"]
        row["status"] = "APPROVED"
        blockers = evaluate_processing_decisions(self.register)
        self.assertIn("PRIVACY_LAWFUL_BASIS_MISSING:PUBLIC_STATEMENTS", blockers)
        self.assertIn("PRIVACY_EVIDENCE_MISSING:PUBLIC_STATEMENTS", blockers)
        self.assertIn("PRIVACY_OWNER_DATE_MISSING:PUBLIC_STATEMENTS", blockers)

    def test_malformed_receipt_and_non_scalar_basis_never_pass(self):
        row = self.register["families"]["PUBLIC_STATEMENTS"]
        row.update(
            status="APPROVED",
            lawful_basis={"invalid": "basis"},
            necessity_receipt="https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/garbage",
        )
        blockers = evaluate_processing_decisions(self.register)
        self.assertIn("PRIVACY_LAWFUL_BASIS_MISSING:PUBLIC_STATEMENTS", blockers)
        self.assertIn("PRIVACY_EVIDENCE_MISSING:PUBLIC_STATEMENTS", blockers)

    def test_all_dated_mechanical_receipts_can_only_reach_pending_owner(self):
        # Fake issue URLs are syntactically possible: neither these fixtures nor
        # the mechanical checker attest legal truth or grant publication.
        receipt = (
            "https://github.com/domenicomassafra/"
            "DichiarazioniPubbliche.it/issues/54#issuecomment-123456"
        )
        for family, row in self.register["families"].items():
            if family == "OPTIONAL_ACCOUNTS":
                continue
            row.update(
                status="APPROVED", lawful_basis="GDPR_ART_6_1_F",
                necessity_receipt=receipt, notice_receipt=receipt,
                retention_receipt=receipt, access_receipt=receipt,
                owner_decision_url=receipt, owner_decision_date="2026-10-20",
            )
        self.assertEqual(evaluate_processing_decisions(self.register), ())
        plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
        plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={q: "DECIDED" for q in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={artifact: True for artifact in REQUIRED_RELEASE_ARTIFACTS},
            privacy_decision_blockers=evaluate_processing_decisions(self.register),
        )
        self.assertEqual(result.disposition, "PENDING-OWNER")
        self.assertFalse(result.launchable)

    def test_optional_accounts_exclusion_fails_if_activation_switches(self):
        self.assertEqual(
            evaluate_processing_decisions(self.register, account_activation_approved=False),
            repository_processing_decisions(ROOT),
        )
        self.assertIn(
            "PRIVACY_EXCLUDED_ACCOUNT_ACTIVATION_CONFLICT",
            evaluate_processing_decisions(self.register, account_activation_approved=True),
        )

    def test_missing_or_duplicate_register_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                repository_processing_decisions(root),
                ("PRIVACY_PROCESSING_REGISTER_OR_INVENTORY_UNAVAILABLE",),
            )
            policy = root / "docs/policy"
            policy.mkdir(parents=True)
            (root / "config").mkdir()
            (root / "config/privacy-field-inventory.v1.json").write_text(
                '{"account_sqlite_activation_approved": false}', encoding="utf-8"
            )
            (policy / "privacy-processing-decisions-v1.json").write_text(
                '{"version":"privacy-processing-decisions-v1",'
                '"version":"privacy-processing-decisions-v1"}', encoding="utf-8"
            )
            self.assertEqual(
                repository_processing_decisions(root),
                ("PRIVACY_PROCESSING_REGISTER_OR_INVENTORY_UNAVAILABLE",),
            )

    def test_full_preflight_carries_real_privacy_blockers_in_receipt(self):
        plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
        plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={q: "DECIDED" for q in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={artifact: True for artifact in REQUIRED_RELEASE_ARTIFACTS},
            privacy_decision_blockers=repository_processing_decisions(ROOT),
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertFalse(result.launchable)
        self.assertIn("PRIVACY_PURPOSE_NOT_APPROVED:OPERATIONAL_LOGS", result.blockers)
        self.assertEqual(result.privacy_blockers, repository_processing_decisions(ROOT))


if __name__ == "__main__":
    unittest.main()
