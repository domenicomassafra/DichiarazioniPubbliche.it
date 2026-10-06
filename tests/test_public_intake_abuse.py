"""DP-508 callable public-intake abuse guard tests."""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    validate_intake_payload,
)
from dichiarazioni_pubbliche.public_intake_abuse import (  # noqa: E402
    MAX_PRIVATE_LOG_RECEIPT_BYTES,
    InMemoryIntakeRateStore,
    IntakeAbuseProfile,
    IntakeGuardState,
    IntakeSpamReason,
    guard_validated_intake,
)


def _payload(**overrides):
    value = {
        "finding_id": "finding:demo:1",
        "body": "Replica privata documentata.",
        "submitter_name": "Persona",
        "submitter_role": "Portavoce",
        "evidence_urls": ["https://example.test/reference"],
        "request_fingerprint": "caller-idempotency-token",
    }
    value.update(overrides)
    return value


def _validation(**overrides):
    return validate_intake_payload(
        _payload(**overrides),
        launch_profile_configured=True,
        intake_enabled=True,
    )


def _profile(**overrides):
    values = {
        "configured": True,
        "window_seconds": 60,
        "bucket_limit": 100,
        "global_quota": 1000,
        "duplicate_window_seconds": 300,
        "duplicate_limit": 100,
        "duplicate_capacity": 256,
    }
    values.update(overrides)
    return IntakeAbuseProfile(**values)


