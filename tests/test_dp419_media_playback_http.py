"""DP419 real authenticated HTTP media bytes, revocation, privacy, and 401/422."""
from __future__ import annotations

from dataclasses import replace
import http.client
import json
import threading

from tests.test_dp419_verified_playback import VerifiedPlaybackTests
from dichiarazioni_pubbliche.studio_local_api import StudioLocalReaders, StudioLoopbackServer


class VerifiedMediaHttpTests(VerifiedPlaybackTests):
    def setUp(self):
        super().setUp()
        self.token = "a" * 64
        self.server = StudioLoopbackServer(
            0,
            StudioLocalReaders(None, self.reader, None,
                               body_store=self.store, rights_reader=self.rights),
            self.token,
        )
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, body, token=None, method="POST", path="/v1/media/playback"):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=10,
        )
        headers = {"Content-Type": "application/json"}
        if token is not False:
            headers["Authorization"] = "Bearer " + (token or self.token)
        connection.request(method, path, json.dumps(body).encode(), headers)
        response = connection.getresponse()
        status = response.status
        payload = response.read()
        reply_headers = dict(response.getheaders())
        connection.close()
        return status, payload, reply_headers

    def test_real_wav_delivered_only_to_authenticated_client(self):
        body = {"binding_id": "media-binding:test"}
        self.assertEqual(self.call(body, token=False)[0], 401)
        self.assertEqual(self.call(body, token="0" * 64)[0], 401)
        self.assertEqual(self.call({"binding_id": "media-binding:test", "extra": 1})[0], 422)
        status, payload, headers = self.call(body)
        self.assertEqual(status, 200, (status, payload[:300]))
        self.assertEqual(payload, self.bytes)
        self.assertEqual(headers["Content-Type"], "audio/wav")
        self.assertEqual(headers["X-Seek-Start-Ms"], "1200")
        self.assertEqual(headers["X-Seek-End-Ms"], "3400")
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertNotIn(b"https:", payload[:1024])

    def test_current_revocation_blocks_further_media_requests(self):
        body = {"binding_id": "media-binding:test"}
        self.assertEqual(self.call(body)[0], 200)
        self.rights.record = replace(self.rights.record, rights_status="REVOKED")
        status, payload, _ = self.call(body)
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(payload)["error"], "STUDIO_LOCAL_REQUEST_OR_DATA_INVALID")
        self.assertNotIn(b"rights-review", payload)
        self.assertNotIn(b"https:", payload)

    def test_capture_mismatch_and_no_player_configuration_hold(self):
        self.reader.material["capture_sha256"] = "0" * 64
        self.assertEqual(self.call({"binding_id": "media-binding:test"})[0], 422)
        self.assertEqual(self.call({"binding_id": "media-binding:test"}, method="GET")[0], 405)


if __name__ == "__main__":
    import unittest
    unittest.main()
