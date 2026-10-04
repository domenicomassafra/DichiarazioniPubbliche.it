import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CandidateMatchingSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT / "db" / "migrations" / "20260930-add-candidate-matching-runtime.sql"
        ).read_text()

    def test_schema_and_migration_have_replay_ledger(self):
        for table in ("candidate_match_run", "candidate_match_result"):
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            self.assertIn(marker, self.schema)
            self.assertIn(marker, self.migration)
        self.assertIn("candidate-matching-v1", self.migration)
        self.assertIn("input_fingerprint", self.migration)

    def test_nullable_target_uniqueness_uses_partial_indexes(self):
        self.assertIn("candidate_match_result_candidate_unique", self.migration)
        self.assertIn("candidate_match_result_atomic_unique", self.migration)
        self.assertNotIn(
            "UNIQUE (run_id, target_type, target_claim_candidate_id, target_atomic_claim_id)",
            self.migration,
        )

    def test_uncertain_has_hold_disposition_and_cluster_proposal_is_reviewable(self):
        self.assertIn("'HOLD'", self.migration)
        self.assertIn("'PROPOSE_CLUSTER'", self.migration)
        self.assertIn("'CANDIDATE_MATCH_RESULT'", self.migration)
        self.assertIn("'CANDIDATE_MATCH_RESULT'", self.schema)
        self.assertIn("'ENTITY_MENTION_CANDIDATE'", self.migration)

    def test_matching_tables_are_private_and_do_not_mutate_claims_or_findings(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for table in ("candidate_match_run", "candidate_match_result"):
            self.assertNotIn(f"FROM {table}", projection)
            self.assertNotIn(f"JOIN {table}", projection)
        lowered = self.migration.lower()
        self.assertNotIn("update atomic_claim", lowered)
        self.assertNotIn("insert into atomic_claim", lowered)
        self.assertNotIn("update finding", lowered)
        self.assertNotIn("insert into finding", lowered)

    def test_candidate_entity_context_uses_passage_provenance_not_fake_statement_fk(self):
        runtime = (ROOT / "poc" / "dichiarazioni_pubbliche" / "candidate_matching.py").read_text()
        self.assertIn("resolution.passage_id", runtime)
        self.assertIn("parent_passage_id", runtime)
        self.assertNotIn("resolution.statement_candidate_id", runtime)

    def test_backup_restore_include_matching_tables(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py"
        ).read_text()
        for table in ("candidate_match_run", "candidate_match_result"):
            self.assertIn(table, backup)
            self.assertIn(f'"{table}"', restore)


if __name__ == "__main__":
    unittest.main()
