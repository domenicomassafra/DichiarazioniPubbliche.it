import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.verification_runtime import (  # noqa: E402
    VerificationAssessment,
    VerificationEvidence,
    VerificationRequest as RuntimeVerificationRequest,
    deterministic_verification_run_id,
    deterministic_evidence_observation_id,
    verify,
)


def evidence(
    value,
    *,
    evidence_id="e1",
    publication_date="2026-09-01",
    metric="employment_rate_pct",
    reference_period="2026-07",
    authoritative=True,
    suitable=True,
    status="APPROVED",
    unit="percent",
    metadata=None,
):
    return VerificationEvidence(
        evidence_id=evidence_id,
        publication_date=publication_date,
        metric=metric,
        value_numeric=value if isinstance(value, (int, float)) else None,
        value_text=value if isinstance(value, str) else None,
        unit=unit,
        reference_period=reference_period,
        suitable=suitable,
        authoritative=authoritative,
        status=status,
        metadata=metadata or {},
    )


def VerificationRequest(*args, **kwargs):
    kwargs.setdefault("source_intelligence_status", "SUFFICIENT_FOR_RULE")
    kwargs.setdefault("source_intelligence_assessment_id", "assessment:test")
    return RuntimeVerificationRequest(*args, **kwargs)


class VerificationRuntimeTests(unittest.TestCase):
    def test_legacy_authoritative_boolean_does_not_bypass_source_intelligence(self):
        request = RuntimeVerificationRequest(
            "claim:a",
            "2026-09-04",
            "numeric_exact",
            {"metric": "employment_rate_pct", "reference_period": "2026-07", "value": 63.2},
        )
        result = verify(request, [evidence(63.2, authoritative=True, suitable=True)])
        self.assertEqual(result.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_INTELLIGENCE_ASSESSMENT_REQUIRED", result.blockers)

    def test_observation_id_is_content_and_extractor_versioned(self):
        common = dict(
            evidence_id="evidence:a",
            observation_type="METRIC",
            metric="rate",
            value_numeric=10.0,
            value_text=None,
            unit="percent",
            reference_period="2025",
            dimensions={},
            extraction_method="MANUAL_STRUCTURED",
            source_pointer={"table": "A", "row": 1},
        )
        first = deterministic_evidence_observation_id(
            **common,
            extraction_version="v1",
        )
        same = deterministic_evidence_observation_id(
            **common,
            extraction_version="v1",
        )
        changed = deterministic_evidence_observation_id(
            **common,
            extraction_version="v2",
        )
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)
    def test_numeric_exact_uses_only_pre_statement_authoritative_evidence(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-04",
            "numeric_exact",
            {
                "metric": "employment_rate_pct",
                "reference_period": "2026-07",
                "value": 63.2,
                "tolerance": 0,
            },
        )
        result = verify(request, [evidence(63.2)])
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        future = verify(
            request,
            [evidence(63.2, publication_date="2026-09-05")],
        )
        self.assertEqual(
            future.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE
        )
        self.assertIn("POST_STATEMENT_EVIDENCE_ONLY", future.blockers)

    def test_conflicting_authoritative_values_are_unresolved(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-04",
            "numeric_exact",
            {
                "metric": "employment_rate_pct",
                "reference_period": "2026-07",
                "value": 63.2,
            },
        )
        result = verify(
            request,
            [
                evidence(63.2, evidence_id="e1"),
                evidence(63.1, evidence_id="e2"),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.UNRESOLVED)

    def test_single_counterexample_falsifies_historical_minimum(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-03",
            "historical_minimum",
            {"metric": "youth_unemployment_rate_pct", "value": 18.4},
        )
        result = verify(
            request,
            [
                evidence(
                    15.1,
                    metric="youth_unemployment_rate_pct",
                    reference_period="2026-05",
                )
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.FACTUALLY_FALSE)

    def test_historical_support_requires_complete_coverage_or_attestation(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-03",
            "historical_peak",
            {"metric": "employment_rate_pct", "value": 63.2},
        )
        incomplete = verify(request, [evidence(63.2)])
        self.assertEqual(
            incomplete.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE
        )
        self.assertIn("HISTORICAL_COVERAGE_INCOMPLETE", incomplete.blockers)
        complete = verify(
            VerificationRequest(
                "claim:a",
                "2026-09-03",
                "historical_peak",
                {
                    "metric": "employment_rate_pct",
                    "value": 63.2,
                    "coverage_complete": True,
                },
            ),
            [evidence(63.2)],
        )
        self.assertEqual(complete.assessment, VerificationAssessment.SUPPORTED)

    def test_historical_peak_counterexample_before_statement_is_false_not_outdated(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-03",
            "historical_peak",
            {"metric": "employment_rate_pct", "value": 63.2},
        )
        result = verify(
            request,
            [
                evidence(
                    64.0,
                    publication_date="2026-09-01",
                    metric="employment_rate_pct",
                    reference_period="2026-08",
                )
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.FACTUALLY_FALSE)

    def test_retrieved_but_not_approved_evidence_is_not_used(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-04",
            "numeric_exact",
            {
                "metric": "employment_rate_pct",
                "reference_period": "2026-07",
                "value": 63.2,
            },
        )
        result = verify(request, [evidence(63.2, status="RETRIEVED")])
        self.assertEqual(
            result.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE
        )

    def test_verification_run_id_is_input_versioned(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-04",
            "numeric_exact",
            {"metric": "x", "reference_period": "2026-07", "value": 1},
        )
        left = deterministic_verification_run_id(
            request,
            [
                evidence(
                    1,
                    metric="x",
                    reference_period="2026-07",
                )
            ],
        )
        right = deterministic_verification_run_id(
            request,
            [
                evidence(
                    2,
                    metric="x",
                    reference_period="2026-07",
                )
            ],
        )
        self.assertNotEqual(left, right)

    def test_numeric_delta_uses_two_suitable_inputs_and_same_unit(self):
        request = VerificationRequest(
            "claim:delta",
            "2026-09-04",
            "numeric_delta",
            {
                "left_metric": "employment_rate_pct",
                "right_metric": "employment_rate_pct_previous",
                "left_reference_period": "2026-07",
                "right_reference_period": "2025-07",
                "value": 1.5,
                "tolerance": 0.01,
            },
        )
        result = verify(
            request,
            [
                evidence(63.5, evidence_id="current"),
                evidence(
                    62.0,
                    evidence_id="previous",
                    metric="employment_rate_pct_previous",
                    reference_period="2025-07",
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        self.assertAlmostEqual(result.result["observed"], 1.5)

    def test_numeric_delta_applies_only_explicit_unit_conversion(self):
        request = VerificationRequest(
            "claim:delta-unit",
            "2026-09-04",
            "numeric_delta",
            {
                "left_metric": "spending_current",
                "right_metric": "spending_previous",
                "value": 500000.0,
                "unit_conversion": {
                    "target_unit": "eur",
                    "factor_to_target": {
                        "million_eur": 1000000.0,
                        "eur": 1.0,
                    },
                },
            },
        )
        result = verify(
            request,
            [
                evidence(
                    1.5,
                    evidence_id="current",
                    metric="spending_current",
                    unit="million_eur",
                ),
                evidence(
                    1000000.0,
                    evidence_id="previous",
                    metric="spending_previous",
                    unit="eur",
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        self.assertAlmostEqual(result.result["observed"], 500000.0)
        self.assertEqual(result.result["unit"], "eur")
        self.assertEqual(
            result.result["unit_conversion"]["left_factor"],
            1000000.0,
        )

    def test_numeric_delta_mismatched_units_still_fail_without_conversion_policy(self):
        request = VerificationRequest(
            "claim:delta-unit-blocked",
            "2026-09-04",
            "numeric_delta",
            {
                "left_metric": "spending_current",
                "right_metric": "spending_previous",
                "value": 500000.0,
            },
        )
        result = verify(
            request,
            [
                evidence(1.5, metric="spending_current", unit="million_eur"),
                evidence(
                    1000000.0,
                    evidence_id="previous",
                    metric="spending_previous",
                    unit="eur",
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE)
        self.assertIn("NUMERIC_UNIT_MISMATCH", result.blockers)

    def test_numeric_percent_change_fails_closed_on_zero_baseline(self):
        request = VerificationRequest(
            "claim:pct",
            "2026-09-04",
            "numeric_percent_change",
            {
                "current_metric": "spending",
                "baseline_metric": "spending_previous",
                "current_reference_period": "2026",
                "baseline_reference_period": "2025",
                "value": 10.0,
            },
        )
        result = verify(
            request,
            [
                evidence(
                    10.0,
                    evidence_id="current",
                    metric="spending",
                    reference_period="2026",
                ),
                evidence(
                    0.0,
                    evidence_id="baseline",
                    metric="spending_previous",
                    reference_period="2025",
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.INSUFFICIENT_EVIDENCE)
        self.assertIn("NUMERIC_DENOMINATOR_ZERO", result.blockers)

    def test_numeric_percent_change_normalizes_explicit_compatible_units(self):
        request = VerificationRequest(
            "claim:pct-unit",
            "2026-09-04",
            "numeric_percent_change",
            {
                "current_metric": "spending",
                "baseline_metric": "spending_previous",
                "value": 50.0,
                "unit_conversion": {
                    "target_unit": "eur",
                    "factor_to_target": {
                        "million_eur": 1000000.0,
                        "eur": 1.0,
                    },
                },
            },
        )
        result = verify(
            request,
            [
                evidence(1.5, metric="spending", unit="million_eur"),
                evidence(
                    1000000.0,
                    evidence_id="baseline",
                    metric="spending_previous",
                    unit="eur",
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        self.assertAlmostEqual(result.result["observed"], 50.0)
        self.assertEqual(result.result["unit_conversion"]["target_unit"], "eur")

    def test_numeric_ratio_detects_mismatch(self):
        request = VerificationRequest(
            "claim:ratio",
            "2026-09-04",
            "numeric_ratio",
            {
                "numerator_metric": "part",
                "denominator_metric": "whole",
                "value": 0.6,
            },
        )
        result = verify(
            request,
            [
                evidence(30.0, evidence_id="part", metric="part"),
                evidence(100.0, evidence_id="whole", metric="whole"),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.FACTUALLY_FALSE)
        self.assertAlmostEqual(result.result["observed"], 0.3)

    def test_numeric_ratio_requires_explicit_denominator_population_dimensions(self):
        request = VerificationRequest(
            "claim:ratio-population",
            "2026-09-04",
            "numeric_ratio",
            {
                "numerator_metric": "employed_people",
                "denominator_metric": "population",
                "value": 0.6,
                "denominator_dimensions": {
                    "population": "working_age",
                    "geography": "IT",
                },
            },
        )
        wrong_population = verify(
            request,
            [
                evidence(30.0, evidence_id="istat-employed", metric="employed_people"),
                VerificationEvidence(
                    evidence_id="istat-pop-total",
                    publication_date="2026-09-01",
                    metric="population",
                    value_numeric=50.0,
                    unit="percent",
                    suitable=True,
                    metadata={
                        "provider_family": "ISTAT",
                        "dimensions": {"population": "total", "geography": "IT"},
                    },
                ),
            ],
        )
        self.assertEqual(
            wrong_population.assessment,
            VerificationAssessment.INSUFFICIENT_EVIDENCE,
        )
        self.assertIn("NUMERIC_DIMENSION_MISMATCH", wrong_population.blockers)

        matched_population = verify(
            request,
            [
                evidence(30.0, evidence_id="istat-employed", metric="employed_people"),
                VerificationEvidence(
                    evidence_id="istat-pop-working-age",
                    publication_date="2026-09-01",
                    metric="population",
                    value_numeric=50.0,
                    unit="percent",
                    suitable=True,
                    metadata={
                        "provider_family": "ISTAT",
                        "dimensions": {"population": "working_age", "geography": "IT"},
                    },
                ),
            ],
        )
        self.assertEqual(matched_population.assessment, VerificationAssessment.SUPPORTED)

    def test_numeric_rounding_policy_is_explicit_for_structured_sources(self):
        request = VerificationRequest(
            "claim:structured-rounding",
            "2026-09-04",
            "numeric_ratio",
            {
                "numerator_metric": "dvns_numerator",
                "denominator_metric": "eurostat_denominator",
                "value": 0.33,
                "rounding": {"mode": "DECIMAL_PLACES", "places": 2},
            },
        )
        result = verify(
            request,
            [
                VerificationEvidence(
                    evidence_id="dvns-structured",
                    publication_date="2026-09-01",
                    metric="dvns_numerator",
                    value_numeric=1.0,
                    unit="count",
                    suitable=True,
                    metadata={"provider_family": "DVNS", "dimensions": {}},
                ),
                VerificationEvidence(
                    evidence_id="eurostat-structured",
                    publication_date="2026-09-01",
                    metric="eurostat_denominator",
                    value_numeric=3.0,
                    unit="count",
                    suitable=True,
                    metadata={"provider_family": "EUROSTAT", "dimensions": {}},
                ),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        self.assertEqual(
            result.result["rounding"],
            {"mode": "DECIMAL_PLACES", "places": 2},
        )
        self.assertEqual(result.result["observed_compared"], 0.33)

    def test_significant_figure_policy_changes_only_the_explicit_comparison(self):
        request = VerificationRequest(
            "claim:sigfig",
            "2026-09-04",
            "numeric_delta",
            {
                "left_metric": "istat_current",
                "right_metric": "istat_previous",
                "value": 1.23,
                "rounding": {"mode": "SIGNIFICANT_FIGURES", "digits": 3},
            },
        )
        result = verify(
            request,
            [
                evidence(11.234, evidence_id="current", metric="istat_current"),
                evidence(10.0, evidence_id="previous", metric="istat_previous"),
            ],
        )
        self.assertEqual(result.assessment, VerificationAssessment.SUPPORTED)
        self.assertAlmostEqual(result.result["observed"], 1.234)
        self.assertEqual(result.result["observed_compared"], 1.23)


if __name__ == "__main__":
    unittest.main()
