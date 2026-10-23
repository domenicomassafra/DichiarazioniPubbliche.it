"""DP-170: isolated synthetic JS renderer, no real sites or credentials."""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import os
import shutil
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.browser_renderer import (  # noqa: E402
    BrowserRenderBlocked,
    PLAYWRIGHT_VERSION,
    PlaywrightBrowserRenderer,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes  # noqa: E402

URL = "https://fixture.example.test/article"
SCRIPT = "https://fixture.example.test/app.js"
HTML = b'<html><body><main><p id="statement"></p></main><script src="/app.js"></script></body></html>'
JS = b'document.getElementById("statement").textContent = "Synthetic JS statement 170";'
RENDERED = b'<html><body><main><p id="statement">Synthetic JS statement 170</p></main><script src="/app.js"></script></body></html>'


def public_dns(host, port, *, type):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP,
             "", ("93.184.216.34", port))]


def response(body, *, final_url, content_type):
    return FetchedBytes(
        body=body, final_url=final_url, status_code=200,
        media_type=content_type, charset="utf-8", content_length=len(body),
    )


class FixtureFetcher:
    def __init__(self, overrides=None):
        self.responses = {
            URL: response(HTML, final_url=URL, content_type="text/html"),
            SCRIPT: response(JS, final_url=SCRIPT, content_type="application/javascript"),
        }
        self.responses.update(overrides or {})
        self.calls = []

    def __call__(self, url, *, timeout, max_response_bytes, resolver, allow_redirects=True):
        self.calls.append((url, timeout, max_response_bytes))
        return self.responses[url]


class FakeRoute:
    def __init__(self, url, resource_type, navigation=False):
        self.request = type("Request", (), {
            "url": url,
            "resource_type": resource_type,
            "method": "GET",
            "is_navigation_request": lambda _: navigation,
        })()
        self.fulfilled = None
        self.aborted = False

    def fulfill(self, **kwargs):
        self.fulfilled = kwargs

    def abort(self):
        self.aborted = True


class FakePage:
    def __init__(self, context, subresources=None):
        self.context = context
        self.url = URL
        self.subresources = subresources or [(SCRIPT, "script")]
        self.rendered = HTML.decode()

    def set_default_timeout(self, timeout):
        self.timeout = timeout

    def goto(self, url, **kwargs):
        self.url = url
        document = FakeRoute(url, "document", navigation=True)
        self.context.handler(document)
        if document.aborted:
            raise RuntimeError("aborted document")
        for resource_url, kind in self.subresources:
            route = FakeRoute(resource_url, kind)
            self.context.handler(route)
            if route.aborted:
                break
            if resource_url == SCRIPT:
                self.rendered = RENDERED.decode()

    def wait_for_timeout(self, value):
        pass

    def on(self, event, handler):
        pass

    def content(self):
        return self.rendered


class FakeContext:
    def __init__(self, subresources):
        self.subresources = subresources
        self.handler = None
        self.websocket_handler = None

    def route(self, pattern, handler):
        self.handler = handler

    def route_web_socket(self, pattern, handler):
        self.websocket_handler = handler

    def new_page(self):
        return FakePage(self, self.subresources)

    def close(self):
        pass


class FakeBrowser:
    version = "Chromium 145.0.0.0"

    def __init__(self, subresources):
        self.subresources = subresources
        self.context_options = None

    def new_context(self, **kwargs):
        self.context_options = kwargs
        return FakeContext(self.subresources)

    def close(self):
        pass


class FakePlaywright:
    def __init__(self, subresources):
        self.chromium = self
        self.subresources = subresources
        self.launch_options = None
        self.browser = None

    def launch(self, **kwargs):
        self.launch_options = kwargs
        self.browser = FakeBrowser(self.subresources)
        return self.browser


class FakeFactory:
    def __init__(self, subresources=None):
        self.playwright = FakePlaywright(subresources)

    def __call__(self):
        return self

    def __enter__(self):
        return self.playwright

    def __exit__(self, *args):
        pass


