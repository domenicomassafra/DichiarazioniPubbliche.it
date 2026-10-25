"""DP-320/#64: an atomic withdrawal during a cached API read must fail closed."""

import json
import http.client
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.public_api import build_server, dispatch, load_index


DEMO = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"


class WithdrawDuringCachedReadTests(unittest.TestCase):
    def test_withdrawn_static_route_never_caches_absence(self):
        with tempfile.TemporaryDirectory(prefix="dp320-issue64-qa-") as temp:
            static = Path(temp) / "static"
            static.mkdir()
            # This URL existed in the previous immutable release. The new
            # static root deliberately omits it after rights withdrawal.
            with build_server(None, static_dir=static) as server:
                runner = threading.Thread(target=server.serve_forever, daemon=True)
                runner.start()
                try:
                    for method in ("GET", "HEAD"):
                        with self.subTest(method=method):
                            connection = http.client.HTTPConnection(
                                "127.0.0.1", server.server_port, timeout=5
                            )
                            try:
                                connection.request(method, "/withdrawn-record.html")
                                response = connection.getresponse()
                                self.assertEqual(response.status, 404)
                                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                                self.assertEqual(response.getheader("Surrogate-Control"), "no-store")
                                self.assertEqual(response.read(), b"")
                            finally:
                                connection.close()
                finally:
                    server.shutdown()
                    runner.join(timeout=5)

    def test_projection_replacement_after_cached_stat_must_not_serve_old_record(self):
        original = DEMO.read_bytes()
        with tempfile.TemporaryDirectory(prefix="dp320-issue64-qa-") as temp:
            target = Path(temp) / "index.json"
            target.write_bytes(original)
            self.assertTrue(load_index(target).entries)
            before = dispatch("GET", "/api/v1/findings", projection_path=target)
            self.assertEqual(before.status, 200)
            self.assertTrue(json.loads(before.body)["data"])

            old_stat = target.stat()
            replacement = Path(temp) / "withdrawn.json"
            invalid = b'{"invalid":true}'
            replacement.write_bytes(invalid + b" " * (len(original) - len(invalid)))
            os.utime(replacement, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))

            real_stat = Path.stat
            swapped = False

            def swap_after_stat(path, *args, **kwargs):
                nonlocal swapped
                result = real_stat(path, *args, **kwargs)
                if path == target and not swapped:
                    swapped = True
                    os.replace(replacement, target)
                return result

            with patch.object(Path, "stat", swap_after_stat):
                after = dispatch(
                    "GET", "/api/v1/findings", projection_path=target,
                    conditional_headers={"if-none-match": before.headers["ETag"]},
                )
            self.assertTrue(swapped)
            self.assertEqual(after.status, 503)
            self.assertEqual(json.loads(after.body)["error"]["code"],
                             "PUBLIC_PROJECTION_UNAVAILABLE")
            self.assertEqual(after.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
