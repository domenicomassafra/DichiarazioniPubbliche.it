import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_local_api import (  # noqa: E402
    STUDIO_LOCAL_MAX_BODY_BYTES,
    StudioLocalReaders,
    StudioLoopbackServer,
    load_private_token,
    _StudioCorpusReader,
    _StudioReadOnlyDb,
    _StudioCandidateReader,
    _StudioCaptureReader,
    _StudioQueueReader,
)
from tests.test_studio_capture_inspector import A, B, FakeCaptureStore  # noqa: E402
from tests.test_studio_candidate_review import Store as FakeMatchStore, RUN_ID as MATCH_RUN_ID  # noqa: E402
from tests.test_studio_operator_search import FakeStore as FakeSearchStore  # noqa: E402
from tests.test_studio_operator_queues import FakeOperatorQueues  # noqa: E402
from tests.test_studio_discovery_inspect import fixture as discovery_inspect_fixture  # noqa: E402
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page  # noqa: E402

TOKEN = "a" * 64


class StudioLocalApiTests(unittest.TestCase):
    def setUp(self):
        self.search = FakeSearchStore()
        self.captures = FakeCaptureStore()
        self.matches = FakeMatchStore()
        self.queues = FakeOperatorQueues()
        self.server = StudioLoopbackServer(
            0, StudioLocalReaders(self.search, self.captures, self.matches, self.queues), TOKEN
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, method, route, value=None, headers=None):
        body = None if value is None else (
            value if isinstance(value, bytes) else json.dumps(value).encode()
        )
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        props = {} if headers is None else dict(headers)
        if body is not None and "Content-Type" not in props:
            props["Content-Type"] = "application/json"
        conn.request(method, route, body=body, headers=props)
        response = conn.getresponse()
        raw = response.read()
        metadata = dict(response.getheaders())
        conn.close()
        return response.status, json.loads(raw) if raw else {}, metadata

    def auth(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def test_successful_metadata_queries_never_serve_private_text(self):
        cases = (
            ("/v1/corpus/search", {"query": "Garlasco", "limit": 2}),
            ("/v1/capture/compare", {"content_id": "content:one", "earlier_hash": A, "later_hash": B}),
            ("/v1/candidate/matches", {"run_id": MATCH_RUN_ID, "claim_candidate_id": "candidate:1"}),
        )
        for route, payload in cases:
            with self.subTest(route=route):
                status, body, headers = self.call("POST", route, payload, self.auth())
                self.assertEqual(status, 200, body)
                self.assertTrue(body["data"]["private_only"])
                self.assertFalse(body["data"]["publication_authority"])
                self.assertEqual(headers["Cache-Control"], "no-store, private")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                for forbidden in (
                    "Sensitive private headline", "Unpublished private transcript",
                    "PRIVATE", "SECRET", "api_key", "private_archive_url",
                ):
                    self.assertNotIn(forbidden, json.dumps(body))
        self.assertEqual(len(self.search.requests), 1)

    def test_default_denies_unauthenticated_wrong_and_duplicate_tokens(self):
        for headers in (
            {}, {"Authorization": "Bearer invalid"},
            {"Authorization": "Basic dGVzdA=="},
            {"Authorization": "Bearer " + TOKEN[:-1]},
        ):
            with self.subTest(headers=headers):
                status, _, _ = self.call("POST", "/v1/corpus/search", {"query": "do not fetch"}, headers)
                self.assertEqual(status, 401)
        self.assertEqual(self.search.requests, [])
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.putrequest("POST", "/v1/corpus/search")
        conn.putheader("Authorization", f"Bearer {TOKEN}")
        conn.putheader("Authorization", f"Bearer {TOKEN}")
        conn.putheader("Content-Type", "application/json")
        payload = b'{"query":"private"}'
        conn.putheader("Content-Length", str(len(payload)))
        conn.endheaders(payload)
        response = conn.getresponse()
        self.assertEqual(response.status, 401)
        response.read()
        conn.close()
        self.assertEqual(self.search.requests, [])

    def test_dns_rebinding_cross_origin_cookie_and_nonloopback_host_refused(self):
        for headers in (
            {"Host": "evil.example"},
            {"Host": f"localhost:{self.server.server_port}"},
            {"Origin": "https://evil.example"},
            {"Origin": "null"},
            {"Cookie": "session=cross-site"},
            {"Transfer-Encoding": "chunked"},
        ):
            with self.subTest(headers=headers):
                status, _, _ = self.call("POST", "/v1/corpus/search", {"query": "not queried"}, self.auth() | headers)
                self.assertEqual(status, 403)
        self.assertEqual(self.search.requests, [])

    def test_non_readonly_paths_verbs_and_body_limits_denied(self):
        for method in ("GET", "HEAD", "DELETE", "PUT", "PATCH", "OPTIONS"):
            with self.subTest(method=method):
                status, _, _ = self.call(method, "/v1/corpus/search", None, self.auth())
                self.assertEqual(status, 405)
        for route in (
            "/v1/review/approve", "/admin/publish", "/v1/candidate/matches?private=1",
            "/v1/corpus/search/", "/health", "/",
        ):
            with self.subTest(route=route):
                status, _, _ = self.call("POST", route, {"query": "x"}, self.auth())
                self.assertEqual(status, 404)
        for payload in (
            b"a" * (STUDIO_LOCAL_MAX_BODY_BYTES + 1),
            b"{malformed",
            b"[1]",
            b'{"query":"ok","publish":true}',
        ):
            status, _, _ = self.call("POST", "/v1/corpus/search", payload, self.auth())
            self.assertIn(status, {413, 422})
        self.assertEqual(self.search.requests, [])

    def test_backend_failure_is_bounded_and_does_not_leak_error_or_query(self):
        self.search.error = RuntimeError("postgres secret password=xyz private customer")
        status, body, _ = self.call("POST", "/v1/corpus/search", {"query": "sensitive query"}, self.auth())
        self.assertEqual(status, 503)
        self.assertEqual(body, {"error": "STUDIO_LOCAL_BACKEND_UNAVAILABLE"})
        self.assertNotIn("sensitive query", json.dumps(body))
        self.assertNotIn("password", json.dumps(body))

    def test_collections_and_discovery_never_expose_private_titles_urls(self):
        cases = [
            ("/v1/collections/list", {
                "id": "collection:one", "status": "ACTIVE", "included_content_count": 3,
                "name": "PRIVATE COLLECTION",
            }),
            ("/v1/discovery/list", {
                "id": "discovery:1", "run_id": "run:1", "content_id": None,
                "disposition": "NEW_CONTENT", "reason_code": None,
                "title": "PRIVATE HIT", "canonical_url": "https://private.example",
            }),
        ]
        for path, persisted in cases:
            with self.subTest(path=path):
                self.queues.rows = [persisted]
                status, reply, _ = self.call("POST", path, {"limit": 20}, self.auth())
                self.assertEqual(status, 200, reply)
                self.assertEqual(len(reply["data"]["results"]), 1)
                self.assertFalse(reply["data"]["publication_authority"])
                self.assertNotIn("PRIVATE", json.dumps(reply))
                self.assertNotIn("canonical_url", json.dumps(reply))

    def test_discovery_inspect_real_loopback_auth_and_no_private_body(self):
        route = "/v1/discovery/inspect"
        request = {"collection_id": "research:1", "hit_id": "hit:1"}
        self.queues.rows = [discovery_inspect_fixture()]
        denied, _, _ = self.call("POST", route, request)
        self.assertEqual(denied, 401)
        status, reply, headers = self.call("POST", route, request, self.auth())
        self.assertEqual(status, 200, reply)
        self.assertEqual(reply["data"]["provenance_path"]["query_id"], "query:1")
        self.assertFalse(reply["data"]["publication_authority"])
        self.assertFalse(reply["data"]["triage_action_authorized"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertNotIn("canonical_url", json.dumps(reply))
        self.assertNotIn("DO NOT LEAK", json.dumps(reply))
        invalid, _, _ = self.call(
            "POST", route, request | {"approve": True}, self.auth(),
        )
        self.assertEqual(invalid, 422)

    def test_discovery_triage_history_loopback_is_scoped_read_only(self):
        route = "/v1/discovery/triage-history"
        request = {"collection_id": "research:1", "hit_id": "hit:1",
                   "limit": 10, "after_revision": 0}
        self.queues.rows = [{
            "collection_id": "research:1", "hit_id": "hit:1",
            "lineage_ok": True, "head_revision": 1, "ledger_count": 1,
            "decisions": [{"revision": 1, "expected_revision": 0,
                           "decision": "NEEDS_REVIEW",
                           "url": "https://private.example/secret",
                           "actor_ref": "PRIVATE REVIEWER"}],
            "metadata": {"source_body": "SECRET"},
        }]
        denied, _, _ = self.call("POST", route, request)
        self.assertEqual(denied, 401)
        status, reply, headers = self.call("POST", route, request, self.auth())
        self.assertEqual(status, 200, reply)
        self.assertEqual(reply["data"]["head_revision"], 1)
        self.assertNotIn("ledger_count", reply["data"])
        self.assertEqual(reply["data"]["results"], [
            {"revision": 1, "decision": "NEEDS_REVIEW"},
        ])
        self.assertFalse(reply["data"]["publication_authority"])
        self.assertFalse(reply["data"]["reviewer_identity_attested"])
        self.assertFalse(reply["data"]["triage_action_authorized"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertNotIn("PRIVATE REVIEWER", json.dumps(reply))
        self.assertNotIn("SECRET", json.dumps(reply))
        for payload in (
            request | {"publish": True},
            request | {"approve": True},
            request | {"after_revision": -1},
            request | {"after_revision": True},
        ):
            rejected, _, _ = self.call("POST", route, payload, self.auth())
            self.assertEqual(rejected, 422)
        refused, _, _ = self.call(
            "POST", "/v1/discovery/triage", request, self.auth(),
        )
        self.assertEqual(refused, 404)

    def test_member_listing_and_exact_detail_require_token_and_included_binding(self):
        cases = [
            ("/v1/collections/members", {"collection_id": "research:garlasco", "limit": 10},
             {"collection_id": "research:garlasco", "state": "PAUSED", "members": [{
                 "content_id": "content:garlasco:001", "source_id": "source:one",
                 "rights_status": "UNKNOWN", "processing_status": "REVIEW_REQUIRED",
                 "title": "PRIVATE SOURCE"
             }]}),
            ("/v1/collections/member",
             {"collection_id": "research:garlasco", "content_id": "content:garlasco:001"},
             {"collection_id": "research:garlasco", "collection_state": "PAUSED",
              "content_id": "content:garlasco:001", "source_id": "source:one",
              "source_exists": True, "rights_status": "UNKNOWN",
              "processing_status": "REVIEW_REQUIRED",
              "capture_count": 0, "passage_count": 0, "statement_candidate_count": 0,
              "claim_candidate_count": 0, "atomic_claim_count": 1,
              "claims": [{"id": "claim:garlasco:001", "speaker_person_id": "person:one",
                          "claim_type": "HISTORICAL_CLAIM", "normalized_claim": "PRIVATE TEXT"}]})
        ]
        for path, request, database_row in cases:
            with self.subTest(path=path):
                self.queues.rows = [database_row]
                denied, _, _ = self.call("POST", path, request)
                self.assertEqual(denied, 401)
                status, reply, headers = self.call("POST", path, request, self.auth())
                self.assertEqual(status, 200, reply)
                self.assertTrue(reply["data"]["private_only"])
                self.assertFalse(reply["data"]["publication_authority"])
                self.assertEqual(headers["Cache-Control"], "no-store, private")
                self.assertNotIn("PRIVATE", json.dumps(reply))
                self.assertNotIn("normalized_claim", json.dumps(reply))
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                malformed = request | {"publication_approve": True}
                status, _, _ = self.call("POST", path, malformed, self.auth())
                self.assertEqual(status, 422)

    def test_claim_provenance_is_exactly_scoped_metadata_only_and_authenticated(self):
        path = "/v1/collections/claim-provenance"
        request = {
            "collection_id": "research:garlasco",
            "content_id": "content:garlasco:one",
            "claim_id": "claim:garlasco:one",
        }
        self.queues.rows = [
            {
                "collection_id": "research:garlasco", "collection_state": "PAUSED",
                "content_id": "content:garlasco:one", "claim_id": "claim:garlasco:one",
                "speaker_person_id": "person:one", "rights_status": "UNKNOWN",
                "processing_status": "REVIEW_REQUIRED", "capture_count": 0,
                "passage_count": 0, "provenance_count": 1,
                "provenance": [{
                    "id": "prov:1", "claim_id": "claim:garlasco:one",
                    "content_id": "content:garlasco:one", "person_id": "person:one",
                    "status": "APPROVED", "selector_type": "TEXT_QUOTE_HASH",
                    "quote_sha256": "a" * 64, "source_sha256": None,
                    "start_char": None, "end_char": None,
                    "attribution_method": "SOURCE_QUOTE",
                    "source_ref": {"private_url": "SECRET"},
                }],
            }
        ]
        denied, _, _ = self.call("POST", path, request)
        self.assertEqual(denied, 401)
        status, response, headers = self.call("POST", path, request, self.auth())
        self.assertEqual(status, 200, response)
        self.assertTrue(response["data"]["private_only"])
        self.assertEqual(response["data"]["records"][0]["status"], "APPROVED")
        self.assertFalse(response["data"]["rights_clearance"])
        self.assertFalse(response["data"]["publication_authority"])
        self.assertNotIn("SECRET", json.dumps(response))
        self.assertNotIn("source_ref", json.dumps(response))
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        invalid, _, _ = self.call("POST", path, request | {"approve": True}, self.auth())
        self.assertEqual(invalid, 422)
        origin, _, _ = self.call(
            "POST", path, request, self.auth() | {"Origin": "https://attacker.invalid"},
        )
        self.assertEqual(origin, 403)

    def test_login_page_is_static_local_only_and_csp_nonce_scoped(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        conn.request("GET", "/")
        response = conn.getresponse()
        page = response.read().decode("utf-8")
        headers = dict(response.getheaders())
        conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn("<h1>Esplora i riferimenti privati</h1>", page)
        self.assertIn("data-panel=\"corpus\"", page)
        self.assertIn("data-panel=\"inbox\"", page)
        self.assertIn("data-panel=\"matches\"", page)
        self.assertIn("data-panel=\"captures\"", page)
        self.assertIn("data-panel=\"collections\"", page)
        self.assertIn('data-endpoint="/v1/collections/members"', page)
        self.assertIn('data-endpoint="/v1/collections/member"', page)
        self.assertIn('data-endpoint="/v1/collections/claim-provenance"', page)
        self.assertIn('id="claim-links"', page)
        self.assertIn("provenanceForm.requestSubmit()", page)
        self.assertIn('id="member-links"', page)
        self.assertIn("memberDetailForm.requestSubmit()", page)
        self.assertIn("memberLinks.replaceChildren()", page)
        self.assertIn("document.createElement('button')", page)
        self.assertIn("credentials: 'omit'", page)
        self.assertIn("results.textContent", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn(TOKEN, page)
        self.assertNotIn("PRIVATE HIT", page)
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        nonce = re.search(r'<script nonce="([a-f0-9]{32})">', page)
        self.assertIsNotNone(nonce)
        self.assertIn(f"script-src 'nonce-{nonce.group(1)}'", headers["Content-Security-Policy"])
        self.assertIn(f'<style nonce="{nonce.group(1)}">', page)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cache-Control"], "no-store, private")

        status, _, _ = self.call("GET", "/", None, {"Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.call("GET", "/", None, {"Origin": "https://malicious.example"})
        self.assertEqual(status, 403)

    def test_html_shell_only_renders_valid_nonce(self):
        with self.assertRaisesRegex(ValueError, "NONCE_INVALID"):
            render_studio_login_page("attacker<script>window.token</script>")


class StudioLocalTokenTests(unittest.TestCase):
    def test_protected_token_file_and_symlink_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secret"
            path.write_text(TOKEN + "\n")
            os.chmod(path, 0o600)
            self.assertEqual(load_private_token(path), TOKEN)
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(ValueError, "UNSAFE"):
                load_private_token(path)
            os.chmod(path, 0o600)
            symlink = Path(tmp) / "link"
            symlink.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "SYMLINK"):
                load_private_token(symlink)
            path.write_text("x" * 64)
            with self.assertRaisesRegex(ValueError, "INVALID"):
                load_private_token(path)

    def test_no_empty_token_weak_port_or_remote_bind_override(self):
        with self.assertRaisesRegex(ValueError, "TOKEN_INVALID"):
            StudioLoopbackServer(0, StudioLocalReaders(None, None, None), "weak")
        for port in (-1, 65536, True):
            with self.subTest(port=port), self.assertRaises((ValueError, OverflowError)):
                StudioLoopbackServer(port, StudioLocalReaders(None, None, None), TOKEN)

class StudioLocalDatabaseTests(unittest.TestCase):
    def test_db_connection_enforces_session_read_only_timeout_and_safe_errors(self):
        recorder = []

        def subprocess_run(args, **kwargs):
            recorder.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout="readonly-result\n", stderr="")

        with patch("dichiarazioni_pubbliche.studio_local_api.subprocess.run", side_effect=subprocess_run):
            result = _StudioReadOnlyDb().run("SELECT :'param'::text;", param="test")
        self.assertEqual(result, "readonly-result")
        args, options = recorder[0]
        self.assertEqual(args[:4], ["psql", "-X", "-qAt", "-v"])
        self.assertIn("param=test", args)
        self.assertEqual(options["timeout"], 8)
        self.assertIn("default_transaction_read_only=on", options["env"]["PGOPTIONS"])
        self.assertIn("statement_timeout=3000", options["env"]["PGOPTIONS"])
        self.assertIn("lock_timeout=1000", options["env"]["PGOPTIONS"])
        self.assertEqual(options["env"]["PGCONNECT_TIMEOUT"], "3")
        self.assertNotIn("password", str(args))

        for reader in (_StudioCorpusReader, _StudioCandidateReader, _StudioCaptureReader, _StudioQueueReader):
            self.assertEqual(reader.run, _StudioReadOnlyDb.run)

        with patch("dichiarazioni_pubbliche.studio_local_api.subprocess.run", return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="FATAL: password=PRIVATE"
        )):
            with self.assertRaisesRegex(RuntimeError, "^STUDIO_LOCAL_DB_QUERY_REFUSED$") as ctx:
                _StudioReadOnlyDb().run("SELECT 1;")
            self.assertIsNone(ctx.exception.__cause__)
            self.assertNotIn("PRIVATE", str(ctx.exception))

        with patch("dichiarazioni_pubbliche.studio_local_api.subprocess.run", side_effect=OSError("secret")):
            with self.assertRaisesRegex(RuntimeError, "^STUDIO_LOCAL_DB_TIMEOUT_OR_UNAVAILABLE$"):
                _StudioReadOnlyDb().run("SELECT 1;")


if __name__ == "__main__":
    unittest.main()
