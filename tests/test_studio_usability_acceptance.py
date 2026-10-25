"""DP-420: operator acceptance must never be certified by search fixtures alone."""

import json
import unittest

from dichiarazioni_pubbliche.studio_usability_acceptance import (
    evaluate_acceptance, read_live_collection_counts,
)


def snapshot(*, captures=0, passages=0, candidates=0):
    return {
        "counts": {
            "captures": captures,
            "passages": passages,
            "statement_candidates": candidates,
            "claim_candidates": candidates,
        },
        "seed_sha256": "a" * 64,
        "private_only": True,
        "publication_authority": False,
    }


def search_results(*, passed=True):
    return {"total": 13, "passed": 13 if passed else 12, "case_recall": 1.0 if passed else 12 / 13,
            "p95_ms": 72.5, "minimum_case_recall": 0.9,
            "cases": [{"id": task_id, "passed": passed or task_id != "dna-unghie-sempio"} for task_id in (
                "dna-unghie-sempio", "tappetini-sangue-scarpe", "impronta-33-sangue",
                "impronta-33-typo", "cromosoma-y-typo", "pena-rito-abbreviato",
                "pc-poggi-10-agosto", "frammenti-audio", "aggravante-crudelta",
                "pasti-chiara-stasi", "rinvio-giudizio-sempio",
                "person-bruzzone", "person-lucarelli",
            )]}


class GarlascoUsabilityAcceptanceTests(unittest.TestCase):
    def test_readback_counts_all_included_collection_sources_not_just_historic_claims(self):
        class CollectionReader:
            sql = ""

            def run(self, sql):
                self.sql = sql
                return json.dumps({
                    "captures": 2, "passages": 3, "statement_candidates": 1,
                    "claim_candidates": 1, "collection_coverage_needs": 4,
                })

        reader = CollectionReader()
        counts = read_live_collection_counts(reader)
        self.assertEqual(counts["captures"], 2)
        self.assertEqual(counts["passages"], 3)
        self.assertEqual(counts["statement_candidates"], 1)
        self.assertIn("research_collection_content", reader.sql.lower())
        self.assertIn("research:garlasco", reader.sql.lower())
        self.assertIn("status='included'", reader.sql.lower())

    def test_collection_count_readback_fails_closed_on_missing_or_bad_data(self):
        class CollectionReader:
            def __init__(self, response):
                self.response = response

            def run(self, sql):
                return self.response

        for response in ('{}', '{"captures": -1}', 'not-json',
                         '{"captures": 1, "passages": 0, "statement_candidates": 0, '
                         '"claim_candidates": true, "collection_coverage_needs": 0}'):
            with self.subTest(response=response), self.assertRaises(ValueError):
                read_live_collection_counts(CollectionReader(response))

    def test_20_real_operator_tasks_and_six_accessibility_modes_are_required(self):
        result = evaluate_acceptance(snapshot(), search_results())
        self.assertEqual(result["total_tasks"], 20)
        self.assertEqual(result["search_cases_passed"], 13)
        self.assertEqual(result["search_cases_total"], 13)
        self.assertEqual(result["operator_passed"], 0)
        self.assertEqual(result["operator_hold"], 20)
        self.assertEqual(result["mode_hold"], 6)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["accepted"])
        self.assertFalse(result["publication_authority"])

    def test_claims_of_success_without_captures_and_passages_remain_hold(self):
        claimed = {"tasks": {name: {"status": "PASS", "time_to_source_ms": 5000,
                                   "actions": 2, "navigation_errors": 0, "evidence_ref": "sha256:" + "f" * 64}
                             for name in ("source-capture", "passage-citation", "candidate-source")}}
        result = evaluate_acceptance(snapshot(), search_results(), observations=claimed)
        self.assertEqual(result["operator_passed"], 0)
        self.assertEqual(result["status"], "HOLD")

    def test_task_result_requires_valid_measures_and_provenance(self):
        claimed = {"tasks": {"source-capture": {"status": "PASS", "actions": 2,
                                                "navigation_errors": 0, "time_to_source_ms": 1000}}}
        result = evaluate_acceptance(snapshot(captures=1, passages=1, candidates=1),
                                     search_results(), observations=claimed)
        self.assertEqual(result["operator_passed"], 0)
        self.assertFalse(result["accepted"])

    def test_real_operator_measures_can_pass_one_task_but_never_whole_acceptance(self):
        observed = {"tasks": {"source-capture": {
            "status": "PASS", "actions": 2, "navigation_errors": 0,
            "time_to_source_ms": 1430, "evidence_ref": "sha256:" + "b" * 64,
            "source_id": "source:garlasco-source", "capture_id": "capture:garlasco-capture",
            "rights_record_id": "private-rights:current-garlasco",
        }}}
        result = evaluate_acceptance(snapshot(captures=1), search_results(), observations=observed)
        self.assertEqual(result["operator_passed"], 1)
        self.assertEqual(result["operator_timed_tasks"], 1)
        self.assertEqual(result["operator_time_to_source_p95_ms"], 1430)
        self.assertEqual(result["operator_navigation_errors"], 0)
        self.assertEqual(result["status"], "HOLD")

    def test_operator_failure_and_benchmark_regression_are_visible(self):
        observations = {"tasks": {"find-dna": {"status": "FAIL", "navigation_errors": 1}}}
        result = evaluate_acceptance(snapshot(), search_results(passed=False),
                                     observations=observations)
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(result["operator_failed"], 0)
        self.assertEqual(result["search_cases_passed"], 12)

    def test_candidate_task_cannot_pass_without_candidate_identity(self):
        record = {
            "status": "PASS", "actions": 3, "navigation_errors": 0,
            "time_to_source_ms": 1500, "evidence_ref": "sha256:" + "c" * 64,
            "source_id": "source:real", "capture_id": "capture:real",
            "passage_id": "passage:real", "rights_record_id": "private-rights:real",
        }
        data = snapshot(captures=1, passages=1, candidates=1)
        result = evaluate_acceptance(data, search_results(),
                                     observations={"tasks": {"candidate-source": record}})
        self.assertEqual(result["task_status"]["candidate-source"], "HOLD")
        record["statement_candidate_id"] = "statement-candidate:real"
        result = evaluate_acceptance(data, search_results(),
                                     observations={"tasks": {"candidate-source": record}})
        self.assertEqual(result["task_status"]["candidate-source"], "PASS")

    def test_coverage_gap_can_be_documented_without_nonexistent_source(self):
        data = snapshot()
        data["counts"]["collection_coverage_needs"] = 1
        record = {
            "status": "PASS", "actions": 2, "navigation_errors": 0,
            "time_to_source_ms": 900, "evidence_ref": "sha256:" + "d" * 64,
            "coverage_need_id": "coverage-need:real",
        }
        result = evaluate_acceptance(data, search_results(),
                                     observations={"tasks": {"coverage-gap": record}})
        self.assertEqual(result["task_status"]["coverage-gap"], "PASS")
        del record["coverage_need_id"]
        result = evaluate_acceptance(data, search_results(),
                                     observations={"tasks": {"coverage-gap": record}})
        self.assertEqual(result["task_status"]["coverage-gap"], "HOLD")


if __name__ == "__main__":
    unittest.main()
