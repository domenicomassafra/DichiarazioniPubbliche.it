import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import (  # noqa: E402
    QueueRuntimeStore,
    deterministic_canonical_segment_id,
    deterministic_followup_job_id,
    deterministic_receipt_id,
    deterministic_segment_id,
    deterministic_variant_id,
)


class QueueRuntimeTests(unittest.TestCase):
    def test_identifiers_are_stable_and_namespaced(self):
        self.assertEqual(
            deterministic_followup_job_id("CLAIM_EXTRACT", "content:abc"),
            deterministic_followup_job_id("CLAIM_EXTRACT", "content:abc"),
        )
        self.assertTrue(
            deterministic_receipt_id("job:a", "youtube", "CAPTION_PROBE").startswith(
                "receipt:"
            )
        )
        self.assertTrue(
            deterministic_variant_id(
                "content:a", "youtube", "YOUTUBE_AUTO_CAPTION", "f" * 64
            ).startswith("transcript:")
        )
        self.assertTrue(deterministic_segment_id("transcript:a", 2).startswith("segment:"))
        self.assertTrue(
            deterministic_canonical_segment_id("content:a", 2).startswith(
                "canonical-segment:"
            )
        )

    def test_variant_identity_changes_with_capture_hash(self):
        left = deterministic_variant_id(
            "content:a", "youtube", "YOUTUBE_AUTO_CAPTION", "a" * 64
        )
        right = deterministic_variant_id(
            "content:a", "youtube", "YOUTUBE_AUTO_CAPTION", "b" * 64
        )
        self.assertNotEqual(left, right)

    def test_runtime_store_exposes_claim_persistence_contract(self):
        self.assertTrue(hasattr(QueueRuntimeStore, "insert_atomic_claims"))
        self.assertTrue(hasattr(QueueRuntimeStore, "claim_count"))
        self.assertTrue(hasattr(QueueRuntimeStore, "upsert_evidence"))
        self.assertTrue(hasattr(QueueRuntimeStore, "link_claim_evidence"))
        self.assertTrue(hasattr(QueueRuntimeStore, "register_organization"))
        self.assertTrue(hasattr(QueueRuntimeStore, "register_person_role_interval"))
        self.assertTrue(hasattr(QueueRuntimeStore, "role_intervals_at"))

    def test_role_interval_review_is_atomic_and_bounded(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "true"

        store = CaptureStore()
        self.assertTrue(
            store.approve_person_role_interval_with_review(
                interval_id="role:a",
                person_id="person:a",
                organization_id="org:a",
                role="Member",
                start_date="2026-01-01",
                end_date=None,
                is_public_role=True,
                source_ref={"url": "https://example.test/role"},
                event_id="review:a",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("BEGIN;", store.sql)
        self.assertIn("'PERSON_ROLE_INTERVAL'", store.sql)
        self.assertIn("status = 'SUPERSEDED'", store.sql)
        self.assertIn("COMMIT;", store.sql)
        with self.assertRaisesRegex(ValueError, "SOURCE_REF"):
            store.approve_person_role_interval_with_review(
                interval_id="role:b",
                person_id="person:a",
                organization_id="org:a",
                role="Member",
                start_date="2026-01-01",
                end_date=None,
                is_public_role=True,
                source_ref={},
                event_id="review:b",
                actor_ref="reviewer",
                reason=None,
            )

    def test_evidence_link_validation_is_fail_closed(self):
        store = QueueRuntimeStore()
        with self.assertRaises(ValueError):
            store.link_claim_evidence(
                claim_id="claim:a",
                evidence_id="evidence:a",
                retrieval_method="test",
                retrieval_version="v1",
                relation_candidate="VERDICT",
            )
        with self.assertRaises(ValueError):
            store.link_claim_evidence(
                claim_id="claim:a",
                evidence_id="evidence:a",
                retrieval_method="test",
                retrieval_version="v1",
                score=2.0,
            )
        with self.assertRaisesRegex(ValueError, "review ledger"):
            store.link_claim_evidence(
                claim_id="claim:a",
                evidence_id="evidence:a",
                retrieval_method="test",
                retrieval_version="v1",
                status="APPROVED",
            )

    def test_observation_approval_cannot_bypass_review_ledger(self):
        store = QueueRuntimeStore()
        with self.assertRaisesRegex(ValueError, "review ledger"):
            store.insert_evidence_observation(
                observation_id="observation:a",
                evidence_id="evidence:a",
                observation_type="METRIC",
                metric="x",
                value_numeric=1.0,
                value_text=None,
                unit=None,
                reference_period=None,
                dimensions={},
                extraction_method="MANUAL",
                extraction_version="v1",
                source_pointer={},
                status="APPROVED",
            )
        with self.assertRaisesRegex(ValueError, "review ledger"):
            store.update_evidence_observation_status("observation:a", "APPROVED")
        with self.assertRaisesRegex(ValueError, "review ledger"):
            store.update_claim_evidence_status(
                claim_id="claim:a",
                evidence_id="evidence:a",
                retrieval_version="v1",
                status="APPROVED",
            )

    def test_reply_publication_requires_published_finding_review_gate(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "false"

        store = CaptureStore()
        self.assertFalse(
            store.publish_right_of_reply_with_review(
                reply_id="reply:a",
                event_id="review:a",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("finding.publication_status IN", store.sql)
        self.assertIn("finding_review.entity_type = 'FINDING'", store.sql)
        self.assertIn("finding_review.action = 'APPROVED'", store.sql)
        self.assertIn("trigger.status = 'PROCESSED'", store.sql)

    def test_correction_publication_requires_both_finding_review_gates(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "false"

        store = CaptureStore()
        self.assertFalse(
            store.publish_correction_with_review(
                correction_id="correction:a",
                event_id="review:a",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("current_review.entity_type = 'FINDING'", store.sql)
        self.assertIn("previous_review.entity_type = 'FINDING'", store.sql)
        self.assertEqual(store.sql.count("action = 'APPROVED'"), 2)
        self.assertIn("trigger.status = 'PROCESSED'", store.sql)
        self.assertIn("child.supersedes_id = current.id", store.sql)

    def test_finding_publication_requires_exact_verification_provenance(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "false"

        store = CaptureStore()
        self.assertFalse(
            store.publish_finding_with_review(
                finding_id="finding:a",
                event_id="review:a",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("verification.claim_id = claim.id", store.sql)
        self.assertIn("finding.assessment = verification.assessment", store.sql)
        self.assertIn("verification.evidence_ids", store.sql)
        self.assertIn("verification.observation_ids", store.sql)
        self.assertIn("'CLAIM_EVIDENCE_CANDIDATE'", store.sql)
        self.assertIn("'EVIDENCE_OBSERVATION'", store.sql)
        self.assertIn("'SPEAKER_IDENTITY_CANDIDATE'", store.sql)
        self.assertIn("'CLAIM_TEXT_PROVENANCE'", store.sql)
        self.assertIn("FROM claim_text_provenance provenance", store.sql)

    def test_claim_replay_cannot_append_segment_provenance(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run_literal(self, sql):
                self.sql = sql
                return "0"

        store = CaptureStore()
        store.insert_atomic_claims(
            [
                {
                    "id": "claim:a",
                    "content_id": "content:a",
                    "normalized_claim": "Claim",
                    "claim_type": "OTHER",
                    "temporal_scope": {},
                    "check_worthy": True,
                    "extraction_model": "test",
                    "extraction_version": "v1",
                    "metadata": {},
                    "segment_ids": ["segment:a"],
                }
            ]
        )
        self.assertIn("JOIN inserted ON inserted.id = input.id", store.sql)
        self.assertIn("replayed AS (", store.sql)
        self.assertIn("FROM rejected", store.sql)
        self.assertNotIn("RETURNING id\n            ),\n            blocked", store.sql)
        self.assertIn("WHEN (SELECT has_rejected FROM blocked) = 1 THEN '0'", store.sql)
        self.assertIn("(SELECT count(*) FROM inserted)", store.sql)
        self.assertIn("(SELECT count(*) FROM replayed)", store.sql)
        self.assertNotIn("content.published_at::date::text", self.store_sql_claim_context())

    def store_sql_claim_context(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return ""

        store = CaptureStore()
        with self.assertRaises(KeyError):
            store.claim_context("missing")
        return store.sql

    def test_finding_replay_cannot_append_unverified_evidence(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "false"

        store = CaptureStore()
        self.assertFalse(
            store.insert_finding_draft(
                {
                    "finding_id": "finding:a",
                    "claim_id": "claim:a",
                    "assessment": "SUPPORTED",
                    "rationale": "r",
                    "publication_status": "POLICY_HOLD",
                    "policy_version": "v1",
                    "model_bundle": {},
                    "verification_run_id": "verification:a",
                    "supersedes_id": None,
                    "evidence_ids": ["evidence:a"],
                }
            )
        )
        self.assertIn(
            "verification.evidence_ids @> :'evidence_ids'::jsonb",
            store.sql,
        )
        self.assertIn(
            ":'evidence_ids'::jsonb @> verification.evidence_ids",
            store.sql,
        )
        self.assertIn("FROM inserted", store.sql)
        self.assertNotIn("SELECT id FROM finding", store.sql)


if __name__ == "__main__":
    unittest.main()
