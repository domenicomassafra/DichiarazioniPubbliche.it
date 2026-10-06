import inspect
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import (  # noqa: E402
    PsqlRuntime,
    ProcessingJob,
    QueueRuntimeStore,
)
from dichiarazioni_pubbliche.queue_store import (  # noqa: E402
    ClaimEvidenceObservationStore,
    QueueExecutionCostStore,
    ReviewPublicationDecisionStore,
    TranscriptCanonicalStore,
)


QUEUE_EXECUTION_COST_METHODS = {
    "reap_expired",
    "claim",
    "renew",
    "complete",
    "retry",
    "defer",
    "block",
    "enqueue_followup",
    "enqueue_jobs_bulk",
    "unfinished_sibling_jobs",
    "state_counts",
    "cost_snapshot",
    "operation_ledger_receipts",
    "operation_ledger_summary",
    "record_receipt",
}

MIGRATED_QUEUE_EXECUTION_METHODS = QUEUE_EXECUTION_COST_METHODS

TRANSCRIPT_CANONICAL_METHODS = {
    "insert_transcript_variant",
    "insert_transcript_segments",
    "transcript_segments",
    "canonical_candidate_variant_ids",
    "canonical_segments",
    "upsert_canonical_segments",
}

CLAIM_EVIDENCE_OBSERVATION_METHODS = {
    "insert_atomic_claims",
    "claim_count",
    "upsert_evidence",
    "link_claim_evidence",
    "claim_evidence_count",
    "insert_evidence_observation",
    "update_evidence_observation_status",
    "update_claim_evidence_status",
    "claim_context",
    "approved_verification_evidence",
    "source_intelligence_relations",
    "insert_evidence_set_assessment",
    "coverage_collection_ids_for_claim",
    "upsert_coverage_need",
    "searchable_coverage_needs",
    "record_coverage_need_attempt",
    "satisfy_coverage_need",
    "coverage_need_original_source_preflight",
    "block_coverage_need",
}

MIGRATED_COVERAGE_METHODS = {
    "coverage_collection_ids_for_claim",
    "upsert_coverage_need",
    "searchable_coverage_needs",
    "record_coverage_need_attempt",
    "satisfy_coverage_need",
    "coverage_need_original_source_preflight",
    "block_coverage_need",
}

MIGRATED_SOURCE_ASSESSMENT_METHODS = {
    "claim_context",
    "approved_verification_evidence",
    "source_intelligence_relations",
    "insert_evidence_set_assessment",
}

MIGRATED_ATOMIC_CLAIM_METHODS = {
    "insert_atomic_claims",
    "claim_count",
}

MIGRATED_EVIDENCE_OBSERVATION_METHODS = {
    "upsert_evidence",
    "link_claim_evidence",
    "claim_evidence_count",
    "insert_evidence_observation",
    "update_evidence_observation_status",
    "update_claim_evidence_status",
}

MIGRATED_CLAIM_EVIDENCE_METHODS = (
    MIGRATED_COVERAGE_METHODS
    | MIGRATED_SOURCE_ASSESSMENT_METHODS
    | MIGRATED_ATOMIC_CLAIM_METHODS
    | MIGRATED_EVIDENCE_OBSERVATION_METHODS
)

LEGACY_CLAIM_EVIDENCE_METHODS = (
    CLAIM_EVIDENCE_OBSERVATION_METHODS - MIGRATED_CLAIM_EVIDENCE_METHODS
)

REVIEW_PUBLICATION_DECISION_METHODS = {
    "publish_finding_with_review",
    "finding_context",
    "insert_verification_run",
    "latest_verification_template",
    "latest_finding_id",
    "insert_finding_draft",
    "insert_relation_candidate",
    "insert_inference_candidate",
    "approve_relation_candidate_with_review",
    "public_relation_candidates",
    "insert_reanalysis_trigger",
    "advance_reanalysis_trigger",
    "record_review_event",
    "insert_right_of_reply",
    "attach_reply_reanalysis_job",
    "publish_right_of_reply_with_review",
    "insert_correction",
    "publish_correction_with_review",
}

MIGRATED_REVIEW_PUBLICATION_METHODS = REVIEW_PUBLICATION_DECISION_METHODS


