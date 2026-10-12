"""DP519: real disposable PostgreSQL Collection worklist on private Studio HTTP."""
from __future__ import annotations

import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import StudioLocalReaders, StudioLoopbackServer
from tests.test_dp519_studio_operator_workload_pg_next import StudioOperatorWorkloadPgTests


class OperatorWorkloadPrivateHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg = StudioOperatorWorkloadPgTests
        cls.pg.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.fixture = self.pg("test_scoped_operator_worklist_counts_no_private_text_or_fabricated_go")
        self.fixture.setUp()
        self.token = "a" * 64
        self.server = StudioLoopbackServer(
            0, StudioLocalReaders(
                None, None, None, workload_reader=self.fixture.store,
            ), self.token,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def call(self, body, *, token=True, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + self.token
        if origin:
            headers["Origin"] = origin
        conn.request("POST", "/v1/operator/workload", json.dumps(body).encode(), headers)
        result = conn.getresponse()
        code = result.status
        received = json.loads(result.read())
        conn.close()
        return code, received

    def test_private_collection_workload_real_postgres_revocation_and_readback(self):
        body = {"collection_id": "col:alpha", "limit": 2}
        self.assertEqual(self.call(body, token=False)[0], 401)
        self.assertEqual(self.call(body, origin="https://evil.invalid")[0], 403)
        status, packet = self.call(body)
        self.assertEqual(status, 200, packet)
        result = packet["data"]
        self.assertEqual(result["version"], "studio-operator-workload-pg-v1")
        self.assertEqual(result["total_members"], 3)
        self.assertEqual([x["content_id"] for x in result["rows"]], ["content:1", "content:2"])
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["text_review_authority"])
        self.assertNotIn("DO NOT LEAK", json.dumps(packet))
        self.assertNotIn("https://fixture.invalid", json.dumps(packet))
        self.fixture.sql(
            "UPDATE content_capture SET rights_status='REVOKED' "
            "WHERE id='capture:one';"
        )
        after_status, after_packet = self.call(body)
        self.assertEqual(after_status, 200, after_packet)
        self.assertEqual(
            after_packet["data"]["rows"][0]["reason"],
            "CAPTURE_RIGHTS_NOT_CLEARED",
        )
        self.assertFalse(after_packet["data"]["dispatch_authorized"])

    def test_wrong_collection_extra_fields_and_inactive_reader_fail_closed(self):
        self.assertEqual(self.call({"collection_id": "col:missing"})[0], 422)
        self.assertEqual(self.call({"collection_id": "col:alpha", "secret": "x"})[0], 422)
        self.assertEqual(self.call({"collection_id": "col:alpha", "limit": True})[0], 422)
        self.assertEqual(self.call({"collection_id": "col:alpha", "after": "bad-cursor"})[0], 422)
        other_code, other = self.call({"collection_id": "col:beta"})
        self.assertEqual(other_code, 200, other)
        self.assertEqual(other["data"]["total_members"], 1)
        self.assertNotIn("content:secret", str(self.call({"collection_id": "col:alpha"})[1]))


if __name__ == "__main__":
    unittest.main()
