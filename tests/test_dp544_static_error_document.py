"""DP-544: an ordinary missing page must explain itself, never return a blank 404.

Before the fix the static server answered every unknown page with
`Content-Length: 0`, so a browser showed its own bare "can't find the page"
error with no navigation. The empty body stays for withheld releases, private
or hidden paths and control files: only a published miss renders the bundled
error document.
"""

from __future__ import annotations

import http.client
from pathlib import Path
import tempfile
import threading
import unittest

from dichiarazioni_pubbliche.public_api import build_server


ERROR_PAGE = (
    '<html lang="it"><head><meta name="robots" content="noindex,nofollow"></head>'
    '<body><main id="main"><h1>Questa pagina non esiste.</h1>'
    '<a href="/esplora/">Cerca nell archivio pubblico</a></main></body></html>'
)


class StaticErrorDocumentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write_site()

    def write_site(self, *, error_page: str | None = ERROR_PAGE):
        (self.root / "index.html").write_text("<html><body>Home</body></html>", encoding="utf8")
        if error_page is not None:
            (self.root / "404.html").write_text(error_page, encoding="utf8")

    def request(self, path, *, method="GET", projection=None):
        server = build_server(projection, host="127.0.0.1", port=0, static_dir=self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_unknown_page_returns_the_bundled_error_document(self):
        # Before: status 404, body b"", no content-type -> browser network error.
        status, body, headers = self.request("/percorso-inesistente-dp544/")
        self.assertEqual(status, 404)
        self.assertEqual(headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertIn(b"Questa pagina non esiste.", body)
        self.assertIn(b'href="/esplora/"', body)
        self.assertEqual(int(headers["Content-Length"]), len(body))

    def test_error_document_never_echoes_the_requested_path(self):
        status, body, _ = self.request("/finding:segreto-ritirato/")
        self.assertEqual(status, 404)
        self.assertNotIn(b"segreto-ritirato", body)
        self.assertNotIn(b"finding:", body)

    def test_head_keeps_the_length_without_a_body(self):
        get_status, get_body, get_headers = self.request("/assente/")
        status, body, headers = self.request("/assente/", method="HEAD")
        self.assertEqual((get_status, status), (404, 404))
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], get_headers["Content-Length"])
        self.assertEqual(int(headers["Content-Length"]), len(get_body))

    def test_unknown_api_path_stays_a_typed_json_404(self):
        projection = Path(__file__).resolve().parents[1] / "web/src/data/demo-projection.json"
        status, body, headers = self.request(
            "/api/v1/records/nonexistent-dp544", projection=projection
        )
        self.assertEqual(status, 404)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertNotIn(b"Questa pagina non esiste.", body)

    def test_release_without_an_error_document_keeps_the_empty_body(self):
        # A rollback to an older immutable release has no 404.html: the server
        # must still answer 404 instead of failing the request.
        self.write_site(error_page=None)
        (self.root / "404.html").unlink(missing_ok=True)
        status, body, headers = self.request("/assente/")
        self.assertEqual(status, 404)
        self.assertEqual(body, b"")
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_private_and_hidden_files_stay_empty(self):
        # The refusal keeps the historical empty body: a probe learns nothing.
        (self.root / ".env").write_text("TOKEN=synthetic", encoding="utf8")
        (self.root / "accounts.sqlite3").write_text("SQLite format 3\x00", encoding="utf8")
        for path in ("/.env", "/accounts.sqlite3"):
            with self.subTest(path=path):
                status, body, _ = self.request(path)
                self.assertEqual(status, 404)
                self.assertEqual(body, b"")


if __name__ == "__main__":
    unittest.main()
