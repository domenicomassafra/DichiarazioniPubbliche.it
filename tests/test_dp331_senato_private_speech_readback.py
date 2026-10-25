"""Consumer regression for the versioned private rights on DP-331 readback."""

import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "poc"))

import dp331_senato_private_speech_readback as consumer
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineError
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from tests.test_senato_akoma_stenographic import URL, blob_sha, fixture


class PrivateSpeechReadbackRightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = fixture()
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.body = self.root / "captures" / "fixture.body"
        self.body.parent.mkdir()
        self.body.write_bytes(self.raw)
        self.subject = RightsSubject(
            source_family=consumer.SOURCE_FAMILY, locator_kind="URL",
            locator_value=URL, content_id="content:fixture",
        )
        now = datetime.now(timezone.utc)
        self.original = PrivateRightsRecord(
            id="private-rights:dp330", subject_fingerprint=rights_subject_fingerprint(self.subject),
            source_family=self.subject.source_family, locator_kind="URL",
            locator_value=URL, content_id=self.subject.content_id,
            evidence_id=None, transcript_segment_id=None, canonical_segment_id=None,
            passage_id=None, rights_status="CLEARED", rights_receipt_ref="fixture:licence",
            permitted_uses=("DISCOVER_METADATA", "FETCH", "RESEARCH_CAPTURE_PRIVATE", "STORE_BODY"),
            attribution_requirements=("ATTRIBUTION_REQUIRED",),
            reviewed_at=(now - timedelta(days=1)).isoformat(),
            expires_at=(now + timedelta(days=2)).isoformat(),
            reviewer_ref="fixture:reviewer", policy_version=consumer.DP330_PRIVATE_CAPTURE_POLICY,
            record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
        )
        self.current = self.original
        self.capture_reads = 0
        self.revoke_during_read = False

    def _readback(self, *, german_draft=None):
        suite = self

        class CaptureStore:
            def find_capture(self, content_id, sha256):
                suite.capture_reads += 1
                if suite.revoke_during_read:
                    suite.current = replace(suite.current, rights_status="REVOKED")
                return {
                    "id": "capture:fixture", "body_ref": "captures/fixture.body",
                    "observed_at": "2026-10-24T23:53:44+02:00",
                }

        class RightsStore:
            def read_current(self, subject):
                suite.assertEqual(subject, suite.subject)
                return suite.current

        with patch.object(consumer, "CapturePipelineStore", return_value=CaptureStore()), \
             patch.object(consumer, "_context", return_value={"id": self.subject.content_id}), \
             patch.object(consumer, "PrivateRightsRegistryStore", return_value=RightsStore()), \
             patch.object(consumer, "CURRENT_URL", URL), \
             patch.object(consumer, "BODY_SHA256", self.digest), \
             patch.object(consumer, "CONTENT_BLOB_SHA1", blob_sha(self.raw)):
            return consumer.run(
                "fixture:read-only", self.root, ordinals=(1,),
                german_draft=german_draft,
                italian_quote_span=(0, 12) if german_draft is not None else None,
            )

    def test_previous_grant_and_parse_text_successor_both_keep_private_hold(self):
        successor = replace(
            self.original, id="private-rights:dp357", supersedes_id=self.original.id,
            permitted_uses=tuple(sorted((*self.original.permitted_uses, "PARSE_TEXT"))),
        )
        for record in (self.original, successor):
            with self.subTest(rights=record.id):
                self.current = record
                result = self._readback(german_draft="Ist die Stellungnahme also nicht positiv?")
                self.assertEqual(result["rights_record_id"], record.id)
                self.assertEqual(result["rights_permitted_uses"], record.permitted_uses)
                self.assertEqual(result["status"], "PRIVATE_HOLD")
                self.assertEqual(result["german_source_status"], "DERIVED_UNREVIEWED_HOLD")
                self.assertFalse(result["extraction_authorized"])
                self.assertFalse(result["publication_authorized"])
                self.assertEqual(result["observations"][0]["decision"], "HOLD")
        self.assertEqual(self.capture_reads, 2)

    def test_incomplete_revoked_expired_or_unreviewed_grants_block_before_capture(self):
        for description, delta in (
            ("missing_store", {"permitted_uses": ("DISCOVER_METADATA", "FETCH", "RESEARCH_CAPTURE_PRIVATE")}),
            ("missing_research", {"permitted_uses": ("DISCOVER_METADATA", "FETCH", "STORE_BODY")}),
            ("public_scope", {"permitted_uses": self.original.permitted_uses + ("EXCERPT_PUBLIC",)}),
            ("unrelated_scope", {"permitted_uses": self.original.permitted_uses + ("TRANSLATE",)}),
            ("unknown_scope", {"permitted_uses": self.original.permitted_uses + ("UNKNOWN_PRIVATE_USE",)}),
            ("revoked", {"rights_status": "REVOKED"}),
            ("expired", {"expires_at": "2020-01-01T00:00:00+00:00"}),
            ("unreviewed", {"reviewed_at": None}),
            ("missing_receipt", {"rights_receipt_ref": None}),
            ("missing_reviewer", {"reviewer_ref": None}),
            ("superseded", {"version_state": "SUPERSEDED"}),
            ("wrong_subject", {"content_id": "content:other"}),
            ("wrong_policy", {"policy_version": "other-policy"}),
        ):
            with self.subTest(description=description), self.assertRaisesRegex(
                (RuntimeError, SourceUseBlocked), "DP331_PRIVATE_RIGHTS_CURRENT_REQUIRED|SOURCE_USE_"
            ):
                self.current = replace(self.original, **delta)
                self._readback()
        self.assertEqual(self.capture_reads, 0)

    def test_tampered_capture_hash_fails_before_speech_observation(self):
        self.body.write_bytes(self.raw + b"tampered")
        with self.assertRaisesRegex(CapturePipelineError, "BODY_FILE_HASH_MISMATCH"):
            self._readback()
        self.assertEqual(self.capture_reads, 1)

    def test_revoke_between_guard_and_body_read_blocks_second_guard(self):
        self.revoke_during_read = True
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_REVOKED"):
            self._readback()
        self.assertEqual(self.capture_reads, 1)


if __name__ == "__main__":
    unittest.main()
