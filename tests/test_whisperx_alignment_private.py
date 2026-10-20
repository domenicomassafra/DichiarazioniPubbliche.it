"""DP-165: synthetic seam contracts; no real model/audio acquisitions."""
import hashlib
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dichiarazioni_pubbliche.parliamentary_alignment import (
    MediaSegment, ParliamentaryIntervention, align_parliamentary_intervention,
)
from dichiarazioni_pubbliche.transcript_contract import TranscriptCandidate
from dichiarazioni_pubbliche.whisperx_alignment_private import (
    AlignmentHold, _parse_words, _receipt, propose_whisperx_alignment,
)

TEXT = "Non aumenteremo 7 tasse."
WORDS = [
    {"word": "Non", "start": .10, "end": .25, "score": .98},
    {"word": "aumenteremo", "start": .25, "end": .80, "score": .95},
    {"word": "7", "start": .85, "end": 1.0, "score": .93},
    {"word": "tasse.", "start": 1.0, "end": 1.4, "score": .91},
]


def intervention(**changes):
    values = dict(intervention_id="i1", session_id="s1",
                  official_speaker_ref="ref", official_speaker_name="Demo",
                  transcript_text=TEXT, source_url="https://example.org/",
                  source_version="v1", speaker_resolution_approved=False)
    values.update(changes)
    return ParliamentaryIntervention(**values)


class WhisperxPrivateAlignmentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio = self.root / "audio"
        self.audio.mkdir()
        self.wav = self.audio / "clip.wav"
        with wave.open(str(self.wav), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 32000)
        self.audio_hash = hashlib.sha256(self.wav.read_bytes()).hexdigest()
        self.model = self.root / "model"
        self.model.mkdir()
        files = {}
        for name, content in (("config.json", b"{}"), ("model.safetensors", b"weights"),
                              ("LICENSE", b"fixture license")):
            path = self.model / name
            path.write_bytes(content)
            files[name] = hashlib.sha256(content).hexdigest()
        self.receipt = self.root / "receipt.json"
        self.manifest = dict(
            model_id="synthetic/local-italian-wav2vec2", revision="a" * 40,
            model_dir=str(self.model), license_spdx="Apache-2.0",
            license_source_url="https://example.org/license/fixture",
            license_reviewed=True, native_notices_reviewed=True, files=files)
        self.receipt.write_text(json.dumps(self.manifest))
        self.kwargs = dict(
            audio_path=str(self.wav), audio_root=self.audio,
            audio_sha256=self.audio_hash, duration_seconds=2.0,
            rights_basis="OWNER_AUTHORIZED", rights_receipt_id="rights:fixture:0001",
            authorization=True, consent_confirmed=False,
            model_receipt_path=self.receipt, source_variant_id="variant-fixture",
            source_segment_id="segment-fixture",
            source_variant_sha256="a" * 64, source_segment_sha256="b" * 64)

    def _run(self, *, output=None, overlap=False, rows=()):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({
            "word_segments": WORDS if output is None else output}))
        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED": "1"}):
            with patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                       return_value="Linux"):
                with patch("dichiarazioni_pubbliche.whisperx_alignment_private.importlib.metadata.version",
                           return_value="3.8.6"):
                    with patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run",
                               return_value=result) as command:
                        proposal = propose_whisperx_alignment(
                            intervention(), segments=rows,
                            overlap_observed=overlap, **self.kwargs)
        return proposal, command

    def test_word_times_and_unverified_candidate(self):
        proposal, command = self._run()
        self.assertEqual(proposal.status, "REVIEW_CANDIDATE")
        self.assertEqual([(w.start_ms, w.end_ms) for w in proposal.words],
                         [(100, 250), (250, 800), (850, 1000), (1000, 1400)])
        self.assertIsInstance(proposal.candidate, TranscriptCandidate)
        self.assertEqual(proposal.candidate.text, TEXT)
        self.assertEqual(proposal.candidate.source_kind, "UNVERIFIED")
        self.assertTrue(proposal.publication_blocked)
        self.assertFalse(proposal.source_span_review_ready)
        self.assertIn("NUMERAL_REQUIRES_REVIEW", proposal.blockers)
        self.assertEqual(proposal.provenance["audio_sha256"], self.audio_hash)
        self.assertEqual(proposal.provenance["source_segment_sha256"], "b" * 64)
        self.assertEqual(command.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")

    def test_official_locator_wins_without_model_or_rights(self):
        self.kwargs.update(authorization=False, model_receipt_path=Path("/absent"))
        with patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run") as child:
            proposal = propose_whisperx_alignment(
                intervention(official_start_ms=40, official_end_ms=1500), **self.kwargs)
        self.assertEqual(proposal.status, "OFFICIAL_PRECEDENCE")
        self.assertEqual(proposal.fallback.method, "OFFICIAL_MEDIA_RANGE")
        self.assertIsNone(proposal.candidate)
        child.assert_not_called()

    def test_text_baseline_and_overlap_hold(self):
        row = MediaSegment("segment-fixture", 0, 2000, TEXT, "media-v1")
        baseline = align_parliamentary_intervention(intervention(), [row])
        proposal, _ = self._run(overlap=True, rows=(row,))
        self.assertEqual(baseline.status, "REVIEW_CANDIDATE")
        self.assertEqual(proposal.fallback, baseline)
        self.assertIn("OVERLAPPING_SPEECH_REQUIRES_REVIEW", proposal.blockers)

    def test_missing_opt_in_rights_and_model_are_held(self):
        with patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run") as child:
            with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED": "0"}):
                with self.assertRaisesRegex(AlignmentHold, "OPT_IN"):
                    propose_whisperx_alignment(intervention(), **self.kwargs)
            with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED": "1"}):
                with patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                           return_value="Linux"):
                    with self.assertRaisesRegex(AlignmentHold, "RIGHTS_UNVERIFIED"):
                        propose_whisperx_alignment(
                            intervention(), **{**self.kwargs, "authorization": False})
                    with self.assertRaisesRegex(AlignmentHold, "RECEIPT_MISSING"):
                        propose_whisperx_alignment(
                            intervention(), **{**self.kwargs,
                                                "model_receipt_path": self.root / "missing"})
        child.assert_not_called()

    def test_model_license_and_hash_enforced(self):
        self.manifest["native_notices_reviewed"] = False
        self.receipt.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(AlignmentHold, "RIGHTS_UNVERIFIED"):
            _receipt(self.receipt)
        self.manifest["native_notices_reviewed"] = True
        self.receipt.write_text(json.dumps(self.manifest))
        (self.model / "model.safetensors").write_bytes(b"changed")
        with self.assertRaisesRegex(AlignmentHold, "HASH_MISMATCH"):
            _receipt(self.receipt)

    def test_unscored_unaligned_and_low_confidence_words_held(self):
        for bad in ({**WORDS[2], "score": None}, {**WORDS[2], "end": None},
                    {**WORDS[2], "score": .15}):
            with self.subTest(bad=bad):
                rows = [*WORDS]
                rows[2] = bad
                with self.assertRaises(AlignmentHold):
                    _parse_words({"word_segments": rows}, text=TEXT, duration_ms=2000)

    def test_negation_number_drift_overlap_and_extra_words(self):
        wrong = [
            [{**WORDS[0], "word": "Sì"}, *WORDS[1:]],
            [WORDS[0], WORDS[1], {**WORDS[2], "word": "8"}, WORDS[3]],
            [*WORDS[:2], {**WORDS[2], "start": .4}, WORDS[3]],
            [*WORDS[:3], {**WORDS[3], "end": 4.0}],
            [*WORDS, WORDS[-1]],
            WORDS[1:],
        ]
        for rows in wrong:
            with self.subTest(rows=rows):
                with self.assertRaises(AlignmentHold):
                    _parse_words({"word_segments": rows}, text=TEXT, duration_ms=2000)


if __name__ == "__main__":
    unittest.main()
