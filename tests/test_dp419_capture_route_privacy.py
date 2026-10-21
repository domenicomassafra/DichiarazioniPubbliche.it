"""DP419 Studio Capture route rejects raw receipts and unexpected private fields."""

import shutil
import subprocess
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page  # noqa: E402


class StudioCaptureRoutePrivacyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_private_capture_route_renders_only_validated_metadata(self):
        result = subprocess.run(
            ["node", str(ROOT / "tests/studio_capture_route_privacy.cjs")],
            input=render_studio_login_page("a" * 32),
            capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0,
                         result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"DP419 private Capture route allowlist", result.stdout)

    def test_studio_source_has_no_raw_private_receipt_fallback(self):
        rendered = render_studio_login_page("a" * 32).decode()
        self.assertFalse("JSON.stringify(receipt" in rendered, "Studio cannot dump private receipts")
        self.assertIn("safeCollectionCaptures(receipt, data)", rendered)
