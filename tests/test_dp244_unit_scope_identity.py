"""DP-244: a forged coverage-unit subclass must not reuse another window receipt."""

from dataclasses import asdict
from datetime import datetime, timezone
import unittest

from dichiarazioni_pubbliche.coverage_catalog_v1 import (
    CoverageUnit, build_source_coverage, public_freshness_descriptor,
)
from tests.test_dp244_coverage_catalog import NOW, SHA, observation, unit


class CoverageUnitIdentityTests(unittest.TestCase):
    def test_subclass_cannot_override_scope_fingerprint_to_widen_source_window(self):
        original = unit()
        receipt = observation()
        self.assertEqual(receipt.scope_fingerprint, original.scope_fingerprint())

        class ForgedScope(CoverageUnit):
            def scope_fingerprint(self):
                return original.scope_fingerprint()

        widened = ForgedScope(**{
            **asdict(original),
            "interval_start": datetime(1920, 1, 1, tzinfo=timezone.utc),
            "interval_end": datetime(1950, 1, 1, tzinfo=timezone.utc),
        })
        self.assertNotEqual(
            CoverageUnit(**asdict(widened)).scope_fingerprint(),
            receipt.scope_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "COVERAGE_INPUT_UNBOUNDED"):
            decision = build_source_coverage(
                widened, (receipt,), now=NOW, baseline_sha256=SHA,
                rights_ready=True, budget_ready=True, capability_ready=True,
            )
            self.assertIsNone(public_freshness_descriptor(
                decision, public_scope_review_id="review:synthetic",
            ))

    def test_exact_unit_still_reconciles_unchanged_scope_with_review(self):
        decision = build_source_coverage(
            unit(), (observation(),), now=NOW, baseline_sha256=SHA,
            rights_ready=True, budget_ready=True, capability_ready=True,
        )
        self.assertEqual(decision.state, "CURRENT_WITHIN_OBSERVED_SCOPE")
        self.assertFalse(decision.dispatch_authorized)


if __name__ == "__main__":
    unittest.main()
