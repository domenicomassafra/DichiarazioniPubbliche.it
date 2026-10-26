"""DP-319C2: durable subscription dispatch at the public PostgreSQL seam."""

import dataclasses
import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from tests import test_dp512_worker_budget_reservations as fixture
from tests.test_dp319_d_receipt_postgres import DReceiptPostgresTests
from dichiarazioni_pubbliche.private_investigation_subscription_d import (
    SubscriptionDDispatch,
    SubscriptionGate,
)


class SubscriptionDPgTests(unittest.TestCase):
    setUpClass = classmethod(fixture.WorkerBudgetReservationPgTests.setUpClass.__func__)
    tearDownClass = classmethod(
        fixture.WorkerBudgetReservationPgTests.tearDownClass.__func__
    )
    exec_sql = classmethod(fixture.WorkerBudgetReservationPgTests.exec_sql.__func__)
    setUp = fixture.WorkerBudgetReservationPgTests.setUp
    scalar = fixture.WorkerBudgetReservationPgTests.scalar
    source_and_attempt = DReceiptPostgresTests.source_and_attempt

    def gate(self, **changes):
        accounts = tuple(
            hashlib.sha256(f"subscription-{n}".encode()).hexdigest() for n in range(12)
        )
        baseline = SubscriptionGate(
            model="antigravity/gemini-3.8-flash-tiered",
            account_scope="subscription:approved-12",
            authorized_connection_fingerprints=accounts,
            observed_connection_fingerprints=accounts,
            subscription_only=True,
            paid_fallback_disabled=True,
            quota_remaining=10,
            quota_upper_bound=3,
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=10),
            evidence_ref="operator-private:omniroute-readback-1",
        )
        return dataclasses.replace(baseline, **changes)

    def dispatch(
        self,
        *,
        gate=None,
        rights=lambda: True,
        provider=None,
        suffix="a",
        verified=lambda _: True,
        authorized=True,
        plan_fingerprint=None,
    ):
        source, attempt = self.source_and_attempt(suffix)
        attempt = dataclasses.replace(
            attempt,
            dispatch_authorized=authorized,
            plan_fingerprint=plan_fingerprint or attempt.plan_fingerprint,
        )
        return SubscriptionDDispatch(self.dsn).run_once(
            source=source,
            attempt=attempt,
            content_id="content:test",
            rights_record_id="private-rights:pg",
            gate=self.gate() if gate is None else gate,
            current_rights=rights,
            send=provider if provider is not None else self.reply,
            verify_usage_evidence=verified,
        )

    def reply(self):
        return {
            "id": "req-from-omniroute",
            "model": "antigravity/gemini-3.8-flash-tiered",
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            "quota": {
                "units_consumed": 2,
                "unit": "subscription-quota-unit",
                "receipt_ref": "provider-usage:verified-1",
            },
        }

    def test_zero_capacity_revocation_and_unverified_route_prevent_any_dispatch(self):
        for gate, rights, expected in (
            (
                self.gate(quota_remaining=0),
                lambda: True,
                "SUBSCRIPTION_QUOTA_EXHAUSTED",
            ),
            (
                self.gate(quota_remaining=None),
                lambda: True,
                "SUBSCRIPTION_QUOTA_UNATTESTED",
            ),
            (
                self.gate(
                    observed_connection_fingerprints=self.gate().observed_connection_fingerprints[
                        :-1
                    ]
                ),
                lambda: True,
                "SUBSCRIPTION_ROUTE_UNVERIFIED",
            ),
            (
                self.gate(paid_fallback_disabled=False),
                lambda: True,
                "SUBSCRIPTION_ROUTE_UNVERIFIED",
            ),
            (self.gate(), lambda: False, "SOURCE_RIGHTS_REVOKED"),
        ):
            with self.subTest(expected=expected):
                outcome = self.dispatch(
                    gate=gate,
                    rights=rights,
                    provider=lambda: self.fail("provider called"),
                )
                self.assertEqual(
                    (outcome.status, outcome.reason_code), ("WAIT_EXTERNAL", expected)
                )
                self.assertFalse(outcome.dispatch_authorized)
                self.assertEqual(outcome.new_child_task_count, 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")

    def test_unapproved_attempt_cannot_dispatch_despite_available_quota(self):
        outcome = self.dispatch(
            authorized=False, provider=lambda: self.fail("unauthorized dispatch")
        )
        self.assertEqual(outcome.status, "WAIT_EXTERNAL")
        self.assertEqual(
            outcome.reason_code, "SUBSCRIPTION_SOURCE_RESERVATION_MISMATCH"
        )
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "0")

    def test_one_dispatch_across_clients_and_restart_returns_same_receipt(self):
        calls = []

        def send():
            calls.append(1)
            return self.reply()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: self.dispatch(provider=send), (1, 2)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "1")
        self.assertEqual(self.scalar("SELECT total_tokens FROM provider_receipt"), "10")
        self.assertEqual(
            self.scalar(
                "SELECT receipt->>'quota_units_consumed' FROM provider_receipt"
            ),
            "2",
        )
        self.assertEqual(
            self.scalar("SELECT billing_basis FROM provider_receipt"), "EXTERNAL_PLAN"
        )
        self.assertEqual(
            self.scalar("SELECT request_id FROM provider_receipt"), "req-from-omniroute"
        )
        replay = self.dispatch(provider=lambda: self.fail("restart dispatched"))
        self.assertEqual(replay.receipt_id, outcomes[0].receipt_id)
        self.assertEqual(replay.status, "RECONCILED")
        self.assertTrue(replay.provider_billing_reconciled)
        self.assertEqual(replay.new_child_task_count, 0)

        exhausted_replay = self.dispatch(
            gate=self.gate(quota_remaining=0),
            provider=lambda: self.fail("exhausted replay dispatched"),
        )
        self.assertEqual(exhausted_replay.receipt_id, replay.receipt_id)
        self.assertEqual(exhausted_replay.status, "RECONCILED")

    def test_atomic_quota_capacity_across_distinct_reserved_attempts(self):
        calls = []
        gate = self.gate(quota_remaining=3)

        def send():
            calls.append(1)
            return self.reply()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(
                    lambda suffix: self.dispatch(
                        gate=gate, provider=send, suffix=suffix
                    ),
                    ("a", "b"),
                )
            )
        self.assertEqual(len(calls), 1)
        self.assertCountEqual(
            [outcome.status for outcome in outcomes], ["RECONCILED", "WAIT_EXTERNAL"]
        )
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "1")

    def test_grant_revoked_after_durable_reservation_blocks_dispatch(self):
        checks = []

        def rights():
            checks.append(1)
            return len(checks) == 1

        first = self.dispatch(
            rights=rights, provider=lambda: self.fail("revoked source dispatched")
        )
        self.assertEqual(first.status, "WAIT_EXTERNAL")
        self.assertEqual(first.reason_code, "SOURCE_RIGHTS_REVOKED")
        self.assertEqual(
            self.scalar("SELECT status FROM provider_receipt"), "PENDING_UNKNOWN"
        )
        replay = self.dispatch(provider=lambda: self.fail("pending retry dispatched"))
        self.assertEqual(replay.status, "WAIT_EXTERNAL")

    def test_claimed_quota_is_unreconciled_without_independent_evidence(self):
        first = self.dispatch(verified=lambda _: False)
        self.assertEqual(first.status, "RECONCILED")
        self.assertFalse(first.provider_billing_reconciled)
        self.assertEqual(
            self.scalar(
                "SELECT receipt->>'quota_units_consumed' FROM provider_receipt"
            ),
            "",
        )
        self.assertEqual(self.scalar("SELECT request_count FROM provider_receipt"), "1")

    def test_tampered_completed_receipt_cannot_claim_provider_reconciliation(self):
        first = self.dispatch()
        self.assertEqual(first.status, "RECONCILED")
        self.exec_sql(
            self.dsn,
            """
            UPDATE provider_receipt
            SET request_id=NULL, total_tokens=NULL,
                receipt='{"provider_billing_reconciled":true}'::jsonb;
        """,
        )
        replay = self.dispatch(
            provider=lambda: self.fail("tampered receipt replayed POST")
        )
        self.assertEqual(replay.status, "WAIT_EXTERNAL")
        self.assertFalse(replay.provider_billing_reconciled)

    def test_invalid_quota_evidence_never_becomes_measured_zero(self):
        first = self.dispatch(
            provider=lambda: {
                **self.reply(),
                "quota": {
                    "units_consumed": 0,
                    "receipt_ref": "provider-usage:missing-unit",
                },
            }
        )
        self.assertEqual(first.status, "RECONCILED")
        self.assertFalse(first.provider_billing_reconciled)
        self.assertEqual(
            self.scalar(
                "SELECT receipt->>'quota_units_consumed' FROM provider_receipt"
            ),
            "",
        )

    def test_outage_429_and_pending_unknown_effects_never_retry(self):
        for suffix, error in (
            ("a", RuntimeError("OMNIROUTE_HTTP_429:QUOTA_EXHAUSTED")),
            ("b", OSError("provider outage")),
        ):

            def send():
                raise error

            first = self.dispatch(suffix=suffix, provider=send)
            self.assertEqual(first.status, "WAIT_EXTERNAL")
            again = self.dispatch(
                suffix=suffix, provider=lambda: self.fail("replayed POST")
            )
            self.assertEqual(again.status, "WAIT_EXTERNAL")
            self.assertEqual(first.receipt_id, again.receipt_id)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "2")
        self.assertEqual(
            self.scalar(
                "SELECT count(*) FROM provider_receipt WHERE status='PENDING_UNKNOWN'"
            ),
            "2",
        )

    def test_new_source_version_requires_distinct_receipt_and_no_false_quota_zero(self):
        first = self.dispatch(provider=lambda: {**self.reply(), "quota": None})
        self.assertEqual(first.status, "RECONCILED")
        self.assertFalse(first.provider_billing_reconciled)
        self.assertEqual(
            self.scalar(
                "SELECT receipt->>'quota_units_consumed' FROM provider_receipt"
            ),
            "",
        )
        newer = self.dispatch(suffix="b")
        self.assertNotEqual(first.receipt_id, newer.receipt_id)
        self.assertEqual(self.scalar("SELECT count(*) FROM provider_receipt"), "2")

    def test_replay_of_same_attempt_with_different_plan_is_held(self):
        first = self.dispatch()
        self.assertEqual(first.status, "RECONCILED")
        replay = self.dispatch(
            plan_fingerprint="c" * 64,
            provider=lambda: self.fail("different plan replay dispatched POST"),
        )
        self.assertEqual(replay.status, "WAIT_EXTERNAL")
        self.assertEqual(replay.reason_code, "SUBSCRIPTION_RECEIPT_CONFLICT")


if __name__ == "__main__":
    unittest.main()
