from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluator import evaluate_case
from .gate import apply_publication_gate
from .domain_vocabulary import EvaluationOutcome, FindingPublicationStatus
from .models import ClaimCase, EvidenceReceipt, SourceType


DEFAULT_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "italian_cases.json"


def load_cases(path: Path = DEFAULT_FIXTURES) -> list[ClaimCase]:
    raw = json.loads(path.read_text())
    cases: list[ClaimCase] = []
    for item in raw["cases"]:
        evidence = tuple(
            EvidenceReceipt(
                evidence_id=e["evidence_id"],
                source_url=e["source_url"],
                publisher=e["publisher"],
                source_type=SourceType(e["source_type"]),
                publication_date=e["publication_date"],
                observed_at=e["observed_at"],
                reference_period=e.get("reference_period"),
                metric=e.get("metric"),
                value=e.get("value"),
                unit=e.get("unit"),
                independence_group=e.get("independence_group", ""),
                fetched=e.get("fetched", True),
                quote_or_fact=e.get("quote_or_fact", ""),
                metadata=e.get("metadata", {}),
            )
            for e in item["evidence"]
        )
        cases.append(
            ClaimCase(
                case_id=item["case_id"],
                subject=item["subject"],
                statement_date=item["statement_date"],
                claim_text=item["claim_text"],
                claim_source_url=item["claim_source_url"],
                claim_source_type=SourceType(item["claim_source_type"]),
                rule=item["rule"],
                evidence=evidence,
                expected_evaluation_outcome=EvaluationOutcome(
                    item["expected_evaluation_outcome"]
                ),
                expected_publication=FindingPublicationStatus(
                    item["expected_publication"]
                ),
                notes=item.get("notes", ""),
            )
        )
    return cases


def run_benchmark(path: Path = DEFAULT_FIXTURES) -> dict:
    rows = []
    passed = 0
    cases = load_cases(path)
    for case in cases:
        candidate = evaluate_case(case)
        decision = apply_publication_gate(case, candidate)
        ok = (
            candidate.evaluation_outcome == case.expected_evaluation_outcome
            and decision.publication == case.expected_publication
        )
        passed += int(ok)
        rows.append(
            {
                "case_id": case.case_id,
                "subject": case.subject,
                "evaluation_outcome": candidate.evaluation_outcome.value,
                "publication": decision.publication.value,
                "expected_evaluation_outcome": (
                    case.expected_evaluation_outcome.value
                ),
                "expected_publication": case.expected_publication.value,
                "pass": ok,
                "rationale": decision.rationale,
                "reason_codes": list(decision.reason_codes),
            }
        )
    return {
        "passed": passed,
        "total": len(cases),
        "pass_rate": passed / len(cases) if cases else 0.0,
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.fixtures)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"Benchmark: {result['passed']}/{result['total']} passed ({result['pass_rate']:.0%})")
    for row in result["cases"]:
        marker = "PASS" if row["pass"] else "FAIL"
        print(
            f"[{marker}] {row['case_id']}: "
            f"{row['evaluation_outcome']} / {row['publication']} — "
            f"{row['rationale']}"
        )


if __name__ == "__main__":
    main()
