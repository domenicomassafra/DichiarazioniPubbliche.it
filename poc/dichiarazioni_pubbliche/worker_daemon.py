from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_runtime import OmniRouteClaimClient
from dichiarazioni_pubbliche.provider_optin import configure_provider_clients
from dichiarazioni_pubbliche.evidence_runtime import (
    SafeEvidenceFetcher,
)
from dichiarazioni_pubbliche.platform_transcript import (
    PrivateTranscriptStore,
    YouTubeResolver,
)
from dichiarazioni_pubbliche.queue_runtime import (
    ContentRecord,
    ProcessingJob,
    QueueRuntimeStore,
)
from dichiarazioni_pubbliche.source_watcher import DEFAULT_REGISTRY, get_source, load_registry
from dichiarazioni_pubbliche.source_intelligence import (
    SourceIntelligenceContract,
    load_source_intelligence_contract,
)
from dichiarazioni_pubbliche.worker_dispatch import (
    UnregisteredWorkerJobType,
    dispatch_processing_worker_job,
)
from dichiarazioni_pubbliche.worker_errors import BlockedJob, DeferredJob, RetryableJob
from dichiarazioni_pubbliche.worker_handlers_claim_evidence import ClaimEvidenceJobHandlers
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers
from dichiarazioni_pubbliche.worker_handlers_verification import (
    VerificationRelationReanalysisJobHandlers,
)


DEFAULT_PRIVATE_ROOT = Path.home() / ".local" / "share" / "dichiarazioni-pubbliche"
DEFAULT_STATE_ROOT = Path.home() / ".local" / "state" / "dichiarazioni-pubbliche"


@dataclass(frozen=True)
class WorkerBudget:
    max_cost_usd_per_day: float = 5.0
    max_cost_usd_per_source_day: float = 1.0
    max_cost_usd_per_job: float = 0.25
    budget_defer_seconds: int = 3600


@dataclass(frozen=True)
class WorkerRunSummary:
    worker_id: str
    reaped_expired: int
    claimed: int
    completed: int
    deferred: int
    blocked: int
    retried: int
    dead_lettered: int
    queue_states: dict[str, int]








