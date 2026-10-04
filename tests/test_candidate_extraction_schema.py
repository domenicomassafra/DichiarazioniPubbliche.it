import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CandidateExtractionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-candidate-extraction-runs.sql").read_text()

    def _block(self, sql, table):
        start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
        return sql[start:sql.index(");", start)]

    def test_schema_and_migration_have_run_and_entity_mention_tables(self):
        for table in ("candidate_extraction_run", "entity_mention_candidate"):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_extraction_run_has_exact_passage_provenance_cost_and_lease(self):
        block = self._block(self.schema, "candidate_extraction_run")
        self.assertIn("FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id)", block)
        self.assertIn("FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id)", block)
        self.assertIn("FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id)", block)
        self.assertIn("operation_key           text NOT NULL UNIQUE", block)
        self.assertIn("cost_upper_bound_usd", block)
        self.assertIn("cost_usd", block)
        self.assertIn("call_count", block)
        self.assertIn("provider_receipt_id", block)
        self.assertIn("lease_owner", block)
        self.assertIn("lease_until", block)
        self.assertIn("(status = 'RUNNING') = (lease_owner IS NOT NULL AND lease_until IS NOT NULL)", block)

    def test_entity_mention_is_reviewable_but_not_identity_merge(self):
        block = self._block(self.schema, "entity_mention_candidate")
        self.assertIn("proposed_entity_type", block)
        self.assertIn("KNOWN_ALIAS", block)
        self.assertIn("MODEL", block)
        self.assertNotIn("target_person_id", block)
        self.assertNotIn("target_organization_id", block)
        for sql in (self.schema, self.migration):
            self.assertIn("'ENTITY_MENTION_CANDIDATE'", sql)

    def test_migration_is_additive_except_review_constraint_refresh(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("insert into atomic_claim", lowered)
        self.assertNotIn("insert into evidence", lowered)
        self.assertNotIn("insert into finding", lowered)
        self.assertIn("drop constraint if exists review_event_entity_type_check", lowered)

    def test_public_projection_cannot_read_extraction_private_tables(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for name in ("candidate_extraction_run", "entity_mention_candidate", "statement_candidate", "claim_candidate"):
            self.assertNotIn(name, projection)

    def test_backup_restore_inventory_includes_extraction_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        for table in ("candidate_extraction_run", "entity_mention_candidate"):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_provider_receipt_precedes_run_in_fresh_schema(self):
        self.assertLess(
            self.schema.index("CREATE TABLE IF NOT EXISTS provider_receipt"),
            self.schema.index("CREATE TABLE IF NOT EXISTS candidate_extraction_run"),
        )

    def test_atomic_commit_sql_has_explicit_parent_cte_dependencies(self):
        runtime = (ROOT / "poc" / "dichiarazioni_pubbliche" / "candidate_extraction.py").read_text()
        self.assertIn("JOIN statement_insert inserted_statement", runtime)
        self.assertIn("LEFT JOIN passage_insert inserted_passage", runtime)
        self.assertIn("EXISTS (SELECT 1 FROM receipt_insert)", runtime)

    def test_extraction_call_and_cost_bounds_are_enforced_in_schema_and_migration(self):
        migration = (ROOT / "db" / "migrations" / "20260929-add-candidate-extraction-runs.sql").read_text()
        for sql in (self.schema, migration):
            self.assertIn("candidate_extraction_run_call_count_check", sql)
            self.assertIn("CHECK (call_count IN (0, 1))", sql)
            self.assertIn("candidate_extraction_run_pre_call_cost_check", sql)
            self.assertIn("CHECK (call_count > 0 OR cost_usd = 0)", sql)
            self.assertIn("candidate_extraction_run_completed_receipt_check", sql)
            self.assertIn("status <> 'COMPLETED' OR (call_count = 1 AND provider_receipt_id IS NOT NULL)", sql)
        self.assertIn("DROP CONSTRAINT IF EXISTS candidate_extraction_run_call_count_check", migration)
        self.assertIn("DROP CONSTRAINT IF EXISTS candidate_extraction_run_pre_call_cost_check", migration)
        self.assertIn("DROP CONSTRAINT IF EXISTS candidate_extraction_run_completed_receipt_check", migration)


if __name__ == "__main__":
    unittest.main()
