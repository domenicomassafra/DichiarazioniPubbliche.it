"""Synthetic, network-free API caption adapter and worker receipt integration tests."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionCapture, CaptionProbe, PlatformAccessRestricted,
    PrivateTranscriptStore, YouTubeResolver,
)
from dichiarazioni_pubbliche.caption_adapter import CaptionSegment  # noqa: E402
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers  # noqa: E402
from dichiarazioni_pubbliche.worker_errors import BlockedJob  # noqa: E402


class TranscriptApiAdapterTests(unittest.TestCase):
    @staticmethod
    def _api_fixture(rows=None, *, generated=False, language="it", error=None):
        rows = rows if rows is not None else [
            {"text": "Testo italiano di prova", "start": 0.25, "duration": 1.5},
            {"text": "Seconda frase", "start": 1.75, "duration": 2.0},
        ]
        fetched = SimpleNamespace(
            language_code=language, is_generated=generated,
            to_raw_data=lambda: rows,
        )
        transcript = SimpleNamespace(
            language_code=language, is_generated=generated,
            fetch=Mock(return_value=fetched),
        )
        tracks = Mock()
        tracks.find_manually_created_transcript.return_value = transcript
        tracks.find_generated_transcript.return_value = transcript
        api = Mock()
        api.list.return_value = tracks
        api.list.side_effect = error
        return api, tracks, transcript

    def test_optional_library_defaults_off_and_does_not_touch_client(self):
        with patch.dict(os.environ, {"DP_YOUTUBE_TRANSCRIPT_API": ""}):
            resolver = YouTubeResolver(transcript_api_factory=lambda: self.fail("called"))
        self.assertFalse(resolver.use_transcript_api)
        existing = CaptionCapture(b"{}", "a" * 64, "ok", "b" * 64,
                                  (CaptionSegment(0, 0, 100, "ok"),), CaptionProbe("manual_caption", "it"))
        with patch.object(resolver, "_capture_yt_dlp_caption", return_value=existing) as fallback:
            self.assertIs(resolver.capture_caption("https://example.test/no-video", existing.probe), existing)
        fallback.assert_called_once()

    def test_pinned_client_limits_hosts_redirects_body_and_timeout(self):
        from dichiarazioni_pubbliche.youtube_transcript_client import (
            TranscriptApiRedirectDenied, new_transcript_client,
        )

        # Default contributor profile has no requests/youtube-transcript-api;
        # exercise the opt-in session policy without installing either donor.
        class FakeSession:
            trust_env = True

            def get(self, url, **kwargs):
                return self.request("GET", url, **kwargs)

            def request(self, method, url, **kwargs):
                raise AssertionError("outbound must be mocked")

        with patch("dichiarazioni_pubbliche.youtube_transcript_client.version", return_value="1.2.4"):
            with patch.dict(sys.modules, {
                "requests": SimpleNamespace(Session=FakeSession),
                "youtube_transcript_api": SimpleNamespace(YouTubeTranscriptApi=lambda http_client: http_client)
            }):
                client = new_transcript_client()
        self.assertFalse(client.trust_env)
        with patch.object(FakeSession, "request") as outbound:
            for url in (
                "http://www.youtube.com/watch?v=AbC123_dEfG",
                "https://www.youtube.com.evil.test/watch",
                "https://www.youtube.com@127.0.0.1/watch",
                "https://www.youtube.com:8443/watch",
                "https://127.0.0.1/watch",
            ):
                with self.subTest(url=url), self.assertRaisesRegex(TranscriptApiRedirectDenied, "URL_NOT_ALLOWED"):
                    client.get(url)
            outbound.assert_not_called()
            # A forged caption URL from donor metadata must not activate yt-dlp
            # after the constrained client rejects it before any outbound HTTP.
            restricted_api = SimpleNamespace(
                list=lambda video_id: client.get("https://foreign.invalid/api/timedtext")
            )
            resolver = YouTubeResolver(
                use_transcript_api=True, transcript_api_factory=lambda: restricted_api,
            )
            with patch.object(resolver, "_capture_yt_dlp_caption") as fallback:
                with self.assertRaisesRegex(PlatformAccessRestricted, "ACCESS_RESTRICTED"):
                    resolver.capture_caption(
                        "https://www.youtube.com/watch?v=AbC123_dEfG",
                        CaptionProbe("manual_caption", "it"),
                    )
                fallback.assert_not_called()
            outbound.assert_not_called()

            allowed_response = Mock()
            allowed_response.status_code = 200
            allowed_response.iter_content.return_value = iter([b'{"ok":true}'])
            outbound.return_value = allowed_response
            result = client.get("https://www.youtube.com/api/timedtext")
            self.assertIs(result, allowed_response)
            self.assertEqual(result._content, b'{"ok":true}')
            self.assertTrue(result._content_consumed)
            allowed_response.close.assert_called_once()
            self.assertEqual(outbound.call_args.kwargs["timeout"], (3.0, 8.0))
            self.assertFalse(outbound.call_args.kwargs["allow_redirects"])
            self.assertTrue(outbound.call_args.kwargs["stream"])

            redirected = Mock(status_code=302)
            outbound.return_value = redirected
            with self.assertRaisesRegex(RuntimeError, "REDIRECT_DENIED"):
                client.get("https://www.youtube.com/watch?v=AbC123_dEfG")
            redirected.close.assert_called_once()

            oversized = Mock()
            oversized.status_code = 200
            oversized.iter_content.return_value = iter([b"x" * (2 * 1024 * 1024 + 1)])
            outbound.return_value = oversized
            with self.assertRaisesRegex(ValueError, "RESPONSE_LIMIT_EXCEEDED"):
                client.get("https://www.youtube.com/watch?v=AbC123_dEfG")
            oversized.close.assert_called_once()

    def test_first_attempt_manual_and_auto_preserves_kind_language_hash_and_raw(self):
        for kind, language, generated in (
            ("manual_caption", "it", False),
            ("automatic_caption", "it-orig", True),
        ):
            with self.subTest(kind=kind):
                api, tracks, transcript = self._api_fixture(generated=generated)
                resolver = YouTubeResolver(use_transcript_api=True,
                                           transcript_api_factory=lambda: api)
                with patch.object(resolver, "_capture_yt_dlp_caption") as fallback:
                    capture = resolver.capture_caption(
                        "https://www.youtube.com/watch?v=AbC123_dEfG", CaptionProbe(kind, language)
                    )
                fallback.assert_not_called()
                api.list.assert_called_once_with("AbC123_dEfG")
                selected = (tracks.find_generated_transcript if generated
                            else tracks.find_manually_created_transcript)
                selected.assert_called_once_with(["it"])
                transcript.fetch.assert_called_once_with(preserve_formatting=False)
                self.assertEqual(capture.probe.kind, kind)
                self.assertEqual(capture.probe.language, language)
                self.assertEqual(capture.provenance["method"], "youtube-transcript-api")
                self.assertEqual(capture.provenance["method_version"], "1.2.4")
                self.assertEqual(capture.segments[0].start_ms, 250)
                self.assertEqual(capture.segments[1].end_ms, 3750)
                self.assertEqual(capture.raw_sha256, hashlib.sha256(capture.raw_bytes).hexdigest())
                self.assertEqual(capture.raw_text_sha256,
                                 hashlib.sha256(capture.raw_text.encode()).hexdigest())
                with tempfile.TemporaryDirectory() as tmp:
                    directory = PrivateTranscriptStore(Path(tmp) / "private").persist_caption(
                        content_id="content:safe", variant_id="variant:safe", capture=capture,
                        receipt={"status": "SUCCESS"},
                    )
                    self.assertEqual(
                        (directory / "caption.raw.youtube-transcript-api.json").read_bytes(),
                        capture.raw_bytes,
                    )
                    self.assertFalse((directory / "caption.raw.json3").exists())
                    receipt = json.loads((directory / "receipt.json").read_text())
                    self.assertEqual(receipt["capture_provenance"]["method_version"], "1.2.4")

    def test_missing_track_timeout_and_time_conflict_fallback_to_json3(self):
        for error in (LookupError("no caption"), TimeoutError("timed out"),
                      ValueError("malformed")):
            with self.subTest(error=error):
                api, _, _ = self._api_fixture(error=error)
                resolver = YouTubeResolver(use_transcript_api=True,
                                           transcript_api_factory=lambda: api)
                existing = CaptionCapture(b"{}", "a" * 64, "ok", "b" * 64,
                                          (CaptionSegment(0, 0, 100, "ok"),), CaptionProbe("manual_caption", "it"))
                with patch.object(resolver, "_capture_yt_dlp_caption", return_value=existing) as fallback:
                    result = resolver.capture_caption(
                        "https://youtu.be/AbC123_dEfG", existing.probe
                    )
                fallback.assert_called_once()
                self.assertEqual(result.provenance["method"], "yt-dlp")
                self.assertEqual(result.provenance["fallback_reason"], type(error).__name__)

        rows = [
            {"text": "Prima", "start": 1, "duration": 2},
            {"text": "Conflitto", "start": 2, "duration": 1},
        ]
        api, _, _ = self._api_fixture(rows)
        resolver = YouTubeResolver(use_transcript_api=True, transcript_api_factory=lambda: api)
        with patch.object(resolver, "_capture_yt_dlp_caption", side_effect=RuntimeError("JSON3 unavailable")):
            with self.assertRaisesRegex(RuntimeError, "JSON3 unavailable"):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", CaptionProbe("manual_caption", "it"))

    def test_platform_denials_never_fallback_to_another_client(self):
        for name in (
            "TooManyRequests", "IpBlocked", "RequestBlocked", "PoTokenRequired",
            "YouTubeRequestFailed", "AgeRestricted", "VideoUnplayable",
            "VideoUnavailable", "FailedToCreateConsentCookie", "TranscriptApiRedirectDenied",
            "HTTPError401", "HTTPError403", "HTTPError429", "HTTPError451",
        ):
            with self.subTest(name=name):
                error = type(name, (Exception,), {})("blocked")
                if name.startswith("HTTPError"):
                    error.response = SimpleNamespace(status_code=int(name.removeprefix("HTTPError")))
                api, _, _ = self._api_fixture(error=error)
                resolver = YouTubeResolver(use_transcript_api=True,
                                           transcript_api_factory=lambda: api)
                with patch.object(resolver, "_capture_yt_dlp_caption") as fallback:
                    with self.assertRaises(PlatformAccessRestricted):
                        resolver.capture_caption(
                            "https://youtu.be/AbC123_dEfG", CaptionProbe("manual_caption", "it")
                        )
                fallback.assert_not_called()

    def test_wrong_language_or_origin_falls_back_without_claiming_success(self):
        api, _, _ = self._api_fixture(language="en")
        resolver = YouTubeResolver(use_transcript_api=True, transcript_api_factory=lambda: api)
        with patch.object(resolver, "_capture_yt_dlp_caption", side_effect=RuntimeError("not found")):
            with self.assertRaises(RuntimeError):
                resolver.capture_caption("https://youtu.be/AbC123_dEfG", CaptionProbe("manual_caption", "it"))

    def test_capture_receipt_records_selected_adapter_in_existing_ledger(self):
        api, _, _ = self._api_fixture()
        capture = YouTubeResolver(use_transcript_api=True,
                                  transcript_api_factory=lambda: api).capture_caption(
                                      "https://youtu.be/AbC123_dEfG", CaptionProbe("manual_caption", "it")
                                  )
        handler = TranscriptAsrJobHandlers()
        handler.store = Mock()
        handler.store.renew.return_value = True
        handler.store.insert_transcript_variant.return_value = ("variant:1", True)
        handler.worker_id = "fixture"
        handler.lease_seconds = 30
        handler.private_store = Mock()
        handler._require_current_ingestion_relevance = Mock()
        handler.resolver = Mock(capture_caption=Mock(return_value=capture))
        job = SimpleNamespace(job_id="job:1", attempt=1,
                              payload={"canonical_url": "https://youtu.be/AbC123_dEfG",
                                       "external_id": "AbC123_dEfG", "caption_kind": "manual_caption",
                                       "caption_language": "it"})
        content = SimpleNamespace(content_id="content:1", source_id="source:1")
        handler.acquire_caption(job, content)
        receipt = handler.store.record_receipt.call_args.kwargs["receipt"]
        metadata = handler.store.insert_transcript_variant.call_args.kwargs["metadata"]
        self.assertEqual(receipt["access_path"], "YOUTUBE_TRANSCRIPT_API_PUBLIC_CAPTION")
        self.assertEqual(receipt["capture_provenance"]["method_version"], "1.2.4")
        self.assertEqual(metadata["capture_provenance"], capture.provenance)
        self.assertEqual(handler.store.record_receipt.call_args.kwargs["billing_basis"], "ZERO_COST")

    def test_blocked_upstream_creates_hold_receipt_without_retry_or_download(self):
        handler = TranscriptAsrJobHandlers()
        handler.store = Mock()
        handler.store.renew.return_value = True
        handler.worker_id = "fixture"
        handler.lease_seconds = 30
        handler._require_current_ingestion_relevance = Mock()
        handler.resolver = Mock(capture_caption=Mock(side_effect=PlatformAccessRestricted("blocked")))
        job = SimpleNamespace(job_id="job:blocked", attempt=1,
                              payload={"canonical_url": "https://youtu.be/AbC123_dEfG",
                                       "external_id": "AbC123_dEfG", "caption_kind": "manual_caption",
                                       "caption_language": "it"})
        with self.assertRaisesRegex(BlockedJob, "YOUTUBE_CAPTION_ACCESS_RESTRICTED"):
            handler.acquire_caption(job, SimpleNamespace(content_id="content:blocked"))
        written = handler.store.record_receipt.call_args.kwargs
        self.assertEqual(written["status"], "ACCESS_RESTRICTED")
        self.assertEqual(written["receipt"]["access_path"],
                         "YOUTUBE_TRANSCRIPT_API_PUBLIC_CAPTION")
        handler.store.insert_transcript_variant.assert_not_called()

    def test_secondary_yt_dlp_429_holds_with_correct_provider_receipt(self):
        handler = TranscriptAsrJobHandlers()
        handler.store = Mock()
        handler.store.renew.return_value = True
        handler.worker_id = "fixture"
        handler.lease_seconds = 30
        handler._require_current_ingestion_relevance = Mock()
        handler.resolver = YouTubeResolver(
            use_transcript_api=False, use_transcript_api_secondary=True,
            transcript_api_factory=lambda: self.fail("API must not bypass 429"),
        )
        job = SimpleNamespace(
            job_id="job:429", attempt=1,
            payload={"canonical_url": "https://youtu.be/AbC123_dEfG",
                     "external_id": "AbC123_dEfG", "caption_kind": "manual_caption",
                     "caption_language": "it"},
        )
        blocked = SimpleNamespace(returncode=1, stderr="HTTP Error 429 Too Many Requests", stdout="")
        with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                   return_value=blocked) as process:
            with self.assertRaisesRegex(BlockedJob, "YOUTUBE_CAPTION_ACCESS_RESTRICTED"):
                handler.acquire_caption(job, SimpleNamespace(content_id="content:429"))
        process.assert_called_once()
        receipt = handler.store.record_receipt.call_args.kwargs
        self.assertEqual(receipt["status"], "ACCESS_RESTRICTED")
        self.assertEqual(receipt["receipt"]["access_path"], "YT_DLP_PUBLIC_CAPTION")
        self.assertEqual(receipt["receipt"]["capture_provenance"]["method"], "yt-dlp")
        self.assertEqual(receipt["receipt"]["youtube_data_api_v3_quota_units"], 0)
        handler.store.insert_transcript_variant.assert_not_called()

    def test_secondary_does_not_downgrade_server_failure_to_missing_captions(self):
        resolver = YouTubeResolver(
            use_transcript_api=False, use_transcript_api_secondary=True,
            transcript_api_factory=lambda: self.fail("ambiguous failure must not fall back"),
        )
        diagnostic = "ERROR: HTTP Error 500: Internal Server Error\nWARNING: no subtitles available"
        with patch("dichiarazioni_pubbliche.youtube_caption_ytdlp.subprocess.run",
                   return_value=SimpleNamespace(returncode=1, stderr=diagnostic, stdout="")) as process:
            with self.assertRaisesRegex(RuntimeError, "YT_DLP_CAPTION_CAPTURE_FAILED") as held:
                resolver.capture_caption("https://youtu.be/AbC123_dEfG",
                                         CaptionProbe("manual_caption", "it"))
        self.assertIn("HTTP Error 500", str(held.exception.__cause__))
        process.assert_called_once()
