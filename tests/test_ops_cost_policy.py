import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    BudgetPolicy,
    CostSnapshot,
    classify_decision_reason,
    estimate_cost_usd,
    preflight,
    validate_cost_policy,
)


class CostEstimationTests(unittest.TestCase):
    def test_known_zero_cost_lane_is_zero(self):
        self.assertEqual(estimate_cost_usd("PUBLIC_PROJECTION_BUILD"), 0.0)

    def test_unknown_operation_is_not_assumed_free(self):
        self.assertIsNone(estimate_cost_usd("SOMETHING_NEW"))

    def test_audio_cost_is_duration_based(self):
        self.assertEqual(
            estimate_cost_usd("AUDIO_TRANSCRIPTION", input_seconds=3600),
            0.04,
        )

    def test_claim_cost_requires_explicit_ceiling_and_token_count(self):
        self.assertIsNone(estimate_cost_usd("CLAIM_EXTRACT", total_tokens=1000))
        self.assertEqual(
            estimate_cost_usd(
                "CLAIM_EXTRACT",
                total_tokens=2500,
                max_usd_per_1k_total_tokens=0.002,
            ),
            0.005,
        )


class BudgetPreflightTests(unittest.TestCase):
    def setUp(self):
        self.policy = BudgetPolicy(
            max_cost_usd_per_job=0.25,
            max_cost_usd_per_source_day=1.0,
            max_cost_usd_per_day=5.0,
        )

    def test_missing_cost_model_blocks(self):
        decision = preflight(
            self.policy,
            CostSnapshot(global_day_usd=0, source_day_usd=0),
            None,
            operation="CLAIM_EXTRACT",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "COST_MODEL_MISSING")
        self.assertEqual(classify_decision_reason(decision.reason), "BLOCK")

    def test_job_cap_defers(self):
        decision = preflight(
            self.policy,
            CostSnapshot(global_day_usd=0, source_day_usd=0),
            0.30,
            operation="CLAIM_EXTRACT",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "JOB_COST_CAP_REACHED")
        self.assertEqual(classify_decision_reason(decision.reason), "DEFER")

    def test_global_cap_defers_without_spending(self):
        decision = preflight(
            self.policy,
            CostSnapshot(global_day_usd=4.95, source_day_usd=0),
            0.10,
            operation="CLAIM_EXTRACT",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "GLOBAL_DAILY_BUDGET_REACHED")

    def test_zero_cost_lane_is_allowed(self):
        decision = preflight(
            self.policy,
            CostSnapshot(global_day_usd=5.0, source_day_usd=1.0),
            0.0,
            operation="PUBLIC_PROJECTION_BUILD",
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "ALLOWED_ZERO_COST")

    def test_default_policy_is_structurally_coherent(self):
        self.assertEqual(validate_cost_policy(), ())


if __name__ == "__main__":
    unittest.main()
