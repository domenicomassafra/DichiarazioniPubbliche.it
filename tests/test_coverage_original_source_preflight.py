import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


class FakeCoverageStore(QueueRuntimeStore):
    def __init__(self, *, need_type, families, edges):
        super().__init__(database_url=None, psql="unused")
        self.need_type = need_type
        self.families = families
        self.edges = edges
        self.satisfaction_called = False

    def run(self, sql: str, **variables):
        if "FROM coverage_need" in sql and "need_type" in sql and "json_build_object" in sql:
            return json.dumps(
                {
                    "id": variables["coverage_need_id"],
                    "need_type": self.need_type,
                    "status": "OPEN",
                }
            )
        if "WITH matching_family" in sql:
            return json.dumps({"families": self.families, "edges": self.edges})
        if "SET status='SATISFIED'" in sql:
            self.satisfaction_called = True
            return "SATISFIED"
        raise AssertionError(f"unexpected SQL: {sql[:120]}")


class CoverageOriginalSourcePreflightTests(unittest.TestCase):
    def root_family(self):
        return [
            {
                "id": "family:1",
                "root_content_id": "content:root",
                "status": "APPROVED",
            }
        ]

    def test_non_original_need_keeps_existing_satisfaction_behavior(self):
        store = FakeCoverageStore(need_type="OFFICIAL_RECORD", families=[], edges=[])
        result = store.satisfy_coverage_need(
            coverage_need_id="need:1",
            event_id="event:1",
            content_id="content:any",
        )
        self.assertEqual(result, "SATISFIED")
        self.assertTrue(store.satisfaction_called)

    def test_primary_need_accepts_reviewed_root_content(self):
        store = FakeCoverageStore(
            need_type="PRIMARY_SOURCE",
            families=self.root_family(),
            edges=[],
        )
        result = store.satisfy_coverage_need(
            coverage_need_id="need:1",
            event_id="event:1",
            content_id="content:root",
        )
        self.assertEqual(result, "SATISFIED")
        self.assertTrue(store.satisfaction_called)

    def test_primary_need_rejects_derived_copy_and_reports_root(self):
        store = FakeCoverageStore(
            need_type="PRIMARY_SOURCE",
            families=self.root_family(),
            edges=[
                {
                    "id": "edge:1",
                    "family_id": "family:1",
                    "derived_content_id": "content:copy",
                    "origin_content_id": "content:root",
                    "relation_type": "REPUBLICATION",
                    "status": "APPROVED",
                }
            ],
        )
        with self.assertRaisesRegex(
            ValueError,
            "COVERAGE_NEED_ORIGINAL_SOURCE_REFUSED:DERIVED_CONTENT_NOT_ORIGINAL_ROOT:content:root",
        ):
            store.satisfy_coverage_need(
                coverage_need_id="need:1",
                event_id="event:1",
                content_id="content:copy",
            )
        self.assertFalse(store.satisfaction_called)

    def test_primary_need_rejects_unknown_original_without_reviewed_family(self):
        store = FakeCoverageStore(
            need_type="PRIMARY_SOURCE",
            families=[],
            edges=[],
        )
        with self.assertRaisesRegex(
            ValueError,
            "NO_APPROVED_DERIVATION_FAMILY",
        ):
            store.satisfy_coverage_need(
                coverage_need_id="need:1",
                event_id="event:1",
                content_id="content:unknown",
            )
        self.assertFalse(store.satisfaction_called)

    def test_attribution_gap_uses_same_original_source_gate(self):
        store = FakeCoverageStore(
            need_type="ATTRIBUTION_GAP",
            families=self.root_family(),
            edges=[],
        )
        preflight = store.coverage_need_original_source_preflight(
            coverage_need_id="need:1",
            content_id="content:root",
        )
        self.assertTrue(preflight["required"])
        self.assertTrue(preflight["accepted"])


if __name__ == "__main__":
    unittest.main()
