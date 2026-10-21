"""DP-508 regression: runtime-memory quota cannot reset on profile changes."""

import unittest

from dichiarazioni_pubbliche.public_intake_abuse import (
    InMemoryIntakeRateStore,
    IntakeGuardState,
    IntakeSpamReason,
    guard_validated_intake,
)
from tests.test_public_intake_abuse import MutableClock, _bucket, _profile, _validation


class InMemoryProfileCheckpointTests(unittest.TestCase):
    def test_changed_profile_is_blocked_without_releasing_quota(self):
        baseline = _profile(bucket_limit=1, global_quota=1)
        variations = (
            {"window_seconds": 1},
            {"bucket_limit": 2},
            {"global_quota": 2},
            {"duplicate_window_seconds": 120},
            {"duplicate_limit": 101},
            {"duplicate_capacity": 128},
        )
        for index, change in enumerate(variations):
            with self.subTest(change=change):
                store = InMemoryIntakeRateStore()
                clock = MutableClock()

                def reserve(body, profile):
                    return guard_validated_intake(
                        _validation(body=body),
                        pseudonymous_bucket_key=_bucket(),
                        profile=profile,
                        rate_store=store,
                        clock=clock,
                        launch_profile_enabled=True,
                    )

                values = {"bucket_limit": 1, "global_quota": 1}
                values.update(change)
                first = reserve("Original request", baseline)
                changed = reserve(f"Changed profile {index}", _profile(**values))
                later = reserve(f"Quota remains spent {index}", baseline)
                self.assertEqual(first.state, IntakeGuardState.ALLOWED_PRIVATE)
                self.assertEqual(changed.state, IntakeGuardState.BLOCKED)
                self.assertEqual(changed.reason, IntakeSpamReason.RATE_STORE_ERROR)
                self.assertEqual(later.state, IntakeGuardState.RATE_LIMITED)


if __name__ == "__main__":
    unittest.main()
