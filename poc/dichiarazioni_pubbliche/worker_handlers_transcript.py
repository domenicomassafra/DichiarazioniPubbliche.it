from __future__ import annotations

from dichiarazioni_pubbliche.asr_router import ProviderState, plan_asr
from dichiarazioni_pubbliche.youtube_caption_acquisition import CaptionAcquisitionHandler
from dichiarazioni_pubbliche.local_asr import PROVIDER_ID as LOCAL_PROVIDER_ID
from dichiarazioni_pubbliche.local_asr import ROUTE as LOCAL_ROUTE
from dichiarazioni_pubbliche.faster_whisper_local import PROVIDER_ID as FASTER_PROVIDER_ID
from dichiarazioni_pubbliche.faster_whisper_local import ROUTE as FASTER_ROUTE
from dichiarazioni_pubbliche.faster_whisper_rights import require_faster_whisper_media_rights
from dichiarazioni_pubbliche.platform_transcript import (
    CaptionProbe,
    PlatformAccessRestricted,
    VideoCandidate,
)
from dichiarazioni_pubbliche.queue_runtime import ContentRecord, ProcessingJob
from dichiarazioni_pubbliche.remote_asr import (
    AsrAccessDenied,
    AsrRateLimited,
    AsrRequestRejected,
    AsrTransientError,
    GroqUrlTranscriber,
)
from dichiarazioni_pubbliche.transcript_contract import (
    TranscriptCandidate,
    reconcile_candidates,
)
from dichiarazioni_pubbliche.worker_errors import BlockedJob, RetryableJob
from dichiarazioni_pubbliche.youtube_caption_receipts import (
    record_caption_receipt as _record_caption_receipt,
)


