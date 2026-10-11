"""Real authenticated loopback routing for DP-242 read-only machine previews."""

import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow,
)
from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders,
    StudioLoopbackServer,
)
from tests.test_studio_discovery_inbox_workflow import FakeRuntime, row
from tests.test_studio_candidate_review_handoff import MatchStore, PromotionContext


class StudioMachineHttpTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime([row()])
        self.match = MatchStore()
        self.promotion = PromotionContext()
        self.server = StudioLoopbackServer(
            0,
            StudioLocalReaders(None, None, self.match, self.runtime, self.promotion),
            "a" * 64,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, path, payload, *, token=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + "a" * 64
        if origin:
            headers["Origin"] = origin
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        conn.request("POST", path, body=json.dumps(payload), headers=headers)
        response = conn.getresponse()
        data, headers = json.loads(response.read()), dict(response.getheaders())
        conn.close()
        return response.status, data, headers

    def test_discovery_machine_preview_requires_local_token_and_exact_cas_inputs(self):
        path = "/v1/discovery/machine-preview"
        snapshot = DiscoveryInboxWorkflow(self.runtime).list_rows(
            collection_id="collection:01"
        )["rows"][0]
        payload = {
            "collection_id": "collection:01",
            "hit_id": "hit:01",
            "request_key": "task:01",
            "expected_revision": 0,
            "expected_snapshot_sha256": snapshot["snapshot_sha256"],
        }
        self.assertEqual(self.call(path, payload, token=False)[0], 401)
        self.assertEqual(
            self.call(path, payload, origin="https://remote.invalid")[0], 403
        )
        code, result, headers = self.call(path, payload)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["data"]["status"], "HELD_EXCEPTION")
        self.assertFalse(result["data"]["dispatch_authorized"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertNotIn("PRIVATE QUERY", json.dumps(result))
        self.assertNotIn("task:01", json.dumps(result))
        self.assertEqual(self.call(path, payload | {"publish": True})[0], 422)
        self.assertEqual(self.call(path, payload | {"expected_revision": 99})[0], 422)

    def test_candidate_machine_preview_is_held_and_never_inherits_human_signoff(self):
        path = "/v1/candidate/machine-preview"
        payload = {
            "run_id": self.match.run_id,
            "claim_candidate_id": "candidate:1",
            "result_id": self.match.rows[0]["id"],
            "request_key": "task:02",
            "expected_content_id": "content:1",
            "expected_capture_sha256": self.promotion.data["passages"][0][
                "capture_sha256"
            ],
            "expected_input_fingerprint": self.match.fingerprint,
        }
        self.assertEqual(self.call(path, payload, token=False)[0], 401)
        code, result, _ = self.call(path, payload)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["data"]["status"], "HELD_MACHINE_AUTHORITY_UNAVAILABLE")
        self.assertFalse(result["data"]["human_review_approved"])
        self.assertFalse(result["data"]["machine_review_approved"])
        self.assertFalse(result["data"]["publication_authority"])
        self.assertEqual(self.call(path, payload | {"approve": True})[0], 422)
        self.promotion.data["passages"][0]["capture_hold_status"] = "RIGHTS"
        code, result, _ = self.call(path, payload)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["data"]["status"], "HELD_SOURCE_OR_ATTRIBUTION")


if __name__ == "__main__":
    unittest.main()
