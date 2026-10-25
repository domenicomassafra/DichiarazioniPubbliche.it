"""DP-432: public YouTube caption acquisition follows DStack's audited order."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.caption_adapter import CaptionSegment
from dichiarazioni_pubbliche.platform_transcript import (
    CaptionCapture, CaptionProbe, PrivateTranscriptStore, YouTubeResolver,
)
from dichiarazioni_pubbliche.queue_runtime import ContentRecord
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers
from dichiarazioni_pubbliche.worker_errors import BlockedJob


VIDEO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
PROBE = CaptionProbe("manual_caption", "en")
ROWS = [{"text": "Original spoken words", "offset": 1200, "duration": 2160, "lang": "en"}]


class DstackFreeCaptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = Path(self.temp.name) / "transcription-services.json"
        self.catalog.write_text(json.dumps({
            "schema_version": 1,
            "source": "https://github.com/domenicomassafra/dodo-services/issues/280",
            "services": [
                {"name": "Unproven", "platform": "youtube", "rank": 0,
                 "identity": "resolved", "evidence": "unverified", "url": "https://unproven.test"},
                {"name": "YTTranscript.dev", "platform": "youtube", "rank": 1,
                 "identity": "resolved", "evidence": "http_captions_observed",
                 "url": "https://yttranscript.dev/"},
            ],
        }))

    @staticmethod
    def _native():
        raw = b'{}'
        return CaptionCapture(raw, hashlib.sha256(raw).hexdigest(), "native",
                              hashlib.sha256(b"native").hexdigest(),
                              (CaptionSegment(0, 0, 1000, "native"),), PROBE)

    def test_catalog_first_yields_original_language_and_ms_provenance(self):
        resolver = YouTubeResolver(free_caption_catalog_path=self.catalog)
        response = json.dumps({"videoId": "jNQXAC9IVRw", "language": "en", "segments": ROWS}).encode()
        with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json",
                   return_value=response) as fetch, patch.object(
                   resolver, "_capture_yt_dlp_caption", side_effect=AssertionError("native ran")):
            capture = resolver.capture_caption(VIDEO, PROBE)
        fetch.assert_called_once()
        self.assertEqual(capture.raw_bytes, response)
        self.assertEqual((capture.segments[0].start_ms, capture.segments[0].end_ms), (1200, 3360))
        self.assertEqual(capture.raw_text, "Original spoken words")
        self.assertEqual(capture.provenance["method"], "yttranscript.dev")
        self.assertEqual(capture.provenance["source_url"], VIDEO)
        self.assertEqual(capture.provenance["original_language"], "en")

    def test_english_original_caption_enters_free_provider_dispatch(self):
        resolver = YouTubeResolver(free_caption_catalog_path=self.catalog)
        metadata = {
            "language": "en",
            "subtitles": {
                "en": [{"ext": "json3", "url": "https://example.org/original"}],
                "it": [{"ext": "json3", "url": "https://example.org/translated"}],
            },
            "automatic_captions": {},
        }
        response = json.dumps({
            "videoId": "jNQXAC9IVRw", "language": "en", "segments": ROWS,
        }).encode()
        with patch.object(resolver, "metadata", return_value=metadata):
            probe = resolver.probe_caption(VIDEO)
        self.assertEqual(probe, CaptionProbe("manual_caption", "en"))
        with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json",
                   return_value=response) as fetch, patch.object(
                   resolver, "_capture_yt_dlp_caption", side_effect=AssertionError("native ran")):
            captured = resolver.capture_caption(VIDEO, probe)
        fetch.assert_called_once()
        self.assertEqual(captured.provenance["original_language"], "en")

    def test_errors_quota_and_invalid_evidence_fall_back_without_asr(self):
        for response in (
            TimeoutError("remote timeout"),
            HTTPError(VIDEO, 402, "guest quota exhausted", None, None),
            HTTPError(VIDEO, 429, "rate limited", None, None),
            json.dumps({"videoId": "other", "language": "en", "segments": ROWS}).encode(),
            json.dumps({"videoId": "jNQXAC9IVRw", "language": "it", "segments": ROWS}).encode(),
            json.dumps({"videoId": "jNQXAC9IVRw", "language": "en", "segments":
                        [{"text": "fabricated", "offset": -1, "duration": 1, "lang": "en"}]}).encode(),
        ):
            with self.subTest(response=response):
                resolver = YouTubeResolver(free_caption_catalog_path=self.catalog)
                with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json",
                           side_effect=response if isinstance(response, Exception) else None,
                           return_value=response if isinstance(response, bytes) else None), patch.object(
                           resolver, "_capture_yt_dlp_caption", return_value=self._native()) as native:
                    capture = resolver.capture_caption(VIDEO, PROBE)
                native.assert_called_once_with(VIDEO, PROBE)
                self.assertEqual(capture.raw_text, "native")
                self.assertEqual(capture.provenance["prior_method"], "yttranscript.dev")
                self.assertEqual(capture.provenance["fallback_reason"], "FREE_CAPTION_UNAVAILABLE")
                if isinstance(response, HTTPError):
                    self.assertEqual(capture.provenance["free_attempt_result"],
                                     f"HTTP_{response.code}")
                elif isinstance(response, TimeoutError):
                    self.assertEqual(capture.provenance["free_attempt_result"], "TIMEOUT")
                else:
                    self.assertEqual(capture.provenance["free_attempt_result"], "INVALID_CAPTIONS")

    def test_missing_or_unverified_catalog_never_calls_remote(self):
        for path in (Path(self.temp.name) / "missing.json", self.catalog):
            if path == self.catalog:
                payload = json.loads(path.read_text())
                payload["services"][1]["evidence"] = "unverified"
                path.write_text(json.dumps(payload))
            resolver = YouTubeResolver(free_caption_catalog_path=path)
            with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json") as fetch, patch.object(
                    resolver, "_capture_yt_dlp_caption", return_value=self._native()):
                self.assertEqual(resolver.capture_caption(VIDEO, PROBE).raw_text, "native")
            fetch.assert_not_called()

    def test_worker_persists_free_caption_as_unverified_source_variant(self):
        resolver = YouTubeResolver(free_caption_catalog_path=self.catalog)
        response = json.dumps({"videoId": "jNQXAC9IVRw", "language": "en", "segments": ROWS}).encode()
        worker = TranscriptAsrJobHandlers()
        worker.resolver = resolver
        worker.store = Mock()
        worker.store.renew.return_value = True
        worker.worker_id = "worker"
        worker.lease_seconds = 60
        worker.private_store = Mock()
        worker._require_current_ingestion_relevance = Mock()
        rights = Mock()
        rights.require.return_value.decision_fingerprint = "f" * 64
        rights.rights_record_id = "rights:test"
        worker._caption_rights_guard = Mock(return_value=rights)
        worker._insert_caption_variant = Mock(return_value=("variant:free", True))
        content = ContentRecord("content:test", "source:test", VIDEO, "Me at the zoo",
                                "2005-04-23", 19000, "DISCOVERED", {})
        job = SimpleNamespace(
            job_id="job:test", attempt=1,
            payload={"canonical_url": VIDEO, "external_id": "jNQXAC9IVRw",
                     "caption_kind": "manual_caption", "caption_language": "en"},
        )
        with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json",
                   return_value=response), patch.object(
                   resolver, "_capture_yt_dlp_caption", side_effect=AssertionError("native ran")):
            worker.acquire_caption(job, content)
        stored = worker._insert_caption_variant.call_args.kwargs
        self.assertEqual(stored["source_kind"], "YOUTUBE_FREE_PROVIDER_CAPTION")
        self.assertFalse(stored["is_manual_caption"])
        self.assertEqual(stored["language"], "en")
        self.assertEqual(stored["segments"][0]["start_ms"], 1200)
        self.assertEqual(stored["metadata"]["capture_provenance"]["catalog_rank"], "1")
        receipt = worker.store.record_receipt.call_args.kwargs
        self.assertEqual(receipt["status"], "SUCCESS")
        self.assertEqual(receipt["receipt"]["access_path"], "DSTACK_FREE_PUBLIC_CAPTION")
        self.assertEqual(receipt["receipt"]["billing_evidence_version"],
                         "dstack-free-public-caption-v1")
        self.assertEqual(receipt["estimated_cost_usd"], 0.0)
        worker.private_store.persist_caption.assert_called_once()

    def test_provider_raw_capture_is_saved_with_distinct_private_filename(self):
        resolver = YouTubeResolver(free_caption_catalog_path=self.catalog)
        response = json.dumps({"videoId": "jNQXAC9IVRw", "language": "en", "segments": ROWS}).encode()
        with patch("dichiarazioni_pubbliche.dstack_free_captions.fetch_captions_json",
                   return_value=response):
            capture = resolver.capture_caption(VIDEO, PROBE)
        output = PrivateTranscriptStore(Path(self.temp.name) / "private").persist_caption(
            content_id="content:test", variant_id="variant:free", capture=capture,
            receipt={"status": "SUCCESS"},
        )
        raw_file = output / "caption.raw.yttranscript-dev.json"
        self.assertEqual(raw_file.read_bytes(), response)
        self.assertEqual(raw_file.stat().st_mode & 0o777, 0o600)

    def test_missing_free_caption_does_not_enqueue_unapproved_paid_asr(self):
        worker = TranscriptAsrJobHandlers()
        worker.store = Mock()
        worker._require_current_ingestion_relevance = Mock()
        content = ContentRecord("content:test", "source:test", VIDEO, "Me at the zoo",
                                "2005-04-23", 19000, "DISCOVERED", {})
        with self.assertRaisesRegex(BlockedJob, "NO_ELIGIBLE_PRIMARY_ASR"):
            worker._enqueue_asr(content, reason="CAPTION_MISSING")
        worker.store.enqueue_followup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
