"""DP-316 signed authority seam: exact, off-DB verifier, never a public grant."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.machine_authority_signed_v1 import (  # noqa: E402
    verify_signed_authority,
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
        profile = MachineAuthorityProfile(
            "profile:one", "profile:v1", "EVENT_SEQUENCE", "STANDARD", "it",
            "policy:v1", REQUIREMENT_VERSION,
        )
        decision = MachineDecisionReference(
            "claim:real", "rev:1", "release:one", "EVENT_SEQUENCE", "STANDARD",
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
        self.registry = {
            "version": "dp316-registry-v1", "mode": "MACHINE_V1",
            "keys": [{
                "key_id": "key:reviewer", "actor_id": "actor:reviewer",
                "role": "MACHINE_AUTHORITY", "public_key_hex": self.key,
                "valid_from": "2026-10-01T00:00:00+00:00",
                "expires_at": "2026-11-01T00:00:00+00:00",
                "revoked": False,
                "source_root": "root:generator",
                "qualified_policy_sha256": next(m.sha256 for m in materials if m.role == "QUALIFIED_POLICY"),
                "rights_sha256": next(m.sha256 for m in materials if m.role == "SOURCE_RIGHTS"),
            }],
        }
        self.payload = {
            "version": "dp316-signed-authority-v1",
            "key_id": "key:reviewer", "issuer_actor": "actor:reviewer",
            "issuer_run": "run:reviewer", "adjudicator_actor": "actor:adjudicator",
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
            "rights_url": "https://example.org/licence",
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

    def evaluate(self, payload=None, *, registry_pin=None, snapshot=None, preflight=None):
        item = self.payload if payload is None else payload
        receipt = dict(item)
        receipt["signature_hex"] = self.private.sign(canonical(item)).hex()
        return verify_signed_authority(
            receipt, snapshot=snapshot or self.snapshot,
            preflight=preflight or self.preflight,
            trusted_registry_path=self.path, pinned_registry_sha256=registry_pin or self.pin,
            now=NOW,
        )

    def test_trusted_signature_proves_issuer_without_machine_signoff_or_public_read(self):
        result = self.evaluate()
        self.assertEqual(result.disposition, "PRIVATE_SIGNATURE_VERIFIED", result.reason_codes)
        self.assertTrue(result.private_signature_verified)
        self.assertFalse(result.machine_signoff)
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.dispatch_authorized)

    def test_signature_cannot_be_forged_or_reused_for_another_record_or_run(self):
        signed = dict(self.payload)
        signed["signature_hex"] = self.private.sign(canonical(self.payload)).hex()
        for key, value in (
            ("record_id", "claim:other"), ("issuer_run", "run:other"),
            ("rights_sha256", "0" * 64), ("scope", "PUBLIC_RESULT"),
        ):
            with self.subTest(field=key):
                changed = dict(signed, **{key: value})
                outcome = verify_signed_authority(
                    changed, snapshot=self.snapshot, preflight=self.preflight,
                    trusted_registry_path=self.path, pinned_registry_sha256=self.pin, now=NOW,
                )
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
                self.assertFalse(self.evaluate(dict(self.payload, **changes)).machine_signoff)

    def test_legacy_cutover_rollback_revocation_key_rotation_and_stale_policy_hold(self):
        original = self.registry
        key = original["keys"][0]
        for change in (
            {"mode": "LEGACY"},
            {"keys": [dict(key, revoked=True)]},
            {"keys": [dict(key, actor_id="actor:forged")]},
            {"keys": [dict(key, source_root="root:other")]},
            {"keys": [dict(key, rights_sha256="f" * 64)]},
            {"keys": [dict(key, expires_at="2026-10-20T00:00:00+00:00")]},
        ):
            with self.subTest(change=change):
                self.registry = {**original, **change}
                self.persist_registry()
                self.assertFalse(self.evaluate().machine_signoff)
        self.registry = original
        self.persist_registry()
        self.assertFalse(self.evaluate(registry_pin="0" * 64).machine_signoff)
        self.assertFalse(self.evaluate(
            preflight=replace(self.preflight, disposition="HOLD")
        ).machine_signoff)

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
                self.assertFalse(self.evaluate(snapshot=changed).machine_signoff)
        new_deps = tuple(replace(dep, epoch=1) if dep.dependency_id == "dep:SOURCE_RIGHTS"
                         else dep for dep in old.fence.dependencies)
        changed_fence = replace(old.fence, dependencies=new_deps)
        self.assertFalse(self.evaluate(snapshot=replace(old, fence=changed_fence)).machine_signoff)
        changed_profile = replace(old.profile, risk_class="HIGH")
        self.assertFalse(self.evaluate(snapshot=replace(old, profile=changed_profile)).machine_signoff)

    def test_registry_file_swap_symlink_and_unknown_key_hold(self):
        baseline_pin = self.pin
        self.registry["keys"] = []
        self.persist_registry()
        self.assertFalse(self.evaluate().machine_signoff)
        self.assertFalse(self.evaluate(registry_pin=baseline_pin).machine_signoff)
        self.path.unlink()
        self.path.symlink_to(self.root / "external")
        self.assertFalse(self.evaluate().machine_signoff)

    def test_untrusted_receipt_fields_and_key_file_permissions_hold(self):
        invalid = dict(self.payload, extra_approval=True)
        self.assertFalse(self.evaluate(invalid).machine_signoff)
        self.path.chmod(0o644)
        self.assertFalse(self.evaluate().machine_signoff)
