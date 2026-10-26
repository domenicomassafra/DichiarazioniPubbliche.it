"""DP-316 signed authority seam: exact, off-DB verifier, never a public grant."""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

import dichiarazioni_pubbliche.machine_authority_signed_v1 as signed_authority_module  # noqa: E402
from dichiarazioni_pubbliche.machine_authority_signed_v1 import (  # noqa: E402
    REGISTRY_VERSION, VERSION, verify_signed_authority,
)
from dichiarazioni_pubbliche.machine_authority_preflight_v1 import (  # noqa: E402
    MachineAuthorityPreflight, MachineAuthoritySnapshot, MachineAuthorityProfile,
    MachineDecisionReference, MaterialBinding, MACHINE_MATERIAL_ROLES,
)
from dichiarazioni_pubbliche.verification_requirements_v1 import VERSION as REQUIREMENT_VERSION  # noqa: E402
from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    MaterialEpoch, PublicationEpochTicket, VERSION as FENCE_VERSION,
)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except ImportError:
    Ed25519PrivateKey = None

NOW = datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc)


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sha(payload):
    return hashlib.sha256(canonical(payload)).hexdigest()


@unittest.skipUnless(Ed25519PrivateKey, "Optional cryptography Ed25519 backend unavailable")
class SignedAuthorityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.private = Ed25519PrivateKey.generate()
        self.key = self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.adjudicator_private = Ed25519PrivateKey.generate()
        self.adjudicator_key = self.adjudicator_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        ).hex()
        profile = MachineAuthorityProfile(
            "profile:one", "profile:v1", "EVENT_SEQUENCE", "STANDARD", "it",
            "policy:v1", REQUIREMENT_VERSION,
        )
        decision = MachineDecisionReference(
            "claim:fixture", "rev:1", "release:fixture", "EVENT_SEQUENCE", "STANDARD",
            "it", "policy:v1", "run:generator", "actor:generator", "root:generator",
            "run:challenger", "actor:challenger", "root:challenger",
            "CURRENT", "CLEAR", "COMPLETED",
        )
        materials = tuple(MaterialBinding(role, "dep:" + role, (i + 1).to_bytes(32, "big").hex(), 0) for i, role in enumerate(MACHINE_MATERIAL_ROLES))
        materials = tuple(replace(m, sha256=sha(asdict(profile))) if m.role == "MACHINE_PROFILE"
            else replace(m, sha256=sha(asdict(decision))) if m.role == "MACHINE_DECISION"
            else m for m in materials)
        deps = tuple(MaterialEpoch(m.ref, m.epoch, m.sha256) for m in sorted(materials, key=lambda m: m.ref))
        fingerprint = sha({
            "version": FENCE_VERSION, "release": decision.release_ref,
            "dependencies": [asdict(d) for d in deps],
        })
        self.snapshot = MachineAuthoritySnapshot(
            profile, decision, materials,
            PublicationEpochTicket(decision.release_ref, deps, fingerprint),
        )
        self.preflight = MachineAuthorityPreflight(
            "NEEDS_EXTERNAL_DECISION", ("OFF_DB_MACHINE_AUTHORITY_UNAVAILABLE",),
            sha(asdict(self.snapshot)),
        )
        policy_sha = next(m.sha256 for m in materials if m.role == "QUALIFIED_POLICY")
        rights_sha = next(m.sha256 for m in materials if m.role == "SOURCE_RIGHTS")
        self.registry = {
            "version": REGISTRY_VERSION, "mode": "MACHINE_V1",
            "keys": [
                {
                    "key_id": "key:reviewer", "actor_id": "actor:reviewer",
                    "role": "MACHINE_AUTHORITY", "public_key_hex": self.key,
                    "valid_from": "2026-10-01T00:00:00+00:00",
                    "expires_at": "2026-11-01T00:00:00+00:00",
                    "revoked": False, "source_root": "root:generator",
                    "qualified_policy_sha256": policy_sha, "rights_sha256": rights_sha,
                },
                {
                    "key_id": "key:adjudicator", "actor_id": "actor:adjudicator",
                    "role": "INDEPENDENT_ADJUDICATOR", "public_key_hex": self.adjudicator_key,
                    "valid_from": "2026-10-01T00:00:00+00:00",
                    "expires_at": "2026-11-01T00:00:00+00:00",
                    "revoked": False, "source_root": "root:independent",
                    "qualified_policy_sha256": policy_sha, "rights_sha256": rights_sha,
                },
            ],
        }
        self.payload = {
            "version": VERSION,
            "key_id": "key:reviewer", "issuer_actor": "actor:reviewer",
            "issuer_run": "run:reviewer", "adjudicator_key_id": "key:adjudicator",
            "adjudicator_actor": "actor:adjudicator",
            "adjudicator_run": "run:adjudicator",
            "adjudicator_source_root": "root:independent",
            "record_id": decision.record_id, "record_version": decision.record_version,
            "release_ref": decision.release_ref, "snapshot_sha256": self.preflight.snapshot_sha256,
            "source_root": decision.generator_source_root_ref,
            "generator_run": decision.generator_run_ref,
            "challenger_run": decision.challenger_run_ref,
            "challenger_source_root": decision.challenger_source_root_ref,
            "policy_version": profile.policy_version,
            "rights_sha256": next(m.sha256 for m in materials if m.role == "SOURCE_RIGHTS"),
            "qualified_policy_sha256": next(m.sha256 for m in materials if m.role == "QUALIFIED_POLICY"),
            "gold_sha256": next(m.sha256 for m in materials if m.role == "GOLD_GATE"),
            "privacy_sha256": next(m.sha256 for m in materials if m.role == "PRIVACY"),
            "fence_sha256": fingerprint, "decision": "ELIGIBLE",
            "scope": "PRIVATE_REFERENCE",
            "rights_url": "https://example.invalid/licence",
            "rights_checked_at": "2026-10-25T12:00:00+00:00",
            "rights_expires_at": "2026-10-27T12:00:00+00:00",
            "permitted_uses": ["PRIVATE_REVIEW"],
            "issued_at": "2026-10-26T15:00:00+00:00",
            "expires_at": "2026-10-27T15:00:00+00:00",
        }
        self.persist_registry()

    def persist_registry(self):
        self.path = self.root / "trusted-registry.json"
        self.path.write_bytes(canonical(self.registry))
        self.path.chmod(0o600)
        self.pin = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def signed_receipt(self, payload=None):
        item = dict(self.payload if payload is None else payload)
        item.pop("signature_hex", None)
        item.pop("adjudicator_signature_hex", None)
        adjudication = {
            field: item[field] for field in signed_authority_module._ADJUDICATION_FIELDS
        }
        item["adjudicator_signature_hex"] = self.adjudicator_private.sign(
            canonical(adjudication)
        ).hex()
        issuer_payload = {
            field: item[field] for field in signed_authority_module._FIELDS
        }
        item["signature_hex"] = self.private.sign(canonical(issuer_payload)).hex()
        return item

    def verify_receipt(
        self, receipt, *, registry_pin=None, snapshot=None, preflight=None, now=NOW,
    ):
        with patch(
            "dichiarazioni_pubbliche.machine_authority_signed_v1._utcnow",
            return_value=now,
        ):
            return verify_signed_authority(
                receipt, snapshot=snapshot or self.snapshot,
                preflight=preflight or self.preflight,
                trusted_registry_path=self.path,
                pinned_registry_sha256=registry_pin or self.pin,
            )

    def evaluate(self, payload=None, *, registry_pin=None, snapshot=None, preflight=None, now=NOW):
        return self.verify_receipt(
            self.signed_receipt(payload), registry_pin=registry_pin,
            snapshot=snapshot, preflight=preflight, now=now,
        )

    def test_trusted_signature_proves_issuer_without_machine_signoff_or_public_read(self):
        result = self.evaluate()
        self.assertEqual(result.disposition, "PRIVATE_SIGNATURE_VERIFIED", result.reason_codes)
        self.assertTrue(result.private_signature_verified)
        self.assertTrue(result.independent_adjudication_verified)
        self.assertFalse(result.machine_signoff)
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.dispatch_authorized)

    def test_dual_read_mode_verifies_private_receipt_without_machine_signoff(self):
        self.registry["mode"] = "DUAL_READ"
        self.persist_registry()
        result = self.evaluate()
        self.assertEqual(result.disposition, "PRIVATE_SIGNATURE_VERIFIED", result.reason_codes)
        self.assertTrue(result.private_signature_verified)
        self.assertTrue(result.independent_adjudication_verified)
        self.assertFalse(result.machine_signoff)
        self.assertFalse(result.publication_authority)

    def test_unregistered_adjudicator_cannot_be_asserted_by_the_issuer(self):
        result = self.evaluate(dict(self.payload, adjudicator_actor="actor:unregistered"))
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)

    def test_verifier_does_not_accept_a_caller_supplied_clock(self):
        self.assertNotIn("now", inspect.signature(verify_signed_authority).parameters)

    def test_adjudicator_signature_is_required_and_bound_to_the_receipt(self):
        receipt = self.signed_receipt()
        receipt["adjudicator_signature_hex"] = "0" * 128
        result = self.verify_receipt(receipt)
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)
        self.assertFalse(result.independent_adjudication_verified)

    def test_same_public_key_cannot_fill_both_authority_roles(self):
        self.registry["keys"][1]["public_key_hex"] = self.key
        self.persist_registry()
        result = self.evaluate()
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)
        self.assertFalse(result.independent_adjudication_verified)

    def test_expired_receipt_holds_against_the_process_clock(self):
        expired = dict(
            self.payload,
            rights_checked_at="2026-10-19T12:00:00+00:00",
            rights_expires_at="2026-10-21T00:00:00+00:00",
            issued_at="2026-10-20T00:00:00+00:00",
            expires_at="2026-10-20T23:59:00+00:00",
        )
        receipt = self.signed_receipt(expired)
        result = verify_signed_authority(
            receipt, snapshot=self.snapshot, preflight=self.preflight,
            trusted_registry_path=self.path, pinned_registry_sha256=self.pin,
        )
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)

    def test_signature_cannot_be_forged_or_reused_for_another_record_or_run(self):
        signed = self.signed_receipt()
        for key, value in (
            ("record_id", "claim:other"), ("issuer_run", "run:other"),
            ("rights_sha256", "0" * 64), ("scope", "PUBLIC_RESULT"),
        ):
            with self.subTest(field=key):
                changed = dict(signed, **{key: value})
                outcome = self.verify_receipt(changed)
                self.assertFalse(outcome.machine_signoff)
                self.assertEqual(outcome.disposition, "HOLD")
                self.assertFalse(outcome.private_signature_verified)

    def test_genuine_signature_still_rejects_changed_root_missing_challenge_rights_or_gold(self):
        for changes in (
            {"source_root": "root:changed"},
            {"challenger_run": ""},
            {"adjudicator_run": "run:generator"},
            {"adjudicator_source_root": "root:challenger"},
            {"rights_url": ""},
            {"rights_expires_at": "2026-10-25T00:00:00+00:00"},
            {"permitted_uses": []},
            {"gold_sha256": "0" * 64},
            {"decision": "HOLD"},
            {"scope": "PUBLIC_RESULT"},
        ):
            with self.subTest(changes=changes):
                result = self.evaluate(dict(self.payload, **changes))
                self.assertEqual(result.disposition, "HOLD", result.reason_codes)
                self.assertFalse(result.private_signature_verified)
                self.assertFalse(result.machine_signoff)

    def test_legacy_cutover_rollback_revocation_key_rotation_and_stale_policy_hold(self):
        original = self.registry
        key, adjudicator_key = original["keys"]
        for change in (
            {"mode": "LEGACY"},
            {"keys": [dict(key, revoked=True)]},
            {"keys": [dict(key, actor_id="actor:forged")]},
            {"keys": [dict(key, source_root="root:other")]},
            {"keys": [dict(key, rights_sha256="f" * 64)]},
            {"keys": [dict(key, expires_at="2026-10-20T00:00:00+00:00")]},
            {"keys": [key, dict(adjudicator_key, revoked=True)]},
            {"keys": [key, dict(adjudicator_key, expires_at="2026-10-20T00:00:00+00:00")]},
        ):
            with self.subTest(change=change):
                self.registry = {**original, **change}
                self.persist_registry()
                result = self.evaluate()
                self.assertEqual(result.disposition, "HOLD", result.reason_codes)
                self.assertFalse(result.private_signature_verified)
                self.assertFalse(result.machine_signoff)
        self.registry = original
        self.persist_registry()
        result = self.evaluate(registry_pin="0" * 64)
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)
        result = self.evaluate(preflight=replace(self.preflight, disposition="HOLD"))
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)

    def test_revoked_rights_epoch_and_changed_record_hold_even_with_old_valid_signature(self):
        old = self.snapshot
        invalid_decisions = (
            replace(old.decision, rights_state="REVOKED"),
            replace(old.decision, correction_state="SUPERSEDED"),
            replace(old.decision, challenger_state="PENDING"),
            replace(old.decision, record_version="rev:2"),
            replace(old.decision, challenger_source_root_ref="root:changed"),
        )
        for decision in invalid_decisions:
            with self.subTest(decision=decision):
                changed = replace(old, decision=decision)
                result = self.evaluate(snapshot=changed)
                self.assertEqual(result.disposition, "HOLD", result.reason_codes)
                self.assertFalse(result.private_signature_verified)
        new_deps = tuple(replace(dep, epoch=1) if dep.dependency_id == "dep:SOURCE_RIGHTS"
                         else dep for dep in old.fence.dependencies)
        changed_fence = replace(old.fence, dependencies=new_deps)
        result = self.evaluate(snapshot=replace(old, fence=changed_fence))
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)
        changed_profile = replace(old.profile, risk_class="HIGH")
        result = self.evaluate(snapshot=replace(old, profile=changed_profile))
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.assertFalse(result.private_signature_verified)

    def test_registry_file_swap_symlink_and_unknown_key_hold(self):
        baseline_pin = self.pin
        self.registry["keys"] = []
        self.persist_registry()
        result = self.evaluate()
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        result = self.evaluate(registry_pin=baseline_pin)
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.path.unlink()
        self.path.symlink_to(self.root / "external")
        result = self.evaluate()
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)

    def test_untrusted_receipt_fields_and_key_file_permissions_hold(self):
        invalid = dict(self.payload, extra_approval=True)
        result = self.evaluate(invalid)
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
        self.path.chmod(0o644)
        result = self.evaluate()
        self.assertEqual(result.disposition, "HOLD", result.reason_codes)
