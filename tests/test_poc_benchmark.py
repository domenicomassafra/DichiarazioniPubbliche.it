import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.benchmark import load_cases, run_benchmark
from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    EvaluationOutcome,
    FindingPublicationStatus,
)
from dichiarazioni_pubbliche.evaluator import evaluate_case
from dichiarazioni_pubbliche.gate import apply_publication_gate


class BenchmarkTests(unittest.TestCase):
    def test_all_curated_cases_match_expected(self):
        result = run_benchmark()
        self.assertEqual(result["passed"], result["total"], result)

    def test_bollo_near_miss_does_not_publish_contradiction(self):
        case = next(
            item for item in load_cases()
            if item.case_id == "meloni-bollo-2016-2026-no-contradiction"
        )
        candidate = evaluate_case(case)
        decision = apply_publication_gate(case, candidate)
        self.assertEqual(
            candidate.evaluation_outcome,
            EvaluationOutcome.NO_CONTRADICTION_ESTABLISHED,
        )
        self.assertEqual(
            decision.publication, FindingPublicationStatus.NO_FINDING
        )

    def test_primary_official_evidence_required_for_numeric_publication(self):
        case = next(
            item for item in load_cases()
            if item.case_id == "rocca-employment-july-2026-supported"
        )
        candidate = evaluate_case(case)
        decision = apply_publication_gate(case, candidate)
        self.assertEqual(decision.publication, FindingPublicationStatus.PUBLISH)

    def test_synthetic_control_cannot_publish(self):
        case = next(
            item for item in load_cases()
            if item.case_id == "synthetic-control-wrong-july-employment-rate"
        )
        decision = apply_publication_gate(case, evaluate_case(case))
        self.assertEqual(
            decision.publication, FindingPublicationStatus.POLICY_HOLD
        )
        self.assertIn("SYNTHETIC_BENCHMARK_CASE", decision.reason_codes)

    def test_future_release_does_not_make_earlier_claim_outdated(self):
        case = next(
            item for item in load_cases()
            if item.case_id == "fdi-employment-rate-peak-outdated"
        )
        evidence = tuple(
            replace(item, publication_date="2026-09-05")
            if item.evidence_id == "istat-july-2026-employment-rate"
            else item
            for item in case.evidence
        )
        candidate = evaluate_case(replace(case, evidence=evidence))
        self.assertEqual(
            candidate.evaluation_outcome, EvaluationOutcome.SUPPORTED
        )


if __name__ == "__main__":
    unittest.main()
