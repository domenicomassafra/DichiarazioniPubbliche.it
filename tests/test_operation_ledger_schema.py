import ast
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
            self.assertIn(
                "billing_basis <> 'MEASURED_PROVIDER_COST'",
                sql,
            )
        self.assertNotIn("COALESCE(estimated_cost_usd, 0) > 0", self.schema)
        migration = (ROOT / "db/migrations/20261011-allow-unknown-discovery-ceiling.sql").read_text()
        self.assertIn("DROP CONSTRAINT IF EXISTS provider_receipt_unknown_cost_check", migration)
        self.assertNotIn("UPDATE provider_receipt", migration)
        self.assertNotIn("DELETE FROM provider_receipt", migration)

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
        package = ROOT / "poc" / "dichiarazioni_pubbliche"
        # Both live consumers now delegate their SQL to a shared module.
        # Assert the actual call site and inspect each function's own SQL,
        # so moving a query cannot silently remove the measured-cost rule.
        queue = (package / "queue_store.py").read_text()
        scheduler = (package / "scheduler_daemon.py").read_text()
        self.assertIn("CostSnapshot(*worker_cost_snapshot(self.run, source_id))", queue)
        self.assertIn("return scheduler_cost_today(self._run, source_id)", scheduler)
        helper = (package / "ops" / "budget_exposure_v1.py").read_text()
        parsed = ast.parse(helper)
        for name in ("worker_cost_snapshot", "scheduler_cost_today"):
            function = next(
                node for node in parsed.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            text = ast.get_source_segment(helper, function)
            self.assertIsNotNone(text)
            self.assertIn("MEASURED_PROVIDER_COST", text)
            self.assertIn("measured_cost_usd", text)
            self.assertIn("estimated_cost_usd", text)
            self.assertRegex(
                text,
                r"WHEN r\.billing_basis='MEASURED_PROVIDER_COST'\s+"
                r"THEN r\.measured_cost_usd\s+ELSE r\.estimated_cost_usd",
            )
            self.assertIn("worker_budget_reservation", text)
        drill = (package / "ops" / "provider_outage_drill.py").read_text()
        for token in ("MEASURED_PROVIDER_COST", "measured_cost_usd", "estimated_cost_usd"):
            self.assertIn(token, drill)

    def test_health_digest_delegates_to_canonical_receipt_reconciliation(self):
        text = (ROOT / "poc/dichiarazioni_pubbliche/health_digest.py").read_text()
        self.assertIn("QueueExecutionCostStore.operation_ledger_receipts(", text)
        self.assertIn("reconcile_operation_billing(", text)
        self.assertIn('"billing_today"', text)
        self.assertNotIn("FROM provider_receipt", text)


if __name__ == "__main__":
    unittest.main()
