"""DP-415/419: delayed local reads must not survive operator disconnect."""

import shutil
import subprocess
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page  # noqa: E402


from tests.studio_collection_vertical_js import _COLLECTION_VERTICAL_JS



class StudioLocalPageAsyncTests(unittest.TestCase):
    def test_disconnection_and_workspace_change_reject_stale_private_results(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable for inline Studio JS test")
        script = ROOT / "tests" / "studio_local_page_async_regression.cjs"
        result = subprocess.run(
            [node, str(script)],
            input=render_studio_login_page("a" * 32).decode(),
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_collection_capture_written_passage_candidate_and_capture_queue(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable for inline Studio JS test")
        result = subprocess.run(
            [node, "-e", _COLLECTION_VERTICAL_JS],
            input=render_studio_login_page("a" * 32).decode(),
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)



if __name__ == "__main__":
    unittest.main()
