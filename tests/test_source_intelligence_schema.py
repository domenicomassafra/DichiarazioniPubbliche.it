import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SourceIntelligenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT / "db" / "migrations" / "20260930-add-source-intelligence.sql"
        ).read_text()

    def test_normalized_source_intelligence_tables_exist(self):
        for table in (
            "source_profile",
            "source_evidence_role",
            "source_authority_scope",
            "source_relation",
            "evidence_requirement_profile",
            "evidence_requirement_rule",
            "evidence_set_assessment",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", self.schema)
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", self.migration)

    def test_source_relations_reuse_dp115_derivation(self):
        self.assertIn(
            "derivation_candidate_id text REFERENCES content_derivation_candidate",
            " ".join(self.schema.split()),
        )
        for relation in (
            "DERIVED_FROM",
            "REPRINTS",
            "SYNDICATED_FROM",
            "MIRRORS",
            "ARCHIVES_COPY_OF",
            "OFFICIAL_RELEASE_OF",
            "SUMMARIZES",
            "INDEPENDENT_OF",
            "UNKNOWN_RELATION",
        ):
            self.assertIn(f"'{relation}'", self.migration)

    def test_independence_requires_affirmative_basis(self):
        self.assertIn("source_relation_independence_basis_check", self.migration)
        self.assertIn("evidence_basis <> '{}'::jsonb", self.migration)

    def test_assessment_is_a_private_gate_not_a_finding(self):
        block = self.migration[
            self.migration.index("CREATE TABLE IF NOT EXISTS evidence_set_assessment") :
        ]
        for status in (
            "SUFFICIENT_FOR_RULE",
            "INSUFFICIENT_PRIMARY_SOURCE",
            "INSUFFICIENT_INDEPENDENCE",
            "TEMPORAL_MISMATCH",
            "SCOPE_MISMATCH",
            "CONFLICTING_EVIDENCE",
            "ACCESS_OR_RIGHTS_BLOCKED",
            "UNRESOLVED_SOURCE_IDENTITY",
            "UNRESOLVED_DERIVATION",
            "NEEDS_REVIEW",
        ):
            self.assertIn(f"'{status}'", block)
        self.assertNotIn("INSERT INTO finding", self.migration)
        self.assertNotIn("INSERT INTO verification_run", self.migration)

    def test_verification_run_links_exact_source_assessment(self):
        self.assertIn(
            "source_intelligence_assessment_id text REFERENCES evidence_set_assessment(id)",
            " ".join(self.schema.split()),
        )
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS source_intelligence_assessment_id",
            self.migration,
        )

    def test_source_intelligence_has_no_global_rating_fields(self):
        block = self.migration[
            self.migration.index("CREATE TABLE IF NOT EXISTS source_profile") :
        ]
        for forbidden in (
            "source_score",
            "trust_score",
            "reliability_score",
            "publisher_score",
            "political_balance_score",
        ):
            self.assertNotIn(forbidden, block.lower())

    def test_backup_and_restore_inventory_include_new_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py"
        ).read_text()
        for table in (
            "source_profile",
            "source_evidence_role",
            "source_authority_scope",
            "source_relation",
            "evidence_requirement_profile",
            "evidence_requirement_rule",
            "evidence_set_assessment",
        ):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)


if __name__ == "__main__":
    unittest.main()
