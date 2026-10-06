import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.worker_daemon import ProcessingWorker  # noqa: E402
from dichiarazioni_pubbliche.worker_handlers_claim_evidence import (  # noqa: E402
    ClaimEvidenceJobHandlers,
)
from dichiarazioni_pubbliche.worker_handlers_transcript import (  # noqa: E402
    TranscriptAsrJobHandlers,
)
from dichiarazioni_pubbliche.worker_handlers_verification import (  # noqa: E402
    VerificationRelationReanalysisJobHandlers,
)
from dichiarazioni_pubbliche.worker_dispatch import (  # noqa: E402
    HandlerCapability,
    HandlerFamily,
    UnregisteredWorkerJobType,
    dispatch_processing_worker_job,
    processing_worker_handler_catalog,
    resolve_processing_worker_handler,
)


EXPECTED_HANDLERS = {
    "TRANSCRIPT_RESOLVE_PLATFORM": "resolve_platform",
    "TRANSCRIPT_ACQUIRE_CAPTION": "acquire_caption",
    "TRANSCRIPT_CANONICALIZE": "canonicalize",
    "TRANSCRIPT_ACQUIRE_ASR": "acquire_asr",
    "CLAIM_PREPARE": "prepare_claim_windows",
    "CLAIM_EXTRACT": "prepare_claim_windows",
    "CLAIM_EXTRACT_WINDOW": "extract_claim_window",
    "EVIDENCE_FETCH_URL": "fetch_evidence_url",
    "EVIDENCE_QUERY_OFFICIAL": "query_official_evidence",
    "EVIDENCE_OBSERVE": "persist_evidence_observation",
    "VERIFY_CLAIM": "verify_claim",
    "CLASSIFY_CLAIM_RELATION": "classify_claim_relation_job",
    "REGISTER_REANALYSIS": "register_reanalysis",
    "REANALYZE_CLAIM": "reanalyze_claim",
}


class WorkerDispatchContractTests(unittest.TestCase):
    def test_process_keeps_content_and_budget_orchestration_before_dispatch(self):
        calls = []

        class Store:
            def content(self, content_id):
                calls.append(("content", content_id))
                return "content-record"

        class Job:
            content_id = "content:a"
            job_type = "VERIFY_CLAIM"

        worker = ProcessingWorker.__new__(ProcessingWorker)
        worker.store = Store()
        worker._ensure_budget = lambda job, content: calls.append(
            ("budget", job, content)
        )

        with patch(
            "dichiarazioni_pubbliche.worker_daemon.dispatch_processing_worker_job",
            side_effect=lambda current, job, content: calls.append(
                ("dispatch", current, job, content)
            ),
        ):
            worker.process(Job())

        self.assertEqual(calls[0], ("content", "content:a"))
        self.assertEqual(calls[1][0], "budget")
        self.assertEqual(calls[2][0], "dispatch")
        self.assertIs(calls[2][1], worker)

    def test_handler_bodies_live_on_three_deep_family_mixins(self):
        owners = {
            TranscriptAsrJobHandlers: {
                "resolve_platform",
                "acquire_caption",
                "canonicalize",
                "acquire_asr",
            },
            ClaimEvidenceJobHandlers: {
                "prepare_claim_windows",
                "extract_claim_window",
                "fetch_evidence_url",
                "query_official_evidence",
                "persist_evidence_observation",
            },
            VerificationRelationReanalysisJobHandlers: {
                "verify_claim",
                "classify_claim_relation_job",
                "register_reanalysis",
                "reanalyze_claim",
            },
        }
        for owner, method_names in owners.items():
            for method_name in method_names:
                with self.subTest(owner=owner.__name__, method=method_name):
                    self.assertIn(method_name, owner.__dict__)
                    self.assertNotIn(method_name, ProcessingWorker.__dict__)
                    self.assertIs(
                        getattr(ProcessingWorker, method_name),
                        getattr(owner, method_name),
                    )

    def test_catalog_is_closed_and_references_existing_handler_callables(self):
        catalog = processing_worker_handler_catalog()

        self.assertEqual(set(catalog), set(EXPECTED_HANDLERS))
        with self.assertRaises(TypeError):
            catalog["EXTRA_JOB"] = catalog["VERIFY_CLAIM"]  # type: ignore[index]

        for job_type, handler_name in EXPECTED_HANDLERS.items():
            with self.subTest(job_type=job_type):
                spec = catalog[job_type]
                self.assertEqual(spec.job_type, job_type)
                self.assertIs(spec.handler, getattr(ProcessingWorker, handler_name))

        self.assertIs(
            catalog["CLAIM_PREPARE"].handler,
            catalog["CLAIM_EXTRACT"].handler,
        )

    def test_catalog_groups_jobs_into_three_deep_handler_families(self):
        catalog = processing_worker_handler_catalog()
        family_counts = {family: 0 for family in HandlerFamily}
        for spec in catalog.values():
            family_counts[spec.family] += 1
            self.assertIsInstance(spec.capability, HandlerCapability)

        self.assertEqual(
            family_counts,
            {
                HandlerFamily.TRANSCRIPT_ASR: 4,
                HandlerFamily.CLAIM_EVIDENCE: 6,
                HandlerFamily.VERIFICATION_RELATION_REANALYSIS: 4,
            },
        )
        self.assertEqual(
            catalog["TRANSCRIPT_ACQUIRE_ASR"].capability,
            HandlerCapability.REMOTE_ASR,
        )
        self.assertEqual(
            catalog["CLAIM_EXTRACT_WINDOW"].capability,
            HandlerCapability.CLAIM_EXTRACTION,
        )
        self.assertEqual(
            catalog["VERIFY_CLAIM"].capability,
            HandlerCapability.DETERMINISTIC_VERIFICATION,
        )

    def test_unknown_job_type_fails_closed_before_invocation(self):
        with self.assertRaisesRegex(
            UnregisteredWorkerJobType,
            r"^NO_HANDLER:DO_SOMETHING_UNKNOWN$",
        ):
            resolve_processing_worker_handler("DO_SOMETHING_UNKNOWN")

        class UnknownJob:
            job_type = "DO_SOMETHING_UNKNOWN"

        with self.assertRaisesRegex(
            UnregisteredWorkerJobType,
            r"^NO_HANDLER:DO_SOMETHING_UNKNOWN$",
        ):
            dispatch_processing_worker_job(object(), UnknownJob(), object())

    def test_dispatch_invokes_handler_without_queue_lifecycle_or_budget_work(self):
        calls = []

        def handler(worker, job, content):
            calls.append((worker, job, content))

        class BombStore:
            def __getattr__(self, name):
                if name in {
                    "reap_expired",
                    "claim",
                    "renew",
                    "defer",
                    "block",
                    "retry",
                    "complete",
                    "state_counts",
                    "cost_snapshot",
                }:
                    raise AssertionError(f"orchestration access from dispatch: {name}")
                raise AttributeError(name)

        class Worker:
            store = BombStore()

        class Job:
            job_type = "TRANSCRIPT_CANONICALIZE"

        worker = Worker()
        job = Job()
        content = object()
        with patch.object(ProcessingWorker, "canonicalize", handler):
            dispatch_processing_worker_job(worker, job, content)

        self.assertEqual(calls, [(worker, job, content)])

    def test_orchestration_methods_are_not_registered_handlers(self):
        registered = {
            spec.handler.__name__ for spec in processing_worker_handler_catalog().values()
        }
        self.assertTrue(
            registered.isdisjoint(
                {
                    "process",
                    "run",
                    "_ensure_budget",
                    "finalize_claim_content_if_complete",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
