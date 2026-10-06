import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.operation_ledger import (  # noqa: E402
    OperationUsageReceipt,
    aggregate_operation_receipts,
    deterministic_operation_key,
    filter_operation_receipts,
    operation_usage_receipt_from_row,
)


def receipt(
    key,
    attempt,
    basis,
    *,
    measured=None,
    estimated=None,
    provider="provider:a",
    claim_id="claim:1",
):
    return OperationUsageReceipt(
        receipt_id=f"receipt:{key}:{attempt}",
        operation_key=key,
        attempt=attempt,
        provider_id=provider,
        model_id="model:test",
        operation="CLAIM_EXTRACT",
        status="SUCCESS",
        billing_basis=basis,
        measured_cost_usd=None if measured is None else Decimal(str(measured)),
        estimated_cost_usd=None if estimated is None else Decimal(str(estimated)),
        total_tokens=100,
        request_count=1,
        claim_id=claim_id,
    )


class OperationLedgerTests(unittest.TestCase):
    def test_operation_key_is_stable_and_provider_model_scoped(self):
        first = deterministic_operation_key(
            operation="CLAIM_EXTRACT",
            input_fingerprint="abc",
            provider_id="provider:a",
            model_id="model:1",
        )
        same = deterministic_operation_key(
            operation="CLAIM_EXTRACT",
            input_fingerprint="abc",
            provider_id="provider:a",
            model_id="model:1",
        )
        changed = deterministic_operation_key(
            operation="CLAIM_EXTRACT",
            input_fingerprint="abc",
            provider_id="provider:a",
            model_id="model:2",
        )
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)

    def test_aggregate_separates_measured_estimated_external_and_unknown(self):
        rows = [
            receipt("op:1", 1, "MEASURED_PROVIDER_COST", measured="0.10"),
            receipt("op:2", 1, "ESTIMATED_ONLY", estimated="0.20"),
            receipt("op:3", 1, "EXTERNAL_PLAN"),
            receipt("op:4", 1, "UNKNOWN"),
            receipt("op:5", 1, "ZERO_COST", estimated="0"),
        ]
        summary = aggregate_operation_receipts(rows)
        self.assertEqual(summary.measured_cost_usd, Decimal("0.10"))
        self.assertEqual(summary.estimated_only_cost_usd, Decimal("0.20"))
        self.assertEqual(summary.external_plan_operation_count, 1)
        self.assertEqual(summary.unknown_cost_operation_count, 1)
        self.assertEqual(summary.zero_cost_operation_count, 1)
        self.assertFalse(summary.cost_complete)

    def test_retry_attempts_are_visible_without_inflating_operation_count(self):
        rows = [
            receipt("op:1", 1, "UNKNOWN"),
            receipt("op:1", 2, "MEASURED_PROVIDER_COST", measured="0.15"),
        ]
        summary = aggregate_operation_receipts(rows)
        self.assertEqual(summary.operation_count, 1)
        self.assertEqual(summary.attempt_count, 2)
        self.assertEqual(summary.measured_cost_usd, Decimal("0.15"))
        self.assertEqual(summary.unknown_cost_operation_count, 1)

    def test_unknown_is_not_zero(self):
        summary = aggregate_operation_receipts([receipt("op:1", 1, "UNKNOWN")])
        self.assertEqual(summary.measured_cost_usd, Decimal("0"))
        self.assertEqual(summary.unknown_cost_operation_count, 1)
        self.assertFalse(summary.cost_complete)

    def test_filter_supports_claim_and_provider_dimensions(self):
        rows = [
            receipt("op:1", 1, "UNKNOWN", provider="provider:a", claim_id="claim:1"),
            receipt("op:2", 1, "UNKNOWN", provider="provider:b", claim_id="claim:2"),
        ]
        filtered = filter_operation_receipts(
            rows,
            claim_id="claim:1",
            provider_id="provider:a",
        )
        self.assertEqual([row.operation_key for row in filtered], ["op:1"])

    def test_persisted_legacy_row_gets_explicit_legacy_key_and_unknown_cost(self):
        row = operation_usage_receipt_from_row(
            {
                "id": "receipt:legacy",
                "operation_key": None,
                "attempt": 1,
                "provider_id": "provider:a",
                "model_id": None,
                "operation": "LEGACY_CALL",
                "status": "SUCCESS",
                "billing_basis": "ESTIMATED_ONLY",
                "estimated_cost_usd": None,
                "request_count": 1,
            }
        )
        self.assertEqual(row.operation_key, "legacy:receipt:legacy")
        self.assertEqual(row.billing_basis, "UNKNOWN")

    def test_persisted_measured_row_keeps_measured_basis(self):
        row = operation_usage_receipt_from_row(
            {
                "id": "receipt:1",
                "operation_key": "provider-operation:1",
                "attempt": 2,
                "provider_id": "provider:a",
                "model_id": "model:a",
                "operation": "CLAIM_EXTRACT",
                "status": "SUCCESS",
                "billing_basis": "MEASURED_PROVIDER_COST",
                "estimated_cost_usd": "0.20",
                "measured_cost_usd": "0.12",
                "total_tokens": 321,
                "request_count": 1,
                "content_id": "content:1",
                "source_id": "source:1",
                "started_at": "2026-10-05T12:00:00+00:00",
                "completed_at": "2026-10-05T12:00:02+00:00",
                "duration_seconds": "2.0",
            }
        )
        self.assertEqual(row.attempt, 2)
        self.assertEqual(row.measured_cost_usd, Decimal("0.12"))
        self.assertEqual(row.total_tokens, 321)
        self.assertEqual(row.model_id, "model:a")
        self.assertEqual(row.duration_seconds, Decimal("2.0"))


if __name__ == "__main__":
    unittest.main()
