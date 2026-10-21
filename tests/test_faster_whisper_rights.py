"""DP-164: independent synthetic checks of current media source-use rights."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dichiarazioni_pubbliche.faster_whisper_rights import require_faster_whisper_media_rights
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.remote_asr import AsrRequestRejected
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)


class FasterWhisperSourceRightsTests(unittest.TestCase):
    def setUp(self):
        self.store = PsqlRuntime()
        self.content_id = "content:synthetic"
        self.url = "https://example.test/private-wav-origin"
        self.subject = RightsSubject(
            source_family="SYNTHETIC_ASR", locator_kind="URL",
            locator_value=self.url, content_id=self.content_id,
        )
        now = datetime.now(timezone.utc)
        self.record = PrivateRightsRecord(
            id="rights:synthetic-asr", subject_fingerprint=rights_subject_fingerprint(self.subject),
            source_family=self.subject.source_family, locator_kind="URL", locator_value=self.url,
            content_id=self.content_id, evidence_id=None, transcript_segment_id=None,
            canonical_segment_id=None, passage_id=None, rights_status="CLEARED",
            rights_receipt_ref="receipt:synthetic-asr", permitted_uses=("ASR_MEDIA",),
            attribution_requirements=(), reviewed_at=(now-timedelta(days=1)).isoformat(),
            expires_at=(now+timedelta(days=1)).isoformat(),
            reviewer_ref="synthetic:operator", policy_version="synthetic-policy-v1",
            record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
        )
        self.payload = {
            "rights_record_id": self.record.id,
            "rights_policy_version": self.record.policy_version,
            "rights_receipt_id": self.record.rights_receipt_ref,
        }

    def check(self, record=None, *, payload=None, url=None, current=None):
        reviewed = self.record if record is None else record
        authoritative = reviewed if current is None else current

        class Registry:
            def read_record(self, record_id):
                return reviewed

            def read_current(self, subject):
                return authoritative

        with patch(
            "dichiarazioni_pubbliche.faster_whisper_rights.PrivateRightsRegistryStore",
            return_value=Registry(),
        ):
            require_faster_whisper_media_rights(
                store=self.store, content_id=self.content_id,
                canonical_url=url or self.url,
                payload=payload if payload is not None else self.payload,
            )

    def test_exact_current_source_use_granted_without_publication_authority(self):
        self.check()

    def test_untrusted_job_receipt_scope_or_policy_blocks_before_model(self):
        for change in (
            {"rights_record_id": None},
            {"rights_policy_version": None},
            {"rights_receipt_id": "receipt:unrelated"},
            {"rights_policy_version": "wrong-policy"},
        ):
            with self.subTest(change=change), self.assertRaises(AsrRequestRejected):
                self.check(payload=self.payload | change)
        with self.assertRaisesRegex(AsrRequestRejected, "ARTIFACT_MISMATCH"):
            self.check(url="https://example.test/different-content")

    def test_revocation_expiry_missing_asr_use_and_supersession_fail_closed(self):
        for record in (
            replace(self.record, rights_status="REVOKED"),
            replace(self.record, permitted_uses=("FETCH", "STORE_BODY")),
            replace(self.record, expires_at="2020-01-01T00:00:00+00:00"),
            replace(self.record, version_state="HISTORICAL"),
        ):
            with self.subTest(record=record.rights_status, uses=record.permitted_uses), \
                    self.assertRaises(AsrRequestRejected):
                self.check(current=record)


if __name__ == "__main__":
    unittest.main()
