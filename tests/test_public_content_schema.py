import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicContentSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261005-add-public-content-resource.sql"
        ).read_text()

    def test_reviewed_public_content_table_is_additive_and_bounded(self):
        for sql in (self.schema, self.migration):
            self.assertIn("content_publication_candidate", sql)
            self.assertIn("publication_version", sql)
            self.assertIn("public-content-v1", sql)
            self.assertIn("public_media_url", sql)
            self.assertIn("media_policy_version", sql)
            for status in ("CANDIDATE", "APPROVED", "REJECTED", "SUPERSEDED"):
                self.assertIn(f"'{status}'", sql)

    def test_only_one_approved_candidate_per_content_and_slug(self):
        for sql in (self.schema, self.migration):
            self.assertIn("content_publication_candidate_approved_unique", sql)
            self.assertIn("content_publication_candidate_slug_approved_unique", sql)
            self.assertIn("WHERE status = 'APPROVED'", sql)

    def test_media_metadata_requires_timed_content_and_policy(self):
        for sql in (self.schema, self.migration):
            self.assertIn("content_kind IN ('VIDEO', 'AUDIO')", sql)
            self.assertIn("media_policy_version IS NOT NULL", sql)
            self.assertIn("OR (duration_ms IS NULL AND public_media_url IS NULL)", sql)

    def test_review_ledger_supports_public_content_candidate(self):
        for sql in (self.schema, self.migration):
            self.assertIn("'CONTENT_PUBLICATION_CANDIDATE'", sql)

    def test_migration_is_transactional_and_replay_safe(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertIn("create table if not exists", lowered)
        self.assertIn("create unique index if not exists", lowered)
        self.assertIn("drop constraint if exists", lowered)
        self.assertNotIn("delete from content_publication_candidate", lowered)
        self.assertNotIn("update content_publication_candidate", lowered)

    def test_backup_and_restore_contract_include_public_content(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (
            ROOT
            / "poc"
            / "dichiarazioni_pubbliche"
            / "ops"
            / "restore_verify.py"
        ).read_text()
        self.assertIn("content_publication_candidate", backup)
        self.assertIn('"content_publication_candidate"', restore)


if __name__ == "__main__":
    unittest.main()
