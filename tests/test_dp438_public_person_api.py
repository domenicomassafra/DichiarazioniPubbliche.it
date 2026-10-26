"""DP-438 HTTP seam: a current independently pinned zero-Statement Person."""
import json
import hashlib
import http.client
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_dp438_public_person import bundle, identity, person, project
from dichiarazioni_pubbliche.public_api import dispatch, build_server


class PublicPersonV3ApiTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="dp438-api-")
        self.addCleanup(self.scratch.cleanup)
        root = Path(self.scratch.name)
        self.api = root / "people.json"
        self.pins = root / "pins.json"
        self.v2 = root / "v2.json"
        self.v2.write_text(json.dumps(bundle(v2=True)), encoding="utf8")
        zero = person("person:zero", slug="persona-zero")
        held = person("person:private", slug="persona-private", name="Private Candidate")
        self.people = project([zero, held], [identity(zero), identity(held, status="HELD")])
        self.api.write_text(json.dumps(self.people, ensure_ascii=False), encoding="utf8")
        self.current_pins = {
            "publicationAuthorized": True,
            "allowPrivatePersonPreview": True,
            "personSha256": self.people["dataset_sha256"],
            "validUntil": "2099-01-01T00:00:00Z",
        }
        self.set_pins(self.current_pins)
        self.api.write_text(json.dumps({**self.people, "release_pins_sha256": hashlib.sha256(
            json.dumps(self.current_pins, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf8")).hexdigest()}), encoding="utf8")
        self.settings = patch.dict(os.environ, {
            "DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3": "1",
            "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_API_PATH": str(self.api),
            "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH": str(self.pins),
        })
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def set_pins(self, pins):
        self.pins.write_text(json.dumps(pins), encoding="utf8")

    def get(self, path, *, method="GET", headers=None):
        return dispatch(method, path, projection_path=self.v2, conditional_headers=headers)

    def test_v3_rejects_legacy_dossier_projection_from_every_api_reader(self):
        # A v2 publication must not reveal someone withheld by independent v3 pins.
        legacy = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"
        candidate = json.loads(legacy.read_text(encoding="utf8"))
        self.assertGreater(candidate["dossier_count"], 0)
        for route in ("/api/v1/people", "/api/v1/records",
                      "/api/v1/health", "/api/v1/index.json"):
            with self.subTest(route=route):
                response = dispatch("GET", route, projection_path=legacy)
                self.assertEqual(response.status, 503)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn(b"Demo", response.body)

    def test_zero_statement_person_visible_in_api_without_finding(self):
        response = self.get("/api/v1/people")
        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["meta"]["count"], 1)
        self.assertEqual(payload["meta"]["dataset_fingerprint"], bundle(v2=True)["dataset_sha256"])
        self.assertEqual(payload["meta"]["person_dataset_sha256"], self.current_pins["personSha256"])
        self.assertEqual(payload["data"][0]["person_id"], "person:zero")
        self.assertEqual(payload["data"][0]["route"], "/persone/persona-zero/")
        self.assertEqual(payload["data"][0]["statements"], [])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        detail = self.get("/api/v1/people/persona-zero")
        self.assertEqual(detail.status, 200)
        detail_payload = json.loads(detail.body)
        self.assertEqual(detail_payload["data"]["person_id"], "person:zero")
        self.assertEqual(detail_payload["data"]["statements"], [])
        self.assertEqual(detail_payload["meta"]["person_dataset_sha256"], self.current_pins["personSha256"])
        self.assertEqual(detail_payload["meta"]["link"], "/api/v1/people/persona-zero")
        self.assertEqual(self.get("/api/v1/people/persona-zero", method="HEAD").body, b"")

    def test_unknown_private_held_and_revoked_share_generic_404(self):
        unknown = self.get("/api/v1/people/does-not-exist")
        for slug in ("persona-private", "persona-revoked"):
            forbidden = self.get("/api/v1/people/" + slug)
            self.assertEqual(forbidden.status, 404)
            self.assertEqual(forbidden.body, unknown.body)
        self.assertNotIn(b"Private Candidate", self.get("/api/v1/people").body)

    def test_expired_or_rotated_release_denies_list_and_detail(self):
        for pins in (
            {**self.current_pins, "personSha256": "f" * 64},
            {**self.current_pins, "publicationAuthorized": False},
            {**self.current_pins, "validUntil": "2000-01-01T00:00:00Z"},
        ):
            with self.subTest(pins=pins):
                self.set_pins(pins)
                self.assertEqual(self.get("/api/v1/people").status, 503)
                self.assertEqual(self.get("/api/v1/people/persona-zero").status, 503)

    def test_signed_asset_with_malformed_statement_route_fails_closed(self):
        # Even a digest-matching malformed asset must not become an API 200
        # or trigger IndexError while checking the static release.
        invalid = json.loads(self.api.read_text(encoding="utf8"))
        invalid["people"][0]["statements"] = [{"statement_route": "/broken"}]
        person_sha = hashlib.sha256(json.dumps(
            invalid["people"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf8")).hexdigest()
        pins = {**self.current_pins, "personSha256": person_sha}
        self.set_pins(pins)
        invalid["dataset_sha256"] = person_sha
        invalid["release_pins_sha256"] = hashlib.sha256(json.dumps(
            pins, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf8")).hexdigest()
        self.api.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf8")
        self.assertEqual(self.get("/api/v1/people").status, 503)

    def test_nonempty_legacy_projection_blocks_v3_api_release(self):
        demo = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"
        self.v2.write_bytes(demo.read_bytes())
        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3": "0"}):
            self.assertEqual(self.get("/api/v1/people").status, 200)
        for endpoint in ("/api/v1/people", "/api/v1/findings", "/api/v1/records"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.get(endpoint).status, 503)

    def test_missing_authority_never_downgrades_to_v2(self):
        self.pins.unlink()
        self.assertEqual(self.get("/api/v1/people").status, 503)

    def test_static_person_search_and_sitemap_are_denied_after_pin_revocation(self):
        root = Path(self.scratch.name) / "site"
        page = root / "persone" / "persona-zero"
        page.mkdir(parents=True)
        (page / "index.html").write_text("Approved Person original", encoding="utf8")
        (root / "search-index.v1.json").write_text(json.dumps({"records": [
            {"kind": "person", "route": "/persone/persona-zero/", "title": "Alex Demo"}
        ]}), encoding="utf8")
        (root / "sitemap.xml").write_text(
            "<urlset><url><loc>https://dichiarazionipubbliche.it/persone/persona-zero/</loc></url></urlset>",
            encoding="utf8")
        (root / "public-people.v3.json").write_bytes(self.api.read_bytes())
        legacy_person = root / "record" / "person" / "persona-private"
        legacy_person.mkdir(parents=True)
        (legacy_person / "index.html").write_text("Private Candidate", encoding="utf8")
        server = build_server(self.v2, static_dir=root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(path, *, method="GET", headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                conn.request(method, path, headers=headers or {})
                response = conn.getresponse()
                return response.status, response.read(), response.getheader("Cache-Control")
            finally:
                conn.close()

        try:
            routes = ("/persone/persona-zero/", "/search-index.v1.json", "/sitemap.xml")
            for route in routes:
                self.assertEqual(request(route)[0], 200)
            # A legacy identity path must not reveal an unapproved Person.
            self.assertEqual(request("/record/person/persona-private/")[0], 404)
            self.set_pins({**self.current_pins, "publicationAuthorized": False})
            for route in (*routes, "/persone/persona-zero"):
                with self.subTest(route=route):
                    status, content, cache = request(route)
                    self.assertEqual(status, 404)
                    self.assertEqual(content, b"")
                    self.assertEqual(cache, "no-store")
                    status, _, cache = request(route, headers={"If-Modified-Since": "Wed, 01 Jan 2099 00:00:00 GMT", "If-None-Match": "*"})
                    self.assertEqual((status, cache), (404, "no-store"))
                    status, body, cache = request(route, method="HEAD")
                    self.assertEqual((status, body, cache), (404, b"", "no-store"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


    def test_v3_api_rejects_nonempty_legacy_v2_projection_on_all_surfaces(self):
        # The same enabled v3 Person release must not expose a v2 dossier
        # through records, health, index or another v1 API entry point.
        demo = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"
        fixture = json.loads(demo.read_text(encoding="utf8"))
        self.assertGreater(fixture["dossier_count"], 0)
        self.v2.write_text(json.dumps(fixture), encoding="utf8")
        for path in ("/api/v1/people", "/api/v1/people/persona-zero",
                     "/api/v1/records", "/api/v1/findings", "/api/v1/health",
                     "/api/v1/index.json", "/api/v1/openapi.json"):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status, 503)
                self.assertNotIn(b"Alex Demo", response.body)

    def test_explicit_zero_opt_out_preserves_v2_api(self):
        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3": "0"}):
            self.assertEqual(self.get("/api/v1/people").status, 200)

    def test_pin_change_with_same_person_sha_withdraws_previous_release(self):
        self.set_pins({**self.current_pins, "statementSha256": "0" * 64})
        self.assertEqual(self.get("/api/v1/people/persona-zero").status, 503)

    def test_authorized_rotation_withdraws_one_person_and_retains_another(self):
        zero = person("person:zero", slug="persona-zero")
        other = person("person:other", slug="persona-other", name="Other Person")
        both = project([zero, other], [identity(zero), identity(other)])
        current = {**self.current_pins, "personSha256": both["dataset_sha256"]}
        self.set_pins(current)
        self.api.write_text(json.dumps({**both, "release_pins_sha256": hashlib.sha256(
            json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()}))
        self.assertEqual(self.get("/api/v1/people/persona-zero").status, 200)
        self.assertEqual(self.get("/api/v1/people/persona-other").status, 200)
        retained = project([other], [identity(other)])
        rotated = {**current, "personSha256": retained["dataset_sha256"]}
        self.set_pins(rotated)
        self.api.write_text(json.dumps({**retained, "release_pins_sha256": hashlib.sha256(
            json.dumps(rotated, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()}))
        self.assertEqual(self.get("/api/v1/people/persona-zero").status, 404)
        self.assertEqual(self.get("/api/v1/people/persona-other").status, 200)
        self.assertEqual(self.get("/api/v1/people/persona-zero").body,
                         self.get("/api/v1/people/unknown-person").body)
        root = Path(self.scratch.name) / "rotated-site"
        for slug in ("persona-zero", "persona-other"):
            page = root / "persone" / slug
            page.mkdir(parents=True)
            (page / "index.html").write_text(slug, encoding="utf8")
        (root / "public-people.v3.json").write_bytes(self.api.read_bytes())
        (root / "search-index.v1.json").write_text(json.dumps({"records": [
            {"kind": "person", "route": "/persone/persona-zero/", "title": "Alex Demo"},
            {"kind": "person", "route": "/persone/persona-other/", "title": "Other Person"},
        ]}), encoding="utf8")
        (root / "sitemap.xml").write_text("<urlset>" + "".join(
            f"<url><loc>https://dichiarazionipubbliche.it/persone/{slug}/</loc></url>"
            for slug in ("persona-zero", "persona-other")) + "</urlset>", encoding="utf8")
        server = build_server(self.v2, static_dir=root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for static_asset in ("/search-index.v1.json", "/sitemap.xml"):
                conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                try:
                    conn.request("GET", static_asset)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 404, static_asset)
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                    response.read()
                finally:
                    conn.close()
            for slug, expected in (("persona-zero", 404), ("persona-other", 200)):
                with self.subTest(slug=slug):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                    try:
                        conn.request("GET", f"/persone/{slug}/")
                        response = conn.getresponse()
                        self.assertEqual(response.status, expected)
                        response.read()
                    finally:
                        conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_v3_static_tree_never_serves_with_disabled_runtime_gate(self):
        root = Path(self.scratch.name) / "disabled-site"
        route = root / "persone" / "persona-zero"
        route.mkdir(parents=True)
        (route / "index.html").write_text("old identity", encoding="utf8")
        (root / "public-people.v3.json").write_text("{}", encoding="utf8")
        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3": "0"}):
            server = build_server(self.v2, static_dir=root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                try:
                    conn.request("GET", "/persone/persona-zero/")
                    response = conn.getresponse()
                    self.assertEqual(response.status, 404)
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                    response.read()
                finally:
                    conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
