"""DP514 material cross-month liability and global attempt replay regressions."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dichiarazioni_pubbliche.ops.cost_policy import (
    BudgetPolicy, CostSnapshot, MonthlyBudgetState, MonthlyEurPolicy,
    MonthlyFxQuote, MonthlySettlementObservation, SQLiteMonthlyReservationStore,
    monthly_period,
)


class CrossMonthLiabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp514-crossmonth-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "budget.sqlite"
        self.store = SQLiteMonthlyReservationStore(self.path)
        self.store.initialize()
        self.policy = MonthlyEurPolicy(version="owner:test:1", cap_eur=Decimal("1"), enabled=True)
        self.oct = datetime(2026, 10, 31, 21, tzinfo=timezone.utc)
        self.nov = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
        self.oct_period = monthly_period(self.oct, "Europe/Rome")
        self.nov_period = monthly_period(self.nov, "Europe/Rome")
        self.assertNotEqual(self.oct_period, self.nov_period)
        for t in (self.oct, self.nov):
            self.assertTrue(self.store.bootstrap(self.policy, MonthlyBudgetState(
                period=monthly_period(t, "Europe/Rome"),
                policy_version=self.policy.version, revision=0)))

    def reserve(self, attempt: str, at: datetime, store=None):
        return (store or self.store).reserve(
            policy=self.policy, attempt_id=attempt, operation="CLAIM_EXTRACT",
            upper_bound_usd=Decimal("0.2"), billing_basis="ESTIMATED_ONLY",
            at=at, fx_quote=MonthlyFxQuote(Decimal("0.9"), "synthetic:fx", "offline",
                                             at - timedelta(minutes=1)),
            legacy_policy=BudgetPolicy(), legacy_snapshot=CostSnapshot(0, 0),
        )

    def observation(self, status="UNKNOWN"):
        return MonthlySettlementObservation(
            observation_id="receipt:old", attempt_id="job:old:attempt:1",
            operation="CLAIM_EXTRACT", status=status,
            reported_cost_usd=Decimal("0.1") if status == "REPORTED_UNVERIFIED" else None,
            source_reference="test:cost" if status == "REPORTED_UNVERIFIED" else None,
            source_sha256="a" * 64 if status == "REPORTED_UNVERIFIED" else None,
            observed_at=self.nov,
        )

    def test_unresolved_previous_month_liability_blocks_even_new_billing_period(self):
        self.assertTrue(self.reserve("job:old:attempt:1", self.oct).committed)
        self.assertTrue(self.store.reconcile(
            policy=self.policy, period=self.oct_period,
            observation=self.observation()).committed)
        result = self.reserve("job:new:attempt:1", self.nov,
                              SQLiteMonthlyReservationStore(self.path))
        self.assertFalse(result.committed)
        self.assertEqual(result.reason, "MONTHLY_PREVIOUS_PERIOD_UNRESOLVED")
        self.assertEqual(self.store.read(self.nov_period).revision, 0)

    def test_cross_month_same_attempt_key_cannot_be_reserved_twice(self):
        self.assertTrue(self.reserve("job:global:attempt:1", self.oct).committed)
        replay = self.reserve("job:global:attempt:1", self.nov)
        self.assertFalse(replay.committed)
        self.assertEqual(replay.reason, "MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT")
        self.assertEqual(self.store.read(self.nov_period).revision, 0)
        fresh = self.reserve("job:nov:attempt:1", self.nov)
        self.assertTrue(fresh.committed)
        self.assertFalse(fresh.dispatch_authorized)

    def test_prior_reported_usage_without_unknown_does_not_block_clean_new_month(self):
        self.assertTrue(self.reserve("job:old:attempt:1", self.oct).committed)
        self.assertTrue(self.store.reconcile(
            policy=self.policy, period=self.oct_period,
            observation=self.observation("REPORTED_UNVERIFIED")).committed)
        self.assertTrue(self.reserve("job:new:attempt:1", self.nov).committed)
        self.assertFalse(self.store.read(self.nov_period).unknown_liability)

    def test_upgrade_backfills_previous_reservations_before_replaying_cross_month(self):
        self.assertTrue(self.reserve("job:existing:attempt:1", self.oct).committed)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TRIGGER IF EXISTS monthly_global_attempt_no_delete")
            db.execute("DROP TRIGGER IF EXISTS monthly_global_attempt_no_update")
            db.execute("DROP TABLE IF EXISTS monthly_global_attempt")
        restarted = SQLiteMonthlyReservationStore(self.path)
        restarted.initialize()
        self.assertEqual(self.reserve("job:existing:attempt:1", self.nov, restarted).reason,
                         "MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT")
        self.assertEqual(restarted.read(self.nov_period).revision, 0)

    def test_failed_state_cas_rolls_back_global_attempt_and_can_recover(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TRIGGER deny_month_state_change
                BEFORE UPDATE ON monthly_budget_state
                BEGIN SELECT RAISE(ABORT, 'synthetic power loss'); END
            """)
        denied = self.reserve("job:crash:attempt:1", self.oct)
        self.assertFalse(denied.committed)
        self.assertEqual(denied.reason, "MONTHLY_STORAGE_UNAVAILABLE")
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM monthly_global_attempt").fetchone()[0], 0)
            db.execute("DROP TRIGGER deny_month_state_change")
        self.assertTrue(self.reserve("job:crash:attempt:1", self.oct).committed)
        self.assertEqual(self.reserve("job:crash:attempt:1", self.nov).reason,
                         "MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT")

    def test_overbound_old_month_freezes_new_month_even_after_restart(self):
        self.assertTrue(self.reserve("job:old:attempt:1", self.oct).committed)
        larger = self.observation("REPORTED_UNVERIFIED")
        from dataclasses import replace
        self.assertTrue(self.store.reconcile(
            policy=self.policy, period=self.oct_period,
            observation=replace(larger, reported_cost_usd=Decimal("0.8"))).committed)
        result = self.reserve("job:new:attempt:1", self.nov,
                              SQLiteMonthlyReservationStore(self.path))
        self.assertEqual(result.reason, "MONTHLY_PREVIOUS_PERIOD_UNRESOLVED")
        self.assertEqual(self.store.read(self.nov_period).revision, 0)

    def test_racing_different_periods_same_attempt_admits_one_global_reservation(self):
        gate = Barrier(2)

        def compete(at):
            gate.wait(timeout=5)
            return self.reserve("job:shared:attempt:1", at,
                                SQLiteMonthlyReservationStore(self.path))

        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(compete, self.oct)
            right = pool.submit(compete, self.nov)
            results = (left.result(), right.result())
        self.assertEqual(sum(value.committed for value in results), 1)
        self.assertIn("MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT",
                      {value.reason for value in results})
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM monthly_global_attempt").fetchone()[0], 1)
        self.assertEqual(sum(self.store.read(p).revision
                             for p in (self.oct_period, self.nov_period)), 1)


if __name__ == "__main__":
    unittest.main()
