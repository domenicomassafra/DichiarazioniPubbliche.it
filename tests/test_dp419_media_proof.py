"""DP-419 media derivation is computed from the captured media, not an attestor digest."""
import hashlib
import subprocess
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

    def test_audio_mp4_container_is_hash_pinned_and_decoded(self):
        mp4 = self.media.with_suffix(".m4a")
        encoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(self.media),
             "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart",
             "-f", "mp4", str(mp4)],
            capture_output=True, check=False, timeout=20,
        )
        if encoded.returncode != 0:
            self.skipTest("ffmpeg AAC/MP4 encoder is unavailable")
        digest = hashlib.sha256(mp4.read_bytes()).hexdigest()
        result = self.derive(
            media_path=mp4, capture_sha256=digest,
            canonical_text_sha256="c" * 64,
        )
        self.assertEqual(result["capture_sha256"], digest)
        self.assertEqual((result["start_ms"], result["end_ms"]), (1200, 3400))
        self.assertEqual(result["capture_segment_binding"], "DECODED_FROM_CAPTURE")

    def test_audio_mp4_type_rejects_video_streams(self):
        media_with_video = self.media.with_suffix(".video.m4a")
        encoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi",
             "-i", "color=c=black:s=16x16:d=4", "-i", str(self.media),
             "-shortest", "-c:v", "mpeg4", "-c:a", "aac", "-b:a", "64k",
             "-movflags", "+faststart", "-f", "mp4", str(media_with_video)],
            capture_output=True, check=False, timeout=20,
        )
        if encoded.returncode != 0:
            self.skipTest("ffmpeg test video encoder is unavailable")
        digest = hashlib.sha256(media_with_video.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "MEDIA_PROOF_AUDIO_CONTAINER_INVALID"):
            self.derive(
                media_path=media_with_video, capture_sha256=digest,
                canonical_text_sha256="d" * 64,
            )


if __name__ == "__main__":
    unittest.main()
