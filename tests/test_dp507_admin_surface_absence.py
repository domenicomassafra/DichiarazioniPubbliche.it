"""DP-507: no remotely reachable administrative mutation is accidentally exposed."""

import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.public_api import build_server  # noqa: E402
from dichiarazioni_pubbliche.studio_local_api import StudioLoopbackServer  # noqa: E402


class AdminHttpBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = build_server(
            str(ROOT / "web" / "src" / "data" / "demo-projection.json"),
            host="127.0.0.1",
            port=0,
            static_dir=cls.temp.name,
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()
        cls.temp.cleanup()

    def test_public_admin_and_studio_mutations_are_rejected_on_actual_http(self):
        port = self.server.server_port
        for path in (
            "/api/v1/admin/review",
            "/api/v1/admin/publish",
            "/admin/approve",
            "/studio/queue-control",
            "/api/v1/review",
            "/api/v1/moderate",
        ):
            for verb in ("POST", "PATCH", "PUT", "DELETE"):
                with self.subTest(path=path, verb=verb):
                    client = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
                    try:
                        client.request(verb, path, headers={"Content-Length": "0"})
                        response = client.getresponse()
                        payload = response.read()
                        self.assertEqual(response.status, 405)
                        self.assertEqual(
                            json.loads(payload)["error"]["code"], "METHOD_NOT_ALLOWED"
                        )
                    finally:
                        client.close()

    def test_normal_studio_handler_refuses_remote_host_and_admin_mutation(self):
        server = StudioLoopbackServer(0, None, "a" * 64)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            self.assertEqual(server.server_address[0], "127.0.0.1")
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
            try:
                client.request(
                    "POST",
                    "/v1/candidate/decision-annotate",
                    headers={"Host": "remote.invalid", "Content-Length": "0"},
                )
                response = client.getresponse()
                response.read()
                self.assertEqual(response.status, 403)
            finally:
                client.close()
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
            try:
                client.request(
                    "POST",
                    "/v1/candidate/decision-annotate",
                    headers={
                        "Host": f"127.0.0.1:{port}",
                        "Authorization": "Bearer " + "a" * 64,
                        "Content-Length": "0",
                    },
                )
                response = client.getresponse()
                response.read()
                self.assertEqual(response.status, 404)
            finally:
                client.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
