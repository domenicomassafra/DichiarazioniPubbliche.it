import hashlib
import os
import stat
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    ArchiveResult,
    CaptureBodyStore,
    CaptureEnrichmentPolicy,
    CapturePipelineError,
    StdlibVisibleTextParser,
    _validate_fetched_resource,
    capture_enrichment_policy_from_source,
    capture_content,
    extract_source_metadata,
    verify_passage_roundtrip,
)
from dichiarazioni_pubbliche.source_watcher import (  # noqa: E402
    FetchedBytes, MAX_DISCOVERY_RESPONSE_BYTES,
)


def fetched(body: bytes, *, media_type="text/html", url="https://example.test/article"):
    return FetchedBytes(
        body=body,
        final_url=url,
        status_code=200,
        media_type=media_type,
        charset="utf-8",
        content_length=len(body),
        etag='"etag-test"',
        last_modified="Tue, 29 Sep 2026 10:00:00 GMT",
    )


class FakeCaptureStore:
    def __init__(self):
        self.captures = {}
        self.passages = {}
        self.events = {}
        self.archive = {}
        self.relevance_allowed = True

    def require_current_ingestion_relevance(self, *, content_ref, canonical_url):
        if not self.relevance_allowed:
            raise RuntimeError("INGESTION_RELEVANCE_MISSING")
        return {"content_ref": content_ref, "canonical_url": canonical_url}

    def issue_ingestion_acquisition_permit(
        self, *, content_ref, canonical_url, operation_kind, operation_ref
    ):
        self.require_current_ingestion_relevance(
            content_ref=content_ref,
            canonical_url=canonical_url,
        )
        return SimpleNamespace(
            permit_id=f"permit:{content_ref}",
            operation_kind=operation_kind,
            operation_ref=operation_ref,
        )

    def require_ingestion_acquisition_permit(
        self, *, permit_id, content_ref, canonical_url, operation_kind, operation_ref
    ):
        self.require_current_ingestion_relevance(
            content_ref=content_ref,
            canonical_url=canonical_url,
        )
        return SimpleNamespace(
            permit_id=permit_id,
            operation_kind=operation_kind,
            operation_ref=operation_ref,
        )

    def find_capture(self, content_id, content_sha256):
        row = self.captures.get((content_id, content_sha256))
        if row is None:
            return None
        record = row["record"]
        return {
            "id": record.id,
            "content_id": record.content_id,
            "content_sha256": record.content_sha256,
            "body_ref": record.body_ref,
            "status": record.status,
            "archive_status": self.archive.get(record.id, record.archive_status),
            "retention_class": record.retention_class,
            "hold_status": record.hold_status,
        }

    def upsert_capture(self, record):
        key = (record.content_id, record.content_sha256)
        row = self.captures.get(key)
        if row is None:
            self.captures[key] = {"record": record}
            return {
                "state": "INSERTED",
                "id": record.id,
                "body_ref": record.body_ref,
                "status": record.status,
                "archive_status": record.archive_status,
                "retention_class": record.retention_class,
                "hold_status": record.hold_status,
            }
        existing = row["record"]
        return {
            "state": "EXISTING",
            "id": existing.id,
            "body_ref": existing.body_ref,
            "status": existing.status,
            "archive_status": self.archive.get(existing.id, existing.archive_status),
            "retention_class": existing.retention_class,
            "hold_status": existing.hold_status,
        }

    def append_event(self, **kwargs):
        key = (kwargs["capture_id"], kwargs["event_type"], kwargs["operation_key"])
        current = self.events.get(key)
        value = dict(kwargs)
        if current is not None:
            if current != value:
                raise CapturePipelineError("CAPTURE_EVENT_CONFLICT")
            return "EXISTING"
        self.events[key] = value
        return "INSERTED"

    def insert_passage(self, record):
        current = self.passages.get(record.id)
        if current is None:
            self.passages[record.id] = record
            return "INSERTED"
        if current != record:
            raise CapturePipelineError("PASSAGE_INSERT_CONFLICT")
        return "EXISTING"

    def list_passages(self, capture_id):
        return [p for p in self.passages.values() if p.capture_id == capture_id]

    def request_archive(self, **kwargs):
        cid = kwargs["capture_id"]
        if self.archive.get(cid) in {None, "NOT_REQUESTED", "FAILED"}:
            self.archive[cid] = "REQUESTED"
            return "ARCHIVE_REQUESTED"
        return "CONFLICT"

    def mark_archive_pending(self, **kwargs):
        self.archive[kwargs["capture_id"]] = "PENDING"
        return "PENDING"

    def complete_archive(self, **kwargs):
        self.archive[kwargs["capture_id"]] = kwargs["outcome"]
        return kwargs["outcome"]


