"""Regression for the real nonce-bound Studio Capture comparison script."""

import shutil
import subprocess
import unittest
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_local_page import (  # noqa: E402
    render_studio_login_page,
)


class StudioCaptureDiffDomTests(unittest.TestCase):
    def test_private_template_preserves_reviewed_exact_bytes(self):
        # The helper JavaScript is injected at render time. Hash the final
        # nonce-bound bytes, including that helper, rather than the raw _PAGE.
        self.assertEqual(
            sha256(render_studio_login_page("a" * 32)).hexdigest(),
            "03f6d6049183de32339609e4d06a582c1fd9ad271a9e2b5dd0145f2673b18ec7",
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_versioned_audit_locators_never_copy_raw_text(self):
        proc = subprocess.run(
            ["node", str(ROOT / "tests/studio_capture_diff_dom.cjs")],
            input=render_studio_login_page("a" * 32),
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout.decode() + proc.stderr.decode())
        self.assertIn(b"DP-419 private Capture diff and audit clipboard PASS", proc.stdout)
