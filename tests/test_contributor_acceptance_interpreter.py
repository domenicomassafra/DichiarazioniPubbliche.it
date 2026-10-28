"""Regression: contributor checks use the selected supported Python interpreter."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContributorAcceptanceInterpreterTests(unittest.TestCase):
    def test_subchecks_ignore_a_shadowed_unsupported_python3(self):
        with tempfile.TemporaryDirectory(prefix="dp543-python-path-") as tmp:
            shadow = Path(tmp) / "python3"
            shadow.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
            shadow.chmod(0o755)
            probe = textwrap.dedent(
                """
                import runpy
                import sys

                scope = runpy.run_path(
                    "tools/check_contributor_acceptance.py", run_name="dp543_probe"
                )
                checks = scope["CHECKS"]
                checks[:] = [
                    (name, [command[0], "-c", "import sys; assert sys.version_info >= (3, 11)"])
                    for name, command in checks
                ]
                raise SystemExit(scope["main"]())
                """
            )
            env = os.environ.copy()
            env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
