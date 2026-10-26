"""DP-438 HTTP seam: a current independently pinned zero-Statement Person."""
import json
import http.client
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from test_dp438_public_person import bundle, identity, person, project
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

    def test_zero_statement_person_visible_in_api_without_finding(self):
        response = self.get("/api/v1/people")
        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["meta"]["count"], 1)
        self.assertEqual(payload["data"][0]["person_id"], "person:zero")
        self.assertEqual(payload["data"][0]["route"], "/persone/persona-zero/")
        self.assertEqual(payload["data"][0]["statements"], [])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.get("/api/v1/people/persona-zero").status, 200)
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

    def test_missing_authority_never_downgrades_to_v2(self):
        self.pins.unlink()
        self.assertEqual(self.get("/api/v1/people").status, 503)

    def test_static_person_search_and_sitemap_are_denied_after_pin_revocation(self):
        root = Path(self.scratch.name) / "site"
        page = root / "persone" / "persona-zero"
        page.mkdir(parents=True)
        (page / "index.html").write_text("Approved Person original", encoding="utf8")
        (root / "search-index.v1.json").write_text('{"records":["persona-zero"]}', encoding="utf8")
        (root / "sitemap.xml").write_text("<loc>/persone/persona-zero/</loc>", encoding="utf8")
        server = build_server(self.v2, static_dir=root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(path):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                conn.request("GET", path)
                response = conn.getresponse()
                return response.status, response.read(), response.getheader("Cache-Control")
            finally:
                conn.close()

        try:
            routes = ("/persone/persona-zero/", "/search-index.v1.json", "/sitemap.xml")
            for route in routes:
                self.assertEqual(request(route)[0], 200)
            self.set_pins({**self.current_pins, "publicationAuthorized": False})
            for route in routes:
                with self.subTest(route=route):
                    status, content, cache = request(route)
                    self.assertEqual(status, 404)
                    self.assertEqual(content, b"")
                    self.assertEqual(cache, "no-store")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
