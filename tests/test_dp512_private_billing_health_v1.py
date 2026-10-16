"""DP-512.4/.6: disposable PostgreSQL ledger ↔ private health consumer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from tests import test_dp512_billing_pg_fence_next as pg_fixture  # noqa: E402

from dichiarazioni_pubbliche.ops.private_billing_health_v1 import (  # noqa: E402
    read_private_billing_health,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore  # noqa: E402
from dichiarazioni_pubbliche.scheduler_daemon import PsqlStore  # noqa: E402


class PrivateBillingHealthPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the established disposable PG fixture, never the MiniPC live DB.
        pg_fixture.BillingPgFenceTests.setUpClass()
        cls.store = QueueExecutionCostStore(pg_fixture.BillingPgFenceTests.dsn)

    @classmethod
    def tearDownClass(cls):
        pg_fixture.BillingPgFenceTests.tearDownClass()

    def sql(self, query):
        return pg_fixture.BillingPgFenceTests.sql(query)

    def setUp(self):
        self.sql("TRUNCATE dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;")

    def insert(
        self,
        name,
        *,
        basis,
        estimated="NULL",
        measured="NULL",
        attempt=1,
        operation_key="'operation:one'",
        status="SUCCESS",
        started="2026-10-15 12:00:00+00",
        completed="2026-10-15 12:01:00+00",
        receipt="'{}'::jsonb",
    ):
        self.sql(
            "INSERT INTO provider_receipt (id,provider_id,model_id,operation,"
            "operation_key,attempt,status,billing_basis,estimated_cost_usd,"
            "measured_cost_usd,started_at,completed_at,receipt) VALUES ("
            f"'receipt:{name}','provider:fixture','model:local','CLAIM_EXTRACT',"
            f"{operation_key},{attempt},'{status}','{basis}',{estimated},{measured},"
            f"'{started}','{completed}',{receipt});"
        )

    def report(
        self, since="2026-10-15T00:00:00+00:00", until="2026-10-16T00:00:00+00:00"
    ):
        return read_private_billing_health(self.store, since=since, until=until)

    def canonical_hash(self):
        return self.sql(
            "SELECT md5(COALESCE(json_agg(r ORDER BY id)::text,'[]')) FROM provider_receipt r;"
        )

    def test_real_pg_retries_legacy_unknown_plan_and_private_output(self):
        self.insert(
            "attempt1",
            basis="ESTIMATED_ONLY",
            estimated="0.4",
            attempt=1,
            status="FAILED",
        )
        self.insert(
            "attempt2", basis="MEASURED_PROVIDER_COST", measured="0.1", attempt=2
        )
        self.insert(
            "legacy",
            basis="ESTIMATED_ONLY",
            operation_key="NULL",
            estimated="NULL",
            receipt='\'{"prompt":"secret-prompt"}\'::jsonb',
        )
        self.insert(
            "plan",
            basis="EXTERNAL_PLAN",
            operation_key="'operation:plan'",
            receipt='\'{"local_energy_basis":"UNKNOWN","token":"secret-token"}\'::jsonb',
        )

        before = self.canonical_hash()
        report = self.report()
        self.assertEqual(before, self.canonical_hash())
        self.assertEqual(report["attempt_count"], 4)
        self.assertEqual(report["operation_count"], 3)
        self.assertEqual(
            report["classification_counts"],
            {
                "MEASURED_PROVIDER_COST": 1,
                "ESTIMATED_ONLY": 1,
                "EXTERNAL_PLAN": 1,
                "UNKNOWN": 1,
                "ZERO_COST": 0,
            },
        )
        self.assertEqual(report["provisional_estimated_usd"], "0.400000")
        self.assertEqual(report["recorded_measured_unverified_usd"], "0.100000")
        self.assertEqual(report["legacy_attempt_count"], 1)
        self.assertEqual(report["unknown_cash_attempt_count"], 1)
        # The integrated ledger classifies absent energy provenance as UNKNOWN
        # for every attempt, not only for the EXTERNAL_PLAN attempt.
        self.assertEqual(report["unknown_local_energy_attempt_count"], 4)
        self.assertEqual(
            report["scheduler_health_parity"], "RECEIPT_IDS_MATCH_NONATOMIC"
        )
        self.assertIsNone(report["verified_invoice_usd"])
        self.assertFalse(report["invoice_attested"])
        self.assertFalse(report["dispatch_authorized"])
        encoded = json.dumps(report)
        for secret in (
            "secret-prompt",
            "secret-token",
            "receipt:legacy",
            "operation:one",
        ):
            self.assertNotIn(secret, encoded)

    def test_undated_unallocated_legacy_is_held_outside_day_window(self):
        self.insert(
            "undated", basis="ESTIMATED_ONLY", estimated="NULL", operation_key="NULL"
        )
        self.sql(
            "UPDATE provider_receipt SET started_at=NULL, completed_at=NULL "
            "WHERE id='receipt:undated';"
        )
        report = self.report()
        self.assertEqual(report["attempt_count"], 0)
        self.assertEqual(report["undated_unallocated_attempt_count"], 1)
        self.assertEqual(report["scheduler_health_parity"], "UNALLOCATED_HELD")
        self.assertFalse(report["dispatch_authorized"])

    def test_rome_month_boundary_uses_explicit_offset(self):
        self.insert(
            "rome-boundary",
            basis="ESTIMATED_ONLY",
            estimated="0.09",
            started="2026-10-31 23:30:00+00",
            completed="2026-10-31 23:31:00+00",
        )
        # November in Rome starts at 23:00 UTC after the October DST switch.
        report = self.report(
            since="2026-11-01T00:00:00+01:00",
            until="2026-11-02T00:00:00+01:00",
        )
        self.assertEqual(report["window_start_utc"], "2026-10-31T23:00:00+00:00")
        self.assertEqual(report["attempt_count"], 1)
        self.assertEqual(report["provisional_estimated_usd"], "0.090000")
        self.assertEqual(
            report["scheduler_health_parity"], "RECEIPT_IDS_MATCH_NONATOMIC"
        )

    def test_cross_period_completion_uses_canonical_start_window(self):
        self.insert(
            "cross-period",
            basis="ESTIMATED_ONLY",
            estimated="0.25",
            started="2026-09-30 23:50:00+00",
            completed="2026-10-15 12:01:00+00",
        )
        report = self.report()
        self.assertEqual(report["attempt_count"], 0)
        self.assertEqual(report["scheduler_health_parity"], "RECEIPT_IDS_MATCH_NONATOMIC")
        self.assertFalse(report["dispatch_authorized"])
        self.assertEqual(report["scheduler_window_attempt_count"], 0)
        self.assertEqual(report["provisional_estimated_usd"], "0.000000")

    def test_zero_ceiling_is_never_verified_free_and_bounds_are_strict(self):
        self.insert("zero-unknown", basis="ESTIMATED_ONLY", estimated="NULL")
        report = self.report()
        self.assertEqual(report["unknown_cash_attempt_count"], 1)
        self.assertEqual(report["classification_counts"]["ZERO_COST"], 0)
        self.assertEqual(
            report["scheduler_health_parity"], "RECEIPT_IDS_MATCH_NONATOMIC"
        )
        with self.assertRaisesRegex(ValueError, "DP512_WINDOW_INVALID"):
            self.report(since="2026-10-15T00:00:00", until="2026-10-16T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "DP512_WINDOW_INVALID"):
            self.report(
                since="2026-10-16T00:00:00+00:00", until="2026-10-15T00:00:00+00:00"
            )

    def test_unknown_receipt_does_not_appear_free_in_worker_cost_snapshot(self):
        self.insert("unpriced", basis="ESTIMATED_ONLY", estimated="NULL")
        self.sql(
            "UPDATE provider_receipt SET started_at=now(),completed_at=now() "
            "WHERE id='receipt:unpriced';"
        )
        snapshot = self.store.cost_snapshot("fixture-source")
        self.assertEqual(snapshot.global_day_usd, float("inf"))
        scheduler = PsqlStore(pg_fixture.BillingPgFenceTests.dsn)
        self.assertEqual(scheduler.cost_today(), float("inf"))

    def test_unverified_zero_receipt_is_held_by_both_actual_pg_consumers(self):
        self.insert("unverified-zero", basis="ZERO_COST", estimated="0")
        self.sql(
            "UPDATE provider_receipt SET started_at=now(),completed_at=now() "
            "WHERE id='receipt:unverified-zero';"
        )
        self.assertEqual(self.store.cost_snapshot("fixture-source").global_day_usd, float("inf"))
        self.assertEqual(
            PsqlStore(pg_fixture.BillingPgFenceTests.dsn).cost_today(), float("inf")
        )

    def test_unresolved_prior_day_liability_cannot_reset_paid_budget_at_midnight(self):
        self.insert("prior-unknown", basis="UNKNOWN", estimated="NULL", measured="NULL")
        self.sql(
            "UPDATE provider_receipt SET started_at=now()-interval '2 days',"
            "completed_at=now() WHERE id='receipt:prior-unknown';"
        )
        # Known day-window costs may reset. An unresolved liability must not.
        snapshot = self.store.cost_snapshot("fixture-source")
        self.assertEqual(snapshot.global_day_usd, float("inf"))
        self.assertEqual(
            PsqlStore(pg_fixture.BillingPgFenceTests.dsn).cost_today(), float("inf")
        )

    def test_private_cli_uses_libpq_env_and_emits_aggregate_only(self):
        self.insert(
            "cli",
            basis="ESTIMATED_ONLY",
            estimated="0.12",
            receipt='\'{"token":"no-secret-in-output"}\'::jsonb',
        )
        env = os.environ.copy()
        env.pop("DICHIARAZIONI_PUBBLICHE_DATABASE_URL", None)
        env.pop("PGSERVICE", None)
        env.update(
            PGDATABASE="dp512_test_billing",
            PGHOST="127.0.0.1",
            PGPORT=str(pg_fixture.BillingPgFenceTests.port),
            PGUSER="postgres",
            PYTHONPATH=str(ROOT / "poc"),
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "dichiarazioni_pubbliche.ops.private_billing_health_v1",
                "--since",
                "2026-10-15T00:00:00+00:00",
                "--until",
                "2026-10-16T00:00:00+00:00",
            ],
            text=True,
            capture_output=True,
            env=env,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["provisional_estimated_usd"], "0.120000")
        self.assertEqual(
            result["scheduler_health_parity"], "RECEIPT_IDS_MATCH_NONATOMIC"
        )
        self.assertFalse(result["dispatch_authorized"])
        self.assertNotIn("receipt:cli", completed.stdout)
        self.assertNotIn("no-secret-in-output", completed.stdout)


if __name__ == "__main__":
    unittest.main()
