"""DP-316 source-only negative machine signoff contract; synthetic data only."""

from __future__ import annotations

import sqlite3
import hashlib
import json
import sys
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    HighRiskDecision,
    HighRiskSignals,
    RiskClass,
)
from dichiarazioni_pubbliche.machine_authority_preflight_v1 import (  # noqa: E402
    MACHINE_MATERIAL_ROLES,
    MachineAuthorityProfile,
    MachineAuthoritySnapshot,
    MachineDecisionReference,
    MaterialBinding,
    preflight_machine_authority,
)
from dichiarazioni_pubbliche.publication_safety import (  # noqa: E402
    PublicationSafetyResult,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    high_risk_binding_sha256,
)
from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    IsolatedPublicationEpochStore,
)
from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementPreflight,
    VERSION as REQUIREMENT_VERSION,
)


def digest(c):
    return c * 64


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class MachineAuthorityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.store = IsolatedPublicationEpochStore(self.conn)
        self.store.init_fixture_schema()
        self.profile = MachineAuthorityProfile(
            profile_ref="profile:synthetic",
            profile_version="machine-profile:v1",
            claim_kind="EVENT_SEQUENCE",
            risk_class="STANDARD",
            jurisdiction_ref="it",
            policy_version="policy:v1",
            requirement_rule_version=REQUIREMENT_VERSION,
        )
        self.risk = HighRiskDecision(
            "STANDARD_REVIEW", (), HighRiskSignals((), (), False), None
        )
        self.materials = tuple(
            MaterialBinding(role, f"dep:{role.lower()}", f"{i + 1:064x}", 0)
            for i, role in enumerate(MACHINE_MATERIAL_ROLES)
        )
        profile_digest = fingerprint(asdict(self.profile))
        risk_digest = high_risk_binding_sha256(
            self.risk,
            input_binding_sha256=next(
                item.sha256 for item in self.materials if item.role == "HIGH_RISK_INPUT"
            ),
        )
        self.materials = tuple(
            replace(item, sha256=profile_digest)
            if item.role == "MACHINE_PROFILE"
            else replace(item, sha256=risk_digest)
            if item.role == "HIGH_RISK_RESULT"
            else item
            for item in self.materials
        )
        for item in self.materials:
            self.store.register_fixture_source(item.ref, item.sha256)
        self.ticket = self.store.mint(
            release_id="release:synthetic",
            dependency_ids=tuple(item.ref for item in self.materials),
        )
        self.decision = MachineDecisionReference(
            record_id="claim:synthetic",
            record_version="revision:1",
            release_ref="release:synthetic",
            claim_kind="EVENT_SEQUENCE",
            risk_class="STANDARD",
            jurisdiction_ref="it",
            policy_version="policy:v1",
            generator_run_ref="run:producer",
            generator_identity_ref="model:producer",
            generator_source_root_ref="root:producer",
            challenger_run_ref="run:challenger",
            challenger_identity_ref="model:challenger",
            challenger_source_root_ref="root:challenger",
            rights_state="CURRENT",
            correction_state="CLEAR",
            challenger_state="COMPLETED",
        )
        self.requirement = RequirementPreflight(
            REQUIREMENT_VERSION,
            "claim:synthetic",
            "CHECKABLE_PENDING",
            (),
            ("PRIMARY_RECORD", "INDEPENDENT_RECORD"),
            ("evidence:1", "evidence:2"),
            (),
            2,
            self.role("REQUIREMENT_RESULT").sha256,
        )
        self.safety = PublicationSafetyResult(
            disposition="ELIGIBLE",
            reason_codes=(),
            required_proofs=("source_identity", "rights"),
            binding_sha256=self.role("SAFETY_RESULT").sha256,
        )

    def snapshot_with_risk(self, risk, profile, decision):
        risk_digest = high_risk_binding_sha256(
            risk, input_binding_sha256=self.role("HIGH_RISK_INPUT").sha256
        )
        materials = tuple(
            replace(item, sha256=fingerprint(asdict(profile)))
            if item.role == "MACHINE_PROFILE"
            else replace(item, sha256=risk_digest)
            if item.role == "HIGH_RISK_RESULT"
            else item
            for item in self.materials
        )
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        store = IsolatedPublicationEpochStore(conn)
        store.init_fixture_schema()
        for item in materials:
            store.register_fixture_source(item.ref, item.sha256)
        ticket = store.mint(
            release_id=decision.release_ref,
            dependency_ids=tuple(item.ref for item in materials),
        )
        return self.snapshot(
            profile=profile, decision=decision, materials=materials, fence=ticket
        )

    def role(self, name):
        return next(item for item in self.materials if item.role == name)

    def snapshot(self, **kwargs):
        return MachineAuthoritySnapshot(
            profile=kwargs.pop("profile", self.profile),
            decision=kwargs.pop("decision", self.decision),
            materials=kwargs.pop("materials", self.materials),
            fence=kwargs.pop("fence", self.ticket),
            **kwargs,
        )

    def evaluate(
        self, *, sealed=None, current=None, requirement=None, safety=None, risk=None
    ):
        return preflight_machine_authority(
            sealed or self.snapshot(),
            current or self.snapshot(),
            requirement=requirement or self.requirement,
            publication_safety=safety or self.safety,
            high_risk=risk or self.risk,
        )

    def test_positive_shaped_local_inputs_never_issue_authority(self):
        result = self.evaluate()
        self.assertEqual(result.disposition, "NEEDS_EXTERNAL_DECISION")
        self.assertIn("OFF_DB_MACHINE_AUTHORITY_UNAVAILABLE", result.reason_codes)
        self.assertIn("CRYPTOGRAPHIC_ATTESTATION_UNVERIFIED", result.reason_codes)
        self.assertIn("INDEPENDENT_GOLD_UNATTESTED", result.reason_codes)
        self.assertFalse(result.machine_signoff)
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.dispatch_authorized)
        self.assertEqual(len(result.snapshot_sha256), 64)
        self.assertEqual(result.snapshot_sha256, self.evaluate().snapshot_sha256)

    def test_forged_caller_approval_never_grants_signoff(self):
        forged = self.snapshot(
            decision=replace(self.decision, claimed_machine_approval=True)
        )
        outcome = self.evaluate(sealed=forged, current=forged)
        self.assertEqual(outcome.disposition, "HOLD")
        self.assertIn("CALLER_SIGNOFF_CLAIM_UNTRUSTED", outcome.reason_codes)
        self.assertFalse(outcome.machine_signoff)
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            outcome.machine_signoff = True
        self.assertFalse(replace(outcome, disposition="ELIGIBLE").machine_signoff)

    def test_two_answers_from_one_generator_are_not_independent_challengers(self):
        for change in (
            {"challenger_identity_ref": self.decision.generator_identity_ref},
            {"challenger_run_ref": self.decision.generator_run_ref},
            {"challenger_source_root_ref": self.decision.generator_source_root_ref},
        ):
            with self.subTest(change=change):
                fake = self.snapshot(decision=replace(self.decision, **change))
                result = self.evaluate(sealed=fake, current=fake)
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn("CHALLENGER_NOT_INDEPENDENT", result.reason_codes)

    def test_profile_or_policy_version_drift_rechecks(self):
        for current in (
            self.snapshot(
                profile=replace(self.profile, profile_version="machine-profile:v2")
            ),
            self.snapshot(
                profile=replace(self.profile, policy_version="policy:v2"),
                decision=replace(self.decision, policy_version="policy:v2"),
            ),
        ):
            with self.subTest(current=current):
                result = self.evaluate(current=current)
                self.assertEqual(result.disposition, "RECHECK")
                self.assertIn("CURRENT_PROFILE_OR_POLICY_CHANGED", result.reason_codes)

    def test_material_drift_rights_correction_and_model_invalidate(self):
        for role in (
            "SOURCE_RIGHTS",
            "CORRECTION_HEAD",
            "MODEL",
            "PROMPT",
            "EVIDENCE_SET",
            "CHALLENGER_PACKET",
            "GOLD_GATE",
        ):
            with self.subTest(role=role):
                updated = tuple(
                    replace(row, sha256=digest("f")) if row.role == role else row
                    for row in self.materials
                )
                result = self.evaluate(current=self.snapshot(materials=updated))
                self.assertEqual(result.disposition, "RECHECK")
                self.assertIn("MATERIAL_CURRENTNESS_CHANGED", result.reason_codes)

    def test_rights_revoked_or_correction_pending_remains_hold_even_if_all_hashes_match(
        self,
    ):
        for change, expected in (
            ({"rights_state": "REVOKED"}, "RIGHTS_NOT_CURRENT"),
            ({"correction_state": "PENDING"}, "CORRECTION_OR_CHALLENGE_PENDING"),
            ({"challenger_state": "PENDING"}, "CHALLENGER_INCOMPLETE"),
        ):
            with self.subTest(change=change):
                changed = self.snapshot(decision=replace(self.decision, **change))
                result = self.evaluate(sealed=changed, current=changed)
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn(expected, result.reason_codes)

    def test_revoked_fence_and_changed_epoch_are_not_reusable(self):
        self.store.revoke(
            source_id=self.role("SOURCE_RIGHTS").ref,
            event_id="event:revoked",
            reason="RIGHTS_WITHDRAWN",
            now=datetime(2026, 10, 11, tzinfo=timezone.utc),
        )
        current_material = tuple(
            replace(row, epoch=1) if row.role == "SOURCE_RIGHTS" else row
            for row in self.materials
        )
        result = self.evaluate(current=self.snapshot(materials=current_material))
        self.assertEqual(result.disposition, "RECHECK")
        self.assertIn("MATERIAL_CURRENTNESS_CHANGED", result.reason_codes)
        # Old fence itself cannot be reused as an independently checked current authority.
        self.assertFalse(result.publication_authority)

    def test_forged_fence_digest_and_missing_role_hold(self):
        altered = self.snapshot(fence=replace(self.ticket, fingerprint=digest("a")))
        result = self.evaluate(sealed=altered, current=altered)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("FENCE_INTEGRITY_INVALID", result.reason_codes)
        missing = self.snapshot(materials=self.materials[:-1])
        result = self.evaluate(sealed=missing, current=missing)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("REQUIRED_MATERIAL_ROLE_MISSING", result.reason_codes)

    def test_other_record_release_cannot_replay_a_structurally_valid_fence(self):
        forged = self.snapshot(
            decision=replace(self.decision, release_ref="release:other")
        )
        result = self.evaluate(sealed=forged, current=forged)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("FENCE_INTEGRITY_INVALID", result.reason_codes)

    def test_rebuilt_profile_and_high_risk_receipt_have_explicit_material_bindings(
        self,
    ):
        fake_profile = self.snapshot(
            profile=replace(self.profile, profile_version="machine-profile:forged")
        )
        result = self.evaluate(sealed=fake_profile, current=fake_profile)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("MACHINE_PROFILE_BINDING_MISMATCH", result.reason_codes)
        altered_risk = replace(self.risk, reason_codes=("caller:SIGNATURE:VALID",))
        result = self.evaluate(risk=altered_risk)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("HIGH_RISK_BINDING_MISMATCH", result.reason_codes)

    def test_badly_shaped_snapshot_does_not_throw_or_assume_good_inputs(self):
        for proposal in (
            None,
            self.snapshot(materials=("not-a-material",)),
            self.snapshot(fence=replace(self.ticket, dependencies=("not-an-epoch",))),
            self.snapshot(
                profile=replace(self.profile, requirement_rule_version="unknown")
            ),
        ):
            with self.subTest(proposal=repr(proposal)[:50]):
                result = (
                    self.evaluate(sealed=proposal)
                    if proposal is not None
                    else preflight_machine_authority(
                        None,
                        self.snapshot(),
                        requirement=self.requirement,
                        publication_safety=self.safety,
                        high_risk=self.risk,
                    )
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertFalse(result.machine_signoff)

    def test_requirement_and_publication_safety_do_not_grant_fact_verdict(self):
        insufficient = replace(self.requirement, state="CHECKED_INSUFFICIENT_EVIDENCE")
        result = self.evaluate(requirement=insufficient)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("UPSTREAM_VERIFICATION_NOT_CHECKABLE", result.reason_codes)
        blocked = replace(
            self.safety, disposition="POLICY_HOLD", reason_codes=("HOLD_RIGHTS",)
        )
        result = self.evaluate(safety=blocked)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("PUBLICATION_SAFETY_HELD", result.reason_codes)

    def test_high_risk_human_only_gate_cannot_be_recast_as_machine_review(self):
        profile = replace(self.profile, risk_class="LEGAL")
        decision = replace(self.decision, risk_class="LEGAL")
        risk = HighRiskDecision(
            "HOLD_HIGH_RISK",
            (
                "HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",
                "HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED",
            ),
            HighRiskSignals((RiskClass.LEGAL_STATUS,), (), False),
            self.role("QUALIFIED_POLICY").ref,
        )
        status = self.snapshot_with_risk(risk, profile, decision)
        outcome = self.evaluate(sealed=status, current=status, risk=risk)
        self.assertEqual(outcome.disposition, "NEEDS_EXTERNAL_DECISION")
        self.assertIn("LEGACY_HUMAN_REVIEW_NOT_MACHINE_SIGNOFF", outcome.reason_codes)
        other = replace(risk, reason_codes=("HOLD_HIGH_RISK_OFFICIAL_RECORD_REQUIRED",))
        held_status = self.snapshot_with_risk(other, profile, decision)
        outcome = self.evaluate(sealed=held_status, current=held_status, risk=other)
        self.assertEqual(outcome.disposition, "HOLD")
        self.assertIn("HIGH_RISK_UPSTREAM_HOLD", outcome.reason_codes)

    def test_legal_signal_cannot_be_downclassified_into_high_risk_profile(self):
        profile = replace(self.profile, risk_class="HIGH")
        decision = replace(self.decision, risk_class="HIGH")
        risk = HighRiskDecision(
            "HOLD_HIGH_RISK",
            ("HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",),
            HighRiskSignals((RiskClass.LEGAL_STATUS,), (), False),
            self.role("QUALIFIED_POLICY").ref,
        )
        case = self.snapshot_with_risk(risk, profile, decision)
        outcome = self.evaluate(sealed=case, current=case, risk=risk)
        self.assertEqual(outcome.disposition, "HOLD")
        self.assertIn("HIGH_RISK_PROFILE_MISMATCH", outcome.reason_codes)

    def test_no_unknown_material_or_wrong_claim_profile_can_be_silently_accepted(self):
        wrong = self.snapshot(profile=replace(self.profile, claim_kind="NUMERIC"))
        result = self.evaluate(sealed=wrong, current=wrong)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("PROFILE_CASE_MISMATCH", result.reason_codes)
        duplicate = self.snapshot(materials=self.materials + (self.materials[0],))
        result = self.evaluate(sealed=duplicate, current=duplicate)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("MATERIAL_ROLE_DUPLICATE", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
