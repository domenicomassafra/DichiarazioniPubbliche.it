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
    _PAGE,
    render_studio_login_page,
)


class StudioCaptureDiffDomTests(unittest.TestCase):
    def test_split_template_preserves_reviewed_exact_bytes(self):
        # The 11-way extraction of the large preexisting page is mechanical.
        # This digest pins its reviewed assembled HTML + inline JS, including
        # the deliberate DP-419 UI additions, so no fragment drifts silently.
        self.assertEqual(
            sha256(_PAGE.encode("utf-8")).hexdigest(),
            "e7f24a531c2fd4c3b6578e8bd9cd919706f875e041f3d8ec5447b90f808ed8bb",
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
