"""#169: caller must clear exact YouTube rights before any caption network or write."""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionCapture, CaptionProbe, PlatformAccessRestricted, VideoCandidate, YouTubeResolver,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRecord, PrivateRightsRegistryStore, RightsSubject,
    rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.worker_errors import BlockedJob  # noqa: E402
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers  # noqa: E402

URL = "https://www.youtube.com/watch?v=QaE00l6JZ8w"
CONTENT_ID = "content:youtube-rights-test"
SUBJECT = RightsSubject("YOUTUBE", "URL", URL, content_id=CONTENT_ID)
NOW = datetime.now(timezone.utc)


def rights(**changes):
    record = PrivateRightsRecord(
        id="private-rights:test-youtube", subject_fingerprint=rights_subject_fingerprint(SUBJECT),
        source_family=SUBJECT.source_family, locator_kind="URL", locator_value=URL,
        content_id=CONTENT_ID, evidence_id=None, transcript_segment_id=None,
        canonical_segment_id=None, passage_id=None, rights_status="CLEARED",
        rights_receipt_ref="owner-reviewed:youtube", permitted_uses=("FETCH", "STORE_BODY"),
        attribution_requirements=(), reviewed_at=(NOW - timedelta(days=1)).isoformat(),
        expires_at=(NOW + timedelta(days=1)).isoformat(), reviewer_ref="reviewer:qualified",
        policy_version="private-use-policy-v1", record_visibility="PRIVATE",
        supersedes_id=None, version_state="CURRENT",
    )
    return replace(record, **changes)


