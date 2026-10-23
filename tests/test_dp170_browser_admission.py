"""#170: admission rules found by running a real browser (launcher scripts, SPA routes)."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.browser_renderer import (  # noqa: E402
    BrowserRenderBlocked, PlaywrightBrowserRenderer,
)
from tests.test_browser_renderer import (  # noqa: E402
    FakeFactory, FakePage, FixtureFetcher, URL, public_dns,
)


def routed_goto(suffix):
    """Patch target for FakePage.goto that simulates a client-side route change."""
    original = FakePage.goto

    def goto(inner, url, **kwargs):
        original(inner, url, **kwargs)
        inner.url = url + suffix

    return goto


class BrowserAdmissionTests(unittest.TestCase):
    def renderer(self, fragment=None):
        factory = FakeFactory()
        renderer = PlaywrightBrowserRenderer(
            enabled=True, chromium_binary="/usr/bin/google-chrome",
            fetcher=FixtureFetcher(), resolver=public_dns,
            playwright_factory=factory,
        )
        return renderer, fragment

    def test_client_side_fragment_route_is_one_representation(self):
        renderer, _ = self.renderer()
        with patch.object(PlaywrightBrowserRenderer, "_preflight"), \
                patch.object(FakePage, "goto", routed_goto("#/active")):
            result = renderer.render(URL, max_response_bytes=2048)
        self.assertTrue(renderer.last_receipt["fragment_only_url_change"])
        self.assertEqual(result.final_url, URL + "#/active")

    def test_any_other_client_route_change_is_refused(self):
        renderer, _ = self.renderer()
        with patch.object(PlaywrightBrowserRenderer, "_preflight"), \
                patch.object(FakePage, "goto", routed_goto("/other")), self.assertRaisesRegex(
                    BrowserRenderBlocked, "BROWSER_FINAL_URL_CHANGED",
                ):
            renderer.render(URL, max_response_bytes=2048)

    @unittest.skipUnless(
        sys.platform == "linux" and shutil.which("bwrap") is not None,
        "launcher refusal is a Linux sandbox policy",
    )
    def test_distribution_launcher_script_is_refused_before_admission(self):
        # Omarchy/Arch ships /usr/bin/google-chrome-stable as a shell script that
        # execs /opt/google/chrome/google-chrome, a path the namespace never
        # mounts: admission must refuse it instead of failing after launch.
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "google-chrome"
            launcher.write_text('#!/bin/sh\nexec /opt/google/chrome/google-chrome "$@"\n')
            launcher.chmod(0o755)
            renderer = PlaywrightBrowserRenderer(
                enabled=True, chromium_binary=str(launcher),
                resolver=public_dns, fetcher=FixtureFetcher(),
            )
            self.assertTrue(os.access(str(launcher), os.X_OK))
            with self.assertRaisesRegex(
                BrowserRenderBlocked, "BROWSER_CHROMIUM_LAUNCHER_SCRIPT",
            ):
                renderer.render(URL, max_response_bytes=2048)


if __name__ == "__main__":
    unittest.main()
