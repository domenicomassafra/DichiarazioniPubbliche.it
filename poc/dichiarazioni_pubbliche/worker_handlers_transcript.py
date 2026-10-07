from __future__ import annotations

from typing import Any

from dichiarazioni_pubbliche.asr_router import plan_asr
from dichiarazioni_pubbliche.platform_transcript import (
    CaptionProbe,
    PlatformAccessRestricted,
    VideoCandidate,
)
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


class TranscriptAsrJobHandlers:
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
        self._require_current_ingestion_relevance(content)
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

        self._require_current_ingestion_relevance(content)
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
        self._require_current_ingestion_relevance(content)
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

        self._require_current_ingestion_relevance(content)
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

        self._require_current_ingestion_relevance(content)
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
