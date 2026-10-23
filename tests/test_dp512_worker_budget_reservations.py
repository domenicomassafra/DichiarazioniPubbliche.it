"""DP-512.5: real PostgreSQL cross-worker reservation, no provider calls."""

import socket
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from tests.test_claim_evidence_retrieval_replay import _bin, _cmd  # noqa: E402
from dichiarazioni_pubbliche.health_digest import build_health_digest  # noqa: E402
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402
from dichiarazioni_pubbliche.scheduler_daemon import PsqlStore  # noqa: E402


class WorkerBudgetReservationPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ("initdb", "pg_ctl", "psql"):
            _bin(name)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp512-worker-budget-")
        cls.data = Path(cls.tmp.name) / "pg"
        cls.started = False
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                cls.port = sock.getsockname()[1]
            _cmd([_bin("initdb"), "-D", str(cls.data), "--username=postgres",
                  "--auth=trust", "--no-locale", "--encoding=UTF8"])
            _cmd([_bin("pg_ctl"), "-D", str(cls.data),
                  "-l", str(Path(cls.tmp.name) / "pg.log"),
                  "-o", f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}",
                  "-w", "start"])
            cls.started = True
            admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            cls.exec_sql(admin, "CREATE DATABASE dp512_test_worker_budget;")
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp512_test_worker_budget"
            cls.exec_sql(cls.dsn, (ROOT / "db" / "schema.v1.sql").read_text())
            cls.exec_sql(cls.dsn, (ROOT / "db" / "job_queue.v1.sql").read_text())
            cls.exec_sql(cls.dsn, (
                ROOT / "db" / "migrations" /
                "20261016-add-worker-budget-reservations.sql"
            ).read_text())
            cls.exec_sql(cls.dsn, (
                ROOT / "db/migrations/20261022-add-atomic-monthly-dispatch.sql"
            ).read_text())
            cls.store = QueueRuntimeStore(cls.dsn)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def exec_sql(cls, dsn, sql):
        return _cmd([_bin("psql"), "-X", "-q", "-A", "-t",
                     "-v", "ON_ERROR_STOP=1", "-d", dsn], stdin=sql)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            _cmd([_bin("pg_ctl"), "-D", str(cls.data), "-m", "immediate", "-w", "stop"])
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def setUp(self):
        self.exec_sql(self.dsn, """
            SET client_min_messages TO warning;
            TRUNCATE dp514_monthly_dispatch_reservation,
                     dp514_monthly_dispatch_policy;
            DELETE FROM worker_budget_reservation;
            DELETE FROM provider_receipt;
            DELETE FROM processing_job;
            INSERT INTO source(id,canonical_name,source_type)
              VALUES('source:test','Source','TEST') ON CONFLICT DO NOTHING;
            INSERT INTO content_item(id,source_id,canonical_url)
              VALUES('content:test','source:test','https://example.test/test')
              ON CONFLICT DO NOTHING;
            INSERT INTO processing_job(id,content_id,job_type,state,
                                       lease_owner,lease_until,payload)
            SELECT 'job:' || n,'content:test','CLAIM_EXTRACT_WINDOW','RUNNING',
                   'worker:' || n,now()+interval '5 minutes',
                   '{"estimated_cost_usd":0.2,"provider_id":"provider:test"}'::jsonb
            FROM generate_series(1,4) n;
            INSERT INTO dp514_monthly_dispatch_policy(
                period,policy_version,accounting_tz,cap_eur,eur_per_usd,
                fx_source,fx_asof,provider_id,quota_remaining_attempts,
                quota_valid_until,quota_evidence_ref,approval_ref,active
            ) VALUES(
                to_char(now() AT TIME ZONE 'Europe/Rome','YYYY-MM'),
                'dp512-fixture-v1','Europe/Rome',10,1,
                'TEST_SYNTHETIC',current_date,'provider:test',100,
                now()+interval '1 day',
                'TEST_QUOTA','TEST_APPROVAL',true
            );
        """)

    def reserve(self, number, amount="0.200000", global_cap="0.300000"):
        return QueueRuntimeStore(self.dsn).reserve_worker_budget(
            job_id=f"job:{number}", attempt=0, worker_id=f"worker:{number}",
            source_id="source:test", upper_bound_usd=amount,
            max_job_usd="0.250000", max_global_usd=global_cap,
            max_source_usd="0.300000", provider_id="provider:test",
        )

    def scalar(self, sql):
        return self.exec_sql(self.dsn, sql).strip()

    def health(self):
        with tempfile.TemporaryDirectory(prefix="dp512-health-") as tmp:
            return build_health_digest(
                self.store, private_root=Path(tmp),
                now=datetime.now(timezone.utc), max_cost_usd_per_day=0.3,
            )

    def test_parallel_worker_admission_is_one_atomic_reservation(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(self.reserve, (1, 2)))
        self.assertCountEqual(outcomes, (
            "RESERVED", "GLOBAL_DAILY_BUDGET_REACHED",
        ))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM worker_budget_reservation"
        ), "1")
        winning = 1 if outcomes[0] == "RESERVED" else 2
        self.assertEqual(self.reserve(winning), "BUDGET_RESERVATION_REPLAY_HELD")
        snapshot = self.store.cost_snapshot("source:test")
        self.assertAlmostEqual(snapshot.global_day_usd, 0.2)
        self.assertAlmostEqual(snapshot.source_day_usd, 0.2)
        scheduler = PsqlStore(self.dsn)
        self.assertAlmostEqual(scheduler.cost_today(), 0.2)
        self.assertAlmostEqual(scheduler.cost_today("source:test"), 0.2)
        health = self.health()
        self.assertEqual(health["billing_today"]["outstanding_reserved_upper_bound_usd"], 0.2)
        self.assertEqual(health["billing_today"]["outstanding_reserved_attempt_count"], 1)
        self.assertEqual(health["billing_today"]["budget_exposure_upper_bound_usd_today"], 0.2)
        statuses = {row["id"]: row["status"] for row in health["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "BREACH")

    def test_receipt_reconciles_without_double_debit(self):
        self.assertEqual(self.reserve(1), "RESERVED")
        self.store.record_receipt(
            job_id="job:1", content_id="content:test",
            provider_id="provider:test", model_id="model:test",
            operation="CLAIM_EXTRACT", request_id="request:test",
            input_bytes=10, input_seconds=None,
            estimated_cost_usd=0.2, status="SUCCESS",
            receipt={"fixture": True}, request_key="fixture",
            billing_basis="ESTIMATED_ONLY",
        )
        self.assertEqual(self.scalar(
            "SELECT state FROM worker_budget_reservation WHERE job_id='job:1'"
        ), "RECEIPTED")
        snapshot = self.store.cost_snapshot("source:test")
        self.assertAlmostEqual(snapshot.global_day_usd, 0.2)
        scheduler = PsqlStore(self.dsn)
        self.assertAlmostEqual(scheduler.cost_today(), 0.2)
        self.assertAlmostEqual(scheduler.cost_today("source:test"), 0.2)
        self.assertEqual(self.reserve(2), "GLOBAL_DAILY_BUDGET_REACHED")
        self.assertEqual(self.reserve(3, amount="0.100000"), "RESERVED")

    def test_receipt_commit_between_admission_reads_keeps_daily_cap(self):
        """A receipt changing RESERVED to RECEIPTED cannot vanish mid-preflight.

        The private fixture exposes the gap between the two SQL reads
        with a session advisory marker. No runtime migration is changed.
        """
        self.assertEqual(self.reserve(1), "RESERVED")
        migration_path = (
            ROOT / "db" / "migrations" /
            "20261016-add-worker-budget-reservations.sql"
        )
        migration = migration_path.read_text()
        marker = "    SELECT COALESCE(sum(h.upper_bound_usd),0),"
        self.assertEqual(migration.count(marker), 1)
        instrumented = migration.replace(
            marker,
            "    PERFORM pg_advisory_xact_lock(20261020, 514);\n"
            "    PERFORM pg_sleep(2);\n" + marker,
        ).replace("CREATE OR REPLACE FUNCTION reserve_worker_budget(",
                  "CREATE OR REPLACE FUNCTION reserve_worker_budget_usd(")
        original_usd = migration.replace(
            "CREATE OR REPLACE FUNCTION reserve_worker_budget(",
            "CREATE OR REPLACE FUNCTION reserve_worker_budget_usd("
        )
        self.exec_sql(self.dsn, instrumented)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                admission = pool.submit(self.reserve, 2)
                for _ in range(80):
                    observed = self.scalar("""
                        SELECT count(*) FROM pg_locks
                        WHERE locktype='advisory' AND classid=20261020
                          AND objid=514 AND granted;
                    """)
                    if observed == "1":
                        break
                    time.sleep(0.025)
                else:
                    self.fail("admission did not reach guarded interleaving")
                self.store.record_receipt(
                    job_id="job:1", content_id="content:test",
                    provider_id="provider:test", model_id="model:test",
                    operation="CLAIM_EXTRACT", request_id="request:test",
                    input_bytes=10, input_seconds=None,
                    estimated_cost_usd=0.2, status="SUCCESS",
                    receipt={"fixture": True}, request_key="race",
                    billing_basis="ESTIMATED_ONLY",
                )
                self.assertEqual(
                    admission.result(timeout=10), "GLOBAL_DAILY_BUDGET_REACHED"
                )
            self.assertEqual(self.scalar("""
                SELECT count(*) FROM worker_budget_reservation
                WHERE state='RECEIPTED';
            """), "1")
            self.assertEqual(self.store.cost_snapshot("source:test").global_day_usd, 0.2)
        finally:
            self.exec_sql(self.dsn, original_usd)

    def test_unreported_cost_and_old_unknown_fail_closed(self):
        self.assertEqual(self.reserve(1), "RESERVED")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM worker_budget_reservation WHERE state='RESERVED'"
        ), "1")
        self.exec_sql(self.dsn, """
          INSERT INTO provider_receipt(id,provider_id,operation,billing_basis,status)
            VALUES ('unpriced:1','external','ASR','UNKNOWN','FAILED');
        """)
        self.assertEqual(self.reserve(2), "UNKNOWN_BILLING_LIABILITY_HELD")
        self.assertEqual(self.store.cost_snapshot("source:test").global_day_usd,
                         float("inf"))
        scheduler = PsqlStore(self.dsn)
        self.assertEqual(scheduler.cost_today(), float("inf"))

    def test_prior_day_ambiguous_reservation_survives_midnight(self):
        self.assertEqual(self.reserve(1), "RESERVED")
        self.exec_sql(self.dsn, """
          UPDATE worker_budget_reservation
          SET reserved_at=now() - interval '2 days'
          WHERE job_id='job:1';
        """)
        self.assertEqual(self.reserve(2), "UNKNOWN_BILLING_LIABILITY_HELD")
        self.assertEqual(self.store.cost_snapshot("source:test").global_day_usd,
                         float("inf"))
        self.assertEqual(self.store.cost_snapshot("source:test").source_day_usd,
                         float("inf"))
        scheduler = PsqlStore(self.dsn)
        self.assertEqual(scheduler.cost_today(), float("inf"))
        self.assertEqual(scheduler.cost_today("source:test"), float("inf"))
        health = self.health()
        self.assertEqual(health["billing_today"]["prior_day_unreconciled_reservation_count"], 1)
        self.assertEqual(health["billing_today"]["outstanding_reserved_upper_bound_usd"], 0.0)
        statuses = {row["id"]: row["status"] for row in health["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_wrong_lease_or_attempt_does_not_reserve(self):
        self.assertEqual(self.reserve(1, amount="0.000000"),
                         "JOB_COST_CAP_REACHED")
        self.assertEqual(self.store.reserve_worker_budget(
            job_id="job:1", attempt=1, worker_id="worker:1",
            source_id="source:test", upper_bound_usd="0.2",
            max_job_usd="0.25", max_global_usd="1", max_source_usd="1",
            provider_id="provider:test",
        ), "BUDGET_JOB_LEASE_OR_SOURCE_INVALID")
        self.assertEqual(self.scalar("SELECT count(*) FROM worker_budget_reservation"), "0")


if __name__ == "__main__":
    unittest.main()