class QueueExecutionCostStoreContractTests(unittest.TestCase):
    def test_store_is_narrow_and_uses_psql_runtime_directly(self):
        self.assertTrue(issubclass(QueueExecutionCostStore, PsqlRuntime))
        self.assertFalse(issubclass(QueueExecutionCostStore, QueueRuntimeStore))

        declared = {
            name
            for name, value in QueueExecutionCostStore.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(declared, QUEUE_EXECUTION_COST_METHODS)

        for unrelated_method in (
            "content",
            "insert_transcript_variant",
            "insert_atomic_claims",
            "upsert_evidence",
            "insert_verification_run",
            "record_review_event",
            "insert_right_of_reply",
            "insert_correction",
            "publish_finding_with_review",
        ):
            self.assertFalse(hasattr(QueueExecutionCostStore, unrelated_method))

    def test_execution_sql_is_owned_by_narrow_store_with_legacy_delegation(self):
        for method_name in MIGRATED_QUEUE_EXECUTION_METHODS:
            with self.subTest(method=method_name):
                narrow = getattr(QueueExecutionCostStore, method_name)
                legacy = getattr(QueueRuntimeStore, method_name)
                self.assertIsNot(narrow, legacy)
                self.assertEqual(inspect.signature(narrow), inspect.signature(legacy))
                legacy_source = inspect.getsource(legacy)
                self.assertIn("QueueExecutionCostStore", legacy_source)
                self.assertNotIn("SELECT ", legacy_source)
                self.assertNotIn("INSERT INTO ", legacy_source)
                self.assertNotIn("UPDATE ", legacy_source)

    def test_claim_executes_through_inherited_runtime_seam(self):
        class CaptureStore(QueueExecutionCostStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return json.dumps(
                    {
                        "id": "job:a",
                        "content_id": "content:a",
                        "job_type": "CAPTION_FETCH",
                        "attempt": 2,
                        "payload": {"language": "it"},
                    }
                )

        store = CaptureStore()
        job = store.claim("worker:a", lease_seconds=45)

        self.assertEqual(
            job,
            ProcessingJob(
                job_id="job:a",
                content_id="content:a",
                job_type="CAPTION_FETCH",
                attempt=2,
                payload={"language": "it"},
            ),
        )
        self.assertIn("claim_processing_job", store.sql)
        self.assertEqual(store.variables["worker_id"], "worker:a")
        self.assertEqual(store.variables["lease_seconds"], 45)

    def test_summary_resolves_receipt_query_on_narrow_store(self):
        class CaptureStore(QueueExecutionCostStore):
            def __init__(self):
                self.filters = None

            def operation_ledger_receipts(self, **filters):
                self.filters = filters
                return ()

        store = CaptureStore()
        summary = store.operation_ledger_summary(content_id="content:a")

        self.assertEqual(store.filters, {"content_id": "content:a"})
        self.assertEqual(summary.operation_count, 0)
        self.assertEqual(summary.attempt_count, 0)


class TranscriptCanonicalStoreContractTests(unittest.TestCase):
    def test_store_is_narrow_and_uses_psql_runtime_directly(self):
        self.assertTrue(issubclass(TranscriptCanonicalStore, PsqlRuntime))
        self.assertFalse(issubclass(TranscriptCanonicalStore, QueueRuntimeStore))

        declared = {
            name
            for name, value in TranscriptCanonicalStore.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(declared, TRANSCRIPT_CANONICAL_METHODS)

        for unrelated_method in (
            "claim",
            "renew",
            "complete",
            "retry",
            "defer",
            "block",
            "enqueue_followup",
            "record_receipt",
            "insert_atomic_claims",
            "upsert_evidence",
            "insert_verification_run",
            "record_review_event",
            "insert_right_of_reply",
            "insert_correction",
            "publish_finding_with_review",
        ):
            self.assertFalse(hasattr(TranscriptCanonicalStore, unrelated_method))

    def test_transcript_sql_is_owned_by_narrow_store_with_legacy_delegation(self):
        for method_name in TRANSCRIPT_CANONICAL_METHODS:
            with self.subTest(method=method_name):
                narrow = getattr(TranscriptCanonicalStore, method_name)
                legacy = getattr(QueueRuntimeStore, method_name)
                self.assertIsNot(narrow, legacy)
                self.assertEqual(inspect.signature(narrow), inspect.signature(legacy))
                legacy_source = inspect.getsource(legacy)
                self.assertIn("TranscriptCanonicalStore", legacy_source)
                self.assertNotIn("SELECT ", legacy_source)
                self.assertNotIn("INSERT INTO ", legacy_source)

    def test_transcript_read_executes_through_inherited_runtime_seam(self):
        class CaptureStore(TranscriptCanonicalStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return json.dumps(
                    [
                        {
                            "id": "segment:a",
                            "segment_index": 0,
                            "start_ms": 10,
                            "end_ms": 20,
                            "text": "ciao",
                        }
                    ]
                )

        store = CaptureStore()
        rows = store.transcript_segments("transcript:a")

        self.assertEqual(rows[0]["id"], "segment:a")
        self.assertIn("FROM transcript_segment", store.sql)
        self.assertEqual(store.variables, {"variant_id": "transcript:a"})


class ClaimEvidenceObservationStoreContractTests(unittest.TestCase):
    def test_store_is_narrow_and_uses_psql_runtime_directly(self):
        self.assertTrue(issubclass(ClaimEvidenceObservationStore, PsqlRuntime))
        self.assertFalse(issubclass(ClaimEvidenceObservationStore, QueueRuntimeStore))

        declared = {
            name
            for name, value in ClaimEvidenceObservationStore.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(declared, CLAIM_EVIDENCE_OBSERVATION_METHODS)

        for unrelated_method in (
            "reap_expired",
            "claim",
            "renew",
            "complete",
            "retry",
            "defer",
            "block",
            "enqueue_followup",
            "record_receipt",
            "insert_transcript_variant",
            "insert_transcript_segments",
            "canonical_segments",
            "upsert_canonical_segments",
            "approve_claim_evidence_with_review",
            "approve_evidence_observation_with_review",
            "finding_context",
            "insert_verification_run",
            "latest_verification_template",
            "latest_finding_id",
            "insert_finding_draft",
            "record_review_event",
            "insert_reanalysis_trigger",
            "insert_right_of_reply",
            "insert_correction",
            "publish_finding_with_review",
        ):
            self.assertFalse(hasattr(ClaimEvidenceObservationStore, unrelated_method))

    def test_migrated_sql_is_owned_by_narrow_store_with_legacy_delegation(self):
        for method_name in MIGRATED_CLAIM_EVIDENCE_METHODS:
            with self.subTest(method=method_name):
                narrow = getattr(ClaimEvidenceObservationStore, method_name)
                legacy = getattr(QueueRuntimeStore, method_name)
                self.assertIsNot(narrow, legacy)
                self.assertEqual(inspect.signature(narrow), inspect.signature(legacy))
                legacy_source = inspect.getsource(legacy)
                self.assertIn("ClaimEvidenceObservationStore", legacy_source)
                self.assertNotIn("SELECT ", legacy_source)
                self.assertNotIn("INSERT INTO ", legacy_source)
                self.assertNotIn("UPDATE ", legacy_source)

    def test_all_declared_claim_evidence_methods_are_migrated(self):
        self.assertEqual(LEGACY_CLAIM_EVIDENCE_METHODS, set())

    def test_claim_read_executes_through_inherited_runtime_seam(self):
        class CaptureStore(ClaimEvidenceObservationStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return "3"

        store = CaptureStore()
        count = store.claim_count("content:a")

        self.assertEqual(count, 3)
        self.assertIn("FROM atomic_claim", store.sql)
        self.assertEqual(store.variables, {"content_id": "content:a"})

    def test_coverage_satisfaction_keeps_original_source_preflight_co_located(self):
        class CaptureStore(ClaimEvidenceObservationStore):
            def __init__(self):
                self.preflight_calls = []

            def coverage_need_original_source_preflight(self, **variables):
                self.preflight_calls.append(variables)
                return {"required": False, "accepted": True, "status": "NOT_APPLICABLE"}

            def run(self, sql, **variables):
                return "SATISFIED"

        store = CaptureStore()
        result = store.satisfy_coverage_need(
            coverage_need_id="coverage:a",
            event_id="event:a",
            content_id="content:a",
        )

        self.assertEqual(result, "SATISFIED")
        self.assertEqual(
            store.preflight_calls,
            [{"coverage_need_id": "coverage:a", "content_id": "content:a"}],
        )

    def test_original_source_satisfaction_persists_bounded_resolution_receipt(self):
        class CaptureStore(ClaimEvidenceObservationStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def coverage_need_original_source_preflight(self, **variables):
                return {
                    "required": True,
                    "accepted": True,
                    "status": "RESOLVED",
                    "need_type": "ATTRIBUTION_GAP",
                    "atomic_claim_id": None,
                    "claim_candidate_id": "claim-candidate:reported",
                    "source_intelligence_assessment_id": "assessment:reported",
                    "root_content_id": "content:root",
                    "path_content_ids": ["content:root"],
                    "path_edge_ids": [],
                    "private_text": "must never persist",
                }

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return "SATISFIED"

        store = CaptureStore()
        self.assertEqual(
            store.satisfy_coverage_need(
                coverage_need_id="coverage:original",
                event_id="event:original",
                content_id="content:root",
            ),
            "SATISFIED",
        )
        receipt = json.loads(store.variables["original_source_resolution"])
        self.assertEqual(receipt["root_content_id"], "content:root")
        self.assertEqual(receipt["path_content_ids"], ["content:root"])
        self.assertEqual(receipt["need_type"], "ATTRIBUTION_GAP")
        self.assertEqual(
            receipt["claim_candidate_id"], "claim-candidate:reported"
        )
        self.assertNotIn("private_text", receipt)
        self.assertIn("UPDATE evidence_set_assessment", store.sql)
        self.assertIn("original_source_resolution", store.sql)
        self.assertNotIn("UPDATE claim_candidate", store.sql)
        self.assertNotIn("UPDATE claim_candidate", store.sql)
        self.assertNotIn("UPDATE statement_candidate", store.sql)


class ReviewPublicationDecisionStoreContractTests(unittest.TestCase):
    def test_store_is_narrow_and_uses_psql_runtime_directly(self):
        self.assertTrue(issubclass(ReviewPublicationDecisionStore, PsqlRuntime))
        self.assertFalse(issubclass(ReviewPublicationDecisionStore, QueueRuntimeStore))

        declared = {
            name
            for name, value in ReviewPublicationDecisionStore.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(declared, REVIEW_PUBLICATION_DECISION_METHODS)

        for unrelated_method in (
            "reap_expired",
            "claim",
            "renew",
            "complete",
            "retry",
            "defer",
            "block",
            "enqueue_followup",
            "record_receipt",
            "insert_transcript_variant",
            "insert_transcript_segments",
            "canonical_segments",
            "upsert_canonical_segments",
            "insert_atomic_claims",
            "claim_count",
            "upsert_evidence",
            "link_claim_evidence",
            "insert_evidence_observation",
            "approve_claim_evidence_with_review",
            "approve_evidence_observation_with_review",
            "source_intelligence_relations",
            "insert_evidence_set_assessment",
            "upsert_coverage_need",
            "satisfy_coverage_need",
        ):
            self.assertFalse(hasattr(ReviewPublicationDecisionStore, unrelated_method))

    def test_review_publication_sql_is_owned_by_narrow_store_with_legacy_delegation(self):
        for method_name in MIGRATED_REVIEW_PUBLICATION_METHODS:
            with self.subTest(method=method_name):
                narrow = getattr(ReviewPublicationDecisionStore, method_name)
                legacy = getattr(QueueRuntimeStore, method_name)
                self.assertIsNot(narrow, legacy)
                self.assertEqual(inspect.signature(narrow), inspect.signature(legacy))
                legacy_source = inspect.getsource(legacy)
                self.assertIn("ReviewPublicationDecisionStore", legacy_source)
                self.assertNotIn("SELECT ", legacy_source)
                self.assertNotIn("INSERT INTO ", legacy_source)
                self.assertNotIn("UPDATE ", legacy_source)

    def test_all_declared_review_publication_methods_are_migrated(self):
        self.assertEqual(
            MIGRATED_REVIEW_PUBLICATION_METHODS,
            REVIEW_PUBLICATION_DECISION_METHODS,
        )

    def test_finding_context_executes_through_inherited_runtime_seam(self):
        class CaptureStore(ReviewPublicationDecisionStore):
            def __init__(self):
                self.sql = ""
                self.variables = {}

            def run(self, sql, **variables):
                self.sql = sql
                self.variables = variables
                return json.dumps(
                    {
                        "finding_id": "finding:a",
                        "claim_id": "claim:a",
                        "content_id": "content:a",
                        "publication_status": "HOLD",
                        "supersedes_id": None,
                    }
                )

        store = CaptureStore()
        context = store.finding_context("finding:a")

        self.assertEqual(context["finding_id"], "finding:a")
        self.assertIn("FROM finding", store.sql)
        self.assertEqual(store.variables, {"finding_id": "finding:a"})


if __name__ == "__main__":
    unittest.main()
