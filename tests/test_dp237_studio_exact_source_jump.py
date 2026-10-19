"""DP-237 Studio read-only consumer must fail closed on provenance drift."""

import hashlib
import http.client
import json
import threading
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord
from dichiarazioni_pubbliche.document_text_extraction import DOCUMENT_TEXT_VERSION
from dichiarazioni_pubbliche.source_watcher import FetchedBytes
from dichiarazioni_pubbliche.studio_exact_source_jump import read_studio_exact_source_jump
from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders, StudioLoopbackServer, _dispatch,
)
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page

TEXT = b"Primo. No, non aumenta. Ultimo."
URL = "https://ntrs.nasa.gov/api/citations/19640005616/downloads/19640005616.txt"
SHA = hashlib.sha256(TEXT).hexdigest()
QUOTE = "No, non aumenta."


class Snapshot:
    def __init__(self, record):
        self.record = record
        self.calls = []

    def run(self, sql, **params):
        self.calls.append((sql, params))
        if not self.record:
            return ""
        return json.dumps(self.record)


class ExactSourceJumpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CaptureBodyStore(Path(self.tmp.name))
        saved = self.store.write(capture_id="capture:one", body=TEXT, content_sha256=SHA)
        self.capture = ContentCaptureRecord(
            id="capture:one", content_id="content:one",
            observed_at="2026-10-19T00:00:00Z", final_url=URL,
            media_type="text/plain", content_sha256=SHA, body_ref=saved.body_ref,
            retrieval_method="SAFE_HTTP", retrieval_version="v1",
            parser_method="NATIVE_DOCUMENT_TEXT", parser_version=DOCUMENT_TEXT_VERSION,
            rights_status="CLEARED", metadata={"page_count": 1},
        )
        self.passage = PassageRecord(
            id="passage:one", content_id="content:one", capture_id="capture:one",
            selector_type="TEXT_POSITION", start_char=0, end_char=len(TEXT),
            text_sha256=SHA, private_text=TEXT.decode(),
            extraction_method="NATIVE_DOCUMENT_TEXT", extraction_version=DOCUMENT_TEXT_VERSION,
        )
        self.record = {
            "source_id": "source:one", "content_rights": "CLEARED",
            "collection_status": "ACTIVE", "rights_leaf_count": 1,
            "rights_ready": True,
            "capture": asdict(self.capture), "passage": asdict(self.passage),
            "families": [{"id": "family:one", "root_content_id": "content:one",
                          "status": "APPROVED"}], "edges": [],
        }
        self.reader = Snapshot(self.record)
        self.body = {
            "collection_id": "collection:one", "content_id": "content:one",
            "capture_id": "capture:one", "passage_id": "passage:one",
            "quote_text": QUOTE,
        }

    def live(self, body=TEXT, url=URL):
        return lambda *_args, **_kwargs: FetchedBytes(
            body, url, 200, "text/plain", "utf-8", len(body),
        )

    def check(self, **options):
        return read_studio_exact_source_jump(
            self.reader, self.store, **self.body,
            fetch=options.get("fetch", self.live()),
        )

    def test_real_parser_and_copyable_studio_text_locator(self):
        result = self.check()
        self.assertEqual(result["status"], "BEST_EFFORT_TEXT")
        self.assertEqual(result["reason"], "BROWSER_TEXT_FRAGMENT_UNCONFIRMED")
        self.assertEqual(
            result["url"], URL + "#:~:text=No%2C%20non%20aumenta.",
        )
        self.assertTrue(result["private_only"])
        self.assertFalse(result["publication_authority"])
        self.assertIn("REPEATABLE READ READ ONLY", self.reader.calls[0][0])
        self.assertEqual(self.reader.calls[0][1]["capture_id"], "capture:one")
        self.assertNotIn(QUOTE, json.dumps(result))

    def test_url_hash_authority_and_body_fail_closed(self):
        cases = (
            ("different_url", self.live(url="https://other.example/source")),
            ("stale_bytes", self.live(body=b"Primo. No, ora aumenta. Ultimo.")),
        )
        for name, live in cases:
            with self.subTest(name=name):
                result = self.check(fetch=live)
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertIsNone(result["url"])
        for key, value in (
            ("families", []),
            ("content_rights", "UNKNOWN"),
            ("collection_status", "PAUSED"),
            ("rights_leaf_count", 0),
            ("rights_ready", False),
            ("source_id", ""),
            ("edges", [{"id":"edge:a", "family_id":"family:one",
                        "derived_content_id":"content:one",
                        "origin_content_id":"content:else",
                        "relation_type":"REPUBLICATION", "status":"APPROVED"}]),
        ):
            with self.subTest(key=key):
                original = self.reader.record[key]
                self.reader.record[key] = value
                result = self.check()
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertIsNone(result["url"])
                self.reader.record[key] = original
        self.reader.record["capture"] = asdict(
            replace(self.capture, hold_status="RIGHTS_HOLD"),
        )
        self.assertEqual(self.check()["reason"], "CAPTURE_RIGHTS_OR_BODY_BLOCKED")

    def test_quote_mismatch_and_multi_occurrence_unavailable(self):
        self.body["quote_text"] = "Primo. Il testo inventato"
        self.assertEqual(self.check()["reason"], "QUOTE_NOT_UNIQUE_IN_PASSAGE")
        self.body["quote_text"] = QUOTE
        self.reader.record["passage"] = asdict(
            replace(self.passage, private_text=QUOTE + " " + QUOTE),
        )
        self.assertEqual(self.check()["reason"], "QUOTE_NOT_UNIQUE_IN_PASSAGE")

    def test_revoked_while_live_request_in_flight_blocks_navigation(self):
        def revoke(*_args, **_kwargs):
            self.reader.record["capture"] = asdict(
                replace(self.capture, hold_status="RIGHTS_HOLD"),
            )
            return self.live()()

        result = self.check(fetch=revoke)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "SOURCE_STATE_CHANGED_DURING_FETCH")
        self.assertIsNone(result["url"])

    def test_http_dispatch_contract_and_form_present(self):
        readers = StudioLocalReaders(
            corpus=None, captures=self.reader, candidates=None,
            body_store=None,
        )
        # The local API delegates the stored snapshot, and a missing body
        # cannot accidentally turn into a browser-openable URL.
        unavailable = _dispatch(readers, "/v1/source/exact-jump", self.body)
        self.assertEqual(unavailable["status"], "UNAVAILABLE")
        self.assertIsNone(unavailable["url"])
        with self.assertRaises(ValueError):
            _dispatch(readers, "/v1/source/exact-jump", {**self.body, "extra": "x"})
        page = render_studio_login_page("f" * 32).decode()
        self.assertIn('id="source-exact-form"', page)
        self.assertIn("/v1/source/exact-jump", page)
        self.assertIn('id="source-exact-open"', page)
        self.assertNotIn("__EXACT_SOURCE_JUMP_BROWSER_HELPERS__", page)

    def test_loopback_http_requires_auth_and_refuses_missing_body_store(self):
        readers = StudioLocalReaders(
            corpus=None, captures=self.reader, candidates=None, body_store=None,
        )
        with StudioLoopbackServer(0, readers, "a" * 64) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            self.addCleanup(conn.close)
            request = json.dumps(self.body)
            headers = {"Content-Type": "application/json"}
            conn.request("POST", "/v1/source/exact-jump", request, headers)
            self.assertEqual(conn.getresponse().status, 401)
            headers["Authorization"] = "Bearer " + "a" * 64
            conn.request("POST", "/v1/source/exact-jump", request, headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            receipt = json.loads(response.read())
            self.assertEqual(receipt["data"]["reason"],
                             "PRIVATE_CAPTURE_BODY_STORE_NOT_CONFIGURED")
            self.assertIsNone(receipt["data"]["url"])
            server.shutdown()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
