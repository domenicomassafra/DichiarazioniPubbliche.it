"""Real SQLite receipts from the authorized private candidate operator command."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.private_candidate_batch import VERSION  # noqa: E402
from dichiarazioni_pubbliche.multi_person_batch_store_v1 import PrivateBatchSQLiteStore  # noqa: E402
from tools import extract_research_candidates  # noqa: E402


class DP240OperatorCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "batch.json"
        self.contexts = self.root / "contexts.json"
        self.ledger = self.root / "receipts.sqlite3"
        self.items = [
            dict(passage_id=f"passage:{n}", content_id=f"content:{n}",
                 capture_id=f"capture:{n}", passage_sha256=str(n + 1) * 64,
                 canonical_url=f"https://example.test/{n}", source_family=f"family:{n}",
                 rights_record_id=f"rights:{n}")
            for n in range(2)
        ]
        self.manifest.write_text(json.dumps({
            "version": VERSION, "collection_id": "collection:reviewed", "items": self.items,
        }))
        self.records = {}
        self.context_rows = {}
        for n, item in enumerate(self.items):
            self.records[item["passage_id"]] = {
                "capture_content_sha256": chr(ord("a") + n) * 64,
                "selector_type": "TEXT_POSITION", "start_char": 10, "end_char": 30,
            }
            self.context_rows[item["passage_id"]] = {
                "passage_id": item["passage_id"], "capture_id": item["capture_id"],
                "content_id": item["content_id"], "source_family": item["source_family"],
                "source_sha256": self.records[item["passage_id"]]["capture_content_sha256"],
                "passage_sha256": item["passage_sha256"],
                "selector_fingerprint": "TEXT_POSITION:10:30",
                "language_tag": "it", "speaker_candidate_id": f"person:{n}",
                "identity_review_status": "CANDIDATE_MATCH", "speech_role": "DIRECT_SPEAKER",
                "speech_act": "DIRECT_ASSERTION", "context_version": "review:v1",
                "context_review_id": f"review:{n}", "rights_status": "CLEARED",
                "estimated_tokens": 200,
            }
        self.contexts.write_text(json.dumps(self.context_rows))

    def run_cli(self, *, execute=False, responses=()):
        args = ["--manifest", str(self.manifest), "--dp240-contexts", str(self.contexts),
                "--dp240-ledger", str(self.ledger), "--model", "fixture-model"]
        if execute:
            args += ["--execute", "--max-cost-usd", "0.10"]

        class Capture:
            def __init__(self, **kwargs):
                pass

            def read_private_capture_safety_counts(self):
                return {"atomic_claim": 3, "publish_finding": 0}

        class Candidate:
            def __init__(inner_self, **kwargs):
                pass

            def read_private_passage_source_binding(inner_self, passage_id):
                return self.records[passage_id]

        class Ready:
            api_key = "fixture-never-dispatched"
            model_id = "fixture-model"
            cost_rate = Decimal("0.01")

        out = io.StringIO()
        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_CAPTURE_STORAGE_ROOT": str(self.root)}), \
             patch.object(extract_research_candidates, "CapturePipelineStore", Capture), \
             patch.object(extract_research_candidates, "CandidateExtractionStore", Candidate), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch",
                          return_value=(lambda: None, lambda: None)), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient", return_value=Ready()), \
             patch.object(extract_research_candidates, "extract_passage_candidates",
                          side_effect=responses) as provider, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(args)
        return result, json.loads(out.getvalue()), provider

    def test_read_only_preflight_returns_plan_without_creating_ledger(self):
        code, data, provider = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "PREFLIGHT_PASS_NO_WRITES")
        self.assertEqual(data["dp240_partitions"], 2)
        self.assertEqual(len(data["dp240_plan_sha256"]), 64)
        self.assertFalse(self.ledger.exists())
        provider.assert_not_called()

    def test_wrong_source_hash_fails_closed_before_provider_or_ledger(self):
        self.context_rows["passage:1"]["source_sha256"] = "f" * 64
        self.contexts.write_text(json.dumps(self.context_rows))
        code, data, provider = self.run_cli(execute=True)
        self.assertEqual(code, 2)
        self.assertEqual(data["reason_code"], "MULTIPERSON_OPERATOR_SOURCE_MISMATCH")
        provider.assert_not_called()
        self.assertFalse(self.ledger.exists())

    def test_partial_failure_is_durable_and_replay_never_redispatches(self):
        failed = SimpleNamespace(status="FAILED", reason_code="PROVIDER_TIMEOUT",
                                 cost_usd=Decimal("0.01"), call_count=1,
                                 content_id="content:0", passage_id="passage:0")
        good = SimpleNamespace(status="COMPLETED", reason_code="CANDIDATE_EXTRACTION_COMPLETED",
                               cost_usd=Decimal("0.02"), call_count=1,
                               content_id="content:1", passage_id="passage:1")
        code, data, provider = self.run_cli(execute=True, responses=(failed,))
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "HALTED_EXTRACTION")
        self.assertEqual(provider.call_count, 1)
        snapshot = PrivateBatchSQLiteStore(self.ledger).resume(data["dp240_plan_sha256"])
        self.assertEqual(snapshot.index.failed_count, 1)
        self.assertEqual(snapshot.index.pending_count, 1)
        self.assertEqual(snapshot.attempts[0].item.content_id, "content:0")
        code, data, provider = self.run_cli(execute=True, responses=(good,))
        self.assertEqual(code, 2)  # one FAILED remains immutable
        self.assertEqual(provider.call_count, 1)  # skip first, resume second
        snapshot = PrivateBatchSQLiteStore(self.ledger).resume(data["dp240_plan_sha256"])
        self.assertEqual(snapshot.index.failed_count, 1)
        self.assertEqual(snapshot.index.private_candidate_count, 1)
        self.assertEqual(snapshot.index.pending_count, 0)
        code, data, provider = self.run_cli(execute=True)
        self.assertEqual(code, 2)
        provider.assert_not_called()
        self.assertEqual(PrivateBatchSQLiteStore(self.ledger).resume(data["dp240_plan_sha256"]).revision, 2)

    def test_provider_source_swap_records_failure_and_halts(self):
        forged = SimpleNamespace(
            status="COMPLETED", reason_code="CANDIDATE_EXTRACTION_COMPLETED",
            cost_usd=Decimal("0"), call_count=1,
            content_id="content:1", passage_id="passage:0",
        )
        code, data, provider = self.run_cli(execute=True, responses=(forged,))
        self.assertEqual(code, 3)
        self.assertEqual(data["status"], "HALTED_SOURCE_BINDING")
        provider.assert_called_once()
        snapshot = PrivateBatchSQLiteStore(self.ledger).resume(data["dp240_plan_sha256"])
        self.assertEqual(snapshot.index.private_candidate_count, 0)
        self.assertEqual(snapshot.index.failed_count, 1)
        self.assertEqual(snapshot.attempts[0].observation.failure_reason,
                         "MULTIPERSON_RESULT_SOURCE_MISMATCH")

    def test_held_rights_cannot_create_ledger_or_dispatch(self):
        self.context_rows["passage:1"]["rights_status"] = "UNKNOWN"
        self.contexts.write_text(json.dumps(self.context_rows))
        code, data, provider = self.run_cli(execute=True)
        self.assertEqual(code, 2)
        self.assertEqual(data["reason_code"], "MULTIPERSON_PLAN_ITEMS_HELD")
        provider.assert_not_called()
        self.assertFalse(self.ledger.exists())

    def test_successful_replay_has_no_provider_calls_or_new_revision(self):
        first = SimpleNamespace(
            status="COMPLETED", reason_code="CANDIDATE_EXTRACTION_COMPLETED",
            cost_usd=Decimal("0"), call_count=1,
            content_id="content:0", passage_id="passage:0",
        )
        second = SimpleNamespace(
            status="COMPLETED", reason_code="CANDIDATE_EXTRACTION_COMPLETED",
            cost_usd=Decimal("0"), call_count=1,
            content_id="content:1", passage_id="passage:1",
        )
        code, data, provider = self.run_cli(execute=True, responses=(first, second))
        self.assertEqual(code, 0)
        self.assertEqual(data["completed"], 2)
        self.assertEqual(provider.call_count, 2)
        plan_sha256 = data["dp240_plan_sha256"]
        self.assertEqual(PrivateBatchSQLiteStore(self.ledger).resume(plan_sha256).revision, 2)

        code, data, provider = self.run_cli(execute=True)
        self.assertEqual(code, 0)
        self.assertEqual(data["completed"], 2)
        provider.assert_not_called()
        self.assertEqual(PrivateBatchSQLiteStore(self.ledger).resume(plan_sha256).revision, 2)


if __name__ == "__main__":
    unittest.main()
