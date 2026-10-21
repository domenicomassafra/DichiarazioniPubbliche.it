import hashlib
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
    PlatformAccessRestricted,
    PrivateTranscriptStore,
    VideoCandidate,
    YouTubeResolver,
    _series_episode,
    _title_score,
    choose_video_candidate,
)
from dichiarazioni_pubbliche.caption_adapter import CaptionSegment  # noqa: E402
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers  # noqa: E402
from dichiarazioni_pubbliche.worker_errors import BlockedJob  # noqa: E402


class PlatformTranscriptTests(unittest.TestCase):
    @staticmethod
    def _second_api_fixture(*, generated=False, error=None):
        rows = [{"text": "Italiano", "start": 0.25, "duration": 1.5},
                {"text": "Ancora", "start": 1.75, "duration": 2.0}]
        fetched = SimpleNamespace(
            language_code="it", is_generated=generated, to_raw_data=lambda: rows,
        )
        track = SimpleNamespace(
            language_code="it", is_generated=generated,
            fetch=Mock(return_value=fetched),
        )
        available = Mock()
        available.find_manually_created_transcript.return_value = track
        available.find_generated_transcript.return_value = track
        api = Mock()
        api.list.return_value = available
        api.list.side_effect = error
        return api, available, track

    def test_second_path_is_opt_in_and_cannot_duplicate_first_api_attempt(self):
        with patch.dict(os.environ, {
            "DP_YOUTUBE_TRANSCRIPT_API": "", "DP_YOUTUBE_TRANSCRIPT_API_SECONDARY": "",
        }):
            self.assertFalse(YouTubeResolver().use_transcript_api_secondary)
        with patch.dict(os.environ, {
            "DP_YOUTUBE_TRANSCRIPT_API": "", "DP_YOUTUBE_TRANSCRIPT_API_SECONDARY": "1",
        }):
            self.assertTrue(YouTubeResolver().use_transcript_api_secondary)
        with self.assertRaisesRegex(ValueError, "TRANSCRIPT_API_MODES_CONFLICT"):
            YouTubeResolver(use_transcript_api=True, use_transcript_api_secondary=True)

    def test_second_path_recovers_missing_json3_preserving_selected_track_and_receipt(self):
        for kind, language, generated in (
            ("manual_caption", "it", False),
            ("automatic_caption", "it-orig", True),
        ):
            with self.subTest(kind=kind):
                api, available, track = self._second_api_fixture(generated=generated)
                resolver = YouTubeResolver(
                    use_transcript_api=False, use_transcript_api_secondary=True,
                    transcript_api_factory=lambda: api,
                )
                probe = CaptionProbe(kind, language)
                with patch.object(resolver, "_capture_yt_dlp_caption",
                                  side_effect=RuntimeError("no subtitles available")) as primary:
                    capture = resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)
                primary.assert_called_once()
                api.list.assert_called_once_with("AbC123_dEfG")
                finder = (available.find_generated_transcript if generated else
                          available.find_manually_created_transcript)
                finder.assert_called_once_with(["it"])
                track.fetch.assert_called_once_with(preserve_formatting=False)
                self.assertEqual(capture.probe, probe)
                self.assertEqual(capture.segments[0].start_ms, 250)
                self.assertEqual(capture.segments[1].end_ms, 3750)
                self.assertEqual(capture.raw_sha256, hashlib.sha256(capture.raw_bytes).hexdigest())
                self.assertEqual(capture.raw_text_sha256, hashlib.sha256(capture.raw_text.encode()).hexdigest())
                self.assertEqual(capture.provenance["method"], "youtube-transcript-api")
                self.assertEqual(capture.provenance["method_version"], "1.2.4")
                self.assertEqual(capture.provenance["prior_method"], "yt-dlp")
                self.assertEqual(capture.provenance["fallback_reason"], "YT_DLP_CAPTION_UNAVAILABLE")

    def test_second_path_does_not_repeat_on_success_or_donor_no_captions(self):
        api, _, _ = self._second_api_fixture(error=LookupError("no captions"))
        resolver = YouTubeResolver(use_transcript_api=False,
                                   use_transcript_api_secondary=True,
                                   transcript_api_factory=lambda: api)
        successful = CaptionCapture(
            b"{}", hashlib.sha256(b"{}").hexdigest(), "ok",
            hashlib.sha256(b"ok").hexdigest(), (CaptionSegment(0, 0, 100, "ok"),),
            CaptionProbe("manual_caption", "it"),
        )
        with patch.object(resolver, "_capture_yt_dlp_caption", return_value=successful) as primary:
            self.assertIs(resolver.capture_caption("https://youtu.be/AbC123_dEfG", successful.probe), successful)
        primary.assert_called_once()
        api.list.assert_not_called()
        with patch.object(resolver, "_capture_yt_dlp_caption",
                          side_effect=RuntimeError("no captions")) as primary:
            with self.assertRaises(LookupError):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", successful.probe)
        primary.assert_called_once()
        api.list.assert_called_once()

    def test_missing_yt_dlp_binary_receipt_explains_the_different_recovery(self):
        api, _, _ = self._second_api_fixture()
        resolver = YouTubeResolver(use_transcript_api=False,
                                   use_transcript_api_secondary=True,
                                   transcript_api_factory=lambda: api)
        with patch.object(resolver, "_capture_yt_dlp_caption", side_effect=FileNotFoundError()):
            capture = resolver.capture_caption("https://youtu.be/AbC123_dEfG",
                                               CaptionProbe("manual_caption", "it"))
        self.assertEqual(capture.provenance["fallback_reason"], "YT_DLP_CLIENT_MISSING")
        api.list.assert_called_once()

    def test_secondary_uses_real_json3_failure_classification_without_network(self):
        api, _, _ = self._second_api_fixture()
        resolver = YouTubeResolver(use_transcript_api=False,
                                   use_transcript_api_secondary=True,
                                   transcript_api_factory=lambda: api)
        with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                   return_value=SimpleNamespace(returncode=1, stderr="no subtitles available", stdout="")) as primary:
            result = resolver.capture_caption("https://youtu.be/AbC123_dEfG",
                                              CaptionProbe("manual_caption", "it"))
        primary.assert_called_once()
        self.assertIn("--ignore-config", primary.call_args.args[0])
        self.assertEqual(primary.call_args.args[0][primary.call_args.args[0].index("--proxy") + 1], "")
        self.assertEqual(result.provenance["fallback_reason"], "YT_DLP_CAPTION_UNAVAILABLE")
        api.list.assert_called_once()

        # An invalid HTTP body might be a consent/challenge response, not a
        # missing subtitle; another network client must not be started.
        with patch.object(resolver, "_capture_yt_dlp_caption",
                          side_effect=json.JSONDecodeError("bad", "<html>", 0)):
            with self.assertRaises(json.JSONDecodeError):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG",
                                         CaptionProbe("manual_caption", "it"))
        api.list.assert_called_once()

    def test_second_path_holds_yt_dlp_429_consent_and_ambiguous_failures(self):
        resolver = YouTubeResolver(use_transcript_api=False,
                                   use_transcript_api_secondary=True,
                                   transcript_api_factory=lambda: self.fail("API bypass"))
        probe = CaptionProbe("manual_caption", "it")
        for reason in (
            "HTTP Error 401 Unauthorized", "HTTP Error 403 Forbidden",
            "HTTP Error 429 Too Many Requests", "IP blocked",
            "Sign in to confirm you're not a bot", "Consent required",
            "video unavailable", "no captions; CAPTCHA challenge",
            "HTTP Error 429 Too Many Requests\nno subtitles available",
        ):
            with self.subTest(reason=reason):
                response = SimpleNamespace(returncode=1, stderr=reason, stdout="")
                with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                           return_value=response) as process:
                    with self.assertRaises(PlatformAccessRestricted) as ctx:
                        resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)
                self.assertEqual(ctx.exception.access_path, "YT_DLP_PUBLIC_CAPTION")
                process.assert_called_once()
        with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                   return_value=SimpleNamespace(returncode=1, stderr="no subtitles",
                                                stdout="HTTP Error 403 Forbidden")):
            with self.assertRaises(PlatformAccessRestricted):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)
        with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                   return_value=SimpleNamespace(returncode=0, stderr="HTTP Error 429 Too Many Requests",
                                                stdout="no subtitles")):
            with self.assertRaises(PlatformAccessRestricted):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)
        with patch.object(resolver, "_capture_yt_dlp_caption",
                          side_effect=RuntimeError("Expected one JSON3 caption, found 2")):
            with self.assertRaisesRegex(RuntimeError, "found 2"):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)
        for failure in (RuntimeError("unclassified provider failure"),
                        RuntimeError("remote server unavailable")):
            with patch.object(resolver, "_capture_yt_dlp_caption", side_effect=failure):
                with self.assertRaises(RuntimeError):
                    resolver.capture_caption("https://youtu.be/AbC123_dEfG", probe)

        with patch.object(resolver, "_capture_yt_dlp_caption") as primary:
            with self.assertRaisesRegex(ValueError, "TRANSCRIPT_API_UNTRUSTED_URL"):
                resolver.capture_caption("https://foreign.invalid/watch?v=AbC123_dEfG", probe)
            primary.assert_not_called()

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

    def test_worker_podcast_without_approved_association_never_falls_back_to_asr(self):
        handler = TranscriptAsrJobHandlers()
        handler.store = Mock()
        handler.registry = {"schema_version": 1, "sources": []}
        handler._source = Mock(return_value={"id": "podcast", "kind": "podcast_rss"})
        handler._require_current_ingestion_relevance = Mock()
        handler._enqueue_asr = Mock()
        handler._probe_and_enqueue_caption = Mock()
        handler.resolver = YouTubeResolver()
        content = SimpleNamespace(
            source_id="podcast", content_id="content:111",
            title="Pulp Podcast #111 - Titolo",
            canonical_url="https://example.test/audio.mp3",
        )
        job = SimpleNamespace(payload={"platform": "podcast_rss"})
        with patch("dichiarazioni_pubbliche.platform_transcript.fetch_text") as fetch:
            with self.assertRaisesRegex(BlockedJob, "SOURCE_ASSOCIATION_POLICY_MISSING"):
                handler.resolve_platform(job, content)
        fetch.assert_not_called()
        handler.store.upsert_locator.assert_not_called()
        handler._probe_and_enqueue_caption.assert_not_called()
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
