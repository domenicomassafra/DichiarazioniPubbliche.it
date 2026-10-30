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
        home = (b'<html><head><link rel="icon" href="/favicon.svg"></head>'
                b'<body><main><h1>Safe static page</h1></main></body></html>')
        (self.static / "index.html").write_bytes(home)
        for route in ("esplora", "metodo", "correzioni", "dati", "progetto",
                      "accedi", "account", "privacy", "segnalazioni"):
            destination = self.static / route / "index.html"
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(home)
        (self.static / "favicon.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
        (self.static / "robots.txt").write_text("User-agent: *\nDisallow: /account/\n")
        (self.static / "sitemap.xml").write_text("<urlset/>")
        quote = self.static / "withdrawn.html"
        if withdrawn:
            quote.unlink(missing_ok=True)
        else:
            quote.write_bytes(b"withdrawn quote 481")
        body = dict(self.demo)
        if withdrawn:
            body.update(dossiers=[], dossier_count=0, topics=[], contents=[], omitted_count=0)
            body["dataset_sha256"] = projection_dataset_sha256(body)
        (self.projection / "index.json").write_text(json.dumps(body, sort_keys=True))
        index = {
            "schema_version": "dichiarazioni-pubbliche-search-index-v1",
            "projection_schema_version": body["schema_version"],
            "projection_sha256": body["dataset_sha256"],
            "generated_at": body["generated_at"],
            "records": [],
        }
        index["index_sha256"] = hashlib.sha256(json.dumps(
            index, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        (self.static / "search-index.v1.json").write_text(json.dumps(index))
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
        (release / "static" / "index.html").write_bytes(
            (b'<html><head><link rel="icon" href="/favicon.svg"></head>'
             b'<body><main><h1>Safe static page</h1></main></body></html>'))
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

    def test_missing_required_runtime_routes_and_favicon_fail_before_stage(self):
        self.make(withdrawn=True)
        for name in ("privacy/index.html", "segnalazioni/index.html", "favicon.svg",
                     "accedi/index.html", "robots.txt"):
            with self.subTest(missing=name):
                asset = self.static / name
                content = asset.read_bytes()
                asset.unlink()
                try:
                    with self.assertRaisesRegex(ValueError, "STATIC_ASSET_MISSING"):
                        stage(self.root, self.source, self.static, self.projection,
                              git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
                finally:
                    asset.parent.mkdir(parents=True, exist_ok=True)
                    asset.write_bytes(content)

    def test_missing_icon_link_fails_closed_before_stage(self):
        self.make(withdrawn=True)
        home = self.static / "index.html"
        home.write_bytes(b"<html><body>old stale home</body></html>")
        with self.assertRaisesRegex(ValueError, "STATIC_ICON_LINK_MISSING"):
            stage(self.root, self.source, self.static, self.projection,
                  git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")

    def test_signed_legacy_incomplete_release_fails_readback(self):
        self.make(withdrawn=True)
        (self.static / "privacy" / "index.html").unlink()
        (self.static / "favicon.svg").unlink()
        # Reproduce an old signed release from before the required-static check.
        with patch.object(release_tool, "check_static_contract", return_value=None):
            legacy = stage(self.root, self.source, self.static, self.projection,
                           git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with self.assertRaisesRegex(ValueError, "STATIC_ASSET_MISSING"):
            release_tool.validated(self.root, legacy["release_id"])

    def test_invalid_required_assets_rejected_before_stage(self):
        self.make(withdrawn=True)
        invalid = {
            "privacy/index.html": b"",
            "metodo/index.html": b"not an HTML document",
            "segnalazioni/index.html": b"<html><head></head><body>unfinished",
            "account/index.html": b"<html><head></head><body></body></html>",
            "progetto/index.html": (b"<html><head></head><body><main><h1>Page</h1>"
                                   b"<section><p>Unclosed paragraph</section></main></body></html>"),
            "favicon.svg": b"not an SVG",
            "sitemap.xml": b"<urlset><url>",
            "robots.txt": b"not a robots.txt document",
            "search-index.v1.json": b"{}",
        }
        for name, contents in invalid.items():
            with self.subTest(asset=name):
                asset = self.static / name
                original = asset.read_bytes()
                try:
                    asset.write_bytes(contents)
                    with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
                        stage(self.root, self.source, self.static, self.projection,
                              git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
                finally:
                    asset.write_bytes(original)

    def test_sealed_release_with_matching_hashes_but_invalid_content_rejected(self):
        self.make(withdrawn=True)
        (self.static / "privacy" / "index.html").write_bytes(b"")
        (self.static / "favicon.svg").write_bytes(b"not an SVG")
        (self.static / "sitemap.xml").write_bytes(b"not XML")
        with patch.object(release_tool, "check_static_contract", return_value=None):
            sealed = stage(self.root, self.source, self.static, self.projection,
                           git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
            activate(self.root, sealed["release_id"], expected=None)
        # The historical contract sealed matching hashes and served unusable public assets.
        host = self.server()
        self.assertEqual(read(host, "/privacy/"), (200, b""))
        self.assertEqual(read(host, "/favicon.svg"), (200, b"not an SVG"))
        self.assertEqual(read(host, "/sitemap.xml"), (200, b"not XML"))
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            release_tool.validated(self.root, sealed["release_id"])

    def test_search_index_projection_drift_rejected_with_valid_self_hash(self):
        self.make(withdrawn=True)
        path = self.static / "search-index.v1.json"
        index = json.loads(path.read_text())
        index["projection_sha256"] = "f" * 64
        material = {key: value for key, value in index.items() if key != "index_sha256"}
        index["index_sha256"] = hashlib.sha256(json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        path.write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            stage(self.root, self.source, self.static, self.projection,
                  git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with patch.object(release_tool, "check_static_contract", return_value=None):
            sealed = stage(self.root, self.source, self.static, self.projection,
                           git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            release_tool.validated(self.root, sealed["release_id"])

    def test_search_records_must_match_public_shape_and_empty_projection(self):
        valid_extra = {
            "id": "not-in-projection", "kind": "content", "title": "Unapproved record",
            "subtitle": "", "published_at": None, "assessment": None,
            "route": "/contenuti/not-in-projection/", "has_corrections": False,
            "has_rights_of_reply": False, "wording_type": None,
            "source_wording_type": None, "direct_quote_eligible": False,
            "primary_terms": [], "secondary_terms": [],
        }
        for withdrawn, records in ((False, [{}]),
                                   (False, [{**valid_extra, "kind": []}]),
                                   (False, [{**valid_extra, "source_wording_type": {}}]),
                                   (True, [valid_extra])):
            with self.subTest(withdrawn=withdrawn):
                self.make(withdrawn=withdrawn)
                path = self.static / "search-index.v1.json"
                index = json.loads(path.read_text())
                index["records"] = records
                material = {key: value for key, value in index.items() if key != "index_sha256"}
                index["index_sha256"] = hashlib.sha256(json.dumps(
                    material, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode()).hexdigest()
                path.write_text(json.dumps(index))
                with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
                    stage(self.root, self.source, self.static, self.projection,
                          git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
                with patch.object(release_tool, "check_static_contract", return_value=None):
                    sealed = stage(self.root, self.source, self.static, self.projection,
                                   git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
                with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
                    release_tool.validated(self.root, sealed["release_id"])

    def test_hidden_only_required_page_rejected_before_stage_and_after_sealing(self):
        self.make(withdrawn=True)
        path = self.static / "privacy/index.html"
        path.write_text(path.read_text().replace("<main>", "<main hidden>"))
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            stage(self.root, self.source, self.static, self.projection,
                  git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with patch.object(release_tool, "check_static_contract", return_value=None):
            sealed = stage(self.root, self.source, self.static, self.projection,
                           git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            release_tool.validated(self.root, sealed["release_id"])

    def test_empty_page_and_missing_astropack_rejected_even_with_sealed_hashes(self):
        self.make(withdrawn=True)
        home = self.static / "index.html"
        original = home.read_text()
        home.write_text(home.read_text().replace(
            "</head>", '<link rel="stylesheet" href="/_astro/absent.css"></head>'))
        with self.assertRaisesRegex(ValueError, "STATIC_ASSET_MISSING"):
            stage(self.root, self.source, self.static, self.projection,
                  git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with patch.object(release_tool, "check_static_contract", return_value=None):
            sealed = stage(self.root, self.source, self.static, self.projection,
                           git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with self.assertRaisesRegex(ValueError, "STATIC_ASSET_MISSING"):
            release_tool.validated(self.root, sealed["release_id"])
        home.write_text(original)
        (self.static / "privacy/index.html").write_text(
            "<html><head></head><body><main></main></body></html>")
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            stage(self.root, self.source, self.static, self.projection,
                  git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with patch.object(release_tool, "check_static_contract", return_value=None):
            sealed_empty = stage(self.root, self.source, self.static, self.projection,
                                 git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            release_tool.validated(self.root, sealed_empty["release_id"])

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