class SequenceFetcher:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, url, *, max_response_bytes):
        self.calls += 1
        if not self.responses:
            raise AssertionError("unexpected fetch")
        return self.responses.pop(0)


class FailingBrowser:
    renderer_id = "fake-browser"
    renderer_version = "v1"

    def __init__(self):
        self.calls = 0

    def render(self, url, *, max_response_bytes):
        self.calls += 1
        raise RuntimeError("browser down")


class SuccessfulBrowser:
    renderer_id = "fake-browser"
    renderer_version = "v1"

    def render(self, url, *, max_response_bytes):
        return fetched(
            b"<html><body><article><p>Rendered useful statement.</p></article></body></html>",
            url=url,
        )


class FailingArchive:
    provider = "fake-archive"

    def __init__(self):
        self.calls = 0

    def archive(self, *, capture, body_path):
        self.calls += 1
        raise RuntimeError("archive unavailable")


class PendingArchive:
    provider = "fake-archive"

    def archive(self, *, capture, body_path):
        return ArchiveResult("PENDING", self.provider, {"request_id": "archive-1"})


class SuccessfulArchive:
    provider = "fake-archive"

    def __init__(self, archive_url="https://archive.example.test/item/1"):
        self.archive_url = archive_url

    def archive(self, *, capture, body_path):
        return ArchiveResult(
            "SUCCEEDED",
            self.provider,
            {"archive_url": self.archive_url, "receipt_id": "archive-receipt-1"},
        )


