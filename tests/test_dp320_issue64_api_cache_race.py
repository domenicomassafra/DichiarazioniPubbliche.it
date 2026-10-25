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
    def test_rotated_release_pointer_does_not_serve_pinned_old_static_bytes(self):
        with tempfile.TemporaryDirectory(prefix="dp320-static-swap-") as temp:
            root = Path(temp)
            old, new = root / "old-release", root / "new-release"
            old.mkdir()
            new.mkdir()
            (old / "withdrawn.html").write_bytes(b"old approved record")
            (old / "retained.html").write_bytes(b"old statement version")
            (new / "retained.html").write_bytes(b"corrected statement version")
            current = root / "current"
            current.symlink_to(old, target_is_directory=True)

            def get(server, path):
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    conn.request("GET", path)
                    response = conn.getresponse()
                    return response.status, response.read(), response.getheader("Cache-Control")
                finally:
                    conn.close()

            with build_server(None, static_dir=current) as server:
                runner = threading.Thread(target=server.serve_forever, daemon=True)
                runner.start()
                try:
                    self.assertEqual(get(server, "/withdrawn.html")[:2], (200, b"old approved record"))
                    replacement = root / "next"
                    replacement.symlink_to(new, target_is_directory=True)
                    os.replace(replacement, current)
                    for path in ("/withdrawn.html", "/retained.html"):
                        with self.subTest(path=path):
                            self.assertEqual(get(server, path), (404, b"", "no-store"))
                    # A rollback to a previously withdrawn inode must not
                    # resurrect its response in an already-running listener.
                    back = root / "back"
                    back.symlink_to(old, target_is_directory=True)
                    os.replace(back, current)
                    self.assertEqual(get(server, "/withdrawn.html"), (404, b"", "no-store"))
                    forward = root / "forward"
                    forward.symlink_to(new, target_is_directory=True)
                    os.replace(forward, current)
                finally:
                    server.shutdown()
                    runner.join(timeout=5)
            with build_server(None, static_dir=current) as server:
                runner = threading.Thread(target=server.serve_forever, daemon=True)
                runner.start()
                try:
                    self.assertEqual(get(server, "/withdrawn.html")[:2], (404, b""))
                    self.assertEqual(get(server, "/retained.html")[:2], (200, b"corrected statement version"))
                finally:
                    server.shutdown()
                    runner.join(timeout=5)

    def test_rotation_after_open_but_before_http_headers_refuses_stale_bytes(self):
        with tempfile.TemporaryDirectory(prefix="dp320-static-open-race-") as temp:
            root = Path(temp)
            old, new = root / "old", root / "corrected"
            old.mkdir()
            new.mkdir()
            (old / "record.html").write_bytes(b"old now-withdrawn record")
            current = root / "current"
            current.symlink_to(old, target_is_directory=True)
            with build_server(None, static_dir=current) as server:
                listener = threading.Thread(target=server.serve_forever, daemon=True)
                listener.start()
                replacement = root / "next"
                replacement.symlink_to(new, target_is_directory=True)
                real_open = os.open
                rotated = threading.Event()

                def open_and_rotate(path, flags, *args, **kwargs):
                    fd = real_open(path, flags, *args, **kwargs)
                    if path == "record.html" and kwargs.get("dir_fd") is not None:
                        os.replace(replacement, current)
                        rotated.set()
                    return fd

                try:
                    with patch("dichiarazioni_pubbliche.public_api.os.open", side_effect=open_and_rotate):
                        connection = http.client.HTTPConnection(
                            "127.0.0.1", server.server_port, timeout=5
                        )
                        try:
                            connection.request("GET", "/record.html")
                            response = connection.getresponse()
                            self.assertEqual(response.status, 404)
                            self.assertEqual(response.getheader("Cache-Control"), "no-store")
                            self.assertEqual(response.read(), b"")
                        finally:
                            connection.close()
                    self.assertTrue(rotated.is_set())
                finally:
                    server.shutdown()
                    listener.join(timeout=5)

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
