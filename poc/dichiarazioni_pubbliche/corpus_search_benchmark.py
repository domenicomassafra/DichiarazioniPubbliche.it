from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from dichiarazioni_pubbliche.corpus_search import CorpusSearchRequest, CorpusSearchStore


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "corpus-search-benchmark-v1.json"


@dataclass(frozen=True)
class SearchBenchmarkCase:
    id: str
    query: str
    expected_any_ids: tuple[str, ...]
    requires_trigram: bool = False
    filters: dict[str, Any] | None = None


@dataclass(frozen=True)
class SearchBenchmarkCaseResult:
    id: str
    query: str
    passed: bool
    expected_any_ids: tuple[str, ...]
    returned_ids: tuple[str, ...]
    elapsed_ms: float
    requires_trigram: bool


@dataclass(frozen=True)
class SearchBenchmarkReport:
    version: str
    total: int
    passed: int
    case_recall: float
    p95_ms: float
    minimum_case_recall: float
    cases: tuple[SearchBenchmarkCaseResult, ...]
    trigram_plan: str | None

    @property
    def meets_gate(self) -> bool:
        return self.case_recall >= self.minimum_case_recall

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total": self.total,
            "passed": self.passed,
            "case_recall": self.case_recall,
            "p95_ms": self.p95_ms,
            "minimum_case_recall": self.minimum_case_recall,
            "meets_gate": self.meets_gate,
            "trigram_plan": self.trigram_plan,
            "cases": [
                {
                    "id": c.id,
                    "query": c.query,
                    "passed": c.passed,
                    "expected_any_ids": list(c.expected_any_ids),
                    "returned_ids": list(c.returned_ids),
                    "elapsed_ms": c.elapsed_ms,
                    "requires_trigram": c.requires_trigram,
                }
                for c in self.cases
            ],
        }


def load_fixture(path: Path = DEFAULT_FIXTURE) -> tuple[str, int, float, tuple[SearchBenchmarkCase, ...]]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("SEARCH_BENCHMARK_FIXTURE_INVALID")
    version = str(raw.get("version") or "").strip()
    if version != "corpus-search-benchmark-v1":
        raise ValueError("SEARCH_BENCHMARK_VERSION_MISMATCH")
    top_k = int(raw.get("top_k") or 5)
    if not 1 <= top_k <= 20:
        raise ValueError("SEARCH_BENCHMARK_TOP_K_INVALID")
    minimum = float(raw.get("minimum_case_recall") or 0.9)
    cases: list[SearchBenchmarkCase] = []
    for item in raw.get("cases") or []:
        expected = tuple(str(x) for x in item.get("expected_any_ids") or [])
        if not expected:
            raise ValueError("SEARCH_BENCHMARK_EXPECTED_IDS_REQUIRED")
        cases.append(
            SearchBenchmarkCase(
                id=str(item["id"]),
                query=str(item["query"]),
                expected_any_ids=expected,
                requires_trigram=bool(item.get("requires_trigram")),
                filters=dict(item.get("filters") or {}),
            )
        )
    if not cases:
        raise ValueError("SEARCH_BENCHMARK_CASES_REQUIRED")
    return version, top_k, minimum, tuple(cases)


def _percentile_95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999)))
    return ordered[index]


def run_benchmark(
    store: CorpusSearchStore,
    *,
    fixture: Path = DEFAULT_FIXTURE,
) -> SearchBenchmarkReport:
    version, top_k, minimum, cases = load_fixture(fixture)
    results: list[SearchBenchmarkCaseResult] = []
    for case in cases:
        request = CorpusSearchRequest(query=case.query, limit=top_k, **(case.filters or {}))
        started = time.perf_counter()
        returned = store.search(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        ids = tuple(item.id for item in returned[:top_k])
        results.append(
            SearchBenchmarkCaseResult(
                id=case.id,
                query=case.query,
                passed=bool(set(ids) & set(case.expected_any_ids)),
                expected_any_ids=case.expected_any_ids,
                returned_ids=ids,
                elapsed_ms=round(elapsed_ms, 3),
                requires_trigram=case.requires_trigram,
            )
        )
    passed = sum(1 for item in results if item.passed)
    typo_queries = [case.query for case in cases if case.requires_trigram]
    trigram_plan = store.trigram_plan_probe(typo_queries[0]) if typo_queries else None
    return SearchBenchmarkReport(
        version=version,
        total=len(results),
        passed=passed,
        case_recall=passed / len(results),
        p95_ms=round(_percentile_95([item.elapsed_ms for item in results]), 3),
        minimum_case_recall=minimum,
        cases=tuple(results),
        trigram_plan=trigram_plan,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the private corpus search benchmark")
    parser.add_argument("--database-url")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_benchmark(CorpusSearchStore(database_url=args.database_url), fixture=args.fixture)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"Corpus search benchmark: {report.passed}/{report.total} "
            f"({report.case_recall:.1%}), p95={report.p95_ms:.1f}ms, gate={report.meets_gate}"
        )
        for case in report.cases:
            state = "PASS" if case.passed else "FAIL"
            print(f"[{state}] {case.id}: {case.query} -> {', '.join(case.returned_ids)}")
        if report.trigram_plan:
            print("Trigram plan probe:")
            print(report.trigram_plan)
    return 0 if report.meets_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
