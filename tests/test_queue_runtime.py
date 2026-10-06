import json
import sys
import unittest
from decimal import Decimal
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
        legacy_receipt_id = deterministic_receipt_id(
            "job:a", "youtube", "CAPTION_PROBE"
        )
        self.assertEqual(
            legacy_receipt_id,
            "receipt:ae929790d96e0319606f51aea1cc0f7e4d5b3ef0674b41fbd4ea18cfe7e4767f",
        )
        first_attempt = deterministic_receipt_id(
            "job:a", "youtube", "CAPTION_PROBE", attempt=1
        )
        second_attempt = deterministic_receipt_id(
            "job:a", "youtube", "CAPTION_PROBE", attempt=2
        )
        self.assertEqual(first_attempt, f"{legacy_receipt_id}:attempt:1")
        self.assertEqual(second_attempt, f"{legacy_receipt_id}:attempt:2")
        self.assertNotEqual(first_attempt, second_attempt)
        with self.assertRaisesRegex(ValueError, "PROVIDER_RECEIPT_ATTEMPT_INVALID"):
            deterministic_receipt_id(
                "job:a", "youtube", "CAPTION_PROBE", attempt=0
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
        self.assertTrue(hasattr(QueueRuntimeStore, "operation_ledger_receipts"))
        self.assertTrue(hasattr(QueueRuntimeStore, "operation_ledger_summary"))

    def test_record_receipt_writes_v2_operation_ledger_fields(self):
        class CaptureStore(QueueRuntimeStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return f"{variables['receipt_id_base']}:attempt:1"

        store = CaptureStore()
        receipt_id = store.record_receipt(
            job_id="job:a",
            content_id="content:a",
            provider_id="provider:a",
            model_id="model:a",
            operation="CLAIM_EXTRACT",
            request_id="request:a",
            input_bytes=100,
            input_seconds=None,
            estimated_cost_usd=0.20,
            measured_cost_usd=0.12,
            total_tokens=321,
            status="SUCCESS",
            receipt={"ok": True},
        )
        self.assertTrue(receipt_id.endswith(":attempt:1"))
        self.assertIn("WITH receipt_candidate AS", store.sql)
        self.assertIn("legacy.id=:'receipt_id_base'", store.sql)
        self.assertIn("ELSE :'receipt_id_base' || ':attempt:'", store.sql)
        self.assertIn("operation_key, attempt", store.sql)
        self.assertIn("measured_cost_usd, billing_basis", store.sql)
        self.assertIn("ledger_scope", store.sql)
        self.assertIn("GREATEST(job.attempt,1)", store.sql)
        self.assertEqual(
            store.variables["billing_basis"],
            "MEASURED_PROVIDER_COST",
        )
        self.assertEqual(store.variables["measured_cost_usd"], 0.12)
        self.assertEqual(store.variables["total_tokens"], 321)
        self.assertIn('"job_id":"job:a"', store.variables["ledger_scope"])

    def test_retry_receipts_are_attempt_scoped_with_stable_logical_operation(self):
        class RetryStore(QueueRuntimeStore):
            def __init__(self):
                self.attempt = 1
                self.persisted = {}

            def run(self, sql, **variables):
                if "INSERT INTO provider_receipt" in sql:
                    receipt_id = (
                        f"{variables['receipt_id_base']}:attempt:{self.attempt}"
                    )
                    if receipt_id not in self.persisted:
                        self.persisted[receipt_id] = {
                            "receipt_id": receipt_id,
                            "operation_key": variables["operation_key"],
                            "attempt": self.attempt,
                            "provider_id": variables["provider_id"],
                            "model_id": variables["model_id"] or None,
                            "operation": variables["operation"],
                            "status": variables["status"],
                            "billing_basis": variables["billing_basis"],
                            "estimated_cost_usd": variables["estimated_cost_usd"],
                            "measured_cost_usd": variables["measured_cost_usd"],
                            "total_tokens": variables["total_tokens"] or None,
                            "input_seconds": variables["input_seconds"] or None,
                            "request_count": variables["request_count"],
                            "claim_id": None,
                            "content_id": variables["content_id"],
                            "source_id": "source:a",
                            "collection_id": None,
                        }
                    return receipt_id
                if "FROM provider_receipt r" in sql:
                    return json.dumps(list(self.persisted.values()))
                return ""

        for request_key in ("", "reused-request-key"):
            with self.subTest(request_key=request_key or "<empty>"):
                store = RetryStore()
                first_id = store.record_receipt(
                    job_id="job:retry",
                    content_id="content:a",
                    provider_id="provider:a",
                    model_id="model:a",
                    operation="CLAIM_EXTRACT",
                    request_id=None,
                    input_bytes=100,
                    input_seconds=None,
                    estimated_cost_usd=0.10,
                    measured_cost_usd=0.10,
                    status="FAILED",
                    receipt={"attempt": 1},
                    request_key=request_key,
                )
                store.attempt = 2
                second_id = store.record_receipt(
                    job_id="job:retry",
                    content_id="content:a",
                    provider_id="provider:a",
                    model_id="model:a",
                    operation="CLAIM_EXTRACT",
                    request_id=None,
                    input_bytes=100,
                    input_seconds=None,
                    estimated_cost_usd=0.20,
                    measured_cost_usd=0.20,
                    status="SUCCESS",
                    receipt={"attempt": 2},
                    request_key=request_key,
                )

                self.assertNotEqual(first_id, second_id)
                self.assertTrue(first_id.endswith(":attempt:1"))
                self.assertTrue(second_id.endswith(":attempt:2"))
                receipts = store.operation_ledger_receipts(content_id="content:a")
                self.assertEqual([row.attempt for row in receipts], [1, 2])
                self.assertEqual(len({row.operation_key for row in receipts}), 1)
                summary = store.operation_ledger_summary(content_id="content:a")
                self.assertEqual(summary.operation_count, 1)
                self.assertEqual(summary.attempt_count, 2)
                self.assertEqual(summary.measured_cost_usd, Decimal("0.3"))
                self.assertEqual(summary.request_count, 2)

    def test_unknown_receipt_requires_nonzero_cost_bound(self):
        class CaptureStore(QueueRuntimeStore):
            def run(self, sql, **variables):
                return ""

        store = CaptureStore()
        with self.assertRaisesRegex(
            ValueError,
            "PROVIDER_RECEIPT_UNKNOWN_COST_BOUND_REQUIRED",
        ):
            store.record_receipt(
                job_id="job:a",
                content_id="content:a",
                provider_id="provider:a",
                model_id=None,
                operation="PAID_CALL",
                request_id=None,
                input_bytes=None,
                input_seconds=None,
                estimated_cost_usd=0.0,
                billing_basis="UNKNOWN",
                status="FAILED",
                receipt={},
            )

    def test_operation_ledger_query_preserves_unknown_legacy_cost(self):
        class CaptureStore(QueueRuntimeStore):
            def run(self, sql, **variables):
                return (
                    '[{"receipt_id":"receipt:old","operation_key":"legacy:receipt:old",'
                    '"attempt":1,"provider_id":"provider:a","operation":"OLD",'
                    '"status":"SUCCESS","billing_basis":"UNKNOWN",'
                    '"estimated_cost_usd":null,"measured_cost_usd":null,'
                    '"total_tokens":null,"input_seconds":null,"request_count":1,'
                    '"claim_id":null,"content_id":"content:a","source_id":"source:a",'
                    '"collection_id":null}]'
                )

        receipts = CaptureStore().operation_ledger_receipts(source_id="source:a")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].billing_basis, "UNKNOWN")
        summary = CaptureStore().operation_ledger_summary(source_id="source:a")
        self.assertFalse(summary.cost_complete)
        self.assertEqual(summary.unknown_cost_operation_count, 1)

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
        self.assertIn("INSERT INTO finding_assertion (", store.sql)
        self.assertIn("INSERT INTO finding_assertion_citation (", store.sql)
        self.assertIn("existing_exact AS (", store.sql)
        self.assertIn("finding_current AS (", store.sql)
        self.assertIn("assertion_current AS (", store.sql)
        self.assertIn("finding.model_bundle = :'model_bundle'::jsonb", store.sql)
        self.assertIn("eligible.observation_ids ? observation.id", store.sql)
        self.assertIn("'SUPPORT'", store.sql)
        self.assertIn("FROM inserted", store.sql)
        self.assertNotIn("SELECT id FROM finding", store.sql)


if __name__ == "__main__":
    unittest.main()
