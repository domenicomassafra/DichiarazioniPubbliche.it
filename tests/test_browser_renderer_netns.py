"""Real MiniPC bubblewrap filesystem-denial regression; no browser download."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

WRAPPER = Path(__file__).resolve().parents[1] / "poc/dichiarazioni_pubbliche/browser_renderer_netns.sh"


@unittest.skipUnless(
    sys.platform == "linux" and shutil.which("bwrap") is not None
    and Path("/usr/bin/sh").is_file(),
    "real bwrap smoke requires supported Linux user namespaces",
)
class BrowserRendererNetnsTests(unittest.TestCase):
    def test_host_filesystem_denied_shell_timing_and_network_namespace_preserved(self):
        # Old --ro-bind / / was RED: host /etc/passwd readable inside wrapper.
        parent_netns = os.readlink("/proc/self/ns/net")
        script = (
            "set -eu; "
            "test ! -e /etc/passwd; test ! -e /etc/shadow; "
            "test ! -e /etc/hostname; test ! -e /etc/ssh; "
            "test ! -e /var/log; test ! -e /root; "
            "test ! -e /home; test ! -e /usr/local; "
            "test ! -e /run/user; test ! -e /sys; "
            "test -x /usr/bin/sh; test -x /bin/sh; "
            "test -w /tmp; test -d /run; test -d /var/run; "
            "readlink /proc/self/ns/net"
        )
        started = time.monotonic()
        process = subprocess.run(
            [str(WRAPPER), "-c", script],
            env={**os.environ, "DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN": "/usr/bin/sh"},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotEqual(process.stdout.strip(), parent_netns)
        self.assertEqual(os.readlink("/proc/self/ns/net"), parent_netns)
        self.assertLess(time.monotonic() - started, 10)

    def test_host_environment_dropped_inside_child(self):
        process = subprocess.run(
            [str(WRAPPER), "-c", 'test -z "${DP170_HOST_TOKEN_TEST:-}" && test "$HOME" = /tmp'],
            env={**os.environ, "DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN": "/usr/bin/sh",
                 "DP170_HOST_TOKEN_TEST": "synthetic-only"},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
