import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.collection_readiness import (  # noqa: E402
    PipelineStage,
    ReadinessState,
    evaluate_collection_readiness,
    format_readiness_report,
    main,
)


class CollectionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.valid_sources = [
            {
                "id": "youtube-pulp-podcast",
                "kind": "youtube_channel",
                "name": "Pulp Podcast",
            }
        ]
        self.all_ready_caps = {
            "claim_extraction_available": True,
            "remote_asr_credential_configured": True,
            "deterministic_verification_available": True,
            "public_projection_writable": True,
            "evidence_retrieval_available": True,
            "relation_analysis_available": True,
        }
        self.sample_queue_counts = {
            "TRANSCRIPT_RESOLVE_PLATFORM": 0,
            "CLAIM_EXTRACT": 0,
            "VERIFY_CLAIM": 0,
        }

    def test_all_ready_pipeline_reports_ready(self):
        report = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=self.all_ready_caps,
            queue_counts=self.sample_queue_counts,
        )
        self.assertEqual(report.overall_state, ReadinessState.READY)
        self.assertTrue(report.is_ready)
        for stage in report.stages:
            self.assertEqual(stage.state, ReadinessState.READY)
            self.assertTrue(stage.downstream_child_jobs_allowed)

    def test_missing_asr_credential_reports_blocked_external_naming_aa_204(self):
        caps = dict(self.all_ready_caps)
        caps["remote_asr_credential_configured"] = False

        report = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=caps,
            queue_counts=self.sample_queue_counts,
        )
        self.assertEqual(report.overall_state, ReadinessState.BLOCKED_EXTERNAL)
        self.assertFalse(report.is_ready)

        asr_stage = next(s for s in report.stages if s.stage == PipelineStage.REMOTE_ASR)
        self.assertEqual(asr_stage.state, ReadinessState.BLOCKED_EXTERNAL)
        self.assertIn("DP-204", asr_stage.next_action)
        self.assertFalse(asr_stage.downstream_child_jobs_allowed)

    def test_missing_claim_extraction_reports_blocked_external_naming_aa_201_and_no_child_jobs(self):
        caps = dict(self.all_ready_caps)
        caps["claim_extraction_available"] = False

        report = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=caps,
            queue_counts=self.sample_queue_counts,
        )
        self.assertEqual(report.overall_state, ReadinessState.BLOCKED_EXTERNAL)
        self.assertFalse(report.is_ready)

        claim_stage = next(s for s in report.stages if s.stage == PipelineStage.CLAIM_EXTRACTION)
        self.assertEqual(claim_stage.state, ReadinessState.BLOCKED_EXTERNAL)
        self.assertIn("DP-201", claim_stage.next_action)
        self.assertFalse(claim_stage.downstream_child_jobs_allowed)

        # Downstream stages should be deferred, and NOT allow child jobs
        downstream_stages = [
            PipelineStage.EVIDENCE_RETRIEVAL,
            PipelineStage.DETERMINISTIC_VERIFICATION,
            PipelineStage.RELATION_ANALYSIS,
        ]
        for st_enum in downstream_stages:
            stage_info = next(s for s in report.stages if s.stage == st_enum)
            self.assertEqual(stage_info.state, ReadinessState.DEFERRED)
            self.assertFalse(stage_info.downstream_child_jobs_allowed)

    def test_unknown_capability_fails_closed(self):
        caps = dict(self.all_ready_caps)
        caps["speculative_unapproved_ai_scoring"] = True

        report = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=caps,
            queue_counts=self.sample_queue_counts,
        )
        self.assertEqual(report.overall_state, ReadinessState.BLOCKED_EXTERNAL)
        self.assertFalse(report.is_ready)
        self.assertIn("speculative_unapproved_ai_scoring", report.unrecognized_capabilities)
        # Every stage fails closed
        for stage in report.stages:
            self.assertEqual(stage.state, ReadinessState.BLOCKED_EXTERNAL)
            self.assertFalse(stage.downstream_child_jobs_allowed)

    def test_missing_sources_reports_unconfigured(self):
        report = evaluate_collection_readiness(
            configured_sources=[],
            capabilities=self.all_ready_caps,
            queue_counts=self.sample_queue_counts,
        )
        source_stage = next(s for s in report.stages if s.stage == PipelineStage.SOURCE_DISCOVERY)
        self.assertEqual(source_stage.state, ReadinessState.UNCONFIGURED)
        self.assertFalse(source_stage.downstream_child_jobs_allowed)

    def test_output_is_deterministic_across_calls(self):
        caps = {
            "claim_extraction_available": False,
            "remote_asr_credential_configured": True,
            "deterministic_verification_available": True,
            "public_projection_writable": True,
            "evidence_retrieval_available": True,
            "relation_analysis_available": True,
        }
        report1 = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=caps,
            queue_counts={"B": 2, "A": 1},
        )
        report2 = evaluate_collection_readiness(
            configured_sources=self.valid_sources,
            capabilities=caps,
            queue_counts={"A": 1, "B": 2},
        )

        dict1 = report1.to_dict()
        dict2 = report2.to_dict()
        self.assertEqual(dict1, dict2)

        txt1 = format_readiness_report(report1)
        txt2 = format_readiness_report(report2)
        self.assertEqual(txt1, txt2)

    def test_cli_empty_capability_input_exits_nonzero_and_names_blocked(self):
        import io
        from unittest.mock import patch

        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            exit_code = main(["--capabilities-json", "{}"])

        self.assertNotEqual(exit_code, 0)
        output = stdout_buf.getvalue()
        self.assertIn("BLOCKED_EXTERNAL", output)
        self.assertIn("DP-201", output)
        self.assertIn("DP-204", output)


if __name__ == "__main__":
    unittest.main()
