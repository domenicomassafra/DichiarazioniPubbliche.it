"""DP-314 synthetic preflight only; no real evidence truth/gold or publication."""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementClaim, RequirementEvidence, preflight_verification_requirements,
    select_requirement_profile,
)


def claim(kind="EVENT_SEQUENCE", **kwargs):
    return replace(RequirementClaim(
        "claim:synthetic", kind, "2025-06-01", "jurisdiction:it", "a" * 64,
        "policy:test:v1", "2025-07-01", "COMPLETED",
    ), **kwargs)


def record(name, role, root, *, sha=None, **kwargs):
    return replace(RequirementEvidence(
        "evidence:" + name, sha or (name[0] * 64), root, "source:" + root,
        "locator:" + name, role, "2025-05-25", "jurisdiction:it",
        "SUPPORT", "APPROVED", "APPROVED",
    ), **kwargs)


def sources():
    return (record("alpha", "PRIMARY_RECORD", "root:a"),
            record("beta", "INDEPENDENT_RECORD", "root:b"))


class RequirementPreflightTests(unittest.TestCase):
    def test_registry_is_explicit_not_universal(self):
        for kind in ("EVENT_SEQUENCE", "DOCUMENTARY_LEGAL_STATUS", "FACTUAL_DENIAL",
                     "NUMERIC", "FACTUAL_TEXT_COMPARISON"):
            self.assertIsNotNone(select_requirement_profile(kind))
        self.assertIsNone(select_requirement_profile("GENERIC_LLM_TRUE"))

    def test_no_run_attempted_insufficient_and_non_factual_are_distinct(self):
        self.assertEqual(preflight_verification_requirements(claim(run_state="NOT_STARTED"), ()).state, "NOT_CHECKED")
        self.assertEqual(preflight_verification_requirements(claim(), ()).state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(preflight_verification_requirements(claim("NON_FACTUAL"), ()).state, "NON_FACTUAL")
        self.assertEqual(preflight_verification_requirements(claim("MAGIC_LLM"), ()).state, "NOT_CHECKABLE_PROFILE_UNAVAILABLE")

    def test_two_declared_independent_roles_only_propose_checkable_pending(self):
        result = preflight_verification_requirements(claim(), sources())
        self.assertEqual(result.state, "CHECKABLE_PENDING")
        self.assertEqual(result.observed_independent_roots, 2)
        self.assertEqual(len(result.eligible_evidence_ids), 2)
        self.assertIsNone(result.verdict)
        self.assertFalse(result.finding_authority)
        self.assertFalse(result.publication_authority)

    def test_one_article_and_derivative_copy_cannot_form_independent_roots(self):
        first, second = sources()
        copied = replace(second, primary_root_ref=first.primary_root_ref)
        result = preflight_verification_requirements(claim(), (first, copied))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("INDEPENDENT_ORIGINAL_ROOT_MISSING", result.reason_codes)
        copied = replace(second, evidence_sha256=first.evidence_sha256)
        result = preflight_verification_requirements(claim(), (first, copied))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("CROSS_ROOT_IDENTICAL_BYTES", result.reason_codes)

    def test_unapproved_rights_and_reviewer_status_stay_excluded(self):
        first, second = sources()
        for change in (dict(source_use_status="REVOKED"), dict(evidence_review_status="PENDING"),
                       dict(evidence_review_status="REVOKED")):
            row = replace(second, **change)
            outcome = preflight_verification_requirements(claim(), (first, row))
            self.assertEqual(outcome.state, "CHECKED_INSUFFICIENT_EVIDENCE")
            self.assertIn("EVIDENCE_OR_RIGHTS_NOT_APPROVED", outcome.reason_codes)

    def test_later_version_later_evidence_and_wrong_jurisdiction_not_retroactive(self):
        first, second = sources()
        for change, code in (
            (dict(published_date="2025-08-01"), "POST_STATEMENT_EVIDENCE_ONLY"),
            (dict(jurisdiction_ref="jurisdiction:de"), "JURISDICTION_MISMATCH"),
        ):
            outcome = preflight_verification_requirements(claim(), (first, replace(second, **change)))
            self.assertEqual(outcome.state, "CHECKED_INSUFFICIENT_EVIDENCE")
            self.assertIn(code, outcome.reason_codes)

    def test_conflicting_support_refute_is_not_truth(self):
        first, second = sources()
        result = preflight_verification_requirements(claim(), (first, replace(second, stance="REFUTE")))
        self.assertEqual(result.state, "UNRESOLVED_CONFLICT")
        self.assertIn("CONTRADICTORY_REVIEWED_OBSERVATIONS", result.reason_codes)
        self.assertIsNone(result.verdict)

    def test_profiles_do_not_use_incorrect_roles_as_sufficient(self):
        for kind, role in (("DOCUMENTARY_LEGAL_STATUS", "PRIMARY_LEGAL_RECORD"),
                           ("NUMERIC", "PRIMARY_STATISTICS"),
                           ("FACTUAL_TEXT_COMPARISON", "PRIMARY_TEXT")):
            with self.subTest(kind=kind):
                good = record("alpha", role, "root:a")
                self.assertEqual(preflight_verification_requirements(claim(kind), (good,)).state,
                                 "CHECKABLE_PENDING")
                self.assertEqual(preflight_verification_requirements(claim(kind), (sources()[0],)).state,
                                 "CHECKED_INSUFFICIENT_EVIDENCE")

    def test_same_inputs_replay_hash_independent_of_order_but_policy_changes_hash(self):
        original = preflight_verification_requirements(claim(), sources())
        reversed_order = preflight_verification_requirements(claim(), tuple(reversed(sources())))
        self.assertEqual(original.snapshot_sha256, reversed_order.snapshot_sha256)
        changed = preflight_verification_requirements(claim(policy_version="policy:test:v2"), sources())
        self.assertNotEqual(original.snapshot_sha256, changed.snapshot_sha256)

    def test_malformed_input_duplicate_ids_and_bad_evidence_sha_fail_closed(self):
        first, second = sources()
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            preflight_verification_requirements(claim(), (first, first))
        with self.assertRaisesRegex(ValueError, "SHA_INVALID"):
            preflight_verification_requirements(claim(), (first, replace(second, evidence_sha256="bad")))
        with self.assertRaisesRegex(ValueError, "INPUT_INVALID"):
            preflight_verification_requirements(claim(), (first,) * 129)
        with self.assertRaisesRegex(ValueError, "RUN_INPUT_INVALID"):
            preflight_verification_requirements(claim(review_cutoff_date="2024-01-01"), ())


if __name__ == "__main__":
    unittest.main()
