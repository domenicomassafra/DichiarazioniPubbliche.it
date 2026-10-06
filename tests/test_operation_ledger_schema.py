import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OperationLedgerSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261005-extend-provider-receipt-ledger.sql"
        ).read_text()

    def test_provider_receipt_has_canonical_ledger_fields(self):
        for sql in (self.schema, self.migration):
            for token in (
                "operation_key",
                "attempt",
                "measured_cost_usd",
                "billing_basis",
                "total_tokens",
                "request_count",
                "ledger_scope",
            ):
                self.assertIn(token, sql)

    def test_billing_basis_distinguishes_unknown_measured_and_zero(self):
        for sql in (self.schema, self.migration):
            for basis in (
                "MEASURED_PROVIDER_COST",
                "ESTIMATED_ONLY",
                "EXTERNAL_PLAN",
                "ZERO_COST",
                "UNKNOWN",
            ):
                self.assertIn(f"'{basis}'", sql)
            self.assertIn("COALESCE(estimated_cost_usd, 0) > 0", sql)
            self.assertIn(
                "billing_basis <> 'MEASURED_PROVIDER_COST'",
                sql,
            )

    def test_operation_and_billing_indexes_exist(self):
        for sql in (self.schema, self.migration):
            self.assertIn("provider_receipt_operation_idx", sql)
            self.assertIn("provider_receipt_billing_idx", sql)

    def test_migration_is_replay_safe_and_does_not_rewrite_receipts(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertIn("add column if not exists", lowered)
        self.assertIn("drop constraint if exists", lowered)
        self.assertIn("create index if not exists", lowered)
        self.assertNotIn("update provider_receipt", lowered)
        self.assertNotIn("delete from provider_receipt", lowered)

    def test_budget_paths_use_measured_else_estimate(self):
        paths = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "queue_store.py",
            ROOT / "poc" / "dichiarazioni_pubbliche" / "scheduler_daemon.py",
            ROOT / "poc" / "dichiarazioni_pubbliche" / "health_digest.py",
            ROOT
            / "poc"
            / "dichiarazioni_pubbliche"
            / "ops"
            / "provider_outage_drill.py",
        )
        for path in paths:
            text = path.read_text()
            self.assertIn("MEASURED_PROVIDER_COST", text)
            self.assertIn("measured_cost_usd", text)
            self.assertIn("estimated_cost_usd", text)


if __name__ == "__main__":
    unittest.main()
