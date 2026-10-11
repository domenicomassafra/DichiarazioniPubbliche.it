"""DP416/417: genuine loopback HTTP → read-only PostgreSQL vertical path.

The canonical schema and records live in one disposable PG cluster; nothing
contacts MiniPC, source providers or production credentials.
"""

import http.client
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_local_api import (  # noqa: E402
    StudioLocalReaders,
    StudioLoopbackServer,
    _StudioQueueReader,
)

TOKEN = "e" * 64


class StudioAuthVerticalNextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests

        cls.pg = PersistedCaptureQueueTests
        cls.pg.setUpClass()
        try:
            cls.pg.store.run("""
                INSERT INTO source (id, canonical_name, source_type, canonical_url)
                VALUES ('source:vertical', 'SECRET SOURCE', 'NEWS', 'https://private.example/hidden');
                UPDATE content_item SET source_id='source:vertical' WHERE id='content:one';
                INSERT INTO passage (id, content_id, capture_id, selector_type,
                  start_char, end_char, text_sha256, private_text,
                  extraction_method, extraction_version, metadata)
                VALUES
                  ('passage:vertical', 'content:one', 'capture:one-new', 'TEXT_POSITION',
                    0, 16, repeat('f',64), 'SECRET PRIVATE QUOTE', 'fixture', 'v1',
                    '{"secret":"PRIVATE PASSPHRASE"}'),
                  ('passage:foreign', 'content:other', 'capture:other', 'TEXT_POSITION',
                    1, 10, repeat('d',64), 'SECRET FOREIGN QUOTE', 'fixture', 'v1', '{}');
                INSERT INTO statement_candidate (id, content_id, statement_text_hash,
                  normalized_statement, extraction_version) VALUES
                  ('statement:vertical-a', 'content:one', repeat('a',64), 'SECRET NORMALIZED', 'v1'),
                  ('statement:vertical-b', 'content:one', repeat('b',64), 'SECRET SECOND', 'v1');
                INSERT INTO statement_candidate_passage (statement_candidate_id, passage_id, content_id)
                VALUES
                  ('statement:vertical-a', 'passage:vertical', 'content:one'),
                  ('statement:vertical-b', 'passage:vertical', 'content:one');
                INSERT INTO claim_candidate (id, statement_candidate_id, content_id,
                  normalized_claim, proposed_claim_type, extraction_version)
                VALUES ('claimcandidate:vertical', 'statement:vertical-a', 'content:one',
                        'SECRET PRIVATE CLAIM', 'HISTORICAL_CLAIM', 'v1');
            """)
        except BaseException:
            cls.pg.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pg"):
            cls.pg.tearDownClass()

    def setUp(self):
        self.pg.store.run("""
            UPDATE research_collection_content SET status='INCLUDED'
              WHERE collection_id='collection:one' AND content_id='content:one';
            UPDATE content_capture SET rights_status='UNKNOWN',hold_status='NONE'
              WHERE id='capture:one-new';
            UPDATE content_item SET rights_status='UNKNOWN',processing_status='DISCOVERED'
              WHERE id='content:one';
        """)
        # Actual store passes through read-only PGOPTIONS in _StudioQueueReader;
        # fake stores do not participate in either new path.
        queue = _StudioQueueReader(self.pg.url)
        self.server = StudioLoopbackServer(
            0,
            StudioLocalReaders(
                corpus=None,
                captures=None,
                candidates=None,
                queues=queue,
            ),
            TOKEN,
        )
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)

    def request(self, path, body, *, auth=True, origin=None, host=None, method="POST"):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {TOKEN}"
        if origin is not None:
            headers["Origin"] = origin
        if host is not None:
            headers["Host"] = host
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=8
        )
        connection.request(method, path, json.dumps(body).encode("utf-8"), headers)
        response = connection.getresponse()
        status = response.status
        response_headers = dict(response.getheaders())
        data = json.loads(response.read())
        connection.close()
        return status, data, response_headers

    def test_capture_queue_auth_origin_host_and_exact_persisted_snapshot(self):
        path = "/v1/discovery/capture-queue"
        body = {"collection_id": "collection:one", "limit": 1}
        self.assertEqual(self.request(path, body, auth=False)[0], 401)
        self.assertEqual(
            self.request(path, body, origin="https://evil.invalid")[0], 403
        )
        self.assertEqual(self.request(path, body, host="evil.invalid")[0], 403)
        allowed = f"http://127.0.0.1:{self.server.server_port}"
        status, packet, headers = self.request(path, body, origin=allowed)
        self.assertEqual(status, 200, packet)
        queue = packet["data"]
        self.assertEqual(queue["contract_version"], "studio-capture-triage-queue-v1")
        self.assertEqual(
            [item["capture_id"] for item in queue["results"]], ["capture:one-new"]
        )
        self.assertEqual(queue["results"][0]["previous_capture_id"], "capture:one-old")
        self.assertEqual(queue["results"][0]["lifecycle_event_id"], "event:new")
        self.assertIsNone(queue["next_after_capture_id"])
        self.assertTrue(queue["private_only"])
        self.assertFalse(queue["triage_action_authorized"])
        self.assertFalse(queue["publication_authority"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.request(path, body | {"approve": True})[0], 422)
        self.assertEqual(self.request(path, body | {"limit": 31})[0], 422)
        self.assertEqual(
            self.request(path, body | {"after_capture_id": "capture:other"})[0], 422
        )
        self.assertEqual(
            self.request(path, body | {"collection_id": "collection:missing"})[0], 422
        )
        self.assertIn(
            "PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED",
            queue["results"][0]["blockers"],
        )
        for forbidden in (
            "SECRET SOURCE",
            "private.example",
            "SECRET A",
            "content_sha256",
            "body_ref",
            "final_url",
            "canonical_url",
        ):
            self.assertNotIn(forbidden, json.dumps(packet))
        try:
            self.pg.store.run("""
                UPDATE content_capture SET rights_status='REVOKED'
                WHERE id='capture:one-new';
            """)
            blocked_code, blocked, _ = self.request(path, body)
            self.assertEqual(blocked_code, 200, blocked)
            self.assertEqual(
                blocked["data"]["results"][0]["queue_family"], "BLOCKED_CAPTURE"
            )
            self.assertIn(
                "CAPTURE_RIGHTS_REVOKED", blocked["data"]["results"][0]["blockers"]
            )
            self.assertFalse(blocked["data"]["rights_clearance"])
            self.assertFalse(blocked["data"]["triage_action_authorized"])
        finally:
            self.pg.store.run("""
                UPDATE content_capture SET rights_status='UNKNOWN'
                WHERE id='capture:one-new';
            """)
        self.assertEqual(self.request(path, body, method="GET")[0], 405)
        self.assertEqual(
            self.request(
                path, body, auth=True, host=f"localhost:{self.server.server_port}"
            )[0],
            403,
        )
        self.assertEqual(
            self.request(path, body, auth=True, origin=allowed + "/bad")[0], 403
        )

    def test_passage_lineage_real_persisted_graph_cursor_and_rights(self):
        path = "/v1/collections/passage-lineage"
        body = {
            "collection_id": "collection:one",
            "content_id": "content:one",
            "capture_id": "capture:one-new",
            "passage_id": "passage:vertical",
            "limit": 1,
        }
        self.assertEqual(self.request(path, body, auth=False)[0], 401)
        self.assertEqual(
            self.request(path, body, origin="https://evil.invalid")[0], 403
        )
        self.assertEqual(self.request(path, body, host="bad.invalid")[0], 403)
        status, packet, headers = self.request(path, body)
        self.assertEqual(status, 200, packet)
        view = packet["data"]
        self.assertEqual(view["source_id"], "source:vertical")
        self.assertEqual(view["capture_sha256"], "b" * 64)
        self.assertEqual(view["passage"]["id"], "passage:vertical")
        self.assertEqual(
            [entry["id"] for entry in view["candidates"]], ["statement:vertical-a"]
        )
        self.assertEqual(
            view["candidates"][0]["claim_candidates"][0]["id"],
            "claimcandidate:vertical",
        )
        self.assertEqual(view["next_after_statement_id"], "statement:vertical-a")
        page2 = self.request(
            path, body | {"after_statement_id": view["next_after_statement_id"]}
        )
        self.assertEqual(page2[0], 200, page2[1])
        self.assertEqual(
            [entry["id"] for entry in page2[1]["data"]["candidates"]],
            ["statement:vertical-b"],
        )
        self.assertEqual(page2[1]["data"]["candidates"][0]["claim_candidates"], [])
        self.assertFalse(view["rights_clearance"])
        self.assertFalse(view["publication_authority"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.request(path, body, method="GET")[0], 405)
        for forbidden in (
            "SECRET",
            "PRIVATE",
            "normalized_claim",
            "private_text",
            "final_url",
            "body_ref",
        ):
            self.assertNotIn(forbidden, json.dumps((packet, page2[1])))
        for invalid in (
            {"collection_id": "collection:other"},
            {"content_id": "content:other"},
            {"capture_id": "capture:one-old"},
            {"passage_id": "passage:foreign"},
            {"after_statement_id": "statement:foreign"},
            {"promote": True},
            {"limit": 31},
            {"after_statement_id": "../invalid"},
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.request(path, body | invalid)[0], 422)
        try:
            self.pg.store.run("""
                UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one';
                UPDATE content_capture SET hold_status='RIGHTS_HOLD' WHERE id='capture:one-new';
            """)
            code, response, _ = self.request(path, body)
            self.assertEqual(code, 200, response)
            self.assertIn("CONTENT_RIGHTS_NOT_APPROVED", response["data"]["blockers"])
            self.assertIn("CAPTURE_NOT_READY_FOR_REVIEW", response["data"]["blockers"])
            self.assertFalse(response["data"]["rights_clearance"])
            self.assertFalse(response["data"]["publication_authority"])
            self.pg.store.run("""
                UPDATE research_collection_content SET status='REMOVED'
                WHERE collection_id='collection:one' AND content_id='content:one';
            """)
            self.assertEqual(self.request(path, body)[0], 422)
            self.assertEqual(
                self.request(
                    "/v1/discovery/capture-queue",
                    {
                        "collection_id": "collection:one",
                        "after_capture_id": "capture:one-new",
                    },
                )[0],
                422,
            )
        finally:
            self.pg.store.run("""
                UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one';
                UPDATE content_capture SET hold_status='NONE' WHERE id='capture:one-new';
                UPDATE research_collection_content SET status='INCLUDED'
                WHERE collection_id='collection:one' AND content_id='content:one';
            """)

    def test_database_context_is_transaction_read_only_and_other_requests_refused(self):
        reader = self.server.readers.queues
        self.assertEqual(reader.run("SHOW default_transaction_read_only;"), "on")
        with self.assertRaises(RuntimeError):
            reader.run(
                "UPDATE content_capture SET status='QUARANTINED' WHERE id='capture:one-new'"
            )
        self.assertEqual(
            self.request(
                "/v1/discovery/capture-queue",
                {"collection_id": "collection:one"},
                auth=False,
            )[0],
            401,
        )
        self.assertEqual(
            self.request(
                "/v1/collections/passage-lineage",
                {
                    "collection_id": "collection:one",
                    "content_id": "content:one",
                    "capture_id": "capture:one-new",
                    "passage_id": "passage:vertical",
                    "write": "unauthorized",
                },
            )[0],
            422,
        )


if __name__ == "__main__":
    unittest.main()
