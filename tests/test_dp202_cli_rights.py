"""DP-202: the installed CLI must re-read registered source-use rights."""

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_extraction_benchmark import main  # noqa: E402
from dichiarazioni_pubbliche.dp202_cli_rights import registered_source_guard  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)

BODY = b'{"segments": [{"start": 0, "text": "Example private text"}]}'
SUBJECT = RightsSubject(
    source_family="TEST_SOCIAL", locator_kind="URL",
    locator_value="https://example.test/clip", content_id="content:test-clip",
)


def current_record():
    return PrivateRightsRecord(
        id="rights:current", subject_fingerprint=rights_subject_fingerprint(SUBJECT),
        source_family=SUBJECT.source_family, locator_kind=SUBJECT.locator_kind,
        locator_value=SUBJECT.locator_value, content_id=SUBJECT.content_id,
        evidence_id=None, transcript_segment_id=None, canonical_segment_id=None,
        passage_id=None, rights_status="CLEARED", rights_receipt_ref="proof:private",
        permitted_uses=("PARSE_TEXT",), attribution_requirements=(),
        reviewed_at="2026-01-01T00:00:00+00:00",
        expires_at="2030-01-01T00:00:00+00:00", reviewer_ref="agent:legal",
        policy_version="test-policy-v1", record_visibility="PRIVATE",
        supersedes_id=None, version_state="CURRENT",
    )


class GiulianiCliRightsTests(unittest.TestCase):
    def test_cli_passes_registered_guard_to_benchmark_and_rechecks_revocation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "rights-context.json"
            audit = root / "audit.json"
            audit.write_text(json.dumps({"content": {
                "instagram_url": SUBJECT.locator_value,
                "tiktok_url": "https://example.test/other-clip",
            }}))
            config.write_text(json.dumps({
                "source_family": SUBJECT.source_family,
                "source_url": SUBJECT.locator_value,
                "content_id": SUBJECT.content_id,
                "policy_version": "test-policy-v1",
                "transcript_sha256": hashlib.sha256(BODY).hexdigest(),
            }))
            report_keys = (
                "model", "reference_claims", "extracted_claims", "matched_claims",
                "claim_recall", "claim_precision", "type_accuracy_on_matched",
                "speaker_accuracy_on_matched", "check_worthy_accuracy_on_matched",
                "numeric_sensitive_accuracy_on_matched", "latency_seconds", "cost_usd",
            )
            with (
                patch("dichiarazioni_pubbliche.dp202_cli_rights.PrivateRightsRegistryStore") as store,
                patch("dichiarazioni_pubbliche.claim_extraction_benchmark.run_live_benchmark") as run,
                patch("sys.argv", ["benchmark", "--audit", str(audit),
                                   "--rights-context", str(config)]),
            ):
                store.return_value.read_current.return_value = current_record()
                run.return_value = ({key: None for key in report_keys}, {})
                with redirect_stdout(io.StringIO()):
                    main()
                guard = run.call_args.kwargs["source_use_guard"]
                self.assertEqual(guard.expected_sha256, hashlib.sha256(BODY).hexdigest())
                self.assertEqual(guard.require("PARSE_TEXT", content_sha256=guard.expected_sha256).status, "PERMITTED")
                store.return_value.read_current.return_value = replace(
                    current_record(), rights_status="REVOKED",
                )
                with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_REVOKED"):
                    guard.require("PARSE_TEXT", content_sha256=guard.expected_sha256)

    def test_unrelated_source_is_rejected_before_registry_access(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit = root / "audit.json"
            audit.write_text(json.dumps({"content": {
                "instagram_url": SUBJECT.locator_value,
                "tiktok_url": "https://example.test/other-clip",
            }}))
            context = root / "rights-context.json"
            context.write_text(json.dumps({
                "source_family": SUBJECT.source_family,
                "source_url": "https://example.test/unrelated",
                "content_id": SUBJECT.content_id,
                "policy_version": "test-policy-v1",
                "transcript_sha256": hashlib.sha256(BODY).hexdigest(),
            }))
            with patch("dichiarazioni_pubbliche.dp202_cli_rights.PrivateRightsRegistryStore") as store:
                with self.assertRaisesRegex(RuntimeError, "DP202_SOURCE_RIGHTS_UNVERIFIED"):
                    registered_source_guard(context, audit_path=audit)
                store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
