import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionCapture,
    CaptionProbe,
    PrivateTranscriptStore,
    VideoCandidate,
    YouTubeResolver,
    _series_episode,
    _title_score,
    choose_video_candidate,
)
from dichiarazioni_pubbliche.caption_adapter import CaptionSegment  # noqa: E402
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers  # noqa: E402


class PlatformTranscriptTests(unittest.TestCase):
    def test_episode_marker_parses_series_number_and_spacing(self):
        cases = {
            "Pulp Podcast #111 - Titolo": ("pulp podcast", 111),
            "PULP   pOdCaSt  #  111 | Titolo": ("pulp podcast", 111),
            "PulpPodcast#111": ("pulp podcast", 111),
            "Pulp Special #20": ("pulp special", 20),
            "PULP  SPECIAL # 20": ("pulp special", 20),
            "Pulpland #9": ("pulpland", 9),
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(_series_episode(title), expected)
        self.assertIsNone(_series_episode("Pulp Podcast senza numero"))

    def test_matching_episode_beats_more_similar_wrong_episode(self):
        title = "Pulp Podcast #111 - Titolo"
        wrong = VideoCandidate(
            "wrong", "Pulp Podcast #112 - Titolo", "https://example.test/wrong"
        )
        right = VideoCandidate(
            "right", "Pulp Podcast #111 - Extra", "https://example.test/right"
        )
        self.assertGreater(_title_score(title, wrong.title), _title_score(title, right.title))
        self.assertEqual(choose_video_candidate(title, [wrong, right]), right)

    def test_no_episode_match_fails_closed_for_known_discordant_candidates(self):
        candidates = [
            VideoCandidate("wrong-112", "Pulp Podcast #112 - Titolo", "https://example.test/112"),
            VideoCandidate("wrong-110", "Pulp Podcast #110 - Titolo", "https://example.test/110"),
            VideoCandidate(
                "wrong-series", "Pulp Special #111 - Titolo", "https://example.test/special"
            ),
        ]
        self.assertIsNone(choose_video_candidate("Pulp Podcast #111 - Titolo", candidates))
        self.assertIsNone(choose_video_candidate("Pulp Podcast #111 - Titolo", candidates[:1]))

    def test_spaced_case_insensitive_episode_beats_fuzzy(self):
        wrong = VideoCandidate("wrong", "Pulp Special #21", "https://example.test/wrong")
        right = VideoCandidate("right", "PULP  SPECIAL  # 20", "https://example.test/right")
        self.assertEqual(choose_video_candidate("Pulp Special #20", [wrong, right]), right)

    def test_no_episode_marker_keeps_threshold_fuzzy_fallback(self):
        close = VideoCandidate("close", "Pulp Podcast intervista speciale", "https://example.test/close")
        far = VideoCandidate("far", "Intervista completamente diversa", "https://example.test/far")
        self.assertEqual(
            choose_video_candidate("Pulp Podcast intervista speciale", [far, close]),
            close,
        )
        self.assertIsNone(choose_video_candidate("Pulp Podcast intervista speciale", [far]))

    def test_worker_podcast_resolution_does_not_persist_discordant_episode(self):
        handler = TranscriptAsrJobHandlers()
        handler.store = Mock()
        handler._source = Mock(return_value={"id": "podcast", "channel_url": "unused"})
        handler._require_current_ingestion_relevance = Mock()
        handler._enqueue_asr = Mock()
        handler._probe_and_enqueue_caption = Mock()
        handler.resolver = YouTubeResolver()
        content = SimpleNamespace(
            source_id="podcast",
            content_id="content:111",
            title="Pulp Podcast #111 - Titolo",
            canonical_url="https://example.test/audio.mp3",
        )
        job = SimpleNamespace(payload={"platform": "podcast_rss"})
        wrong = VideoCandidate("wrong", "Pulp Podcast #112 - Titolo", "https://example.test/wrong")
        with patch.object(handler.resolver, "_atom_candidates", return_value=[wrong]), patch.object(
            handler.resolver, "_flat_candidates", return_value=[]
        ):
            handler.resolve_platform(job, content)
        handler.store.upsert_locator.assert_not_called()
        handler._probe_and_enqueue_caption.assert_not_called()
        handler._enqueue_asr.assert_called_once_with(content, reason="PLATFORM_COPY_NOT_FOUND")

        handler.store.reset_mock()
        handler._enqueue_asr.reset_mock()
        handler._probe_and_enqueue_caption.reset_mock()
        right = VideoCandidate(
            "right", "Pulp Podcast #111 - Extra", "https://example.test/right"
        )
        with patch.object(
            handler.resolver, "_atom_candidates", return_value=[wrong, right]
        ):
            handler.resolve_platform(job, content)
        handler.store.upsert_locator.assert_called_once_with(
            content.content_id,
            platform="youtube",
            external_id="right",
            canonical_url=right.canonical_url,
            metadata={"resolved_from": "podcast_rss"},
        )
        handler._probe_and_enqueue_caption.assert_called_once_with(job, content, right)
        handler._enqueue_asr.assert_not_called()

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
