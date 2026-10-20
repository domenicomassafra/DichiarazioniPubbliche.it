"""DP-508: malformed input cannot change quota state; RAM/SQLite agree."""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from dichiarazioni_pubbliche.public_intake_abuse import (
    InMemoryIntakeRateStore,
    IntakeGuardState,
    IntakeSpamReason,
    RateStoreRequest,
    RateStoreStatus,
    SQLiteIntakeRateStore,
    guard_validated_intake,
)
from tests.test_public_intake_abuse import MutableClock, _bucket, _profile, _validation


def _request(**change):
    return replace(
        RateStoreRequest(
            bucket_key=_bucket(),
            fingerprint="a" * 64,
            now_epoch=1_780_000_000,
            window_seconds=60,
            bucket_limit=1,
            global_quota=1,
            duplicate_window_seconds=300,
            duplicate_limit=10,
            duplicate_capacity=5,
        ),
        **change,
    )


class StrictStoreValidationTests(unittest.TestCase):
    def test_invalid_request_never_reserves_or_binds_initial_profile(self):
        invalid = (
            {"fingerprint": "bad fingerprint"},
            {"bucket_key": "raw-ip"},
            {"now_epoch": True},
            {"window_seconds": 60.5},
            {"bucket_limit": True},
            {"global_quota": 0},
            {"duplicate_window_seconds": 60.0},
            {"duplicate_limit": -1},
            {"duplicate_capacity": False},
        )
        for change in invalid:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                stores = (
                    InMemoryIntakeRateStore(),
                    SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
                )
                errors = []
                for store in stores:
                    with self.assertRaises(ValueError) as ctx:
                        store.reserve(_request(**change))
                    errors.append(str(ctx.exception))
                    # Different valid policy proves malformed input did not bind a checkpoint.
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30)).status,
                        RateStoreStatus.RESERVED,
                    )
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30, fingerprint="b" * 64)).status,
                        RateStoreStatus.GLOBAL_QUOTA,
                    )
                self.assertEqual(errors[0], errors[1])

    def test_malformed_reserve_preserves_existing_quota_and_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            for store in (
                InMemoryIntakeRateStore(),
                SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
            ):
                with self.subTest(store=type(store).__name__):
                    self.assertEqual(store.reserve(_request()).status, RateStoreStatus.RESERVED)
                    with self.assertRaisesRegex(ValueError, "INTAKE_RATE_LIMITS_INVALID"):
                        store.reserve(_request(window_seconds=1.5, global_quota=10))
                    self.assertEqual(
                        store.reserve(_request(fingerprint="c" * 64)).status,
                        RateStoreStatus.GLOBAL_QUOTA,
                    )
                    with self.assertRaisesRegex(ValueError, "INTAKE_RATE_PROFILE_CHANGED"):
                        store.reserve(_request(window_seconds=30))

    def test_non_integer_profiles_block_before_touching_either_store(self):
        changes = (
            {"configured": 1},
            {"window_seconds": 60.0},
            {"window_seconds": 60.5},
            {"bucket_limit": True},
            {"global_quota": 10.0},
            {"duplicate_window_seconds": 300.0},
            {"duplicate_limit": False},
            {"duplicate_capacity": 4.0},
        )
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                profile = _profile(**change)
                self.assertFalse(profile.valid())
                stores = (
                    InMemoryIntakeRateStore(),
                    SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
                )
                for store in stores:
                    response = guard_validated_intake(
                        _validation(body="Valid intake"),
                        pseudonymous_bucket_key=_bucket(),
                        profile=profile,
                        rate_store=store,
                        clock=MutableClock(),
                        launch_profile_enabled=True,
                    )
                    self.assertEqual(response.state, IntakeGuardState.BLOCKED)
                    self.assertEqual(response.reason, IntakeSpamReason.PROFILE_MISSING)
                    # An invalid guard profile must never initialize a quota checkpoint.
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30)).status,
                        RateStoreStatus.RESERVED,
                    )


    def test_only_literal_true_can_enable_the_private_guard(self):
        for flag in ("false", "0", 1, None, [], False):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as folder:
                for store in (
                    InMemoryIntakeRateStore(),
                    SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
                ):
                    receipt = guard_validated_intake(
                        _validation(body="Valid intake"),
                        pseudonymous_bucket_key=_bucket(),
                        profile=_profile(),
                        rate_store=store,
                        clock=MutableClock(),
                        launch_profile_enabled=flag,
                    )
                    self.assertEqual(receipt.state, IntakeGuardState.BLOCKED)
                    self.assertEqual(receipt.reason, IntakeSpamReason.PUBLIC_INTAKE_DISABLED)
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30)).status,
                        RateStoreStatus.RESERVED,
                    )
        enabled = guard_validated_intake(
            _validation(body="Valid intake"),
            pseudonymous_bucket_key=_bucket(),
            profile=_profile(),
            rate_store=InMemoryIntakeRateStore(),
            clock=MutableClock(),
            launch_profile_enabled=True,
        )
        self.assertEqual(enabled.state, IntakeGuardState.ALLOWED_PRIVATE)

    def test_bucket_alias_is_rejected_without_consuming_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            for store in (
                InMemoryIntakeRateStore(),
                SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
            ):
                with self.subTest(store=type(store).__name__):
                    alias = _request(bucket_key=" " + _bucket() + " ")
                    with self.assertRaisesRegex(ValueError, "INTAKE_RATE_IDENTITY_INVALID"):
                        store.reserve(alias)
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30)).status,
                        RateStoreStatus.RESERVED,
                    )
                    with self.assertRaisesRegex(ValueError, "INTAKE_RATE_IDENTITY_INVALID"):
                        store.reserve(replace(alias, window_seconds=30, fingerprint="b" * 64))
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30, fingerprint="b" * 64)).status,
                        RateStoreStatus.GLOBAL_QUOTA,
                    )

    def test_string_like_fingerprint_is_rejected_without_checkpoint(self):
        class FakeDigest:
            def __str__(self):
                return "a" * 64

        with tempfile.TemporaryDirectory() as folder:
            for store in (
                InMemoryIntakeRateStore(),
                SQLiteIntakeRateStore(Path(folder) / "quota.sqlite3"),
            ):
                with self.subTest(store=type(store).__name__):
                    with self.assertRaisesRegex(ValueError, "INTAKE_RATE_IDENTITY_INVALID"):
                        store.reserve(_request(fingerprint=FakeDigest()))
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30)).status,
                        RateStoreStatus.RESERVED,
                    )
                    self.assertEqual(
                        store.reserve(_request(window_seconds=30, fingerprint="b" * 64)).status,
                        RateStoreStatus.GLOBAL_QUOTA,
                    )

    def test_six_hundred_valid_requests_match_sqlite_with_restarts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "quota.sqlite3"
            memory = InMemoryIntakeRateStore()
            sqlite_store = SQLiteIntakeRateStore(path)
            clock = MutableClock()
            profile = _profile(bucket_limit=100, global_quota=24)
            outcomes = []
            for index in range(600):
                if index and index % 47 == 0:
                    sqlite_store = SQLiteIntakeRateStore(path)
                body_index = index if index < 22 else (index - 22 if index < 24 else index)
                validation = _validation(body=f"Intake parity {body_index}")
                states = tuple(
                    guard_validated_intake(
                        validation,
                        pseudonymous_bucket_key=_bucket(),
                        profile=profile,
                        rate_store=store,
                        clock=clock,
                        launch_profile_enabled=True,
                    )
                    for store in (memory, sqlite_store)
                )
                self.assertEqual(
                    (states[0].state, states[0].reason),
                    (states[1].state, states[1].reason),
                    f"request index {index}",
                )
                outcomes.append(states[0].state)
            self.assertEqual(
                Counter(outcomes),
                {IntakeGuardState.ALLOWED_PRIVATE: 22,
                 IntakeGuardState.REPLAY: 2,
                 IntakeGuardState.RATE_LIMITED: 576},
            )

    def test_concurrent_profile_variation_and_quota_remain_atomic(self):
        store = InMemoryIntakeRateStore()
        first_profile = _request(bucket_limit=100, global_quota=13)
        changed_profile = replace(first_profile, window_seconds=30)
        # Reserve the first profile before workers race, and spend one quota unit.
        self.assertEqual(store.reserve(first_profile).status, RateStoreStatus.RESERVED)

        def reserve(index):
            request = first_profile if index % 2 == 0 else changed_profile
            request = replace(request, fingerprint=f"{index + 1:064x}")
            try:
                return store.reserve(request).status.value
            except ValueError as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=16) as executor:
            outcomes = Counter(executor.map(reserve, range(100)))
        self.assertEqual(outcomes["RESERVED"], 12)
        self.assertEqual(outcomes["GLOBAL_QUOTA"], 38)
        self.assertEqual(outcomes["INTAKE_RATE_PROFILE_CHANGED"], 50)


if __name__ == "__main__":
    unittest.main()
