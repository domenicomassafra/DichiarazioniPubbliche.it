"""DP418: authenticated read-only PG review receipt, no mutation authority."""
from __future__ import annotations

import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders, StudioLoopbackServer, _StudioDecisionReader,
)
from tests.test_dp418_persisted_decision_pg_next import PersistedDecisionPgTests


class StudioDecisionReadHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PersistedDecisionPgTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        PersistedDecisionPgTests.tearDownClass()

    def setUp(self):
        self.fixture = PersistedDecisionPgTests(
            methodName="test_actual_pg_receipt_restart_replay_and_missing_identity_hold")
        self.fixture.setUp()
        self.token = "7" * 64
        self.server = StudioLoopbackServer(
            0, StudioLocalReaders(None, None, None,
                                  decision_reader=_StudioDecisionReader(self.fixture.pg.dsn)),
            self.token,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.fixture.tearDown()

    def request(self, body: dict, *, auth=True, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        if origin is not None:
            headers["Origin"] = origin
        connection.request("POST", "/v1/candidate/decision-receipt",
                           json.dumps(body).encode(), headers)
        response = connection.getresponse()
        status, headers = response.status, dict(response.getheaders())
        body = json.loads(response.read())
        connection.close()
        return status, body, headers

    def payload(self):
        return {
            "candidate_id": "candidate:review",
            "run_id": self.fixture.run_id,
            "capture_id": "capture:review",
            "passage_id": "passage:review",
            "request_key": "request:alice",
        }

    def test_attested_decision_restart_http_read_and_rights_withdrawal(self):
        record = self.fixture.request(decision="REVIEW_CREATE")
        event, receipt = self.fixture.sign(record, "alice")
        created = self.fixture.store.record(record, authority=self.fixture.authority,
                                       review_event=event, authority_receipt_id=receipt,
                                       credential_id="alice")
        self.assertEqual(created["result_code"], "CREATED")
        payload = self.payload()
        self.assertEqual(self.request(payload,auth=False)[0], 401)
        self.assertEqual(self.request(payload,origin="https://evil.invalid")[0],403)
        status, packet, headers = self.request(payload)
        self.assertEqual(status, 200, packet)
        view = packet["data"]
        self.assertTrue(view["historical_only"])
        self.assertFalse(view["review_authority"])
        self.assertFalse(view["promotion_authority"])
        self.assertFalse(view["publication_authority"])
        self.assertEqual(view["receipt_sha256"], created["receipt_sha256"])
        self.assertEqual(view["status"], "HISTORICAL_SOURCE_CURRENT")
        self.assertEqual(view["decision"], "REVIEW_CREATE")
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        serialized = json.dumps(packet)
        for secret in ("reviewer:alice", receipt, "PRIVATE fixture text", "PRIVATE claim",
                       "normalized_claim", "private_text", "credential_id"):
            self.assertNotIn(secret, serialized)
        self.fixture.pg._sql("UPDATE content_capture SET rights_status='REVOKED' WHERE id='capture:review';")
        revoked = self.request(payload)
        self.assertEqual(revoked[0],200,revoked[1])
        self.assertEqual(revoked[1]["data"]["status"],"HISTORICAL_SOURCE_WITHDRAWN")
        self.assertFalse(revoked[1]["data"]["review_authority"])
        self.assertEqual(self.request(payload | {"approve":True})[0],422)

    def test_foreign_candidate_run_capture_and_key_not_discoverable(self):
        for change in (
            {"candidate_id":"candidate:comparison"}, {"run_id":"run:foreign"},
            {"capture_id":"capture:foreign"}, {"passage_id":"passage:foreign"},
            {"request_key":"request:foreign"}, {"request_key":"../secret"},
        ):
            with self.subTest(change=change):
                code, data, _ = self.request(self.payload() | change)
                self.assertEqual(code,422,data)
                self.assertNotIn("PRIVATE",json.dumps(data))


if __name__ == "__main__":
    unittest.main()
