"""Subscription route scope must follow verified readback without a fixed count."""

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from dichiarazioni_pubbliche.private_investigation_subscription_d import SubscriptionGate


class SubscriptionGateContractTests(unittest.TestCase):
    def gate(self, count):
        connections = tuple(
            hashlib.sha256(f"pro-account-{i}".encode()).hexdigest()
            for i in range(count)
        )
        return SubscriptionGate(
            model="antigravity/gemini-3.8-flash-tiered",
            account_scope="subscription:verified-current",
            authorized_connection_fingerprints=connections,
            observed_connection_fingerprints=connections,
            subscription_only=True,
            paid_fallback_disabled=True,
            quota_remaining=10,
            quota_upper_bound=3,
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=10),
            evidence_ref="omniroute:scoped-readback",
        )

    def test_valid_verified_connection_sets_are_not_count_limited(self):
        for count in (1, 12, 13, 31):
            with self.subTest(count=count):
                self.assertIsNone(self.gate(count).blocker())

    def test_empty_duplicate_or_unverified_scope_fails_closed(self):
        gate = self.gate(13)
        for candidate in (
            self.gate(0),
            dataclasses.replace(
                gate,
                observed_connection_fingerprints=gate.observed_connection_fingerprints[:-1],
            ),
            dataclasses.replace(
                gate,
                observed_connection_fingerprints=gate.observed_connection_fingerprints
                + (gate.observed_connection_fingerprints[0],),
            ),
            dataclasses.replace(gate, subscription_only=False),
            dataclasses.replace(gate, paid_fallback_disabled=False),
        ):
            with self.subTest(candidate=candidate):
                self.assertEqual(candidate.blocker(), "SUBSCRIPTION_ROUTE_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
