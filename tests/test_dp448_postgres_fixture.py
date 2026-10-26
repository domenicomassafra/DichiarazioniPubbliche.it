"""Regression for the disposable DP417 PostgreSQL fixture on macOS."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_dp417_queue_family_next as dp417


class DisposablePostgresFixtureTests(unittest.TestCase):
    def test_starts_even_if_host_tmpdir_makes_unix_socket_path_too_long(self):
        with tempfile.TemporaryDirectory(prefix="dp448-repro-", dir="/tmp") as scratch:
            long_tmpdir = Path(scratch) / ("x" * 65)
            long_tmpdir.mkdir()
            would_be_socket = long_tmpdir / "dp417-queue-family-next-12345678" / ".s.PGSQL.65535"
            self.assertGreater(len(str(would_be_socket).encode()), 103)

            with patch.object(tempfile, "tempdir", str(long_tmpdir)):
                dp417.PersistedCaptureQueueTests.setUpClass()
                try:
                    self.assertTrue(dp417.PersistedCaptureQueueTests.started)
                finally:
                    dp417.PersistedCaptureQueueTests.tearDownClass()
