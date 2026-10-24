"""#170: the JS fallback must never certify HTTP partial bodies as full captures."""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.browser_renderer import (  # noqa: E402
    BrowserRenderBlocked, PlaywrightBrowserRenderer,
)
from tests.test_browser_renderer import (  # noqa: E402
    FakeFactory, FixtureFetcher, HTML, JS, SCRIPT, URL, public_dns, response,
)


class PartialHttpResponseTests(unittest.TestCase):
    def test_document_and_script_partial_content_fail_closed(self):
        # Neither request uses Range. A 206 body is an incomplete
        # representation even when declared length equals transferred bytes.
        for resource_url in (URL, SCRIPT):
            with self.subTest(resource_url=resource_url):
                is_document = resource_url == URL
                original = response(
                    HTML if is_document else JS,
                    final_url=resource_url,
                    content_type="text/html" if is_document else "application/javascript",
                )
                fetcher = FixtureFetcher({
                    resource_url: replace(original, status_code=206),
                })
                renderer = PlaywrightBrowserRenderer(
                    enabled=True,
                    chromium_binary="/usr/bin/google-chrome",
                    resolver=public_dns,
                    fetcher=fetcher,
                    playwright_factory=FakeFactory(),
                )
                with patch.object(PlaywrightBrowserRenderer, "_preflight"):
                    with self.assertRaisesRegex(BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"):
                        renderer.render(URL, max_response_bytes=2048)
                self.assertIsNone(renderer.last_receipt)


class StaticCapturePartialResponseTests(unittest.TestCase):
    def test_static_capture_rejects_partial_content_before_persistence(self):
        import tempfile
        from dichiarazioni_pubbliche.capture_http_validation import CapturePipelineError
        from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content
        from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher

        partial = replace(response(
            HTML, final_url=URL, content_type="text/html",
        ), status_code=206)
        store = FakeCaptureStore()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(
                CapturePipelineError, "CAPTURE_HTTP_PARTIAL_CONTENT_REFUSED",
            ):
                capture_content(
                    content_id="fixture-170-partial-static", url=URL,
                    store=store, body_store=CaptureBodyStore(Path(temp)),
                    fetcher=SequenceFetcher(partial),
                )
            self.assertFalse(list(Path(temp).rglob("*.body")))
        self.assertEqual(store.captures, {})

    def test_no_content_statuses_are_not_confused_with_partial_responses(self):
        from dichiarazioni_pubbliche.capture_http_validation import _validate_fetched_resource

        complete = response(b"", final_url=URL, content_type="text/html")
        for status in (204, 205):
            with self.subTest(status=status):
                _validate_fetched_resource(
                    replace(complete, status_code=status), max_response_bytes=1024,
                )


if __name__ == "__main__":
    unittest.main()
