import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CorpusRetentionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT / "db" / "migrations" / "20260929-add-corpus-retention-lifecycle.sql"
        ).read_text()

    def _capture_block(self, sql):
        start = sql.index("CREATE TABLE IF NOT EXISTS content_capture")
        return sql[start:sql.index(");", start)]

    def test_fresh_schema_has_hold_archive_and_purge_receipts(self):
        block = self._capture_block(self.schema)
        for field in (
            "hold_status", "archive_status", "archive_provider", "archive_requested_at",
            "archive_completed_at", "archive_receipt", "body_purged_at", "purge_reason", "purge_receipt",
        ):
            self.assertIn(field, block)
        self.assertIn("'POLICY_PENDING', 'EPHEMERAL', 'DURABLE_PRIVATE', 'DURABLE_PROVENANCE'", block)
        self.assertIn("'PURGE_PENDING', 'PURGED_BODY'", block)

    def test_purged_body_cannot_keep_body_ref_or_lose_receipt(self):
        for sql in (self.schema, self.migration):
            self.assertIn("body_ref IS NULL", sql)
            self.assertIn("purge_receipt <> '{}'::jsonb", sql)
            self.assertIn("body_purged_at IS NOT NULL", sql)

    def test_archive_terminal_state_requires_nonempty_receipt(self):
        for sql in (self.schema, self.migration):
            self.assertIn("archive_status NOT IN ('SUCCEEDED', 'FAILED')", sql)
            self.assertIn("archive_receipt <> '{}'::jsonb", sql)

    def test_lifecycle_event_is_append_only_receipt_table(self):
        for sql in (self.schema, self.migration):
            self.assertIn("CREATE TABLE IF NOT EXISTS capture_lifecycle_event", sql)
            self.assertIn("'BODY_PURGED'", sql)
            self.assertIn("'ARCHIVE_FAILED'", sql)
            self.assertIn("'HOLD_SET'", sql)
            self.assertIn("receipt             jsonb NOT NULL", sql)

    def test_migration_is_additive_no_data_rewrite(self):
        lowered = self.migration.lower()
        self.assertIn("add column if not exists", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update content_capture", lowered)

    def test_public_projection_does_not_read_capture_bodies_or_lifecycle(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        self.assertNotIn("capture_lifecycle_event", projection)
        self.assertNotIn("content_capture", projection)
        self.assertNotIn("private_text", projection)
        self.assertNotIn("body_ref", projection)

    def test_backup_restore_include_lifecycle_events(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        self.assertIn("capture_lifecycle_event", backup)
        self.assertIn('"capture_lifecycle_event"', restore)


if __name__ == "__main__":
    unittest.main()
