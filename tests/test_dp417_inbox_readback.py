"""DP-417: a source-less runtime must not be reported as a successful Inbox."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/dp417_inbox_readback.py"
SPEC = importlib.util.spec_from_file_location("dp417_inbox_readback", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Dp417ReadbackTests(unittest.TestCase):
    def test_no_runs_does_not_claim_acceptance(self):
        counts = dict.fromkeys(module._COUNTS, 0)
        counts["collections"] = 1
        result = module.summarize(counts)
        self.assertFalse(result["runtime_acceptance_proven"])
        self.assertEqual(result["blockers"], [
            "NO_PERSISTED_DISCOVERY_RUN", "NO_PERSISTED_DISCOVERY_HIT",
        ])
        self.assertNotIn("collection_id", result)

    def test_real_counts_cannot_confer_source_rights_or_approval(self):
        counts = {
            "collections": 1, "manifests": 1, "runs": 2,
            "completed_runs": 2, "blocked_runs": 0,
            "hits": 3, "annotated_hits": 1, "invalid_lineage_hits": 0,
            "incomplete_runs": 0,
        }
        result = module.summarize(counts)
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["runtime_acceptance_proven"])
        self.assertFalse("source_url" in str(result))
        self.assertIn("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                      module.READBACK_SQL)

    def test_blocked_run_with_hits_is_not_silently_clean(self):
        counts = dict.fromkeys(module._COUNTS, 0)
        counts.update(runs=1, blocked_runs=1, hits=1)
        self.assertIn("BLOCKED_OR_FAILED_DISCOVERY_RUN", module.summarize(counts)["blockers"])

    def test_running_or_partial_run_with_hits_is_not_silently_clean(self):
        counts = dict.fromkeys(module._COUNTS, 0)
        counts.update(runs=2, completed_runs=1, hits=1, incomplete_runs=1)
        self.assertIn("INCOMPLETE_DISCOVERY_RUN", module.summarize(counts)["blockers"])

    def test_mismatched_annotation_collection_counts_as_invalid_lineage(self):
        self.assertIn("research_discovery_triage_decision", module.READBACK_SQL)
        self.assertIn("decision.collection_id IS DISTINCT FROM manifest.collection_id", module.READBACK_SQL)

    def test_invalid_store_rows_fail_closed(self):
        counts = dict.fromkeys(module._COUNTS, 0)
        for bad in (
            counts | {"hits": True}, counts | {"runs": -1},
            counts | {"completed_runs": 1}, counts | {"unexpected": 1},
            counts | {"hits": 1, "annotated_hits": 2},
            counts | {"runs": 1},
            counts | {"runs": 1, "incomplete_runs": 2},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                module.validate_readback(bad)


if __name__ == "__main__":
    unittest.main()
