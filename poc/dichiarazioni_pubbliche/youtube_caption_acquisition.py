"""Captures permission-gated public YouTube captions into private provenance records."""
from __future__ import annotations

from dichiarazioni_pubbliche.platform_transcript import CaptionProbe, PlatformAccessRestricted
from dichiarazioni_pubbliche.queue_runtime import ContentRecord, ProcessingJob
from dichiarazioni_pubbliche.worker_errors import BlockedJob, RetryableJob
from dichiarazioni_pubbliche.youtube_caption_receipts import (
    caption_source_kind as _caption_source_kind,
    record_caption_receipt as _record_caption_receipt,
    segment_rows as _segment_rows,
)


class CaptionAcquisitionHandler:
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
        except PlatformAccessRestricted:
            _record_caption_receipt(self.store,
                job_id=job.job_id,
                content_id=content.content_id,
                provider_id="youtube", model_id=None,
                operation="CAPTION_CAPTURE", request_id=None,
                input_bytes=None, input_seconds=None,
                estimated_cost_usd=0.0, status="ACCESS_RESTRICTED",
                receipt={"error_type": "PlatformAccessRestricted",
                         "access_path": "YOUTUBE_TRANSCRIPT_API_PUBLIC_CAPTION",
                         "capture_provenance": {
                             "method": "youtube-transcript-api", "method_version": "1.2.4",
                         }},
                request_key=f"{job.payload.get('external_id') or url}:attempt:{job.attempt}",
            )
            raise BlockedJob("YOUTUBE_CAPTION_ACCESS_RESTRICTED")
        except Exception as exc:
            _record_caption_receipt(self.store,
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
                "capture_provenance": capture.provenance,
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
            "capture_provenance": capture.provenance,
            "access_path": capture.provenance.get("access_path", "YT_DLP_PUBLIC_CAPTION"),
        }
        self.private_store.persist_caption(
            content_id=content.content_id,
            variant_id=variant_id,
            capture=capture,
            receipt=receipt,
        )
        _record_caption_receipt(self.store,
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
