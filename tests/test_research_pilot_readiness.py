from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.research_pilot_readiness import (
    PILOT_TARGET, ResearchPilotReadinessStore, ReadinessReportError,
    summarize_readiness, load_unreviewed_public_leads,
)
from tools import report_research_pilot


def summary(status="PAUSED", **changes):
    result = dict(collection_id="research:pilot", collection_status=status,
                  members_total=2, persisted_unlinked_discovery_hits=0, discovery_runs=1,
                  baseline_garlasco_claims=30)
    result.update(changes)
    return result


def member(content_id="content:one", **changes):
    result = dict(
        content_id=content_id, membership_status="INCLUDED", capture_authorized=False,
        content_rights_status="UNKNOWN", accepted_discovery_hits=0,
        observed_accepted_source_families=[],
        current_rights_records=0, current_relevance_records=0,
        captures=0, captured_with_body=0, passages=0, statement_candidates=0,
        claim_candidates=0,
    )
    result.update(changes)
    return result


class ReadinessReportTests(unittest.TestCase):
    def test_realistic_paused_collection_is_no_go_with_precise_missing_counts(self):
        items = [member(), member("content:two", membership_status="REMOVED")]
        report = summarize_readiness(summary(), items)
        self.assertEqual(report["status"], "NO_GO_READ_ONLY")
        self.assertEqual(report["included_items"], 1)
        self.assertEqual(report["remaining_to_target"], PILOT_TARGET - 1)
        self.assertFalse(report["target_proven"])
        self.assertEqual(report["persisted_unlinked_discovery_hits"], 0)
        self.assertEqual(report["missing_prerequisite_counts"]["COLLECTION_NOT_ACTIVE"], 1)
        self.assertEqual(report["missing_prerequisite_counts"]["MEMBERSHIP_NOT_INCLUDED"], 1)
        self.assertEqual(report["missing_prerequisite_counts"]["ACCEPTED_DISCOVERY_MISSING"], 1)
        self.assertEqual(report["missing_prerequisite_counts"]["CAPTURE_MISSING"], 1)
        self.assertNotIn("members", report)
        self.assertFalse(report["qualified_rights_verified"])
        self.assertFalse(report["publication_authorized"])
        self.assertEqual(len(report["missing_required_source_families"]), 5)
        self.assertTrue(report["baseline_claim_count_matches"])

    def test_inventory_never_converts_absent_approval_into_go(self):
        ready = member(
            capture_authorized=True, content_rights_status="CLEARED",
            accepted_discovery_hits=1,
            observed_accepted_source_families=["VIDEO_PODCAST"],
            current_rights_records=1,
            current_relevance_records=1, captures=1, captured_with_body=1,
            passages=1, statement_candidates=1, claim_candidates=1,
        )
        report = summarize_readiness(summary(status="ACTIVE", members_total=1), [ready], include_ids=True)
        self.assertEqual(report["missing_prerequisite_counts"], {})
        self.assertEqual(report["stage_presence_counts"]["claim_candidate"], 1)
        self.assertEqual(report["observed_persisted_source_families"], ["VIDEO_PODCAST"])
        self.assertEqual(len(report["missing_required_source_families"]), 4)
        self.assertFalse(report["qualified_rights_verified"])
        self.assertFalse(report["model_provider_verified"])
        self.assertFalse(report["target_proven"])
        self.assertEqual(report["members"][0]["content_id"], "content:one")
        self.assertNotIn("canonical_url", json.dumps(report))

    def test_report_is_idempotent_and_order_independent(self):
        left = member("content:a")
        right = member("content:b", captures=1, captured_with_body=0)
        first = summarize_readiness(summary(), [left, right], include_ids=True)
        second = summarize_readiness(summary(), [right, left], include_ids=True)
        self.assertEqual(first["snapshot_sha256"], second["snapshot_sha256"])
        self.assertEqual(first["stage_presence_counts"]["captured"], 1)
        self.assertEqual(first["missing_prerequisite_counts"]["CAPTURE_NOT_READY_OR_HELD"], 1)

    def test_invalid_counts_duplicates_and_incomplete_snapshots_fail_closed(self):
        for s, m in (
            (summary(members_total=3), [member(), member("content:two")]),
            (summary(), [member(), member()]),
            (summary(), [member(captures=-1), member("content:two")]),
            (summary(), [member(accepted_discovery_hits=True), member("content:two")]),
            (summary(status="UNKNOWN"), [member(), member("content:two")]),
            (summary(persisted_unlinked_discovery_hits=-1), [member(), member("content:two")]),
        ):
            with self.subTest(s=s, m=m), self.assertRaises(ReadinessReportError):
                summarize_readiness(s, m)

    def test_store_queries_use_bounded_safe_sql_and_never_read_private_text(self):
        class Probe(ResearchPilotReadinessStore):
            def __init__(self):
                self.queries = []

            def run(self, sql, **values):
                self.queries.append((sql, values))
                return json.dumps({"summary": summary(members_total=1),
                                   "members": [member()]})

        store = Probe()
        s, rows = store.read_collection("research:pilot")
        self.assertEqual(len(rows), 1)
        self.assertEqual(s["members_total"], 1)
        self.assertEqual(len(store.queries), 1)
        self.assertIn("json_agg(member_row.value::json", store.queries[0][0])
        self.assertIn("LIMIT 2001", store.queries[0][0])
        self.assertTrue(all(q[1] == {"collection_id": "research:pilot"} for q in store.queries))
        self.assertTrue(all("private_text" not in q[0] for q in store.queries))
        with self.assertRaises(ReadinessReportError):
            store.read_collection("bad'\nSELECT 1; --")

    def test_store_snapshot_denies_missing_malformed_drift_and_private_db_errors(self):
        class Probe(ResearchPilotReadinessStore):
            def __init__(self, value):
                self.value = value
            def run(self, sql, **values):
                if isinstance(self.value, Exception):
                    raise self.value
                return self.value

        for response, code in (
            (json.dumps({"summary": None, "members": []}), "COLLECTION_NOT_FOUND"),
            (json.dumps({"summary": summary(members_total=2), "members": [member()]}), "MEMBERSHIP_DRIFT"),
            (json.dumps({"summary": summary(members_total=True), "members": [member()]}), "COUNT_INVALID"),
            (json.dumps({"summary": summary(collection_id="research:other", members_total=1), "members": [member()]}), "COLLECTION_SCOPE_MISMATCH"),
            (json.dumps({"summary": summary(members_total=1), "members": [None]}), "SNAPSHOT_MEMBER_INVALID"),
            (json.dumps({"summary": {}, "members": []}), "COLLECTION_SCOPE_MISMATCH"),
            (json.dumps({"summary": summary(), "members": "private content"}), "SNAPSHOT_INVALID"),
            (json.dumps({"summary": summary(), "members": [], "extra": "leak"}), "SNAPSHOT_INVALID"),
            ("{not-json}", "SNAPSHOT_INVALID"),
            ("x" * 2_000_001, "SNAPSHOT_EMPTY_OR_OVERSIZE"),
            (RuntimeError("password=DO_NOT_EXPOSE"), "SNAPSHOT_STORE_UNAVAILABLE"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(ReadinessReportError, code) as raised:
                Probe(response).read_collection("research:pilot")
            self.assertNotIn("DO_NOT_EXPOSE", str(raised.exception))

    def test_readonly_cli_returns_structured_report_no_mutation(self):
        with patch.object(report_research_pilot, "ResearchPilotReadinessStore") as store:
            store.return_value.read_collection.return_value = (
                summary(members_total=1), [member()],
            )
            from io import StringIO
            from contextlib import redirect_stdout
            output = StringIO()
            with redirect_stdout(output):
                rc = report_research_pilot.main(["--collection-id", "research:pilot"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "NO_GO_READ_ONLY")
            self.assertFalse(json.loads(output.getvalue())["publication_authorized"])

    def test_separate_real_public_candidate_file_has_no_authority(self):
        file = ROOT / "config" / "garlasco-public-discovery-leads.v1.json"
        hints = load_unreviewed_public_leads(file)
        self.assertEqual(hints["unreviewed_file_candidates"], 6)
        self.assertEqual(hints["source_locator_only"], 1)
        self.assertEqual(hints["file_leads_counted_in_pilot"], 0)
        self.assertFalse(hints["file_candidates_verified_in_postgres"])
        self.assertFalse(hints["file_candidates_capture_authorized"])


if __name__ == "__main__":
    unittest.main()
