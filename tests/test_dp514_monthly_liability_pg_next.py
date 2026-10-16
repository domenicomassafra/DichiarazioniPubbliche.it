"""DP514: real isolated PostgreSQL monetary liability from DP512/DP513."""

from __future__ import annotations

import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from tests import test_dp512_billing_pg_fence_next as fixture  # noqa: E402
from dichiarazioni_pubbliche.ops.monthly_liability_pg_v1 import (  # noqa: E402
    DisposableMonthlyLiabilityPg,
    _SNAPSHOT,
)
from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    BudgetPolicy, CostSnapshot, MonthlyBudgetState, MonthlyEurPolicy,
    MonthlyFxQuote, monthly_budget_preflight,
)

OCT = "2026-10@Europe/Rome"
NOV = "2026-11@Europe/Rome"


class MonthlyLiabilityPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.BillingPgFenceTests.setUpClass.__func__(cls)
        cls.reader = DisposableMonthlyLiabilityPg(cls.dsn)
        cls.reader.install_disposable_schema()

    @classmethod
    def tearDownClass(cls):
        fixture.BillingPgFenceTests.tearDownClass.__func__(cls)

    @classmethod
    def sql(cls, query):
        return fixture.BillingPgFenceTests.sql.__func__(cls, query)

    def setUp(self):
        self.sql("TRUNCATE dp514_pg_event, dp514_pg_state, "
                 "dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;")

    def receipt(self, *args, **kwargs):
        return fixture.BillingPgFenceTests.receipt(self, *args, **kwargs)

    def classify(self, receipt_id, basis="UNKNOWN", amount=None, event=None, evidence=None):
        return self.store.record(
            receipt_id=receipt_id, event_id=event or "event:" + receipt_id,
            expected_revision=0, asserted_basis=basis, asserted_usd=amount,
            evidence_ref=evidence,
        )

    def report(self, *, at=None, between=None):
        return self.reader.read(
            as_of=at or datetime(2026, 11, 2, tzinfo=timezone.utc),
            timezone_name="Europe/Rome", _between=between,
        )

    def test_unknown_zero_estimate_still_blocks_november_not_billed_zero(self):
        key = self.receipt("unknown", basis="UNKNOWN", estimate="0")
        self.classify(key)
        result = self.report()
        self.assertEqual(result.total_attempts, 1)
        self.assertEqual(result.unknown_attempts, 1)
        self.assertIsNone(result.billed_eur)
        self.assertTrue(result.hold_new_spend)
        self.assertEqual(result.months[0].period, OCT)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.invoice_attested)

    def test_missing_estimate_normalizes_to_dp513_unknown_without_false_zero(self):
        self.receipt("unpriced-estimate", basis="ESTIMATED_ONLY", estimate=None)
        report = self.report()
        self.assertEqual(report.total_attempts, 1)
        self.assertEqual(report.unknown_attempts, 1)
        self.assertEqual(report.months[0].unknown_attempts, 1)
        self.assertTrue(report.hold_new_spend)
        self.assertIsNone(report.billed_eur)

    def test_valid_estimate_alone_does_not_claim_paid_monthly_budget(self):
        key = self.receipt("estimate-only", basis="ESTIMATED_ONLY", estimate="0.10")
        self.classify(key, "ESTIMATED_ONLY", "0.10")
        report = self.report()
        self.assertEqual(report.unknown_attempts, 0)
        self.assertTrue(report.hold_new_spend)
        self.assertFalse(report.dispatch_authorized)
        self.assertFalse(report.usd_daily_caps_verified)
        self.assertFalse(report.fx_attested)

    def test_estimate_measured_ref_plan_refund_never_invoice_proof(self):
        a = self.receipt("estimated", basis="ESTIMATED_ONLY", estimate="0.24",
                         operation_key="op:estimated")
        b = self.receipt("measured", basis="MEASURED_PROVIDER_COST", measured="0.11",
                         operation_key="op:measured")
        c = self.receipt("plan", basis="EXTERNAL_PLAN", operation_key="op:plan")
        self.classify(a, "ESTIMATED_ONLY", "0.24")
        self.classify(b, "MEASURED_PROVIDER_COST", "0.11", evidence="receipt:synthetic")
        self.classify(c, "EXTERNAL_PLAN")
        result = self.report()
        self.assertEqual(result.provisional_estimated_usd, Decimal("0.24"))
        self.assertEqual(result.recorded_measured_usd, Decimal("0.11"))
        self.assertEqual(result.plan_or_unpriced_attempts, 1)
        self.assertIsNone(result.billed_eur)
        self.assertIsNone(result.refunded_eur)
        self.assertTrue(result.hold_new_spend)
        self.assertNotIn("receipt:synthetic", repr(result))

    def test_month_uses_started_at_not_late_completed_november_or_provider_reset(self):
        key = self.receipt("late", basis="ESTIMATED_ONLY", estimate="0.12")
        self.sql("UPDATE provider_receipt SET started_at='2026-10-31 22:59:59+00', "
                 "completed_at='2026-11-01 01:01:00+00' WHERE id='receipt:late';")
        self.classify(key, "ESTIMATED_ONLY", "0.12")
        self.assertEqual(self.report().months[0].period, OCT)
        self.assertEqual(
            self.reader.read(as_of=datetime(2026, 11, 2, tzinfo=timezone.utc),
                             timezone_name="UTC").months[0].period,
            "2026-10@UTC",
        )
        self.assertIsNone(self.report().billed_eur)

    def test_unknown_october_and_estimated_november_both_counted_no_reset(self):
        old = self.receipt("oct", basis="UNKNOWN", operation_key="op:oct")
        new = self.receipt("nov", basis="ESTIMATED_ONLY", estimate="0.15",
                           operation_key="op:nov")
        self.sql("UPDATE provider_receipt SET started_at='2026-11-01 03:10:00+00', "
                 "completed_at='2026-11-01 03:11:00+00' "
                 "WHERE id='receipt:nov';")
        self.classify(old)
        self.classify(new, "ESTIMATED_ONLY", "0.15")
        result = self.report()
        self.assertEqual([x.period for x in result.months], [OCT, NOV])
        self.assertEqual(result.prior_unknown_attempts, 1)
        self.assertTrue(result.hold_new_spend)
        self.assertEqual(result.provisional_estimated_usd, Decimal("0.15"))

    def test_observation_cas_replay_restart_conflict_and_attempt_uniqueness(self):
        key = self.receipt("cas", basis="ESTIMATED_ONLY", estimate="0.07")
        self.classify(key, "ESTIMATED_ONLY", "0.07")
        first = self.reader.append(
            receipt_id=key, event_id="observation:one", expected_revision=0,
            kind="OBSERVED", amount_usd="0.07",
        )
        self.assertEqual(first["revision"], 1)
        restarted = DisposableMonthlyLiabilityPg(self.dsn)
        self.assertEqual(restarted.append(
            receipt_id=key, event_id="observation:one", expected_revision=0,
            kind="OBSERVED", amount_usd="0.07",
        ), first)
        with self.assertRaisesRegex(ValueError, "DP514_EVENT_REPLAY_CONFLICT"):
            restarted.append(receipt_id=key, event_id="observation:one",
                             expected_revision=0, kind="REFUND_CLAIM", amount_usd="0.07")
        with self.assertRaisesRegex(ValueError, "DP514_REVISION_CONFLICT"):
            restarted.append(receipt_id=key, event_id="observation:two",
                             expected_revision=0, kind="OBSERVED", amount_usd="0.07")
        self.assertEqual(self.report().observation_events, 1)

    def test_event_id_reused_for_different_attempt_denied_without_orphan_state(self):
        left = self.receipt("event-left", basis="ESTIMATED_ONLY", estimate="0.03",
                            operation_key="op:event-left")
        right = self.receipt("event-right", basis="ESTIMATED_ONLY", estimate="0.04",
                             operation_key="op:event-right")
        self.classify(left, "ESTIMATED_ONLY", "0.03")
        self.classify(right, "ESTIMATED_ONLY", "0.04")
        self.reader.append(receipt_id=left, event_id="obs:shared",
                           expected_revision=0, kind="OBSERVED", amount_usd="0.03")
        with self.assertRaisesRegex(ValueError, "DP514_EVENT_REPLAY_CONFLICT"):
            self.reader.append(receipt_id=right, event_id="obs:shared",
                               expected_revision=0, kind="OBSERVED", amount_usd="0.04")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp514_pg_state;"), "1")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp514_pg_event;"), "1")

    def test_claimed_refund_is_append_only_but_never_offsets_spend(self):
        key = self.receipt("refund", basis="MEASURED_PROVIDER_COST", measured="0.21")
        self.classify(key, "MEASURED_PROVIDER_COST", "0.21", evidence="usage:synthetic")
        self.reader.append(receipt_id=key, event_id="observation:refund",
                           expected_revision=0, kind="REFUND_CLAIM", amount_usd="0.21")
        result = self.report()
        self.assertEqual(result.recorded_measured_usd, Decimal("0.21"))
        self.assertEqual(result.unverified_refund_claim_usd, Decimal("0.21"))
        self.assertEqual(result.refund_claim_events, 1)
        self.assertIsNone(result.refunded_eur)
        self.assertTrue(result.hold_new_spend)
        self.assertFalse(result.dispatch_authorized)
        for statement in (
            "UPDATE dp514_pg_event SET kind='OBSERVED';",
            "DELETE FROM dp514_pg_event;",
        ):
            with self.assertRaises(RuntimeError):
                self.sql(statement)

    def test_adjustment_after_observation_keeps_monthly_replay_and_append_usable(self):
        key = self.receipt(
            "adjust-cross-ledger", basis="MEASURED_PROVIDER_COST",
            measured="0.40", status="SUCCEEDED",
        )
        self.classify(key, "MEASURED_PROVIDER_COST", "0.40",
                      evidence="usage:synthetic")
        first = self.reader.append(
            receipt_id=key, event_id="obs:before-adjust", expected_revision=0,
            kind="OBSERVED", amount_usd="0.40",
        )
        self.store.adjust(
            receipt_id=key, event_id="adjust:refund-cross-ledger",
            expected_revision=1, adjustment_kind="REFUND",
            amount_usd="0.10", evidence_ref="statement:synthetic",
        )
        self.assertEqual(
            self.reader.append(
                receipt_id=key, event_id="obs:before-adjust",
                expected_revision=0, kind="OBSERVED", amount_usd="0.40",
            ),
            first,
        )
        second = self.reader.append(
            receipt_id=key, event_id="obs:after-adjust", expected_revision=1,
            kind="REFUND_CLAIM", amount_usd="0.10",
        )
        self.assertEqual(second["revision"], 2)
        report = self.report()
        self.assertEqual(report.recorded_measured_usd, Decimal("0.40"))
        self.assertEqual(report.unverified_refund_claim_usd, Decimal("0.10"))
        self.assertEqual(report.observation_events, 1)
        self.assertEqual(report.refund_claim_events, 1)
        self.assertTrue(report.hold_new_spend)
        self.assertFalse(report.invoice_attested)
        self.assertFalse(report.dispatch_authorized)

    def test_cold_snapshot_disables_jit_locally_without_changing_liability(self):
        key = self.receipt("jit", basis="MEASURED_PROVIDER_COST", measured="0.21")
        self.classify(key, "MEASURED_PROVIDER_COST", "0.21", evidence="usage:synthetic")
        self.reader.append(receipt_id=key, event_id="refund:jit", expected_revision=0,
                           kind="REFUND_CLAIM", amount_usd="0.21")
        original_jit = self.sql("SHOW jit;")
        # Verify the actual SQL-local setting while preserving the complete
        # financial snapshot and restoring the separate connection's default.
        observed = self.reader._run(
            _SNAPSHOT.replace("SELECT COALESCE(", "SHOW jit;\nSELECT COALESCE(", 1),
            _family="SNAPSHOT",
        ).splitlines()
        self.assertEqual(observed[0], "off")
        self.assertEqual(len(json.loads(observed[1])), 1)
        self.assertEqual(self.sql("SHOW jit;"), original_jit)
        report = self.report()
        self.assertEqual(report.recorded_measured_usd, Decimal("0.21"))
        self.assertEqual(report.unverified_refund_claim_usd, Decimal("0.21"))
        self.assertTrue(report.hold_new_spend)
        self.assertFalse(report.dispatch_authorized)

    def test_parallel_competing_cas_one_commits_and_loser_cannot_double_claim(self):
        key = self.receipt("race", basis="ESTIMATED_ONLY", estimate="0.05")
        self.classify(key, "ESTIMATED_ONLY", "0.05")

        def record(num):
            try:
                return self.reader.append(receipt_id=key, event_id=f"obs:race:{num}",
                                          expected_revision=0, kind="OBSERVED",
                                          amount_usd="0.05")["revision"]
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = [pool.submit(record, n) for n in range(2)]
            self.assertEqual({v.result(timeout=15) for v in result},
                             {1, "DP514_REVISION_CONFLICT"})
        self.assertEqual(self.report().observation_events, 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp514_pg_event;"), "1")

    def test_original_row_mutation_or_dp512_reclassification_blocks_stale_basis(self):
        key = self.receipt("drift", basis="ESTIMATED_ONLY", estimate="0.06")
        self.classify(key, "ESTIMATED_ONLY", "0.06")
        self.sql("UPDATE provider_receipt SET estimated_cost_usd=0.17 "
                 "WHERE id='receipt:drift';")
        with self.assertRaisesRegex(ValueError, "DP513_CANONICAL_RECEIPT_DRIFT"):
            self.report()
        with self.assertRaisesRegex(ValueError, "DP514_CANONICAL_DRIFT"):
            self.reader.append(receipt_id=key, event_id="obs:stale",
                               expected_revision=0, kind="OBSERVED", amount_usd="0.06")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp514_pg_event;"), "0")

    def test_distinct_receipts_duplicate_canonical_attempt_is_rejected(self):
        self.receipt("one", basis="UNKNOWN")
        self.receipt("two", basis="UNKNOWN")
        self.sql(
            "UPDATE provider_receipt SET started_at='2026-11-01 03:10:00+00', "
            "completed_at='2026-11-01 03:11:00+00' WHERE id='receipt:two';"
        )
        with self.assertRaisesRegex(ValueError, "DP513_CANONICAL_ATTEMPT_CONFLICT"):
            self.report()
        with self.assertRaisesRegex(ValueError, "DP514_AMBIGUOUS_ATTEMPT"):
            self.reader.append(receipt_id="receipt:one", event_id="obs:collision",
                               expected_revision=0, kind="OBSERVED", amount_usd=None)

    def test_fault_during_event_insert_rolls_back_revision_then_retry(self):
        key = self.receipt("rollback", basis="ESTIMATED_ONLY", estimate="0.08")
        self.classify(key, "ESTIMATED_ONLY", "0.08")
        self.sql("""CREATE OR REPLACE FUNCTION dp514_test_abort() RETURNS trigger
          LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'TEST_ABORT_EVENT'; END $$;
          CREATE TRIGGER dp514_test_abort_insert BEFORE INSERT ON dp514_pg_event
          FOR EACH ROW EXECUTE FUNCTION dp514_test_abort();""")
        try:
            with self.assertRaises(RuntimeError):
                self.reader.append(receipt_id=key, event_id="obs:rollback",
                                   expected_revision=0, kind="OBSERVED", amount_usd="0.08")
        finally:
            self.sql("DROP TRIGGER dp514_test_abort_insert ON dp514_pg_event;")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp514_pg_state;"), "0")
        self.reader.append(receipt_id=key, event_id="obs:rollback",
                           expected_revision=0, kind="OBSERVED", amount_usd="0.08")
        self.assertEqual(self.report().observation_events, 1)

    def test_dp512_revision_change_invalidates_prior_observation_until_new_cas(self):
        key = self.receipt("basis-revision", basis="ESTIMATED_ONLY", estimate="0.14")
        self.classify(key, "ESTIMATED_ONLY", "0.14")
        self.reader.append(
            receipt_id=key, event_id="observation:old-basis", expected_revision=0,
            kind="OBSERVED", amount_usd="0.14",
        )
        self.store.record(
            receipt_id=key, event_id="event:revalidated", expected_revision=1,
            asserted_basis="ESTIMATED_ONLY", asserted_usd="0.14",
            evidence_ref="rate:synthetic-next",
        )
        with self.assertRaisesRegex(ValueError, "DP514_LIABILITY_INTEGRITY"):
            self.report()
        with self.assertRaisesRegex(ValueError, "DP514_AMOUNT_CONFLICT"):
            self.reader.append(
                receipt_id=key, event_id="observation:bad-basis", expected_revision=1,
                kind="OBSERVED", amount_usd="0.01",
            )
        self.reader.append(
            receipt_id=key, event_id="observation:new-basis", expected_revision=1,
            kind="OBSERVED", amount_usd="0.14",
        )
        report = self.report()
        self.assertEqual(report.observation_events, 2)
        self.assertEqual(report.provisional_estimated_usd, Decimal("0.14"))
        self.assertFalse(report.invoice_attested)

    def test_refund_claim_cannot_revalidate_stale_observation_after_reclassification(self):
        key = self.receipt("stale-class", basis="ESTIMATED_ONLY", estimate="0.14")
        self.classify(key, "ESTIMATED_ONLY", "0.14")
        self.reader.append(
            receipt_id=key, event_id="obs:stale-first", expected_revision=0,
            kind="OBSERVED", amount_usd="0.14",
        )
        self.store.record(
            receipt_id=key, event_id="event:class-new", expected_revision=1,
            asserted_basis="ESTIMATED_ONLY", asserted_usd="0.14",
            evidence_ref=None,
        )
        self.reader.append(
            receipt_id=key, event_id="claim:new-class", expected_revision=1,
            kind="REFUND_CLAIM", amount_usd="0.04",
        )
        with self.assertRaisesRegex(ValueError, "DP514_LIABILITY_INTEGRITY"):
            self.report()
        self.reader.append(
            receipt_id=key, event_id="obs:current-class", expected_revision=2,
            kind="OBSERVED", amount_usd="0.14",
        )
        report = self.report()
        self.assertEqual(report.observation_events, 2)
        self.assertEqual(report.refund_claim_events, 1)
        self.assertTrue(report.hold_new_spend)
        self.assertFalse(report.dispatch_authorized)

    def test_double_read_refuses_new_receipt_between_dp513_and_snapshot(self):
        key = self.receipt("first", basis="ESTIMATED_ONLY", estimate="0.01")
        self.classify(key, "ESTIMATED_ONLY", "0.01")

        def competitor():
            self.receipt("second", basis="UNKNOWN", operation_key="op:second")

        with self.assertRaisesRegex(ValueError, "DP514_READ_DRIFT"):
            self.report(between=competitor)

    def test_sqlite_month_policy_remains_undispatched_with_unknown_pg_liability(self):
        self.receipt("unknown", basis="UNKNOWN")
        report = self.report()
        state = MonthlyBudgetState(period=NOV, policy_version="synthetic-policy",
                                   revision=0, unknown_liability=report.hold_new_spend)
        at = datetime(2026, 11, 2, tzinfo=timezone.utc)
        decision = monthly_budget_preflight(
            policy=MonthlyEurPolicy(version="synthetic-policy", enabled=True,
                                    cap_eur=Decimal("10")),
            state=state, attempt_id="job:new", operation="CLAIM_EXTRACT",
            upper_bound_usd=Decimal("0.15"), billing_basis="ESTIMATED_ONLY",
            at=at, fx_quote=MonthlyFxQuote(
                rate_eur_per_usd=Decimal("0.9"), reference="synthetic:fx",
                source="synthetic", observed_at=at,
            ), legacy_policy=BudgetPolicy(),
            legacy_snapshot=CostSnapshot(0, 0), expected_revision=0,
        )
        self.assertEqual(decision.reason, "MONTHLY_UNKNOWN_LIABILITY")
        self.assertFalse(decision.dispatch_authorized)


if __name__ == "__main__":
    unittest.main()
