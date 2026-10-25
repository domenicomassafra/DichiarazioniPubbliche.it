"""DP-419 exact original Ogg byte->PG Capture->Segment->HTTP playback canary.

Opt-in: DP419_REAL_MEDIA_PATH must point to the *unaltered* public-domain
JFK Rice University Wikimedia Commons 2010 upload. No production DB writes.
A resolved transcript and approval are fixture assertions, not verified ASR.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.media_capture_proof import derive_media_capture_segment
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.studio_local_api import (
    _StudioCaptureReader, StudioLocalReaders,
    StudioLoopbackServer,
)
from dichiarazioni_pubbliche.studio_media_capture_binding_pg import PgMediaCaptureBindingStore
from dichiarazioni_pubbliche.studio_media_playback_http import StudioMediaRightsReader
from tests import test_dp419_media_capture_binding_pg_next as binding_fixture

ORIGINAL_SHA = "7486fba805c20bde4d43750bd9c34aee86ab7acfd3854a1d0f3d64f62ae68b27"
SOURCE = "https://upload.wikimedia.org/wikipedia/commons/5/50/Jfk_rice_university_we_choose_to_go_to_the_moon.ogg"
SEGMENT_TEXT = "We choose to go to the Moon in this decade and do the other things, not because they are easy"
CONTENT = "content:jfk-rice-1962"
CAPTURE = "capture:jfk-rice-1962-wikimedia"
SEGMENT = "segment:jfk-rice-1962-522000"
BINDING = "binding:jfk-rice-1962-522000"
BEGIN, END = 522000, 534000


class OriginalMediaRealPgAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asset = os.environ.get("DP419_REAL_MEDIA_PATH")
        if not asset:
            raise unittest.SkipTest("DP419_REAL_MEDIA_PATH original Ogg is required")
        cls.asset = Path(asset)
        if not cls.asset.is_file():
            raise AssertionError("original source missing")
        cls.bytes = cls.asset.read_bytes()
        if hashlib.sha256(cls.bytes).hexdigest() != ORIGINAL_SHA:
            raise AssertionError("original source digest mismatch")
        cls.pg = binding_fixture.DP419MediaCaptureBindingPgNext
        cls.pg.setUpClass()
        cls.temp = tempfile.TemporaryDirectory(prefix="dp419-real-body-")
        try:
            cls.store = CaptureBodyStore(Path(cls.temp.name) / "body")
            body = cls.store.write(
                capture_id=CAPTURE, body=cls.bytes, content_sha256=ORIGINAL_SHA,
            )
            text_sha = hashlib.sha256(SEGMENT_TEXT.encode("utf-8")).hexdigest()
            cls.proof = derive_media_capture_segment(
                media_path=cls.asset, capture_sha256=ORIGINAL_SHA,
                content_id=CONTENT, capture_id=CAPTURE,
                canonical_segment_id=SEGMENT, canonical_text_sha256=text_sha,
                start_ms=BEGIN, end_ms=END,
            )
            cls.pg._sql(f"""
                INSERT INTO content_item
                  (id, canonical_url, duration_ms, rights_status)
                VALUES ('{CONTENT}', '{SOURCE}', 1060250, 'CLEARED');
                INSERT INTO content_capture
                  (id,content_id,observed_at,final_url,content_sha256,body_ref,
                   media_type,retrieval_method,retrieval_version,
                   rights_status,retention_class,hold_status,status)
                VALUES ('{CAPTURE}','{CONTENT}','2026-10-25T14:00:00Z','{SOURCE}',
                  '{ORIGINAL_SHA}','{body.body_ref}',
                  'audio/ogg','DP419_REAL_MEDIA_BYTES','v1',
                  'CLEARED','DURABLE_PRIVATE','NONE','CAPTURED');
                INSERT INTO canonical_transcript_segment
                  (id,content_id,segment_index,start_ms,end_ms,canonical_text,
                   transcript_status,publication_blocked)
                VALUES ('{SEGMENT}','{CONTENT}',1,{BEGIN},{END},
                  '{SEGMENT_TEXT}','RESOLVED',false);
                INSERT INTO passage
                  (id,content_id,canonical_segment_id,selector_type,text_sha256,
                   extraction_method,extraction_version)
                VALUES ('passage:jfk-rice-1962','{CONTENT}','{SEGMENT}',
                  'MEDIA_SEGMENT_REF','{text_sha}','isolated-fixture','v1');
                INSERT INTO statement_candidate
                  (id,content_id,statement_text_hash,normalized_statement,
                   extraction_version,status)
                VALUES ('statement:jfk-rice-1962','{CONTENT}','{text_sha}',
                  '{SEGMENT_TEXT}','v1','APPROVED');
                INSERT INTO statement_candidate_passage
                  (statement_candidate_id,passage_id,content_id)
                VALUES ('statement:jfk-rice-1962','passage:jfk-rice-1962','{CONTENT}');
            """)
            cls.binding = PgMediaCaptureBindingStore(cls.pg.dsn)
            cls.binding.record(
                binding_id=BINDING, event_id="event:jfk-522000-attest",
                expected_revision=0, action="ATTEST",
                content_id=CONTENT, capture_id=CAPTURE,
                capture_sha256=ORIGINAL_SHA,
                canonical_segment_id=SEGMENT, start_ms=BEGIN, end_ms=END,
                evidence_sha256=cls.proof["evidence_sha256"],
                attestor_ref="agent:dp419-fixture",
            )
            cls.rights = PrivateRightsRegistryStore(cls.pg.dsn)
            clock = datetime.now(timezone.utc)
            cls.current_record = cls.rights.record_rights(
                subject=RightsSubject(
                    source_family="WIKIMEDIA_COMMONS", locator_kind="URL",
                    locator_value=SOURCE, content_id=CONTENT,
                ),
                policy_version="dp419-public-domain-research-v1",
                rights_status="CLEARED",
                rights_receipt_ref="source-jfk-commons-and-jfk-archives-20261025",
                permitted_uses=("FETCH", "STORE_BODY", "ASR_MEDIA", "PLAYBACK"),
                attribution_requirements=("CREDIT_JFK_PRESIDENTIAL_LIBRARY",),
                reviewed_at=(clock - timedelta(minutes=5)).isoformat(),
                expires_at=(clock + timedelta(days=30)).isoformat(),
                reviewer_ref="agent:dp419-source-rights",
            )
        except BaseException:
            cls.temp.cleanup()
            cls.pg.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()
        if hasattr(cls, "pg"):
            cls.pg.tearDownClass()

    def test_real_ogg_postgres_persisted_proof_and_authenticated_seek(self):
        row = self.binding.inspect(binding_id=BINDING)
        self.assertEqual(row["binding_state"], "ATTESTED")
        self.assertEqual(row["hold_reasons"], ["RIGHTS_NOT_INDEPENDENTLY_APPROVED"])
        self.assertEqual(row["capture_sha256"], ORIGINAL_SHA)
        self.assertEqual(row["start_ms"], BEGIN)
        self.assertEqual(row["end_ms"], END)
        self.assertNotIn(SOURCE, json.dumps(row))
        self.assertFalse(row["seek_authorized"])
        bearer = "d" * 64
        server = StudioLoopbackServer(
            0, StudioLocalReaders(
                None, _StudioCaptureReader(self.pg.dsn), None,
                body_store=CaptureBodyStore.open_existing_readonly(self.store.root),
                rights_reader=StudioMediaRightsReader(self.pg.dsn),
            ), bearer,
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=25,
            )
            payload = json.dumps({"binding_id": BINDING})
            connection.request(
                "POST", "/v1/media/playback", payload,
                {"Authorization": "Bearer " + bearer, "Content-Type": "application/json"},
            )
            reply = connection.getresponse()
            self.assertEqual(reply.status, 200)
            self.assertEqual(reply.getheader("Content-Type"), "audio/ogg")
            self.assertEqual(reply.getheader("X-Seek-Start-Ms"), str(BEGIN))
            self.assertEqual(reply.getheader("X-Seek-End-Ms"), str(END))
            actual = reply.read()
            self.assertEqual(hashlib.sha256(actual).hexdigest(), ORIGINAL_SHA)
            self.assertEqual(len(actual), 17193282)
            connection.close()
            self.pg._sql(f"""UPDATE content_capture SET rights_status='REVOKED'
                             WHERE id='{CAPTURE}';""")
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=10,
            )
            connection.request(
                "POST", "/v1/media/playback", payload,
                {"Authorization": "Bearer " + bearer, "Content-Type": "application/json"},
            )
            held = connection.getresponse()
            self.assertEqual(held.status, 422)
            self.assertEqual(json.loads(held.read())["error"],
                             "STUDIO_LOCAL_REQUEST_OR_DATA_INVALID")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
