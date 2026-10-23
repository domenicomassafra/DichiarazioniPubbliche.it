"""#170: a revoked capture right must stop subsequent browser resource fetches."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.browser_renderer import PlaywrightBrowserRenderer
from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore, CaptureEnrichmentPolicy, capture_content,
)
from tests.test_browser_renderer import (
    URL, HTML, FakeFactory, FixtureFetcher, public_dns, response,
)
from tests.test_capture_pipeline import FakeCaptureStore, SequenceFetcher


class BrowserResourceRightsRaceTests(unittest.TestCase):
    def test_source_right_revoked_after_document_prevents_script_fetch(self):
        approval = {"current": True}

        def current_rights():
            if not approval["current"]:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_RIGHTS_REVOKED")

        class RevokingFetcher(FixtureFetcher):
            def __call__(self, url, *, timeout, max_response_bytes, resolver,
                         allow_redirects=True):
                fetched = super().__call__(
                    url, timeout=timeout, max_response_bytes=max_response_bytes,
                    resolver=resolver, allow_redirects=allow_redirects,
                )
                if url == URL:
                    approval["current"] = False
                return fetched

        fetcher = RevokingFetcher()
        renderer = PlaywrightBrowserRenderer(
            enabled=True, chromium_binary="/usr/bin/google-chrome",
            fetcher=fetcher, resolver=public_dns,
            playwright_factory=FakeFactory(),
        )
        with tempfile.TemporaryDirectory() as temp, patch.object(
            PlaywrightBrowserRenderer, "_preflight",
        ):
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                capture_content(
                    content_id="fixture-170-revocation",
                    url=URL, store=FakeCaptureStore(),
                    body_store=CaptureBodyStore(Path(temp)),
                    fetcher=SequenceFetcher(response(
                        HTML, final_url=URL, content_type="text/html",
                    )),
                    browser_renderer=renderer, rights_status="CLEARED",
                    rights_guard=current_rights,
                    enrichment_policy=CaptureEnrichmentPolicy(browser_render_enabled=True),
                )
        self.assertEqual([call[0] for call in fetcher.calls], [URL],
                         "Browser fetched a subresource after capture rights were revoked")
        self.assertIsNone(renderer.last_receipt)


if __name__ == "__main__":
    unittest.main()
