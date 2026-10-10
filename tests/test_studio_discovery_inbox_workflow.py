"""DP-417: bounded database-derived Inbox read model and bulk safety gate."""

import json
import unittest
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow, plan_bulk_annotation, render_private_inbox_fragment,
)


def row(hit_id="hit:01", *, disposition="NEW_CONTENT", revision=0,
        latest=None, attempt="HEALTHY", member="INCLUDED", collection="ACTIVE",
        manifest="ACTIVE", run="COMPLETED", rights="CLEARED", lineage=True,
        count=None, query="query:01", content="content:01"):
    return {
        "hit_id": hit_id, "run_id": "run:01", "attempt_id": "attempt:01",
        "query_id": query, "manifest_id": "manifest:01", "collection_id": "collection:01",
        "content_id": content, "disposition": disposition, "reason_code": None,
        "source_family": "official", "adapter_id": "adapter:official",
        "collection_state": collection, "manifest_state": manifest,
        "run_state": run, "attempt_state": attempt,
        "rights_state": rights, "membership_state": member,
        "lineage_ok": lineage, "manifest_digest_ok": True,
        "family_scope_ok": True, "adapter_scope_ok": True,
        "content_url_ok": True,
        "head_revision": revision,
        "ledger_count": revision if count is None else count,
        "latest_decision": latest,
        "url": "https://private.invalid/SHOULD_NEVER_LEAK",
        "query_text": "PRIVATE QUERY SHOULD NEVER LEAK",
    }


class FakeRuntime:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        output = [r for r in self.rows if r["hit_id"] > variables["after_id"]]
        return "\n".join(json.dumps(v) for v in output[:variables["limit"]])


