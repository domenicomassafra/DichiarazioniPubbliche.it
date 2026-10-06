import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class KnowledgeSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-knowledge-entity-resolution.sql").read_text()

    def _block(self, sql: str, table: str) -> str:
        start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
        return sql[start:sql.index(");", start)]

    def test_schema_and_migration_have_all_knowledge_tables(self):
        for table in (
            "topic", "topic_alias", "event", "event_alias", "organization_alias",
            "entity_identifier", "entity_resolution_candidate",
        ):
            marker=f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_resolution_candidate_is_private_review_state_not_public_fact(self):
        for sql in (self.schema, self.migration):
            block=self._block(sql,"entity_resolution_candidate").lower()
            self.assertIn("supporting_features", block)
            self.assertIn("contradicting_features", block)
            self.assertIn("candidate", block)
            for token in ("publication_status", "truth_score", "reliability", "fitness", "ideology"):
                self.assertNotIn(token, block)
            self.assertIn("'entity_resolution_candidate'", sql.lower())

    def test_identifier_exact_uniqueness_is_database_enforced(self):
        for sql in (self.schema, self.migration):
            self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS entity_identifier_active_unique", sql)
            self.assertIn("entity_type, authority, identifier_kind, identifier_value", sql)
            self.assertIn("WHERE status = 'ACTIVE'", sql)

    def test_polymorphic_targets_require_exactly_one_matching_family(self):
        for table in ("entity_identifier", "entity_resolution_candidate"):
            block=self._block(self.schema,table)
            self.assertIn("::integer +", block)
            for entity_type in ("PERSON","ORGANIZATION","TOPIC","EVENT"):
                self.assertIn(f"entity_type = '{entity_type}'", block)

    def test_resolution_passage_must_match_content(self):
        block=self._block(self.schema,"entity_resolution_candidate")
        self.assertIn(
            "FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id)", block
        )

    def test_topic_event_changes_use_supersession_lineage(self):
        for table in ("topic","event"):
            block=self._block(self.schema,table)
            self.assertIn("supersedes_id", block)
            self.assertIn("status IN ('ACTIVE', 'SUPERSEDED')", block)
            self.assertNotIn("truth_score", block.lower())

    def test_public_projection_private_resolution_reads_are_dp222_gated(self):
        projection=(ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        schema=(ROOT / "poc" / "dichiarazioni_pubbliche" / "public_schema.py").read_text()
        # DP-114 kept these tables private from the original projection. DP-222 is the
        # separately-approved bridge: reviewed rows may now be consumed as internal gate
        # input, but they are never a public entity graph or public dossier fields.
        self.assertIn("evaluate_public_attribution", projection)
        self.assertIn("public_attribution_input", projection)
        self.assertIn("FROM entity_identifier", projection)
        self.assertIn("FROM entity_resolution_candidate", projection)
        for private_key in (
            "retrieval_score",
            "supporting_features",
            "contradicting_features",
            "identifier_value",
            "speaker_label",
        ):
            self.assertIn(private_key, projection)
            self.assertIn(private_key, schema)

    def test_backup_restore_inventory_includes_knowledge_tables(self):
        backup=(ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore=(ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        for table in (
            "topic","topic_alias","event","event_alias","organization_alias",
            "entity_identifier","entity_resolution_candidate",
        ):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_migration_is_additive_except_review_constraint_replacement(self):
        lowered=self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertIn("drop constraint if exists review_event_entity_type_check", lowered)


if __name__ == "__main__":
    unittest.main()
