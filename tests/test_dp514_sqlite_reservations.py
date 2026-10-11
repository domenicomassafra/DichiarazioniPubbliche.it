"""DP-514: disposable SQLite contention proof, never a paid dispatch gate."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    BudgetPolicy,
    CostSnapshot,
    MonthlyBudgetState,
    MonthlyEurPolicy,
    MonthlyFxQuote,
    SQLiteMonthlyReservationStore,
    monthly_period,
)


class SQLiteMonthlyReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="dp514-sqlite-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "budget.sqlite3"
        self.store = SQLiteMonthlyReservationStore(self.path)
        self.store.initialize()
        self.now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        self.policy = MonthlyEurPolicy(
            version="synthetic-owner-v1", cap_eur=Decimal("0.18"), enabled=True
        )
        self.state = MonthlyBudgetState(
            period=monthly_period(self.now, "Europe/Rome"),
            policy_version=self.policy.version, revision=0,
        )
        self.assertTrue(self.store.bootstrap(self.policy, self.state))
        self.fx = MonthlyFxQuote(
            rate_eur_per_usd=Decimal("0.9"), source="synthetic",
            reference="synthetic-rate", observed_at=self.now - timedelta(minutes=10),
        )

    def reserve(self, attempt_id, *, store=None, policy=None, snapshot=None):
        return (store or self.store).reserve(
            policy=policy or self.policy,
            attempt_id=attempt_id, operation="CLAIM_EXTRACT",
            upper_bound_usd=Decimal("0.2"), billing_basis="ESTIMATED_ONLY",
            at=self.now, fx_quote=self.fx, legacy_policy=BudgetPolicy(),
            legacy_snapshot=snapshot or CostSnapshot(0, 0),
        )

    def test_two_independent_sqlite_connections_cannot_oversubscribe_month(self):
        gate = Barrier(2)

        def competing_worker(attempt):
            separate_process_view = SQLiteMonthlyReservationStore(self.path)
            gate.wait(timeout=5)
            return self.reserve(attempt, store=separate_process_view)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(competing_worker, ("job:1:attempt:1", "job:2:attempt:1")))
        self.assertEqual(sum(row.committed for row in results), 1)
        self.assertEqual(sorted(row.reason for row in results),
                         ["MONTHLY_CAP_REACHED", "MONTHLY_RESERVATION_COMMITTED"])
        self.assertTrue(all(not row.dispatch_authorized for row in results))
        saved = SQLiteMonthlyReservationStore(self.path).read(self.state.period)
        self.assertEqual(saved.revision, 1)
        self.assertEqual(saved.committed_total_eur, Decimal("0.180000"))
        self.assertEqual(len(saved.reservations), 1)

    def test_restart_replay_does_not_reset_or_double_charge_attempt(self):
        first = self.reserve("job:1:attempt:1")
        self.assertTrue(first.committed)
        restarted = SQLiteMonthlyReservationStore(self.path)
        self.assertFalse(restarted.bootstrap(self.policy, self.state))
        replay = self.reserve("job:1:attempt:1", store=restarted)
        self.assertFalse(replay.committed)
        self.assertEqual(replay.reason, "MONTHLY_RESERVATION_ALREADY_RECORDED")
        self.assertEqual(self.reserve("job:2:attempt:1", store=restarted).reason,
                         "MONTHLY_CAP_REACHED")
        self.assertEqual(restarted.read(self.state.period).committed_total_eur,
                         Decimal("0.180000"))

    def test_concurrent_retries_of_exact_attempt_id_create_one_hold(self):
        gate = Barrier(2)

        def retry():
            separate_connection = SQLiteMonthlyReservationStore(self.path)
            gate.wait(timeout=5)
            return self.reserve("job:retry:attempt:1", store=separate_connection)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result() for future in (pool.submit(retry), pool.submit(retry))]
        self.assertEqual(sum(result.committed for result in results), 1)
        self.assertCountEqual((result.reason for result in results), (
            "MONTHLY_RESERVATION_COMMITTED", "MONTHLY_RESERVATION_ALREADY_RECORDED",
        ))
        saved = SQLiteMonthlyReservationStore(self.path).read(self.state.period)
        self.assertEqual(len(saved.reservations), 1)
        self.assertEqual(saved.committed_total_eur, Decimal("0.180000"))

    def test_pinned_policy_cannot_be_raised_under_same_version(self):
        raised = replace(self.policy, cap_eur=Decimal("5"))
        self.assertEqual(self.reserve("job:1:attempt:1", policy=raised).reason,
                         "MONTHLY_STORED_POLICY_MISMATCH")
        self.assertEqual(self.store.read(self.state.period).revision, 0)

    def test_disabled_or_legacy_cap_blocks_before_reserving(self):
        self.assertEqual(
            self.reserve("job:1:attempt:1", policy=replace(self.policy, enabled=False)).reason,
            "MONTHLY_POLICY_DISABLED",
        )
        self.assertEqual(
            self.reserve("job:2:attempt:1", snapshot=CostSnapshot(5, 0)).reason,
            "GLOBAL_DAILY_BUDGET_REACHED",
        )
        self.assertEqual(self.store.read(self.state.period).reservations, ())

    def test_malformed_persistent_snapshot_blocks_without_recreating_month(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE monthly_budget_state SET state_sha256='0' WHERE period=?",
                         (self.state.period,))
        failure = self.reserve("job:1:attempt:1")
        self.assertFalse(failure.committed)
        self.assertFalse(failure.dispatch_authorized)
        self.assertEqual(failure.reason, "MONTHLY_STORAGE_INTEGRITY_FAILURE")
        with self.assertRaises(ValueError):
            self.store.read(self.state.period)


if __name__ == "__main__":
    unittest.main()