def _bucket(label="a"):
    return "bucket:" + hashlib.sha256(label.encode()).hexdigest()


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 10, 5, 21, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class PublicIntakeAbuseGuardTests(unittest.TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.store = InMemoryIntakeRateStore()

    def guard(self, validation=None, **kwargs):
        return guard_validated_intake(
            validation or _validation(),
            pseudonymous_bucket_key=kwargs.pop("pseudonymous_bucket_key", _bucket()),
            profile=kwargs.pop("profile", _profile()),
            rate_store=kwargs.pop("rate_store", self.store),
            clock=kwargs.pop("clock", self.clock),
            launch_profile_enabled=kwargs.pop("launch_profile_enabled", True),
            **kwargs,
        )

    def test_public_intake_stays_disabled_without_separate_launch_enable(self):
        receipt = self.guard(launch_profile_enabled=False)
        self.assertEqual(receipt.state, IntakeGuardState.BLOCKED)
        self.assertEqual(receipt.reason, IntakeSpamReason.PUBLIC_INTAKE_DISABLED)

    def test_missing_profile_rate_store_or_clock_fail_closed(self):
        cases = (
            {"profile": None, "reason": IntakeSpamReason.PROFILE_MISSING},
            {"rate_store": None, "reason": IntakeSpamReason.RATE_STORE_MISSING},
            {"clock": None, "reason": IntakeSpamReason.CLOCK_MISSING},
        )
        for case in cases:
            reason = case.pop("reason")
            with self.subTest(reason=reason):
                receipt = self.guard(**case)
                self.assertEqual(receipt.state, IntakeGuardState.BLOCKED)
                self.assertEqual(receipt.reason, reason)

    def test_allowed_intake_uses_only_validated_fingerprint_and_pseudonymous_bucket(self):
        receipt = self.guard()
        self.assertEqual(receipt.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(receipt.reason, IntakeSpamReason.OK)

    def test_replay_is_deterministic_and_does_not_become_second_allowed_intake(self):
        first = self.guard()
        second = self.guard()
        third = self.guard()
        self.assertEqual(first.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(second.state, IntakeGuardState.REPLAY)
        self.assertEqual(third.state, IntakeGuardState.REPLAY)
        self.assertEqual(second.reason, IntakeSpamReason.SPAM_DUPLICATE_REPLAY)
        self.assertEqual(second.private_log_receipt, third.private_log_receipt)

    def test_concurrent_replay_has_single_allowed_winner(self):
        validation = _validation()

        def invoke(_):
            return self.guard(validation)

        with ThreadPoolExecutor(max_workers=12) as executor:
            receipts = list(executor.map(invoke, range(12)))
        states = [receipt.state for receipt in receipts]
        self.assertEqual(states.count(IntakeGuardState.ALLOWED_PRIVATE), 1)
        self.assertEqual(states.count(IntakeGuardState.REPLAY), 11)

    def test_concurrent_unique_requests_respect_atomic_bucket_limit(self):
        profile = _profile(bucket_limit=4)

        def invoke(index):
            return self.guard(
                _validation(body=f"Replica documentata numero {index}."),
                profile=profile,
            )

        with ThreadPoolExecutor(max_workers=10) as executor:
            receipts = list(executor.map(invoke, range(10)))
        states = [receipt.state for receipt in receipts]
        self.assertEqual(states.count(IntakeGuardState.ALLOWED_PRIVATE), 4)
        self.assertEqual(states.count(IntakeGuardState.RATE_LIMITED), 6)
        self.assertTrue(
            all(
                receipt.reason is IntakeSpamReason.SPAM_BUCKET_RATE_LIMIT
                for receipt in receipts
                if receipt.state is IntakeGuardState.RATE_LIMITED
            )
        )

    def test_window_reset_allows_new_request_after_bucket_limit(self):
        profile = _profile(bucket_limit=1, window_seconds=60)
        first = self.guard(_validation(body="Prima replica."), profile=profile)
        limited = self.guard(_validation(body="Seconda replica."), profile=profile)
        self.clock.value += timedelta(seconds=60)
        after_reset = self.guard(_validation(body="Terza replica."), profile=profile)
        self.assertEqual(first.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(limited.state, IntakeGuardState.RATE_LIMITED)
        self.assertEqual(after_reset.state, IntakeGuardState.ALLOWED_PRIVATE)

    def test_global_quota_applies_across_pseudonymous_buckets(self):
        profile = _profile(global_quota=2)
        first = self.guard(
            _validation(body="Uno."), profile=profile, pseudonymous_bucket_key=_bucket("a")
        )
        second = self.guard(
            _validation(body="Due."), profile=profile, pseudonymous_bucket_key=_bucket("b")
        )
        third = self.guard(
            _validation(body="Tre."), profile=profile, pseudonymous_bucket_key=_bucket("c")
        )
        self.assertEqual(first.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(second.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(third.state, IntakeGuardState.RATE_LIMITED)
        self.assertEqual(third.reason, IntakeSpamReason.SPAM_GLOBAL_QUOTA_EXCEEDED)

    def test_duplicate_burst_has_explicit_spam_reason(self):
        profile = _profile(duplicate_limit=1)
        first = self.guard(profile=profile)
        replay = self.guard(profile=profile)
        burst = self.guard(profile=profile)
        self.assertEqual(first.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertEqual(replay.state, IntakeGuardState.REPLAY)
        self.assertEqual(burst.state, IntakeGuardState.RATE_LIMITED)
        self.assertEqual(burst.reason, IntakeSpamReason.SPAM_DUPLICATE_BURST)

    def test_duplicate_retention_is_bounded(self):
        profile = _profile(duplicate_capacity=3)
        for index in range(8):
            receipt = self.guard(
                _validation(body=f"Unique body {index}."),
                profile=profile,
                pseudonymous_bucket_key=_bucket(str(index)),
            )
            self.assertEqual(receipt.state, IntakeGuardState.ALLOWED_PRIVATE)
        self.assertLessEqual(self.store.retained_fingerprint_count, 3)

    def test_pii_quarantine_signal_is_preserved_as_private_quarantine(self):
        validation = _validation(body="Scrivimi a private@example.test per dettagli.")
        receipt = self.guard(validation)
        self.assertEqual(receipt.state, IntakeGuardState.QUARANTINED)
        self.assertEqual(receipt.reason, IntakeSpamReason.SPAM_PII_QUARANTINE)
        self.assertGreaterEqual(receipt.signal_count, 1)

    def test_reserved_field_signal_never_reaches_allowed_intake(self):
        validation = validate_intake_payload(
            {**_payload(), "status": "PUBLISHED"},
            launch_profile_configured=True,
            intake_enabled=True,
        )
        receipt = self.guard(validation)
        self.assertEqual(receipt.state, IntakeGuardState.QUARANTINED)
        self.assertEqual(receipt.reason, IntakeSpamReason.SPAM_RESERVED_FIELD_SIGNAL)

    def test_raw_ip_or_source_identifier_is_refused_as_bucket_key(self):
        for raw_identifier in ("203.0.113.7", "source:facebook-user-123"):
            with self.subTest(raw_identifier=raw_identifier):
                receipt = self.guard(pseudonymous_bucket_key=raw_identifier)
                self.assertEqual(receipt.state, IntakeGuardState.BLOCKED)
                self.assertEqual(receipt.reason, IntakeSpamReason.BUCKET_KEY_INVALID)

    def test_private_log_receipt_is_bounded_and_contains_no_private_identifiers(self):
        validation = _validation()
        fingerprint = validation.source_hash
        bucket = _bucket("PRIVATE_NETWORK_SENTINEL")
        receipt = self.guard(validation, pseudonymous_bucket_key=bucket)
        rendered = json.dumps(receipt.private_log_receipt, sort_keys=True)
        self.assertTrue(receipt.is_bounded())
        self.assertLessEqual(len(rendered.encode()), MAX_PRIVATE_LOG_RECEIPT_BYTES)
        self.assertNotIn(str(fingerprint), rendered)
        self.assertNotIn(bucket, rendered)
        self.assertNotIn(_payload()["body"], rendered)

    def test_no_dns_network_or_provider_surface_is_used(self):
        class BombStore(InMemoryIntakeRateStore):
            def call_provider(self, *args, **kwargs):
                raise AssertionError("provider forbidden")

        with mock.patch.object(
            socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")
        ), mock.patch.object(
            socket, "create_connection", side_effect=AssertionError("network forbidden")
        ):
            receipt = self.guard(rate_store=BombStore())
        self.assertEqual(receipt.state, IntakeGuardState.ALLOWED_PRIVATE)


if __name__ == "__main__":
    unittest.main()