class CaptionRightsGateTests(unittest.TestCase):
    def setUp(self):
        self.store = QueueRuntimeStore()
        self.store.renew = Mock(return_value=True)
        self.store.require_current_ingestion_relevance = Mock()
        self.store.insert_transcript_variant = Mock(return_value=("variant:test", True))
        self.store.run_literal = Mock(return_value="private-rights:test-youtube\n1|t|1")
        self.store.insert_transcript_segments = Mock()
        self.store.record_receipt = Mock(return_value="receipt:test")
        self.store.enqueue_followup = Mock()
        self.store.update_content_status = Mock()
        self.handler = TranscriptAsrJobHandlers()
        self.handler.store = self.store
        self.handler.worker_id = "worker:fixture"
        self.handler.lease_seconds = 30
        self.handler.private_store = Mock()
        self.handler.resolver = Mock()
        self.job = SimpleNamespace(
            job_id="job:caption", attempt=1,
            payload={"canonical_url": URL, "external_id": "QaE00l6JZ8w",
                     "caption_kind": "manual_caption", "caption_language": "it"},
        )
        self.content = SimpleNamespace(content_id=CONTENT_ID, source_id="source:fixture",
                                       canonical_url=URL)
        self.handler.resolver.capture_caption.return_value = CaptionCapture(
            b"{}", "a" * 64, "test caption", "b" * 64,
            (SimpleNamespace(segment_index=0, start_ms=0, end_ms=1500, text="test caption"),),
            CaptionProbe("manual_caption", "it"),
        )

    def test_missing_revoked_expired_or_wrong_use_blocks_before_fetch(self):
        for record in (None, rights(rights_status="REVOKED"),
                       rights(expires_at=(NOW - timedelta(seconds=1)).isoformat()),
                       rights(permitted_uses=("FETCH",)),
                       rights(locator_value="https://www.youtube.com/watch?v=INVALID0000")):
            with self.subTest(record=record):
                with patch.object(PrivateRightsRegistryStore, "read_current", return_value=record):
                    with self.assertRaises(BlockedJob):
                        self.handler.acquire_caption(self.job, self.content)
                self.handler.resolver.capture_caption.assert_not_called()
                self.store.insert_transcript_variant.assert_not_called()
                self.handler.private_store.persist_caption.assert_not_called()

    def test_metadata_probe_never_fetches_without_rights(self):
        candidate = VideoCandidate("QaE00l6JZ8w", "Test", URL)
        with patch.object(PrivateRightsRegistryStore, "read_current", return_value=None):
            with self.assertRaises(BlockedJob):
                self.handler._probe_and_enqueue_caption(self.job, self.content, candidate)
        self.handler.resolver.probe_caption.assert_not_called()
        self.store.record_receipt.assert_not_called()

    def test_429_at_probe_cannot_dispatch_asr_bypass(self):
        candidate = VideoCandidate("QaE00l6JZ8w", "Test", URL)
        self.handler.resolver.probe_caption.side_effect = PlatformAccessRestricted("HTTP_429")
        self.handler._enqueue_asr = Mock()
        with patch.object(PrivateRightsRegistryStore, "read_current", return_value=rights()):
            with self.assertRaisesRegex(BlockedJob, "YOUTUBE_CAPTION_ACCESS_RESTRICTED"):
                self.handler._probe_and_enqueue_caption(self.job, self.content, candidate)
        self.handler._enqueue_asr.assert_not_called()
        self.store.enqueue_followup.assert_not_called()
        self.assertEqual(self.store.record_receipt.call_args.kwargs["status"], "ACCESS_RESTRICTED")

    def test_metadata_429_then_no_subtitles_never_retries_or_dispatches_asr(self):
        self.handler.resolver = YouTubeResolver()
        self.handler._enqueue_asr = Mock()
        diagnostic = "ERROR: HTTP Error 429 Too Many Requests\nWARNING: no subtitles available"
        blocked = SimpleNamespace(returncode=1, stderr=diagnostic, stdout="")
        with patch.object(PrivateRightsRegistryStore, "read_current", return_value=rights()):
            with patch("dichiarazioni_pubbliche.platform_transcript.subprocess.run",
                       return_value=blocked) as executor:
                with self.assertRaisesRegex(BlockedJob, "YOUTUBE_CAPTION_ACCESS_RESTRICTED"):
                    self.handler._probe_and_enqueue_caption(
                        self.job, self.content,
                        VideoCandidate("QaE00l6JZ8w", "Synthetic", URL),
                    )
        executor.assert_called_once()
        self.handler._enqueue_asr.assert_not_called()
        self.store.enqueue_followup.assert_not_called()
        self.assertEqual(self.store.record_receipt.call_args.kwargs["status"], "ACCESS_RESTRICTED")

    def test_revocation_during_network_blocks_all_writes(self):
        current = [rights()]
        expected = self.handler.resolver.capture_caption.return_value
        def revoke_then_return(*_args):
            current[0] = rights(rights_status="REVOKED")
            return expected
        self.handler.resolver.capture_caption.side_effect = revoke_then_return
        with patch.object(PrivateRightsRegistryStore, "read_current", side_effect=lambda _: current[0]):
            with self.assertRaises(BlockedJob):
                self.handler.acquire_caption(self.job, self.content)
        self.store.insert_transcript_variant.assert_not_called()
        self.handler.private_store.persist_caption.assert_not_called()
        self.store.record_receipt.assert_not_called()

    def test_revoked_before_private_body_persist_cannot_write_raw_bytes(self):
        current = [rights()]
        def revoke_inside_atomic_insert(sql):
            self.assertIn("FOR UPDATE", sql)
            self.assertIn("NOT EXISTS", sql)
            current[0] = rights(rights_status="REVOKED")
            return "private-rights:test-youtube\n0|f|0"
        self.store.run_literal.side_effect = revoke_inside_atomic_insert
        with patch.object(PrivateRightsRegistryStore, "read_current", side_effect=lambda _: current[0]):
            with self.assertRaises(BlockedJob):
                self.handler.acquire_caption(self.job, self.content)
        self.store.insert_transcript_variant.assert_not_called()
        self.store.insert_transcript_segments.assert_not_called()
        self.handler.private_store.persist_caption.assert_not_called()
        self.store.enqueue_followup.assert_not_called()

    def test_registry_failure_or_wrong_content_fails_closed(self):
        for returned in (RuntimeError("db unavailable"),
                         rights(content_id="content:unrelated")):
            with self.subTest(returned=returned):
                with patch.object(PrivateRightsRegistryStore, "read_current",
                                  side_effect=returned if isinstance(returned, Exception) else None,
                                  return_value=returned if not isinstance(returned, Exception) else None):
                    with self.assertRaises(BlockedJob):
                        self.handler.acquire_caption(self.job, self.content)
                self.handler.resolver.capture_caption.assert_not_called()

    def test_approved_exact_rights_allow_private_receipt(self):
        with patch.object(PrivateRightsRegistryStore, "read_current", return_value=rights()):
            self.handler.acquire_caption(self.job, self.content)
        self.handler.resolver.capture_caption.assert_called_once()
        self.store.insert_transcript_variant.assert_not_called()
        self.store.insert_transcript_segments.assert_not_called()
        sql = self.store.run_literal.call_args.args[0]
        self.assertIn("FOR UPDATE", sql)
        self.assertIn("STORE_BODY", sql)
        self.assertIn("JOIN inserted ON inserted.id=x.variant_id", sql)
        self.handler.private_store.persist_caption.assert_called_once()
        receipt = self.handler.private_store.persist_caption.call_args.kwargs["receipt"]
        self.assertEqual(receipt["source_rights_record_id"], "private-rights:test-youtube")
        self.assertIn("FETCH", receipt["source_rights_fingerprints"])
        self.assertIn("STORE_BODY", receipt["source_rights_fingerprints"])


if __name__ == "__main__":
    unittest.main()
