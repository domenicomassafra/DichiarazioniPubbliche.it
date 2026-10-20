"""#182: private worker orchestration for an approved podcast→YouTube link."""
from __future__ import annotations

from dichiarazioni_pubbliche.platform_transcript import PlatformAccessRestricted, _series_episode
from dichiarazioni_pubbliche.source_associations import (
    SourceAssociationBlocked, select_podcast_youtube_association,
)
from dichiarazioni_pubbliche.worker_errors import BlockedJob, RetryableJob


def resolve_podcast_platform(self, job, content) -> None:
    # Relevance precedes any association and any possible network fetch.
    self._require_current_ingestion_relevance(content)
    try:
        association, youtube_source = select_podcast_youtube_association(
            self.registry, content.source_id,
        )
    except SourceAssociationBlocked as exc:
        raise BlockedJob(str(exc)) from exc

    def check_catalog_rights(url: str) -> None:
        self._require_current_ingestion_relevance(content)
        guard = self._caption_rights_guard(content, url)
        self._caption_rights_receipt(guard)

    try:
        candidate = self.resolver.resolve_associated(
            content.title, youtube_source, association=association,
            check_fetch=check_catalog_rights,
        )
    except (BlockedJob, SourceAssociationBlocked) as exc:
        if isinstance(exc, BlockedJob):
            raise
        raise BlockedJob(str(exc)) from exc
    except PlatformAccessRestricted:
        raise BlockedJob("YOUTUBE_CATALOG_ACCESS_RESTRICTED") from None
    except Exception as exc:
        raise RetryableJob(
            f"YOUTUBE_RESOLUTION_FAILED:{type(exc).__name__}", 300,
        ) from exc
    if candidate is None:
        # No match in a bounded Atom listing does not prove that an
        # older episode lacks an authorized YouTube copy. A separate
        # content/episode-bound absence review is compulsory for ASR.
        try:
            association.reviewed_absence(content.content_id, _series_episode(content.title))
        except SourceAssociationBlocked as exc:
            raise BlockedJob(str(exc)) from exc
        self._require_podcast_asr_clearance(content)
        self._enqueue_asr(content, reason="PLATFORM_COPY_NOT_FOUND")
        return
    self._require_current_ingestion_relevance(content)
    video_rights = self._caption_rights_guard(content, candidate.canonical_url)
    rights_receipt = self._caption_rights_receipt(video_rights)
    self.store.upsert_locator(
        content.content_id,
        platform="youtube",
        external_id=candidate.video_id,
        canonical_url=candidate.canonical_url,
        metadata={
            "resolved_from": "podcast_rss",
            "podcast_source_id": content.source_id,
            "podcast_canonical_url": content.canonical_url,
            "youtube_source_id": youtube_source["id"],
            "youtube_channel_id": association.youtube_channel_id,
            "youtube_catalog_url": youtube_source["discovery_url"],
            "youtube_catalog_sha256": candidate.catalog_sha256,
            "source_association_id": association.id,
            "source_association_version": association.version,
            "source_association_policy_version": association.policy_version,
            "source_association_approval_ref": association.approval_ref,
            "youtube_rights_record_id": rights_receipt["source_rights_record_id"],
            "youtube_rights_fingerprints": rights_receipt["source_rights_fingerprints"],
        },
    )
    self._probe_and_enqueue_caption(job, content, candidate)
