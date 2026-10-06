from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
PRIMARY_REGISTRY = ROOT / "config" / "source-registry.v1.json"
DEFAULT_REGISTRY = PRIMARY_REGISTRY

ATOM = "http://www.w3.org/2005/Atom"
YT = "http://www.youtube.com/xml/schemas/2015"
MEDIA = "http://search.yahoo.com/mrss/"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MAX_DISCOVERY_RESPONSE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class DiscoveredContent:
    source_id: str
    platform: str
    external_id: str
    title: str
    canonical_url: str
    published_at: str
    author: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    duration_seconds: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class FetchedBytes:
    body: bytes
    final_url: str
    status_code: int
    media_type: str
    charset: str | None
    content_length: int
    etag: str | None = None
    last_modified: str | None = None



def load_registry(path: Path | None = None) -> dict[str, Any]:
    resolved = path if path is not None else PRIMARY_REGISTRY
    return json.loads(resolved.read_text())


def get_source(registry: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in registry.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(f"Unknown source_id: {source_id}")


def parse_youtube_feed(xml_text: str, source_id: str) -> list[DiscoveredContent]:
    root = ET.fromstring(xml_text)
    items: list[DiscoveredContent] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        video_id = entry.findtext(f"{{{YT}}}videoId")
        title = entry.findtext(f"{{{ATOM}}}title") or ""
        published = entry.findtext(f"{{{ATOM}}}published") or ""
        author_node = entry.find(f"{{{ATOM}}}author")
        author = None
        if author_node is not None:
            author = author_node.findtext(f"{{{ATOM}}}name")
        link_node = entry.find(f"{{{ATOM}}}link[@rel='alternate']")
        href = (
            link_node.attrib.get("href")
            if link_node is not None
            else f"https://www.youtube.com/watch?v={video_id}"
        )
        if not video_id:
            continue
        items.append(
            DiscoveredContent(
                source_id=source_id,
                platform="youtube",
                external_id=video_id,
                title=title,
                canonical_url=href,
                published_at=published,
                author=author,
            )
        )
    return items


def parse_podcast_rss(xml_text: str, source_id: str) -> list[DiscoveredContent]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    author = channel.findtext(f"{{{ITUNES}}}author") or channel.findtext("title")
    items: list[DiscoveredContent] = []
    for item in channel.findall("item"):
        guid = (item.findtext("guid") or "").strip()
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        published_at = pub_date
        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
        enclosure = item.find("enclosure")
        media_url = enclosure.attrib.get("url") if enclosure is not None else None
        media_type = enclosure.attrib.get("type") if enclosure is not None else None
        duration_raw = (item.findtext(f"{{{ITUNES}}}duration") or "").strip()
        duration_seconds = int(duration_raw) if duration_raw.isdigit() else None
        external_id = guid or media_url or title
        if not external_id:
            continue
        items.append(
            DiscoveredContent(
                source_id=source_id,
                platform="podcast_rss",
                external_id=external_id,
                title=title,
                canonical_url=media_url or "",
                published_at=published_at,
                author=author or None,
                media_url=media_url,
                media_type=media_type,
                duration_seconds=duration_seconds,
                description=description,
            )
        )
    return items


def validate_discovery_url(
    url: str,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    raw = str(url).strip()
    parsed = urlsplit(raw)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("DISCOVERY_URL_PORT_INVALID") from exc
    if parsed.scheme.lower() != "https":
        raise ValueError("DISCOVERY_URL_HTTPS_REQUIRED")
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ValueError("DISCOVERY_URL_AUTHORITY_REFUSED")
    try:
        addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("DISCOVERY_URL_DNS_FAILED") from exc
    if not addresses:
        raise ValueError("DISCOVERY_URL_DNS_EMPTY")
    for row in addresses:
        address = row[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("DISCOVERY_URL_DNS_INVALID") from exc
        if not ip.is_global:
            raise ValueError("DISCOVERY_URL_NONPUBLIC_IP")
    return raw


class _DiscoveryRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, resolver=socket.getaddrinfo) -> None:
        super().__init__()
        self.resolver = resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_discovery_url(newurl, resolver=self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(
    url: str,
    timeout: float = 15.0,
    *,
    max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
    resolver=socket.getaddrinfo,
) -> FetchedBytes:
    """Fetch one bounded public HTTPS representation with the discovery SSRF policy."""
    url = validate_discovery_url(url, resolver=resolver)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DichiarazioniPubbliche.it/0.0.1"},
    )
    opener = urllib.request.build_opener(_DiscoveryRedirectHandler(resolver=resolver))
    with opener.open(request, timeout=timeout) as response:
        final_url = validate_discovery_url(response.geturl(), resolver=resolver)
        if final_url != response.geturl():
            raise ValueError("DISCOVERY_URL_CANONICALIZATION_DRIFT")
        limit = max(int(max_response_bytes), 1)
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("DISCOVERY_RESPONSE_TOO_LARGE")
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except (TypeError, ValueError) as exc:
                raise ValueError("DISCOVERY_CONTENT_LENGTH_INVALID") from exc
            if declared_length < 0:
                raise ValueError("DISCOVERY_CONTENT_LENGTH_INVALID")
            if declared_length > limit:
                raise ValueError("DISCOVERY_RESPONSE_TOO_LARGE")
            if len(body) != declared_length:
                raise ValueError("DISCOVERY_RESPONSE_INCOMPLETE")
        status = int(getattr(response, "status", None) or response.getcode() or 200)
        media_type = response.headers.get_content_type() or "application/octet-stream"
        charset = response.headers.get_content_charset()
        return FetchedBytes(
            body=body,
            final_url=final_url,
            status_code=status,
            media_type=str(media_type).lower(),
            charset=charset,
            content_length=len(body),
            etag=(response.headers.get("ETag") or None),
            last_modified=(response.headers.get("Last-Modified") or None),
        )


def fetch_text(
    url: str,
    timeout: float = 15.0,
    *,
    max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
) -> str:
    fetched = fetch_bytes(url, timeout=timeout, max_response_bytes=max_response_bytes)
    charset = fetched.charset or "utf-8"
    return fetched.body.decode(charset)


def discover_source(
    source: dict[str, Any],
    *,
    feed_xml: str | None = None,
) -> list[DiscoveredContent]:
    from dichiarazioni_pubbliche.source_adapters import (
        discover_source as discover_source_with_adapter,
    )

    return discover_source_with_adapter(source, feed_xml=feed_xml)


def filter_discovered_content(
    source: dict[str, Any],
    items: list[DiscoveredContent],
) -> list[DiscoveredContent]:
    policy = source.get("content_policy", {})
    preferred_title = policy.get("prefer_longform_title_contains")
    out: list[DiscoveredContent] = []
    for item in items:
        if (
            policy.get("ignore_youtube_shorts_by_default", False)
            and "/shorts/" in item.canonical_url
        ):
            continue
        if preferred_title and preferred_title not in item.title:
            continue
        out.append(item)
    return out


def _run_yt_dlp_json(video_url: str) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "yt-dlp",
            "--skip-download",
            "--dump-single-json",
            video_url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def select_italian_caption(metadata: dict[str, Any]) -> dict[str, Any] | None:
    manual = metadata.get("subtitles") or {}
    automatic = metadata.get("automatic_captions") or {}

    for key in ("it-orig", "it"):
        tracks = manual.get(key)
        if tracks:
            return {
                "kind": "manual_caption",
                "language": key,
                "tracks": tracks,
            }

    for key in ("it-orig", "it"):
        tracks = automatic.get(key)
        if tracks:
            return {
                "kind": "automatic_caption",
                "language": key,
                "tracks": tracks,
            }
    return None


def plan_ingest(
    source: dict[str, Any],
    content: DiscoveredContent,
    *,
    youtube_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = source.get("content_policy", {})
    if content.platform == "podcast_rss":
        return {
            "content_id": content.external_id,
            "action": "RESOLVE_PLATFORM_TRANSCRIPT_THEN_AUDIO",
            "download_media": False,
            "prefer_audio_only": True,
            "podcast_audio_url_available": bool(content.media_url),
            "duration_seconds": content.duration_seconds,
            "next_order": [
                "MATCH_YOUTUBE_BY_TITLE_OR_GUEST",
                "ACQUIRE_PLATFORM_CAPTION",
                "USE_PODCAST_AUDIO_REMOTE_ASR_IF_NEEDED",
            ],
        }
    if content.platform != "youtube":
        return {
            "content_id": content.external_id,
            "action": "DISCOVERY_ONLY",
            "reason": "NO_PLATFORM_PLAN_IN_POC",
        }

    metadata = (
        youtube_metadata
        if youtube_metadata is not None
        else _run_yt_dlp_json(content.canonical_url)
    )
    caption = select_italian_caption(metadata)
    if caption:
        return {
            "content_id": content.external_id,
            "action": "ACQUIRE_CAPTION",
            "caption_kind": caption["kind"],
            "caption_language": caption["language"],
            "download_media": False,
            "next_if_low_confidence": (
                "REMOTE_ASR"
                if policy.get(
                    "download_media_only_if_transcript_missing_or_low_confidence",
                    True,
                )
                else "HOLD"
            ),
        }

    return {
        "content_id": content.external_id,
        "action": "REMOTE_ASR",
        "download_media": False,
        "prefer_audio_only": policy.get(
            "prefer_audio_only_when_visual_analysis_not_required",
            True,
        ),
        "reason": "NO_ITALIAN_CAPTION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--probe-captions", action="store_true")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    source = get_source(registry, args.source_id)
    items = discover_source(source)[: args.limit]
    output = []
    for item in items:
        row: dict[str, Any] = {"content": asdict(item)}
        if args.probe_captions:
            row["plan"] = plan_ingest(source, item)
        output.append(row)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
