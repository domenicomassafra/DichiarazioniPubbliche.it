"""#182: bounded approved YouTube Atom lookup for one podcast episode.

Loaded only by YouTubeResolver after the current worker's rights gate; no
independent network route, yt-dlp fallback, cookies, or source guessing.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

from dichiarazioni_pubbliche.source_watcher import fetch_bytes, parse_youtube_feed

class PodcastYouTubeResolutionMixin:
    """Non-invasive adapter over the existing YouTube catalog methods."""

    def resolve(self, title: str, source: dict[str, Any]) -> VideoCandidate | None:
        # Never interpret arbitrary RSS podcast XML as a YouTube Atom catalog.
        if source.get("kind") != "youtube_channel":
            raise ValueError("YOUTUBE_SOURCE_KIND_REQUIRED")
        from dichiarazioni_pubbliche.platform_transcript import VideoCandidate, choose_video_candidate

        combined: dict[str, VideoCandidate] = {}
        for candidate in self._atom_candidates(source):
            combined[candidate.video_id] = candidate
        match = choose_video_candidate(title, list(combined.values()))
        if match is not None:
            return match
        for candidate in self._flat_candidates(source):
            combined.setdefault(candidate.video_id, candidate)
        return choose_video_candidate(title, list(combined.values()))

    def resolve_associated(self, title: str, source: dict[str, Any], *,
                           association, check_fetch: Callable[[str], None]):
        return resolve_associated(
            self, title, source, association=association,
            check_fetch=check_fetch, fetch_catalog=fetch_bytes,
        )

def resolve_associated(
    self, title: str, source: dict[str, Any], *, association,
    check_fetch: Callable[[str], None], fetch_catalog: Callable,
) -> VideoCandidate | None:
    """Only the approved channel Atom, with rights rechecked around network I/O.

    The podcast RSS is not a YouTube catalog; unapproved flat-playlist
    searches can cross source boundaries and cannot establish channel identity.
    """
    import xml.etree.ElementTree as ET

    from dichiarazioni_pubbliche.platform_transcript import (
        VideoCandidate, _series_episode, choose_video_candidate,
    )

    from dichiarazioni_pubbliche.feed_parsing import ATOM, YT
    from dichiarazioni_pubbliche.source_associations import SourceAssociationBlocked

    if (source.get("id") != association.youtube_source_id
            or source.get("channel_id") != association.youtube_channel_id):
        raise SourceAssociationBlocked("SOURCE_ASSOCIATION_CHANNEL_MISMATCH")
    catalog_url = str(source["discovery_url"])
    check_fetch(catalog_url)
    fetched = fetch_catalog(catalog_url, allow_redirects=False)
    # Cross-URL redirects have their own rights subjects, never inherited.
    if fetched.final_url != catalog_url:
        raise SourceAssociationBlocked("YOUTUBE_ASSOCIATED_REDIRECT_UNAUTHORIZED")
    check_fetch(fetched.final_url)
    payload = fetched.body.decode(fetched.charset or "utf-8")
    catalog_sha256 = hashlib.sha256(fetched.body).hexdigest()
    # Atom feed identity is authoritative for this lookup, including empty
    # catalogs. A mismatched channel must never cause ASR or a locator.
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SourceAssociationBlocked("YOUTUBE_ASSOCIATED_FEED_INVALID") from exc
    if (root.tag != f"{ATOM}feed"
            or (root.findtext(f"{YT}channelId") or "").strip()
            != association.youtube_channel_id):
        raise SourceAssociationBlocked("YOUTUBE_ASSOCIATED_CHANNEL_UNVERIFIED")
    expected = _series_episode(title)
    if expected is None:
        return None
    candidates = []
    for row in parse_youtube_feed(payload, association.youtube_source_id):
        # Never accept alternate/feed links or an invalid ID as a locator.
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", row.external_id):
            continue
        if _series_episode(row.title) != expected:
            continue
        candidates.append(VideoCandidate(
            video_id=row.external_id, title=row.title,
            canonical_url=f"https://www.youtube.com/watch?v={row.external_id}",
            catalog_sha256=catalog_sha256,
        ))
    # Equal series/episode markers can describe clips, reuploads, or separate
    # editions. Never attach one of multiple distinct video IDs by title rank.
    if len({candidate.video_id for candidate in candidates}) > 1:
        raise SourceAssociationBlocked("YOUTUBE_ASSOCIATED_EPISODE_AMBIGUOUS")
    return choose_video_candidate(title, candidates)
