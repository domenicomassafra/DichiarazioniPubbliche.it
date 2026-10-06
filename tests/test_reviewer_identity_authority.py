import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRole,
    ReviewStage,
    build_review_event,
)
from dichiarazioni_pubbliche.publication_safety import PublicationSafetyResult  # noqa: E402
from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    HighRiskDecision,
    HighRiskSignals,
)
from dichiarazioni_pubbliche.publication_review_persistence import (  # noqa: E402
    identity_attestation_blockers,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority,
    initialize_authority_root,
    provision_reviewer_credential,
)


def review_event(*, actor_ref: str, credential_fingerprint: str, suffix: str = "1"):
    return build_review_event(
        record_id=f"finding:{suffix}",
        record_version="finding:v1",
        stage=ReviewStage.PRIMARY,
        role=ReviewRole.DECISION_REVIEWER,
        action="APPROVED",
        actor_ref=actor_ref,
        credential_fingerprint=credential_fingerprint,
        reviewed_at="2026-10-06T00:00:00+02:00",
        publication_safety=PublicationSafetyResult(
            disposition="ELIGIBLE",
            reason_codes=(),
            required_proofs=(),
            binding_sha256="a" * 64,
        ),
        high_risk=HighRiskDecision(
            disposition="STANDARD_REVIEW",
            reason_codes=(),
            signals=HighRiskSignals(
                risk_classes=(),
                procedural_statuses=(),
                allegation_framing=False,
            ),
            policy_decision_ref=None,
        ),
        high_risk_input_binding_sha256="b" * 64,
    )


class LocalReviewerIdentityAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "authority"
        alice = provision_reviewer_credential(
            self.root,
            credential_id="alice-v1",
            actor_ref="reviewer:alice",
            key_version="v1",
            secret_hex="11" * 32,
        )
        bob = provision_reviewer_credential(
            self.root,
            credential_id="bob-v1",
            actor_ref="reviewer:bob",
            key_version="v1",
            secret_hex="33" * 32,
        )
        self.alice = alice
        self.bob = bob
        self.authority = LocalFileReviewerIdentityAuthority(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identity_is_derived_from_private_credential_not_caller_claim(self):
        identity = self.authority.identity("alice-v1")
        self.assertEqual(identity.actor_ref, "reviewer:alice")
        self.assertEqual(identity.credential_fingerprint, self.alice.credential_fingerprint)
        event = review_event(
            actor_ref="reviewer:mallory",
            credential_fingerprint=self.alice.credential_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "EVENT_ACTOR_MISMATCH"):
            self.authority.issue(
                event,
                credential_id="alice-v1",
                issued_at="2026-10-06T00:01:00+02:00",
            )

    def test_receipt_survives_restart_and_binds_exact_event(self):
        event = review_event(
            actor_ref=self.alice.actor_ref,
            credential_fingerprint=self.alice.credential_fingerprint,
        )
        issued = self.authority.issue(
            event,
            credential_id="alice-v1",
            issued_at="2026-10-06T00:01:00+02:00",
        )
        restarted = LocalFileReviewerIdentityAuthority(self.root)
        resolved = restarted.resolve(issued.receipt_id)
        self.assertEqual(resolved, issued)
        self.assertEqual(identity_attestation_blockers(event, resolved), ())
        altered = replace(event, record_version="finding:v2")
        self.assertIn("REVIEW_IDENTITY_AUTHORITY_EVENT_MISMATCH", identity_attestation_blockers(altered, resolved))

    def test_tampered_receipt_is_rejected(self):
        event = review_event(
            actor_ref=self.alice.actor_ref,
            credential_fingerprint=self.alice.credential_fingerprint,
        )
        issued = self.authority.issue(
            event,
            credential_id="alice-v1",
            issued_at="2026-10-06T00:01:00+02:00",
        )
        path = self.root / "receipts" / f"{issued.receipt_id}.json"
        payload = json.loads(path.read_text())
        payload["attestation"]["record_version"] = "finding:tampered"
        path.write_text(json.dumps(payload))
        os.chmod(path, 0o600)
        self.assertIsNone(self.authority.resolve(issued.receipt_id))

    def test_authority_refuses_an_event_with_self_invented_integrity(self):
        event = review_event(
            actor_ref=self.alice.actor_ref,
            credential_fingerprint=self.alice.credential_fingerprint,
        )
        tampered = replace(event, integrity_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "EVENT_TAMPERED"):
            self.authority.issue(
                tampered,
                credential_id="alice-v1",
                issued_at="2026-10-06T00:01:00+02:00",
            )

    def test_unsafe_permissions_fail_closed(self):
        path = self.root / "credentials" / "alice-v1.json"
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(ValueError, "PERMISSIONS_UNSAFE"):
            self.authority.identity("alice-v1")

    def test_revocation_blocks_new_issue_but_keeps_historical_verification(self):
        event = review_event(
            actor_ref=self.alice.actor_ref,
            credential_fingerprint=self.alice.credential_fingerprint,
        )
        issued = self.authority.issue(
            event,
            credential_id="alice-v1",
            issued_at="2026-10-06T00:01:00+02:00",
        )
        revoked = self.authority.revoke("alice-v1")
        self.assertEqual(revoked.status, "REVOKED")
        self.assertEqual(self.authority.resolve(issued.receipt_id), issued)
        with self.assertRaisesRegex(ValueError, "REVOKED"):
            self.authority.issue(
                event,
                credential_id="alice-v1",
                issued_at="2026-10-06T00:02:00+02:00",
            )

    def test_same_secret_cannot_be_registered_as_two_actor_identities(self):
        path = self.root / "credentials" / "mallory-v1.json"
        path.write_text(
            json.dumps(
                {
                    "contract_version": "local-reviewer-credential-v1",
                    "credential_id": "mallory-v1",
                    "actor_ref": "reviewer:mallory",
                    "key_version": "v1",
                    "status": "ACTIVE",
                    "secret_hex": "11" * 32,
                }
            )
        )
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(ValueError, "FINGERPRINT_SHARED_ACROSS_ACTORS"):
            self.authority.identity("alice-v1")

    def test_receipt_files_do_not_contain_another_reviewers_secret(self):
        event = review_event(
            actor_ref=self.bob.actor_ref,
            credential_fingerprint=self.bob.credential_fingerprint,
            suffix="2",
        )
        issued = self.authority.issue(
            event,
            credential_id="bob-v1",
            issued_at="2026-10-06T00:01:00+02:00",
        )
        receipt = (self.root / "receipts" / f"{issued.receipt_id}.json").read_text()
        self.assertNotIn("33" * 32, receipt)
        self.assertNotIn("secret_hex", receipt)

    def test_authority_root_itself_must_be_private(self):
        other = Path(self.tmp.name) / "unsafe"
        initialize_authority_root(other)
        os.chmod(other, 0o755)
        with self.assertRaisesRegex(ValueError, "PERMISSIONS_UNSAFE"):
            LocalFileReviewerIdentityAuthority(other)


if __name__ == "__main__":
    unittest.main()
