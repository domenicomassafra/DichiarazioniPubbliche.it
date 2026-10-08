"""Adversarial checks for Capture authorization from completed Discovery lineage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.discovery_provenance import (
    accepted_discovery_family_counts, valid_discovery_hit_groups_sql,
)
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore
from dichiarazioni_pubbliche.private_capture_batch import require_persisted_discovery
from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.research_pilot_readiness import _MEMBER_READ_SQL
from test_private_capture_batch import make_batch, research_context
from tools.check_discovery_provenance_sql import ephemeral_provenance_sql, check_receipts


class DiscoveryProvenanceAuthorizationTests(unittest.TestCase):
    def test_strict_sql_joins_all_lineage_and_enforces_a_healthy_attempt(self):
        sql = valid_discovery_hit_groups_sql(
            collection_id_sql="collection.id",
            content_id_sql="content.id",
            canonical_url_sql="content.canonical_url",
        )
        for needle in (
            "attempt.id=hit.attempt_id", "attempt.run_id=run.id",
            "attempt.query_id=hit.query_id", "attempt.status='HEALTHY'",
            "discovery_query.id=hit.query_id", "discovery_query.id=attempt.query_id",
            "discovery_query.manifest_id=manifest.id",
            "discovery_query.source_families ? hit.source_family",
            "discovery_query.adapter_ids ? attempt.adapter_id",
            "manifest.source_families ? hit.source_family",
            "manifest.manifest_sha256=run.manifest_sha256",
            "manifest.status='ACTIVE'",
            "run.status IN ('COMPLETED','PARTIAL')",
            "hit.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, sql)
                self.assertIn(needle, _MEMBER_READ_SQL)

    def test_interpolation_rejects_untrusted_sql(self):
        for invalid in (
            "content.id) OR TRUE --", "'research:other'", "content.title",
            "content.id;DROP TABLE content_item", "public.content_item.id",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                valid_discovery_hit_groups_sql(
                    collection_id_sql=invalid,
                    content_id_sql="content.id",
                    canonical_url_sql="content.canonical_url",
                )

    def test_capture_operator_sql_and_report_share_same_verified_lineage(self):
        class QueryProbe(CapturePipelineStore):
            def __init__(self):
                self.last_sql = None
            def run(self, sql, **variables):
                self.last_sql = sql
                return ""

        probe = QueryProbe()
        self.assertIsNone(probe.read_research_capture_context("research:approved", "content:reviewed"))
        for needle in (
            "attempt.status='HEALTHY'",
            "discovery_query.manifest_id=manifest.id",
            "discovery_query.source_families ? hit.source_family",
            "manifest.source_families ? hit.source_family",
        ):
            self.assertIn(needle, probe.last_sql)
        self.assertIn("accepted_discovery_groups", probe.last_sql)
        self.assertIn("accepted_discovery_hits", probe.last_sql)

    def test_counts_fail_closed_on_type_conflicts_and_missing_source_family(self):
        item = make_batch().items[0]
        row = research_context(item)
        require_persisted_discovery(row, collection_id="research:approved", item=item)
        for change in (
            {"accepted_discovery_groups": [{"source_family": "UNRELATED", "hit_count": 1}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": 2}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": 0}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": True}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": "1"}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": 1, "extra": True}]},
            {"accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": 1},
                                             {"source_family": item.source_family, "hit_count": 1}]},
            {"accepted_discovery_groups": None},
            {"accepted_discovery_hits": True},
        ):
            with self.subTest(change=change), self.assertRaises(PrivateCaptureAuthorizationBlocked):
                require_persisted_discovery(
                    {**row, **change},
                    collection_id="research:approved",
                    item=item,
                )

    def test_valid_multiple_families_must_include_exact_authorized_source(self):
        item = make_batch().items[0]
        row = research_context(item, accepted_discovery_hits=3, accepted_discovery_groups=[
            {"source_family": item.source_family, "hit_count": 1},
            {"source_family": "ANOTHER", "hit_count": 2},
        ])
        self.assertEqual(accepted_discovery_family_counts(row)[item.source_family], 1)
        require_persisted_discovery(row, collection_id="research:approved", item=item)

    def test_pg_temp_canary_only_rollback_and_strict_receipt_coverage(self):
        sql = ephemeral_provenance_sql()
        self.assertIn("CREATE TEMP TABLE research_discovery_hit", sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertIn("SET LOCAL search_path TO pg_temp, public", sql)
        self.assertNotIn("INSERT INTO content_item", sql)
        valid = (
            "valid_only|1|REPORTING\nrevoked_attempt|0|\npaused_manifest|0|\n"
            "stale_run_digest|0|\nblocked_run|0|\n"
        )
        self.assertEqual(check_receipts(valid)["status"], "PASS_ROLLBACK_ONLY")
        for tampered in (valid.replace("valid_only|1|", "valid_only|2|"),
                         valid.replace("paused_manifest|0|", "paused_manifest|1|REPORTING"),
                         valid.replace("blocked_run|0|\n", "")):
            with self.subTest(tampered=tampered), self.assertRaises(RuntimeError):
                check_receipts(tampered)


if __name__ == "__main__":
    unittest.main()
