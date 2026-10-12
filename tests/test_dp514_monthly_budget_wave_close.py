"""Adversarial USD+EUR admission on real, disposable monthly SQLite state.

An unusable legacy counter or cap must never become an EUR reservation permit.
These are deliberately synthetic inputs, not evidence of provider charges.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import sqlite3
import unittest

from dichiarazioni_pubbliche.ops.cost_policy import (
    BudgetPolicy,
    CostSnapshot,
    MonthlyBudgetState,
    MonthlyEurPolicy,
    MonthlyFxQuote,
    SQLiteMonthlyReservationStore,
    monthly_period,
    preflight,
)


class MonthlyLegacyUsdAdmissionTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(prefix="dp514-month-guard-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "month.sqlite"
        self.store = SQLiteMonthlyReservationStore(self.path)
        self.store.initialize()
        self.policy = MonthlyEurPolicy(version="synthetic-owner-v1", cap_eur=Decimal("0.6"), enabled=True)
        self.oct = datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc)
        self.nov = self.oct + timedelta(hours=1)
        self.assertNotEqual(monthly_period(self.oct, "Europe/Rome"), monthly_period(self.nov, "Europe/Rome"))
        for at in (self.oct, self.nov):
            self.store.bootstrap(self.policy, MonthlyBudgetState(
                period=monthly_period(at, "Europe/Rome"),
                policy_version=self.policy.version, revision=0,
            ))

    def reserve(self, attempt, *, at=None, legacy_policy=None, snapshot=None, store=None):
        at = at or self.oct
        return (store or self.store).reserve(
            policy=self.policy, attempt_id=attempt, operation="CLAIM_EXTRACT",
            upper_bound_usd=Decimal("0.2"), billing_basis="ESTIMATED_ONLY",
            at=at,
            fx_quote=MonthlyFxQuote(Decimal("0.9"), "synthetic-fx", "test", at - timedelta(seconds=1)),
            legacy_policy=legacy_policy or BudgetPolicy(),
            legacy_snapshot=snapshot or CostSnapshot(0, 0),
        )

    def test_nonfinite_and_negative_daily_counters_cannot_mint_eur_reservations(self):
        invalid = (float("nan"), float("-inf"), -0.01)
        for field in ("global_day_usd", "source_day_usd"):
            for index, counter in enumerate(invalid):
                with self.subTest(field=field, counter=counter):
                    values = dict(global_day_usd=0, source_day_usd=0)
                    values[field] = counter
                    result = self.reserve(f"bad:{field}:{index}", snapshot=CostSnapshot(**values))
                    self.assertFalse(result.committed)
                    self.assertEqual(result.reason, "COST_SNAPSHOT_INVALID")
        after_restart = SQLiteMonthlyReservationStore(self.path)
        self.assertEqual(after_restart.read(monthly_period(self.oct, "Europe/Rome")).revision, 0)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM monthly_global_attempt").fetchone()[0], 0)
        legitimate = self.reserve("valid:first", store=after_restart)
        self.assertTrue(legitimate.committed)
        self.assertFalse(legitimate.dispatch_authorized)
        self.assertEqual(self.reserve("valid:first", store=after_restart).reason,
                         "MONTHLY_RESERVATION_ALREADY_RECORDED")

    def test_nonfinite_and_negative_legacy_caps_fail_before_eur_cas(self):
        for cap in (float("nan"), float("inf"), -1.0):
            with self.subTest(cap=cap):
                result = self.reserve("bad:cap", legacy_policy=BudgetPolicy(
                    max_cost_usd_per_job=cap,
                ))
                self.assertFalse(result.committed)
                self.assertEqual(result.reason, "COST_POLICY_INVALID")
        self.assertEqual(self.store.read(monthly_period(self.oct, "Europe/Rome")).revision, 0)

    def test_unpriced_numeric_estimate_never_satisfies_legacy_guards(self):
        for numeric in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(estimate=numeric):
                decision = preflight(BudgetPolicy(), CostSnapshot(0, 0), numeric,
                                     operation="CLAIM_EXTRACT")
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "COST_ESTIMATE_INVALID")

    def test_rejected_october_counter_does_not_poison_or_erase_november_after_restart(self):
        denied = self.reserve("attempt:oct", snapshot=CostSnapshot(math.nan, 0))
        self.assertEqual(denied.reason, "COST_SNAPSHOT_INVALID")
        restarted = SQLiteMonthlyReservationStore(self.path)
        self.assertTrue(self.reserve("attempt:nov", at=self.nov, store=restarted).committed)
        self.assertTrue(self.reserve("attempt:oct", at=self.oct, store=restarted).committed)
        self.assertEqual(self.reserve("attempt:oct", at=self.nov, store=restarted).reason,
                         "MONTHLY_ATTEMPT_GLOBAL_PERIOD_CONFLICT")
        self.assertEqual(restarted.read(monthly_period(self.oct, "Europe/Rome")).revision, 1)
        self.assertEqual(restarted.read(monthly_period(self.nov, "Europe/Rome")).revision, 1)


if __name__ == "__main__":
    unittest.main()
