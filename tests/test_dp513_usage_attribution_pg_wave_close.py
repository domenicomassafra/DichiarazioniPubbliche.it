"""DP-513 wave: cross-backend snapshot drift must fail closed on real PG17.

The independent canonical consumer omits private JSON and DP-512 revision
events. A billing event or invisible raw-receipt mutation between readbacks
must not silently produce an apparently current empirical cost report.
"""

from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from dichiarazioni_pubbliche.ops.usage_attribution_pg_v1 import (
    DisposablePgUsageAttribution,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore
from tests import test_dp512_billing_pg_fence_next as fixture


class UsageAttributionWaveClosePgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.BillingPgFenceTests.setUpClass.__func__(cls)
        cls.reader = DisposablePgUsageAttribution(cls.dsn)

    @classmethod
    def tearDownClass(cls):
        fixture.BillingPgFenceTests.tearDownClass.__func__(cls)

    @classmethod
    def sql(cls, query):
        return fixture.BillingPgFenceTests.sql.__func__(cls, query)

    def setUp(self):
        fixture.BillingPgFenceTests.setUp(self)

    def receipt(self, *args, **kwargs):
        return fixture.BillingPgFenceTests.receipt(self, *args, **kwargs)

    def save(self, *args, **kwargs):
        return fixture.BillingPgFenceTests.save(self, *args, **kwargs)

    def consumer(self):
        return QueueExecutionCostStore(self.dsn).operation_ledger_receipts()

    def test_existing_canonical_receipt_stable_two_readbacks_agree(self):
        receipt_id = self.receipt(
            "stable",
            basis="ESTIMATED_ONLY",
            estimate="0.030000",
        )
        self.save(receipt_id, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.03")
        first = self.reader.read()
        self.assertEqual(first, self.reader.read())
        self.assertEqual(first.attempt_count, 1)
        self.assertEqual(first.attempts[0].classification_revision, 1)
        self.assertEqual(first.provisional_estimated_usd, Decimal("0.03"))
        self.assertFalse(first.invoice_attested)

    def test_concurrent_dp512_revision_after_snapshot_does_not_return_stale_report(
        self,
    ):
        receipt_id = self.receipt(
            "racing-event",
            basis="ESTIMATED_ONLY",
            estimate="0.03",
        )
        self.save(receipt_id, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.03")

        def mutate_between_reads():
            # Independently committed PostgreSQL transaction, not a mocked
            # event or a change to the canonical consumer's typed fields.
            with ThreadPoolExecutor(max_workers=1) as pool:
                revision = pool.submit(
                    self.store.record,
                    receipt_id=receipt_id,
                    event_id="event:concurrent",
                    expected_revision=1,
                    asserted_basis="ESTIMATED_ONLY",
                    asserted_usd="0.03",
                    evidence_ref="rate:revised",
                ).result(timeout=10)
            self.assertEqual(revision["revision"], 2)
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=mutate_between_reads)
        reopened = DisposablePgUsageAttribution(self.dsn)
        current = reopened.read()
        self.assertEqual(current.attempt_count, 1)
        self.assertEqual(current.attempts[0].classification_revision, 2)
        self.assertEqual(current.attempts[0].classification_history_count, 2)

    def test_first_dp512_classification_arriving_midread_is_not_ignored(self):
        receipt_id = self.receipt(
            "late-classification",
            basis="ESTIMATED_ONLY",
            estimate="0.01",
        )

        def classify_between_reads():
            self.save(
                receipt_id,
                asserted_basis="ESTIMATED_ONLY",
                asserted_usd="0.01",
            )
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=classify_between_reads)
        current = self.reader.read()
        self.assertEqual(current.attempts[0].classification_revision, 1)

    def test_private_receipt_json_changed_midread_cannot_evade_parity(self):
        self.receipt(
            "private-body",
            basis="UNKNOWN",
            receipt_body="""'{"private_note":"initial private value"}'::jsonb""",
        )

        def update_unprojected_body():
            self.sql(
                "UPDATE provider_receipt SET "
                "receipt=jsonb_set(receipt, '{private_note}', "
                "'\"modified private value\"'::jsonb) "
                "WHERE id='receipt:private-body';"
            )
            return self.consumer()

        # The queue consumer projects neither private_note nor full receipt
        # bytes; its ordinary typed fields are identical across this mutation.
        before = tuple(self.consumer())
        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=update_unprojected_body)
        self.assertEqual(before, tuple(self.consumer()))
        self.assertNotIn("modified private value", repr(self.reader.read()))

    def test_opaque_ledger_scope_mutation_midread_is_detected(self):
        self.receipt("private-scope", basis="UNKNOWN")

        def update_hidden_ledger_scope():
            self.sql(
                "UPDATE provider_receipt SET "
                "ledger_scope=jsonb_set(ledger_scope, '{account_secret}', "
                "'\"private account X\"'::jsonb) "
                "WHERE id='receipt:private-scope';"
            )
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=update_hidden_ledger_scope)
        self.assertNotIn("private account X", repr(self.reader.read()))

    def test_dp512_receipt_event_reference_mutation_during_read_is_detected(self):
        receipt_id = self.receipt(
            "ref-change",
            basis="MEASURED_PROVIDER_COST",
            measured="0.041",
        )
        self.save(
            receipt_id,
            asserted_basis="MEASURED_PROVIDER_COST",
            asserted_usd="0.041",
            evidence_ref="usage:first",
        )

        def add_new_reference():
            self.store.record(
                receipt_id=receipt_id,
                event_id="event:second-reference",
                expected_revision=1,
                asserted_basis="MEASURED_PROVIDER_COST",
                asserted_usd="0.041",
                evidence_ref="usage:second",
            )
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=add_new_reference)
        current = self.reader.read()
        self.assertEqual(current.attempts[0].classification_revision, 2)
        self.assertTrue(current.attempts[0].source_reference_present)
        self.assertFalse(current.invoice_attested)
        self.assertNotIn("usage:second", repr(current))

    def test_normal_canonical_price_mutation_is_still_denied(self):
        receipt_id = self.receipt(
            "price-change",
            basis="ESTIMATED_ONLY",
            estimate="0.04",
        )
        self.save(receipt_id, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.04")

        def alter_price():
            self.sql(
                "UPDATE provider_receipt SET estimated_cost_usd=0.95 "
                "WHERE id='receipt:price-change';"
            )
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=alter_price)
        with self.assertRaisesRegex(ValueError, "CANONICAL_RECEIPT_DRIFT"):
            self.reader.read()

    def test_latest_replayed_correction_is_idempotent_and_not_double_billed(self):
        receipt_id = self.receipt(
            "replay",
            basis="ESTIMATED_ONLY",
            estimate="0.125",
        )
        self.save(receipt_id, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.125")
        correction = self.store.record(
            receipt_id=receipt_id,
            event_id="event:correction",
            expected_revision=1,
            asserted_basis="ESTIMATED_ONLY",
            asserted_usd="0.125",
            evidence_ref="quote:revision",
        )
        self.assertEqual(
            self.store.record(
                receipt_id=receipt_id,
                event_id="event:correction",
                expected_revision=1,
                asserted_basis="ESTIMATED_ONLY",
                asserted_usd="0.125",
                evidence_ref="quote:revision",
            ),
            correction,
        )
        result = DisposablePgUsageAttribution(self.dsn).read()
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(result.attempts[0].classification_revision, 2)
        self.assertEqual(result.attempts[0].classification_history_count, 2)
        self.assertEqual(result.provisional_estimated_usd, Decimal("0.125"))
        self.assertFalse(result.dispatch_authorized)

    def test_receipts_without_dp512_events_are_current_only_if_unmodified(self):
        self.receipt("unclassified", basis="UNKNOWN")
        first = self.reader.read()
        self.assertEqual(first.attempts[0].classification_revision, 0)
        self.assertEqual(first.unknown_cash_attempts, 1)

        def changed_raw_unclassified():
            self.sql(
                "UPDATE provider_receipt SET "
                'receipt=\'{"unpriced":"private raw edit"}\'::jsonb '
                "WHERE id='receipt:unclassified';"
            )
            return self.consumer()

        with self.assertRaisesRegex(ValueError, "CANONICAL_READ_DRIFT"):
            self.reader.read(_consumer=changed_raw_unclassified)
        second = self.reader.read()
        self.assertEqual(second.unknown_cash_attempts, 1)
        self.assertEqual(second.attempts[0].classification_revision, 0)

    def test_postgresql_immutable_dp512_history_cannot_be_forged_in_place(self):
        receipt_id = self.receipt(
            "append-only",
            basis="ESTIMATED_ONLY",
            estimate="0.02",
        )
        self.save(receipt_id, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.02")
        with self.assertRaisesRegex(Exception, "append-only"):
            self.sql(
                "UPDATE dp512_pg_event SET asserted_basis='UNKNOWN' "
                "WHERE event_id='event:first';"
            )
        original = self.reader.read()
        self.assertEqual(original.attempt_count, 1)
        self.assertEqual(original.attempts[0].billing_basis, "ESTIMATED_ONLY")
        self.assertEqual(original.attempts[0].classification_revision, 1)


if __name__ == "__main__":
    unittest.main()