class BrowserRendererTests(unittest.TestCase):
    def renderer(self, fetcher=None, subresources=None, **kwargs):
        factory = FakeFactory(subresources=subresources)
        renderer = PlaywrightBrowserRenderer(
            enabled=True,
            chromium_binary="/usr/bin/google-chrome",
            fetcher=fetcher or FixtureFetcher(),
            resolver=public_dns,
            playwright_factory=factory,
            **kwargs,
        )
        return renderer, factory

    def mock_preflight(self):
        # Fake browser tests exercise routing only. The real preflight has its
        # own strict opt-in, host/namespace, pinned-version checks.
        return patch.object(PlaywrightBrowserRenderer, "_preflight")

    def test_disabled_by_default_even_with_factory(self):
        renderer, _ = self.renderer()
        renderer.enabled = False
        with self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_POLICY_DISABLED"):
            renderer.render(URL, max_response_bytes=2048)

    def test_javascript_fixture_rendition_receipt_and_isolation_options(self):
        fetcher = FixtureFetcher()
        renderer, factory = self.renderer(fetcher=fetcher)
        with self.mock_preflight():
            result = renderer.render(URL, max_response_bytes=2048)
        self.assertIn(b"Synthetic JS statement 170", result.body)
        self.assertEqual(result.content_length, len(result.body))
        self.assertEqual(fetcher.calls[0][0], URL)
        self.assertEqual(fetcher.calls[1][0], SCRIPT)
        self.assertEqual(renderer.last_receipt["rendered_sha256"], hashlib.sha256(result.body).hexdigest())
        self.assertEqual(renderer.last_receipt["chromium_version"], "Chromium 145.0.0.0")
        self.assertEqual(renderer.last_receipt["resource_count"], 2)
        self.assertTrue(factory.playwright.launch_options["chromium_sandbox"])
        self.assertEqual(factory.playwright.browser.context_options["service_workers"], "block")
        self.assertFalse(factory.playwright.browser.context_options["accept_downloads"])
        self.assertEqual(factory.playwright.launch_options["env"]["HOME"], "/tmp")

    def test_http_redirected_resources_are_refused_even_with_allowed_hosts(self):
        # route.fulfill serves bytes under the requested URL; HTTP redirect
        # destinations would otherwise be lost from provenance and rights.
        for requested, final in (
            (URL, "https://assets.example.test/other-document"),
            (URL, "https://fixture.example.test/other-document"),
            (SCRIPT, "https://assets.example.test/other-script"),
            (SCRIPT, "https://fixture.example.test/other-script"),
        ):
            with self.subTest(requested=requested, final=final):
                is_document = requested == URL
                fetcher = FixtureFetcher({
                    requested: response(
                        HTML if is_document else JS,
                        final_url=final,
                        content_type="text/html" if is_document else "application/javascript",
                    ),
                })
                renderer, _ = self.renderer(
                    fetcher=fetcher,
                    allowed_subresource_hosts=("assets.example.test",),
                )
                with self.mock_preflight(), self.assertRaisesRegex(
                    BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"
                ):
                    renderer.render(URL, max_response_bytes=2048)
                self.assertIsNone(renderer.last_receipt)

    def test_blocks_private_redirect_for_subresource(self):
        fetcher = FixtureFetcher({SCRIPT: response(
            b"<script>unsafe</script>", final_url="https://127.0.0.1/private",
            content_type="application/javascript",
        )})
        renderer, _ = self.renderer(fetcher=fetcher)
        with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
            renderer.render(URL, max_response_bytes=2048)
        self.assertIsNone(renderer.last_receipt)

    def test_blocks_private_or_http_subresources_before_fetch(self):
        for unsafe in ("https://127.0.0.1/secret", "http://fixture.example.test/file",
                       "https://host.internal/file", "https://0x7f000001/a"):
            with self.subTest(unsafe=unsafe):
                fetcher = FixtureFetcher()
                renderer, _ = self.renderer(
                    fetcher=fetcher, subresources=[(unsafe, "script")],
                )
                with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
                    renderer.render(URL, max_response_bytes=2048)
                self.assertEqual([x[0] for x in fetcher.calls], [URL])

    def test_oversized_subresource_and_rendered_document_refused(self):
        fetcher = FixtureFetcher({SCRIPT: response(
            b"A" * 4096, final_url=SCRIPT, content_type="application/javascript",
        )})
        renderer, _ = self.renderer(fetcher=fetcher)
        with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
            renderer.render(URL, max_response_bytes=1024)
        renderer, _ = self.renderer()
        with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RENDERED_BODY_TOO_LARGE"):
            renderer.render(URL, max_response_bytes=100)

    def test_request_budget_and_timeout_fail_closed(self):
        renderer, _ = self.renderer(max_requests=1)
        with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
            renderer.render(URL, max_response_bytes=2048)
        renderer, _ = self.renderer()
        with self.mock_preflight(), patch(
            "dichiarazioni_pubbliche.browser_renderer.time.monotonic",
            side_effect=itertools.chain([0.0], itertools.repeat(20.0)),
        ), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_TIMEOUT"):
            renderer.render(URL, max_response_bytes=2048)

    def test_cross_origin_needs_explicit_host_policy(self):
        foreign = "https://other.example.test/app.js"
        fetcher = FixtureFetcher({foreign: response(
            JS, final_url=foreign, content_type="application/javascript",
        )})
        renderer, _ = self.renderer(fetcher=fetcher, subresources=[(foreign, "script")])
        with self.mock_preflight(), self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
            renderer.render(URL, max_response_bytes=2048)
        self.assertEqual([x[0] for x in fetcher.calls], [URL])
        renderer, _ = self.renderer(
            fetcher=fetcher, subresources=[(foreign, "script")],
            allowed_subresource_hosts=("other.example.test",),
        )
        with self.mock_preflight():
            result = renderer.render(URL, max_response_bytes=2048)
        self.assertEqual(result.status_code, 200)

    @unittest.skipUnless(
        sys.platform == "linux" and shutil.which("bwrap") is not None
        and Path("/usr/bin/sh").is_file(),
        "real bwrap smoke requires supported Linux user namespaces",
    )
    def test_actual_bwrap_wrapper_hides_host_session_bus(self):
        import subprocess
        host_bus = Path(f"/run/user/{os.getuid()}/bus")
        if not host_bus.is_socket():
            self.skipTest("host user session bus absent")
        parent_ns = os.readlink("/proc/self/ns/net")
        script = (
            "test -d /run && test -d /var/run && "
            "test ! -S /run/user/$(id -u)/bus && "
            "test ! -S /var/run/user/$(id -u)/bus && "
            "test ! -d /home/$(id -un) && "
            "readlink /proc/self/ns/net"
        )
        wrapper = ROOT / "poc/dichiarazioni_pubbliche/browser_renderer_netns.sh"
        process = subprocess.run(
            [str(wrapper), "-c", script],
            env={**os.environ, "DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN": "/usr/bin/sh"},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotEqual(process.stdout.strip(), parent_ns)
        self.assertEqual(os.readlink("/proc/self/ns/net"), parent_ns)

    @unittest.skipUnless(
        importlib.util.find_spec("playwright") is not None
        and shutil.which("bwrap") is not None
        and Path("/usr/bin/google-chrome").exists(),
        "real JS smoke requires opt-in Playwright 1.64 and isolated Linux Chromium",
    )
    def test_actual_chromium_executes_local_synthetic_js(self):
        renderer = PlaywrightBrowserRenderer(
            enabled=True, chromium_binary="/usr/bin/google-chrome",
            resolver=public_dns, fetcher=FixtureFetcher(),
        )
        result = renderer.render(URL, max_response_bytes=2048)
        self.assertIn(b"Synthetic JS statement 170", result.body)

    def test_pipeline_requires_current_rights_for_real_renderer(self):
        import tempfile
        from dichiarazioni_pubbliche.capture_pipeline import (
            CaptureBodyStore, CaptureEnrichmentPolicy, capture_content,
        )
        from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher

        store = FakeCaptureStore()
        renderer, _ = self.renderer()
        with tempfile.TemporaryDirectory() as tmp:
            result = capture_content(
                content_id="fixture-170-rights", url=URL,
                store=store, body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(response(
                    HTML, final_url=URL, content_type="text/html",
                )),
                rights_status="UNKNOWN", browser_renderer=renderer,
                enrichment_policy=CaptureEnrichmentPolicy(browser_render_enabled=True),
            )
        self.assertEqual(result.browser_status, "BLOCKED_RIGHTS")
        self.assertEqual(result.parse_status, "FAILED")
        self.assertEqual(len(store.captures), 1)
        self.assertIsNone(renderer.last_receipt)

    def test_pipeline_renders_only_failed_html_with_rights_and_persists_receipt(self):
        import tempfile
        from dichiarazioni_pubbliche.capture_pipeline import (
            CaptureBodyStore, CaptureEnrichmentPolicy, capture_content,
        )
        from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher

        store = FakeCaptureStore()
        renderer, _ = self.renderer()
        checks = []
        with tempfile.TemporaryDirectory() as tmp, self.mock_preflight():
            result = capture_content(
                content_id="fixture-170-rendered", url=URL,
                store=store, body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(response(
                    HTML, final_url=URL, content_type="text/html",
                )),
                browser_renderer=renderer, rights_status="CLEARED",
                rights_guard=lambda: checks.append("revalidated"),
                enrichment_policy=CaptureEnrichmentPolicy(browser_render_enabled=True),
            )
        self.assertGreater(len(checks), 2)
        self.assertEqual(result.browser_status, "SUCCEEDED")
        self.assertEqual(result.parse_status, "SUCCEEDED")
        self.assertNotEqual(result.primary_capture_id, result.selected_capture_id)
        self.assertEqual(len(store.captures), 2)
        self.assertTrue(result.passage_ids)
        events = [event for event in store.events.values()
                  if event["event_type"] == "BROWSER_RENDER_RECEIPT"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["capture_id"], result.selected_capture_id)
        self.assertEqual(events[0]["receipt"]["rendered_sha256"],
                         hashlib.sha256(RENDERED).hexdigest())
        self.assertEqual(events[0]["receipt"]["playwright_version"], PLAYWRIGHT_VERSION)

    def test_static_html_with_renderer_opted_in_never_opens_browser(self):
        import tempfile
        from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content
        from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher

        renderer, factory = self.renderer()
        with tempfile.TemporaryDirectory() as tmp:
            result = capture_content(
                content_id="fixture-170-static", url=URL,
                store=FakeCaptureStore(), body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(response(
                    b"<article><p>Static source captured by safe HTTP.</p></article>",
                    final_url=URL, content_type="text/html",
                )),
                browser_renderer=renderer, rights_status="CLEARED",
                rights_guard=lambda: None,
            )
        self.assertEqual(result.parse_status, "SUCCEEDED")
        self.assertEqual(result.browser_status, "NOT_REQUESTED")
        self.assertIsNone(factory.playwright.launch_options)

    def test_browser_source_policy_defaults_off_and_rejects_invalid_values(self):
        import tempfile
        from dichiarazioni_pubbliche.capture_pipeline import (
            CaptureBodyStore, CaptureEnrichmentPolicy, CapturePipelineError,
            capture_content, capture_enrichment_policy_from_source,
        )
        from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher

        self.assertFalse(capture_enrichment_policy_from_source({}).browser_render_enabled)
        self.assertTrue(capture_enrichment_policy_from_source({
            "content_policy": {"browser_render_enabled": True},
        }).browser_render_enabled)
        with self.assertRaisesRegex(CapturePipelineError, "SOURCE_BROWSER_RENDER_ENABLED_INVALID"):
            capture_enrichment_policy_from_source({
                "content_policy": {"browser_render_enabled": "yes"},
            })
        renderer, factory = self.renderer()
        with tempfile.TemporaryDirectory() as tmp:
            result = capture_content(
                content_id="fixture-170-policy", url=URL,
                store=FakeCaptureStore(), body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(response(
                    HTML, final_url=URL, content_type="text/html",
                )),
                rights_status="CLEARED", rights_guard=lambda: None,
                browser_renderer=renderer, enrichment_policy=CaptureEnrichmentPolicy(),
            )
        self.assertEqual(result.browser_status, "DISABLED_POLICY")
        self.assertEqual(result.parse_status, "FAILED")
        self.assertIsNone(factory.playwright.launch_options)
