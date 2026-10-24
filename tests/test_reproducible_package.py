"""The reproducible build receipt identifies the exact committed candidate."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_reproducible_package as reproducible  # noqa: E402


class ReproduciblePackageReceiptTests(unittest.TestCase):
    def test_receipt_version_is_from_commit_even_if_checkout_is_dirty(self):
        with tempfile.TemporaryDirectory() as scratch:
            source = Path(scratch) / "candidate"
            source.mkdir()

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=source, check=True, capture_output=True, text=True
                )

            git("init", "-q")
            (source / "VERSION").write_text("0.0.1")
            git("add", "VERSION")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-qm", "candidate")
            # The built artifact uses the commit, not the changed working file.
            (source / "VERSION").write_text("9.9.9")

            stdout = StringIO()
            with (
                mock.patch.object(reproducible.importlib.util, "find_spec", return_value=object()),
                mock.patch.object(
                    reproducible, "build_once",
                    return_value={"candidate.whl": "a" * 64},
                ),
                mock.patch.object(
                    sys, "argv",
                    ["check_reproducible_package.py", "--source", str(source)],
                ),
                redirect_stdout(stdout),
            ):
                self.assertEqual(reproducible.main(), 0)

            receipt = stdout.getvalue()
            self.assertIn("VERSION=0.0.1", receipt)
            self.assertNotIn("VERSION=9.9.9", receipt)


if __name__ == "__main__":
    unittest.main()
