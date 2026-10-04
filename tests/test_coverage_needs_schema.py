import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoverageNeedSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT / "db" / "migrations" / "20260930-add-coverage-needs.sql"
        ).read_text()

    def test_private_need_and_event_tables_exist(self):
        for table in ("coverage_need", "coverage_need_event"):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_terminal_states_are_explicit_and_bounded(self):
        for token in ("'OPEN'", "'SEARCHING'", "'SATISFIED'", "'BLOCKED'", "'WAIVED'"):
            self.assertIn(token, self.migration)
        self.assertIn("max_attempts BETWEEN 1 AND 10", self.migration)
        self.assertIn("attempt_count <= max_attempts", self.migration)
        self.assertIn("status <> 'BLOCKED' OR blocker_code IS NOT NULL", self.migration)

    def test_satisfaction_requires_explicit_link(self):
        self.assertIn("status <> 'SATISFIED'", self.migration)
        self.assertIn("satisfied_by_content_id IS NOT NULL", self.migration)
        self.assertIn("satisfied_by_evidence_id IS NOT NULL", self.migration)
        self.assertIn("satisfied_by_source_profile_id IS NOT NULL", self.migration)

    def test_no_priority_or_political_score(self):
        block = self.migration.lower()
        for token in ("priority_score", "political_score", "trust_score", "reliability_score"):
            self.assertNotIn(token, block)

    def test_backup_restore_include_coverage_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        for table in ("coverage_need", "coverage_need_event"):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_discovery_manifest_can_target_only_searchable_needs(self):
        discovery = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "research_discovery.py"
        ).read_text()
        self.assertIn("coverage_need_ids", self.schema)
        self.assertIn("ADD COLUMN IF NOT EXISTS coverage_need_ids", self.migration)
        self.assertIn("need.status NOT IN ('OPEN','SEARCHING')", discovery)
        self.assertIn("need.attempt_count >= need.max_attempts", discovery)

    def test_public_projection_does_not_read_coverage_need_state(self):
        projection = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py"
        ).read_text()
        self.assertNotIn("FROM coverage_need", projection)
        self.assertNotIn("JOIN coverage_need", projection)


if __name__ == "__main__":
    unittest.main()
