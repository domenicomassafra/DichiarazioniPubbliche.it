import json
import sys
import tempfile
import unittest
from dataclasses import replace
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore,
    CaptureEnrichmentPolicy,
    capture_enrichment_policy_from_source,
    capture_content,
)
from dichiarazioni_pubbliche.source_oembed_lookup import (  # noqa: E402
    OEMBED_MAX_RESPONSE_BYTES,
    OEMBED_TIMEOUT_SECONDS,
    fetch_oembed_json,
    lookup_vimeo_oembed,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes  # noqa: E402
from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher, fetched  # noqa: E402


def vimeo_reply(*, title="Documentary", author="Creator", **extra):
    response = {
        "version": "1.0", "type": "video", "provider_name": "Vimeo",
        "title": title, "author_name": author,
        "html": "<iframe src='https://untrusted.invalid/embed'>PRIVATE HTML</iframe>",
        **extra,
    }
    return json.dumps(response).encode()


def oembed_fetched(url, body, *, media_type="application/json", status=200, final_url=None):
    return FetchedBytes(
        body=body, final_url=final_url or url, status_code=status,
        media_type=media_type, charset="utf-8", content_length=len(body),
    )


class OEmbedLookupTests(unittest.TestCase):
    def test_exact_provider_endpoint_and_budgets_are_pinned(self):
        calls = []

        def fetcher(url, *, timeout, max_response_bytes):
            calls.append((url, timeout, max_response_bytes))
            return oembed_fetched(url, vimeo_reply())

        result = lookup_vimeo_oembed("https://vimeo.com/12345678", fetcher=fetcher)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.title_candidate, "Documentary")
        self.assertEqual(result.author_candidate, "Creator")
        self.assertEqual(result.provider_candidate, "Vimeo")
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.identity_mutation_allowed)
        self.assertEqual(
            calls,
            [(
                "https://vimeo.com/api/oembed.json?url=https%3A%2F%2Fvimeo.com%2F12345678",
                OEMBED_TIMEOUT_SECONDS, OEMBED_MAX_RESPONSE_BYTES,
            )],
        )
        self.assertNotIn("iframe", json.dumps(result.to_dict()))
        self.assertNotIn("PRIVATE HTML", json.dumps(result.to_dict()))

    def test_foreign_private_non_video_and_query_urls_do_not_fetch(self):
        calls = []

        def bad_fetcher(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("must not call")

        for url in (
            "https://evil.example/oembed",
            "https://vimeo.com.evil.example/123",
            "http://vimeo.com/123",
            "https://user:pass@vimeo.com/123",
            "https://vimeo.com:444/123",
            "https://vimeo.com/api/oembed.json?url=https://other.example",
            "https://vimeo.com/123?h=private",
            "https://vimeo.com/123#fragment",
            "https://vimeo.com/abc",
            "https://127.0.0.1/123",
        ):
            self.assertEqual(
                lookup_vimeo_oembed(url, fetcher=bad_fetcher).status,
                "NOT_APPLICABLE", url,
            )
        self.assertEqual(calls, [])

    def test_malformed_redirect_oversize_http_error_and_provider_conflict_fail_closed(self):
        good = vimeo_reply()
        bad_cases = (
            {"final_url": "https://redirect.invalid/"},
            {"media_type": "text/html"},
            {"status": 404},
            {"body": b"x" * (OEMBED_MAX_RESPONSE_BYTES + 1)},
            {"body": b"{unparseable"},
            {"body": vimeo_reply(provider_name="Other")},
            {"body": vimeo_reply(version="2.0")},
            {"body": vimeo_reply(title="", author="")},
        )
        for case in bad_cases:
            with self.subTest(case=case):
                def fetcher(url, *, timeout, max_response_bytes):
                    return oembed_fetched(
                        url, case.get("body", good),
                        media_type=case.get("media_type", "application/json"),
                        status=case.get("status", 200),
                        final_url=case.get("final_url"),
                    )
                result = lookup_vimeo_oembed("https://vimeo.com/123", fetcher=fetcher)
                self.assertEqual(result.status, "FAILED")
                self.assertIsNone(result.title_candidate)
                self.assertIsNone(result.response_sha256)

    def test_custom_fetcher_must_not_fabricate_complete_http_200_from_bad_metadata(self):
        body = vimeo_reply()
        endpoint_reply = oembed_fetched("https://vimeo.com/api/oembed.json", body)
        for override in (
            {"content_length": len(body) + 1},
            {"content_length": len(body) - 1},
            {"content_length": 0},
            {"content_length": -1},
            {"content_length": True},
            {"content_length": float(len(body))},
            {"content_length": str(len(body))},
            {"status_code": 200.0},
            {"status_code": 200 + 0j},
            {"status_code": True},
        ):
            def untrusted_fetcher(url, *, timeout, max_response_bytes):
                return replace(endpoint_reply, final_url=url, **override)

            with self.subTest(override=override):
                result = lookup_vimeo_oembed("https://vimeo.com/123", fetcher=untrusted_fetcher)
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.reason_code, "OEMBED_RESPONSE_INVALID")
                self.assertIsNone(result.response_sha256)
                self.assertIsNone(result.title_candidate)
        def allowed_fetcher(url, *, timeout, max_response_bytes):
            return replace(endpoint_reply, final_url=url,
                           media_type="application/json; charset=utf-8")
        self.assertEqual(
            lookup_vimeo_oembed("https://vimeo.com/123", fetcher=allowed_fetcher).status,
            "SUCCEEDED",
        )

    def test_duplicate_json_keys_cannot_override_conflicting_provider_or_private_fields(self):
        for payload in (
            b'{"version":"2.0","version":"1.0","type":"video","provider_name":"Vimeo","title":"T"}',
            b'{"version":"1.0","type":"video","provider_name":"Other","provider_name":"Vimeo","title":"T"}',
            b'{"version":"1.0","type":"video","provider_name":"Vimeo","title":"private key", "title":"T"}',
        ):
            def untrusted_fetcher(url, *, timeout, max_response_bytes):
                return oembed_fetched(url, payload)

            with self.subTest(payload=payload):
                result = lookup_vimeo_oembed("https://vimeo.com/123", fetcher=untrusted_fetcher)
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.reason_code, "OEMBED_SCHEMA_INVALID")
                self.assertIsNone(result.response_sha256)
                self.assertNotIn("private key", json.dumps(result.to_dict()))

    def test_unexpected_custom_fetcher_error_never_discloses_private_exception(self):
        def untrusted_fetcher(url, *, timeout, max_response_bytes):
            raise RuntimeError("private provider url https://example.invalid/?api_key=DO_NOT_ECHO")

        result = lookup_vimeo_oembed("https://vimeo.com/123", fetcher=untrusted_fetcher)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.reason_code, "OEMBED_FETCH_OR_PARSE_FAILED")
        self.assertNotIn("DO_NOT_ECHO", str(result.to_dict()))

    def test_pinned_network_fetch_refuses_declared_length_mismatch_or_bad_budget_no_network(self):
        body = vimeo_reply()
        endpoint = "https://vimeo.com/api/oembed.json?url=https%3A%2F%2Fvimeo.com%2F123"

        class FakeReply:
            status = 200

            def __init__(self, content_length):
                self.headers = Message()
                self.headers["Content-Type"] = "application/json"
                if content_length is not None:
                    self.headers["Content-Length"] = str(content_length)
                self.read_called = False

            def geturl(self):
                return endpoint

            def read(self, size):
                self.read_called = True
                return body[:size]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        for declared in (str(len(body) - 1), str(len(body) + 1), "-1", "not-a-number",
                         str(OEMBED_MAX_RESPONSE_BYTES + 1)):
            response = FakeReply(declared)
            with self.subTest(declared=declared), patch(
                "dichiarazioni_pubbliche.source_oembed_lookup.validate_discovery_url",
                return_value=endpoint,
            ), patch(
                "dichiarazioni_pubbliche.source_oembed_lookup.urllib.request.build_opener",
                return_value=SimpleNamespace(open=lambda *args, **kwargs: response),
            ):
                with self.assertRaisesRegex(ValueError, "OEMBED_CONTENT_LENGTH_INVALID|OEMBED_RESPONSE_TOO_LARGE|OEMBED_RESPONSE_INCOMPLETE"):
                    fetch_oembed_json(endpoint, timeout=OEMBED_TIMEOUT_SECONDS,
                                     max_response_bytes=OEMBED_MAX_RESPONSE_BYTES)

        for limit in (True, 0, -1, 1.5, "8192", None, OEMBED_MAX_RESPONSE_BYTES + 1):
            with self.subTest(limit=limit), patch(
                "dichiarazioni_pubbliche.source_oembed_lookup.urllib.request.build_opener",
                side_effect=AssertionError("network must not be opened"),
            ):
                with self.assertRaisesRegex(ValueError, "OEMBED_RESPONSE_LIMIT_INVALID"):
                    fetch_oembed_json(endpoint, timeout=OEMBED_TIMEOUT_SECONDS,
                                     max_response_bytes=limit)

    def test_network_exception_never_echoes_exception_or_secret(self):
        def failing_fetcher(*args, **kwargs):
            raise OSError("token=not-for-logs")
        result = lookup_vimeo_oembed("https://vimeo.com/123", fetcher=failing_fetcher)
        self.assertEqual(result.status, "FAILED")
        self.assertNotIn("not-for-logs", str(result))

    def test_outbound_dns_policy_is_checked_before_opening_socket(self):
        with patch(
            "dichiarazioni_pubbliche.source_oembed_lookup.validate_discovery_url",
            side_effect=ValueError("DISCOVERY_URL_NONPUBLIC_IP"),
        ), patch(
            "dichiarazioni_pubbliche.source_oembed_lookup.urllib.request.build_opener",
            side_effect=AssertionError("unexpected network"),
        ):
            result = lookup_vimeo_oembed("https://vimeo.com/123")
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.reason_code, "OEMBED_FETCH_OR_PARSE_FAILED")

    def test_network_fetch_uses_no_redirect_handler_and_no_proxy(self):
        from dichiarazioni_pubbliche.source_oembed_lookup import _NoRedirect
        from dichiarazioni_pubbliche.source_watcher import _DiscoveryHTTPSHandler
        redirect = _NoRedirect()
        self.assertIsNone(
            redirect.redirect_request(None, None, 302, "Moved", {}, "https://other.example/")
        )
        build_args = []

        def opener(*handlers):
            build_args.extend(handlers)
            raise OSError("network disabled")

        with patch(
            "dichiarazioni_pubbliche.source_oembed_lookup.validate_discovery_url",
            return_value=True,
        ), patch(
            "dichiarazioni_pubbliche.source_oembed_lookup.urllib.request.build_opener",
            side_effect=opener,
        ):
            with self.assertRaises(OSError):
                fetch_oembed_json(
                    "https://vimeo.com/api/oembed.json?url=https%3A%2F%2Fvimeo.com%2F123",
                    timeout=OEMBED_TIMEOUT_SECONDS,
                    max_response_bytes=OEMBED_MAX_RESPONSE_BYTES,
                )
        self.assertTrue(any(isinstance(handler, _NoRedirect) for handler in build_args))
        # A preflight-only DNS check would still permit DNS rebinding when
        # urllib opens its socket. The actual transport must pin vetted IPs.
        self.assertTrue(
            any(isinstance(handler, _DiscoveryHTTPSHandler) for handler in build_args),
            "oEmbed acquisition must share the DNS-pinned HTTPS transport",
        )
        self.assertTrue(any(
            type(handler).__name__ == "ProxyHandler" and not handler.proxies
            for handler in build_args
        ))

    def test_source_policy_default_denies_and_requires_boolean_opt_in(self):
        self.assertFalse(capture_enrichment_policy_from_source({}).oembed_lookup_enabled)
        self.assertTrue(
            capture_enrichment_policy_from_source(
                {"content_policy": {"oembed_lookup_enabled": True}}
            ).oembed_lookup_enabled
        )
        with self.assertRaisesRegex(RuntimeError, "OEMBED_LOOKUP_ENABLED_INVALID"):
            capture_enrichment_policy_from_source(
                {"content_policy": {"oembed_lookup_enabled": "true"}}
            )

    def test_capture_private_append_only_event_without_rewriting_primary_capture(self):
        html = b"<html><body>Public source is captured; oEmbed is private context.</body></html>"
        calls = []
        def oembed_fetcher(url, *, timeout, max_response_bytes):
            calls.append(url)
            return oembed_fetched(url, vimeo_reply())

        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            args = dict(
                content_id="content:oembed",
                url="https://vimeo.com/123",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-10-08T10:00:00+00:00",
                fetcher=SequenceFetcher(
                    fetched(html, url="https://vimeo.com/123"),
                    fetched(html, url="https://vimeo.com/123"),
                ),
                oembed_fetcher=oembed_fetcher,
            )
            without_opt_in = capture_content(**args)
            self.assertEqual(without_opt_in.oembed_status, "NOT_REQUESTED")
            self.assertEqual(calls, [])
            before = next(iter(store.captures.values()))["record"]
            self.assertNotIn("title_candidate", json.dumps(before.metadata))

            opted_store = FakeCaptureStore()
            opted_args = {
                **args,
                "store": opted_store,
                "fetcher": SequenceFetcher(
                    fetched(html, url="https://vimeo.com/123"),
                    fetched(html, url="https://vimeo.com/123"),
                ),
                "enrichment_policy": CaptureEnrichmentPolicy(oembed_lookup_enabled=True),
            }
            with_opt_in = capture_content(**opted_args)
            self.assertEqual(with_opt_in.oembed_status, "SUCCEEDED")
            self.assertEqual(len(calls), 1)
            after = next(iter(opted_store.captures.values()))["record"]
            self.assertEqual(before, after)
            private_events = [
                event for event in opted_store.events.values()
                if event["event_type"] == "PRIVATE_OEMBED_LOOKUP"
            ]
            self.assertEqual(len(private_events), 1)
            receipt = private_events[0]["receipt"]
            self.assertEqual(receipt["title_candidate"], "Documentary")
            self.assertFalse(receipt["publication_authority"])
            self.assertNotIn("iframe", json.dumps(receipt))
            self.assertNotIn("PRIVATE HTML", json.dumps(receipt))
            replayed = capture_content(**opted_args)
            self.assertEqual(replayed.oembed_status, "SKIPPED_REPLAY")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len([
                event for event in opted_store.events.values()
                if event["event_type"] == "PRIVATE_OEMBED_LOOKUP"
            ]), 1)

    def test_metadata_disabled_keeps_optional_provider_off_even_when_flagged(self):
        calls = []
        def cannot_fetch(*args, **kwargs):
            calls.append(1)
            raise AssertionError("unexpected provider call")
        with tempfile.TemporaryDirectory() as tmp:
            receipt = capture_content(
                content_id="content:disabled",
                url="https://vimeo.com/123",
                store=FakeCaptureStore(),
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-10-08T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Keep capture.</p>", url="https://vimeo.com/123")),
                oembed_fetcher=cannot_fetch,
                enrichment_policy=CaptureEnrichmentPolicy(
                    metadata_enabled=False, oembed_lookup_enabled=True,
                ),
            )
            self.assertEqual(receipt.oembed_status, "NOT_REQUESTED")
            self.assertEqual(calls, [])

    def test_provider_failure_keeps_primary_capture_and_private_failure_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()

            def unavailable(*args, **kwargs):
                raise OSError("access denied: source is private")

            receipt = capture_content(
                content_id="content:provider-failed",
                url="https://vimeo.com/123",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-10-08T10:00:00+00:00",
                fetcher=SequenceFetcher(
                    fetched(b"<p>Source survives provider outage.</p>", url="https://vimeo.com/123")
                ),
                oembed_fetcher=unavailable,
                enrichment_policy=CaptureEnrichmentPolicy(oembed_lookup_enabled=True),
            )
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            self.assertEqual(receipt.oembed_status, "FAILED")
            self.assertEqual(len(store.captures), 1)
            event = next(e for e in store.events.values() if e["event_type"] == "PRIVATE_OEMBED_LOOKUP")
            self.assertEqual(event["receipt"]["reason_code"], "OEMBED_FETCH_OR_PARSE_FAILED")
            self.assertNotIn("access denied", json.dumps(event))


if __name__ == "__main__":
    unittest.main()
