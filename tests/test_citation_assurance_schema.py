import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CitationAssuranceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261005-add-finding-citation-assurance.sql"
        ).read_text()
        cls.passage_binding_migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261006-add-passage-citation-hash-binding.sql"
        ).read_text()

    def test_schema_and_migration_have_assertion_and_citation_tables(self):
        for table in ("finding_assertion", "finding_assertion_citation"):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_assertion_text_is_hash_and_finding_version_bound(self):
        for sql in (self.schema, self.migration):
            self.assertIn("assertion_text_sha256", sql)
            self.assertIn("assertion_text_sha256 ~ '^[0-9a-f]{64}$'", sql)
            self.assertIn("REFERENCES finding(id) ON DELETE CASCADE", sql)
            self.assertIn("'RATIONALE_MATERIAL'", sql)
            self.assertIn("'finding-assertion-v1'", sql)

    def test_citation_requires_exact_private_support_pointer(self):
        for sql in (self.schema, self.migration):
            self.assertIn(
                "evidence_id         text NOT NULL REFERENCES evidence(id) ON DELETE CASCADE",
                sql,
            )
            self.assertIn(
                "observation_id      text REFERENCES evidence_observation(id) ON DELETE CASCADE",
                sql,
            )
            self.assertIn(
                "passage_id          text REFERENCES passage(id) ON DELETE SET NULL",
                sql,
            )
            self.assertIn(
                "CHECK (observation_id IS NOT NULL OR passage_id IS NOT NULL)",
                sql,
            )
            self.assertIn("finding_assertion_citation_identity_idx", sql)

    def test_migration_is_additive_and_replay_safe(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update finding", lowered)
        self.assertNotIn("delete from", lowered)
        self.assertGreaterEqual(lowered.count("create table if not exists"), 2)
        self.assertGreaterEqual(lowered.count("create index if not exists"), 3)

    def test_unstructured_passage_binding_is_hash_bound_and_additive(self):
        self.assertIn("passage_text_sha256", self.schema)
        self.assertIn("source_content_sha256", self.schema)
        self.assertIn("finding_assertion_passage_binding_valid", self.schema)
        migration = self.passage_binding_migration.lower()
        self.assertIn("add column if not exists passage_text_sha256", migration)
        self.assertIn("add column if not exists source_content_sha256", migration)
        self.assertIn("finding_assertion_passage_binding_valid", migration)
        self.assertIn("create index if not exists", migration)
        self.assertNotIn("drop table", migration)
        self.assertNotIn("drop column", migration)
        self.assertNotIn("update finding", migration)
        self.assertNotIn("delete from", migration)

    def test_backup_and_restore_inventory_include_assertion_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (
            ROOT
            / "poc"
            / "dichiarazioni_pubbliche"
            / "ops"
            / "restore_verify.py"
        ).read_text()
        for table in ("finding_assertion", "finding_assertion_citation"):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_public_projection_consumes_citation_assurance_fail_closed(self):
        projection = (
            ROOT
            / "poc"
            / "dichiarazioni_pubbliche"
            / "public_projection.py"
        ).read_text()
        self.assertIn("FROM finding_assertion assertion", projection)
        self.assertIn("FROM finding_assertion_citation citation", projection)
        self.assertIn("assertion.assertion_text = finding.rationale", projection)
        self.assertIn("verification.observation_ids ?", projection)
        self.assertIn("finding_assertion_passage_binding_valid", projection)
        self.assertNotIn("cited_passage.private_text", projection)


if __name__ == "__main__":
    unittest.main()
