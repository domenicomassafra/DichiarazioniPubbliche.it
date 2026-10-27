"""DP-437: real public HTTP seams require an independently current v3 release."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.public_api import build_server, dispatch  # noqa: E402
from test_dp437_public_opinion_api import ReviewedSyntheticOpinions  # noqa: E402


class PublicOpinionHttpV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = ReviewedSyntheticOpinions()
        self.bundle = self.source.build()
        self.candidate = self.root / "approved-candidate.json"
        self.pin = self.root / "current-release-sha256"
        self.install(self.bundle)

    def install(self, bundle):
        self.candidate.write_text(json.dumps(bundle), encoding="utf-8")
        self.pin.write_text(bundle["dataset_sha256"] + "\n", encoding="ascii")

    def read(self, path, method="GET", enabled=True):
        params = {
            "statement_projection_path": self.candidate,
            "statement_current_fingerprint_path": self.pin,
        } if enabled else {}
        return dispatch(method, path, **params)

    def test_default_closed_and_exact_routes(self):
        self.assertEqual(self.read("/api/v3/statements", enabled=False).status, 404)
        listing = self.read("/api/v3/statements")
        self.assertEqual(listing.status, 200)
        self.assertEqual(json.loads(listing.body)["meta"]["count"], 3)
        self.assertEqual(listing.headers["Cache-Control"], "no-store")
        detail = self.read("/api/v3/statements/statement:1")
        self.assertEqual(detail.status, 200)
        self.assertEqual(json.loads(detail.body)["data"]["speech_act"], "OPINION")
        self.assertIsNone(json.loads(detail.body)["data"]["finding_id"])
        self.assertEqual(self.read("/api/v3/statements/statement:private").status, 404)
        self.assertEqual(self.read("/api/v3/other").status, 404)
        self.assertEqual(self.read("/api/v3/statements/statement:1?ignore=1").status, 400)

    def test_endorsed_opinions_and_filters_do_not_infer_from_quotes(self):
        grouped = self.read("/api/v3/opinions?person_id=person:A&content_id=content:B")
        self.assertEqual(grouped.status, 200)
        self.assertEqual(json.loads(grouped.body)["meta"]["count"], 1)
        self.assertEqual(self.read("/api/v3/opinions?person_id=../hidden").status, 400)
        self.assertEqual(self.read("/api/v3/opinions?unexpected=true").status, 400)
        self.source.subjects[0].gates["context"]["endorsed"] = False
        self.install(self.source.build())
        result = self.read("/api/v3/opinions")
        self.assertEqual(json.loads(result.body)["meta"]["count"], 2)

    def test_withdrawal_rechecks_external_pin_and_fails_closed(self):
        previous = self.read("/api/v3/statements")
        self.assertEqual(previous.status, 200)
        self.pin.write_text("f" * 64 + "\n", encoding="ascii")
        self.assertEqual(self.read("/api/v3/statements").status, 503)
        self.pin.unlink()
        self.assertEqual(self.read("/api/v3/statements").status, 503)
        self.install(self.bundle)
        self.candidate.write_text("{corrupt", encoding="utf-8")
        self.assertEqual(self.read("/api/v3/statements").status, 503)
        self.install(self.bundle)
        alias = self.root / "unsafe-release-pointer"
        alias.symlink_to(self.pin)
        self.assertEqual(dispatch(
            "GET", "/api/v3/statements",
            statement_projection_path=self.candidate,
            statement_current_fingerprint_path=alias,
        ).status, 503)

    def test_v3_release_control_files_cannot_be_served_statically(self):
        with self.assertRaisesRegex(ValueError, "PUBLIC_V3_CONTROL_FILE_IN_STATIC_ROOT"):
            build_server(
                self.root / "v2.json", host="127.0.0.1", port=0,
                static_dir=self.root,
                statement_projection_path=self.candidate,
                statement_current_fingerprint_path=self.pin,
            )

    def test_head_and_read_only_semantics(self):
        get = self.read("/api/v3/statements")
        head = self.read("/api/v3/statements", method="HEAD")
        self.assertEqual(head.status, get.status)
        self.assertEqual(head.body, b"")
        self.assertEqual(head.length, len(get.body))
        self.assertEqual(self.read("/api/v3/statements", method="POST").status, 405)

    def test_same_origin_server_routes_to_authorized_public_reader(self):
        server = build_server(
            None, host="127.0.0.1", port=0,
            statement_projection_path=self.candidate,
            statement_current_fingerprint_path=self.pin,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/api/v3/statements"
            with urlopen(url, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response)["meta"]["count"], 3)
            self.pin.unlink()
            with self.assertRaises(HTTPError) as error:
                urlopen(url, timeout=3)
            self.assertEqual(error.exception.code, 503)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
