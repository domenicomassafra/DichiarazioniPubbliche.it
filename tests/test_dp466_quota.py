"""Correction submissions have an atomic quota shared by HTTP processes."""

import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))


class CorrectionQuotaTests(unittest.TestCase):
    def test_per_actor_and_global_limits_survive_new_store_instances(self):
        from dichiarazioni_pubbliche.correction_intake_quota import SqliteCorrectionQuota

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE throttle(bucket TEXT PRIMARY KEY, window INTEGER NOT NULL, used INTEGER NOT NULL)")
            now = 1_800_000_000
            quota = SqliteCorrectionQuota(path, per_actor_per_minute=2, global_per_minute=3)
            alice, bob = "oidc:" + "a" * 64, "oidc:" + "b" * 64
            self.assertTrue(quota.reserve(alice, now))
            self.assertTrue(SqliteCorrectionQuota(path, 2, 3).reserve(alice, now))
            self.assertFalse(quota.reserve(alice, now))
            self.assertTrue(quota.reserve(bob, now))
            self.assertFalse(SqliteCorrectionQuota(path, 2, 3).reserve(bob, now))
            self.assertTrue(quota.reserve(alice, now + 61))

    def test_invalid_identity_and_missing_store_refuse_without_creating_database(self):
        from dichiarazioni_pubbliche.correction_intake_quota import SqliteCorrectionQuota

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.sqlite3"
            quota = SqliteCorrectionQuota(path)
            with self.assertRaises(ValueError):
                quota.reserve("private@example.com", 1_800_000_000)
            with self.assertRaises(sqlite3.Error):
                quota.reserve("oidc:" + "a" * 64, 1_800_000_000)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
