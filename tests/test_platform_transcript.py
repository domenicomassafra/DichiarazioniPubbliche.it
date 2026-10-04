import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionCapture,
    CaptionProbe,
    PrivateTranscriptStore,
    VideoCandidate,
    choose_video_candidate,
)
from dichiarazioni_pubbliche.caption_adapter import CaptionSegment  # noqa: E402


class PlatformTranscriptTests(unittest.TestCase):
    def test_episode_marker_beats_translated_title(self):
        candidates = [
            VideoCandidate(
                "wrong",
                "RESPONDING to SHY. | Pulp Special #19",
                "https://example.test/wrong",
            ),
            VideoCandidate(
                "right",
                "RESPONDING to SHY. | Pulp Special #20",
                "https://example.test/right",
            ),
        ]
        chosen = choose_video_candidate(
            "RISPONDIAMO a SHY | Pulp Special #20",
            candidates,
        )
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.video_id, "right")

    def test_weak_title_match_fails_closed(self):
        chosen = choose_video_candidate(
            "Completely unrelated episode",
            [
                VideoCandidate(
                    "x",
                    "Another topic entirely",
                    "https://example.test/x",
                )
            ],
        )
        self.assertIsNone(chosen)

    def test_private_store_is_private_and_retains_raw_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private"
            capture = CaptionCapture(
                raw_bytes=json.dumps({"events": []}).encode(),
                raw_sha256="a" * 64,
                raw_text="Il valore è 10.",
                raw_text_sha256="b" * 64,
                segments=(CaptionSegment(0, 0, 1000, "Il valore è 10."),),
                probe=CaptionProbe("automatic_caption", "it-orig"),
            )
            directory = PrivateTranscriptStore(root).persist_caption(
                content_id="content:test",
                variant_id="transcript:test",
                capture=capture,
                receipt={"status": "SUCCESS"},
            )
            for name in ("caption.raw.json3", "segments.json", "receipt.json"):
                path = directory / name
                self.assertTrue(path.is_file())
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(directory).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(root).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(root / "transcripts").st_mode & 0o777, 0o700)

    def test_raw_caption_versions_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PrivateTranscriptStore(Path(tmp) / "private")
            first = CaptionCapture(
                raw_bytes=b'{"version":1}',
                raw_sha256="a" * 64,
                raw_text="stesso testo",
                raw_text_sha256="c" * 64,
                segments=(CaptionSegment(0, 0, 1000, "stesso testo"),),
                probe=CaptionProbe("automatic_caption", "it-orig"),
            )
            second = CaptionCapture(
                raw_bytes=b'{"version":2}',
                raw_sha256="b" * 64,
                raw_text="stesso testo",
                raw_text_sha256="c" * 64,
                segments=(CaptionSegment(0, 0, 1000, "stesso testo"),),
                probe=CaptionProbe("automatic_caption", "it-orig"),
            )
            left = store.persist_caption(
                content_id="content:test",
                variant_id="transcript:same-text",
                capture=first,
                receipt={"capture": 1},
            )
            right = store.persist_caption(
                content_id="content:test",
                variant_id="transcript:same-text",
                capture=second,
                receipt={"capture": 2},
            )
            self.assertNotEqual(left, right)
            self.assertEqual((left / "caption.raw.json3").read_bytes(), first.raw_bytes)
            self.assertEqual((right / "caption.raw.json3").read_bytes(), second.raw_bytes)


if __name__ == "__main__":
    unittest.main()
