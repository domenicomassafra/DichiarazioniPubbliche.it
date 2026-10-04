import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClaimPromotionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-claim-candidate-promotion.sql").read_text()

    def test_schema_and_migration_have_promotion_ledger(self):
        marker = "CREATE TABLE IF NOT EXISTS claim_candidate_promotion"
        self.assertIn(marker, self.schema)
        self.assertIn(marker, self.migration)

    def test_ledger_is_one_promotion_per_candidate_and_version(self):
        for sql in (self.schema, self.migration):
            start = sql.index("CREATE TABLE IF NOT EXISTS claim_candidate_promotion")
            block = sql[start:sql.index(");", start)]
            self.assertIn("UNIQUE (claim_candidate_id, promotion_version)", block)
            self.assertIn("idempotency_key     text NOT NULL UNIQUE", block)
            self.assertIn("action IN ('CREATED', 'LINKED_EXISTING')", block)
            self.assertIn("provenance_channel IN ('WRITTEN', 'MEDIA')", block)
            self.assertIn("jsonb_typeof(provenance_refs) = 'array'", block)

    def test_migration_is_additive(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update atomic_claim", lowered)
        self.assertNotIn("update evidence", lowered)
        self.assertNotIn("update finding", lowered)

    def test_backup_restore_inventory_includes_promotion_ledger(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py").read_text()
        self.assertIn("claim_candidate_promotion", backup)
        self.assertIn('"claim_candidate_promotion"', restore)

    def test_public_projection_does_not_read_promotion_ledger(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        self.assertNotIn("claim_candidate_promotion", projection)


if __name__ == "__main__":
    unittest.main()
