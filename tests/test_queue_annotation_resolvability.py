"""Worker and coverage-store type hints must resolve at runtime.

These are metadata-only imports and reflections, not provider, DB or queue calls.
"""

import unittest
from typing import get_type_hints

from dichiarazioni_pubbliche.queue_runtime import (
    ContentRecord,
    ProcessingJob,
    QueueRuntimeStore,
)
from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore
from dichiarazioni_pubbliche.worker_handlers_claim_evidence import (
    ClaimEvidenceJobHandlers,
)
from dichiarazioni_pubbliche.worker_handlers_transcript import (
    TranscriptAsrJobHandlers,
)
from dichiarazioni_pubbliche.worker_handlers_verification import (
    VerificationRelationReanalysisJobHandlers,
)


class QueueAnnotationResolvabilityTests(unittest.TestCase):
    def test_coverage_store_mapping_annotations_resolve(self):
        for store in (QueueRuntimeStore, ClaimEvidenceObservationStore):
            for method in ("record_coverage_need_attempt", "block_coverage_need"):
                with self.subTest(store=store.__name__, method=method):
                    hints = get_type_hints(getattr(store, method))
                    self.assertIn("metadata", hints)

    def test_worker_job_and_content_annotations_resolve(self):
        targets = (
            (ClaimEvidenceJobHandlers, "prepare_claim_windows"),
            (TranscriptAsrJobHandlers, "triage_content"),
            (VerificationRelationReanalysisJobHandlers, "verify_claim"),
        )
        for handler, method in targets:
            with self.subTest(handler=handler.__name__, method=method):
                hints = get_type_hints(getattr(handler, method))
                self.assertIs(hints["job"], ProcessingJob)
                self.assertIs(hints["content"], ContentRecord)


if __name__ == "__main__":
    unittest.main()
