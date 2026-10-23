"""Versioned, explicitly reviewed podcast-to-YouTube associations (offline F3 seam).

An association is a locator contract, never proof of ingestion or source-use rights.
Rights for each live URL are checked separately and currently at the fetch seam.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.source_watcher import get_source

_CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")


class SourceAssociationBlocked(ValueError):
    """Stable fail-closed code; no implicit cross-source consent."""


@dataclass(frozen=True)
class PodcastYouTubeAssociation:
    id: str
    version: int
    podcast_source_id: str
    youtube_source_id: str
    youtube_channel_id: str
    policy_version: str
    approval_ref: str
    reviewer_ref: str
    absence_reviews: tuple[tuple[str, str, str, str], ...] = ()

    def reviewed_absence(self, content_id: str, episode: tuple[str, int] | None) -> str:
        """A short Atom listing is never proof of no YouTube copy."""
        if episode is None:
            raise SourceAssociationBlocked("SOURCE_ASSOCIATION_EPISODE_UNVERIFIED")
        marker = f"{episode[0]}#{episode[1]}"
        found = [review for review in self.absence_reviews
                 if review[0] == content_id and review[1] == marker]
        if len(found) != 1:
            raise SourceAssociationBlocked("YOUTUBE_COPY_ABSENCE_UNREVIEWED")
        return found[0][2]


def select_podcast_youtube_association(
    registry: dict[str, Any], podcast_source_id: str,
) -> tuple[PodcastYouTubeAssociation, dict[str, Any]]:
    """Select one approved exact channel, with no guessing by title or RSS links."""
    if not isinstance(registry, dict) or registry.get("source_associations_version") != 1:
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_POLICY_MISSING")
    entries = registry.get("source_associations")
    if not isinstance(entries, list):
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_REGISTRY_INVALID")
    matching = [item for item in entries if isinstance(item, dict)
                and item.get("podcast_source_id") == podcast_source_id]
    if not matching:
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_MISSING")
    if len(matching) != 1:
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_AMBIGUOUS")
    item = matching[0]
    required = ("id", "podcast_source_id", "youtube_source_id", "youtube_channel_id",
                "approval_ref", "reviewer_ref", "policy_version")
    if (item.get("version") != 1 or isinstance(item.get("version"), bool)
            or item.get("status") != "APPROVED"
            or any(not isinstance(item.get(key), str) or not item[key].strip()
                   or item[key] != item[key].strip() for key in required)
            or item.get("policy_version") != "source-association-v1"
            or not _CHANNEL.fullmatch(str(item.get("youtube_channel_id") or ""))):
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_NOT_APPROVED")
    try:
        podcast = get_source(registry, podcast_source_id)
        youtube = get_source(registry, item["youtube_source_id"])
    except KeyError as exc:
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_SOURCE_MISSING") from exc
    channel = item["youtube_channel_id"]
    if (podcast.get("kind") != "podcast_rss"
            or youtube.get("kind") != "youtube_channel"
            or youtube.get("channel_id") != channel
            or youtube.get("channel_url") != f"https://www.youtube.com/channel/{channel}"
            or youtube.get("discovery_url") !=
            f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}"):
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_CHANNEL_MISMATCH")
    raw_absences = item.get("asr_absence_reviews", [])
    if not isinstance(raw_absences, list) or len(raw_absences) > 64:
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_ABSENCE_INVALID")
    absences = []
    for review in raw_absences:
        if not isinstance(review, dict):
            raise SourceAssociationBlocked("SOURCE_ASSOCIATION_ABSENCE_INVALID")
        fields = ("content_id", "episode_marker", "approval_ref", "reviewer_ref")
        if (review.get("status") != "APPROVED"
                or any(not isinstance(review.get(key), str) or not review[key].strip()
                       or review[key] != review[key].strip() for key in fields)
                or not re.fullmatch(r"[a-z ]+#[1-9][0-9]*", review["episode_marker"])):
            raise SourceAssociationBlocked("SOURCE_ASSOCIATION_ABSENCE_INVALID")
        absences.append(tuple(review[key] for key in fields))
    if len({row[:2] for row in absences}) != len(absences):
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_ABSENCE_AMBIGUOUS")
    return PodcastYouTubeAssociation(**{key: item[key] for key in required},
                                     version=1, absence_reviews=tuple(absences)), youtube


def podcast_asr_source_guard(
    store: QueueRuntimeStore, *, content_id: str, url: str,
) -> SourceFamilyUseGuard:
    """Require exact podcast media rights independently of a matched YouTube channel."""
    if (not isinstance(store, QueueRuntimeStore) or not isinstance(content_id, str)
            or not content_id or not isinstance(url, str) or not url.startswith("https://")):
        raise SourceUseBlocked("SOURCE_USE_PODCAST_CONTEXT_INVALID")
    subject = RightsSubject("PODCAST_RSS", "URL", url, content_id=content_id)
    registry = PrivateRightsRegistryStore(database_url=store.database_url, psql=store.psql)
    try:
        current = registry.read_current(subject)
    except Exception:
        raise SourceUseBlocked("SOURCE_USE_READ_UNAVAILABLE") from None
    if current is None:
        raise SourceUseBlocked("SOURCE_USE_RECORD_MISSING")
    guard = SourceFamilyUseGuard(
        read_current=registry.read_current, subject=subject,
        rights_record_id=current.id, policy_version=current.policy_version,
    )
    guard.bind_capture(content_id=content_id, url=url)
    guard.bind_fetched(final_url=url)
    return guard
