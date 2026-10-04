import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.caption_adapter import Chapter  # noqa: E402
from dichiarazioni_pubbliche.longform_prepare import (  # noqa: E402
    build_candidate_windows,
    prepare_longform_caption,
)
from dichiarazioni_pubbliche.caption_adapter import parse_youtube_json3  # noqa: E402


class LongformPrepareTests(unittest.TestCase):
    def _payload(self):
        return {
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 4000,
                    "segs": [{"utf8": "Il valore è 10 milioni di euro."}],
                },
                {
                    "tStartMs": 5000,
                    "dDurationMs": 4000,
                    "segs": [{"utf8": "Seconda frase dichiarativa."}],
                },
                {
                    "tStartMs": 50000,
                    "dDurationMs": 4000,
                    "segs": [{"utf8": "Nuovo capitolo con una tesi."}],
                },
            ]
        }

    def test_windows_split_on_chapter_boundary(self):
        segments = parse_youtube_json3(self._payload())
        windows = build_candidate_windows(
            segments,
            chapters=[Chapter(0, "A"), Chapter(45, "B")],
            max_window_seconds=60,
        )
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].chapter_index, 0)
        self.assertEqual(windows[1].chapter_index, 1)

    def test_public_scaffold_contains_no_transcript_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            caption = root / "caption.json3"
            caption.write_text(json.dumps(self._payload(), ensure_ascii=False))
            private_dir = root / "private"
            public = root / "public.json"
            scaffold = prepare_longform_caption(
                caption_path=caption,
                private_dir=private_dir,
                public_output=public,
                source_id="source",
                external_id="video",
                canonical_url="https://example.invalid/video",
                title="Example",
                published_at="2026-09-22",
                chapters=[Chapter(0, "A"), Chapter(45, "B")],
                registry_caption_sha256="0" * 64,
            )
            public_text = public.read_text()
            self.assertNotIn("10 milioni", public_text)
            self.assertNotIn(str(private_dir), public_text)
            self.assertIn('"sensitive_signature": [', public_text)
            self.assertIn('"NUMBER"', public_text)
            self.assertEqual(scaffold["claims"], [])
            self.assertEqual(scaffold["findings"], [])
            self.assertEqual(scaffold["pipeline"]["claim_extraction"], "BLOCKED")
            self.assertTrue((private_dir / "youtube-auto-it-orig.segments.json").is_file())
            self.assertIn(
                "10 milioni",
                (private_dir / "youtube-auto-it-orig.segments.json").read_text(),
            )

    def test_caption_capture_drift_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            caption = root / "caption.json3"
            caption.write_text(json.dumps(self._payload()))
            scaffold = prepare_longform_caption(
                caption_path=caption,
                private_dir=root / "private",
                public_output=root / "public.json",
                source_id="source",
                external_id="video",
                canonical_url="https://example.invalid/video",
                title="Example",
                published_at="2026-09-22",
                registry_caption_sha256="0" * 64,
            )
            self.assertFalse(
                scaffold["transcript_provenance"]["source_mutability"][
                    "matches_registry_proof"
                ]
            )


if __name__ == "__main__":
    unittest.main()
