from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues
from dichiarazioni_pubbliche.studio_discovery_detail import present_discovery_detail
from dichiarazioni_pubbliche.studio_local_api import _dispatch, StudioLocalReaders
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page
from tools.check_studio_discovery_inspect_sql import (
    synthetic_inspection_sql, evaluate_synthetic_rows,
)


def fixture(**changed):
    values = dict(
        id="hit:1", collection_id="research:1", run_id="run:1",
        attempt_id="attempt:1", query_id="query:1", manifest_id="manifest:1",
        content_id="content:1", disposition="NEW_CONTENT", reason_code=None,
        source_family="REPORTING", collection_status="ACTIVE",
        manifest_status="ACTIVE", run_status="COMPLETED", attempt_status="HEALTHY",
        lineage_ok=True, manifest_digest_ok=True, family_ok=True, adapter_ok=True,
        url_ok=True, membership_status="INCLUDED", capture_authorized=True,
        content_rights_status="CLEARED", canonical_url="https://PRIVATE.example/secret",
        title="DO NOT LEAK", metadata={"private_body": "DO NOT LEAK"},
    )
    return values | changed


class FakeQueue(StudioOperatorQueues):
    def __init__(self, rows=(), error=None):
        self.rows = rows
        self.error = error
        self.calls = []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        if self.error:
            raise self.error
        return "\n".join(json.dumps(row) for row in self.rows)


class DiscoveryInspectTests(unittest.TestCase):
    def test_exact_persisted_provenance_read_only_without_private_fields(self):
        store = FakeQueue([fixture()])
        result = store.inspect_discovery(collection_id="research:1", hit_id="hit:1")
        self.assertEqual(result["provenance_path"]["attempt_id"], "attempt:1")
        self.assertEqual(result["lineage_blockers"], [])
        self.assertTrue(result["lineage_checks_passed"])
        self.assertIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", result["blockers"])
        self.assertIn("DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE", result["blockers"])
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["triage_action_authorized"])
        self.assertFalse(result["capture_authorized"])
        self.assertNotIn("DO NOT LEAK", json.dumps(result))
        self.assertNotIn("https://PRIVATE.example", json.dumps(result))
        self.assertNotIn("canonical_url", json.dumps(result))
        sql, args = store.calls[0]
        self.assertIn("manifest.collection_id=:'collection_id'", sql)
        self.assertIn("hit.id=:'hit_id'", sql)
        self.assertIn("attempt.query_id=hit.query_id", sql)
        self.assertIn("discovery_query.manifest_id=manifest.id", sql)
        self.assertNotIn("'title', hit.title", sql)
        self.assertEqual(args, {"collection_id": "research:1", "hit_id": "hit:1"})

    def test_blocker_conditions_are_deterministic_and_not_approval(self):
        result = present_discovery_detail(fixture(
            collection_status="PAUSED", attempt_status="FAILED",
            lineage_ok=False, url_ok=False, content_rights_status="UNKNOWN",
            capture_authorized=False, disposition="REJECTED_POLICY",
        ))
        self.assertIn("COLLECTION_NOT_ACTIVE", result["blockers"])
        self.assertIn("DISCOVERY_ATTEMPT_NOT_HEALTHY", result["blockers"])
        self.assertIn("DISCOVERY_URL_BINDING_MISMATCH", result["blockers"])
        self.assertIn("DISCOVERY_CONTENT_RIGHTS_UNCLEARED", result["blockers"])
        self.assertIn("DISCOVERY_CAPTURE_NOT_AUTHORIZED", result["blockers"])
        self.assertFalse(result["lineage_checks_passed"])
        self.assertTrue(all(item["condition"] for item in result["unblock_conditions"]))
        self.assertEqual(len(result["blockers"]), len(result["unblock_conditions"]))
        self.assertFalse(result["publication_authority"])

    def test_malformed_result_scope_and_leak_fails_closed(self):
        store = FakeQueue([fixture(id="hit:other")])
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            store.inspect_discovery(collection_id="research:1", hit_id="hit:1")
        for changed in (
            {"attempt_id": "bad\nID"}, {"lineage_ok": "true"},
            {"source_family": "UNSAFE\nFAMILY"}, {"reason_code": "<secret>"},
            {"run_status": None}, {"disposition": "APPROVED"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                FakeQueue([fixture(**changed)]).inspect_discovery(
                    collection_id="research:1", hit_id="hit:1",
                )
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            FakeQueue().inspect_discovery(collection_id="research:1", hit_id="hit:1")
        with self.assertRaisesRegex(RuntimeError, "STORE_UNAVAILABLE") as caught:
            FakeQueue(error=RuntimeError("PASSWORD=NOT_PUBLIC")).inspect_discovery(
                collection_id="research:1", hit_id="hit:1",
            )
        self.assertNotIn("NOT_PUBLIC", str(caught.exception))

    def test_api_rejects_extra_fields_and_dispatches_read_only_inspection(self):
        queue = FakeQueue([fixture()])
        readers = StudioLocalReaders(corpus=None, captures=None, candidates=None, queues=queue)
        result = _dispatch(readers, "/v1/discovery/inspect",
                           {"collection_id": "research:1", "hit_id": "hit:1"})
        self.assertEqual(result["provenance_path"]["run_id"], "run:1")
        for bad in (
            {"collection_id": "research:1"},
            {"collection_id": "research:1", "hit_id": "hit:1", "approve": True},
        ):
            with self.assertRaises(ValueError):
                _dispatch(readers, "/v1/discovery/inspect", bad)

    def test_page_exposes_read_only_inspection_without_review_actions(self):
        page = render_studio_login_page("a" * 32).decode()
        self.assertIn('data-endpoint="/v1/discovery/inspect"', page)
        self.assertIn('name="collection_id"', page)
        self.assertIn('name="hit_id"', page)
        self.assertIn("non approvazioni automatiche", page)

    def test_rollback_canary_checks_actual_sql_positive_and_revoked_attempt(self):
        statement = synthetic_inspection_sql()
        self.assertEqual(statement.count("ROLLBACK;"), 1)
        self.assertEqual(statement.count("FROM research_discovery_hit hit"), 2)
        self.assertIn("CREATE TEMP TABLE research_discovery_hit", statement)
        raw = "\n".join(json.dumps(case) for case in (
            fixture(), fixture(attempt_status="FAILED"),
        ))
        self.assertTrue(evaluate_synthetic_rows(raw)["failed_attempt_blocker_detected"])
        with self.assertRaisesRegex(RuntimeError, "REVOCATION"):
            evaluate_synthetic_rows("\n".join(json.dumps(fixture()) for _ in range(2)))


if __name__ == "__main__":
    unittest.main()