class InboxWorkflowTests(unittest.TestCase):
    def test_database_derived_scoped_queue_provenance_and_no_leak(self):
        runtime = FakeRuntime([row(), row("hit:02", disposition="EXISTING_CONTENT", revision=1, latest="NEEDS_REVIEW")])
        receipt = DiscoveryInboxWorkflow(runtime).list_rows(collection_id="collection:01", limit=2)
        self.assertEqual(len(receipt["rows"]), 2)
        self.assertEqual([r["queue"] for r in receipt["rows"]], ["NEW_CONTENT", "EXISTING_CONTENT"])
        self.assertEqual(receipt["rows"][1]["annotation_revision"], 1)
        self.assertEqual(receipt["rows"][0]["provenance_path"]["manifest_id"], "manifest:01")
        self.assertEqual(receipt["rows"][0]["provenance_path"]["attempt_id"], "attempt:01")
        self.assertEqual(receipt["next_after_id"], "hit:02")
        blob = json.dumps(receipt)
        for sensitive in ("SHOULD_NEVER_LEAK", "PRIVATE QUERY", "source_url", "actor_ref"):
            self.assertNotIn(sensitive, blob)
        sql, bindings = runtime.calls[0]
        self.assertIn("manifest.collection_id=:'collection_id'", sql)
        self.assertIn("research_discovery_triage_decision", sql)
        self.assertEqual(bindings["collection_id"], "collection:01")

    def test_blocker_codes_and_recovery_are_specific(self):
        value = DiscoveryInboxWorkflow(FakeRuntime([
            row(attempt="BUDGET_BLOCKED", member=None, manifest="SUPERSEDED",
                rights="PENDING", revision=1, latest="DEFERRED")
        ])).list_rows(collection_id="collection:01")["rows"][0]
        blockers = value["blockers"]
        self.assertIn("DISCOVERY_ATTEMPT_BUDGET_BLOCKED", blockers)
        self.assertIn("DISCOVERY_MANIFEST_SUPERSEDED", blockers)
        self.assertIn("DISCOVERY_MEMBERSHIP_NOT_INCLUDED", blockers)
        self.assertIn("DISCOVERY_CONTENT_RIGHTS_UNCLEARED", blockers)
        self.assertIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", blockers)
        self.assertFalse(value["current"])
        self.assertFalse(value["action_authorized"])
        conditions = {x["blocker"]: x["unblock_condition"] for x in value["unblock_conditions"]}
        self.assertEqual(conditions["DISCOVERY_ATTEMPT_BUDGET_BLOCKED"], "REAUTHORIZE_BUDGET_AND_RETRY_ATTEMPT")

    def test_incoherent_lineage_is_not_exposed_as_current(self):
        result = DiscoveryInboxWorkflow(FakeRuntime([
            row(lineage=False, revision=3, latest="REJECTED")
        ])).list_rows(collection_id="collection:01")["rows"][0]
        self.assertFalse(result["current"])
        self.assertIn("DISCOVERY_LINEAGE_MISMATCH", result["blockers"])
        self.assertIsNone(result["latest_annotation"])
        self.assertIsNone(result["annotation_revision"])

    def test_tampered_or_gapped_ledger_refused(self):
        for bad in (row(revision=2, count=1, latest="NEEDS_REVIEW"),
                    row(revision=1, latest=None), row(revision=0, latest="REJECTED")):
            with self.subTest(bad=bad["head_revision"]):
                with self.assertRaisesRegex(ValueError, "STUDIO_INBOX_LEDGER_INCOMPLETE"):
                    DiscoveryInboxWorkflow(FakeRuntime([bad])).list_rows(collection_id="collection:01")

    def test_bad_scope_and_large_page_blocked(self):
        instance = DiscoveryInboxWorkflow(FakeRuntime([row()]))
        with self.assertRaises(ValueError):
            instance.list_rows(collection_id="../bad'--")
        with self.assertRaises(ValueError):
            instance.list_rows(collection_id="collection:01", limit=100)
        with self.assertRaises(ValueError):
            instance.list_rows(collection_id="collection:01", after_id="bad\nline")

    def test_safe_bounded_private_html_readonly_fragment(self):
        page = DiscoveryInboxWorkflow(FakeRuntime([row()])).list_rows(collection_id="collection:01")
        rendered = render_private_inbox_fragment(page)
        self.assertIn("Discovery Inbox · sola lettura", rendered)
        self.assertIn("run:01", rendered)
        self.assertIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", rendered)
        self.assertNotIn("private.invalid", rendered)
        self.assertNotIn("PRIVATE QUERY", rendered)
        for forbidden in ("<button", "<form", "onclick=", "<script", "href="):
            self.assertNotIn(forbidden, rendered)
        with self.assertRaisesRegex(ValueError, "FRAGMENT_SCOPE_INVALID"):
            render_private_inbox_fragment(page | {"rows": [page["rows"][0] | {"collection_id": "other"}]})
        with self.assertRaisesRegex(ValueError, "FRAGMENT_ROWS_INVALID"):
            render_private_inbox_fragment(page | {"rows": page["rows"] * 31})

    def test_bulk_allowed_only_homogeneous_metadata_annotations_never_mutates(self):
        runtime = FakeRuntime([row(), row("hit:02")])
        rows = DiscoveryInboxWorkflow(runtime).list_rows(collection_id="collection:01")["rows"]
        plan = plan_bulk_annotation(rows, decision="NEEDS_REVIEW", expected_collection_id="collection:01")
        self.assertEqual(plan["result_code"], "DRY_RUN_ONLY")
        self.assertEqual([x["expected_revision"] for x in plan["items"]], [0, 0])
        self.assertFalse(plan["mutation_authorized"])
        self.assertFalse(plan["publication_authority"])
        self.assertEqual(len(runtime.calls), 1)
        self.assertNotIn("request_key", json.dumps(plan))

    def test_bulk_rejects_mixed_states_risky_actions_or_stale_selection(self):
        good = DiscoveryInboxWorkflow(FakeRuntime([row(), row("hit:02")])).list_rows(collection_id="collection:01")["rows"]
        mismatched = DiscoveryInboxWorkflow(FakeRuntime([row(), row("hit:02", latest="DEFERRED", revision=1)])).list_rows(collection_id="collection:01")["rows"]
        for selection, reason in (
            (mismatched, "BULK_REVIEW_STATES_INCOMPATIBLE"),
            ([good[0], good[0]], "BULK_DUPLICATE_SELECTION"),
            ([good[0], {**good[1], "current": False}], "BULK_ROW_NOT_CURRENT"),
            ([good[0], {**good[1], "annotation_revision": 8}], "BULK_REVIEW_STATES_INCOMPATIBLE"),
            ([good[0], {**good[1], "source_family": "other"}], "BULK_REVIEW_STATES_INCOMPATIBLE"),
            ([good[0], {**good[1], "blockers": ["BUDGET_BLOCKED"]}], "BULK_REVIEW_STATES_INCOMPATIBLE"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ValueError, reason):
                    plan_bulk_annotation(selection, decision="DEFERRED", expected_collection_id="collection:01")
        for forbidden in ("REJECTED", "MERGE", "PROMOTE", "CAPTURE", "PUBLISH"):
            with self.assertRaisesRegex(ValueError, "BULK_ACTION_NOT_ALLOWED"):
                plan_bulk_annotation(good, decision=forbidden, expected_collection_id="collection:01")
        rejected = DiscoveryInboxWorkflow(FakeRuntime([row(revision=1, latest="REJECTED")])).list_rows(
            collection_id="collection:01")["rows"]
        with self.assertRaisesRegex(ValueError, "BULK_REVIEW_STATES_INCOMPATIBLE"):
            plan_bulk_annotation(rejected, decision="NEEDS_REVIEW", expected_collection_id="collection:01")

    def test_real_isolated_postgres_scoped_lineage_history_and_currentness(self):
        # Reuse the established DP-417 fresh-schema ephemeral database fixture.
        # It owns its own PostgreSQL process; no source or prod DB is written.
        from tests.test_studio_discovery_triage_schema import DiscoveryTriageSchemaTests
        from dichiarazioni_pubbliche.studio_discovery_triage_store import StudioDiscoveryTriageStore

        pg = DiscoveryTriageSchemaTests
        pg.setUpClass()
        try:
            prefix = "dp417:inbox"
            digest = "a" * 64
            pg.require_sql(f"""
                INSERT INTO research_collection
                  (id, slug, name, scope_text, policy_version)
                  VALUES ('{prefix}:collection', 'dp417-inbox', 'fixture', 'isolated', 'test-v1');
                INSERT INTO research_discovery_manifest
                  (id, collection_id, manifest_sha256, max_results,
                   max_results_per_host, cost_cap_usd, source_families)
                  VALUES ('{prefix}:manifest', '{prefix}:collection', '{digest}',
                          5, 2, 0.01, '["official"]');
                INSERT INTO research_discovery_query
                  (id, manifest_id, ordinal, query_text, source_families,
                   adapter_ids, max_results)
                  VALUES ('{prefix}:query', '{prefix}:manifest', 0,
                          'PRIVATE SYNTHETIC QUERY', '["official"]', '["adapter:official"]', 5);
                INSERT INTO research_discovery_run
                  (id, manifest_id, manifest_sha256, status)
                  VALUES ('{prefix}:run', '{prefix}:manifest', '{digest}', 'COMPLETED');
                INSERT INTO research_discovery_attempt
                  (id, run_id, query_id, adapter_id, adapter_version, status)
                  VALUES ('{prefix}:attempt', '{prefix}:run', '{prefix}:query',
                          'adapter:official', 'v1', 'HEALTHY');
                INSERT INTO research_discovery_hit
                  (id, run_id, attempt_id, query_id, hit_key, ordinal,
                   canonical_url, source_host, source_family, disposition)
                  VALUES ('{prefix}:hit', '{prefix}:run', '{prefix}:attempt',
                          '{prefix}:query', '{digest}', 0,
                          'https://example.invalid/private', 'example.invalid',
                          'official', 'NEW_CONTENT');
            """, database=pg.fresh_url)
            scope = f"{prefix}:collection"
            queue = DiscoveryInboxWorkflow(PsqlRuntime(database_url=pg.fresh_url))
            rows = queue.list_rows(collection_id=scope)["rows"]
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["current"])
            self.assertEqual(rows[0]["annotation_revision"], 0)
            self.assertIn("DISCOVERY_CONTENT_UNRESOLVED", rows[0]["blockers"])
            self.assertNotIn("PRIVATE SYNTHETIC", json.dumps(rows))
            store = StudioDiscoveryTriageStore(database_url=pg.fresh_url)
            created = store.record(
                collection_id=scope, hit_id=f"{prefix}:hit",
                request_key="dp417-inbox:review:01", decision="NEEDS_REVIEW",
                expected_revision=0, actor_ref="operator:isolated",
            )
            self.assertEqual(created["result_code"], "CREATED")
            with_history = queue.list_rows(collection_id=scope)["rows"][0]
            self.assertEqual(with_history["annotation_revision"], 1)
            self.assertEqual(with_history["latest_annotation"], "NEEDS_REVIEW")
            self.assertEqual(queue.list_rows(collection_id="collection:unrelated")["rows"], [])
            pg.require_sql(
                f"UPDATE research_discovery_manifest SET status='SUPERSEDED' "
                f"WHERE id='{prefix}:manifest';", database=pg.fresh_url,
            )
            superseded = queue.list_rows(collection_id=scope)["rows"][0]
            self.assertFalse(superseded["current"])
            self.assertIn("DISCOVERY_MANIFEST_SUPERSEDED", superseded["blockers"])
            self.assertNotEqual(with_history["snapshot_sha256"], superseded["snapshot_sha256"])
            pg.require_sql(f"""
                INSERT INTO research_discovery_query
                  (id, manifest_id, ordinal, query_text, source_families,
                   adapter_ids, max_results)
                  VALUES ('{prefix}:second-query', '{prefix}:manifest', 1,
                          'PRIVATE OTHER QUERY', '["official"]', '["adapter:official"]', 5);
                UPDATE research_discovery_hit SET query_id='{prefix}:second-query'
                WHERE id='{prefix}:hit';
            """, database=pg.fresh_url)
            stale = queue.list_rows(collection_id=scope)["rows"][0]
            self.assertFalse(stale["current"])
            self.assertIn("DISCOVERY_LINEAGE_MISMATCH", stale["blockers"])
            self.assertIsNone(stale["latest_annotation"])
            self.assertIsNone(stale["annotation_revision"])
        finally:
            pg.tearDownClass()


if __name__ == "__main__":
    unittest.main()
