from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import socket
import urllib.error
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.asr_router import plan_asr
from dichiarazioni_pubbliche.claim_contract import validate_atomic_claim
from dichiarazioni_pubbliche.claim_runtime import (
    OmniRouteClaimClient,
    deterministic_claim_id,
    estimate_claim_request_cost,
)
from dichiarazioni_pubbliche.claim_windows import (
    build_claim_windows,
    canonical_segment_from_row,
)
from dichiarazioni_pubbliche.coverage_needs import (
    coverage_need_params,
    materialize_coverage_need_specs,
)
from dichiarazioni_pubbliche.evidence_runtime import (
    EvidencePolicyError,
    EvidenceRateLimited,
    SafeEvidenceFetcher,
    deterministic_evidence_id,
    get_evidence_source,
)
from dichiarazioni_pubbliche.evidence_query import compile_official_query
from dichiarazioni_pubbliche.finding_runtime import finding_draft_from_verification
from dichiarazioni_pubbliche.platform_transcript import (
    CaptionProbe,
    PlatformAccessRestricted,
    PrivateTranscriptStore,
    VideoCandidate,
    YouTubeResolver,
)
from dichiarazioni_pubbliche.queue_runtime import (
    ContentRecord,
    ProcessingJob,
    QueueRuntimeStore,
    deterministic_followup_job_id,
)
from dichiarazioni_pubbliche.remote_asr import (
    AsrAccessDenied,
    AsrRateLimited,
    AsrRequestRejected,
    AsrTransientError,
    GroqUrlTranscriber,
)
from dichiarazioni_pubbliche.reanalysis_runtime import deterministic_reanalysis_trigger
from dichiarazioni_pubbliche.relation_runtime import (
    RelationCandidateType,
    StructuredClaimRelationInput,
    classify_relation,
    deterministic_relation_candidate_id,
)
from dichiarazioni_pubbliche.source_watcher import DEFAULT_REGISTRY, get_source, load_registry
from dichiarazioni_pubbliche.source_intelligence import (
    SourceIntelligenceContract,
    SourceRelation,
    assess_evidence_set,
    evidence_item_from_row,
    load_source_intelligence_contract,
)
from dichiarazioni_pubbliche.transcript_contract import (
    TranscriptCandidate,
    reconcile_candidates,
)
from dichiarazioni_pubbliche.verification_runtime import (
    VerificationEvidence,
    VerificationRequest,
    deterministic_evidence_observation_id,
    deterministic_verification_run_id,
    verification_input_fingerprint,
    verify,
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


class BlockedJob(RuntimeError):
    pass


class DeferredJob(RuntimeError):
    def __init__(self, reason: str, delay_seconds: int) -> None:
        super().__init__(reason)
        self.delay_seconds = max(delay_seconds, 0)


class RetryableJob(RuntimeError):
    def __init__(self, reason: str, delay_seconds: int = 60) -> None:
        super().__init__(reason)
        self.delay_seconds = max(delay_seconds, 0)


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


def _caption_source_kind(probe: CaptionProbe) -> str:
    if probe.kind == "manual_caption":
        return "YOUTUBE_MANUAL_CAPTION"
    return "YOUTUBE_AUTO_CAPTION"


def _segment_rows(capture) -> list[dict[str, Any]]:
    return [
        {
            "segment_index": segment.segment_index,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "text": segment.text,
            "metadata": {},
        }
        for segment in capture.segments
    ]


class ProcessingWorker:
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

    def _enqueue_asr(self, content: ContentRecord, *, reason: str) -> None:
        if not content.duration_ms or content.duration_ms <= 0:
            raise BlockedJob("ASR_DURATION_UNKNOWN")
        duration_seconds = max(int(round(content.duration_ms / 1000)), 1)
        try:
            routing = plan_asr(duration_seconds=duration_seconds)
        except RuntimeError as exc:
            raise BlockedJob(str(exc)) from exc
        payload = {
            "source_id": content.source_id,
            "canonical_url": content.canonical_url,
            "duration_seconds": duration_seconds,
            "provider_id": routing.primary.provider_id,
            "route": routing.primary.route,
            "estimated_cost_usd": routing.primary.estimated_cost_usd or 0.0,
            "reason": reason,
        }
        self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="TRANSCRIPT_ACQUIRE_ASR",
            payload=payload,
            variant=routing.primary.route,
        )
        self.store.update_content_status(
            content.content_id,
            "TRANSCRIPT_ASR_QUEUED",
            {"asr_reason": reason, "asr_route": routing.primary.route},
        )

    def _probe_and_enqueue_caption(
        self,
        job: ProcessingJob,
        content: ContentRecord,
        candidate: VideoCandidate,
    ) -> None:
        if not self.store.renew(
            job.job_id, self.worker_id, lease_seconds=self.lease_seconds
        ):
            raise RetryableJob("LEASE_LOST_BEFORE_CAPTION_PROBE", 0)
        try:
            probe = self.resolver.probe_caption(candidate.canonical_url)
        except PlatformAccessRestricted:
            self.store.record_receipt(
                job_id=job.job_id,
                content_id=content.content_id,
                provider_id="youtube",
                model_id=None,
                operation="CAPTION_PROBE",
                request_id=None,
                input_bytes=None,
                input_seconds=None,
                estimated_cost_usd=0.0,
                status="ACCESS_RESTRICTED",
                receipt={
                    "video_id": candidate.video_id,
                    "reason": "PLATFORM_ENTITLEMENT_REQUIRED",
                },
                request_key=f"{candidate.video_id}:attempt:{job.attempt}",
            )
            self._enqueue_asr(content, reason="YOUTUBE_COPY_ACCESS_RESTRICTED")
            return
        except Exception as exc:
            self.store.record_receipt(
                job_id=job.job_id,
                content_id=content.content_id,
                provider_id="youtube",
                model_id=None,
                operation="CAPTION_PROBE",
                request_id=None,
                input_bytes=None,
                input_seconds=None,
                estimated_cost_usd=0.0,
                status="FAILED",
                receipt={
                    "video_id": candidate.video_id,
                    "error_type": type(exc).__name__,
                },
                request_key=f"{candidate.video_id}:attempt:{job.attempt}",
            )
            raise RetryableJob(f"CAPTION_PROBE_FAILED:{type(exc).__name__}") from exc

        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id="youtube",
            model_id=None,
            operation="CAPTION_PROBE",
            request_id=None,
            input_bytes=None,
            input_seconds=None,
            estimated_cost_usd=0.0,
            status="SUCCESS",
            receipt={
                "video_id": candidate.video_id,
                "caption_found": probe is not None,
                "caption_kind": probe.kind if probe else None,
                "caption_language": probe.language if probe else None,
            },
            request_key=f"{candidate.video_id}:attempt:{job.attempt}",
        )
        if probe is None:
            self._enqueue_asr(content, reason="NO_ITALIAN_PLATFORM_CAPTION")
            return

        self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="TRANSCRIPT_ACQUIRE_CAPTION",
            payload={
                "source_id": content.source_id,
                "platform": "youtube",
                "external_id": candidate.video_id,
                "canonical_url": candidate.canonical_url,
                "caption_kind": probe.kind,
                "caption_language": probe.language,
                "estimated_cost_usd": 0.0,
            },
            variant=f"{candidate.video_id}:{probe.kind}:{probe.language}",
        )
        self.store.update_content_status(
            content.content_id,
            "TRANSCRIPT_CAPTION_QUEUED",
            {
                "youtube_video_id": candidate.video_id,
                "caption_kind": probe.kind,
                "caption_language": probe.language,
            },
        )

    def resolve_platform(self, job: ProcessingJob, content: ContentRecord) -> None:
        source = self._source(content.source_id)
        platform = str(job.payload.get("platform") or "")
        if platform == "youtube":
            video_id = str(job.payload.get("external_id") or "").strip()
            url = str(job.payload.get("canonical_url") or "").strip()
            if not video_id or not url:
                raise BlockedJob("YOUTUBE_JOB_MISSING_ID_OR_URL")
            candidate = VideoCandidate(video_id, content.title, url)
        elif platform == "podcast_rss":
            try:
                candidate = self.resolver.resolve(content.title, source)
            except Exception as exc:
                raise RetryableJob(
                    f"YOUTUBE_RESOLUTION_FAILED:{type(exc).__name__}",
                    300,
                ) from exc
            if candidate is None:
                self._enqueue_asr(content, reason="PLATFORM_COPY_NOT_FOUND")
                return
            self.store.upsert_locator(
                content.content_id,
                platform="youtube",
                external_id=candidate.video_id,
                canonical_url=candidate.canonical_url,
                metadata={"resolved_from": "podcast_rss"},
            )
        else:
            raise BlockedJob(f"UNSUPPORTED_PLATFORM:{platform or 'missing'}")
        self._probe_and_enqueue_caption(job, content, candidate)

    def acquire_caption(self, job: ProcessingJob, content: ContentRecord) -> None:
        url = str(job.payload.get("canonical_url") or "").strip()
        probe = CaptionProbe(
            kind=str(job.payload.get("caption_kind") or ""),
            language=str(job.payload.get("caption_language") or ""),
        )
        if not url or probe.kind not in {"manual_caption", "automatic_caption"}:
            raise BlockedJob("INVALID_CAPTION_JOB_PAYLOAD")
        if not probe.language:
            raise BlockedJob("CAPTION_LANGUAGE_MISSING")
        if not self.store.renew(
            job.job_id, self.worker_id, lease_seconds=self.lease_seconds
        ):
            raise RetryableJob("LEASE_LOST_BEFORE_CAPTION_CAPTURE", 0)
        try:
            capture = self.resolver.capture_caption(url, probe)
        except Exception as exc:
            self.store.record_receipt(
                job_id=job.job_id,
                content_id=content.content_id,
                provider_id="youtube",
                model_id=None,
                operation="CAPTION_CAPTURE",
                request_id=None,
                input_bytes=None,
                input_seconds=None,
                estimated_cost_usd=0.0,
                status="FAILED",
                receipt={"error_type": type(exc).__name__},
                request_key=(
                    f"{job.payload.get('external_id') or url}:attempt:{job.attempt}"
                ),
            )
            raise RetryableJob(
                f"CAPTION_CAPTURE_FAILED:{type(exc).__name__}", 300
            ) from exc

        source_kind = _caption_source_kind(probe)
        variant_id, inserted = self.store.insert_transcript_variant(
            content_id=content.content_id,
            provider_id="youtube",
            source_kind=source_kind,
            language=probe.language,
            raw_text=capture.raw_text,
            raw_text_sha256=capture.raw_text_sha256,
            is_platform_caption=True,
            is_manual_caption=probe.kind == "manual_caption",
            metadata={
                "raw_caption_sha256": capture.raw_sha256,
                "video_id": job.payload.get("external_id"),
                "caption_kind": probe.kind,
            },
        )
        if inserted:
            self.store.insert_transcript_segments(
                variant_id=variant_id,
                segments=_segment_rows(capture),
            )

        receipt = {
            "raw_caption_sha256": capture.raw_sha256,
            "raw_text_sha256": capture.raw_text_sha256,
            "segment_count": len(capture.segments),
            "caption_kind": probe.kind,
            "caption_language": probe.language,
            "variant_id": variant_id,
        }
        self.private_store.persist_caption(
            content_id=content.content_id,
            variant_id=variant_id,
            capture=capture,
            receipt=receipt,
        )
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id="youtube",
            model_id=None,
            operation="CAPTION_CAPTURE",
            request_id=None,
            input_bytes=len(capture.raw_bytes),
            input_seconds=(
                max(segment.end_ms for segment in capture.segments) / 1000.0
            ),
            estimated_cost_usd=0.0,
            status="SUCCESS",
            receipt=receipt,
            request_key=capture.raw_sha256,
        )
        self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="TRANSCRIPT_CANONICALIZE",
            payload={
                "source_id": content.source_id,
                "variant_id": variant_id,
                "estimated_cost_usd": 0.0,
            },
            variant=variant_id,
        )
        self.store.update_content_status(
            content.content_id,
            "TRANSCRIPT_CANDIDATE_READY",
            {
                "transcript_variant_id": variant_id,
                "caption_raw_sha256": capture.raw_sha256,
                "caption_segment_count": len(capture.segments),
            },
        )

    def canonicalize(self, job: ProcessingJob, content: ContentRecord) -> None:
        variant_id = str(job.payload.get("variant_id") or "").strip()
        if not variant_id:
            raise BlockedJob("CANONICALIZE_VARIANT_ID_MISSING")
        existing_variants = self.store.canonical_candidate_variant_ids(
            content.content_id
        )
        if existing_variants and existing_variants != {variant_id}:
            raise BlockedJob("MULTI_VARIANT_CANONICAL_RECONCILIATION_REQUIRED")
        segments = self.store.transcript_segments(variant_id)
        if not segments:
            raise RetryableJob("CANONICALIZE_SEGMENTS_MISSING", 60)
        rows = []
        blocked = 0
        for row in segments:
            candidate = TranscriptCandidate(
                candidate_id=row["id"],
                provider_id="youtube",
                text=row["text"],
                start_ms=int(row["start_ms"]),
                end_ms=int(row["end_ms"]),
                source_kind="PLATFORM_CAPTION",
            )
            canonical = reconcile_candidates((candidate,))
            blocked += int(canonical.publication_blocked)
            signatures = sorted(
                {value for group in canonical.sensitive_signatures for value in group}
            )
            rows.append(
                {
                    "segment_index": int(row["segment_index"]),
                    "start_ms": canonical.start_ms,
                    "end_ms": canonical.end_ms,
                    "canonical_text": canonical.canonical_text,
                    "transcript_status": canonical.status.value,
                    "publication_blocked": canonical.publication_blocked,
                    "sensitive_signature": signatures,
                }
            )
        self.store.upsert_canonical_segments(
            content_id=content.content_id,
            variant_id=variant_id,
            rows=rows,
        )
        self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="CLAIM_PREPARE",
            payload={
                "source_id": content.source_id,
                "variant_id": variant_id,
                "segment_count": len(rows),
                "publication_blocked_segments": blocked,
                "estimated_cost_usd": 0.0,
            },
            variant=variant_id,
        )
        self.store.update_content_status(
            content.content_id,
            "TRANSCRIPT_CANONICAL_READY",
            {
                "canonical_segment_count": len(rows),
                "publication_blocked_segment_count": blocked,
            },
        )

    def prepare_claim_windows(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        variant_id = str(job.payload.get("variant_id") or "").strip()
        if not variant_id:
            raise BlockedJob("CLAIM_PREPARE_VARIANT_ID_MISSING")
        blocker = self._claim_runtime_blocker()
        if blocker:
            self.store.update_content_status(
                content.content_id,
                "CLAIM_EXTRACTION_BLOCKED",
                {
                    "runtime_blocker": blocker,
                    "claim_variant_id": variant_id,
                    "claim_window_materialized": False,
                },
            )
            raise BlockedJob(blocker)
        rows = self.store.canonical_segments(content.content_id)
        if not rows:
            raise RetryableJob("CLAIM_PREPARE_CANONICAL_SEGMENTS_MISSING", 60)
        windows = build_claim_windows(
            [canonical_segment_from_row(row) for row in rows]
        )
        if not windows:
            raise BlockedJob("CLAIM_PREPARE_NO_WINDOWS")
        ordered = sorted(
            windows,
            key=lambda window: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(window.priority, 3),
                window.window_index,
            ),
        )
        jobs = []
        total_tokens = 0
        for window in ordered:
            payload = window.queue_payload(
                source_id=content.source_id,
                variant_id=variant_id,
                model=self.claim_client.model,
                prompt_version=self.claim_client.prompt_version,
            )
            estimated_cost = estimate_claim_request_cost(
                estimated_input_tokens=window.estimated_input_tokens,
                max_output_tokens=self.claim_client.max_output_tokens,
                max_usd_per_1k_total_tokens=(
                    self.claim_max_usd_per_1k_total_tokens
                ),
            )
            if estimated_cost is None:
                raise BlockedJob("CLAIM_EXTRACTION_COST_MODEL_MISSING")
            payload["estimated_cost_usd"] = estimated_cost
            payload["max_output_tokens"] = self.claim_client.max_output_tokens
            total_tokens += window.estimated_input_tokens
            jobs.append(
                {
                    "id": deterministic_followup_job_id(
                        "CLAIM_EXTRACT_WINDOW",
                        content.content_id,
                        window.input_sha256,
                    ),
                    "content_id": content.content_id,
                    "job_type": "CLAIM_EXTRACT_WINDOW",
                    "state": "QUEUED",
                    "payload": payload,
                    "last_error": "",
                }
            )
        created = self.store.enqueue_jobs_bulk(jobs)
        self.store.update_content_status(
            content.content_id,
            "CLAIM_EXTRACTION_QUEUED",
            {
                "claim_window_count": len(windows),
                "claim_window_new_jobs": created,
                "claim_window_blocked_jobs": 0,
                "claim_window_estimated_input_tokens": total_tokens,
                "claim_window_schema_version": "claim-window-v2",
                "claim_prompt_version": self.claim_client.prompt_version,
            },
        )

    def _claim_runtime_blocker(self) -> str | None:
        if self.claim_client is None:
            return "CLAIM_EXTRACTION_CREDENTIAL_MISSING"
        if self.claim_max_usd_per_1k_total_tokens is None:
            return "CLAIM_EXTRACTION_COST_MODEL_MISSING"
        if self._claim_probe is None:
            self._claim_probe = self.claim_client.probe()
        if not self._claim_probe.healthy:
            reason = self._claim_probe.reason.replace(" ", "_")[:180]
            return f"CLAIM_EXTRACTION_CANARY_FAILED:{reason}"
        return None

    def extract_claim_window(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        blocker = self._claim_runtime_blocker()
        if blocker:
            raise BlockedJob(blocker)
        expected_hash = str(job.payload.get("input_sha256") or "").strip()
        if not expected_hash:
            raise BlockedJob("CLAIM_WINDOW_HASH_MISSING")
        rows = self.store.canonical_segments(content.content_id)
        windows = build_claim_windows(
            [canonical_segment_from_row(row) for row in rows]
        )
        matches = [window for window in windows if window.input_sha256 == expected_hash]
        if len(matches) != 1:
            raise BlockedJob("CLAIM_WINDOW_SOURCE_DRIFT")
        window = matches[0]
        payload_indices = tuple(
            int(value) for value in job.payload.get("segment_indices") or []
        )
        if payload_indices != window.segment_indices:
            raise BlockedJob("CLAIM_WINDOW_SEGMENT_DRIFT")
        try:
            result = self.claim_client.extract(
                window_text=window.text,
                allowed_segment_indices=window.segment_indices,
            )
        except RuntimeError as exc:
            message = str(exc)
            if "HTTP_429" in message or "HTTP_503" in message or "timed out" in message:
                raise RetryableJob(
                    f"CLAIM_PROVIDER_TRANSIENT:{message[:160]}",
                    300,
                ) from exc
            raise BlockedJob(f"CLAIM_PROVIDER_BLOCKED:{message[:180]}") from exc
        except ValueError as exc:
            raise BlockedJob(f"CLAIM_RESPONSE_INVALID:{str(exc)[:180]}") from exc

        segment_id_by_index = {
            int(row["segment_index"]): str(row["id"]) for row in rows
        }
        claim_rows = []
        for claim in result.claims:
            claim_id = deterministic_claim_id(
                content_id=content.content_id,
                window_sha256=window.input_sha256,
                prompt_version=self.claim_client.prompt_version,
                model=self.claim_client.model,
                claim=claim,
            )
            segment_ids = [
                segment_id_by_index[index]
                for index in claim.source_segment_indices
                if index in segment_id_by_index
            ]
            if len(segment_ids) != len(claim.source_segment_indices):
                raise BlockedJob("CLAIM_RESPONSE_SEGMENT_MAPPING_FAILED")
            statement_date = str(
                job.payload.get("statement_date") or ""
            ).strip() or None
            try:
                contract = validate_atomic_claim(
                    claim_id=claim_id,
                    content_id=content.content_id,
                    normalized_claim=claim.normalized_claim,
                    claim_type=claim.claim_type,
                    statement_date=statement_date,
                    check_worthy=claim.check_worthy,
                    source_segment_ids=tuple(segment_ids),
                    metadata={
                        "speaker_label": claim.speaker,
                        "numeric_sensitive": claim.numeric_sensitive,
                        "window_sha256": window.input_sha256,
                        "source_segment_indices": list(
                            claim.source_segment_indices
                        ),
                        "request_id": result.request_id,
                    },
                )
            except ValueError as exc:
                raise BlockedJob(
                    f"CLAIM_CONTRACT_INVALID:{str(exc)[:140]}"
                ) from exc
            claim_rows.append(
                {
                    "id": contract.claim_id,
                    "content_id": content.content_id,
                    "normalized_claim": contract.normalized_claim,
                    "claim_type": contract.claim_type.value,
                    "temporal_scope": {
                        "statement_date": contract.temporal_scope.statement_date,
                        "source_timestamp": claim.source_timestamp,
                        "window_start_ms": window.start_ms,
                        "window_end_ms": window.end_ms,
                    },
                    "check_worthy": contract.check_worthy,
                    "extraction_model": self.claim_client.model,
                    "extraction_version": self.claim_client.prompt_version,
                    "metadata": contract.metadata,
                    "segment_ids": list(contract.source_segment_ids),
                }
            )
        inserted = self.store.insert_atomic_claims(claim_rows)
        if inserted != len(claim_rows):
            raise BlockedJob("CLAIM_REPLAY_CONFLICT")
        estimated = float(job.payload.get("estimated_cost_usd") or 0.0)
        observed = (
            result.observed_cost_usd
            if result.observed_cost_usd is not None
            else estimated
        )
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id="omniroute",
            model_id=self.claim_client.model,
            operation="CLAIM_EXTRACT",
            request_id=result.request_id,
            input_bytes=len(window.text.encode()),
            input_seconds=None,
            estimated_cost_usd=max(observed, 0.0),
            status="SUCCESS",
            receipt={
                "prompt_version": self.claim_client.prompt_version,
                "window_sha256": window.input_sha256,
                "claims_returned": len(result.claims),
                "claims_inserted": inserted,
                "latency_seconds": round(result.latency_seconds, 3),
                "usage": result.usage,
            },
            request_key=window.input_sha256,
        )
        self.store.update_content_status(
            content.content_id,
            "CLAIM_EXTRACTION_IN_PROGRESS",
            {
                "atomic_claim_count": self.store.claim_count(content.content_id),
                "claim_last_window_sha256": window.input_sha256,
            },
        )

    def fetch_evidence_url(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        if self.evidence_fetcher is None:
            raise BlockedJob("EVIDENCE_FETCHER_NOT_CONFIGURED")
        source_id = str(job.payload.get("evidence_source_id") or "").strip()
        url = str(job.payload.get("url") or "").strip()
        claim_id = str(job.payload.get("claim_id") or "").strip()
        retrieval_version = str(
            job.payload.get("retrieval_version") or "evidence-url-v1"
        ).strip()
        retrieval_method = str(
            job.payload.get("retrieval_method") or "EXPLICIT_OFFICIAL_URL"
        ).strip()
        relation_candidate = str(
            job.payload.get("relation_candidate") or "UNKNOWN"
        ).strip()
        if not source_id or not url or not claim_id:
            raise BlockedJob("EVIDENCE_FETCH_PAYLOAD_INCOMPLETE")
        try:
            source = get_evidence_source(
                self.evidence_fetcher.registry, source_id
            )
        except KeyError as exc:
            raise BlockedJob("EVIDENCE_SOURCE_NOT_REGISTERED") from exc
        try:
            result = self.evidence_fetcher.fetch(source_id, url)
        except EvidenceRateLimited as exc:
            raise DeferredJob(
                f"EVIDENCE_RATE_LIMIT:{source_id}",
                max(int(math.ceil(exc.retry_after_seconds)), 1),
            ) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = int(retry_after) if retry_after else 300
                except ValueError:
                    delay = 300
                raise DeferredJob(
                    f"EVIDENCE_HTTP_429:{source_id}", delay
                ) from exc
            if 500 <= exc.code < 600:
                raise RetryableJob(
                    f"EVIDENCE_HTTP_{exc.code}:{source_id}", 300
                ) from exc
            raise BlockedJob(
                f"EVIDENCE_HTTP_{exc.code}:{source_id}"
            ) from exc
        except (EvidencePolicyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_POLICY:{str(exc)[:180]}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise RetryableJob(
                f"EVIDENCE_NETWORK:{type(exc).__name__}", 300
            ) from exc
        self._persist_evidence_result(
            job=job,
            content=content,
            source_id=source_id,
            source=source,
            result=result,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
        )

    def query_official_evidence(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        if self.evidence_fetcher is None:
            raise BlockedJob("EVIDENCE_FETCHER_NOT_CONFIGURED")
        source_id = str(job.payload.get("evidence_source_id") or "").strip()
        query_kind = str(job.payload.get("query_kind") or "").strip()
        claim_id = str(job.payload.get("claim_id") or "").strip()
        params = job.payload.get("query_params")
        if not source_id or not query_kind or not claim_id:
            raise BlockedJob("EVIDENCE_QUERY_PAYLOAD_INCOMPLETE")
        if not isinstance(params, dict):
            raise BlockedJob("EVIDENCE_QUERY_PARAMS_INVALID")
        try:
            compiled = compile_official_query(source_id, query_kind, params)
            source = get_evidence_source(
                self.evidence_fetcher.registry, source_id
            )
        except (KeyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_QUERY_POLICY:{str(exc)[:180]}"
            ) from exc
        try:
            result = self.evidence_fetcher.request(
                compiled.source_id,
                compiled.url,
                method=compiled.method,
                body=compiled.body,
                content_type=compiled.content_type,
            )
        except EvidenceRateLimited as exc:
            raise DeferredJob(
                f"EVIDENCE_RATE_LIMIT:{source_id}",
                max(int(math.ceil(exc.retry_after_seconds)), 1),
            ) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = int(retry_after) if retry_after else 300
                except ValueError:
                    delay = 300
                raise DeferredJob(
                    f"EVIDENCE_HTTP_429:{source_id}", delay
                ) from exc
            if 500 <= exc.code < 600:
                raise RetryableJob(
                    f"EVIDENCE_HTTP_{exc.code}:{source_id}", 300
                ) from exc
            raise BlockedJob(
                f"EVIDENCE_HTTP_{exc.code}:{source_id}"
            ) from exc
        except (EvidencePolicyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_POLICY:{str(exc)[:180]}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise RetryableJob(
                f"EVIDENCE_NETWORK:{type(exc).__name__}", 300
            ) from exc
        self._persist_evidence_result(
            job=job,
            content=content,
            source_id=source_id,
            source=source,
            result=result,
            retrieval_method=compiled.retrieval_method,
            retrieval_version=compiled.retrieval_version,
            relation_candidate=str(
                job.payload.get("relation_candidate") or "UNKNOWN"
            ).strip(),
        )

    def _persist_evidence_result(
        self,
        *,
        job: ProcessingJob,
        content: ContentRecord,
        source_id: str,
        source: dict[str, Any],
        result,
        retrieval_method: str,
        retrieval_version: str,
        relation_candidate: str,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        if not claim_id:
            raise BlockedJob("EVIDENCE_CLAIM_ID_MISSING")
        receipt = result.receipt
        evidence_id = deterministic_evidence_id(
            source_id,
            receipt.canonical_url,
            receipt.content_sha256,
        )
        rights_status = str(
            job.payload.get("rights_status")
            or source.get("rights_status")
            or "UNKNOWN"
        )
        self.store.upsert_evidence(
            evidence_id=evidence_id,
            canonical_url=receipt.canonical_url,
            publisher=receipt.publisher,
            source_type=receipt.evidence_class,
            publication_date=(
                str(job.payload.get("publication_date") or "").strip()
                or None
            ),
            fetched_at=receipt.fetched_at,
            content_sha256=receipt.content_sha256,
            excerpt=None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip()
                or None
            ),
            independence_group=(
                str(job.payload.get("independence_group") or source_id).strip()
                or source_id
            ),
            rights_status=rights_status,
            metadata={
                "evidence_source_id": source_id,
                "authoritative": receipt.authoritative,
                "http_status": receipt.http_status,
                "content_type": receipt.content_type,
                "response_bytes": receipt.response_bytes,
                "final_url": receipt.final_url,
                "from_cache": receipt.from_cache,
                "private_body": "CONTENT_ADDRESSED",
                "etag_present": bool(receipt.etag),
                "last_modified": receipt.last_modified,
            },
        )
        self.store.link_claim_evidence(
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
            status="RETRIEVED",
            score=None,
            statement_cutoff=(
                str(job.payload.get("statement_cutoff") or "").strip()
                or None
            ),
            metadata={
                "source_id": source_id,
                "content_sha256": receipt.content_sha256,
                "authoritative": receipt.authoritative,
            },
        )
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id=source_id,
            model_id=None,
            operation="EVIDENCE_FETCH",
            request_id=None,
            input_bytes=None,
            input_seconds=None,
            estimated_cost_usd=0.0,
            status="SUCCESS",
            receipt={
                "evidence_id": evidence_id,
                "content_sha256": receipt.content_sha256,
                "response_bytes": receipt.response_bytes,
                "content_type": receipt.content_type,
                "from_cache": receipt.from_cache,
                "authoritative": receipt.authoritative,
                "retrieval_method": retrieval_method,
                "retrieval_version": retrieval_version,
            },
            request_key=f"{source_id}:{receipt.content_sha256}",
        )

    def persist_evidence_observation(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        evidence_id = str(job.payload.get("evidence_id") or "").strip()
        observation_type = str(
            job.payload.get("observation_type") or ""
        ).strip()
        extraction_method = str(
            job.payload.get("extraction_method") or ""
        ).strip()
        extraction_version = str(
            job.payload.get("extraction_version") or ""
        ).strip()
        if not evidence_id or not observation_type:
            raise BlockedJob("EVIDENCE_OBSERVATION_IDENTITY_MISSING")
        if not extraction_method or not extraction_version:
            raise BlockedJob("EVIDENCE_OBSERVATION_EXTRACTOR_MISSING")
        value_numeric = job.payload.get("value_numeric")
        value_text = job.payload.get("value_text")
        if value_numeric is None and value_text is None:
            raise BlockedJob("EVIDENCE_OBSERVATION_VALUE_MISSING")
        try:
            numeric = None if value_numeric is None else float(value_numeric)
        except (TypeError, ValueError) as exc:
            raise BlockedJob("EVIDENCE_OBSERVATION_NUMERIC_INVALID") from exc
        dimensions = job.payload.get("dimensions") or {}
        source_pointer = job.payload.get("source_pointer") or {}
        if not isinstance(dimensions, dict) or not isinstance(source_pointer, dict):
            raise BlockedJob("EVIDENCE_OBSERVATION_POINTER_INVALID")
        observation_id = deterministic_evidence_observation_id(
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=str(job.payload.get("metric") or "").strip() or None,
            value_numeric=numeric,
            value_text=(
                str(value_text).strip() if value_text is not None else None
            ),
            unit=str(job.payload.get("unit") or "").strip() or None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip() or None
            ),
            dimensions=dimensions,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=source_pointer,
        )
        self.store.insert_evidence_observation(
            observation_id=observation_id,
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=str(job.payload.get("metric") or "").strip() or None,
            value_numeric=numeric,
            value_text=(
                str(value_text).strip() if value_text is not None else None
            ),
            unit=str(job.payload.get("unit") or "").strip() or None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip() or None
            ),
            dimensions=dimensions,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=source_pointer,
            # Extraction and approval are deliberately separate actions.
            status="CANDIDATE",
            metadata={
                "job_id": job.job_id,
                "content_id": content.content_id,
            },
        )

    def verify_claim(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        verification_kind = str(
            job.payload.get("verification_kind") or ""
        ).strip()
        verification_rule = job.payload.get("verification_rule")
        if not claim_id or not verification_kind:
            raise BlockedJob("VERIFICATION_PAYLOAD_INCOMPLETE")
        if not isinstance(verification_rule, dict):
            raise BlockedJob("VERIFICATION_RULE_INVALID")
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("VERIFICATION_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("VERIFICATION_CONTENT_MISMATCH")
        canonical_statement_date = str(
            context.get("statement_date") or ""
        ).strip()
        payload_statement_date = str(
            job.payload.get("statement_date") or ""
        ).strip()
        if (
            canonical_statement_date
            and payload_statement_date
            and payload_statement_date != canonical_statement_date
        ):
            raise BlockedJob("VERIFICATION_STATEMENT_DATE_MISMATCH")
        statement_date = canonical_statement_date or payload_statement_date
        if not statement_date:
            raise BlockedJob("VERIFICATION_STATEMENT_DATE_MISSING")
        evidence_rows = self.store.approved_verification_evidence(claim_id)
        source_evidence = tuple(
            evidence_item_from_row(row, self.source_intelligence_contract)
            for row in evidence_rows
        )
        relations = tuple(
            SourceRelation(**row)
            for row in self.store.source_intelligence_relations()
        )
        claim_requirements: dict[str, Any] = {}
        temporal_scope = context.get("temporal_scope")
        if isinstance(temporal_scope, dict):
            claim_requirements.update(temporal_scope)
        claim_metadata = context.get("metadata")
        if isinstance(claim_metadata, dict):
            configured_requirements = claim_metadata.get("source_requirements")
            if isinstance(configured_requirements, dict):
                claim_requirements.update(configured_requirements)
        claim_requirements.update(verification_rule)
        source_assessment = assess_evidence_set(
            target_type="ATOMIC_CLAIM",
            target_id=claim_id,
            claim_type=str(context.get("claim_type") or ""),
            statement_date=statement_date,
            claim_requirements=claim_requirements,
            evidence=source_evidence,
            contract=self.source_intelligence_contract,
            relations=relations,
        )
        self.store.insert_evidence_set_assessment(
            assessment_id=source_assessment.id,
            atomic_claim_id=claim_id,
            claim_candidate_id=None,
            requirement_profile_id=source_assessment.requirement_profile_id,
            requirement_profile_version=source_assessment.requirement_profile_version,
            input_fingerprint=source_assessment.input_fingerprint,
            assessment=source_assessment.status,
            qualifying_evidence_ids=list(source_assessment.qualifying_evidence_ids),
            rejected_evidence=list(source_assessment.rejected_evidence),
            satisfied_rules=list(source_assessment.satisfied_rules),
            missing_rules=list(source_assessment.missing_rules),
            conflict_groups=list(source_assessment.conflict_groups),
            coverage_need_candidates=[
                asdict(item) for item in source_assessment.coverage_need_candidates
            ],
            rationale_codes=list(source_assessment.rationale_codes),
            assessment_version=source_assessment.assessment_version,
        )
        collection_ids = self.store.coverage_collection_ids_for_claim(claim_id)
        coverage_specs = materialize_coverage_need_specs(
            target_type="ATOMIC_CLAIM",
            target_id=claim_id,
            source_intelligence_assessment_id=source_assessment.id,
            candidates=[
                asdict(item) for item in source_assessment.coverage_need_candidates
            ],
            collection_ids=tuple(collection_ids),
        )
        for coverage_spec in coverage_specs:
            self.store.upsert_coverage_need(**coverage_need_params(coverage_spec))
        if source_assessment.status != "SUFFICIENT_FOR_RULE":
            raise BlockedJob(
                f"SOURCE_INTELLIGENCE_{source_assessment.status}:"
                f"{source_assessment.id}"
            )
        suitable_ids = set(source_assessment.qualifying_evidence_ids)
        evidence = tuple(
            VerificationEvidence(
                evidence_id=str(row["evidence_id"]),
                observation_id=str(row.get("observation_id") or "") or None,
                publication_date=str(row["publication_date"]),
                metric=(
                    str(row.get("metric") or "").strip() or None
                ),
                value_numeric=(
                    None
                    if row.get("value_numeric") is None
                    else float(row["value_numeric"])
                ),
                value_text=(
                    str(row.get("value_text") or "").strip() or None
                ),
                unit=str(row.get("unit") or "").strip() or None,
                reference_period=(
                    str(row.get("reference_period") or "").strip() or None
                ),
                suitable=str(row["evidence_id"]) in suitable_ids,
                authoritative=bool(row.get("authoritative")),
                status=str(row.get("status") or ""),
                metadata=(
                    row.get("metadata")
                    if isinstance(row.get("metadata"), dict)
                    else {}
                ),
            )
            for row in evidence_rows
        )
        request = VerificationRequest(
            claim_id=claim_id,
            statement_date=statement_date,
            kind=verification_kind,
            rule=verification_rule,
            source_intelligence_status=source_assessment.status,
            source_intelligence_assessment_id=source_assessment.id,
        )
        try:
            result = verify(request, evidence)
        except (KeyError, TypeError, ValueError) as exc:
            raise BlockedJob(
                f"VERIFICATION_RULE_REFUSED:{str(exc)[:180]}"
            ) from exc
        fingerprint = verification_input_fingerprint(request, evidence)
        run_id = deterministic_verification_run_id(request, evidence)
        self.store.insert_verification_run(
            run_id=run_id,
            claim_id=claim_id,
            source_intelligence_assessment_id=source_assessment.id,
            verification_kind=verification_kind,
            verification_version=result.verification_version,
            verification_rule=verification_rule,
            input_fingerprint=fingerprint,
            statement_cutoff=result.statement_cutoff,
            assessment=result.assessment.value,
            evidence_ids=list(result.evidence_ids),
            observation_ids=sorted(
                {
                    item.observation_id
                    for item in evidence
                    if (
                        item.observation_id is not None
                        and item.evidence_id in result.evidence_ids
                    )
                }
            ),
            blockers=list(result.blockers),
            rationale_codes=list(result.rationale_codes),
            result=result.result,
        )
        provisional = finding_draft_from_verification(
            verification_run_id=run_id,
            input_fingerprint=fingerprint,
            result=result,
        )
        previous = self.store.latest_finding_id(
            claim_id,
            exclude_finding_id=provisional.finding_id,
        )
        draft = finding_draft_from_verification(
            verification_run_id=run_id,
            input_fingerprint=fingerprint,
            result=result,
            supersedes_id=previous,
        )
        self.store.insert_finding_draft(asdict(draft))
        trigger_id = str(
            job.payload.get("reanalysis_trigger_id") or ""
        ).strip()
        if trigger_id:
            self.store.advance_reanalysis_trigger(
                trigger_id,
                status="PROCESSED",
                enqueued_job_id=job.job_id,
            )

    @staticmethod
    def _structured_relation_input(
        raw: object,
    ) -> StructuredClaimRelationInput:
        if not isinstance(raw, dict):
            raise BlockedJob("RELATION_INPUT_INVALID")
        try:
            return StructuredClaimRelationInput(
                claim_id=str(raw["claim_id"]).strip(),
                statement_date=str(raw["statement_date"]).strip(),
                proposition_key=(
                    str(raw.get("proposition_key") or "").strip() or None
                ),
                topic_key=str(raw.get("topic_key") or "").strip() or None,
                stance=str(raw.get("stance") or "").strip() or None,
                scope_start=str(raw.get("scope_start") or "").strip() or None,
                scope_end=str(raw.get("scope_end") or "").strip() or None,
                asserts_past_continuity=bool(
                    raw.get("asserts_past_continuity", False)
                ),
            )
        except KeyError as exc:
            raise BlockedJob("RELATION_INPUT_INCOMPLETE") from exc

    def classify_claim_relation_job(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        prior = self._structured_relation_input(job.payload.get("prior"))
        later = self._structured_relation_input(job.payload.get("later"))
        try:
            prior_context = self.store.claim_context(prior.claim_id)
            later_context = self.store.claim_context(later.claim_id)
        except KeyError as exc:
            raise BlockedJob("RELATION_CLAIM_NOT_FOUND") from exc
        if content.content_id not in {
            prior_context["content_id"],
            later_context["content_id"],
        }:
            raise BlockedJob("RELATION_JOB_CONTENT_MISMATCH")
        try:
            result = classify_relation(prior, later)
        except ValueError as exc:
            raise BlockedJob(f"RELATION_REFUSED:{str(exc)[:180]}") from exc
        if result.relation_type == RelationCandidateType.NO_RELATION:
            return
        candidate_id = deterministic_relation_candidate_id(result)
        self.store.insert_relation_candidate(
            {
                "id": candidate_id,
                "subject_claim_id": result.subject_claim_id,
                "object_claim_id": result.object_claim_id,
                "relation_type": result.relation_type.value,
                "relation_version": result.relation_version,
                "status": "CANDIDATE",
                "confidence": result.confidence,
                "rationale_codes": list(result.rationale_codes),
                "metadata": {"source_job_id": job.job_id},
            }
        )

    def register_reanalysis(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("REANALYSIS_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("REANALYSIS_CONTENT_MISMATCH")
        try:
            trigger = deterministic_reanalysis_trigger(
                claim_id=claim_id,
                trigger_type=str(
                    job.payload.get("trigger_type") or ""
                ).strip(),
                source_type=str(
                    job.payload.get("source_type") or ""
                ).strip(),
                source_id=str(job.payload.get("source_id") or "").strip(),
                source_hash=(
                    str(job.payload.get("source_hash") or "").strip() or None
                ),
            )
        except ValueError as exc:
            raise BlockedJob(f"REANALYSIS_TRIGGER_REFUSED:{exc}") from exc
        self.store.insert_reanalysis_trigger(
            {
                "id": trigger.trigger_id,
                "claim_id": trigger.claim_id,
                "trigger_type": trigger.trigger_type,
                "source_type": trigger.source_type,
                "source_id": trigger.source_id,
                "source_hash": trigger.source_hash,
                "metadata": {"source_job_id": job.job_id},
            }
        )
        followup_id, _ = self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="REANALYZE_CLAIM",
            payload={
                "claim_id": claim_id,
                "trigger_id": trigger.trigger_id,
                "estimated_cost_usd": 0.0,
            },
            variant=trigger.trigger_id,
        )
        self.store.advance_reanalysis_trigger(
            trigger.trigger_id,
            status="ENQUEUED",
            enqueued_job_id=followup_id,
        )

    def reanalyze_claim(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        trigger_id = str(job.payload.get("trigger_id") or "").strip()
        if not claim_id or not trigger_id:
            raise BlockedJob("REANALYSIS_PAYLOAD_INCOMPLETE")
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("REANALYSIS_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("REANALYSIS_CONTENT_MISMATCH")
        template = self.store.latest_verification_template(claim_id)
        if template is None:
            raise BlockedJob("REANALYSIS_NO_VERIFICATION_TEMPLATE")
        verification_job_id, _ = self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="VERIFY_CLAIM",
            payload={
                "claim_id": claim_id,
                "verification_kind": template["verification_kind"],
                "verification_rule": template["verification_rule"],
                "statement_date": template["statement_cutoff"],
                "reanalysis_trigger_id": trigger_id,
                "estimated_cost_usd": 0.0,
            },
            variant=trigger_id,
        )
        self.store.advance_reanalysis_trigger(
            trigger_id,
            status="ENQUEUED",
            enqueued_job_id=verification_job_id,
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

    def acquire_asr(self, job: ProcessingJob, content: ContentRecord) -> None:
        provider_id = str(job.payload.get("provider_id") or "").strip()
        route = str(job.payload.get("route") or "").strip()
        audio_url = str(job.payload.get("canonical_url") or content.canonical_url).strip()
        if provider_id != "groq-whisper-large-v3-turbo":
            raise BlockedJob(f"ASR_PROVIDER_NOT_IMPLEMENTED:{provider_id or 'missing'}")
        if route != "groq/whisper-large-v3-turbo":
            raise BlockedJob(f"ASR_ROUTE_NOT_IMPLEMENTED:{route or 'missing'}")
        if not audio_url.startswith(("https://", "http://")):
            raise BlockedJob("ASR_AUDIO_URL_INVALID")
        if not self.groq_api_key:
            self.store.update_content_status(
                content.content_id,
                "TRANSCRIPT_ASR_BLOCKED",
                {"runtime_blocker": "GROQ_API_KEY_MISSING"},
            )
            raise BlockedJob("GROQ_API_KEY_MISSING")
        if not self.store.renew(
            job.job_id, self.worker_id, lease_seconds=max(self.lease_seconds, 600)
        ):
            raise RetryableJob("LEASE_LOST_BEFORE_ASR", 0)

        transcriber = GroqUrlTranscriber(self.groq_api_key)
        try:
            result = transcriber.transcribe_url(audio_url)
        except AsrRateLimited as exc:
            raise RetryableJob(
                "GROQ_RATE_LIMITED", exc.retry_after_seconds
            ) from exc
        except AsrTransientError as exc:
            raise RetryableJob(str(exc), 300) from exc
        except AsrAccessDenied as exc:
            self.store.update_content_status(
                content.content_id,
                "TRANSCRIPT_ASR_BLOCKED",
                {"runtime_blocker": str(exc)},
            )
            raise BlockedJob(str(exc)) from exc
        except AsrRequestRejected as exc:
            self.store.record_receipt(
                job_id=job.job_id,
                content_id=content.content_id,
                provider_id=provider_id,
                model_id="whisper-large-v3-turbo",
                operation="AUDIO_TRANSCRIPTION",
                request_id=None,
                input_bytes=None,
                input_seconds=(
                    content.duration_ms / 1000.0 if content.duration_ms else None
                ),
                estimated_cost_usd=0.0,
                status="REJECTED",
                receipt={"error": str(exc)},
                request_key=f"attempt:{job.attempt}",
            )
            raise BlockedJob(str(exc)) from exc

        variant_id, inserted = self.store.insert_transcript_variant(
            content_id=content.content_id,
            provider_id=provider_id,
            source_kind="REMOTE_ASR",
            language=result.language,
            raw_text=result.text,
            raw_text_sha256=result.text_sha256,
            is_platform_caption=False,
            is_manual_caption=False,
            metadata={
                "model_id": result.model_id,
                "request_id": result.request_id,
                "audio_transport": "REMOTE_URL",
            },
        )
        if inserted:
            self.store.insert_transcript_segments(
                variant_id=variant_id,
                segments=[
                    {
                        "segment_index": segment.segment_index,
                        "start_ms": segment.start_ms,
                        "end_ms": segment.end_ms,
                        "text": segment.text,
                        "metadata": {},
                    }
                    for segment in result.segments
                ],
            )
        estimated_cost = float(job.payload.get("estimated_cost_usd") or 0.0)
        receipt = {
            "variant_id": variant_id,
            "text_sha256": result.text_sha256,
            "segment_count": len(result.segments),
            "audio_transport": "REMOTE_URL",
            "source_audio_persisted": False,
        }
        self.private_store.persist_asr_response(
            content_id=content.content_id,
            variant_id=variant_id,
            response=result.raw_response,
            receipt=receipt,
        )
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id=provider_id,
            model_id=result.model_id,
            operation="AUDIO_TRANSCRIPTION",
            request_id=result.request_id,
            input_bytes=None,
            input_seconds=result.duration_seconds,
            estimated_cost_usd=estimated_cost,
            status="SUCCESS",
            receipt=receipt,
            request_key=result.request_id or result.text_sha256,
        )
        self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="TRANSCRIPT_CANONICALIZE",
            payload={
                "source_id": content.source_id,
                "variant_id": variant_id,
                "estimated_cost_usd": 0.0,
            },
            variant=variant_id,
        )
        self.store.update_content_status(
            content.content_id,
            "TRANSCRIPT_CANDIDATE_READY",
            {
                "transcript_variant_id": variant_id,
                "asr_provider": provider_id,
                "asr_model": result.model_id,
            },
        )

    def process(self, job: ProcessingJob) -> None:
        content = self.store.content(job.content_id)
        self._ensure_budget(job, content)
        if job.job_type == "TRANSCRIPT_RESOLVE_PLATFORM":
            self.resolve_platform(job, content)
            return
        if job.job_type == "TRANSCRIPT_ACQUIRE_CAPTION":
            self.acquire_caption(job, content)
            return
        if job.job_type == "TRANSCRIPT_CANONICALIZE":
            self.canonicalize(job, content)
            return
        if job.job_type == "TRANSCRIPT_ACQUIRE_ASR":
            self.acquire_asr(job, content)
            return
        if job.job_type in {"CLAIM_PREPARE", "CLAIM_EXTRACT"}:
            self.prepare_claim_windows(job, content)
            return
        if job.job_type == "CLAIM_EXTRACT_WINDOW":
            self.extract_claim_window(job, content)
            return
        if job.job_type == "EVIDENCE_FETCH_URL":
            self.fetch_evidence_url(job, content)
            return
        if job.job_type == "EVIDENCE_QUERY_OFFICIAL":
            self.query_official_evidence(job, content)
            return
        if job.job_type == "EVIDENCE_OBSERVE":
            self.persist_evidence_observation(job, content)
            return
        if job.job_type == "VERIFY_CLAIM":
            self.verify_claim(job, content)
            return
        if job.job_type == "CLASSIFY_CLAIM_RELATION":
            self.classify_claim_relation_job(job, content)
            return
        if job.job_type == "REGISTER_REANALYSIS":
            self.register_reanalysis(job, content)
            return
        if job.job_type == "REANALYZE_CLAIM":
            self.reanalyze_claim(job, content)
            return
        raise BlockedJob(f"NO_HANDLER:{job.job_type}")

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

    claim_rate_raw = os.environ.get(
        "DICHIARAZIONI_PUBBLICHE_CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS"
    )
    claim_rate = float(claim_rate_raw) if claim_rate_raw not in {None, ""} else None
    omni_key = os.environ.get("OMNIROUTE_API_KEY", "").strip()
    claim_client = (
        OmniRouteClaimClient(
            api_key=omni_key,
            base_url=os.environ.get(
                "DICHIARAZIONI_PUBBLICHE_OMNIROUTE_BASE_URL",
                "http://127.0.0.1:20128",
            ),
        )
        if omni_key
        else None
    )

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
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            claim_client=claim_client,
            claim_max_usd_per_1k_total_tokens=claim_rate,
            evidence_fetcher=SafeEvidenceFetcher(),
        )
        print(json.dumps(asdict(worker.run(args.max_jobs)), ensure_ascii=False, indent=2))
    finally:
        lock.release()


if __name__ == "__main__":
    main()