class TranscriptAsrJobHandlers(CaptionAcquisitionHandler):
    def _require_current_ingestion_relevance(self, content: ContentRecord) -> None:
        try:
            self.store.require_current_ingestion_relevance(
                content_ref=content.content_id,
                canonical_url=content.canonical_url,
            )
        except RuntimeError as exc:
            raise BlockedJob(str(exc)) from exc

    def triage_content(self, job: ProcessingJob, content: ContentRecord) -> None:
        """Complete metadata-only discovery without inventing downstream work.

        ``DISCOVERY_ONLY`` sources are intentionally not transcript/claim inputs.
        The scheduler still emits a durable CONTENT_TRIAGE job so discovery has a
        replayable queue receipt; this handler closes that receipt while keeping
        the content in DISCOVERED state and performing zero network/provider work.
        """
        action = str(job.payload.get("ingest_action") or "").strip()
        if action != "DISCOVERY_ONLY":
            raise BlockedJob(
                f"CONTENT_TRIAGE_ACTION_INVALID:{action or 'MISSING'}"
            )
        self.store.update_content_status(
            content.content_id,
            content.processing_status or "DISCOVERED",
            {
                "ingest_action": "DISCOVERY_ONLY",
                "triage_status": "METADATA_ONLY_COMPLETE",
            },
        )

    def _enqueue_asr(self, content: ContentRecord, *, reason: str) -> None:
        self._require_current_ingestion_relevance(content)
        if not content.duration_ms or content.duration_ms <= 0:
            raise BlockedJob("ASR_DURATION_UNKNOWN")
        duration_seconds = max(int(round(content.duration_ms / 1000)), 1)
        try:
            # A URL-only generic dispatch cannot carry the operator-reviewed
            # local WAV rights/hash/model receipt. Keep those routes manual
            # even if a later model canary marks the provider proven.
            routing = plan_asr(
                duration_seconds=duration_seconds,
                states={
                    LOCAL_PROVIDER_ID: ProviderState(LOCAL_PROVIDER_ID, enabled=False),
                    FASTER_PROVIDER_ID: ProviderState(FASTER_PROVIDER_ID, enabled=False),
                },
            )
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
        self, job: ProcessingJob, content: ContentRecord, candidate: VideoCandidate
    ) -> None:
        return CaptionAcquisitionHandler._probe_and_enqueue_caption(self, job, content, candidate)

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
            self._require_current_ingestion_relevance(content)
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
            self._require_current_ingestion_relevance(content)
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
        """Retain the registered handler on its family while sharing the capture seam."""
        return CaptionAcquisitionHandler.acquire_caption(self, job, content)

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
    def acquire_asr(self, job: ProcessingJob, content: ContentRecord) -> None:
        provider_id = str(job.payload.get("provider_id") or "").strip()
        route = str(job.payload.get("route") or "").strip()
        if provider_id == LOCAL_PROVIDER_ID and route == LOCAL_ROUTE:
            self._acquire_local_asr(job, content, transcriber=self.local_asr, provider_id=provider_id)
            return
        if provider_id == FASTER_PROVIDER_ID and route == FASTER_ROUTE:
            self._acquire_local_asr(job, content, transcriber=self.faster_whisper_asr, provider_id=provider_id)
            return
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

        self._require_current_ingestion_relevance(content)
        self._reserve_paid_dispatch(job, content)
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

        self._require_current_ingestion_relevance(content)
        self._persist_asr_result(
            job, content, result, provider_id=provider_id,
            source_kind="REMOTE_ASR", audio_transport="REMOTE_URL",
            input_sha256=None, model_sha256=None, rights_receipt_id=None,
            input_bytes=None,
        )

    def _acquire_local_asr(self, job: ProcessingJob, content: ContentRecord,
                           *, transcriber, provider_id: str) -> None:
        payload = job.payload
        # An operator explicitly enqueues a bounded, rights-cleared local WAV;
        # discovery and generic fallback routing never create this job.
        if transcriber is None:
            raise BlockedJob("LOCAL_ASR_RUNTIME_NOT_CONFIGURED")
        try:
            requested_duration = float(payload.get("duration_seconds"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise BlockedJob("LOCAL_ASR_CONTENT_DURATION_MISMATCH") from exc
        if (not content.duration_ms or content.duration_ms <= 0
                or content.duration_ms > 30_000
                or not 0 < requested_duration <= 30.0
                or abs(content.duration_ms / 1000.0 - requested_duration) > 0.25):
            raise BlockedJob("LOCAL_ASR_CONTENT_DURATION_MISMATCH")
        if str(payload.get("canonical_url") or "") != content.canonical_url:
            raise BlockedJob("LOCAL_ASR_CONTENT_URL_MISMATCH")
        if not self.store.renew(
            job.job_id, self.worker_id, lease_seconds=max(self.lease_seconds, 180)
        ):
            raise RetryableJob("LEASE_LOST_BEFORE_LOCAL_ASR", 0)
        self._require_current_ingestion_relevance(content)
        if provider_id == FASTER_PROVIDER_ID:
            self._require_faster_whisper_rights(content, payload)
        try:
            result = transcriber.transcribe(
                audio_path=payload.get("local_audio_path"),
                input_sha256=payload.get("audio_sha256"),
                rights_basis=payload.get("rights_basis"),
                rights_receipt_id=payload.get("rights_receipt_id"),
                authorization=payload.get("local_audio_authorized"),
                consent_confirmed=payload.get("consent_confirmed"),
                duration_seconds=payload.get("duration_seconds"),
                language=payload.get("language", "it"),
            )
        except AsrTransientError as exc:
            raise RetryableJob(str(exc), 60) from exc
        except AsrRequestRejected as exc:
            self.store.update_content_status(
                content.content_id, "TRANSCRIPT_ASR_BLOCKED",
                {"runtime_blocker": str(exc)},
            )
            raise BlockedJob(str(exc)) from exc
        self._require_current_ingestion_relevance(content)
        if provider_id == FASTER_PROVIDER_ID:
            self._require_faster_whisper_rights(content, payload)
        audio_sha = str(payload["audio_sha256"])
        self._persist_asr_result(
            job, content, result, provider_id=provider_id,
            source_kind="LOCAL_ASR", audio_transport="PRIVATE_WAV",
            input_sha256=audio_sha,
            model_sha256=transcriber.model_sha256,
            rights_receipt_id=str(payload["rights_receipt_id"]),
            input_bytes=None,
        )

    def _require_faster_whisper_rights(self, content: ContentRecord, payload) -> None:
        try:
            require_faster_whisper_media_rights(
                store=self.store, content_id=content.content_id,
                canonical_url=content.canonical_url, payload=payload,
            )
        except AsrRequestRejected as exc:
            raise BlockedJob(str(exc)) from exc

    def _persist_asr_result(
        self, job: ProcessingJob, content: ContentRecord, result,
        *, provider_id: str, source_kind: str, audio_transport: str,
        input_sha256: str | None, model_sha256: str | None,
        rights_receipt_id: str | None, input_bytes: int | None,
    ) -> None:
        variant_id, inserted = self.store.insert_transcript_variant(
            content_id=content.content_id,
            provider_id=provider_id,
            source_kind=source_kind,
            language=result.language,
            raw_text=result.text,
            raw_text_sha256=result.text_sha256,
            is_platform_caption=False,
            is_manual_caption=False,
            metadata={
                "model_id": result.model_id,
                "request_id": result.request_id,
                "audio_transport": audio_transport,
                "input_audio_sha256": input_sha256,
                "model_sha256": model_sha256,
                "rights_receipt_id": rights_receipt_id,
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
            "audio_transport": audio_transport,
            "source_audio_persisted": False,
            "input_audio_sha256": input_sha256,
            "model_sha256": model_sha256,
            "rights_receipt_id": rights_receipt_id,
            "quality_gate": "UNRECONCILED_ASR_CANDIDATE",
            "publication_approved": False,
            "billing_basis": (
                "LOCAL_COMPUTE_UNMETERED" if source_kind == "LOCAL_ASR"
                else "PROVIDER_COST_ESTIMATE"
            ),
            # Keep the legacy nested classification, and make the canonical
            # monetary ledger and independent local energy uncertainty explicit.
            "ledger_billing_basis": "ESTIMATED_ONLY",
            "local_energy_basis": "UNKNOWN" if source_kind == "LOCAL_ASR" else None,
            "local_energy_wh": None,
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
            input_bytes=input_bytes,
            input_seconds=result.duration_seconds,
            estimated_cost_usd=estimated_cost,
            billing_basis="ESTIMATED_ONLY",
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
