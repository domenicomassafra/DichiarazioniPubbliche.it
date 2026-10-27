"""DP-518A: immutable on-host releases, HTTP readback and safe rollback."""

import hashlib
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.public_api import build_server
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from tools.dp481_minipc_release import activate, rehearse, stage, verify
from tools import dp481_minipc_release as release_tool


ROOT = Path(__file__).resolve().parents[1]


def read(server, path):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache"})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


class MiniPCImmutableReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dp481-release-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        (self.source / "poc" / "dichiarazioni_pubbliche").mkdir(parents=True)
        (self.source / "poc" / "dichiarazioni_pubbliche" / "__init__.py").write_text("# test source\n")
        (self.source / "db").mkdir()
        (self.source / "db" / "schema.v1.sql").write_text("-- schema fixture\n")
        self.static = self.base / "static"
        self.static.mkdir()
        self.projection = self.base / "projection"
        self.projection.mkdir()
        self.root = self.base / "releases-root"
        self.demo = json.loads((ROOT / "web/src/data/demo-projection.json").read_text())

    def make(self, *, withdrawn):
        (self.static / "index.html").write_bytes(b"<html>safe static</html>")
        quote = self.static / "withdrawn.html"
        if withdrawn:
            quote.unlink(missing_ok=True)
        else:
            quote.write_bytes(b"withdrawn quote 481")
        (self.static / "search-index.v1.json").write_bytes(b"{}" if withdrawn else b'{"old":true}')
        body = dict(self.demo)
        if withdrawn:
            body.update(dossiers=[], dossier_count=0, topics=[], contents=[], omitted_count=0)
            body["dataset_sha256"] = projection_dataset_sha256(body)
        (self.projection / "index.json").write_text(json.dumps(body, sort_keys=True))
        return stage(self.root, self.source, self.static, self.projection,
                     git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")

    def server(self):
        server = build_server(self.root / "current" / "projection" / "index.json",
                              static_dir=self.root / "current" / "static")
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        runner.start()
        self.addCleanup(lambda: (server.shutdown(), runner.join(timeout=5), server.server_close()))
        return server

    def test_immutable_stage_atomic_switch_live_http_and_rollback(self):
        old = self.make(withdrawn=False)
        activate(self.root, old["release_id"], expected=None)
        host = self.server()
        self.assertEqual(read(host, "/withdrawn.html"), (200, b"withdrawn quote 481"))
        self.assertEqual(verify(self.root, origin=f"http://127.0.0.1:{host.server_port}")["status"], "PASS")

        safe = self.make(withdrawn=True)
        with self.assertRaisesRegex(ValueError, "POINTER_MISMATCH"):
            activate(self.root, safe["release_id"], expected=None)
        activate(self.root, safe["release_id"], expected=old["release_id"])
        self.assertEqual(read(host, "/withdrawn.html")[0], 404)
        self.assertEqual(json.loads(read(host, "/api/v1/index.json")[1])["dossier_count"], 0)
        # Old listener is pinned to the old inode and MUST be restarted to pass readback.
        with self.assertRaisesRegex(ValueError, "HTTP_MISMATCH"):
            verify(self.root, origin=f"http://127.0.0.1:{host.server_port}")
        fresh = self.server()
        proof = verify(self.root, origin=f"http://127.0.0.1:{fresh.server_port}")
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["release_id"], safe["release_id"])
        self.assertEqual(read(fresh, "/withdrawn.html")[0], 404)

        # Replaying an unsafe old release is detectable; safe rollback restores it.
        activate(self.root, old["release_id"], expected=safe["release_id"])
        self.assertEqual(read(fresh, "/withdrawn.html")[0], 404)
        activate(self.root, safe["release_id"], expected=old["release_id"])
        self.assertEqual(verify(self.root, origin=f"http://127.0.0.1:{self.server().server_port}")["status"], "PASS")

    def test_wrong_hash_stale_pointer_and_manifest_mutation_fail(self):
        first = self.make(withdrawn=True)
        activate(self.root, first["release_id"], expected=None)
        release = self.root / "releases" / first["release_id"]
        (release / "static" / "index.html").chmod(0o644)
        (release / "static" / "index.html").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            verify(self.root)
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            activate(self.root, first["release_id"], expected=first["release_id"])
        (release / "static" / "index.html").write_bytes(b"<html>safe static</html>")
        self.assertEqual(verify(self.root)["status"], "PASS")
        (self.root / "current").unlink()
        (self.root / "current").symlink_to("releases/nonexistent")
        with self.assertRaisesRegex(ValueError, "POINTER_INVALID"):
            verify(self.root)

    def test_stage_rejects_symlinked_public_asset_and_idempotent_restage(self):
        candidate = self.make(withdrawn=True)
        self.assertEqual(candidate["release_id"], self.make(withdrawn=True)["release_id"])
        (self.static / "leak.txt").symlink_to(self.projection / "index.json")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ASSET"):
            self.make(withdrawn=True)

    def test_disposable_host_rehearsal_verifies_safe_http_rollback(self):
        self.make(withdrawn=True)
        result = rehearse(self.source, self.static, self.projection,
                          git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        self.assertEqual(result["status"], "PASS_PRIVATE_REHEARSAL")
        self.assertEqual(result["safe_release_id"], result["rollback_release_id"])
        self.assertEqual(result["withdrawn_old_listener_http"], 404)
        self.assertFalse(result["publication_authorized"])

    def test_symlink_inserted_after_source_preflight_cannot_copy_private_bytes(self):
        self.make(withdrawn=True)
        secret = self.base / "private.txt"
        secret.write_bytes(b"private not public")
        target = self.static / "search-index.v1.json"
        original_check = release_tool.safe_files

        def swap_after_preflight(directory):
            result = original_check(directory)
            if directory == self.static:
                target.unlink()
                target.symlink_to(secret)
            return result

        with patch.object(release_tool, "safe_files", side_effect=swap_after_preflight):
            with self.assertRaisesRegex(ValueError, "UNSAFE_ASSET"):
                stage(self.root, self.source, self.static, self.projection,
                      git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")


if __name__ == "__main__":
    unittest.main()
