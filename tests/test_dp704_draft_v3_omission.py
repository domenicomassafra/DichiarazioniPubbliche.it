"""DP-704: a signed DRAFT release cannot pass live verification with v3 exposed."""

import unittest
from unittest.mock import patch

from tests import test_dp481_minipc_release as release_tests
from tools.dp481_minipc_release import activate, verify


class DraftReleaseV3OmissionTests(unittest.TestCase):
    setUp = release_tests.MiniPCImmutableReleaseTests.setUp
    make = release_tests.MiniPCImmutableReleaseTests.make
    server = release_tests.MiniPCImmutableReleaseTests.server

    def test_draft_release_rejects_accidentally_public_v3_http(self):
        draft = self.make(withdrawn=True)
        activate(self.root, draft["release_id"], expected=None)
        host = self.server()
        origin = f"http://127.0.0.1:{host.server_port}"
        self.assertEqual(verify(self.root, origin=origin)["status"], "PASS")
        handler = host.RequestHandlerClass
        original = handler._serve_api
        for leaked_path in ("/api/v3/statements", "/api/v3/opinions"):
            with self.subTest(path=leaked_path):
                def misconfigured(instance, method):
                    if instance.path == leaked_path:
                        instance.send_response(200)
                        instance.send_header("Content-Type", "application/json")
                        instance.send_header("Content-Length", "2")
                        instance.end_headers()
                        instance.wfile.write(b"{}")
                    else:
                        original(instance, method)

                with patch.object(handler, "_serve_api", misconfigured):
                    self.assertEqual(release_tests.read(host, leaked_path), (200, b"{}"))
                    with self.assertRaisesRegex(ValueError, "DP481_HTTP_MISMATCH"):
                        verify(self.root, origin=origin)
