"""DP-359: independent word-boundary acceptance at the private canary seam."""
import hashlib
import json
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.whisperx_alignment_private import AlignmentHold, WordTime
from tools.dp165_alignment_canary import run_canary


class AlignmentReferenceCanaryTests(unittest.TestCase):
    def job(self, *, tolerance=100, baseline=None):
        return SimpleNamespace(
            intervention=SimpleNamespace(official_start_ms=None, transcript_sha256="a" * 64),
            scope=SimpleNamespace(rights_record_id="rights:test", policy_version="v1"),
            manifest_sha256="b" * 64, audio_sha256="c" * 64,
            audio_path="/synthetic.wav", audio_root=Path("/synthetic"),
            duration_seconds=2.0, rights_basis="OWNER_AUTHORIZED",
            rights_receipt_id="rights:test", consent_confirmed=False,
            model_receipt_path=Path("/synthetic-model-receipt.json"),
            source_variant_id="variant", source_segment_id="segment",
            source_variant_sha256="d" * 64, source_segment_sha256="e" * 64,
            language="it", overlap_observed=False, timeout_seconds=120,
            reference_source="https://example.test/licensed-word-annotation",
            reference_sha256="d" * 64, max_boundary_error_ms=tolerance,
            reference_words=baseline if baseline is not None else (
                ("Non", 100, 250), ("aumenteremo", 250, 800),
                ("7", 850, 1000), ("tasse", 1000, 1400)),
        )

    def proposal(self, *, middle_end=800):
        return SimpleNamespace(
            status="REVIEW_CANDIDATE", candidate=SimpleNamespace(
                candidate_id="alignment:fixture", source_kind="UNVERIFIED"),
            blockers=("NUMERAL_REQUIRES_REVIEW",), publication_blocked=True,
            source_span_review_ready=False,
            words=(
                WordTime("Non", 100, 250, .98),
                WordTime("aumenteremo", 250, middle_end, .95),
                WordTime("7", 850, 1000, .93),
                WordTime("tasse.", 1000, 1400, .91)),
            provenance={"alignment_output_sha256": hashlib.sha256(b"test").hexdigest()},
        )

    def exercise(self, job, proposal):
        with patch("tools.dp165_alignment_canary.alignment_authorization_guard",
                   return_value=lambda: None), patch(
                       "tools.dp165_alignment_canary.propose_whisperx_alignment",
                       return_value=proposal):
            return run_canary(job, enabled=False)

    def test_matching_independent_word_times_are_reported_as_measured_not_published(self):
        receipt = self.exercise(self.job(), self.proposal())
        self.assertEqual(receipt["status_kind"], "REVIEW_CANDIDATE")
        self.assertEqual(receipt["reference_sha256"], "d" * 64)
        self.assertEqual(receipt["max_boundary_error_ms"], 0)
        self.assertEqual(receipt["boundary_tolerance_ms"], 100)
        self.assertTrue(receipt["publication_blocked"])
        self.assertFalse(receipt["source_span_review_ready"])

    def test_inexact_word_boundaries_are_held_even_with_good_ctc_scores(self):
        with self.assertRaisesRegex(AlignmentHold, "WHISPERX_REFERENCE_BOUNDARY_MISMATCH"):
            self.exercise(self.job(), self.proposal(middle_end=650))

    def test_inexact_word_identity_is_held_even_with_matching_boundaries(self):
        wrong = (("Non", 100, 250), ("aumenteremo", 250, 800),
                 ("8", 850, 1000), ("tasse", 1000, 1400))
        with self.assertRaisesRegex(AlignmentHold, "WHISPERX_REFERENCE_WORD_MISMATCH"):
            self.exercise(self.job(baseline=wrong), self.proposal())


class ReferenceManifestValidationTests(unittest.TestCase):
    def setUp(self):
        from tests import test_whisperx_alignment_rights as original
        self.fixture = original.AlignmentCanaryTests(
            "test_permitted_attestation_produces_a_private_hold_receipt_only")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_missing_or_forged_reference_fails_closed_before_inference(self):
        for changed in ("missing", "word", "time", "tolerance"):
            with self.subTest(changed=changed):
                manifest = json.loads(json.dumps(self.fixture.manifest))
                if changed == "missing":
                    manifest.pop("reference")
                elif changed == "word":
                    manifest["reference"]["words"][2]["word"] = "8"
                elif changed == "time":
                    manifest["reference"]["words"][1]["end_ms"] = 9000
                else:
                    manifest["reference"]["max_boundary_error_ms"] = 1000
                self.fixture.write(manifest)
                with patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run") as child:
                    code, printed = self.fixture.call("--enabled")
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(printed)["status"], "INVALID_MANIFEST")
                child.assert_not_called()
        self.fixture.write()

    def test_official_locator_still_wins_without_reference_or_model(self):
        manifest = json.loads(json.dumps(self.fixture.manifest))
        manifest.pop("reference")
        manifest["intervention"]["official_start_ms"] = 100
        manifest["intervention"]["official_end_ms"] = 1500
        self.fixture.write(manifest)
        code, printed = self.fixture.call()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(printed)["status"], "OFFICIAL_PRECEDENCE")
        self.assertTrue(json.loads(printed)["publication_blocked"])
        self.fixture.write()



if __name__ == "__main__":
    unittest.main()
