"""DP-419 media derivation is computed from the captured media, not an attestor digest."""
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from dichiarazioni_pubbliche.media_capture_proof import derive_media_capture_segment


class MediaCaptureProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp419-media-proof-")
        self.addCleanup(self.tmp.cleanup)
        self.media = Path(self.tmp.name) / "source.wav"
        with wave.open(str(self.media), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\x00\x01" * (16000 * 4))
        self.digest = hashlib.sha256(self.media.read_bytes()).hexdigest()

    def derive(self, **changes):
        data = dict(
            media_path=self.media, capture_sha256=self.digest,
            content_id="content:one", capture_id="capture:one",
            canonical_segment_id="canonical:one",
            canonical_text_sha256="b" * 64,
            start_ms=1200, end_ms=3400,
        )
        data.update(changes)
        return derive_media_capture_segment(**data)

    def test_real_decoder_binds_capture_digest_and_exact_segment(self):
        result = self.derive()
        self.assertEqual(result["capture_sha256"], self.digest)
        self.assertEqual(result["start_ms"], 1200)
        self.assertEqual(result["end_ms"], 3400)
        self.assertRegex(result["excerpt_pcm_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(result["evidence_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(result["capture_segment_binding"], "DECODED_FROM_CAPTURE")
        self.assertFalse(result["seek_authorized"])
        self.assertFalse(result["publication_authority"])
        self.assertNotIn(str(self.media), str(result))
        self.assertNotIn("source.wav", str(result))
        self.assertEqual(self.derive(), result)

    def test_changed_capture_or_invalid_range_cannot_create_proof(self):
        for changes in (
            {"capture_sha256": "0" * 64},
            {"start_ms": 4500, "end_ms": 4700},
            {"end_ms": 1200},
            {"start_ms": -1},
            {"canonical_text_sha256": "bad"},
            {"canonical_segment_id": "../escape"},
            {"media_path": self.media.with_suffix(".m3u8")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.derive(**changes)

    def test_decoded_excerpts_change_when_time_span_changes(self):
        first = self.derive()
        second = self.derive(start_ms=1700, end_ms=3300)
        self.assertNotEqual(first["evidence_sha256"], second["evidence_sha256"])


if __name__ == "__main__":
    unittest.main()
