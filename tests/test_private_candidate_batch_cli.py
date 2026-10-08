import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.private_candidate_batch import VERSION
from dichiarazioni_pubbliche.private_candidate_commit_fence import PrivateCandidateCommitFence
from tools import extract_research_candidates


class CandidateCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "manifest.json"
        self.path.write_text(json.dumps({
            "version": VERSION,
            "collection_id": "research:reviewed",
            "items": [{
                "passage_id": "passage:reviewed",
                "content_id": "content:reviewed",
                "capture_id": "capture:reviewed",
                "passage_sha256": "a" * 64,
                "canonical_url": "https://example.test/reviewed",
                "source_family": "REPORTING",
                "rights_record_id": "private-rights:reviewed",
            }],
        }), encoding="utf-8")

    def test_default_dry_run_never_creates_model_client_or_runs_extraction(self):
        out = io.StringIO()
        with patch.object(extract_research_candidates, "CapturePipelineStore"), \
             patch.object(extract_research_candidates, "CandidateExtractionStore"), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch", return_value=(lambda: None,)), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient") as provider, \
             patch.object(extract_research_candidates, "extract_passage_candidates") as extraction, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(["--manifest", str(self.path)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "PREFLIGHT_PASS_NO_WRITES")
        provider.assert_not_called()
        extraction.assert_not_called()

    def test_failed_authority_preflight_never_constructs_provider(self):
        out = io.StringIO()
        with patch.object(extract_research_candidates, "CapturePipelineStore"), \
             patch.object(extract_research_candidates, "CandidateExtractionStore"), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch",
                          side_effect=PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_COLLECTION_NOT_ACTIVE")), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient") as provider, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(
                ["--manifest", str(self.path), "--execute", "--max-cost-usd", "0.01"]
            )
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED_NO_MODEL_CALL")
        provider.assert_not_called()

    def test_execution_requires_positive_budget_and_explicit_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as issue:
                extract_research_candidates.main(["--manifest", str(self.path), "--execute"])
        self.assertEqual(issue.exception.code, 2)

    def test_unconfigured_provider_is_truthfully_blocked(self):
        out = io.StringIO()
        class Missing:
            api_key = ""
            model_id = None
            cost_rate = None

        with patch.object(extract_research_candidates, "CapturePipelineStore"), \
             patch.object(extract_research_candidates, "CandidateExtractionStore"), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch", return_value=(lambda: None,)), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient", return_value=Missing()), \
             patch.object(extract_research_candidates, "extract_passage_candidates") as extraction, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(
                ["--manifest", str(self.path), "--execute", "--max-cost-usd", "0.01"]
            )
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED_PROVIDER_NOT_CONFIGURED")
        extraction.assert_not_called()

    def test_execution_allocates_budget_across_passages_and_never_promotes(self):
        raw = json.loads(self.path.read_text())
        second = dict(raw["items"][0])
        second.update(
            passage_id="passage:second",
            capture_id="capture:second",
            passage_sha256="b" * 64,
        )
        raw["items"].append(second)
        self.path.write_text(json.dumps(raw))

        class Capture:
            def __init__(self, **kwargs):
                pass

            def read_private_capture_safety_counts(self):
                return dict(atomic_claim=30, publish_finding=2,
                            statement_candidate=0, claim_candidate=0)

        class Ready:
            api_key = "fixture-credential-never-sent"
            model_id = "fixture-model"
            cost_rate = Decimal("0.01")

        receipts = [
            SimpleNamespace(status="COMPLETED", cost_usd=Decimal("0.03"),
                            call_count=1, reason_code="CANDIDATE_EXTRACTION_COMPLETED"),
            SimpleNamespace(status="COMPLETED", cost_usd=Decimal("0.04"),
                            call_count=1, reason_code="CANDIDATE_EXTRACTION_COMPLETED"),
        ]
        out = io.StringIO()
        with patch.object(extract_research_candidates, "CapturePipelineStore", Capture), \
             patch.object(extract_research_candidates, "CandidateExtractionStore"), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch",
                          return_value=(lambda: None, lambda: None)), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient",
                          return_value=Ready()), \
             patch.object(extract_research_candidates, "extract_passage_candidates",
                          side_effect=receipts) as extract, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(
                ["--manifest", str(self.path), "--execute", "--max-cost-usd", "0.10"]
            )
        self.assertEqual(result, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "PRIVATE_CANDIDATES_EXTRACTED")
        self.assertEqual(data["completed"], 2)
        self.assertEqual(data["actual_cost_usd"], "0.07")
        self.assertFalse(data["publication"])
        self.assertFalse(data["claim_promotion"])
        self.assertEqual(extract.call_count, 2)
        self.assertEqual(
            [call.kwargs["max_cost_usd"] for call in extract.call_args_list],
            [Decimal("0.10"), Decimal("0.07")],
        )
        self.assertTrue(all(
            isinstance(call.kwargs["commit_fence"], PrivateCandidateCommitFence)
            and call.kwargs["commit_fence"].collection_id == "research:reviewed"
            and call.kwargs["commit_fence"].content_id == "content:reviewed"
            and call.kwargs["commit_fence"].rights_record_id == "private-rights:reviewed"
            and call.kwargs["commit_fence"].passage_id == call.kwargs["passage_id"]
            for call in extract.call_args_list
        ))

    def test_rejected_first_candidate_stops_batch_without_second_call(self):
        class Capture:
            def __init__(self, **kwargs):
                pass

            def read_private_capture_safety_counts(self):
                return dict(atomic_claim=30, publish_finding=2,
                            statement_candidate=0, claim_candidate=0)

        class Ready:
            api_key = "fixture-only"
            model_id = "fixture"
            cost_rate = Decimal("0.01")

        out = io.StringIO()
        with patch.object(extract_research_candidates, "CapturePipelineStore", Capture), \
             patch.object(extract_research_candidates, "CandidateExtractionStore"), \
             patch.object(extract_research_candidates, "PrivateRightsRegistryStore"), \
             patch.object(extract_research_candidates, "preflight_candidate_batch",
                          return_value=(lambda: None,)), \
             patch.object(extract_research_candidates, "OmniRouteCandidateExtractionClient",
                          return_value=Ready()), \
             patch.object(extract_research_candidates, "extract_passage_candidates",
                          return_value=SimpleNamespace(
                              status="BLOCKED", cost_usd=Decimal(0),
                              call_count=0, reason_code="COST_CAP_PRECALL",
                          )) as extract, \
             contextlib.redirect_stdout(out):
            result = extract_research_candidates.main(
                ["--manifest", str(self.path), "--execute", "--max-cost-usd", "0.01"]
            )
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "HALTED_EXTRACTION")
        extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()