class WorkerProcessLock:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self._handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        handle = open(self.path, "a+", encoding="utf-8")
        os.chmod(self.path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "WorkerProcessLock":
        if not self.acquire():
            raise RuntimeError("WORKER_ALREADY_RUNNING")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()






class ProcessingWorker(
    TranscriptAsrJobHandlers,
    ClaimEvidenceJobHandlers,
    VerificationRelationReanalysisJobHandlers,
):
    def __init__(
        self,
        *,
        store: QueueRuntimeStore,
        registry: dict[str, Any],
        resolver: YouTubeResolver,
        private_store: PrivateTranscriptStore,
        worker_id: str,
        budget: WorkerBudget,
        lease_seconds: int = 300,
        max_attempts: int = 5,
        groq_api_key: str | None = None,
        local_asr=None,
        claim_client: OmniRouteClaimClient | None = None,
        claim_max_usd_per_1k_total_tokens: float | None = None,
        evidence_fetcher: SafeEvidenceFetcher | None = None,
        source_intelligence_contract: SourceIntelligenceContract | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.resolver = resolver
        self.private_store = private_store
        self.worker_id = worker_id
        self.budget = budget
        self.lease_seconds = max(lease_seconds, 30)
        self.max_attempts = max(max_attempts, 1)
        self.groq_api_key = groq_api_key or ""
        self.local_asr = local_asr
        self.claim_client = claim_client
        self.claim_max_usd_per_1k_total_tokens = (
            claim_max_usd_per_1k_total_tokens
        )
        self._claim_probe = None
        self.evidence_fetcher = evidence_fetcher
        self.source_intelligence_contract = (
            source_intelligence_contract or load_source_intelligence_contract()
        )

    def _source(self, source_id: str) -> dict[str, Any]:
        try:
            return get_source(self.registry, source_id)
        except KeyError as exc:
            raise BlockedJob(f"SOURCE_NOT_IN_REGISTRY:{source_id}") from exc

    def _ensure_budget(self, job: ProcessingJob, content: ContentRecord) -> None:
        try:
            estimate = float(job.payload.get("estimated_cost_usd") or 0.0)
        except (TypeError, ValueError) as exc:
            raise BlockedJob("INVALID_ESTIMATED_COST") from exc
        if estimate < 0:
            raise BlockedJob("NEGATIVE_ESTIMATED_COST")
        if estimate > self.budget.max_cost_usd_per_job:
            raise DeferredJob(
                "JOB_COST_CAP_REACHED", self.budget.budget_defer_seconds
            )
        if estimate == 0:
            return
        snapshot = self.store.cost_snapshot(content.source_id)
        if snapshot.global_day_usd + estimate > self.budget.max_cost_usd_per_day:
            raise DeferredJob(
                "GLOBAL_DAILY_BUDGET_REACHED", self.budget.budget_defer_seconds
            )
        if (
            snapshot.source_day_usd + estimate
            > self.budget.max_cost_usd_per_source_day
        ):
            raise DeferredJob(
                "SOURCE_DAILY_BUDGET_REACHED", self.budget.budget_defer_seconds
            )


















    def finalize_claim_content_if_complete(self, job: ProcessingJob) -> None:
        if job.job_type != "CLAIM_EXTRACT_WINDOW":
            return
        remaining = self.store.unfinished_sibling_jobs(
            content_id=job.content_id,
            job_type="CLAIM_EXTRACT_WINDOW",
            exclude_job_id="__no_such_job__",
        )
        if remaining != 0:
            return
        self.store.update_content_status(
            job.content_id,
            "CLAIMS_EXTRACTED",
            {
                "atomic_claim_count": self.store.claim_count(job.content_id),
                "claim_windows_remaining": 0,
            },
        )


    def process(self, job: ProcessingJob) -> None:
        content = self.store.content(job.content_id)
        self._ensure_budget(job, content)
        try:
            dispatch_processing_worker_job(self, job, content)
        except UnregisteredWorkerJobType as exc:
            raise BlockedJob(str(exc)) from exc

    def run(self, max_jobs: int) -> WorkerRunSummary:
        reaped = self.store.reap_expired(self.max_attempts)
        claimed = completed = deferred = blocked = retried = dead = 0
        for _ in range(max(max_jobs, 0)):
            job = self.store.claim(self.worker_id, self.lease_seconds)
            if job is None:
                break
            claimed += 1
            try:
                self.process(job)
            except DeferredJob as exc:
                self.store.defer(
                    job.job_id,
                    self.worker_id,
                    str(exc),
                    delay_seconds=exc.delay_seconds,
                )
                deferred += 1
            except BlockedJob as exc:
                self.store.block(job.job_id, self.worker_id, str(exc))
                blocked += 1
            except RetryableJob as exc:
                state = self.store.retry(
                    job.job_id,
                    self.worker_id,
                    str(exc),
                    delay_seconds=exc.delay_seconds,
                    max_attempts=self.max_attempts,
                )
                if state == "DEAD_LETTER":
                    dead += 1
                else:
                    retried += 1
            except Exception as exc:
                delay = min(60 * (2 ** max(job.attempt, 0)), 3600)
                state = self.store.retry(
                    job.job_id,
                    self.worker_id,
                    f"{type(exc).__name__}:{exc}"[:1000],
                    delay_seconds=delay,
                    max_attempts=self.max_attempts,
                )
                if state == "DEAD_LETTER":
                    dead += 1
                else:
                    retried += 1
            else:
                if not self.store.complete(job.job_id, self.worker_id):
                    raise RuntimeError(f"LEASE_LOST_ON_COMPLETE:{job.job_id}")
                completed += 1
                self.finalize_claim_content_if_complete(job)

        return WorkerRunSummary(
            worker_id=self.worker_id,
            reaped_expired=reaped,
            claimed=claimed,
            completed=completed,
            deferred=deferred,
            blocked=blocked,
            retried=retried,
            dead_lettered=dead,
            queue_states=self.store.state_counts(),
        )


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Dichiarazioni Pubbliche processing worker one-shot")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--private-root",
        type=Path,
        default=Path(
            os.environ.get("DICHIARAZIONI_PUBBLICHE_PRIVATE_DATA_ROOT", str(DEFAULT_PRIVATE_ROOT))
        ),
    )
    parser.add_argument("--worker-id", default=_default_worker_id())
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=Path(
            os.environ.get(
                "DICHIARAZIONI_PUBBLICHE_WORKER_LOCK",
                str(DEFAULT_STATE_ROOT / "worker.lock"),
            )
        ),
    )
    parser.add_argument("--max-jobs", type=int, default=5)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--max-cost-usd-day", type=float, default=5.0)
    parser.add_argument("--max-cost-usd-source-day", type=float, default=1.0)
    parser.add_argument("--max-cost-usd-job", type=float, default=0.25)
    args = parser.parse_args()

    try:
        provider_clients = configure_provider_clients(os.environ)
    except ValueError as exc:
        parser.error(str(exc))

    lock = WorkerProcessLock(args.lock_file)
    if not lock.acquire():
        print(
            json.dumps(
                {
                    "worker_id": args.worker_id,
                    "status": "SKIPPED_ALREADY_RUNNING",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    try:
        worker = ProcessingWorker(
            store=QueueRuntimeStore(args.database_url),
            registry=load_registry(args.registry),
            resolver=YouTubeResolver(),
            private_store=PrivateTranscriptStore(args.private_root),
            worker_id=args.worker_id,
            budget=WorkerBudget(
                max_cost_usd_per_day=max(args.max_cost_usd_day, 0.0),
                max_cost_usd_per_source_day=max(args.max_cost_usd_source_day, 0.0),
                max_cost_usd_per_job=max(args.max_cost_usd_job, 0.0),
            ),
            lease_seconds=args.lease_seconds,
            max_attempts=args.max_attempts,
            groq_api_key=provider_clients.groq_api_key,
            local_asr=provider_clients.local_asr,
            claim_client=provider_clients.claim_client,
            claim_max_usd_per_1k_total_tokens=provider_clients.claim_rate,
            evidence_fetcher=SafeEvidenceFetcher(),
        )
        print(json.dumps(asdict(worker.run(args.max_jobs)), ensure_ascii=False, indent=2))
    finally:
        lock.release()


if __name__ == "__main__":
    main()
