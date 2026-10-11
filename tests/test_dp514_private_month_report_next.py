"""Read-only private report against an actual persisted isolated SQLite ledger."""
from __future__ import annotations
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dichiarazioni_pubbliche.ops.cost_policy import (
    BudgetPolicy, CostSnapshot, MonthlyBudgetState, MonthlyEurPolicy,
    MonthlyFxQuote, MonthlySettlementObservation, SQLiteMonthlyReservationStore,
    monthly_period,
)
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/dp514_private_month_report.py"


class PrivateMonthReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp514-private-report-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "synthetic.sqlite"
        self.store = SQLiteMonthlyReservationStore(self.db)
        self.store.initialize()
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.period = monthly_period(self.now, "Europe/Rome")
        self.policy = MonthlyEurPolicy("synthetic:operator:1", Decimal("1"), enabled=True)
        self.store.bootstrap(self.policy, MonthlyBudgetState(self.period, self.policy.version, 0))

    def cli(self, path=None, period=None):
        return subprocess.run([sys.executable, str(SCRIPT),
                               "--db", str(path or self.db),
                               "--period", period or self.period],
                              text=True, capture_output=True, check=False, timeout=8)

    def test_persisted_unknown_receipt_read_only_no_leak_or_authority(self):
        attempt = "job:confidential:42"
        self.assertTrue(self.store.reserve(
            policy=self.policy, attempt_id=attempt, operation="CLAIM_EXTRACT",
            upper_bound_usd=Decimal("0.2"), billing_basis="ESTIMATED_ONLY",
            at=self.now,
            fx_quote=MonthlyFxQuote(Decimal("0.9"), "private-quote-id", "synthetic-provider",
                                     self.now-timedelta(minutes=2)),
            legacy_policy=BudgetPolicy(), legacy_snapshot=CostSnapshot(0, 0),
        ).committed)
        observed = MonthlySettlementObservation(
            "event:unverified", attempt, "CLAIM_EXTRACT", "UNKNOWN",
            None, None, None, self.now + timedelta(minutes=2),
        )
        self.assertTrue(self.store.reconcile(
            policy=self.policy, period=self.period, observation=observed).committed)
        before = self.db.stat().st_size
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["reserved_attempts"], 1)
        self.assertEqual(report["observed_attempts"], 1)
        self.assertEqual(report["held_eur"], "0.180000")
        self.assertTrue(report["unknown_liability"])
        self.assertFalse(report["invoice_attested"])
        self.assertFalse(report["dispatch_authorized"])
        self.assertEqual(self.db.stat().st_size, before)
        for secret in ("confidential", "private-quote", "synthetic-provider"):
            self.assertNotIn(secret, result.stdout)

    def test_missing_db_symlink_wrong_period_fail_without_creating(self):
        missing = Path(self.tmp.name) / "missing.sqlite"
        self.assertEqual(self.cli(path=missing).returncode, 2)
        self.assertFalse(missing.exists())
        link = Path(self.tmp.name) / "link.sqlite"
        link.symlink_to(self.db)
        self.assertEqual(self.cli(path=link).returncode, 2)
        self.assertEqual(self.cli(period="bad-month").returncode, 2)
        self.assertEqual(self.cli(period="2027-01@Europe/Rome").returncode, 2)

    def test_explicit_read_only_connection_forbids_database_update(self):
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location("dp514_private_month_report", SCRIPT)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        reader = module.ReadOnlyBudgetStore(self.db)
        conn = reader._connect()
        try:
            with self.assertRaises(sqlite3.Error):
                conn.execute("UPDATE monthly_budget_state SET revision=100")
        finally:
            conn.close()
        self.assertEqual(self.store.read(self.period).revision, 0)

    def test_real_committed_reservation_during_report_refuses_mixed_snapshot(self):
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location("dp514_private_month_report", SCRIPT)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module.ReadOnlyBudgetStore.reconciliation_report

        def racing_reader(reader, period):
            before = original(reader, period)
            committed = self.store.reserve(
                policy=self.policy, attempt_id="job:racing:1",
                operation="CLAIM_EXTRACT",
                upper_bound_usd=Decimal("0.2"), billing_basis="ESTIMATED_ONLY",
                at=self.now,
                fx_quote=MonthlyFxQuote(
                    Decimal("0.9"), "synthetic:fx", "offline",
                    self.now - timedelta(minutes=1),
                ),
                legacy_policy=BudgetPolicy(), legacy_snapshot=CostSnapshot(0, 0),
            )
            self.assertTrue(committed.committed)
            return before

        with patch.object(module.ReadOnlyBudgetStore, "reconciliation_report", racing_reader):
            with self.assertRaisesRegex(ValueError, "MONTHLY_REPORT_CHANGED_DURING_READ"):
                module.redacted_month_report(self.db, self.period)
        self.assertEqual(self.store.read(self.period).revision, 1)


if __name__ == "__main__":
    unittest.main()
