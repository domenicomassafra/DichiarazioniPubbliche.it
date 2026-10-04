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
    metadata=None,
):
    return VerificationEvidence(
        evidence_id=evidence_id,
        publication_date=publication_date,
        metric=metric,
        value_numeric=value if isinstance(value, (int, float)) else None,
        value_text=value if isinstance(value, str) else None,
        unit="percent",
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


if __name__ == "__main__":
    unittest.main()
