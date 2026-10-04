import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PropositionClusteringSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-proposition-clusters-derivation.sql").read_text()

    def _block(self, sql: str, table: str) -> str:
        start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
        return sql[start:sql.index(");", start)]

    def test_schema_and_migration_have_all_private_tables(self):
        for table in (
            "content_derivation_family",
            "content_derivation_candidate",
            "proposition_cluster",
            "proposition_cluster_member",
        ):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)

    def test_same_proposition_and_longitudinal_relation_are_separate_models(self):
        block = self._block(self.schema, "proposition_cluster_member")
        self.assertIn("'SAME_PROPOSITION'", block)
        self.assertIn("'RELATED'", block)
        self.assertIn("'DIFFERENT'", block)
        self.assertIn("'UNCERTAIN'", block)
        self.assertNotIn("CONTRADICTION_CANDIDATE", block)
        relation_block = self._block(self.schema, "claim_relation_candidate")
        self.assertIn("'CONTRADICTION_CANDIDATE'", relation_block)

    def test_member_has_exactly_one_claim_family(self):
        block = self._block(self.schema, "proposition_cluster_member")
        self.assertIn(
            "(claim_candidate_id IS NOT NULL)::integer + (atomic_claim_id IS NOT NULL)::integer = 1",
            block,
        )
        self.assertIn("member_type = 'CLAIM_CANDIDATE'", block)
        self.assertIn("member_type = 'ATOMIC_CLAIM'", block)

    def test_derivation_edge_is_reviewable_and_cannot_self_link(self):
        block = self._block(self.schema, "content_derivation_candidate")
        self.assertIn("CHECK (derived_content_id <> origin_content_id)", block)
        self.assertIn("'REPUBLICATION'", block)
        self.assertIn("'SYNDICATION'", block)
        self.assertIn("supporting_features", block)
        self.assertIn("contradicting_features", block)
        self.assertIn("status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')", block)

    def test_review_constraint_knows_all_four_private_entities(self):
        for entity_type in (
            "PROPOSITION_CLUSTER",
            "PROPOSITION_CLUSTER_MEMBER",
            "CONTENT_DERIVATION_FAMILY",
            "CONTENT_DERIVATION_CANDIDATE",
        ):
            self.assertIn(f"'{entity_type}'", self.schema)
            self.assertIn(f"'{entity_type}'", self.migration)

    def test_public_projection_does_not_read_cluster_or_derivation_tables(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for table in (
            "proposition_cluster",
            "proposition_cluster_member",
            "content_derivation_family",
            "content_derivation_candidate",
        ):
            self.assertNotIn(f"FROM {table}", projection)
            self.assertNotIn(f"JOIN {table}", projection)

    def test_backup_restore_inventory_includes_all_four_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        for table in (
            "proposition_cluster",
            "proposition_cluster_member",
            "content_derivation_family",
            "content_derivation_candidate",
        ):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)

    def test_migration_is_additive_and_does_not_mutate_evidence(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update evidence", lowered)
        self.assertNotIn("insert into evidence", lowered)
        self.assertNotIn("update finding", lowered)
        self.assertNotIn("insert into finding", lowered)
        self.assertIn("drop constraint if exists review_event_entity_type_check", lowered)


if __name__ == "__main__":
    unittest.main()
