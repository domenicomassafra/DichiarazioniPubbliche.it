"""DP-514: disposable SQLite contention proof, never a paid dispatch gate."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
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
    MonthlySettlementObservation,
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

    def observation(self, attempt="job:1:attempt:1", *, event="event:one",
                    amount="0.10", status="REPORTED_UNVERIFIED"):
        return MonthlySettlementObservation(
            observation_id=event, attempt_id=attempt,
            operation="CLAIM_EXTRACT", status=status,
            reported_cost_usd=(None if amount is None else Decimal(amount)),
            source_reference=("synthetic-usage:1" if status == "REPORTED_UNVERIFIED" else None),
            source_sha256=("a" * 64 if status == "REPORTED_UNVERIFIED" else None),
            observed_at=self.now + timedelta(minutes=1),
        )

    def reconcile(self, observation, *, store=None, policy=None):
        return (store or self.store).reconcile(
            policy=policy or self.policy, period=self.state.period,
            observation=observation,
        )

    def test_reported_usd_observation_is_provisional_and_never_releases_budget(self):
        attempt = "job:1:attempt:1"
        self.assertTrue(self.reserve(attempt).committed)
        result = self.reconcile(self.observation(attempt))
        self.assertTrue(result.committed)
        self.assertEqual(result.reason, "MONTHLY_OBSERVATION_RECORDED")
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.invoice_attested)
        self.assertEqual(result.receipt.status, "PROVISIONAL_HELD")
        self.assertEqual(result.receipt.provisional_eur, Decimal("0.090000"))
        restarted = SQLiteMonthlyReservationStore(self.path)
        replay = self.reconcile(self.observation(attempt), store=restarted)
        self.assertFalse(replay.committed)
        self.assertEqual(replay.reason, "MONTHLY_OBSERVATION_ALREADY_RECORDED")
        self.assertEqual(replay.receipt, result.receipt)
        saved = restarted.read(self.state.period)
        self.assertEqual(saved.revision, 2)
        self.assertEqual(saved.held_total_eur, Decimal("0.180000"))
        self.assertEqual(saved.settled_eur, Decimal("0"))
        report = restarted.reconciliation_report(self.state.period)
        self.assertEqual(report.provisional_observed_eur, Decimal("0.090000"))
        self.assertEqual(report.held_total_eur, Decimal("0.180000"))
        self.assertEqual(report.unknown_attempts, 0)
        self.assertFalse(report.invoice_attested)
        self.assertFalse(report.dispatch_authorized)
        self.assertEqual(self.reserve("job:2:attempt:1").reason, "MONTHLY_CAP_REACHED")

    def test_unknown_source_cost_is_persisted_and_blocks_new_reservations(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        unknown = self.observation(status="UNKNOWN", amount=None)
        result = self.reconcile(unknown)
        self.assertTrue(result.committed)
        self.assertEqual(result.receipt.status, "UNKNOWN_HELD")
        self.assertIsNone(result.receipt.provisional_eur)
        self.assertTrue(SQLiteMonthlyReservationStore(self.path).read(self.state.period).unknown_liability)
        self.assertEqual(self.reserve("job:2:attempt:1").reason, "MONTHLY_UNKNOWN_LIABILITY")
        report = self.store.reconciliation_report(self.state.period)
        self.assertEqual(report.unknown_attempts, 1)
        self.assertIsNone(report.authoritative_billed_eur)
        self.assertEqual(report.held_total_eur, Decimal("0.180000"))

    def test_over_bound_report_freezes_month_instead_of_bypassing_cap(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        result = self.reconcile(self.observation(amount="0.25"))
        self.assertTrue(result.committed)
        self.assertEqual(result.receipt.status, "OVER_BOUND_HELD")
        self.assertEqual(result.receipt.provisional_eur, Decimal("0.225000"))
        report = self.store.reconciliation_report(self.state.period)
        self.assertEqual(report.over_bound_attempts, 1)
        self.assertTrue(report.unknown_liability)
        self.assertEqual(self.reserve("job:2:attempt:1").reason, "MONTHLY_UNKNOWN_LIABILITY")
        self.assertEqual(self.store.read(self.state.period).committed_total_eur, Decimal("0.180000"))

    def test_negative_refund_forged_scope_and_changed_replays_fail_closed(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        with self.assertRaisesRegex(ValueError, "MONTHLY_OBSERVATION_COST_INVALID"):
            self.observation(amount="-0.01")
        missing = self.reconcile(self.observation(attempt="job:missing:attempt:1"))
        self.assertFalse(missing.committed)
        self.assertEqual(missing.reason, "MONTHLY_RESERVATION_NOT_FOUND")
        altered_operation = replace(self.observation(), operation="OTHER_OPERATION")
        self.assertEqual(self.reconcile(altered_operation).reason, "MONTHLY_ATTEMPT_ID_CONFLICT")
        first = self.reconcile(self.observation())
        self.assertTrue(first.committed)
        changed = self.reconcile(self.observation(amount="0.09"))
        self.assertFalse(changed.committed)
        self.assertEqual(changed.reason, "MONTHLY_OBSERVATION_CONFLICT")
        self.assertFalse(changed.dispatch_authorized)
        self.assertEqual(self.store.read(self.state.period).revision, 2)
        self.assertEqual(self.reconcile(self.observation(), policy=replace(
            self.policy, cap_eur=Decimal("5"))).reason, "MONTHLY_STORED_POLICY_MISMATCH")

    def test_concurrent_identical_settlement_replays_once_across_connections(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        gate = Barrier(2)

        def writer():
            gate.wait(timeout=5)
            return self.reconcile(self.observation(),
                                  store=SQLiteMonthlyReservationStore(self.path))

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result() for f in (pool.submit(writer), pool.submit(writer))]
        self.assertEqual(sum(item.committed for item in results), 1)
        self.assertCountEqual((item.reason for item in results), (
            "MONTHLY_OBSERVATION_RECORDED", "MONTHLY_OBSERVATION_ALREADY_RECORDED"))
        self.assertTrue(all(not item.dispatch_authorized for item in results))
        self.assertEqual(SQLiteMonthlyReservationStore(self.path).read(self.state.period).revision, 2)
        self.assertEqual(self.store.reconciliation_report(self.state.period).observed_attempts, 1)

    def test_concurrent_disagreeing_settlement_sources_never_overwrite_winner(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        gate = Barrier(2)

        def writer(amount):
            gate.wait(timeout=5)
            separate = SQLiteMonthlyReservationStore(self.path)
            return self.reconcile(self.observation(amount=amount), store=separate)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result() for f in (pool.submit(writer, "0.10"),
                                             pool.submit(writer, "0.12"))]
        self.assertEqual(sum(item.committed for item in results), 1)
        self.assertCountEqual((item.reason for item in results), (
            "MONTHLY_OBSERVATION_RECORDED", "MONTHLY_OBSERVATION_CONFLICT"))
        report = self.store.reconciliation_report(self.state.period)
        self.assertIn(report.provisional_observed_eur,
                      (Decimal("0.090000"), Decimal("0.108000")))
        self.assertEqual(report.observed_attempts, 1)
        self.assertEqual(report.held_total_eur, Decimal("0.180000"))
        self.assertEqual(self.store.read(self.state.period).revision, 2)

    def test_late_next_month_observation_never_resets_original_month(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        late = replace(self.observation(),
                       observed_at=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
        self.assertEqual(monthly_period(late.observed_at, "Europe/Rome"),
                         "2026-11@Europe/Rome")
        recorded = self.reconcile(late)
        self.assertTrue(recorded.committed)
        self.assertEqual(recorded.receipt.period, "2026-10@Europe/Rome")
        self.assertEqual(recorded.receipt.provisional_eur, Decimal("0.090000"))
        self.assertEqual(self.store.read(self.state.period).held_total_eur,
                         Decimal("0.180000"))
        self.assertEqual(self.store.reconciliation_report(self.state.period).observed_attempts, 1)

    def test_unverified_zero_usage_is_not_a_refund_or_zero_marginal_invoice(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        recorded = self.reconcile(self.observation(amount="0"))
        self.assertTrue(recorded.committed)
        self.assertEqual(recorded.receipt.status, "PROVISIONAL_HELD")
        self.assertEqual(recorded.receipt.provisional_eur, Decimal("0.000000"))
        self.assertEqual(self.store.reconciliation_report(self.state.period).held_total_eur,
                         Decimal("0.180000"))
        self.assertEqual(self.reserve("job:2:attempt:1").reason, "MONTHLY_CAP_REACHED")

    def test_distinct_settlement_receipt_id_cannot_be_reused_for_other_attempt(self):
        wider = replace(self.policy, cap_eur=Decimal("0.50"))
        separate = SQLiteMonthlyReservationStore(Path(self.temp.name) / "wide.sqlite3")
        separate.initialize()
        self.assertTrue(separate.bootstrap(wider, self.state))
        self.assertTrue(self.reserve("job:1:attempt:1", store=separate, policy=wider).committed)
        self.assertTrue(self.reserve("job:2:attempt:1", store=separate, policy=wider).committed)
        self.assertTrue(self.reconcile(self.observation(), store=separate, policy=wider).committed)
        collision = self.reconcile(self.observation(
            attempt="job:2:attempt:1"), store=separate, policy=wider)
        self.assertEqual(collision.reason, "MONTHLY_OBSERVATION_ID_CONFLICT")
        self.assertEqual(separate.read(self.state.period).revision, 3)

    def test_tampered_settlement_receipt_fails_integrity_read_and_replay(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        self.assertTrue(self.reconcile(self.observation()).committed)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE monthly_reconciliation_receipt SET receipt_sha256 = '0'")
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("DROP TRIGGER monthly_reconciliation_receipt_no_update")
            conn.execute("UPDATE monthly_reconciliation_receipt SET receipt_sha256='0'")
        with self.assertRaises(ValueError):
            self.store.reconciliation_report(self.state.period)
        failed = self.reconcile(self.observation())
        self.assertEqual(failed.reason, "MONTHLY_STORAGE_INTEGRITY_FAILURE")

    def test_insert_abort_rolls_back_revision_and_does_not_poison_retry(self):
        self.assertTrue(self.reserve("job:1:attempt:1").committed)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("""
                CREATE TRIGGER synthetic_reconciliation_abort
                BEFORE INSERT ON monthly_reconciliation_receipt
                BEGIN SELECT RAISE(ABORT, 'synthetic post-CAS write failure'); END
            """)
        failed = self.reconcile(self.observation())
        self.assertFalse(failed.committed)
        self.assertFalse(failed.dispatch_authorized)
        self.assertEqual(failed.reason, "MONTHLY_STORAGE_UNAVAILABLE")
        self.assertEqual(self.store.read(self.state.period).revision, 1)
        self.assertEqual(self.store.reconciliation_report(self.state.period).observed_attempts, 0)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("DROP TRIGGER synthetic_reconciliation_abort")
        restarted = SQLiteMonthlyReservationStore(self.path)
        restarted.initialize()  # additive/idempotent initialization does not wipe receipts
        self.assertTrue(self.reconcile(self.observation(), store=restarted).committed)
        self.assertEqual(restarted.reconciliation_report(self.state.period).observed_attempts, 1)
        self.assertEqual(restarted.read(self.state.period).revision, 2)

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
        with closing(sqlite3.connect(self.path)) as conn, conn:
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
