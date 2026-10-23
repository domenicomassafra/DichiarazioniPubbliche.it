"""#170: no redirect destination may be fetched before provenance validation."""
import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.browser_renderer import BrowserRenderBlocked, PlaywrightBrowserRenderer
from tests.test_browser_renderer import FakeFactory, FixtureFetcher, SCRIPT, URL, public_dns


class RendererRedirectBoundaryTests(unittest.TestCase):
    def test_redirect_refused_before_second_get_even_if_origin_is_allowlisted(self):
        # The fake models source_watcher.fetch_bytes: with allow_redirects=True
        # a 3xx follow-up GET happens before final_url is returned.
        destination = "https://third-party.example.test/private"

        class RedirectingFetcher(FixtureFetcher):
            def __init__(self):
                super().__init__()
                self.followed = []

            def __call__(self, url, *, timeout, max_response_bytes, resolver,
                         allow_redirects=True):
                if url == SCRIPT:
                    if allow_redirects:
                        self.followed.append(destination)
                    raise ValueError("SYNTHETIC_REDIRECT_REFUSED")
                return super().__call__(
                    url, timeout=timeout, max_response_bytes=max_response_bytes,
                    resolver=resolver, allow_redirects=allow_redirects,
                )

        fetcher = RedirectingFetcher()
        renderer = PlaywrightBrowserRenderer(
            enabled=True, chromium_binary="/usr/bin/google-chrome",
            resolver=public_dns, fetcher=fetcher, playwright_factory=FakeFactory(),
        )
        with patch.object(PlaywrightBrowserRenderer, "_preflight"), self.assertRaisesRegex(
            BrowserRenderBlocked, "BROWSER_RESOURCE_REFUSED"
        ):
            renderer.render(URL, max_response_bytes=2048)
        self.assertEqual(fetcher.followed, [],
                         "A redirect target was fetched before provenance validation")
        self.assertEqual([call[0] for call in fetcher.calls], [URL])
        self.assertIsNone(renderer.last_receipt)


if __name__ == "__main__":
    unittest.main()
