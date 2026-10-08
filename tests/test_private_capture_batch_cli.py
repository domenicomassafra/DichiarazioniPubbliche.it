"""Operator command: no network unless --execute + all authoritative preflights."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked  # noqa: E402
from dichiarazioni_pubbliche.private_capture_batch import BATCH_VERSION  # noqa: E402
from tools import capture_research_batch  # noqa: E402


class BatchCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest = Path(self.tmp.name) / "batch.json"
        self.manifest.write_text(json.dumps({
            "version": BATCH_VERSION,
            "collection_id": "research:reviewed",
            "items": [{
                "content_id": "content:1",
                "canonical_url": "https://example.test/one",
                "source_family": "REPORTING",
                "rights_record_id": "private-rights:approved",
            }],
        }), encoding="utf-8")

    def test_default_dry_run_never_constructs_body_store_or_fetches(self):
        output = io.StringIO()
        with patch.object(capture_research_batch, "CapturePipelineStore"), \
             patch.object(capture_research_batch, "PrivateRightsRegistryStore"), \
             patch.object(capture_research_batch, "preflight_capture_batch", return_value=(lambda: None,)), \
             patch.object(capture_research_batch, "capture_content") as fetch, \
             patch.object(capture_research_batch, "CaptureBodyStore") as body, \
             contextlib.redirect_stdout(output):
            exit_code = capture_research_batch.main(["--manifest", str(self.manifest)])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "PREFLIGHT_PASS_NO_WRITES")
        fetch.assert_not_called()
        body.assert_not_called()

    def test_failed_rights_preflight_blocks_before_any_fetch(self):
        output = io.StringIO()
        with patch.object(capture_research_batch, "CapturePipelineStore"), \
             patch.object(capture_research_batch, "PrivateRightsRegistryStore"), \
             patch.object(capture_research_batch, "preflight_capture_batch",
                          side_effect=PrivateCaptureAuthorizationBlocked("RIGHTS_MISSING")), \
             patch.object(capture_research_batch, "capture_content") as fetch, \
             patch.object(capture_research_batch, "CaptureBodyStore") as body, \
             contextlib.redirect_stdout(output):
            exit_code = capture_research_batch.main(["--manifest", str(self.manifest), "--execute"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED_NO_FETCH")
        fetch.assert_not_called()
        body.assert_not_called()

    def test_execute_checks_downstream_counts_after_private_capture(self):
        class Store:
            def __init__(self, **kwargs):
                self.counts = [
                    {"atomic_claim": 30, "publish_finding": 2, "statement_candidate": 0, "claim_candidate": 0},
                    {"atomic_claim": 31, "publish_finding": 2, "statement_candidate": 0, "claim_candidate": 0},
                ]

            def read_private_capture_safety_counts(self):
                return self.counts.pop(0)

        output = io.StringIO()
        with patch.object(capture_research_batch, "CapturePipelineStore", Store), \
             patch.object(capture_research_batch, "PrivateRightsRegistryStore"), \
             patch.object(capture_research_batch, "preflight_capture_batch", return_value=(lambda: None,)), \
             patch.object(capture_research_batch, "CaptureBodyStore"), \
             patch.object(capture_research_batch, "capture_content",
                          return_value=SimpleNamespace(parse_status="SUCCEEDED")) as fetch, \
             contextlib.redirect_stdout(output):
            exit_code = capture_research_batch.main(["--manifest", str(self.manifest), "--execute"])
        self.assertEqual(exit_code, 3)
        self.assertEqual(json.loads(output.getvalue())["status"], "HALTED_DOWNSTREAM_COUNTS_CHANGED")
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
