"""DP-516 oversized private batch metadata must be rejected without scanning it."""

import unittest

from tests.test_dp516_historical_batch_gate import plan, resources


class NonIterableOversizedTuple(tuple):
    """An attacker-controlled oversized tuple can be expensive to iterate."""

    def __iter__(self):
        raise AssertionError("DP516_SCANNED_EXCESS_METADATA")


class BoundedHistoricalInputsTests(unittest.TestCase):
    def test_oversized_cost_or_watch_tuples_hold_without_iteration(self):
        costs, watches = resources()
        for label, overrides in (
            ("costs", {"costs": NonIterableOversizedTuple(costs * 5)}),
            ("watches", {"watches": NonIterableOversizedTuple(watches * 5)}),
        ):
            with self.subTest(field=label):
                result = plan(**overrides)
                self.assertEqual(result.status, "HELD")
                self.assertIn("BATCH_ITEM_CAP", result.holds)
                self.assertEqual(result.proposals, ())
                self.assertIsNone(result.proposed_budget_state)


if __name__ == "__main__":
    unittest.main()
