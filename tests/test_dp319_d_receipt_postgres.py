"""DP-319C: verify zero-provider D accounting in an actual disposable PG ledger."""

from __future__ import annotations

import dataclasses
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests import test_dp512_worker_budget_reservations as fixture
from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (
    InvestigationReservation,
    InvestigationSourceRecord,
)
from dichiarazioni_pubbliche.private_investigation_d_receipt import (
    PrivateDReceiptLedger,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore


class DReceiptPostgresTests(unittest.TestCase):
    # Reuse the existing disposable PostgreSQL cluster fixture without
    # inheriting/re-running its unrelated worker tests.
    setUpClass = classmethod(fixture.WorkerBudgetReservationPgTests.setUpClass.__func__)
    tearDownClass = classmethod(
        fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__
    )
    exec_sql = classmethod(fixture.WorkerBudgetReservationPgTests.exec_sql.__func__)
    setUp = fixture.WorkerBudgetReservationPgTests.setUp
    scalar = fixture.WorkerBudgetReservationPgTests.scalar

    def source_and_attempt(self, suffix="a"):
        sha = "a" * 64
        source = InvestigationSourceRecord(
            need_id="need:dp319-pg",
            source_id="source:test",
            candidate_id="candidate:dp319-pg",
            material_fingerprint="sha256:" + sha,
            source_version="capture:version-" + suffix,
            source_sha256=sha,
            rights_status="CLEARED",
            policy_status="ALLOWED",
            revision=1,
        )
        attempt = InvestigationReservation(
            attempt_id="attempt:pg-" + suffix,
            assignment_id="assignment:pg",
            lane="OFFICIAL_STRUCTURED",
            material_fingerprint=source.material_fingerprint,
            plan_fingerprint="b" * 64,
            source_id=source.source_id,
            candidate_id=source.candidate_id,
            source_version=source.source_version,
            source_sha256=source.source_sha256,
            source_revision=1,
            key="dp319-pg",
        )
        return source, attempt

    def write(self, suffix="a", *, rights="private-rights:pg"):
        source, attempt = self.source_and_attempt(suffix)
        return PrivateDReceiptLedger(self.dsn).record_zero_attempt(
            attempt=attempt,
            source=source,
            content_id="content:test",
            rights_record_id=rights,
        )

    def test_exact_zero_request_replay_survives_new_client_and_is_in_d_ledger(self):
        receipt_id = self.write()
        self.assertEqual(self.write(), receipt_id)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "1")
        self.assertEqual(self.scalar("SELECT request_count FROM provider_receipt"), "0")
        self.assertEqual(
            self.scalar(
                "SELECT receipt->>'quota_units_consumed' FROM provider_receipt"
            ),
            "0",
        )
        self.assertEqual(
            self.scalar("SELECT billing_basis FROM provider_receipt"), "ZERO_COST"
        )
        rows = QueueRuntimeStore(self.dsn).operation_ledger_receipts(
            content_id="content:test", operation="DP319_PRIVATE_SOURCE_INSPECTION"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].receipt_id, receipt_id)
        self.assertEqual(rows[0].request_count, 0)
        self.assertEqual(rows[0].operation, "DP319_PRIVATE_SOURCE_INSPECTION")

    def test_conflicting_grant_cannot_replace_immutable_receipt(self):
        initial = self.write()
        with self.assertRaisesRegex(ValueError, "DP319_D_RECEIPT_CONFLICT"):
            self.write(rights="private-rights:revoked")
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "1")
        self.assertEqual(
            self.scalar("SELECT receipt->>'rights_record_id' FROM provider_receipt"),
            "private-rights:pg",
        )
        self.assertEqual(self.write(), initial)

    def test_parallel_replay_and_new_source_version_preserve_old_receipt(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            repeated = list(pool.map(lambda _: self.write(), (1, 2)))
        self.assertEqual(repeated[0], repeated[1])
        newer = self.write("b")
        self.assertNotEqual(repeated[0], newer)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "2")

    def test_source_mutation_fails_before_a_postgres_write(self):
        source, attempt = self.source_and_attempt()
        with self.assertRaisesRegex(ValueError, "DP319_D_SOURCE_RESERVATION_MISMATCH"):
            PrivateDReceiptLedger(self.dsn).record_zero_attempt(
                attempt=dataclasses.replace(attempt, source_sha256="c" * 64),
                source=source,
                content_id="content:test",
                rights_record_id="private-rights:pg",
            )
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")

    def test_revoked_source_and_dispatch_right_cannot_create_a_zero_receipt(self):
        source, attempt = self.source_and_attempt()
        with self.assertRaisesRegex(ValueError, "DP319_D_SOURCE_RESERVATION_MISMATCH"):
            PrivateDReceiptLedger(self.dsn).record_zero_attempt(
                attempt=attempt,
                source=dataclasses.replace(source, rights_status="REVOKED"),
                content_id="content:test",
                rights_record_id="private-rights:revoked",
            )
        with self.assertRaisesRegex(ValueError, "DP319_D_SOURCE_RESERVATION_MISMATCH"):
            PrivateDReceiptLedger(self.dsn).record_zero_attempt(
                attempt=dataclasses.replace(attempt, dispatch_authorized=True),
                source=source,
                content_id="content:test",
                rights_record_id="private-rights:pg",
            )
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")
