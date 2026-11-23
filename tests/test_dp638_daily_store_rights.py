import hashlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.daily_store import DailyCaptureRecord, DailyStore  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)


class DailyStoreRightsTests(unittest.TestCase):
    def test_real_guard_can_be_reused_for_capture_and_statement_writes(self):
        text = "Una frase esatta."
        url = "https://example.org/article"
        now = datetime(2026, 11, 23, 11, 0, tzinfo=timezone.utc)
        capture = DailyCaptureRecord(
            id="capture-1",
            content_capture_id="content-capture-1",
            content_id="content-1",
            source_id="source-1",
            kind="article_text",
            url=url,
            char_count=len(text),
            content_sha256="a" * 64,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            media_type="text/html",
        )
        subject = RightsSubject(
            source_family="TEST_OFFICIAL_TEXT",
            locator_kind="URL",
            locator_value=url,
            content_id="content-1",
        )
        rights_record = PrivateRightsRecord(
            id="private-rights:daily",
            subject_fingerprint=rights_subject_fingerprint(subject),
            source_family=subject.source_family,
            locator_kind=subject.locator_kind,
            locator_value=subject.locator_value,
            content_id=subject.content_id,
            evidence_id=None,
            transcript_segment_id=None,
            canonical_segment_id=None,
            passage_id=None,
            rights_status="CLEARED",
            rights_receipt_ref="private-reviewed-receipt:daily",
            permitted_uses=("EXTRACT_CANDIDATES",),
            attribution_requirements=(),
            reviewed_at="2026-11-22T11:00:00+00:00",
            expires_at="2026-11-24T11:00:00+00:00",
            reviewer_ref="operator:qualified",
            policy_version="private-use-policy-v1",
            record_visibility="PRIVATE",
            supersedes_id=None,
            version_state="CURRENT",
            record_version=PRIVATE_RIGHTS_RECORD_VERSION,
        )
        reads = []

        def read_current(requested_subject):
            reads.append(requested_subject)
            return rights_record

        guard = SourceFamilyUseGuard(
            read_current=read_current,
            subject=subject,
            rights_record_id=rights_record.id,
            policy_version=rights_record.policy_version,
            expected_sha256=capture.content_sha256,
            expected_media_type=capture.media_type,
            clock=lambda: now,
        )
        statement = {
            "id": "statement-1",
            "content_id": capture.content_id,
            "capture_id": capture.id,
            "source_id": capture.source_id,
            "source_url": capture.url,
            "source_title": "Titolo",
            "source_publisher": "Editore",
            "statement_date": "2026-11-23",
            "quote": text,
            "quote_offset": 0,
            "claim_nature": "FACTUAL",
            "status": "CANDIDATE",
            "metadata": {},
        }

        with patch.object(DailyStore, "run", side_effect=["capture-1", "statement-1"]) as run:
            store = DailyStore()
            self.assertTrue(
                store.save_capture(
                    capture, captured_text=text, source_use_guard=guard
                )
            )
            self.assertTrue(
                store.save_statement(
                    statement,
                    capture=capture,
                    captured_text=text,
                    source_use_guard=guard,
                )
            )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads, [subject, subject])


if __name__ == "__main__":
    unittest.main()
