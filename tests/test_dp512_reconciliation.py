"""DP-512 read-only receipt/invoice comparison; no payment or invoice authority."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.operation_ledger import (  # noqa: E402
    BillingStatementLine,
    aggregate_operation_receipts,
    reconcile_operation_billing,
    operation_usage_receipt_from_row,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore  # noqa: E402


def persisted(receipt, attempt, basis, *, cost=None, estimate=None, energy=None):
    return {
        "receipt_id": receipt, "operation_key": "operation:retry", "attempt": attempt,
        "provider_id": "provider:offline", "model_id": "model:offline",
        "operation": "CANDIDATE_EXTRACT", "status": "FAILED" if attempt == 1 else "SUCCESS",
        "billing_basis": basis, "measured_cost_usd": cost,
        "estimated_cost_usd": estimate, "total_tokens": 120,
        "request_count": 1, "input_seconds": None, "local_energy_basis": energy,
    }


def line(*, line_id="invoice-line:1", receipt="receipt:2", attempt=2,
         amount="0.15", currency="USD", source="invoice:unverified-2026-10"):
    return BillingStatementLine(
        line_id=line_id, receipt_id=receipt, operation_key="operation:retry",
        attempt=attempt, provider_id="provider:offline", currency=currency,
        amount=Decimal(amount), source_reference=source,
        observed_at="2026-10-11T13:00:00+00:00",
    )


class BillingReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.first = operation_usage_receipt_from_row(
            persisted("receipt:1", 1, "ESTIMATED_ONLY", estimate="0.30"))
        self.second = operation_usage_receipt_from_row(
            persisted("receipt:2", 2, "MEASURED_PROVIDER_COST", cost="0.15", estimate="0.2"))

    def test_real_queue_receipt_consumer_read_only_attempt_reconciliation(self):
        class Store(QueueExecutionCostStore):
            def run(self, sql, **filters):
                self.last_sql = sql
                self.filters = filters
                return json.dumps([
                    persisted("receipt:1", 1, "ESTIMATED_ONLY", estimate="0.30"),
                    persisted("receipt:2", 2, "MEASURED_PROVIDER_COST", cost="0.15", estimate="0.2"),
                    persisted("receipt:1", 1, "ESTIMATED_ONLY", estimate="0.30"),
                ])

        store = Store()
        rows = store.operation_ledger_receipts(content_id="content:one")
        report = reconcile_operation_billing(rows, (line(), line()))
        self.assertIn("FROM provider_receipt", store.last_sql)
        self.assertEqual(store.filters["content_id"], "content:one")
        self.assertEqual(report.operation_count, 1)
        self.assertEqual(report.attempt_count, 2)
        self.assertEqual(report.duplicate_receipt_replays, 1)
        self.assertEqual(report.duplicate_billing_line_replays, 1)
        self.assertEqual(report.recorded_measured_usd, Decimal("0.15"))
        self.assertEqual(report.provisional_estimated_usd, Decimal("0.30"))
        self.assertEqual(report.matched_unverified_billing_lines, 1)
        self.assertEqual(report.unmatched_billing_lines, 0)
        self.assertEqual(len(report.groups), 1)
        group = report.groups[0]
        self.assertEqual(group.operation_key, "operation:retry")
        self.assertEqual(group.provider_id, "provider:offline")
        self.assertEqual(group.attempt_count, 2)
        self.assertEqual([row.attempt for row in group.attempts], [1, 2])
        self.assertEqual([row.comparison_status for row in group.attempts],
                         ["NO_STATEMENT_LINE", "MATCHED_UNVERIFIED"])
        self.assertEqual(group.attempts[0].provisional_estimated_usd, Decimal("0.30"))
        self.assertIsNone(group.attempts[0].recorded_measured_usd)
        self.assertEqual(group.attempts[1].recorded_measured_usd, Decimal("0.15"))
        self.assertIsNone(group.attempts[1].provisional_estimated_usd)
        self.assertEqual(group.attempts[0].status, "FAILED")
        self.assertEqual(group.attempts[1].status, "SUCCESS")
        self.assertFalse(group.publication_authority)
        self.assertTrue(group.private_only)
        self.assertIsNone(report.authoritative_billed_usd)
        self.assertFalse(report.authorizes_dispatch)
        self.assertFalse(report.invoice_attested)
        self.assertFalse(report.cost_complete)
        self.assertEqual(rows[0].estimated_cost_usd, Decimal("0.30"))

    def test_exact_replays_are_idempotent_but_collisions_fail_closed(self):
        before = aggregate_operation_receipts([self.first, self.second])
        after = aggregate_operation_receipts([self.first, self.second, self.first])
        self.assertEqual(after, before)
        with self.assertRaisesRegex(ValueError, "OPERATION_RECEIPT_REPLAY_CONFLICT"):
            reconcile_operation_billing([self.first, replace(self.first, estimated_cost_usd=Decimal("0.8"))])
        with self.assertRaisesRegex(ValueError, "OPERATION_ATTEMPT_ID_CONFLICT"):
            reconcile_operation_billing([self.first, replace(self.first, receipt_id="receipt:other")])
        with self.assertRaisesRegex(ValueError, "BILLING_LINE_REPLAY_CONFLICT"):
            reconcile_operation_billing([self.second], [line(), line(amount="0.9")])

    def test_invoice_line_comparison_does_not_rewrite_immutable_receipt(self):
        incorrect = line(amount="0.40")
        report = reconcile_operation_billing([self.first, self.second], [incorrect])
        self.assertEqual(report.disputed_billing_lines, 1)
        self.assertEqual(report.groups[0].attempts[1].comparison_status, "AMOUNT_DISPUTED")
        self.assertEqual(report.matched_unverified_billing_lines, 0)
        self.assertEqual(report.recorded_measured_usd, Decimal("0.15"))
        self.assertIsNone(report.authoritative_billed_usd)
        self.assertEqual(self.second.measured_cost_usd, Decimal("0.15"))
        self.assertFalse(report.cost_complete)
        unknown_external = reconcile_operation_billing([self.first], [line()])
        self.assertEqual(unknown_external.unmatched_billing_lines, 1)
        self.assertIsNone(unknown_external.authoritative_billed_usd)

    def test_distinct_invoice_lines_claiming_same_attempt_cannot_fake_multiple_matches(self):
        with self.assertRaisesRegex(ValueError, "BILLING_ATTEMPT_MULTIPLE_LINES_UNVERIFIED"):
            reconcile_operation_billing(
                [self.second], [line(), line(line_id="invoice-line:other")],
            )

    def test_unknown_plan_quota_provisional_and_energy_are_not_faked_money(self):
        rows = [
            operation_usage_receipt_from_row(persisted("receipt:u", 3, "UNKNOWN", estimate="0")),
            operation_usage_receipt_from_row(persisted("receipt:p", 4, "EXTERNAL_PLAN", energy="UNKNOWN")),
            self.first,
        ]
        report = reconcile_operation_billing(rows)
        self.assertEqual(report.unknown_cash_attempts, 2)
        self.assertEqual(report.external_plan_attempts, 1)
        self.assertEqual(report.unknown_energy_attempts, 3)
        self.assertEqual(report.provisional_estimated_usd, Decimal("0.30"))
        self.assertEqual(report.recorded_measured_usd, Decimal("0"))
        self.assertIsNone(report.plan_quota_consumed)
        self.assertIsNone(report.subscription_allocation_eur)
        self.assertIsNone(report.measured_energy_wh)
        self.assertIsNone(report.authoritative_billed_usd)
        self.assertFalse(report.cost_complete)

    def test_unattested_zero_estimate_plan_and_zero_recorded_cost_are_cash_unknown(self):
        rows = [
            operation_usage_receipt_from_row(persisted("receipt:zero-estimate", 1, "ESTIMATED_ONLY", estimate="0")),
            operation_usage_receipt_from_row(persisted("receipt:plan", 2, "EXTERNAL_PLAN")),
            operation_usage_receipt_from_row(persisted("receipt:zero", 3, "ZERO_COST", estimate="0")),
            operation_usage_receipt_from_row(persisted("receipt:zero-measured", 4, "MEASURED_PROVIDER_COST", cost="0")),
        ]
        report = reconcile_operation_billing(rows)
        self.assertEqual(report.unknown_cash_attempts, 4)
        self.assertEqual(report.external_plan_attempts, 1)
        self.assertEqual(report.zero_cost_attempts, 1)
        self.assertEqual(report.recorded_measured_usd, Decimal("0"))
        self.assertEqual(report.provisional_estimated_usd, Decimal("0"))
        self.assertEqual([a.billing_basis for a in report.groups[0].attempts],
                         ["ESTIMATED_ONLY", "EXTERNAL_PLAN", "ZERO_COST", "MEASURED_PROVIDER_COST"])
        self.assertTrue(all(a.cash_uncertainty for a in report.groups[0].attempts))
        self.assertFalse(report.invoice_attested)

    def test_missing_or_unpriced_invoice_foreign_currency_is_not_converted(self):
        report = reconcile_operation_billing([self.second], [line(currency="EUR")])
        self.assertEqual(report.uncomparable_currency_lines, 1)
        self.assertEqual(report.groups[0].attempts[0].comparison_status, "FX_REQUIRED")
        self.assertIsNone(report.authoritative_billed_usd)
        for invalid in ({"source": ""}, {"amount": "NaN"}, {"attempt": 0}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                line(**invalid)

    def test_nonfinite_legacy_amount_cannot_poison_digest_or_become_zero(self):
        for number in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(number=number), self.assertRaises(ValueError):
                operation_usage_receipt_from_row(persisted(
                    "receipt:nonfinite", 1, "ESTIMATED_ONLY", estimate=number))
        with self.assertRaises(ValueError):
            operation_usage_receipt_from_row(persisted("receipt:zero-attempt", 0, "UNKNOWN"))

    def test_operation_key_cannot_group_multiple_provider_identities(self):
        with self.assertRaisesRegex(ValueError, "OPERATION_KEY_SCOPE_CONFLICT"):
            reconcile_operation_billing([
                self.first, replace(self.second, provider_id="other-provider"),
            ])

    def test_grouped_private_report_never_echoes_untrusted_receipt_status_or_body(self):
        poisoned = replace(self.first, status="FAILED: source=https://private.invalid?token=secret")
        output = reconcile_operation_billing([poisoned])
        self.assertEqual(output.groups[0].attempts[0].status, "UNRECOGNIZED_STATUS")
        self.assertNotIn("private.invalid", str(output))
        with self.assertRaisesRegex(ValueError, "OPERATION_RECONCILIATION_IDENTIFIER_INVALID"):
            reconcile_operation_billing([replace(self.first, receipt_id="receipt:secret\nprivate")])


if __name__ == "__main__":
    unittest.main()
