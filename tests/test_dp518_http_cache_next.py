"""DP-518: the real HTTP adapter forbids new storage of withdrawable bytes."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.linked_data import (
    projection_linked_data_receipt,
    projection_ntriples,
)
from dichiarazioni_pubbliche.public_api import build_server


DEMO = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"


class DP518HTTPNoStoreTests(unittest.TestCase):
    def test_real_get_head_and_redirects_have_no_store_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            static = root / "static"
            private = root / "private"
            static.mkdir()
            private.mkdir()
            (static / "index.html").write_text("<html>DP518 safe canary</html>", encoding="utf-8")
            (static / "nested").mkdir()
            bundle = json.loads(DEMO.read_text(encoding="utf-8"))
            (private / "index.json").write_text(json.dumps(bundle), encoding="utf-8")
            (private / "index.nt").write_text(projection_ntriples(bundle), encoding="utf-8")
            (private / "linked-data-receipt.json").write_text(
                json.dumps(projection_linked_data_receipt(bundle)), encoding="utf-8"
            )
            with build_server(private / "index.json", static_dir=static) as server:
                runner = threading.Thread(target=server.serve_forever, daemon=True)
                runner.start()
                try:
                    paths = ("/", "/api/v1/health", "/api/v1/index.json",
                             "/api/v1/findings", "/llms.txt", "/index.nt")
                    for path in paths:
                        for method in ("GET", "HEAD"):
                            with self.subTest(path=path, method=method):
                                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                                try:
                                    conn.request(method, path)
                                    response = conn.getresponse()
                                    payload = response.read()
                                    self.assertEqual(response.status, 200)
                                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                                    self.assertEqual(response.getheader("Surrogate-Control"), "no-store")
                                    if method == "HEAD":
                                        self.assertEqual(payload, b"")
                                finally:
                                    conn.close()
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    try:
                        conn.request("GET", "/nested")
                        response = conn.getresponse()
                        self.assertEqual(response.status, 301)
                        self.assertEqual(response.getheader("Cache-Control"), "no-store")
                        response.read()
                    finally:
                        conn.close()
                finally:
                    server.shutdown()
                    runner.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
