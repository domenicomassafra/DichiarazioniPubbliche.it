"""DP-516 oversized private batch metadata must be rejected without scanning it."""

import unittest

from tests.test_dp516_historical_batch_gate import plan, resources


class NonIterableOversizedTuple(tuple):
    """An attacker-controlled oversized tuple can be expensive to iterate."""

    def __iter__(self):
        raise AssertionError("DP516_SCANNED_EXCESS_METADATA")


class PoisonSlice(tuple):
    def __getitem__(self, key):
        raise AssertionError("DP516_SLICED_HELD_INPUT")


class SideEffectSlice(tuple):
    slice_calls = 0

    def __getitem__(self, key):
        self.slice_calls += 1
        return super().__getitem__(key)


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


    def test_oversized_tuple_subclasses_cannot_run_slice_hooks(self):
        costs, watches = resources()
        for field, values in (("costs", costs), ("watches", watches)):
            for cls in (PoisonSlice, SideEffectSlice):
                with self.subTest(field=field, tuple_type=cls.__name__):
                    input_rows = cls(values * 5)
                    original = tuple.__getitem__(input_rows, slice(None))
                    result = plan(**{field: input_rows})
                    self.assertEqual(result.status, "HELD")
                    self.assertIn("BATCH_ITEM_CAP", result.holds)
                    self.assertEqual(result.proposals, ())
                    self.assertIsNone(result.proposed_budget_state)
                    self.assertEqual(tuple.__getitem__(input_rows, slice(None)), original)
                    if isinstance(input_rows, SideEffectSlice):
                        self.assertEqual(input_rows.slice_calls, 0)

    def test_oversize_preserves_other_hold_reasons(self):
        costs, _ = resources()
        result = plan(costs=PoisonSlice(costs * 5), verifier=None)
        self.assertEqual(result.status, "HELD")
        self.assertIn("BATCH_ITEM_CAP", result.holds)
        self.assertIn("DP443_PILOT_SIGNED_ACCEPTANCE_REQUIRED", result.holds)
        self.assertEqual(result.proposals, ())
        self.assertIsNone(result.proposed_budget_state)

    def test_within_cap_normal_tuples_still_plan(self):
        costs, watches = resources()
        result = plan(costs=costs, watches=watches)
        self.assertEqual(result.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(result.proposals), len(costs))
        self.assertIsNotNone(result.proposed_budget_state)


if __name__ == "__main__":
    unittest.main()
