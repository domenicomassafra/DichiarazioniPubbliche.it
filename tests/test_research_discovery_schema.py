import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ResearchDiscoverySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-research-discovery-runs.sql").read_text()

    def _block(self, sql, table):
        start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
        return sql[start:sql.index(");", start)]

    def test_schema_and_migration_have_all_discovery_tables(self):
        for table in (
            "research_discovery_manifest",
            "research_discovery_query",
            "research_discovery_run",
            "research_discovery_attempt",
            "research_discovery_hit",
        ):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_clean_schema_defines_discovery_dependencies_before_discovery_tables(self):
        content_pos = self.schema.index("CREATE TABLE IF NOT EXISTS content_item")
        collection_pos = self.schema.index("CREATE TABLE IF NOT EXISTS research_collection")
        discovery_pos = self.schema.index("CREATE TABLE IF NOT EXISTS research_discovery_manifest")
        self.assertLess(content_pos, collection_pos)
        self.assertLess(collection_pos, discovery_pos)

    def test_manifest_and_query_are_versioned_and_bounded(self):
        manifest = self._block(self.schema, "research_discovery_manifest")
        self.assertIn("manifest_sha256", manifest)
        self.assertIn("max_results BETWEEN 1 AND 200", manifest)
        self.assertIn("max_results_per_host BETWEEN 1 AND 50", manifest)
        self.assertIn("cost_cap_usd >= 0 AND cost_cap_usd <= 25", manifest)
        query = self._block(self.schema, "research_discovery_query")
        self.assertIn("adapter_ids", query)
        self.assertIn("source_families", query)
        self.assertIn("seeds", query)
        self.assertIn("max_results BETWEEN 1 AND 100", query)

    def test_run_receipt_has_partial_blocked_failed_states_and_cost(self):
        block = self._block(self.schema, "research_discovery_run")
        for status in ("RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED"):
            self.assertIn(f"'{status}'", block)
        self.assertIn("cost_usd", block)
        self.assertIn("raw_hits", block)
        self.assertIn("new_content", block)
        self.assertIn("existing_content", block)
        self.assertIn("rejected_hits", block)

    def test_attempt_is_unique_per_run_query_adapter_and_has_cost_upper_bound(self):
        block = self._block(self.schema, "research_discovery_attempt")
        self.assertIn("UNIQUE (run_id, query_id, adapter_id)", block)
        self.assertIn("cost_upper_bound_usd", block)
        self.assertIn("provider_receipt", block)
        self.assertIn("BUDGET_BLOCKED", block)

    def test_every_hit_has_disposition_and_content_link_is_optional(self):
        block = self._block(self.schema, "research_discovery_hit")
        for disposition in (
            "NEW_CONTENT", "EXISTING_CONTENT", "DUPLICATE_WITHIN_RUN",
            "HOST_LIMIT", "RESULT_LIMIT", "OUTSIDE_DATE_WINDOW",
            "REJECTED_POLICY", "AMBIGUOUS_CONTENT_IDENTITY",
        ):
            self.assertIn(f"'{disposition}'", block)
        self.assertIn("content_id              text REFERENCES content_item(id)", block)
        self.assertNotIn("raw_body", block)
        self.assertNotIn("transcript", block.lower())

    def test_public_projection_does_not_read_discovery_receipts(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for table in (
            "research_discovery_manifest", "research_discovery_query", "research_discovery_run",
            "research_discovery_attempt", "research_discovery_hit",
        ):
            self.assertNotIn(table, projection)

    def test_backup_restore_inventory_includes_discovery_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        for table in (
            "research_discovery_manifest", "research_discovery_query", "research_discovery_run",
            "research_discovery_attempt", "research_discovery_hit",
        ):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_migration_is_additive(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update finding", lowered)
        self.assertNotIn("insert into finding", lowered)
        self.assertNotIn("insert into evidence", lowered)
        self.assertNotIn("insert into atomic_claim", lowered)


if __name__ == "__main__":
    unittest.main()