class CapturePipelineTests(unittest.TestCase):
    def test_refuse_unsafe_initial_target_before_any_fetch_or_permit(self):
        unsafe_urls = (
            "https://127.0.0.1/secret",
            "https://[::1]/secret",
            "https://2130706433/secret",  # decimal IPv4 loopback alias
            "https://0x7f000001/secret",  # hex IPv4 loopback alias
            "https://169.254.169.254/latest/meta-data/",
            "https://localhost./secret",
            "https://service.internal/secret",
            "https://service.local./secret",
            "https://example.test:8443/path",
            "https://operator:secret@example.test/path",
            "https://[::1",  # malformed authority
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            for url in unsafe_urls:
                fetcher = SequenceFetcher(fetched(b"<p>private bytes</p>"))
                with self.subTest(url=url), self.assertRaisesRegex(
                    CapturePipelineError, "CAPTURE_URL_"
                ):
                    capture_content(
                        content_id="content:unsafe-url", url=url,
                        store=store, body_store=CaptureBodyStore(Path(tmp)),
                        fetcher=fetcher,
                    )
                self.assertEqual(fetcher.calls, 0)
                self.assertEqual(store.captures, {})
                self.assertEqual(store.passages, {})
                self.assertFalse(list(Path(tmp).rglob("*.body")))

    def test_refuse_unsafe_final_redirect_or_non_success_without_persistence(self):
        valid = fetched(b"<p>Visible public body.</p>")
        unsafe_responses = (
            replace(valid, final_url="https://localhost/private"),
            replace(valid, final_url="https://127.0.0.1/private"),
            replace(valid, final_url="https://0x7f000001/private"),
            replace(valid, final_url="https://2130706433/private"),
            replace(valid, final_url="https://service.internal/private"),
            replace(valid, final_url="https://service.local./private"),
            replace(valid, final_url="https://169.254.169.254/metadata"),
            replace(valid, final_url="https://example.test:8080/article"),
            replace(valid, final_url="https://operator:password@example.test/article"),
            replace(valid, final_url="https://[::1"),
            replace(valid, status_code=301),
            replace(valid, status_code=302),
            replace(valid, status_code=307),
            replace(valid, status_code=200.5),
            replace(valid, content_length=True),
            replace(valid, content_length=1.2),
            replace(valid, content_length="26"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            for response in unsafe_responses:
                with self.subTest(response=(response.final_url, response.status_code, response.content_length)):
                    with self.assertRaises(CapturePipelineError):
                        capture_content(
                            content_id="content:unsafe-final",
                            url="https://example.test/article", store=store,
                            body_store=CaptureBodyStore(Path(tmp)),
                            fetcher=SequenceFetcher(response),
                        )
                    self.assertEqual(store.captures, {})
                    self.assertEqual(store.passages, {})
                    self.assertFalse(list(Path(tmp).rglob("*.body")))

    def test_unbounded_or_invalid_response_limit_rejected_before_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            for bad_limit in (True, 0, -1, 1.5, "4096", None, MAX_DISCOVERY_RESPONSE_BYTES + 1):
                fetcher = SequenceFetcher(fetched(b"<p>not fetched</p>"))
                with self.subTest(bad_limit=bad_limit), self.assertRaisesRegex(
                    CapturePipelineError, "CAPTURE_RESPONSE_LIMIT_INVALID"
                ):
                    capture_content(
                        content_id="content:bad-limit", url="https://example.test/article",
                        store=store, body_store=CaptureBodyStore(Path(tmp)),
                        max_response_bytes=bad_limit, fetcher=fetcher,
                    )
                self.assertEqual(fetcher.calls, 0)
                self.assertEqual(store.captures, {})

    def test_direct_fetch_validation_checks_complete_public_2xx_bytes(self):
        safe = fetched(b"<p>Public representation.</p>")
        _validate_fetched_resource(safe, max_response_bytes=len(safe.body))
        _validate_fetched_resource(
            replace(safe, final_url="https://1.1.1.1/verified", status_code=206),
            max_response_bytes=len(safe.body),
        )
        cases = (
            (replace(safe, status_code=304), "CAPTURE_HTTP_STATUS_BLOCKED"),
            (replace(safe, body=bytearray(safe.body)), "CAPTURE_BODY_INVALID"),
            (replace(safe, content_length=-1), "CAPTURE_CONTENT_LENGTH_MISMATCH"),
            (replace(safe, content_length=False), "CAPTURE_CONTENT_LENGTH_MISMATCH"),
            (replace(safe, final_url="https://127.1/hidden"), "CAPTURE_FINAL_URL_AMBIGUOUS_IP"),
            (replace(safe, final_url="https://[::1]/hidden"), "CAPTURE_FINAL_URL_NONPUBLIC_IP"),
        )
        for response, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(
                CapturePipelineError, expected
            ):
                _validate_fetched_resource(response, max_response_bytes=MAX_DISCOVERY_RESPONSE_BYTES)

    def test_fetch_adapter_exception_redacts_private_error_before_persistence(self):
        def unsafe_fetcher(url, *, max_response_bytes):
            raise RuntimeError("https://private.example/api?token=supersecret")

        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            with self.assertRaisesRegex(CapturePipelineError, "CAPTURE_FETCH_FAILED") as caught:
                capture_content(
                    content_id="content:failed-fetch", url="https://example.test/article",
                    store=store, body_store=CaptureBodyStore(Path(tmp)),
                    fetcher=unsafe_fetcher,
                )
            self.assertNotIn("supersecret", str(caught.exception))
            self.assertEqual(store.captures, {})
            self.assertEqual(store.passages, {})
            self.assertFalse(list(Path(tmp).rglob("*.body")))

    def test_browser_fallback_cannot_persist_unsafe_final_url(self):
        class UnsafeRedirectBrowser:
            renderer_id = "fake-browser"
            renderer_version = "v1"

            def render(self, url, *, max_response_bytes):
                return fetched(b"<article><p>private intranet text</p></article>",
                               url="https://127.0.0.1/private")

        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:browser-unsafe", url="https://example.test/article",
                store=store, body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(fetched(b"<html><script>empty()</script></html>")),
                browser_renderer=UnsafeRedirectBrowser(),
            )
            self.assertEqual(receipt.browser_status, "FAILED")
            self.assertEqual(len(store.captures), 1)
            self.assertFalse(store.passages)
            self.assertTrue(any(key[1] == "BROWSER_FALLBACK_FAILED" for key in store.events))
            self.assertNotIn("intranet", repr(store.events))

    def test_relevance_supersession_during_fetch_blocks_before_body_or_capture_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            body_store = CaptureBodyStore(Path(tmp))

            def fetch_and_supersede(url, *, max_response_bytes):
                store.relevance_allowed = False
                return fetched(b"<p>Must not be persisted after relevance becomes stale.</p>")

            with self.assertRaisesRegex(
                CapturePipelineError, "INGESTION_RELEVANCE_MISSING"
            ):
                capture_content(
                    content_id="content:relevance-race",
                    url="https://example.test/relevance-race",
                    store=store,
                    body_store=body_store,
                    observed_at="2026-10-07T20:30:00+00:00",
                    fetcher=fetch_and_supersede,
                )

            self.assertEqual(store.captures, {})
            self.assertEqual(store.passages, {})
            self.assertFalse(any(Path(tmp).rglob("*.body")))

    def test_source_content_policy_compiles_enrichment_permissions_fail_closed(self):
        policy = capture_enrichment_policy_from_source(
            {
                "content_policy": {
                    "metadata_enrichment_enabled": False,
                    "archive_enabled": False,
                }
            }
        )
        self.assertFalse(policy.metadata_enabled)
        self.assertFalse(policy.archive_enabled)
        self.assertEqual(
            capture_enrichment_policy_from_source({}),
            CaptureEnrichmentPolicy(),
        )
        with self.assertRaisesRegex(
            CapturePipelineError, "SOURCE_METADATA_ENRICHMENT_ENABLED_INVALID"
        ):
            capture_enrichment_policy_from_source(
                {"content_policy": {"metadata_enrichment_enabled": "no"}}
            )

    def test_source_metadata_extracts_canonical_social_jsonld_and_oembed(self):
        html = """
        <html><head>
          <link rel="canonical" href="/canonical">
          <link rel="alternate" type="application/json+oembed" href="https://embed.example.test/oembed">
          <meta property="og:title" content="Titolo OG">
          <meta name="author" content="Autore">
          <script type="application/ld+json">
            {"@type":"NewsArticle","headline":"Titolo JSON-LD",
             "author":{"@type":"Person","name":"Mario Rossi"},
             "publisher":{"@type":"Organization","name":"Editore"},
             "articleBody":"PRIVATE BODY MUST NOT BE COPIED"}
          </script>
        </head><body><p>Visible text.</p></body></html>
        """
        metadata = extract_source_metadata(
            html,
            base_url="https://example.test/article",
        )
        self.assertEqual(
            metadata["canonical_url_candidates"],
            ["https://example.test/canonical"],
        )
        self.assertEqual(metadata["meta"]["og:title"], "Titolo OG")
        self.assertEqual(metadata["meta"]["author"], "Autore")
        self.assertEqual(
            metadata["oembed_candidates"][0]["url"],
            "https://embed.example.test/oembed",
        )
        self.assertEqual(
            metadata["jsonld_identity"][0]["author"]["name"],
            "Mario Rossi",
        )
        self.assertNotIn("articleBody", metadata["jsonld_identity"][0])

    def test_source_metadata_rejects_non_https_identity_urls(self):
        metadata = extract_source_metadata(
            '<link rel="canonical" href="http://example.test/insecure">'
            '<link rel="alternate" type="application/json+oembed" href="javascript:alert(1)">',
            base_url="https://example.test/article",
        )
        self.assertEqual(metadata["canonical_url_candidates"], [])
        self.assertEqual(metadata["oembed_candidates"], [])

    def test_parse_result_carries_source_metadata_without_changing_visible_text(self):
        body = (
            b'<html><head><meta property="og:title" content="Metadata title"></head>'
            b'<body><article><p>Actual visible statement.</p></article></body></html>'
        )
        result = StdlibVisibleTextParser().parse(fetched(body))
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.canonical_text, "Actual visible statement.")
        self.assertEqual(result.metadata["meta"]["og:title"], "Metadata title")

    def test_changed_bytes_create_new_capture_same_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            body_store = CaptureBodyStore(Path(tmp))
            first = capture_content(
                content_id="content:1",
                url="https://example.test/a",
                store=store,
                body_store=body_store,
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Version one factual text.</p>")),
            )
            second = capture_content(
                content_id="content:1",
                url="https://example.test/a",
                store=store,
                body_store=body_store,
                observed_at="2026-09-29T10:05:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Version two changed factual text.</p>")),
            )
            self.assertEqual(len(store.captures), 2)
            self.assertNotEqual(first.primary_capture_id, second.primary_capture_id)
            self.assertNotEqual(first.content_sha256, second.content_sha256)
            self.assertEqual(first.capture_state, "INSERTED")
            self.assertEqual(second.capture_state, "INSERTED")

    def test_unchanged_replay_reuses_capture_and_passages_and_records_reobservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            body_store = CaptureBodyStore(Path(tmp))
            body = b"<article><p>Same factual paragraph.</p><p>Second paragraph.</p></article>"
            first = capture_content(
                content_id="content:1", url="https://example.test/a", store=store,
                body_store=body_store, observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(body)),
            )
            second = capture_content(
                content_id="content:1", url="https://example.test/a", store=store,
                body_store=body_store, observed_at="2026-09-29T11:00:00+00:00",
                fetcher=SequenceFetcher(fetched(body)),
            )
            self.assertEqual(len(store.captures), 1)
            self.assertEqual(first.primary_capture_id, second.primary_capture_id)
            self.assertEqual(second.capture_state, "EXISTING")
            self.assertEqual(first.passage_ids, second.passage_ids)
            self.assertTrue(second.passage_states)
            self.assertEqual(set(second.passage_states), {"EXISTING"})
            reobserved = [k for k in store.events if k[1] == "CAPTURE_REOBSERVED"]
            self.assertEqual(len(reobserved), 1)

    def test_parser_failure_keeps_capture_and_truthful_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:empty", url="https://example.test/empty", store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<html><script>onlyScript()</script></html>")),
            )
            self.assertEqual(receipt.parse_status, "FAILED")
            self.assertEqual(receipt.reason_code, "PARSER_EMPTY_TEXT")
            self.assertEqual(len(store.captures), 1)
            self.assertEqual(len(store.passages), 0)
            failures = [v for k, v in store.events.items() if k[1] == "PARSE_FAILED"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["receipt"]["error_category"], "PARSER_EMPTY_TEXT")

    def test_browser_failure_isolated_from_successful_safe_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            browser = FailingBrowser()
            receipt = capture_content(
                content_id="content:browser", url="https://example.test/browser", store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<html><body></body></html>")),
                browser_renderer=browser,
            )
            self.assertEqual(browser.calls, 1)
            self.assertEqual(receipt.browser_status, "FAILED")
            self.assertEqual(receipt.capture_state, "INSERTED")
            self.assertEqual(len(store.captures), 1)
            self.assertTrue(any(k[1] == "BROWSER_FALLBACK_FAILED" for k in store.events))

    def test_browser_success_creates_distinct_render_capture_and_passages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:browser-ok", url="https://example.test/browser", store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<html><body></body></html>")),
                browser_renderer=SuccessfulBrowser(),
            )
            self.assertEqual(receipt.browser_status, "SUCCEEDED")
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            self.assertNotEqual(receipt.primary_capture_id, receipt.selected_capture_id)
            self.assertEqual(len(store.captures), 2)
            self.assertTrue(receipt.passage_ids)

    def test_archive_failure_does_not_erase_parsed_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            archive = FailingArchive()
            receipt = capture_content(
                content_id="content:archive", url="https://example.test/archive", store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Archive independent parsing.</p>")),
                archive_adapter=archive,
            )
            self.assertEqual(archive.calls, 1)
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            self.assertTrue(receipt.passage_ids)
            self.assertEqual(receipt.archive_status, "FAILED")
            self.assertEqual(store.archive[receipt.primary_capture_id], "FAILED")

    def test_archive_pending_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:archive-pending", url="https://example.test/archive", store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Pending archive paragraph.</p>")),
                archive_adapter=PendingArchive(),
            )
            self.assertEqual(receipt.archive_status, "PENDING")
            self.assertEqual(store.archive[receipt.primary_capture_id], "PENDING")

    def test_archive_success_requires_safe_durable_https_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:archive-success",
                url="https://example.test/archive-success",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Archived source.</p>")),
                archive_adapter=SuccessfulArchive(),
            )
            self.assertEqual(receipt.archive_status, "SUCCEEDED")
            self.assertEqual(store.archive[receipt.primary_capture_id], "SUCCEEDED")

        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:archive-unsafe-success",
                url="https://example.test/archive-unsafe-success",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Unsafe archive locator.</p>")),
                archive_adapter=SuccessfulArchive("http://archive.example.test/item/1"),
            )
            self.assertEqual(receipt.archive_status, "FAILED")
            self.assertEqual(store.archive[receipt.primary_capture_id], "FAILED")

    def test_source_policy_can_disable_metadata_enrichment_without_disabling_parse(self):
        body = b"""
        <html><head>
          <meta property="og:title" content="Private metadata title">
          <link rel="alternate" type="application/json+oembed" href="https://embed.example.test/oembed">
        </head><body><p>Visible source text remains parseable.</p></body></html>
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:metadata-policy",
                url="https://example.test/metadata-policy",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(body)),
                enrichment_policy=CaptureEnrichmentPolicy(metadata_enabled=False),
            )
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            self.assertTrue(receipt.passage_ids)
            record = next(iter(store.captures.values()))["record"]
            self.assertEqual(record.metadata["source_metadata_policy"], "DISABLED")
            self.assertEqual(record.metadata["source_metadata"], {})

    def test_source_policy_can_disable_archive_before_adapter_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            archive = FailingArchive()
            receipt = capture_content(
                content_id="content:archive-policy",
                url="https://example.test/archive-policy",
                store=store,
                body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"<p>Policy-gated archive.</p>")),
                archive_adapter=archive,
                enrichment_policy=CaptureEnrichmentPolicy(archive_enabled=False),
            )
            self.assertEqual(archive.calls, 0)
            self.assertEqual(receipt.archive_status, "DISABLED_POLICY")
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            record = next(iter(store.captures.values()))["record"]
            self.assertEqual(record.archive_status, "NOT_REQUESTED")
            self.assertEqual(record.metadata["source_archive_policy"], "DISABLED")

    def test_passage_roundtrip_reparses_capture_bytes(self):
        body = b"<article><h1>Heading</h1><p>First paragraph with fact.</p><p>Second fact.</p></article>"
        parsed = StdlibVisibleTextParser().parse(fetched(body))
        self.assertEqual(parsed.status, "SUCCEEDED")
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:roundtrip", url="https://example.test/roundtrip", store=store,
                body_store=CaptureBodyStore(Path(tmp)), observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(body)),
            )
            for passage_id in receipt.passage_ids:
                passage = store.passages[passage_id]
                self.assertTrue(
                    verify_passage_roundtrip(
                        body=body, media_type="text/html", charset="utf-8", passage=passage
                    )
                )

    def test_binary_media_is_captured_but_not_misparsed_as_written_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:pdf", url="https://example.test/doc.pdf", store=store,
                body_store=CaptureBodyStore(Path(tmp)), observed_at="2026-09-29T10:00:00+00:00",
                fetcher=SequenceFetcher(fetched(b"%PDF fake", media_type="application/pdf")),
            )
            self.assertEqual(receipt.parse_status, "FAILED")
            self.assertEqual(receipt.reason_code, "PARSER_UNSUPPORTED_MEDIA_TYPE")
            self.assertFalse(receipt.passage_ids)
            self.assertEqual(len(store.captures), 1)

    def test_body_store_is_private_and_not_shared_across_capture_ids(self):
        body = b"same bytes"
        digest = hashlib.sha256(body).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = CaptureBodyStore(root)
            first = store.write(capture_id="capture:one", body=body, content_sha256=digest)
            second = store.write(capture_id="capture:two", body=body, content_sha256=digest)
            self.assertNotEqual(first.body_ref, second.body_ref)
            self.assertEqual(store.read(first.body_ref, expected_sha256=digest), body)
            self.assertEqual(store.read(second.body_ref, expected_sha256=digest), body)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(store.path(first.body_ref).stat().st_mode), 0o600)

    def test_body_store_refuses_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(CapturePipelineError, "BODY_HASH_MISMATCH"):
                CaptureBodyStore(Path(tmp)).write(
                    capture_id="capture:x", body=b"actual", content_sha256="0" * 64
                )


if __name__ == "__main__":
    unittest.main()
