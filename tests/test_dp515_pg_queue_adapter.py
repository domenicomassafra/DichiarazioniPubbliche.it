"""#370: real disposable PostgreSQL, watcher CAS plus held canonical job."""
import unittest
import socket
import os
from unittest.mock import patch
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests import test_dp512_worker_budget_reservations as fixture
from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchObservation, WatchPolicy, WatchReadiness, WatchState, policy_fingerprint,
)
from dichiarazioni_pubbliche.source_watch_pg_queue_adapter import PostgresSourceWatchStore

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/20261025-add-dp515-watch-pg.sql"
MODIFIED = "Fri, 09 Oct 2026 08:00:00 GMT"


class PostgresWatchQueueTests(unittest.TestCase):
    exec_sql = fixture.WorkerBudgetReservationPgTests.exec_sql
    scalar = fixture.WorkerBudgetReservationPgTests.scalar

    @staticmethod
    def _pg_command(args):
        # macOS Homebrew PostgreSQL can become multithreaded without LC_ALL.
        with patch.dict(os.environ, {"LC_ALL": "C"}):
            return fixture._cmd(args)

    @classmethod
    def setUpClass(cls):
        # Reuse the DP-512 disposable PG fixture schema with a small cluster
        # so concurrent Studio PostgreSQL suites do not exhaust shared memory.
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp515-pg-queue-")
        cls.data = Path(cls.tmp.name) / "pg"
        cls.started = False
        log = Path(cls.tmp.name) / "pg.log"
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                cls.port = sock.getsockname()[1]
            cls._pg_command([
                fixture._bin("initdb"), "-D", str(cls.data),
                "--username=postgres", "--auth=trust",
                "--no-locale", "--encoding=UTF8",
            ])
            try:
                cls._pg_command([
                    fixture._bin("pg_ctl"), "-D", str(cls.data), "-l", str(log),
                    "-o", (f"-F -p {cls.port} -h 127.0.0.1 "
                           f"-k {cls.tmp.name} -c shared_buffers=8MB "
                           "-c max_connections=10"),
                    "-w", "start",
                ])
            except RuntimeError as exc:
                raise RuntimeError(
                    str(exc) + "\nTemporary PG log: " +
                    (log.read_text()[-3000:] if log.exists() else "(missing)")
                ) from exc
            cls.started = True
            admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            cls.exec_sql(admin, "CREATE DATABASE dp515_test_queue;")
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp515_test_queue"
            cls.exec_sql(cls.dsn, (ROOT / "db/schema.v1.sql").read_text())
            cls.exec_sql(cls.dsn, (ROOT / "db/job_queue.v1.sql").read_text())
            cls.exec_sql(cls.dsn, (ROOT / "db/migrations/20261016-add-worker-budget-reservations.sql").read_text())
            cls.exec_sql(cls.dsn, (ROOT / "db/migrations/20261022-add-atomic-monthly-dispatch.sql").read_text())
            cls.exec_sql(cls.dsn, MIGRATION.read_text())
        except BaseException:
            fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__(cls)
            raise

    @classmethod
    def tearDownClass(cls):
        fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        # One disposable database per case: rights records are append-only.
        case_database = "dp515_case_" + self._testMethodName[-32:].replace("_", "")[:30]
        self.exec_sql(
            self.dsn, "SELECT 1;"
        )
        admin = f"postgresql://postgres@127.0.0.1:{self.port}/postgres"
        self.exec_sql(admin, f"CREATE DATABASE {case_database} TEMPLATE dp515_test_queue;")
        self.dsn = f"postgresql://postgres@127.0.0.1:{self.port}/{case_database}"
        fixture.WorkerBudgetReservationPgTests.setUp(self)
        self.exec_sql(self.dsn, """
            INSERT INTO private_source_rights_record
                (id,subject_fingerprint,source_family,locator_kind,locator_value,
                 content_id,rights_status,rights_receipt_ref,permitted_uses,
                 policy_version,reviewed_at,reviewer_ref,expires_at)
            VALUES ('rights:test',repeat('a',64),'OFFICIAL_RSS','URL',
                    'https://example.test/test','content:test','CLEARED',
                    'fixture:rights:approved',ARRAY['FETCH'],'fixture',
                    now(),'fixture:reviewer',now()+interval '1 day');
        """)
        self.store = PostgresSourceWatchStore(self.dsn)
        self.p = WatchPolicy(
            source_id="source:test", locator_id="https://example.test/test",
            source_family="OFFICIAL_RSS", corpus_id="corpus:private",
            corpus_cutoff="2026-10-01", policy_revision="fixture-r1",
            enabled=True,
        )
        self.state = WatchState(
            source_id=self.p.source_id,
            policy_fingerprint=policy_fingerprint(self.p), revision=3,
            etag='"old"', content_sha256="a"*64,
            source_version="v1", last_modified=MODIFIED,
            last_attempted_at=self.now-timedelta(days=1),
            last_successful_observed_at=self.now-timedelta(days=1),
            last_attempt_id="previous",
        )
        self.gate = self.gates()
        self.store.register_source(self.p, self.state, self.gate, content_id="content:test")

    def gates(self, **changes):
        values = dict(
            source_id=self.p.source_id, policy_fingerprint=policy_fingerprint(self.p),
            corpus_id=self.p.corpus_id, rights_status="READY",
            rights_receipt="rights:test", capability_status="READY",
            capability_receipt="fixture:capability:source:test",
            budget_status="READY", budget_receipt="TEST_APPROVAL",
            remaining_children=1,
        )
        return WatchReadiness(**(values | changes))

    def observation(self, *, at=None, digest="b"*64, version="v2", etag='"new"'):
        return WatchObservation(
            observed_at=at or self.now+timedelta(seconds=2), status_code=200,
            content_sha256=digest, source_version=version,
            last_modified=MODIFIED, etag=etag,
        )

    def begin(self, attempt="attempt:1", at=None, lease_seconds=60):
        return self.store.begin_poll(
            self.p.source_id, attempt_id=attempt, attempted_at=at or self.now,
            lease_seconds=lease_seconds,
        )

    def commit(self, attempt="attempt:1", obs=None):
        return self.store.commit_observation(
            self.p.source_id, attempt_id=attempt,
            observation=obs or self.observation(),
        )

    def jobs(self):
        return self.scalar(
            "SELECT count(*) FROM processing_job "
            "WHERE job_type='SOURCE_REVALIDATION_REVIEW'"
        )

    def test_changed_enqueues_one_held_canonical_job_and_replay_is_exact(self):
        self.assertTrue(self.begin().allowed)
        result = self.commit()
        self.assertEqual(result.disposition, "CHANGED")
        self.assertEqual(self.jobs(), "1")
        self.assertEqual(self.scalar(
            "SELECT state FROM processing_job "
            "WHERE job_type='SOURCE_REVALIDATION_REVIEW'"
        ), "BLOCKED")
        self.assertEqual(PostgresSourceWatchStore(self.dsn).commit_observation(
            self.p.source_id, attempt_id="attempt:1", observation=self.observation()
        ), result)
        self.assertEqual(self.jobs(), "1")
        self.assertEqual(self.store.read_state(self.p.source_id), result.next_state)
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.commit(obs=self.observation(digest="c"*64))

    def test_two_workers_only_one_lease_and_crash_restart_expiration(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    PostgresSourceWatchStore(self.dsn).begin_poll,
                    self.p.source_id, attempt_id=f"attempt:{n}",
                    attempted_at=self.now, lease_seconds=120,
                )
                for n in (1, 2)
            ]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(future.result())
                except ValueError as exc:
                    outcomes.append(str(exc))
        self.assertEqual(sum(isinstance(x, str) for x in outcomes), 1)
        winner = next(x for x in outcomes if not isinstance(x, str))
        self.assertTrue(winner.allowed)
        self.assertEqual(self.jobs(), "0")
        # Simulate an expired server-side lease without trusting a future
        # caller-supplied clock to expire an active reservation.
        self.exec_sql(self.dsn, """
            UPDATE dp515_watch_attempt
            SET lease_expires_at=clock_timestamp()-interval '1 second'
            WHERE source_id='source:test' AND status='IN_FLIGHT';
        """)
        PostgresSourceWatchStore(self.dsn).expire_stale_attempt(
            self.p.source_id, attempt_id=winner.attempt_id,
            as_of=datetime.now(timezone.utc), expected_state_revision=3,
            expected_gate_revision=0,
        )
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT|LEASE"):
            self.store.commit_observation(
                self.p.source_id, attempt_id=winner.attempt_id,
                observation=self.observation(),
            )
        self.assertTrue(self.begin("attempt:after-crash", self.now+timedelta(seconds=3)).allowed)

    def test_revocation_at_commit_holds_prior_version_and_zero_jobs(self):
        self.begin()
        self.store.update_readiness(
            self.gates(rights_status="REVOKED"), expected_gate_revision=0
        )
        result = self.commit()
        self.assertEqual(result.disposition, "BLOCKED")
        self.assertEqual(self.jobs(), "0")
        self.assertEqual(self.store.read_state(self.p.source_id).content_sha256, "a"*64)

    def test_cas_lost_on_ready_gate_epoch_change_preserves_prior_state(self):
        self.begin()
        self.assertEqual(
            self.store.update_readiness(self.gates(), expected_gate_revision=0), 1
        )
        with self.assertRaisesRegex(ValueError, "GATE_CHANGED"):
            self.commit()
        self.assertEqual(self.store.read_state(self.p.source_id), self.state)
        self.assertEqual(self.jobs(), "0")

    def test_unattested_receipt_does_not_admit_even_if_gate_says_ready(self):
        self.store.update_readiness(
            self.gates(rights_receipt="fixture:not-in-registry"),
            expected_gate_revision=0,
        )
        self.assertEqual(self.begin().reason, "RIGHTS_NOT_READY")
        self.assertEqual(self.jobs(), "0")

    def test_authoritative_rights_unknown_or_budget_cap_holds_without_state_change(self):
        self.store.update_readiness(
            self.gates(rights_status="UNKNOWN"), expected_gate_revision=0
        )
        self.assertFalse(self.begin().allowed)
        self.assertEqual(self.jobs(), "0")
        self.assertEqual(self.store.read_state(self.p.source_id), self.state)
        self.store.update_readiness(self.gates(), expected_gate_revision=1)
        self.exec_sql(self.dsn, "TRUNCATE dp514_monthly_dispatch_reservation, dp514_monthly_dispatch_policy;")
        self.assertFalse(self.begin().allowed)
        self.assertEqual(self.jobs(), "0")

    def test_exhausted_monthly_eur_cap_holds_even_with_ready_label(self):
        self.exec_sql(self.dsn, """
            INSERT INTO worker_budget_reservation
                (job_id,attempt,content_id,source_id,upper_bound_usd)
            VALUES('job:1',0,'content:test','source:test',10);
            INSERT INTO dp514_monthly_dispatch_reservation
                (job_id,attempt,period,policy_version,provider_id,
                 upper_bound_eur,pinned_eur_per_usd)
            VALUES ('job:1',0,to_char(now() AT TIME ZONE 'Europe/Rome','YYYY-MM'),
                    'dp512-fixture-v1','provider:test',10,1);
        """)
        self.assertEqual(self.begin().reason, "BUDGET_NOT_READY")
        self.assertEqual(self.jobs(), "0")
        self.assertEqual(self.store.read_state(self.p.source_id), self.state)

    def test_unknown_provider_liability_holds_without_watch_job(self):
        self.exec_sql(self.dsn, """
            INSERT INTO provider_receipt(
                id,provider_id,operation,billing_basis,status,
                estimated_cost_usd)
            VALUES('receipt:outside','provider:test','ASR',
                   'ESTIMATED_ONLY','SUCCESS',0.1);
        """)
        self.assertEqual(self.begin().reason, "BUDGET_NOT_READY")
        self.assertEqual(self.jobs(), "0")
        self.assertEqual(self.store.read_state(self.p.source_id), self.state)

    def test_cas_lost_and_out_of_band_revoke_cannot_create_job(self):
        self.begin()
        self.exec_sql(self.dsn, """
            INSERT INTO private_source_rights_record(
                id,subject_fingerprint,source_family,locator_kind,locator_value,
                content_id,rights_status,rights_receipt_ref,permitted_uses,
                policy_version,reviewed_at,reviewer_ref,supersedes_id)
            VALUES('rights:revoked',repeat('a',64),'OFFICIAL_RSS','URL',
                   'https://example.test/test','content:test','REVOKED',
                   'fixture:revoked',ARRAY[]::text[],'fixture',now(),
                   'fixture:reviewer','rights:test');
        """)
        with self.assertRaisesRegex(ValueError, "RIGHTS_NOT_READY|GATE_CHANGED"):
            self.commit()
        self.assertEqual(self.jobs(), "0")
        self.assertEqual(self.store.read_state(self.p.source_id), self.state)

    def test_failure_between_version_and_enqueue_rolls_back_everything(self):
        self.begin()
        self.exec_sql(self.dsn, """
            CREATE OR REPLACE FUNCTION dp515_fixture_fail_job()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'FIXTURE_ENQUEUE_FAILURE'; END $$;
            CREATE TRIGGER dp515_fixture_fail_job_trg
            BEFORE INSERT ON processing_job FOR EACH ROW
            WHEN (NEW.job_type='SOURCE_REVALIDATION_REVIEW')
            EXECUTE FUNCTION dp515_fixture_fail_job();
        """)
        try:
            with self.assertRaises(Exception):
                self.commit()
            self.assertEqual(self.jobs(), "0")
            self.assertEqual(self.store.read_state(self.p.source_id), self.state)
        finally:
            self.exec_sql(self.dsn, """
                DROP TRIGGER dp515_fixture_fail_job_trg ON processing_job;
                DROP FUNCTION dp515_fixture_fail_job();
            """)
        self.assertEqual(self.commit().disposition, "CHANGED")
        self.assertEqual(self.jobs(), "1")

    def test_unchanged_304_and_etag_collision_never_enqueue(self):
        self.begin()
        unchanged = WatchObservation(
            observed_at=self.now+timedelta(seconds=2), status_code=304,
        )
        self.assertEqual(self.commit(obs=unchanged).disposition, "UNCHANGED")
        self.assertEqual(self.jobs(), "0")
        self.assertTrue(self.begin("attempt:2", self.now+timedelta(seconds=5)).allowed)
        collision = self.observation(at=self.now+timedelta(seconds=6), etag='"old"')
        result = self.commit("attempt:2", collision)
        self.assertEqual((result.disposition, result.reason),
                         ("UNAVAILABLE", "ETAG_CONTENT_CONFLICT"))
        self.assertEqual(self.jobs(), "0")


if __name__ == "__main__":
    unittest.main()
