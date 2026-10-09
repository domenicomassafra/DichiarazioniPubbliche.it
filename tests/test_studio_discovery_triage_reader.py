"""DP-417: read-only scoped triage history never grants reviewer authority."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_discovery_triage_reader import (  # noqa: E402
    _TRIAGE_HISTORY_SQL, read_triage_history,
)
from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues  # noqa: E402
from dichiarazioni_pubbliche.studio_local_api import (  # noqa: E402
    _ALLOWED_PATHS, _dispatch, StudioLocalReaders,
)
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page  # noqa: E402


def fixture(**override):
    return {
        "collection_id": "research:one", "hit_id": "hit:one",
        "lineage_ok": True, "head_revision": 2, "ledger_count": 2,
        "decisions": [
            {"revision": 1, "expected_revision": 0, "decision": "NEEDS_REVIEW",
             "source_url": "https://private.example/token"},
            {"revision": 2, "expected_revision": 1, "decision": "DEFERRED",
             "actor_ref": "private-operator", "body": "SECRET SOURCE"},
        ],
        "source_query": "SECRET QUERY", "raw_receipts": {"token": "SECRET KEY"},
    } | override


class Queue(StudioOperatorQueues):
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.calls = []

    def run(self, sql, **vars):
        self.calls.append((sql, vars))
        if self.error is not None:
            raise self.error
        return json.dumps(self.row) if self.row is not None else ""


class TriageHistoryTests(unittest.TestCase):
    def test_paged_allowlisted_history_no_public_authority(self):
        queue = Queue(fixture())
        value = queue.inspect_discovery_triage(
            collection_id="research:one", hit_id="hit:one", limit=2,
            after_revision=0,
        )
        self.assertEqual(value["results"], [
            {"revision": 1, "decision": "NEEDS_REVIEW"},
            {"revision": 2, "decision": "DEFERRED"},
        ])
        self.assertNotIn("ledger_count", value)
        self.assertEqual(value["next_after_revision"], 2)
        self.assertEqual(value["head_revision"], 2)
        self.assertFalse(value["publication_authority"])
        self.assertFalse(value["rights_clearance"])
        self.assertFalse(value["reviewer_identity_attested"])
        self.assertFalse(value["triage_action_authorized"])
        self.assertIn("TRIAGE_REVIEWER_AUTHORITY_NOT_REEVALUATED", value["blockers"])
        self.assertNotIn("private.example", json.dumps(value))
        self.assertNotIn("SECRET", json.dumps(value))
        sql, vars = queue.calls[0]
        self.assertEqual(vars, {
            "collection_id": "research:one", "hit_id": "hit:one",
            "limit": 2, "after_revision": 0,
        })
        self.assertIn("manifest.collection_id=:'collection_id'", sql)
        self.assertIn("history.collection_id=:'collection_id'", sql)
        self.assertIn("history.revision > :'after_revision'::bigint", sql)
        self.assertNotIn("actor_ref", sql)
        self.assertNotIn("payload_sha256", sql)
        self.assertNotIn("canonical_url", sql)

    def test_mutated_lineage_is_reported_not_hidden_or_authorized(self):
        queue = Queue(fixture(lineage_ok=False, head_revision=0, ledger_count=0, decisions=[]))
        value = queue.inspect_discovery_triage(
            collection_id="research:one", hit_id="hit:one",
        )
        self.assertEqual(value["results"], [])
        self.assertIn("DISCOVERY_LINEAGE_MISMATCH", value["blockers"])
        self.assertFalse(value["publication_authority"])

    def test_scope_invalid_rows_and_bogus_history_fail_closed(self):
        for change in (
            {"collection_id": "research:other"},
            {"hit_id": "hit:other"},
            {"lineage_ok": "true"},
            {"head_revision": True},
            {"head_revision": -1},
            {"decisions": "SECRET"},
            {"decisions": [{"revision": 2, "expected_revision": 0,
                            "decision": "DEFERRED"}]},
            {"decisions": [{"revision": 1, "expected_revision": 0,
                            "decision": "PUBLISHED"}]},
            {"decisions": [{"revision": 1, "expected_revision": 0,
                            "decision": "DEFERRED"}] * 2},
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "RESULT_INVALID"):
                Queue(fixture(**change)).inspect_discovery_triage(
                    collection_id="research:one", hit_id="hit:one",
                )
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            Queue().inspect_discovery_triage(
                collection_id="research:one", hit_id="hit:one",
            )
        with self.assertRaisesRegex(RuntimeError, "STORE_UNAVAILABLE") as caught:
            Queue(error=RuntimeError("PRIVATE PASSWORD")).inspect_discovery_triage(
                collection_id="research:one", hit_id="hit:one",
            )
        self.assertNotIn("PASSWORD", str(caught.exception))
        for wrong_args in (
            {"limit": True}, {"limit": 31}, {"after_revision": -1},
            {"after_revision": "0"}, {"hit_id": "hit:secret\nBAD"},
        ):
            with self.subTest(args=wrong_args), self.assertRaises(ValueError):
                Queue(fixture()).inspect_discovery_triage(
                    **({"collection_id": "research:one", "hit_id": "hit:one"} | wrong_args),
                )

    def test_reader_rejects_missing_deleted_or_inconsistent_ledger_events(self):
        first = {"revision": 1, "expected_revision": 0, "decision": "NEEDS_REVIEW"}
        second = {"revision": 2, "expected_revision": 1, "decision": "DEFERRED"}
        third = {"revision": 3, "expected_revision": 2, "decision": "REJECTED"}
        for change in (
            # MAX(revision) cannot establish completeness if a row is lost.
            {"head_revision": 3, "ledger_count": 2, "decisions": [first, third]},
            {"head_revision": 3, "ledger_count": 3, "decisions": [second, third]},
            {"ledger_count": 1},
            {"ledger_count": 3},
            {"ledger_count": True},
            {"ledger_count": "2"},
            {"ledger_count": -1},
            # SQL LIMIT 20 would return both records for a genuine head 2.
            {"decisions": [first]},
            {"decisions": []},
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "RESULT_INVALID"):
                Queue(fixture(**change)).inspect_discovery_triage(
                    collection_id="research:one", hit_id="hit:one",
                )

    def test_sql_counts_scoped_ledger_rows_before_redacting_history(self):
        self.assertIn("'ledger_count'", _TRIAGE_HISTORY_SQL)
        self.assertIn("count(*)", _TRIAGE_HISTORY_SQL.lower())
        self.assertIn("history.collection_id=:'collection_id'", _TRIAGE_HISTORY_SQL)
        # Overshot cursors are legitimate empty pages, but cannot reinterpret
        # a missing history as a zero-head response.
        value = Queue(fixture(decisions=[])).inspect_discovery_triage(
            collection_id="research:one", hit_id="hit:one", after_revision=3,
        )
        self.assertEqual(value["results"], [])
        self.assertIsNone(value["next_after_revision"])

    def test_local_api_and_browser_are_read_only(self):
        self.assertIn("/v1/discovery/triage-history", _ALLOWED_PATHS)
        self.assertNotIn("/v1/discovery/triage", _ALLOWED_PATHS)
        queue = Queue(fixture(decisions=[
            {"revision": 1, "expected_revision": 0, "decision": "REJECTED"}
        ], head_revision=1, ledger_count=1))
        readers = StudioLocalReaders(corpus=None, captures=None, candidates=None, queues=queue)
        data = _dispatch(readers, "/v1/discovery/triage-history", {
            "collection_id": "research:one", "hit_id": "hit:one", "limit": 10,
        })
        self.assertEqual(data["results"][0]["decision"], "REJECTED")
        with self.assertRaisesRegex(ValueError, "FIELDS_INVALID"):
            _dispatch(readers, "/v1/discovery/triage-history", {
                "collection_id": "research:one", "hit_id": "hit:one", "approve": True,
            })
        page = render_studio_login_page("a" * 32).decode()
        self.assertIn('data-endpoint="/v1/discovery/triage-history"', page)
        self.assertIn("name=\"after_revision\"", page)
        self.assertIn("Dopo revisione", page)
        self.assertIn("|| key === 'after_revision'", page)
        self.assertNotIn('data-endpoint="/v1/discovery/triage"', page)

    def test_real_postgres_migrated_history_and_wrong_collection_fence(self):
        # Reuse the other DP-417 suite's ephemeral PostgreSQL fixture rather
        # than ever mutating the MiniPC's durable schema or production rows.
        from tests.test_studio_discovery_triage_schema import DiscoveryTriageSchemaTests
        from dichiarazioni_pubbliche.studio_discovery_triage_store import StudioDiscoveryTriageStore

        cluster = DiscoveryTriageSchemaTests
        cluster.setUpClass()
        try:
            fixture_test = cluster("test_append_only_history_preserves_disposition")
            fixture_test.setUp()
            store = StudioDiscoveryTriageStore(database_url=cluster.url)
            queue = StudioOperatorQueues(database_url=cluster.url)
            empty = queue.inspect_discovery_triage(
                collection_id="collection:one", hit_id=fixture_test.hit, limit=1,
            )
            self.assertEqual(empty["head_revision"], 0)
            self.assertEqual(empty["results"], [])
            common = {
                "collection_id": "collection:one",
                "hit_id": fixture_test.hit,
                "actor_ref": "operator:fixture-only",
            }
            first = store.record(**common, request_key="history:one",
                                 decision="NEEDS_REVIEW", expected_revision=0)
            second = store.record(**common, request_key="history:two",
                                  decision="DEFERRED", expected_revision=1)
            self.assertEqual((first["result_code"], second["result_code"]),
                             ("CREATED", "CREATED"))
            part1 = queue.inspect_discovery_triage(
                collection_id="collection:one", hit_id=fixture_test.hit, limit=1,
            )
            self.assertEqual(part1["results"], [{"revision": 1, "decision": "NEEDS_REVIEW"}])
            self.assertEqual(part1["head_revision"], 2)
            self.assertEqual(part1["next_after_revision"], 1)
            part2 = queue.inspect_discovery_triage(
                collection_id="collection:one", hit_id=fixture_test.hit, limit=1,
                after_revision=1,
            )
            self.assertEqual(part2["results"], [{"revision": 2, "decision": "DEFERRED"}])
            self.assertTrue(part2["lineage_ok"])
            self.assertFalse(part2["reviewer_identity_attested"])
            self.assertNotIn("operator:fixture-only", json.dumps(part2))
            with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
                queue.inspect_discovery_triage(
                    collection_id="collection:two", hit_id=fixture_test.hit,
                )
            with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
                queue.inspect_discovery_triage(
                    collection_id="collection:one", hit_id="hit:missing",
                )
            # Corrupt *only this disposable local fixture*, simulating a
            # missing first event under an otherwise valid head revision.
            # Production forbids DELETE; the reader must independently detect
            # the broken chain if storage has been damaged or restored badly.
            cluster.require_sql(
                "ALTER TABLE research_discovery_triage_decision "
                "DISABLE TRIGGER research_discovery_triage_decision_append_only;"
            )
            try:
                self.assertEqual(cluster.require_sql(
                    "DELETE FROM research_discovery_triage_decision "
                    f"WHERE hit_id='{fixture_test.hit}' AND revision=1 RETURNING revision;"
                ), "1")
            finally:
                cluster.require_sql(
                    "ALTER TABLE research_discovery_triage_decision "
                    "ENABLE TRIGGER research_discovery_triage_decision_append_only;"
                )
            with self.assertRaisesRegex(ValueError, "STUDIO_TRIAGE_HISTORY_RESULT_INVALID"):
                queue.inspect_discovery_triage(
                    collection_id="collection:one", hit_id=fixture_test.hit,
                )
        finally:
            cluster.tearDownClass()


if __name__ == "__main__":
    unittest.main()
