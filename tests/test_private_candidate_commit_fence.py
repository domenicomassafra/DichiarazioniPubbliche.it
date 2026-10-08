from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.candidate_extraction import (
    CandidateExtractionError, CandidateExtractionStore, _COMMIT_BATCH_SQL,
    extract_passage_candidates,
)
from dichiarazioni_pubbliche.private_candidate_commit_fence import (
    PRIVATE_CANDIDATE_COMMIT_AUTHORITY_CTE, PrivateCandidateCommitFence,
)
from test_candidate_extraction import FakeProvider, FakeStore, valid_payload, written_context
from tools.check_private_candidate_commit_fence import (
    ephemeral_fence_sql, evaluate_receipts, fixture_scope,
)


def fake_scope():
    context = written_context()
    return replace(
        fixture_scope(),
        content_id=context.content_id,
        capture_id=context.capture_id,
        passage_id=context.passage_id,
        passage_sha256=context.text_sha256,
    )


class CommitFenceTests(unittest.TestCase):
    def test_sql_gate_is_inside_same_statement_as_every_candidate_and_receipt_insert(self):
        self.assertIn("WITH commit_authority AS MATERIALIZED", _COMMIT_BATCH_SQL)
        self.assertNotIn("SELECT 1 AS allowed WHERE false", _COMMIT_BATCH_SQL)
        self.assertIn("rights.permitted_uses @> ARRAY[", _COMMIT_BATCH_SQL)
        self.assertIn("relevance.content_binding_sha256=:'fence_relevance_binding_sha256'", _COMMIT_BATCH_SQL)
        self.assertIn("EXISTS (SELECT 1 FROM commit_authority)", _COMMIT_BATCH_SQL)
        self.assertIn("fence_required", _COMMIT_BATCH_SQL)
        self.assertIn("content_id=:'fence_content_id'", _COMMIT_BATCH_SQL)
        self.assertIn("passage_id=:'fence_passage_id'", _COMMIT_BATCH_SQL)
        self.assertIn("capture_id=:'fence_capture_id'", _COMMIT_BATCH_SQL)
        for thing in (
            "passage_insert AS (", "statement_insert AS (", "mention_insert AS (",
            "resolution_insert AS (", "claim_insert AS (",
            "receipt_insert AS (", "updated AS (",
        ):
            self.assertIn(thing, _COMMIT_BATCH_SQL)
        self.assertIn("FROM locked", _COMMIT_BATCH_SQL)
        self.assertIn("AND EXISTS (SELECT 1 FROM receipt_insert)", _COMMIT_BATCH_SQL)
        self.assertIn("CREATE TEMP TABLE private_source_rights_record", ephemeral_fence_sql())
        self.assertIn("ROLLBACK;", ephemeral_fence_sql())

    def test_required_capture_rights_relevance_discovery_and_no_supersession(self):
        cte = PRIVATE_CANDIDATE_COMMIT_AUTHORITY_CTE
        for phrase in (
            "collection.status='ACTIVE'",
            "member.metadata->'capture_authorized'='true'::jsonb",
            "source_passage.text_sha256=:'fence_passage_sha256'",
            "capture.body_ref IS NOT NULL",
            "capture.hold_status='NONE'",
            "rights.permitted_uses @> ARRAY[",
            "'OMNIROUTE_MODEL_EXTRACTION_PRIVATE'",
            "superseding.supersedes_id=rights.id",
            "relevance.content_binding_sha256=:'fence_relevance_binding_sha256'",
            "successor.supersedes_authority_id=relevance.authority_id",
            "provenance.source_family=:'fence_source_family'",
            "attempt.status='HEALTHY'",
            "other_member.metadata->'capture_authorized' IS DISTINCT FROM 'true'::jsonb",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, cte)

    def test_parameters_are_immutable_derived_scope_not_sql_fragments(self):
        good = fixture_scope()
        parameters = good.sql_parameters()
        self.assertEqual(parameters["fence_collection_id"], good.collection_id)
        self.assertEqual(len(parameters["fence_relevance_binding_sha256"]), 64)
        for changed in (
            replace(good, content_id="other';DROP TABLE passage;--"),
            replace(good, passage_sha256="stale"),
            replace(good, canonical_url="http://unsafe.test/"),
            replace(good, rights_record_id="bad\nline"),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                changed.sql_parameters()

    def test_authority_changed_inside_commit_finishes_blocked_with_reserved_cost(self):
        class CommitRevoked(FakeStore):
            def commit_batch(self, **kwargs):
                self.last_scope = kwargs["commit_fence"]
                raise CandidateExtractionError("CANDIDATE_COMMIT_AUTHORITY_CHANGED")

        store = CommitRevoked()
        provider = FakeProvider(valid_payload(), upper=Decimal("0.003"), cost=Decimal("0.002"))
        receipt = extract_passage_candidates(
            passage_id="passage:parent",
            store=store,
            provider=provider,
            max_cost_usd="1",
            authorization_guard=lambda: None,
            commit_fence=fake_scope(),
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.reason_code, "CANDIDATE_COMMIT_AUTHORITY_CHANGED")
        self.assertEqual(receipt.call_count, 1)
        self.assertEqual(receipt.cost_usd, Decimal("0.003"))
        self.assertFalse(store.committed_batches)
        self.assertEqual(store.last_scope, fake_scope())

    def test_invalid_scope_fails_before_provider_or_run(self):
        store = FakeStore()
        provider = FakeProvider(valid_payload())
        with self.assertRaisesRegex(CandidateExtractionError, "FENCE_INVALID"):
            extract_passage_candidates(
                passage_id="passage:parent", store=store, provider=provider,
                max_cost_usd="1",
                commit_fence=replace(fake_scope(), passage_sha256="BAD"),
            )
        with self.assertRaisesRegex(CandidateExtractionError, "FENCE_CONTEXT_MISMATCH"):
            extract_passage_candidates(
                passage_id="passage:parent", store=store, provider=provider,
                max_cost_usd="1",
                commit_fence=replace(fake_scope(), content_id="content:wrong"),
            )
        self.assertFalse(store.start_calls)
        self.assertEqual(provider.calls, 0)

    def test_postgresql_canary_receipts_require_all_negative_cases(self):
        keys = (
            "valid", "rights_revoked", "rights_superseded", "rights_expired",
            "model_use_removed", "collection_paused", "capture_held",
            "body_purged", "passage_hash_changed", "privacy_superseded",
            "privacy_binding_stale", "discovery_attempt_failed",
            "discovery_source_family_mismatch", "membership_authorization_revoked",
            "content_rights_revoked", "conflicting_collection_paused",
        )
        source = "\n".join(f"{name}|{1 if name == 'valid' else 0}" for name in keys)
        report = evaluate_receipts(source)
        self.assertEqual(report["revocation_or_mismatch_blocked"], len(keys) - 1)
        for bad in (source.replace("valid|1", "valid|0"),
                    source.replace("privacy_superseded|0", "privacy_superseded|1"),
                    source.rsplit("\n", 1)[0]):
            with self.assertRaisesRegex(RuntimeError, "BYPASS"):
                evaluate_receipts(bad)


if __name__ == "__main__":
    unittest.main()
