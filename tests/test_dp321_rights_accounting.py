"""DP-321 eligibility must reflect missing publication-rights proof."""

import unittest

from tests.test_dp321_independent_reference_benchmark import (
    ALLOW_SIMULATED_EXTERNAL,
    case,
    manifest,
    pred,
)
from dichiarazioni_pubbliche.independent_reference_benchmark_v1 import (
    evaluate_independent_reference,
)


class RightsAccountingTests(unittest.TestCase):
    def test_public_prediction_without_rights_proof_is_not_eligible(self):
        row = case("missing-rights-proof")
        report = evaluate_independent_reference(
            manifest(row),
            (pred(row, claimed_rights_clearance=False),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(report.metrics["sample_coverage"].numerator, 1)
        self.assertEqual(report.metrics["unsupported_publication"].numerator, 1)
        for metric in ("eligible_recall", "conditional_publishability"):
            self.assertEqual(
                (report.metrics[metric].numerator, report.metrics[metric].denominator),
                (0, 1),
            )
