"""DP-513 private usage reconciliation over genuine disposable PostgreSQL 17."""

from __future__ import annotations

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from tests import test_dp512_billing_pg_fence_next as dp512_fixture
from dichiarazioni_pubbliche.ops.usage_attribution_pg_v1 import (
    DisposablePgUsageAttribution,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore


class UsageAttributionPgTests(unittest.TestCase):
    """Reuses the real PG17 fixture, canonical DDL, and DP-512 fenced writer."""

    @classmethod
    def setUpClass(cls):
        dp512_fixture.BillingPgFenceTests.setUpClass.__func__(cls)
        cls.reader = DisposablePgUsageAttribution(cls.dsn)

    @classmethod
    def tearDownClass(cls):
        dp512_fixture.BillingPgFenceTests.tearDownClass.__func__(cls)

    @classmethod
    def sql(cls, query):
        return dp512_fixture.BillingPgFenceTests.sql.__func__(cls, query)

    def receipt(self, *args, **kwargs):
        return dp512_fixture.BillingPgFenceTests.receipt(self, *args, **kwargs)

    def save(self, *args, **kwargs):
        return dp512_fixture.BillingPgFenceTests.save(self, *args, **kwargs)

    def setUp(self):
        dp512_fixture.BillingPgFenceTests.setUp(self)

    def test_canonical_unknown_zero_and_estimated_zero_never_become_measured(self):
        unknown = self.receipt("unknown", basis="UNKNOWN", estimate="0")
        self.save(unknown)
        quoted = self.receipt(
            "estimate", basis="ESTIMATED_ONLY", estimate="0", attempt=2
        )
        self.save(
            quoted,
            event_id="event:quoted",
            asserted_basis="ESTIMATED_ONLY",
            asserted_usd="0",
        )
        report = self.reader.read()
        self.assertEqual(report.attempt_count, 2)
        self.assertEqual(report.operation_count, 1)
        self.assertEqual(report.unknown_cash_attempts, 1)
        self.assertEqual(report.recorded_measured_usd, Decimal("0"))
        self.assertEqual(report.provisional_estimated_usd, Decimal("0"))
        self.assertEqual(
            {x.billing_confidence for x in report.attempts},
            {"UNPRICED", "PROVISIONAL_ESTIMATE"},
        )
        self.assertFalse(report.invoice_attested)
        self.assertFalse(report.dispatch_authorized)

    def test_measured_requires_dp512_reference_and_is_never_invoice_attested(self):
        key = self.receipt(
            "measured",
            basis="MEASURED_PROVIDER_COST",
            measured="0.041",
            estimate="0.10",
            status="SUCCEEDED",
        )
        missing = self.reader.read()
        self.assertEqual(
            missing.attempts[0].billing_confidence,
            "RECORDED_MEASURED_REFERENCE_MISSING",
        )
        self.assertEqual(missing.source_reference_missing_attempts, 1)
        self.save(
            key,
            asserted_basis="MEASURED_PROVIDER_COST",
            asserted_usd="0.041",
            evidence_ref="provider-usage:fixture:s1",
        )
        report = self.reader.read()
        self.assertEqual(report.recorded_measured_usd, Decimal("0.041"))
        self.assertEqual(
            report.attempts[0].billing_confidence,
            "RECORDED_MEASURED_REFERENCE_UNVERIFIED",
        )
        self.assertTrue(report.attempts[0].source_reference_present)
        self.assertFalse(report.invoice_attested)
        self.assertNotIn("provider-usage:fixture:s1", repr(report))

    def test_provider_and_logical_attempts_retry_failures_and_reader_parity(self):
        first = self.receipt("one", status="FAILED", basis="UNKNOWN")
        second = self.receipt(
            "two",
            attempt=2,
            status="SUCCEEDED",
            basis="ESTIMATED_ONLY",
            estimate="0.09",
        )
        self.save(first)
        self.save(
            second,
            event_id="event:two",
            asserted_basis="ESTIMATED_ONLY",
            asserted_usd="0.09",
        )
        report = self.reader.read()
        self.assertTrue(report.canonical_ledger_parity)
        self.assertEqual(report.provider_count, 1)
        self.assertEqual(report.operation_count, 1)
        self.assertEqual([r.attempt for r in report.attempts], [1, 2])
        self.assertEqual(report.provisional_estimated_usd, Decimal("0.09"))
        self.assertEqual(report.unknown_cash_attempts, 1)
        self.assertEqual(report.attempts[0].status, "FAILED")
        self.assertEqual(report.attempts[1].status, "SUCCEEDED")
        self.assertEqual(report.attempts[0].day_utc, "2026-10-12")
        self.assertEqual(
            len(QueueExecutionCostStore(self.dsn).operation_ledger_receipts()), 2
        )

    def test_external_plan_energy_and_untrusted_subscription_remain_unpriced(self):
        key = self.receipt(
            "plan",
            basis="EXTERNAL_PLAN",
            receipt_body="""'{"local_energy_basis":"UNKNOWN","quota_units":888,
            "account_token":"PRIVATE TOKEN","plan_price_usd":0}'::jsonb""",
        )
        self.save(key, asserted_basis="EXTERNAL_PLAN")
        report = self.reader.read()
        self.assertEqual(report.external_plan_attempts, 1)
        self.assertEqual(report.recorded_measured_usd, Decimal("0"))
        self.assertEqual(report.attempts[0].local_energy_basis, "UNKNOWN")
        self.assertEqual(report.attempts[0].billing_confidence, "PLAN_QUOTA_UNVERIFIED")
        self.assertEqual(report.account_entitlement_status, "UNVERIFIED")
        self.assertNotIn("PRIVATE TOKEN", repr(report))

    def test_no_fake_refund_from_receipt_json_or_duplicate_statement_claim(self):
        key = self.receipt(
            "refund",
            basis="MEASURED_PROVIDER_COST",
            measured="0.27",
            receipt_body="""'{"refund_usd":0.27,
            "invoice_ref":"PRIVATE INVOICE","refund_status":"PAID"}'::jsonb""",
        )
        self.save(
            key,
            asserted_basis="MEASURED_PROVIDER_COST",
            asserted_usd="0.27",
            evidence_ref="usage:simulated",
        )
        report = self.reader.read()
        self.assertEqual(report.recorded_measured_usd, Decimal("0.27"))
        self.assertEqual(report.confirmed_refund_usd, None)
        self.assertFalse(report.refund_attested)
        self.assertNotIn("PRIVATE INVOICE", repr(report))

    def test_canonical_duplicate_attempt_different_ids_is_rejected(self):
        self.receipt("first", basis="UNKNOWN")
        self.receipt("second", basis="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "CANONICAL_ATTEMPT_CONFLICT"):
            self.reader.read()

    def test_dp512_append_only_corrections_count_latest_only_after_restart(self):
        key = self.receipt("correction", basis="ESTIMATED_ONLY", estimate="0.123")
        self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.123")
        self.store.record(
            receipt_id=key,
            event_id="event:correction",
            expected_revision=1,
            asserted_basis="ESTIMATED_ONLY",
            asserted_usd="0.123",
            evidence_ref="rate:revised",
        )
        restarted = DisposablePgUsageAttribution(self.dsn)
        result = restarted.read()
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(result.provisional_estimated_usd, Decimal("0.123"))
        self.assertEqual(result.attempts[0].classification_revision, 2)
        self.assertEqual(result.attempts[0].classification_history_count, 2)
        self.assertFalse(result.invoice_attested)

    def test_canonical_mutation_invalidates_dp512_binding(self):
        key = self.receipt("drift", basis="ESTIMATED_ONLY", estimate="0.10")
        self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.10")
        self.sql(
            "UPDATE provider_receipt SET estimated_cost_usd=0.90 "
            "WHERE id='receipt:drift';"
        )
        with self.assertRaisesRegex(ValueError, "CANONICAL_RECEIPT_DRIFT"):
            self.reader.read()

    def test_ledger_change_between_snapshot_and_consumer_read_is_rejected(self):
        key = self.receipt("racing", basis="UNKNOWN")
        self.save(key)

        def competing_consumer():
            self.sql(
                "UPDATE provider_receipt SET status='RETRIED' "
                "WHERE id='receipt:racing';"
            )
            return QueueExecutionCostStore(self.dsn).operation_ledger_receipts()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=competing_consumer)

    def test_concurrent_dp512_corrections_one_wins_and_readback_is_consistent(self):
        key = self.receipt("race", basis="ESTIMATED_ONLY", estimate="0.03")
        self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.03")

        def correction(number):
            try:
                return self.store.record(
                    receipt_id=key,
                    event_id=f"event:race:{number}",
                    expected_revision=1,
                    asserted_basis="ESTIMATED_ONLY",
                    asserted_usd="0.03",
                    evidence_ref=f"rate:{number}",
                )["revision"]
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(correction, i) for i in range(2)]
            self.assertEqual(
                {r.result(timeout=10) for r in results},
                {2, "BILLING_REVISION_CONFLICT"},
            )
        report = self.reader.read()
        self.assertEqual(report.attempt_count, 1)
        self.assertEqual(report.attempts[0].classification_revision, 2)
        self.assertTrue(report.canonical_ledger_parity)

    def test_two_providers_have_separate_denominators_no_inferred_api_access(self):
        self.receipt("alpha", provider="provider:alpha", operation_key="run:a")
        self.receipt("beta", provider="provider:beta", operation_key="run:b")
        report = self.reader.read()
        self.assertEqual(report.provider_count, 2)
        self.assertEqual(report.operation_count, 2)
        self.assertEqual(report.attempt_count, 2)
        self.assertEqual(report.account_entitlement_status, "UNVERIFIED")
        self.assertFalse(report.dispatch_authorized)

    def test_cross_provider_same_operation_key_is_not_falsely_one_provider(self):
        self.receipt(
            "provider-a",
            provider="provider:alpha",
            operation_key="operation:collision",
            attempt=1,
        )
        self.receipt(
            "provider-b",
            provider="provider:beta",
            operation_key="operation:collision",
            attempt=2,
        )
        with self.assertRaisesRegex(ValueError, "CANONICAL_LEDGER_INVALID"):
            self.reader.read()

    def test_untrusted_status_is_redacted_and_does_not_change_denominator(self):
        self.receipt("hostile", status="PROMPT_PRIVATE_SECRET", basis="UNKNOWN")
        report = self.reader.read()
        self.assertEqual(report.attempt_count, 1)
        self.assertEqual(report.attempts[0].status, "UNRECOGNIZED_STATUS")
        self.assertNotIn("PROMPT_PRIVATE_SECRET", repr(report))

    def test_utc_day_boundary_and_time_format_have_no_fake_local_reset(self):
        self.receipt("before", operation_key="run:before", basis="UNKNOWN")
        self.receipt("after", operation_key="run:after", basis="UNKNOWN")
        self.sql(
            "UPDATE provider_receipt SET started_at='2026-10-11 23:58:00+00', "
            "completed_at="
            "'2026-10-11 23:59:59+00' WHERE id='receipt:before';"
            "UPDATE provider_receipt SET completed_at="
            "'2026-10-12 00:00:01+00' WHERE id='receipt:after';"
        )
        report = self.reader.read()
        self.assertEqual(
            {a.day_utc for a in report.attempts},
            {"2026-10-11", "2026-10-12"},
        )
        self.assertEqual(report.unknown_cash_attempts, 2)
        self.assertEqual(report.recorded_measured_usd, Decimal("0"))

    def test_hidden_raw_receipt_strings_and_account_scope_do_not_leak(self):
        self.receipt(
            "secret",
            basis="UNKNOWN",
            receipt_body="""'{"secret":"PROMPT ORIGINAL PRIVATE",
            "billing_account":"ACCOUNT OWNER PRIVATE",
            "audio":"UNPUBLISHED CONTENT"}'::jsonb""",
        )
        report = self.reader.read()
        raw = json.dumps([r.__dict__ for r in report.attempts], default=str)
        for secret in (
            "PROMPT ORIGINAL PRIVATE",
            "ACCOUNT OWNER PRIVATE",
            "UNPUBLISHED CONTENT",
        ):
            self.assertNotIn(secret, raw)


if __name__ == "__main__":
    unittest.main()
