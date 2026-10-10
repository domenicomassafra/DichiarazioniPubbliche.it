import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.private_pipeline_reconciliation import (
    MAX_CANDIDATES_PER_MEMBER, _CHAIN_SQL, _analyze, reconcile_rows,
    PrivatePipelineReconciliationStore,
)
from tools.inspect_private_pipeline import main

HASH = "a" * 64


def row(**overrides):
    value = {
        "content_id": "synthetic:content-1",
        "source_id": "synthetic:source-1",
        "source_exists": True,
        "collection_status": "ACTIVE",
        "member_status": "INCLUDED",
        "capture_authorized": True,
        "content_rights": "CLEARED",
        "rights_current": True,
        "latest_capture_id": "synthetic:capture-1",
        "capture_count": 1,
        "passage_count": 1,
        "discovery_count": 1,
        "candidate_count": 1,
        "candidate_id": "synthetic:candidate-1",
        "candidate_status": "CANDIDATE",
        "candidate_promoted": False,
        "statement_id": "synthetic:statement-1",
        "statement_status": "CANDIDATE",
        "speaker_present": False,
        "statement_hash": HASH,
        "passage_link_count": 1,
        "parent_passage_id": "synthetic:passage-1",
        "passage_id": "synthetic:passage-1",
        "passage_hash": HASH,
        "selector_type": "TEXT_POSITION",
        "capture_id": "synthetic:capture-1",
        "capture_status": "CAPTURED",
        "capture_rights": "CLEARED",
        "capture_hold": "NONE",
        "capture_retention": "DURABLE_PRIVATE",
        "body_available": True,
        "match_run_id": None,
        "match_status": None,
        "match_result_id": None,
        "match_class": None,
        "match_disposition": None,
        "match_result_status": None,
        "target_content_id": None,
        "target_source_id": None,
    }
    value.update(overrides)
    return value


