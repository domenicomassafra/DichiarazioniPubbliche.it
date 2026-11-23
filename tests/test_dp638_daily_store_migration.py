import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DailyStoreMigrationTests(unittest.TestCase):
    def test_migration_is_additive_and_contains_owner_verdict_and_rights_contracts(self):
        migration = (
            ROOT / "db" / "migrations" / "20261112-add-dp638-daily-machine.sql"
        ).read_text(encoding="utf-8")
        self.assertEqual(migration.count("CREATE TABLE IF NOT EXISTS daily_"), 4)
        self.assertNotIn("UPDATE processing_job", migration)
        self.assertNotIn("DROP TABLE", migration)
        self.assertIn("CONTRADICTORY_WITH_ITSELF", migration)
        self.assertIn("daily_verdict_factual_only", migration)
        self.assertIn("daily_statement_status_check", migration)
        self.assertIn("DP638_CAPTURE_SOURCE_MISMATCH", migration)
        self.assertIn("DP638_RIGHTS_HOLD_PUBLIC_RSS", migration)
        self.assertIn("DP638_CAPTURE_RIGHTS_OR_RETENTION_BLOCKED", migration)
        self.assertIn(
            "content_capture_id  text NOT NULL UNIQUE REFERENCES content_capture(id)",
            migration,
        )
        self.assertIn(
            "retention_class NOT IN ('DURABLE_PRIVATE', 'DURABLE_PROVENANCE')",
            migration,
        )
        self.assertIn("lower(source.source_type)", migration)
        self.assertNotIn("body            text NOT NULL", migration)
        self.assertIn(
            "FOREIGN KEY (capture_id, content_id, source_id, source_url)",
            migration,
        )
        self.assertIn("claim_nature        text NOT NULL,", migration)


if __name__ == "__main__":
    unittest.main()
