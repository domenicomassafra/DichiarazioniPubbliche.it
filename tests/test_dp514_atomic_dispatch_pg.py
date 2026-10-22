"""DP-514: PostgreSQL USD/EUR/quota admission at the live queue interface.

All provider costs, approval receipts and quota samples are synthetic.
A fresh throwaway PostgreSQL cluster is created by the existing DP-512 fixture.
"""
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests import test_dp512_worker_budget_reservations as _pg_fixture

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/20261022-add-atomic-monthly-dispatch.sql"


class MonthlyDispatchPgTests(unittest.TestCase):
    exec_sql = _pg_fixture.WorkerBudgetReservationPgTests.exec_sql
    reserve = _pg_fixture.WorkerBudgetReservationPgTests.reserve
    scalar = _pg_fixture.WorkerBudgetReservationPgTests.scalar

    @classmethod
    def setUpClass(cls):
        _pg_fixture.WorkerBudgetReservationPgTests.setUpClass.__func__(cls)
        try:
            cls.exec_sql(cls.dsn, MIGRATION.read_text())
        except BaseException:
            _pg_fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__(cls)
            raise

    @classmethod
    def tearDownClass(cls):
        _pg_fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__(cls)

    def setUp(self):
        _pg_fixture.WorkerBudgetReservationPgTests.setUp(self)
        # This class tests a missing policy by clearing the synthetic default.
        self.exec_sql(self.dsn, """
            TRUNCATE dp514_monthly_dispatch_reservation,
                     dp514_monthly_dispatch_policy;
        """)

    def approve_fixture(self, *, cap="0.300000", quota=2, days=1,
                        fx="1.00000000", active="true", provider="provider:test",
                        fx_asof="current_date"):
        self.exec_sql(self.dsn, f"""
            INSERT INTO dp514_monthly_dispatch_policy(
                period,policy_version,accounting_tz,cap_eur,eur_per_usd,
                fx_source,fx_asof,provider_id,quota_remaining_attempts,
                quota_valid_until,quota_evidence_ref,approval_ref,active
            ) VALUES(
                to_char(now() AT TIME ZONE 'Europe/Rome','YYYY-MM'),
                'fixture-version-1','Europe/Rome',{cap},{fx},
                'TEST_SYNTHETIC',{fx_asof},'{provider}',{quota},
                now()+interval '{days} days',
                'TEST_SYNTHETIC_QUOTA','TEST_SYNTHETIC_APPROVAL',{active}
            );
        """)

    def test_unapproved_monthly_policy_blocks_paid_dispatch(self):
        self.assertEqual(self.reserve(1), "MONTHLY_POLICY_UNAVAILABLE")
        self.assertEqual(self.scalar("SELECT count(*) FROM worker_budget_reservation"), "0")

    def test_disabled_policy_and_missing_provider_quota_fail_closed(self):
        self.approve_fixture(active="false")
        self.assertEqual(self.reserve(1), "MONTHLY_POLICY_UNATTESTED")
        self.assertEqual(self.scalar("SELECT count(*) FROM worker_budget_reservation"), "0")

    def test_concurrent_eur_cap_is_atomic_across_workers(self):
        self.approve_fixture(cap="0.300000")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda number: self.reserve(number, global_cap="1.000000"), (1, 2)
            ))
        self.assertCountEqual(results, ["RESERVED", "MONTHLY_EUR_BUDGET_REACHED"])
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM dp514_monthly_dispatch_reservation"), "1")
        self.assertEqual(self.scalar(
            "SELECT sum(upper_bound_eur) FROM dp514_monthly_dispatch_reservation"),
            "0.200000")

    def test_replay_receipt_and_restart_keep_full_month_exposure(self):
        self.approve_fixture()
        self.assertEqual(self.reserve(1, global_cap="1.000000"), "RESERVED")
        self.assertEqual(self.reserve(1, global_cap="1.000000"),
                         "BUDGET_RESERVATION_REPLAY_HELD")
        self.store.record_receipt(
            job_id="job:1", content_id="content:test",
            provider_id="provider:test", model_id="model:test",
            operation="CLAIM_EXTRACT", request_id="request:test",
            input_bytes=10, input_seconds=None, estimated_cost_usd=0.1,
            status="SUCCESS", receipt={"synthetic": True}, request_key="replay",
            billing_basis="ESTIMATED_ONLY",
        )
        # A smaller/unmatched provisional receipt cannot clear its hold.
        # The receipt ledger conservatively classifies the mismatch UNKNOWN.
        self.assertEqual(self.reserve(2, global_cap="1.000000"),
                         "UNKNOWN_BILLING_LIABILITY_HELD")
        self.assertEqual(self.scalar(
            "SELECT sum(upper_bound_eur) FROM dp514_monthly_dispatch_reservation"),
            "0.200000")

    def test_provider_quota_and_usd_daily_guard_both_remain_restrictive(self):
        self.approve_fixture(cap="2.000000", quota=1)
        self.assertEqual(self.reserve(1, global_cap="1.000000"), "RESERVED")
        self.assertEqual(self.reserve(2, global_cap="1.000000"), "PROVIDER_QUOTA_REACHED")
        self.exec_sql(self.dsn, """
            TRUNCATE dp514_monthly_dispatch_reservation,
                     dp514_monthly_dispatch_policy CASCADE;
            DELETE FROM worker_budget_reservation;
        """)
        self.approve_fixture(cap="2.000000", quota=4)
        self.assertEqual(self.reserve(1), "RESERVED")
        self.assertEqual(self.reserve(2), "GLOBAL_DAILY_BUDGET_REACHED")

    def test_expired_quota_and_wrong_provider_cannot_dispatch(self):
        self.approve_fixture(days=-1)
        self.assertEqual(self.reserve(1), "PROVIDER_QUOTA_EVIDENCE_EXPIRED")
        self.assertEqual(self.scalar("SELECT count(*) FROM worker_budget_reservation"), "0")

    def test_provider_mismatch_and_stale_fx_hold_without_usd_reservation(self):
        self.approve_fixture(provider="provider:other")
        self.assertEqual(self.reserve(1), "PROVIDER_QUOTA_UNATTESTED")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM worker_budget_reservation"), "0")

    def test_provider_quota_reset_does_not_release_project_month_eur(self):
        self.approve_fixture(cap="0.300000", quota=50)
        self.assertEqual(self.reserve(1, global_cap="1.000000"), "RESERVED")
        # Even a later provider window with plentiful attempts cannot clear
        # the existing project's EUR month hold.
        self.assertEqual(self.reserve(2, global_cap="1.000000"),
                         "MONTHLY_EUR_BUDGET_REACHED")

    def test_out_of_band_receipt_and_prior_day_hold_fail_closed(self):
        self.approve_fixture(cap="1.000000")
        self.exec_sql(self.dsn, """
            INSERT INTO provider_receipt(
                id,provider_id,operation,billing_basis,status,estimated_cost_usd
            ) VALUES('external:test','provider:test','ASR',
                     'ESTIMATED_ONLY','SUCCESS',0.1);
        """)
        self.assertEqual(self.reserve(1, global_cap="1.000000"),
                         "UNKNOWN_BILLING_LIABILITY_HELD")

    def test_policy_is_immutable_and_pins_fx_version(self):
        self.approve_fixture(cap="1.000000", fx="0.80000000")
        self.assertEqual(self.reserve(1, global_cap="1.000000"), "RESERVED")
        self.assertEqual(self.scalar("""
            SELECT upper_bound_eur || ':' || policy_version
            FROM dp514_monthly_dispatch_reservation
        """), "0.160000:fixture-version-1")
        with self.assertRaises(Exception):
            self.exec_sql(self.dsn, """
                UPDATE dp514_monthly_dispatch_policy SET cap_eur=10;
            """)

    def test_dst_calendar_month_is_separate_from_utc_quota_clock(self):
        self.assertEqual(self.scalar("""
            SELECT to_char('2026-10-31 23:15:00+00'::timestamptz
                    AT TIME ZONE 'Europe/Rome','YYYY-MM') || ':' ||
                   to_char('2026-10-31 23:15:00+00'::timestamptz
                    AT TIME ZONE 'UTC','YYYY-MM')
        """), "2026-11:2026-10")


if __name__ == "__main__":
    unittest.main()
