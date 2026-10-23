"""#182: bounded private canary for one approved podcast episode -> YouTube locator.

The canary reuses the production resolver (:func:`resolve_associated`), the strict
Atom channel identity and the approved registry association; it adds only what a
private, reviewable proof needs:

* an explicit, canary-scoped rights decision that names the allowed hosts and
  scopes (metadata fetch and metadata retention only: never media, never ASR);
* bounded HTTPS fetches with redirects refused and a hard byte ceiling;
* a JSON receipt with the hashes, identities and provenance of both sides.

It writes nothing to the database, downloads no media, starts no ASR and
publishes nothing. A missing or ambiguous input is a refusal, never a guess.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any, Callable

from dichiarazioni_pubbliche.feed_parsing import MAX_FEED_BYTES
from dichiarazioni_pubbliche.platform_transcript import _series_episode
from dichiarazioni_pubbliche.podcast_youtube_resolution import resolve_associated
from dichiarazioni_pubbliche.source_associations import (
    SourceAssociationBlocked, select_podcast_youtube_association,
)
from dichiarazioni_pubbliche.source_watcher import fetch_bytes, parse_podcast_rss

SCHEMA = "podcast-youtube-canary-v1"
REQUIRED_SCOPES = ("FETCH", "STORE_METADATA")


class CanaryRefused(ValueError):
    """Fail-closed canary refusal; the code is stable and never generic."""


def _rights_guard(decision: Any, url: str) -> None:
    """Only a current metadata-only decision for this exact host may fetch."""
    if not isinstance(decision, dict) or decision.get("status") != "APPROVED":
        raise CanaryRefused("CANARY_RIGHTS_DECISION_MISSING")
    scopes = decision.get("scopes")
    if (not isinstance(scopes, list)
            or any(scope not in scopes for scope in REQUIRED_SCOPES)
            or "ASR_MEDIA" in scopes or "PUBLISH" in scopes):
        raise CanaryRefused("CANARY_RIGHTS_SCOPE_UNSUPPORTED")
    for key in ("id", "reviewer_ref", "approved_at"):
        value = decision.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise CanaryRefused("CANARY_RIGHTS_DECISION_INVALID")
    hosts = decision.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise CanaryRefused("CANARY_RIGHTS_HOST_MISSING")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise CanaryRefused("CANARY_URL_INSECURE")
    host = url.split("/", 3)[2].split("@")[-1].split(":")[0].lower()
    if host not in {str(item).lower() for item in hosts}:
        raise CanaryRefused("CANARY_RIGHTS_HOST_UNAUTHORIZED")


def _fetch(url: str, *, rights: Any, fetcher: Callable) -> tuple[bytes, str]:
    """One bounded, redirect-free HTTPS representation with its SHA-256."""
    _rights_guard(rights, url)
    fetched = fetcher(url, allow_redirects=False)
    if fetched.final_url != url:
        raise CanaryRefused("CANARY_REDIRECT_UNAUTHORIZED")
    _rights_guard(rights, fetched.final_url)
    body = fetched.body
    if not isinstance(body, bytes) or not body or len(body) > MAX_FEED_BYTES:
        raise CanaryRefused("CANARY_FEED_INVALID")
    return body, hashlib.sha256(body).hexdigest()


def _select_episode(registry: dict[str, Any], podcast_source_id: str, xml: str,
                    *, guid: str | None, title: str | None) -> dict[str, Any]:
    rows = parse_podcast_rss(xml, podcast_source_id)
    if guid:
        matches = [row for row in rows if row.external_id == guid]
    elif title:
        matches = [row for row in rows if row.title == title]
    else:
        raise CanaryRefused("CANARY_EPISODE_SELECTOR_MISSING")
    if len(matches) != 1:
        raise CanaryRefused("CANARY_EPISODE_AMBIGUOUS")
    episode = matches[0]
    if _series_episode(episode.title) is None:
        # A numbered series/episode marker is the exact identity an approved
        # association may resolve; without it the title is not an identity.
        raise CanaryRefused("CANARY_EPISODE_MARKER_MISSING")
    return {
        "guid": episode.external_id,
        "title": episode.title,
        "published_at": episode.published_at,
        "canonical_url": episode.canonical_url,
    }


def resolve_episode(
    *, registry: dict[str, Any], podcast_source_id: str, rights: Any,
    guid: str | None = None, title: str | None = None,
    fetcher: Callable = fetch_bytes, clock: Callable = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Return a receipt for one exact episode; raise :class:`CanaryRefused`."""
    if not isinstance(registry, dict):
        raise CanaryRefused("CANARY_REGISTRY_INVALID")
    try:
        association, youtube_source = select_podcast_youtube_association(
            registry, podcast_source_id,
        )
    except SourceAssociationBlocked as exc:
        raise CanaryRefused(str(exc)) from exc
    podcast_source = next(
        (item for item in registry.get("sources", [])
         if isinstance(item, dict) and item.get("id") == podcast_source_id), None,
    )
    if podcast_source is None:
        raise CanaryRefused("CANARY_PODCAST_SOURCE_MISSING")
    rss_url = str(podcast_source.get("discovery_url") or "")
    if not rss_url.startswith("https://"):
        raise CanaryRefused("CANARY_URL_INSECURE")
    rss_bytes, rss_sha256 = _fetch(rss_url, rights=rights, fetcher=fetcher)
    episode = _select_episode(
        registry, podcast_source_id, rss_bytes.decode("utf-8", "strict"),
        guid=guid, title=title,
    )

    def check_fetch(url: str) -> None:
        _rights_guard(rights, url)

    try:
        candidate = resolve_associated(
            None, episode["title"], youtube_source, association=association,
            check_fetch=check_fetch, fetch_catalog=fetcher,
        )
    except CanaryRefused:
        raise
    except SourceAssociationBlocked as exc:
        raise CanaryRefused(str(exc)) from exc
    except ValueError as exc:
        raise CanaryRefused(f"CANARY_ATOM_REFUSED:{exc}") from exc
    if candidate is None:
        raise CanaryRefused("CANARY_YOUTUBE_COPY_UNPROVEN")

    series, episode_number = _series_episode(episode["title"])
    return {
        "schema": SCHEMA,
        "decision": "RESOLVED",
        "generated_at": clock().isoformat().replace("+00:00", "Z"),
        "podcast": {
            "source_id": podcast_source_id,
            "feed_url": rss_url,
            "feed_sha256": rss_sha256,
            "guid": episode["guid"],
            "title": episode["title"],
            "published_at": episode["published_at"],
            "media_url": episode["canonical_url"],
            "series": series,
            "episode_number": episode_number,
        },
        "youtube": {
            "source_id": youtube_source["id"],
            "channel_id": association.youtube_channel_id,
            "catalog_url": youtube_source["discovery_url"],
            "catalog_sha256": candidate.catalog_sha256,
            "video_id": candidate.video_id,
            "video_title": candidate.title,
            "canonical_url": candidate.canonical_url,
        },
        "association": {
            "id": association.id,
            "version": association.version,
            "policy_version": association.policy_version,
            "approval_ref": association.approval_ref,
            "reviewer_ref": association.reviewer_ref,
        },
        "rights": {
            "decision_id": rights["id"],
            "reviewer_ref": rights["reviewer_ref"],
            "approved_at": rights["approved_at"],
            "hosts": sorted(rights["hosts"]),
            "scopes": list(rights["scopes"]),
            "asr_granted": False,
            "media_downloaded": False,
        },
        "publication": "HOLD",
        "side_effects": {"database_writes": 0, "media_fetches": 0, "asr_jobs": 0},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bounded private #182 canary")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--podcast-source-id", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--episode-guid")
    parser.add_argument("--episode-title")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    with open(args.registry, encoding="utf-8") as handle:
        registry = json.load(handle)
    with open(args.rights, encoding="utf-8") as handle:
        rights = json.load(handle)
    try:
        receipt = resolve_episode(
            registry=registry, podcast_source_id=args.podcast_source_id,
            rights=rights, guid=args.episode_guid, title=args.episode_title,
        )
    except CanaryRefused as exc:
        print(json.dumps({"schema": SCHEMA, "decision": "HOLD", "code": str(exc)}))
        return 3
    payload = json.dumps(receipt, indent=1, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload)
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
