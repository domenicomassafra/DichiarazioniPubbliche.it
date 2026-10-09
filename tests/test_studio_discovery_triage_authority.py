"""DP-417 off-DB identity attestation: fail-closed, no publication authority."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority,
    initialize_authority_root,
    provision_reviewer_credential,
)
from dichiarazioni_pubbliche.studio_discovery_triage_authority import (  # noqa: E402
    TRIAGE_ATTESTATION_DOMAIN,
    issue_triage_attestation,
    verify_triage_attestation,
)
from dichiarazioni_pubbliche import studio_discovery_triage_authority as triage_authority  # noqa: E402
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (  # noqa: E402
    make_triage_request,
)
from dichiarazioni_pubbliche.studio_local_api import _ALLOWED_PATHS  # noqa: E402


def triage_request(**overrides):
    return make_triage_request(**({
        "collection_id": "research:1",
        "hit_id": "hit:1",
        "request_key": "triage:request-001",
        "decision": "NEEDS_REVIEW",
        "expected_revision": 0,
        "actor_ref": "reviewer:alice",
    } | overrides))


class PrivateDiscoveryTriageAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reviewer-private"
        initialize_authority_root(self.root)
        self.alice_secret = "11" * 32
        self.bob_secret = "22" * 32
        provision_reviewer_credential(
            self.root, credential_id="alice-v1", actor_ref="reviewer:alice",
            key_version="v1", secret_hex=self.alice_secret,
        )
        provision_reviewer_credential(
            self.root, credential_id="bob-v1", actor_ref="reviewer:bob",
            key_version="v1", secret_hex=self.bob_secret,
        )
        self.authority = LocalFileReviewerIdentityAuthority(self.root)
        self.request = triage_request()

    def _issue(self, request=None):
        return issue_triage_attestation(self.authority, request or self.request, "alice-v1")

    def _file(self, receipt=None):
        receipt = receipt or self._issue()
        return self.root / "triage-receipts" / f"{receipt['receipt_id']}.json"

    def test_issue_verify_restart_private_receipt_secret_never_emitted(self):
        issued = self._issue()
        self.assertEqual(set(issued), {"receipt_id", "payload_sha256"})
        self.assertRegex(issued["receipt_id"], r"^triage-receipt-[0-9a-f]{64}$")
        self.assertEqual(issued["payload_sha256"], self.request.payload_sha256)
        self.assertEqual(
            verify_triage_attestation(
                LocalFileReviewerIdentityAuthority(self.root), self.request,
                issued["receipt_id"],
            ),
            issued,
        )
        path = self._file(issued)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(list(path.parent.glob("*.json"))), 1)
        self.assertEqual(len(list((self.root / "receipts").glob("*.json"))), 0)
        text = path.read_text(encoding="utf-8")
        self.assertNotIn(self.alice_secret, text)
        self.assertNotIn(self.bob_secret, text)
        self.assertNotIn("secret_hex", text)
        self.assertNotIn("mac_sha256", json.dumps(issued))
        self.assertNotIn("APPROVE", json.dumps(issued))
        self.assertNotIn("PUBLISH", json.dumps(issued))
        self.assertEqual(json.loads(text)["domain"], TRIAGE_ATTESTATION_DOMAIN)
        self.assertNotIn("/v1/discovery/triage", _ALLOWED_PATHS)

    def test_replay_exact_match_does_not_rewrite_or_duplicate(self):
        first = self._issue()
        path = self._file(first)
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        second = self._issue()
        self.assertEqual(first, second)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_replay_different_intent_cannot_use_original_receipt(self):
        issued = self._issue()
        variants = (
            {"collection_id": "research:2"}, {"hit_id": "hit:2"},
            {"request_key": "triage:request-002"}, {"decision": "DEFERRED"},
            {"decision": "REJECTED"}, {"expected_revision": 1},
            {"actor_ref": "reviewer:bob"},
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                verify_triage_attestation(
                    self.authority, triage_request(**changed), issued["receipt_id"],
                )
        self.assertEqual(verify_triage_attestation(
            self.authority, self.request, issued["receipt_id"],
        ), issued)

    def test_actor_is_exact_and_not_substitutable(self):
        with self.assertRaisesRegex(ValueError, "ACTOR_MISMATCH"):
            issue_triage_attestation(self.authority, self.request, "bob-v1")
        with self.assertRaisesRegex(ValueError, "ACTOR_MISMATCH"):
            issue_triage_attestation(
                self.authority, triage_request(actor_ref="reviewer:bob"), "alice-v1",
            )
        self.assertFalse((self.root / "triage-receipts").exists())

    def test_revocation_blocks_verify_and_new_issue_even_after_restart(self):
        issued = self._issue()
        self.authority.revoke("alice-v1")
        fresh_authority = LocalFileReviewerIdentityAuthority(self.root)
        with self.assertRaisesRegex(ValueError, "REVOKED"):
            verify_triage_attestation(fresh_authority, self.request, issued["receipt_id"])
        with self.assertRaisesRegex(ValueError, "REVOKED"):
            issue_triage_attestation(fresh_authority, self.request, "alice-v1")
        self.assertEqual(len(list((self.root / "triage-receipts").glob("*.json"))), 1)

    def test_revocation_during_signature_check_blocks_verification(self):
        issued = self._issue()
        original = triage_authority._check_signed

        def revoke_after_signature(*args):
            original(*args)
            self.authority.revoke("alice-v1")

        with patch.object(triage_authority, "_check_signed", side_effect=revoke_after_signature):
            with self.assertRaisesRegex(ValueError, "REVOKED"):
                verify_triage_attestation(self.authority, self.request, issued["receipt_id"])

    def test_receipt_replacement_during_credential_check_blocks_verification(self):
        issued = self._issue()
        path = self._file(issued)
        original = triage_authority._credential

        def alter_after_credential(*args):
            identity = original(*args)
            payload = json.loads(path.read_text())
            payload["decision"] = "REJECTED"
            path.write_text(json.dumps(payload))
            return identity

        with patch.object(triage_authority, "_credential", side_effect=alter_after_credential):
            with self.assertRaisesRegex(ValueError, "DP417_TRIAGE_RECEIPT_INVALID"):
                verify_triage_attestation(self.authority, self.request, issued["receipt_id"])

    def test_child_directories_remain_anchored_to_open_authority_root(self):
        alternate = Path(self.tmp.name) / "replacement-private"
        initialize_authority_root(alternate)
        provision_reviewer_credential(
            alternate, credential_id="alice-v1", actor_ref="reviewer:alice",
            key_version="v1", secret_hex="44" * 32,
        )
        (self.root / "triage-receipts").mkdir(mode=0o700)
        (alternate / "triage-receipts").mkdir(mode=0o700)
        original_receipts_inode = (self.root / "triage-receipts").stat().st_ino
        replacement_receipts_inode = (alternate / "triage-receipts").stat().st_ino
        saved_root = self.root.with_name("reviewer-original")
        original_open = triage_authority._open_private_dir
        switched = False

        def swap_root_after_open(path):
            nonlocal switched
            fd = original_open(path)
            if not switched and Path(path) == self.root:
                self.root.rename(saved_root)
                self.root.symlink_to(alternate, target_is_directory=True)
                switched = True
            return fd

        try:
            with patch.object(triage_authority, "_open_private_dir", side_effect=swap_root_after_open):
                receipt_fd = triage_authority._receipt_dir(self.authority, create=False)
            try:
                self.assertNotEqual(original_receipts_inode, replacement_receipts_inode)
                self.assertEqual(os.fstat(receipt_fd).st_ino, original_receipts_inode)
            finally:
                os.close(receipt_fd)
        finally:
            if switched:
                self.root.unlink()
                saved_root.rename(self.root)

    def test_credential_root_swap_cannot_use_other_authority_credentials(self):
        alternate = Path(self.tmp.name) / "replacement-private"
        initialize_authority_root(alternate)
        provision_reviewer_credential(
            alternate, credential_id="alice-v1", actor_ref="reviewer:alice",
            key_version="v1", secret_hex="44" * 32,
        )
        saved_root = self.root.with_name("reviewer-original")
        original_open = triage_authority._open_private_dir
        switched = False

        def swap_root_after_open(path):
            nonlocal switched
            fd = original_open(path)
            if not switched and Path(path) == self.root:
                self.root.rename(saved_root)
                self.root.symlink_to(alternate, target_is_directory=True)
                switched = True
            return fd

        try:
            with patch.object(triage_authority, "_open_private_dir", side_effect=swap_root_after_open):
                with self.assertRaisesRegex(ValueError, "DP417_TRIAGE_CREDENTIAL_INVALID"):
                    triage_authority._credential(self.authority, "alice-v1")
        finally:
            if switched:
                self.root.unlink()
                saved_root.rename(self.root)

    def test_receipt_mac_and_signed_field_tampering_rejected(self):
        issued = self._issue()
        path = self._file(issued)
        original = path.read_bytes()
        mutations = (
            {"mac_sha256": "0" * 64},
            {"actor_ref": "reviewer:bob"},
            {"collection_id": "research:2"},
            {"decision": "REJECTED"},
            {"expected_revision": 9},
            {"payload_sha256": "f" * 64},
            {"request_key": "triage:request-002"},
            {"credential_fingerprint": "f" * 64},
            {"key_version": "v2"},
            {"domain": "DP310_PUBLICATION_V1"},
            {"malicious_extra_field": "PRIVATE"},
        )
        try:
            for update in mutations:
                with self.subTest(update=update):
                    modified = json.loads(original)
                    modified.update(update)
                    path.write_text(json.dumps(modified), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        verify_triage_attestation(
                            self.authority, self.request, issued["receipt_id"],
                        )
                    with self.assertRaises(ValueError):
                        self._issue()
        finally:
            path.write_bytes(original)
        self.assertEqual(
            verify_triage_attestation(self.authority, self.request, issued["receipt_id"]),
            issued,
        )

    def test_valid_hmac_for_another_application_still_denied(self):
        issued = self._issue()
        path = self._file(issued)
        altered = json.loads(path.read_text())
        altered["domain"] = "DP310_PUBLICATION_REVIEW_V1"
        material = {k: v for k, v in altered.items() if k != "mac_sha256"}
        altered["mac_sha256"] = hmac.new(
            bytes.fromhex(self.alice_secret),
            json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
            hashlib.sha256,
        ).hexdigest()
        path.write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, "BINDING_MISMATCH"):
            verify_triage_attestation(self.authority, self.request, issued["receipt_id"])

    def test_symlinked_receipt_and_directory_rejected_without_overwriting(self):
        issued = self._issue()
        path = self._file(issued)
        original = path.read_bytes()
        outside = Path(self.tmp.name) / "outside.json"
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        for operation in (
            lambda: self._issue(),
            lambda: verify_triage_attestation(
                self.authority, self.request, issued["receipt_id"],
            ),
        ):
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(outside.read_bytes(), original)
        path.unlink()
        triage_dir = self.root / "triage-receipts"
        triage_dir.rmdir()
        triage_dir.symlink_to(Path(self.tmp.name))
        with self.assertRaises(ValueError):
            self._issue()
        with self.assertRaises(ValueError):
            verify_triage_attestation(
                self.authority, self.request, issued["receipt_id"],
            )
        self.assertEqual(outside.read_bytes(), original)

    def test_symlinked_credential_refused_even_if_points_to_real_credential(self):
        credential = self.root / "credentials" / "alice-v1.json"
        old = credential.with_suffix(".saved")
        credential.rename(old)
        credential.symlink_to(old)
        with self.assertRaises(ValueError):
            self._issue()
        self.assertFalse((self.root / "triage-receipts").exists())

    def test_insecure_directory_receipt_and_credential_permissions_refused(self):
        issued = self._issue()
        path = self._file(issued)
        credential = self.root / "credentials" / "alice-v1.json"
        triage_dir = self.root / "triage-receipts"
        for target, permissions in (
            (path, 0o644), (triage_dir, 0o755),
            (credential, 0o640), (self.root, 0o755),
        ):
            with self.subTest(target=target):
                original = target.stat().st_mode & 0o777
                try:
                    os.chmod(target, permissions)
                    with self.assertRaises(ValueError):
                        self._issue()
                    with self.assertRaises(ValueError):
                        verify_triage_attestation(
                            self.authority, self.request, issued["receipt_id"],
                        )
                finally:
                    os.chmod(target, original)
        self.assertEqual(verify_triage_attestation(
            self.authority, self.request, issued["receipt_id"],
        ), issued)

    def test_hardlinked_receipt_refused(self):
        issued = self._issue()
        path = self._file(issued)
        hardlink = Path(self.tmp.name) / "link.json"
        os.link(path, hardlink)
        with self.assertRaises(ValueError):
            verify_triage_attestation(self.authority, self.request, issued["receipt_id"])

    def test_credential_key_rotation_fails_existing_hmac_and_receipt_binding(self):
        issued = self._issue()
        path = self.root / "credentials" / "alice-v1.json"
        old = json.loads(path.read_text())
        rotated = old | {"secret_hex": "33" * 32}
        path.write_text(json.dumps(rotated))
        with self.assertRaises(ValueError):
            verify_triage_attestation(self.authority, self.request, issued["receipt_id"])
        # The previous receipt and its old signature remain intact and no
        # legacy publication-review receipts are created.
        self.assertEqual(len(list((self.root / "triage-receipts").glob("*.json"))), 1)
        self.assertEqual(len(list((self.root / "receipts").glob("*.json"))), 0)

    def test_truncated_and_duplicate_key_receipt_are_rejected(self):
        issued = self._issue()
        path = self._file(issued)
        original = path.read_bytes()
        try:
            for candidate in (
                b"{",
                original.rstrip()[:-1] + b',"domain":"DP417_TRIAGE_V1"}',
                original.rstrip()[:-1] + b',"secret_hex":"NOT_ALLOWED"}',
            ):
                with self.subTest(candidate=candidate[:20]):
                    path.write_bytes(candidate)
                    with self.assertRaises(ValueError):
                        verify_triage_attestation(
                            self.authority, self.request, issued["receipt_id"],
                        )
                    with self.assertRaises(ValueError):
                        self._issue()
        finally:
            path.write_bytes(original)
        self.assertEqual(
            verify_triage_attestation(self.authority, self.request, issued["receipt_id"]),
            issued,
        )

    def test_rejects_invalid_request_forged_fingerprint_and_receipt_ids(self):
        issued = self._issue()
        forged = triage_request()
        object.__setattr__(forged, "payload_sha256", "0" * 64)
        with self.assertRaisesRegex(ValueError, "FINGERPRINT_INVALID"):
            self._issue(forged)
        with self.assertRaisesRegex(ValueError, "FINGERPRINT_INVALID"):
            verify_triage_attestation(self.authority, forged, issued["receipt_id"])
        for invalid in (None, {}, "APPROVE", "PUBLISH", "not-a-request"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                issue_triage_attestation(self.authority, invalid, "alice-v1")
        for receipt_id in ("", "../receipts/review-receipt-a", issued["receipt_id"] + "\n", "review-receipt-" + "a" * 64):
            with self.subTest(receipt_id=receipt_id), self.assertRaises(ValueError):
                verify_triage_attestation(self.authority, self.request, receipt_id)
        for credential_id in ("../alice-v1", "alice-v1\n", "alice/v1"):
            with self.subTest(credential_id=credential_id), self.assertRaises(ValueError):
                issue_triage_attestation(self.authority, self.request, credential_id)
        for decision in ("APPROVE", "EXTRACT", "MERGE", "PUBLISH"):
            with self.assertRaises(ValueError):
                triage_request(decision=decision)

    def test_verification_does_not_initialize_absent_receipt_directory(self):
        with self.assertRaises(ValueError):
            verify_triage_attestation(
                self.authority, self.request, "triage-receipt-" + "0" * 64,
            )
        self.assertFalse((self.root / "triage-receipts").exists())


if __name__ == "__main__":
    unittest.main()