class PipelineReconciliationTests(unittest.TestCase):
    def test_private_review_readiness_counts_only_proven_healthy_discovery_lineage(self):
        # A raw Hit can have an FAILED attempt, stale manifest or different
        # Source even when its Content ID and URL match. Such a hit must not
        # unlock the private review queue or bind an unrelated rights family.
        for needle in (
            "attempt.status='HEALTHY'",
            "attempt.run_id=run.id",
            "attempt.query_id=hit.query_id",
            "discovery_query.manifest_id=manifest.id",
            "discovery_query.adapter_ids ? attempt.adapter_id",
            "manifest.collection_id=member.collection_id",
            "manifest.status='ACTIVE'",
            "manifest.manifest_sha256=run.manifest_sha256",
            "hit.source_id=content.source_id",
            "rights.source_family = ANY(provenance.source_families)",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, _CHAIN_SQL)
        self.assertNotIn("SELECT count(*) FROM research_discovery_hit hit", _CHAIN_SQL)

        fixture = (ROOT / "tests/fixtures/private_pipeline_reconciliation.sql").read_text()
        for table in ("manifest", "run", "query", "attempt"):
            self.assertIn(f"CREATE TABLE research_discovery_{table}", fixture)
        self.assertIn("'synthetic-adapter','fixture-v1','HEALTHY'", fixture)

    def test_read_only_query_uses_strict_foreign_key_chain_and_current_private_rights(self):
        self.assertIn("BEGIN READ ONLY;", _CHAIN_SQL)
        self.assertIn("COMMIT;", _CHAIN_SQL)
        self.assertIn("statement_candidate_passage", _CHAIN_SQL)
        self.assertIn("successor.supersedes_id=rights.id", _CHAIN_SQL)
        self.assertIn("candidate.metadata->>'parent_passage_id'", _CHAIN_SQL)
        self.assertIn("hit.source_id=content.source_id", _CHAIN_SQL)
        self.assertIn("candidate_match_result", _CHAIN_SQL)
        self.assertIn("ORDER BY member.content_id, candidate.id", _CHAIN_SQL)
        self.assertNotIn("INSERT INTO", _CHAIN_SQL)
        self.assertNotIn("UPDATE ", _CHAIN_SQL)
        self.assertNotIn("DELETE FROM", _CHAIN_SQL)

    def test_synthetic_cleared_rights_and_exact_written_chain_is_only_private_review_ready(self):
        output = _analyze(row())
        self.assertEqual(output["state"], "REVIEW_READY_PRIVATE_NOT_APPROVED")
        self.assertEqual(output["blockers"], [])
        self.assertTrue(output["private_review_queue_eligible"])
        self.assertIn("SPEAKER_ATTRIBUTION_NOT_REVIEWED", output["review_warnings"])
        self.assertIn("MATCH_NOT_RUN", output["review_warnings"])
        self.assertIn("CAPTURE_BYTES_AND_SELECTOR_REVALIDATION_REQUIRED", output["review_warnings"])
        self.assertEqual(output["next_private_step"], "PRIVATE_STUDIO_CANDIDATE_REVIEW")
        for field in ("publication_authority", "promotion_authority", "review_authority"):
            self.assertIs(output[field], False)
        self.assertNotIn("statement_hash", output)
        self.assertNotIn("passage_hash", output)

    def test_missing_or_revoked_rights_and_inactive_membership_force_hold(self):
        for altered, expected in (
            ({"rights_current": False}, "RIGHTS_HOLD_CURRENT_GRANT_MISSING"),
            ({"content_rights": "UNKNOWN"}, "RIGHTS_HOLD_CURRENT_GRANT_MISSING"),
            ({"collection_status": "PAUSED"}, "COLLECTION_OR_MEMBERSHIP_INACTIVE"),
            ({"member_status": "REMOVED"}, "COLLECTION_OR_MEMBERSHIP_INACTIVE"),
            ({"capture_authorized": False}, "CAPTURE_MEMBERSHIP_NOT_AUTHORIZED"),
            ({"discovery_count": 0}, "DISCOVERY_PROVENANCE_NOT_PERSISTED"),
            ({"source_exists": False}, "SOURCE_IDENTITY_NOT_PERSISTED"),
            ({"capture_rights": "RIGHTS_HOLD"}, "CAPTURE_PRIVATE_INTEGRITY_OR_RIGHTS_HOLD"),
            ({"capture_hold": "RIGHTS_HOLD"}, "CAPTURE_PRIVATE_INTEGRITY_OR_RIGHTS_HOLD"),
            ({"body_available": False}, "CAPTURE_PRIVATE_INTEGRITY_OR_RIGHTS_HOLD"),
        ):
            with self.subTest(altered=altered):
                actual = _analyze(row(**altered))
                self.assertFalse(actual["private_review_queue_eligible"])
                self.assertIn(expected, actual["blockers"])

    def test_missing_source_capture_passage_and_candidate_hold_without_guessing(self):
        empty = row(
            source_id=None, source_exists=False, latest_capture_id=None,
            capture_count=0, passage_count=0, candidate_count=0,
            candidate_id=None, statement_id=None, statement_hash=None,
            passage_id=None, passage_hash=None, passage_link_count=0,
            parent_passage_id=None, capture_id=None,
        )
        result = _analyze(empty)
        self.assertIn("NO_CAPTURE", result["blockers"])
        self.assertIn("NO_PASSAGE", result["blockers"])
        self.assertIn("NO_CLAIM_CANDIDATE", result["blockers"])
        self.assertEqual(result["next_private_step"], "REVIEW_DISCOVERY_SOURCE_BINDING")
        self.assertNotIn("STATEMENT_BINDING_MISSING", result["blockers"])

    def test_stale_capture_hash_or_non_atomic_link_never_review_ready(self):
        for altered, expected in (
            ({"statement_status": "REJECTED"}, "STATEMENT_NOT_PENDING_REVIEW"),
            ({"statement_status": "HELD"}, "STATEMENT_NOT_PENDING_REVIEW"),
            ({"statement_status": "SUPERSEDED"}, "STATEMENT_NOT_PENDING_REVIEW"),
            ({"latest_capture_id": "synthetic:capture-new"}, "CAPTURE_VERSION_STALE"),
            ({"passage_link_count": 2}, "PASSAGE_BINDING_NOT_ATOMIC"),
            ({"parent_passage_id": "synthetic:passage-other"}, "CANDIDATE_PARENT_PASSAGE_MISMATCH"),
            ({"passage_hash": "b" * 64}, "STATEMENT_PASSAGE_EXACT_HASH_UNVERIFIED"),
            ({"selector_type": "MEDIA_SEGMENT_REF"}, "WRITTEN_SELECTOR_UNVERIFIED"),
            ({"candidate_status": "PROMOTED", "candidate_promoted": True}, "CANDIDATE_NOT_PENDING_REVIEW"),
        ):
            with self.subTest(altered=altered):
                result = _analyze(row(**altered))
                self.assertIn(expected, result["blockers"])
                self.assertFalse(result["private_review_queue_eligible"])

    def test_approved_statement_with_still_pending_claim_is_private_reviewable(self):
        result = _analyze(row(statement_status="APPROVED"))
        self.assertTrue(result["private_review_queue_eligible"])
        self.assertFalse(result["publication_authority"])

    def test_cross_source_only_when_persisted_match_targets_distinct_source(self):
        matched = row(
            match_run_id="synthetic:run-1", match_status="COMPLETED",
            match_result_id="synthetic:result-1", match_class="SAME_PROPOSITION",
            match_result_status="CANDIDATE", match_disposition="PROPOSE_CLUSTER",
            target_content_id="synthetic:content-2", target_source_id="synthetic:source-2",
        )
        output = _analyze(matched)
        self.assertTrue(output["cross_source_persisted_match_unreviewed"])
        self.assertIn("MATCH_CURRENTNESS_AND_REVIEW_REQUIRED", output["review_warnings"])
        self.assertIs(output["publication_authority"], False)
        for modified in (
            {"target_source_id": "synthetic:source-1"},
            {"target_content_id": "synthetic:content-1"},
            {"match_result_id": None},
            {"match_class": "DIFFERENT"},
            {"match_result_status": "REJECTED"},
        ):
            self.assertFalse(_analyze(matched | modified)["cross_source_persisted_match_unreviewed"])
        self.assertIn("UNCERTAIN_MATCH_REQUIRES_HUMAN_REVIEW", _analyze(
            matched | {"match_class": "UNCERTAIN"}
        )["review_warnings"])

    def test_page_order_and_bounded_candidate_rows_are_strict(self):
        source = row()
        output = reconcile_rows([source], limit=1)
        self.assertEqual(output["contents"], 1)
        self.assertTrue(output["private_only"])
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            reconcile_rows([source, source], limit=2)
        with self.assertRaisesRegex(ValueError, "BOUNDS"):
            reconcile_rows([row(content_id=f"synthetic:content-{n:02d}") for n in range(26)], limit=25)
        with self.assertRaisesRegex(ValueError, "ROW_BOUNDS"):
            reconcile_rows([row(candidate_id=f"synthetic:candidate-{n}") for n in range(
                MAX_CANDIDATES_PER_MEMBER + 1
            )], limit=1)

    def test_fake_store_readback_is_scoped_no_mutation_or_body_returned(self):
        class Fake(PrivatePipelineReconciliationStore):
            def run(self, sql, **variables):
                self.query = sql
                self.variables = variables
                return json.dumps(row())
        store = Fake()
        receipt = store.read_collection(collection_id="synthetic:collection", limit=1)
        self.assertEqual(receipt["collection_id"], "synthetic:collection")
        self.assertEqual(receipt["next_after_content_id"], "synthetic:content-1")
        self.assertEqual(store.variables["collection_id"], "synthetic:collection")
        self.assertNotIn("passage_hash", str(receipt))
        self.assertNotIn("https://", json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "ID_INVALID"):
            store.read_collection(collection_id="a'; DROP TABLE content_item; --")

    def test_cli_defaults_no_writes_and_has_safe_failure(self):
        with patch("tools.inspect_private_pipeline.PrivatePipelineReconciliationStore") as store:
            store.return_value.read_collection.side_effect = RuntimeError("PRIVATE_CHAIN_READ_ONLY_STORE_UNAVAILABLE")
            self.assertEqual(main(["--collection-id", "synthetic:collection"]), 2)

    def test_cli_summary_aggregates_without_emitting_private_member_ids(self):
        from contextlib import redirect_stdout
        from io import StringIO
        payload = reconcile_rows([row()], limit=1)
        with patch("tools.inspect_private_pipeline.PrivatePipelineReconciliationStore") as store:
            store.return_value.read_collection.return_value = payload
            stream = StringIO()
            with redirect_stdout(stream):
                self.assertEqual(main(["--collection-id", "synthetic:collection", "--summary"]), 0)
        self.assertNotIn("synthetic:candidate-1", stream.getvalue())
        response = json.loads(stream.getvalue())
        self.assertEqual(response["review_ready_private"], 1)
        self.assertEqual(response["next_private_steps"], {"PRIVATE_STUDIO_CANDIDATE_REVIEW": 1})
        self.assertFalse(response["publication_authority"])


if __name__ == "__main__":
    unittest.main()
