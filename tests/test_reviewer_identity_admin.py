import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    HighRiskDecision,
    HighRiskSignals,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRole,
    ReviewStage,
    build_review_event,
)
from dichiarazioni_pubbliche.publication_safety import PublicationSafetyResult  # noqa: E402


class ReviewerIdentityAdminTests(unittest.TestCase):
    def _run(self, *args, check=True):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "poc")
        return subprocess.run(
            [sys.executable, "-m", "dichiarazioni_pubbliche.reviewer_identity_admin", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_cli_provision_attest_restart_resolve_and_revoke_without_secret_output(self):
        with tempfile.TemporaryDirectory(prefix="dp311-cli-") as tmp:
            root = Path(tmp) / "authority"
            provision = self._run(
                "--root",
                str(root),
                "provision",
                "--credential-id",
                "alice-v1",
                "--actor",
                "reviewer:alice",
                "--key-version",
                "v1",
            )
            identity = json.loads(provision.stdout)
            self.assertEqual(identity["actor_ref"], "reviewer:alice")
            self.assertEqual(identity["status"], "ACTIVE")
            self.assertNotIn("secret", provision.stdout.lower())

            event = build_review_event(
                record_id="finding:cli",
                record_version="finding:v1",
                stage=ReviewStage.PRIMARY,
                role=ReviewRole.DECISION_REVIEWER,
                action="APPROVED",
                actor_ref=identity["actor_ref"],
                credential_fingerprint=identity["credential_fingerprint"],
                reviewed_at="2026-10-06T00:10:00+02:00",
                publication_safety=PublicationSafetyResult(
                    disposition="ELIGIBLE",
                    reason_codes=(),
                    required_proofs=(),
                    binding_sha256="a" * 64,
                ),
                high_risk=HighRiskDecision(
                    disposition="STANDARD_REVIEW",
                    reason_codes=(),
                    signals=HighRiskSignals((), (), False),
                    policy_decision_ref=None,
                ),
                high_risk_input_binding_sha256="b" * 64,
            )
            event_path = Path(tmp) / "event.json"
            event_path.write_text(json.dumps(asdict(event), default=str), encoding="utf-8")
            attest = self._run(
                "--root",
                str(root),
                "attest-event",
                "--credential-id",
                "alice-v1",
                "--event-json",
                str(event_path),
                "--issued-at",
                "2026-10-06T00:11:00+02:00",
            )
            receipt = json.loads(attest.stdout)
            self.assertEqual(receipt["actor_ref"], "reviewer:alice")
            self.assertNotIn("secret", attest.stdout.lower())

            resolved = self._run(
                "--root",
                str(root),
                "resolve",
                "--receipt-id",
                receipt["receipt_id"],
            )
            self.assertEqual(json.loads(resolved.stdout), receipt)

            revoked = self._run(
                "--root",
                str(root),
                "revoke",
                "--credential-id",
                "alice-v1",
            )
            self.assertEqual(json.loads(revoked.stdout)["status"], "REVOKED")
            resolved_after_revoke = self._run(
                "--root",
                str(root),
                "resolve",
                "--receipt-id",
                receipt["receipt_id"],
            )
            self.assertEqual(json.loads(resolved_after_revoke.stdout), receipt)


if __name__ == "__main__":
    unittest.main()
