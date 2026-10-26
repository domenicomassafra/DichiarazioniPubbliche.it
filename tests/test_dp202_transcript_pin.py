"""DP-202 must send only transcript bytes covered by current rights."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_extraction_benchmark import run_live_benchmark  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import RightsSubject  # noqa: E402


class TranscriptPinTests(unittest.TestCase):
    def test_benchmark_sends_exact_transcript_bytes_checked_by_rights(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit = root / "audit.json"
            audit.write_text(json.dumps({"claims": []}))
            transcript = root / "transcript.json"
            initial = json.dumps({"full_text": "Authorized original transcript"}).encode()
            transcript.write_bytes(initial)
            changed = json.dumps({"full_text": "Unauthorized changed transcript"}).encode()
            receipt = root / "parent-canary.json"
            receipt.write_text(json.dumps({
                "status": "CANARY_PASSED", "model_requested": "antigravity/gemini-3.8-flash-tiered",
                "model_returned": "gemini-3.8-flash-tiered", "subscription_gateway_verified": True,
                "schema_constrained": True, "model_identity_exact": True, "model_calls": 1,
                "request_id": "req-test", "usage": {"prompt_tokens": 30, "completion_tokens": 10},
                "observed_cost_usd": None,
            }))
            guard = SourceFamilyUseGuard(
                read_current=lambda _subject: None,
                subject=RightsSubject(
                    source_family="TEST", locator_kind="URL",
                    locator_value="https://example.test/clip", content_id="clip:1",
                ),
                rights_record_id="rights:test", policy_version="v1",
                expected_sha256=hashlib.sha256(initial).hexdigest(),
            )
            response = {"choices": [{"message": {"content": '{"claims": []}'}}]}
            with (
                patch.object(guard, "require", side_effect=lambda *_args, **_kwargs: transcript.write_bytes(changed)),
                patch("dichiarazioni_pubbliche.claim_extraction_benchmark.call_omniroute",
                      return_value=(response, 0.01)) as provider,
            ):
                run_live_benchmark(audit_path=audit, transcript_path=transcript,
                                   parent_canary_receipt=receipt, source_use_guard=guard)
            prompt = provider.call_args.kwargs["prompt"]
            self.assertIn("Authorized original transcript", prompt)
            self.assertNotIn("Unauthorized changed transcript", prompt)


if __name__ == "__main__":
    unittest.main()
