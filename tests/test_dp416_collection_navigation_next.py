"""DP416: one authenticated PostgreSQL snapshot of a usable collection tree."""
from __future__ import annotations

import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders, StudioLoopbackServer, _StudioQueueReader,
)
from dichiarazioni_pubbliche.studio_collection_navigation import read_collection_navigation
from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests


class FakeStore:
    def __init__(self, packet):
        self.packet = packet
        self.calls = []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        return json.dumps(self.packet)


class CollectionNavigationContractTests(unittest.TestCase):
    def test_one_scoped_bounded_snapshot_no_body(self):
        fixture = {"collection_id": "collection:one", "state": "ACTIVE",
                   "cursor_valid": True, "members": [{
                       "content_id": "content:one", "source_id": "source:one",
                       "source_exists": True, "rights_status": "UNKNOWN",
                       "processing_status": "DISCOVERED", "capture_count": 1,
                       "latest_capture": {
                           "id": "capture:one", "content_sha256": "a" * 64,
                           "status": "CAPTURED", "hold_status": "NONE",
                           "rights_status": "UNKNOWN", "archive_status": "NOT_REQUESTED",
                           "passage_count": 1, "passages": [{
                               "id": "passage:one", "text_sha256": "b" * 64,
                               "selector_type": "TEXT_POSITION",
                               "start_char": 0, "end_char": 10,
                               "page_start": None, "page_end": None,
                               "candidate_count": 1,
                               "first_candidate_id": "statement:one",
                           }],
                       },
                   }]}
        fake = FakeStore(fixture)
        result = read_collection_navigation(fake, collection_id="collection:one")
        self.assertEqual(result["members"][0]["latest_capture"]["passages"][0]["first_candidate_id"], "statement:one")
        self.assertTrue(result["private_only"])
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["review_authority"])
        self.assertNotIn("normalized_statement", json.dumps(result))
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", fake.calls[0][0])
        self.assertNotIn("private_text", fake.calls[0][0])
        self.assertNotIn("canonical_url", fake.calls[0][0])
        self.assertNotIn("source_title", fake.calls[0][0])

    def test_bad_anchor_foreign_and_forged_children_refuse_entire_tree(self):
        base = {"collection_id": "collection:one", "state": "ACTIVE",
                "cursor_valid": True, "members": []}
        for altered in [
            {"collection_id": "collection:foreign"},
            {"cursor_valid": False},
            {"members": [{"content_id": "content:one"}]},
            {"members": ["SECRET PRIVATE"]},
        ]:
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                read_collection_navigation(
                    FakeStore(base | altered), collection_id="collection:one",
                    after_content_id="content:one" if altered.get("cursor_valid") is False else None,
                )
        for body in ({"collection_id": "../bad"}, {"collection_id": "collection:one", "limit": 31},
                     {"collection_id": "collection:one", "after_content_id": "secret\nbody"},
                     {"collection_id": "collection:one", "limit": True}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                read_collection_navigation(FakeStore(base), **body)


class CollectionNavigationPostgresHttpTests(unittest.TestCase):
    """The real canonical PostgreSQL schema and a real authenticated socket."""

    @classmethod
    def setUpClass(cls):
        cls.pg = PersistedCaptureQueueTests
        cls.pg.setUpClass()
        try:
            cls.pg.store.run("""
                INSERT INTO source (id, canonical_name, source_type, canonical_url)
                VALUES ('source:nav', 'SECRET SOURCE', 'NEWS', 'https://private.invalid/secret');
                UPDATE content_item SET source_id='source:nav'
                  WHERE id='content:one';
                INSERT INTO passage (id, content_id, capture_id, selector_type,
                  start_char, end_char, text_sha256, private_text,
                  extraction_method, extraction_version)
                VALUES ('passage:nav', 'content:one', 'capture:one-new',
                  'TEXT_POSITION', 0, 12, repeat('f',64),
                  'SECRET PRIVATE PASSAGE', 'test', 'v1');
                INSERT INTO statement_candidate (id, content_id, statement_text_hash,
                  normalized_statement, extraction_version)
                VALUES ('statement:nav', 'content:one', repeat('e',64),
                  'SECRET PRIVATE STATEMENT', 'v1');
                INSERT INTO statement_candidate_passage (statement_candidate_id, passage_id, content_id)
                VALUES ('statement:nav','passage:nav','content:one');
                INSERT INTO claim_candidate (id, statement_candidate_id, content_id,
                  normalized_claim, proposed_claim_type, extraction_version)
                VALUES ('claim:nav', 'statement:nav','content:one','SECRET CLAIM','HISTORICAL_CLAIM','v1');
            """)
        except BaseException:
            cls.pg.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.pg.store.run("""
            UPDATE research_collection_content SET status='INCLUDED'
            WHERE collection_id='collection:one' AND content_id='content:one';
            UPDATE content_item SET rights_status='UNKNOWN'
            WHERE id='content:one';
        """)
        self.token = "9" * 64
        self.server = StudioLoopbackServer(
            0, StudioLocalReaders(None, None, None,
                                  queues=_StudioQueueReader(self.pg.url)), self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, body, *, auth=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        connection.request("POST", "/v1/collections/navigate",
                           json.dumps(body).encode("utf-8"), headers)
        response = connection.getresponse()
        status, headers = response.status, dict(response.getheaders())
        content = json.loads(response.read())
        connection.close()
        return status, content, headers

    def test_auth_real_db_source_capture_passage_candidate_pagination_and_revocation(self):
        self.assertEqual(self.request({"collection_id": "collection:one"}, auth=False)[0], 401)
        code, packet, headers = self.request({"collection_id": "collection:one", "limit": 1})
        self.assertEqual(code, 200, packet)
        data = packet["data"]
        self.assertEqual(data["members"][0]["content_id"], "content:one")
        capture = data["members"][0]["latest_capture"]
        self.assertEqual(capture["id"], "capture:one-new")
        self.assertEqual(capture["content_sha256"], "b"*64)
        self.assertEqual(capture["passages"][0]["id"], "passage:nav")
        self.assertEqual(capture["passages"][0]["first_candidate_id"], "statement:nav")
        self.assertEqual(capture["passages"][0]["candidate_count"], 1)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["next_after_content_id"], "content:one")
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertFalse(data["publication_authority"])
        for secret in ("SECRET", "private.invalid", "normalized_statement",
                       "private_text", "canonical_url"):
            self.assertNotIn(secret, json.dumps(packet))
        page = self.request({"collection_id": "collection:one", "limit": 1,
                             "after_content_id": "content:one"})
        self.assertEqual(page[0], 200, page)
        self.assertEqual(page[1]["data"]["members"][0]["content_id"], "content:unchanged")
        self.assertEqual(self.request({"collection_id": "collection:one",
                                       "after_content_id": "content:removed"})[0], 422)
        try:
            self.pg.store.run("""
                UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one';
                UPDATE research_collection_content SET status='REMOVED'
                WHERE collection_id='collection:one' AND content_id='content:unchanged';
            """)
            code, changed, _ = self.request({"collection_id": "collection:one"})
            self.assertEqual(code, 200, changed)
            self.assertEqual(len(changed["data"]["members"]), 1)
            self.assertIn("CONTENT_RIGHTS_NOT_APPROVED",
                          changed["data"]["members"][0]["blockers"])
            self.assertFalse(changed["data"]["members"][0]["source_preview_authorized"])
        finally:
            self.pg.store.run("""
                UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one';
                UPDATE research_collection_content SET status='INCLUDED'
                WHERE collection_id='collection:one' AND content_id='content:unchanged';
            """)


if __name__ == "__main__":
    unittest.main()
