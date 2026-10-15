"""DP-512: canonical provider_receipt + disposable PostgreSQL classification CAS."""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from tests.test_claim_evidence_retrieval_replay import _bin, _cmd  # noqa: E402
from dichiarazioni_pubbliche.ops.billing_pg_fence_v1 import (  # noqa: E402
    DisposableBillingPgFence,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore  # noqa: E402
from dichiarazioni_pubbliche.operation_ledger import (  # noqa: E402
    reconcile_operation_billing,
)
from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    preflight,
    BudgetPolicy,
    CostSnapshot,
)


class BillingPgFenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for item in ("initdb", "pg_ctl", "psql"):
            _bin(item)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp512-billing-pg-")
        cls.data = Path(cls.tmp.name) / "pg"
        cls.ctl = _bin("pg_ctl")
        cls.started = False
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                cls.port = sock.getsockname()[1]
            _cmd(
                [
                    _bin("initdb"),
                    "-D",
                    str(cls.data),
                    "--username=postgres",
                    "--auth=trust",
                    "--no-locale",
                    "--encoding=UTF8",
                ]
            )
            _cmd(
                [
                    cls.ctl,
                    "-D",
                    str(cls.data),
                    "-l",
                    str(Path(cls.tmp.name) / "pg.log"),
                    "-o",
                    f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}",
                    "-w",
                    "start",
                ]
            )
            cls.started = True
            cls.admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            _cmd(
                [_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.admin],
                stdin="CREATE DATABASE dp512_test_billing;",
            )
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp512_test_billing"
            _cmd(
                [_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
                stdin=(ROOT / "db" / "schema.v1.sql").read_text(),
            )
            cls.store = DisposableBillingPgFence(cls.dsn)
            cls.store.install_disposable_schema()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            _cmd([cls.ctl, "-D", str(cls.data), "-m", "immediate", "-w", "stop"])
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def sql(cls, query):
        return _cmd(
            [
                _bin("psql"),
                "-X",
                "-q",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                cls.dsn,
            ],
            stdin=query,
        )

    def setUp(self):
        self.sql("TRUNCATE dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;")

    def receipt(
        self,
        suffix,
        *,
        basis="UNKNOWN",
        estimate=None,
        measured=None,
        attempt=1,
        operation_key="operation:one",
        status="FAILED",
        provider="provider:fixture",
        receipt_body="'{}'::jsonb",
    ):
        def amount(value):
            return "NULL" if value is None else str(Decimal(str(value)))

        self.sql(
            "INSERT INTO provider_receipt "
            "(id, provider_id, model_id, operation, operation_key, attempt, "
            " billing_basis, estimated_cost_usd, measured_cost_usd, "
            " status, receipt, started_at, completed_at) VALUES "
            f"('receipt:{suffix}', '{provider}', 'model:local', 'CLAIM_EXTRACT', "
            f" '{operation_key}', {attempt}, '{basis}', {amount(estimate)}, "
            f" {amount(measured)}, '{status}', {receipt_body}, "
            " '2026-10-12 00:00:00+00', '2026-10-12 00:01:00+00');"
        )
        return f"receipt:{suffix}"

    def save(self, receipt_id, **changes):
        args = dict(
            receipt_id=receipt_id,
            event_id="event:first",
            expected_revision=0,
            asserted_basis="UNKNOWN",
            asserted_usd=None,
            evidence_ref=None,
        )
        return self.store.record(**(args | changes))

    def test_unknown_zero_ceiling_is_not_zero_billed_or_dispatchable(self):
        key = self.receipt("unknown", estimate=0)
        result = self.save(key)
        self.assertEqual(result["basis"], "UNKNOWN")
        self.assertIsNone(result["recorded_usd"])
        self.assertEqual(result["cash_status"], "UNPRICED")
        self.assertFalse(result["invoice_attested"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_event"), "1")
        self.assertFalse(
            preflight(
                BudgetPolicy(), CostSnapshot(0, 0), None, operation="CLAIM_EXTRACT"
            ).allowed
        )

    def test_estimated_zero_is_still_estimated_not_verified_free(self):
        key = self.receipt("estimated", basis="ESTIMATED_ONLY", estimate="0")
        result = self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0")
        self.assertEqual(result["basis"], "ESTIMATED_ONLY")
        self.assertEqual(result["recorded_usd"], "0.000000")
        self.assertFalse(result["invoice_attested"])
        self.assertFalse(result["zero_cost_verified"])

    def test_external_plan_does_not_gain_monetary_bill_or_quoted_entitlement(self):
        key = self.receipt(
            "plan",
            basis="EXTERNAL_PLAN",
            receipt_body="""'{"local_energy_basis":"UNKNOWN",
            "plan_quota_units":12,"scope":"PRIVATE ACCOUNT"}'::jsonb""",
        )
        result = self.save(key, asserted_basis="EXTERNAL_PLAN")
        self.assertEqual(result["cash_status"], "PLAN_ENTITLEMENT_UNVERIFIED")
        self.assertEqual(result["local_energy_basis"], "UNKNOWN")
        self.assertIsNone(result["recorded_usd"])
        self.assertFalse(result["invoice_attested"])
        self.assertNotIn("PRIVATE ACCOUNT", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "BILLING_CLASSIFICATION_CONFLICT"):
            self.save(key, asserted_basis="EXTERNAL_PLAN", asserted_usd="0")

    def test_untrusted_local_energy_basis_never_leaks_private_receipt(self):
        # A historic provider receipt is immutable but its nested energy label
        # is untrusted. Only canonical labels may leave the private PG store.
        for suffix, raw_basis in (
            ("private-energy", "PRIVATE_TOKEN_PROVIDER_USAGE_VALUE"),
            ("legacy-energy", "LOCAL_COMPUTE_UNMETERED"),
        ):
            key = self.receipt(
                suffix, operation_key=f"operation:{suffix}",
                receipt_body=f"'{json.dumps({'local_energy_basis': raw_basis})}'::jsonb",
            )
            outcome = self.save(key, event_id=f"event:{suffix}")
            self.assertEqual(outcome["local_energy_basis"], "UNKNOWN")
            self.assertNotIn(raw_basis, json.dumps(outcome))
            self.assertFalse(outcome["dispatch_authorized"])
            self.assertFalse(outcome["invoice_attested"])
            self.assertEqual(
                self.sql("SELECT receipt->>'local_energy_basis' "
                         f"FROM provider_receipt WHERE id='receipt:{suffix}'"),
                raw_basis,
            )

    def test_canonical_local_energy_labels_still_roundtrip(self):
        for suffix, energy_basis in (
            ("unknown-energy", "UNKNOWN"),
            ("estimated-energy", "ESTIMATED"),
            ("measured-energy", "MEASURED"),
        ):
            key = self.receipt(
                suffix, operation_key=f"operation:{suffix}",
                receipt_body=f"'{json.dumps({'local_energy_basis': energy_basis})}'::jsonb",
            )
            result = self.save(key, event_id=f"event:{suffix}")
            self.assertEqual(result["local_energy_basis"], energy_basis)
            self.assertIsNone(result["recorded_usd"])
            self.assertFalse(result["invoice_attested"])
            self.assertFalse(result["dispatch_authorized"])

    def test_measured_requires_raw_canonical_measured_and_source_reference(self):
        key = self.receipt(
            "measured",
            basis="MEASURED_PROVIDER_COST",
            estimate="0.06",
            measured="0.041",
            status="SUCCEEDED",
        )
        with self.assertRaisesRegex(ValueError, "BILLING_PROVENANCE_REQUIRED"):
            self.save(
                key, asserted_basis="MEASURED_PROVIDER_COST", asserted_usd="0.041"
            )
        result = self.save(
            key,
            asserted_basis="MEASURED_PROVIDER_COST",
            asserted_usd="0.041",
            evidence_ref="provider-usage:fixture:line-1",
        )
        self.assertEqual(result["basis"], "MEASURED_PROVIDER_COST")
        self.assertEqual(result["recorded_usd"], "0.041000")
        self.assertEqual(result["cash_status"], "RECORDED_MEASURED_UNVERIFIED")
        self.assertFalse(result["invoice_attested"])
        self.assertNotIn("provider-usage:fixture", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "BILLING_CLASSIFICATION_CONFLICT"):
            self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.06")

    def test_estimate_cannot_be_upgraded_with_forged_invoice_line(self):
        key = self.receipt("quote", basis="ESTIMATED_ONLY", estimate="0.02")
        with self.assertRaisesRegex(ValueError, "BILLING_CLASSIFICATION_CONFLICT"):
            self.save(
                key,
                asserted_basis="MEASURED_PROVIDER_COST",
                asserted_usd="0.02",
                evidence_ref="invoice:invented",
            )
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_event"), "0")

    def test_failed_then_success_retry_are_two_receipts_one_operation(self):
        first = self.receipt("failed", basis="UNKNOWN", attempt=1)
        second = self.receipt(
            "successful",
            basis="ESTIMATED_ONLY",
            estimate="0.05",
            attempt=2,
            status="SUCCEEDED",
        )
        self.save(first)
        self.save(
            second,
            event_id="event:second",
            asserted_basis="ESTIMATED_ONLY",
            asserted_usd="0.05",
        )
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_state"), "2")
        reader = QueueExecutionCostStore(self.dsn)
        canonical = tuple(reader.operation_ledger_receipts())
        aggregation = reconcile_operation_billing(canonical)
        self.assertEqual(aggregation.attempt_count, 2)
        self.assertEqual(aggregation.operation_count, 1)
        self.assertEqual(aggregation.unknown_cash_attempts, 1)
        self.assertEqual(aggregation.provisional_estimated_usd, Decimal("0.05"))

    def test_restart_idempotent_event_and_append_only_correction_cas(self):
        key = self.receipt("restart", basis="ESTIMATED_ONLY", estimate="0.03")
        args = dict(asserted_basis="ESTIMATED_ONLY", asserted_usd="0.03")
        first = self.save(key, **args)
        restarted = DisposableBillingPgFence(self.dsn)
        self.assertEqual(
            restarted.record(
                receipt_id=key,
                event_id="event:first",
                expected_revision=0,
                evidence_ref=None,
                **args,
            ),
            first,
        )
        correction = restarted.record(
            receipt_id=key,
            event_id="event:correction",
            expected_revision=1,
            evidence_ref="rate:amended",
            **args,
        )
        self.assertEqual(correction["revision"], 2)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_event"), "2")
        with self.assertRaisesRegex(ValueError, "BILLING_REVISION_CONFLICT"):
            restarted.record(
                receipt_id=key,
                event_id="event:new",
                expected_revision=1,
                evidence_ref=None,
                **args,
            )
        with self.assertRaisesRegex(Exception, "append-only"):
            self.sql("UPDATE dp512_pg_event SET asserted_basis='UNKNOWN';")

    def test_competing_clients_same_expected_revision_one_winner(self):
        key = self.receipt("race", basis="ESTIMATED_ONLY", estimate="0.01")

        def attempt(n):
            try:
                return DisposableBillingPgFence(self.dsn).record(
                    receipt_id=key,
                    event_id=f"event:race:{n}",
                    expected_revision=0,
                    asserted_basis="ESTIMATED_ONLY",
                    asserted_usd="0.01",
                    evidence_ref=None,
                )["revision"]
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = {
                x.result(timeout=15)
                for x in (pool.submit(attempt, 1), pool.submit(attempt, 2))
            }
        self.assertEqual(outcomes, {1, "BILLING_REVISION_CONFLICT"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_event"), "1")

    def test_duplicate_canonical_attempt_fails_closed_even_different_receipt_id(self):
        first = self.receipt("a", basis="UNKNOWN")
        self.receipt("b", basis="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "BILLING_CANONICAL_ATTEMPT_AMBIGUOUS"):
            self.save(first)

    def test_same_event_id_cannot_be_reused_for_other_attempt_or_cost(self):
        first = self.receipt("first", basis="ESTIMATED_ONLY", estimate="0.02")
        second = self.receipt(
            "second", basis="ESTIMATED_ONLY", estimate="0.03", attempt=2
        )
        self.save(first, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.02")
        with self.assertRaisesRegex(ValueError, "BILLING_EVENT_REPLAY_CONFLICT"):
            self.save(second, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.03")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_state"), "1")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_event"), "1")

    def test_bad_decimal_nan_precision_and_negative_do_not_touch_canonical(self):
        key = self.receipt("invalid", basis="UNKNOWN")
        for amount in ("NaN", "Infinity", "-0.01", "0.0000009"):
            with (
                self.subTest(amount=amount),
                self.assertRaisesRegex(ValueError, "BILLING_AMOUNT_"),
            ):
                self.save(key, asserted_usd=amount)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp512_pg_state"), "0")

    def test_raw_receipt_mutation_after_snapshot_requires_new_review(self):
        key = self.receipt("drift", basis="ESTIMATED_ONLY", estimate="0.05")
        self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.05")
        self.sql(
            "UPDATE provider_receipt SET status='FAILED_AFTER_REVIEW' "
            "WHERE id='receipt:drift'"
        )
        with self.assertRaisesRegex(ValueError, "BILLING_ORIGINAL_DRIFT"):
            self.save(key, asserted_basis="ESTIMATED_ONLY", asserted_usd="0.05")

    def test_original_receipt_and_private_output_are_redacted(self):
        key = self.receipt(
            "private",
            receipt_body="""'{"secret":"PROMPT SECRET",
            "token":"API KEY","source_url":"https://private"}'::jsonb""",
        )
        outcome = self.save(key)
        self.assertNotIn("PROMPT SECRET", json.dumps(outcome))
        self.assertNotIn("API KEY", json.dumps(outcome))
        self.assertNotIn("https://private", json.dumps(outcome))
        self.assertEqual(
            self.sql(
                "SELECT receipt->>'secret' FROM "
                "provider_receipt WHERE id='receipt:private'"
            ),
            "PROMPT SECRET",
        )

    def test_measured_charge_refund_and_correction_are_immutable_cas_events(self):
        key = self.receipt("adjust", basis="MEASURED_PROVIDER_COST",
                           measured="0.40", status="SUCCEEDED")
        self.save(key, asserted_basis="MEASURED_PROVIDER_COST",
                  asserted_usd="0.40", evidence_ref="usage:synthetic")
        before = self.sql("SELECT md5(json_agg(r ORDER BY id)::text) FROM provider_receipt r")
        first = self.store.adjust(
            receipt_id=key, event_id="adjust:refund", expected_revision=1,
            adjustment_kind="REFUND", amount_usd="0.10",
            evidence_ref="statement:refund-1",
        )
        self.assertEqual(first["revision"], 2)
        self.assertEqual(first["unverified_net_recorded_usd"], "0.300000")
        self.assertFalse(first["invoice_attested"])
        self.assertFalse(first["cash_settled"])
        self.assertFalse(first["dispatch_authorized"])
        reopened = DisposableBillingPgFence(self.dsn)
        self.assertEqual(first, reopened.adjust(
            receipt_id=key, event_id="adjust:refund", expected_revision=1,
            adjustment_kind="REFUND", amount_usd="0.10",
            evidence_ref="statement:refund-1",
        ))
        second = reopened.adjust(
            receipt_id=key, event_id="adjust:correction", expected_revision=2,
            adjustment_kind="CORRECTION_UP", amount_usd="0.05",
            evidence_ref="statement:correction-1",
        )
        self.assertEqual(second["unverified_net_recorded_usd"], "0.350000")
        self.assertEqual(self.sql("SELECT count(*) FROM dp512_pg_adjustment"), "2")
        self.assertEqual(before, self.sql(
            "SELECT md5(json_agg(r ORDER BY id)::text) FROM provider_receipt r"))
        self.assertNotIn("statement:refund-1", json.dumps(first))
        with self.assertRaisesRegex(Exception, "append-only"):
            self.sql("UPDATE dp512_pg_adjustment SET amount_usd=0.01;")

    def test_refund_requires_recorded_measured_parent_provenance_and_nonnegative_net(self):
        unknown = self.receipt("unbilled", basis="UNKNOWN")
        self.save(unknown)
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_MEASURED_REQUIRED"):
            self.store.adjust(receipt_id=unknown, event_id="adjust:unbilled",
                              expected_revision=1, adjustment_kind="REFUND",
                              amount_usd="0.01", evidence_ref="statement:refund")
        key = self.receipt("bounded", basis="MEASURED_PROVIDER_COST",
                           measured="0.10", attempt=2)
        self.save(key, event_id="event:bounded",
                  asserted_basis="MEASURED_PROVIDER_COST",
                  asserted_usd="0.10", evidence_ref="usage:bounded")
        def adjust(event="adjust:bad", revision=1, kind="REFUND",
                   amount="0.01", evidence="statement:refund"):
            return self.store.adjust(
                receipt_id=key, event_id=event, expected_revision=revision,
                adjustment_kind=kind, amount_usd=amount, evidence_ref=evidence)
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_UNDERFLOW"):
            adjust(amount="0.11")
        for amount in ("0", "-0.01", "NaN", "0.0000001"):
            with self.subTest(amount=amount), self.assertRaisesRegex(
                ValueError, "BILLING_AMOUNT_"
            ):
                adjust(amount=amount)
        with self.assertRaisesRegex(ValueError, "BILLING_EVIDENCE_REFERENCE_INVALID"):
            adjust(evidence="")
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_KIND_INVALID"):
            adjust(kind="FAKE_PAYMENT")
        first = adjust(amount="0.08", event="adjust:real")
        self.assertEqual(first["unverified_net_recorded_usd"], "0.020000")
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_REPLAY_CONFLICT"):
            adjust(amount="0.07", event="adjust:real")
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_REFERENCE_REUSED"):
            adjust(amount="0.01", event="adjust:other", revision=2)
        with self.assertRaisesRegex(ValueError, "BILLING_ADJUSTMENT_REFERENCE_REUSED"):
            adjust(amount="0.01", event="adjust:alternate-kind", revision=2,
                   kind="CORRECTION_DOWN")
        self.assertEqual(self.sql("SELECT count(*) FROM dp512_pg_adjustment"), "1")

    def test_competing_adjustments_same_revision_only_one_commits(self):
        key = self.receipt("refund-race", basis="MEASURED_PROVIDER_COST",
                           measured="0.10", status="SUCCEEDED")
        self.save(key, asserted_basis="MEASURED_PROVIDER_COST",
                  asserted_usd="0.10", evidence_ref="usage:race")
        def adjust(n):
            try:
                return DisposableBillingPgFence(self.dsn).adjust(
                    receipt_id=key, event_id=f"adjust:race:{n}",
                    expected_revision=1, adjustment_kind="REFUND",
                    amount_usd="0.06", evidence_ref=f"statement:race:{n}",
                )["revision"]
            except ValueError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = {future.result(timeout=20) for future in (
                pool.submit(adjust, 1), pool.submit(adjust, 2))}
        self.assertEqual(outcomes, {2, "BILLING_REVISION_CONFLICT"})
        self.assertEqual(self.sql("SELECT count(*) FROM dp512_pg_adjustment"), "1")

    def test_disposable_client_rejects_password_embedded_in_psql_argv_dsn(self):
        # The psql subprocess receives -d with the DSN in its command-line
        # arguments. Database credentials belong in libpq's native store,
        # not a process listing or the model-visible command transcript.
        with self.assertRaisesRegex(ValueError, "BILLING_DISPOSABLE_DSN_REQUIRED"):
            DisposableBillingPgFence(
                "postgresql://postgres:private-password@127.0.0.1:5432/"
                "dp512_test_billing"
            )


if __name__ == "__main__":
    unittest.main()
