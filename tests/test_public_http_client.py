import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.public_api import API_VERSION_HEADER  # noqa: E402
from dichiarazioni_pubbliche.public_http_client import (  # noqa: E402
    PUBLIC_CLIENT_METADATA,
    PublicClientError,
    PublicHttpClient,
)
from dichiarazioni_pubbliche.openapi import OPENAPI_VERSION, fictional_dossier  # noqa: E402
from dichiarazioni_pubbliche.public_schema import PUBLIC_SCHEMA_VERSION  # noqa: E402


FINGERPRINT = "a" * 64


def envelope(data, **meta):
    return {
        "data": data,
        "meta": {
            "api_version": "v1",
            "public_schema_version": PUBLIC_SCHEMA_VERSION,
            "contract_status": "DRAFT",
            "dataset_fingerprint": FINGERPRINT,
            "projection_generated_at": "2026-10-05T20:00:00+00:00",
            **meta,
        },
    }


class Handler(BaseHTTPRequestHandler):
    calls = []
    retry_count = 0

    def log_message(self, format, *args):  # noqa: A003, ANN001
        return

    def _write(self, status, payload, *, headers=None, raw=None, api_version="v1"):
        body = raw if raw is not None else json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(API_VERSION_HEADER, api_version)
        self.send_header("ETag", '"fixture-etag"')
        self.send_header("Last-Modified", "Mon, 05 Oct 2026 20:00:00 GMT")
        self.send_header("Cache-Control", "public, max-age=300")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        type(self).calls.append(("GET", self.path))
        if self.path == "/api/v1/health":
            self._write(200, envelope({"status": "ok"}))
        elif self.path == "/api/v1/findings?limit=1":
            self._write(200, envelope([{"finding_id": "finding:1", "assessment": "UNRESOLVED"}], count=1))
        elif self.path == "/api/v1/stale":
            self._write(200, envelope([], dataset_fingerprint="b" * 64))
        elif self.path == "/api/v1/bad-version":
            self._write(200, envelope([]), api_version="v2")
        elif self.path == "/api/v1/malformed":
            self._write(200, {}, raw=b"{broken")
        elif self.path == "/api/v1/large":
            self._write(200, {}, raw=b"x" * 2048)
        elif self.path == "/api/v1/redirect":
            self.send_response(302)
            self.send_header("Location", "/api/v1/health")
            self.send_header(API_VERSION_HEADER, "v1")
            self.end_headers()
        elif self.path == "/api/v1/retry":
            type(self).retry_count += 1
            if type(self).retry_count == 1:
                self._write(503, {"error": {"code": "PUBLIC_PROJECTION_UNAVAILABLE", "message": "retry"}})
            else:
                self._write(200, envelope({"status": "ok"}))
        elif self.path == "/api/v1/findings/finding:bounded":
            self._write(
                200,
                envelope(
                    fictional_dossier(
                        finding_id="finding:bounded",
                        with_correction=True,
                        with_reply=True,
                        with_relations=True,
                    )
                ),
            )
        elif self.path == "/api/v1/findings/finding:private":
            dossier = fictional_dossier(finding_id="finding:private", with_reply=True)
            dossier["rights_of_reply"][0]["private_note"] = "must never cross the public boundary"
            self._write(200, envelope(dossier))
        elif self.path == "/api/v1/findings/finding:raw":
            dossier = fictional_dossier(finding_id="finding:raw")
            dossier["raw_transcript"] = "private transcript body"
            self._write(200, envelope(dossier))
        elif self.path == "/api/v1/findings/finding:out-of-schema":
            dossier = fictional_dossier(finding_id="finding:out-of-schema")
            dossier["unexpected_public_field"] = "not in DP-105"
            self._write(200, envelope(dossier))
        elif self.path == "/api/v1/deprecated":
            self._write(
                200,
                envelope({"status": "ok"}),
                headers={
                    "Deprecation": "Mon, 05 Oct 2026 20:00:00 GMT",
                    "Sunset": "Sun, 10 Jan 2027 20:00:00 GMT",
                },
            )
        elif self.path == "/api/v1/deprecated-incomplete":
            self._write(
                200,
                envelope({"status": "ok"}),
                headers={"Deprecation": "Mon, 05 Oct 2026 20:00:00 GMT"},
            )
        elif self.path == "/api/v1/deprecated-invalid-sunset":
            self._write(
                200,
                envelope({"status": "ok"}),
                headers={
                    "Deprecation": "Mon, 05 Oct 2026 20:00:00 GMT",
                    "Sunset": "not-an-http-date",
                },
            )
        else:
            self._write(404, {"error": {"code": "NOT_FOUND", "message": "not found"}})

    def do_HEAD(self):  # noqa: N802
        type(self).calls.append(("HEAD", self.path))
        self._write(200, envelope({"status": "ok"}))

    def do_POST(self):  # noqa: N802
        type(self).calls.append(("POST", self.path))
        self._write(405, {"error": {"code": "METHOD_NOT_ALLOWED", "message": "read-only"}})


class PublicHttpClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/api/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        Handler.calls.clear()
        Handler.retry_count = 0

    def client(self, **overrides):
        values = dict(
            expected_dataset_fingerprint=FINGERPRINT,
            allow_test_loopback=True,
            timeout_seconds=1,
            max_response_bytes=1024,
            max_retries=1,
        )
        values.update(overrides)
        return PublicHttpClient(self.base, **values)

    def test_valid_read_preserves_unresolved_semantics_and_metadata(self):
        response = self.client().request("/findings?limit=1")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.data[0]["assessment"], "UNRESOLVED")
        self.assertNotIn("verdict", response.data[0])
        self.assertNotEqual(response.data[0]["assessment"], "SUPPORTED")
        self.assertEqual(response.meta["dataset_fingerprint"], FINGERPRINT)
        self.assertEqual(response.api_version, "v1")
        self.assertEqual(response.etag, '"fixture-etag"')

    def test_bounded_correction_reply_and_relation_payloads_are_preserved_as_public_data(self):
        response = self.client(max_response_bytes=100_000).request("/findings/finding:bounded")
        dossier = response.data

        correction = dossier["corrections"][0]
        self.assertEqual(
            set(correction),
            {"id", "finding_id", "previous_finding_id", "reason", "changed_fields", "created_at"},
        )
        self.assertLessEqual(len(correction["reason"]), 2000)
        self.assertEqual(correction["previous_finding_id"], "finding:fictional:1")

        reply = dossier["rights_of_reply"][0]
        self.assertEqual(reply["status"], "PUBLISHED")
        self.assertLessEqual(len(reply["body"]), 4000)
        self.assertLessEqual(len(reply["evidence_urls"]), 32)

        relation = dossier["relations"][0]
        self.assertEqual(relation["status"], "APPROVED")
        self.assertEqual(relation["relation_type"], "SAME_PROPOSITION")
        self.assertNotIn("assessment", relation)
        self.assertNotIn("intent", relation)

    def test_private_raw_and_out_of_schema_dossier_fields_fail_closed(self):
        for path, code in (
            ("/findings/finding:private", "PRIVATE_FIELD_FORBIDDEN"),
            ("/findings/finding:raw", "PRIVATE_FIELD_FORBIDDEN"),
            ("/findings/finding:out-of-schema", "RESPONSE_SCHEMA_INVALID"),
        ):
            with self.subTest(path=path), self.assertRaises(PublicClientError) as caught:
                self.client(max_response_bytes=100_000).request(path)
            self.assertEqual(caught.exception.code, code)

    def test_deprecation_and_sunset_are_bounded_explicit_response_metadata(self):
        response = self.client().request("/deprecated")
        self.assertIsNotNone(response.deprecation)
        self.assertEqual(response.deprecation.deprecation, "Mon, 05 Oct 2026 20:00:00 GMT")
        self.assertEqual(response.deprecation.sunset, "Sun, 10 Jan 2027 20:00:00 GMT")

        for path in ("/deprecated-incomplete", "/deprecated-invalid-sunset"):
            with self.subTest(path=path), self.assertRaises(PublicClientError) as caught:
                self.client().request(path)
            self.assertEqual(caught.exception.code, "DEPRECATION_HEADERS_INVALID")

    def test_client_metadata_records_supported_contract_and_openapi_source_version(self):
        client = self.client()
        self.assertIs(client.contract_metadata, PUBLIC_CLIENT_METADATA)
        self.assertEqual(client.contract_metadata.supported_api_versions, ("v1",))
        self.assertEqual(client.contract_metadata.public_schema_version, PUBLIC_SCHEMA_VERSION)
        self.assertEqual(client.contract_metadata.source_openapi_version, OPENAPI_VERSION)

    def test_head_is_read_only_and_bodyless(self):
        response = self.client().request("/health", method="HEAD")
        self.assertEqual(response.status, 200)
        self.assertIsNone(response.data)
        self.assertEqual(Handler.calls, [("HEAD", "/api/v1/health")])

    def test_mutation_is_rejected_before_network_call(self):
        client = self.client()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method), self.assertRaisesRegex(PublicClientError, "read-only"):
                client.request("/health", method=method)
        self.assertEqual(Handler.calls, [])

    def test_stale_projection_and_incompatible_version_fail_closed(self):
        with self.assertRaisesRegex(PublicClientError, "expected projection") as stale:
            self.client().request("/stale")
        self.assertEqual(stale.exception.code, "STALE_PROJECTION")
        with self.assertRaises(PublicClientError) as version:
            self.client().request("/bad-version")
        self.assertEqual(version.exception.code, "API_VERSION_HEADER_MISMATCH")

    def test_malformed_oversized_and_redirect_fail_closed(self):
        with self.assertRaises(PublicClientError) as malformed:
            self.client().request("/malformed")
        self.assertEqual(malformed.exception.code, "MALFORMED_JSON")
        with self.assertRaises(PublicClientError) as large:
            self.client().request("/large")
        self.assertEqual(large.exception.code, "RESPONSE_TOO_LARGE")
        with self.assertRaises(PublicClientError) as redirect:
            self.client().request("/redirect")
        self.assertEqual(redirect.exception.code, "REDIRECT_FORBIDDEN")

    def test_typed_404_is_preserved_without_fabricating_empty_data(self):
        with self.assertRaises(PublicClientError) as caught:
            self.client().request("/missing")
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(caught.exception.code, "NOT_FOUND")

    def test_retry_is_bounded_to_safe_read_503(self):
        response = self.client(max_retries=1).request("/retry")
        self.assertEqual(response.status, 200)
        self.assertEqual(Handler.retry_count, 2)
        self.assertEqual(len(Handler.calls), 2)

    def test_default_client_refuses_plain_http_and_credentials(self):
        with self.assertRaises(PublicClientError) as http:
            PublicHttpClient("http://example.test/api/v1")
        self.assertEqual(http.exception.code, "BASE_URL_UNSAFE")
        with self.assertRaises(PublicClientError) as credential:
            PublicHttpClient("https://user:pass@example.test/api/v1")
        self.assertEqual(credential.exception.code, "BASE_URL_INVALID")

    def test_unknown_contract_versions_and_unbounded_limits_are_rejected(self):
        with self.assertRaises(PublicClientError) as version:
            PublicHttpClient(self.base, allow_test_loopback=True, expected_api_version="v2")
        self.assertEqual(version.exception.code, "CLIENT_API_VERSION_UNSUPPORTED")
        with self.assertRaises(PublicClientError) as timeout:
            PublicHttpClient(self.base, allow_test_loopback=True, timeout_seconds=100)
        self.assertEqual(timeout.exception.code, "TIMEOUT_INVALID")
        with self.assertRaises(PublicClientError) as size:
            PublicHttpClient(self.base, allow_test_loopback=True, max_response_bytes=100_000_000)
        self.assertEqual(size.exception.code, "RESPONSE_LIMIT_INVALID")


if __name__ == "__main__":
    unittest.main()
