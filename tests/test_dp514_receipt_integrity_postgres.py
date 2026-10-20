"""DP-514: receipt integrity and bounded PostgreSQL lock wait, no paid provider."""

import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests import test_dp512_worker_budget_reservations as fixture
from dichiarazioni_pubbliche.psql_command import execute_psql


class ReceiptIntegrityPgTests(fixture.WorkerBudgetReservationPgTests):
    """Exercise the real queue store against the inherited disposable PG cluster."""

    def receipt(self, *, content_id="content:test", request_key="first"):
        return self.store.record_receipt(
            job_id="job:1",
            content_id=content_id,
            provider_id="provider:test",
            model_id="model:test",
            operation="CLAIM_EXTRACT",
            request_id="request:test",
            input_bytes=10,
            input_seconds=None,
            estimated_cost_usd=0.2,
            status="SUCCESS",
            receipt={"synthetic": True},
            request_key=request_key,
            billing_basis="ESTIMATED_ONLY",
        )

    def test_foreign_content_cannot_release_original_source_hold(self):
        self.exec_sql(self.dsn, """
            INSERT INTO source(id,canonical_name,source_type)
              VALUES('source:foreign','Foreign','TEST') ON CONFLICT DO NOTHING;
            INSERT INTO content_item(id,source_id,canonical_url)
              VALUES('content:foreign','source:foreign','https://example.test/foreign')
              ON CONFLICT DO NOTHING;
        """)
        self.assertEqual(self.reserve(1, global_cap="1"), "RESERVED")
        with self.assertRaisesRegex(ValueError, "RECEIPT_JOB_CONTENT_MISMATCH"):
            self.receipt(content_id="content:foreign")
        self.assertEqual(self.scalar(
            "SELECT state FROM worker_budget_reservation WHERE job_id='job:1'"
        ), "RESERVED")
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")
        self.assertEqual(self.reserve(2, global_cap="1"),
                         "SOURCE_DAILY_BUDGET_REACHED")

    def test_different_request_keys_cannot_bill_one_reserved_attempt_twice(self):
        self.assertEqual(self.reserve(1, global_cap="1"), "RESERVED")
        original_id = self.receipt(request_key="original")
        with self.assertRaisesRegex(ValueError, "RECEIPT_ATTEMPT_ALREADY_CHARGED"):
            self.receipt(request_key="different")
        self.assertTrue(original_id.startswith("receipt:"))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM provider_receipt WHERE ledger_scope->>'job_id'='job:1'"
        ), "1")
        self.assertEqual(self.scalar(
            "SELECT cost_usd FROM processing_job WHERE id='job:1'"
        ), "0.200000")

    def test_parallel_different_request_keys_share_only_one_charge(self):
        self.assertEqual(self.reserve(1), "RESERVED")

        def persist(request_key):
            try:
                return self.receipt(request_key=request_key)
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(persist, ("parallel:a", "parallel:b")))
        self.assertEqual(sum(value.startswith("receipt:") for value in results), 1)
        self.assertEqual(sum(
            value == "RECEIPT_ATTEMPT_ALREADY_CHARGED" for value in results
        ), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "1")
        self.assertEqual(self.scalar(
            "SELECT cost_usd FROM processing_job WHERE id='job:1'"
        ), "0.200000")

    def test_stalled_ledger_mutex_fails_closed_and_can_retry(self):
        self.assertEqual(self.reserve(1), "RESERVED")
        with ThreadPoolExecutor(max_workers=1) as pool:
            holder = pool.submit(self.exec_sql, self.dsn, """
                BEGIN;
                SELECT pg_advisory_xact_lock(
                    hashtextextended('dp512:worker:global',0));
                SELECT pg_sleep(4);
                COMMIT;
            """)
            for _ in range(100):
                locked = self.scalar("""
                    SELECT count(*) FROM pg_locks
                    WHERE locktype='advisory' AND granted;
                """)
                if locked == "1":
                    break
                time.sleep(0.02)
            else:
                self.fail("fixture did not acquire receipt ledger mutex")
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, "lock timeout"):
                self.receipt()
            self.assertLess(time.monotonic() - started, 3.5)
            self.assertEqual(self.scalar(
                "SELECT state FROM worker_budget_reservation WHERE job_id='job:1'"
            ), "RESERVED")
            self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")
            holder.result(timeout=8)
        self.receipt()
        self.assertEqual(self.scalar(
            "SELECT state FROM worker_budget_reservation WHERE job_id='job:1'"
        ), "RECEIPTED")


class PsqlCommandTimeoutTests(unittest.TestCase):
    def test_external_subprocess_deadline_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, "PSQL_QUERY_TIMEOUT"):
            execute_psql(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                "SELECT 1;", 0.05,
            )
