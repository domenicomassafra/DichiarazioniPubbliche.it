from __future__ import annotations

import ipaddress
import json
import math
import re
import socket
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

MAX_DISCOVERY_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_DISCOVERED_ITEMS_PER_SOURCE = 20
MAX_TEXT_LENGTH = 4096
MAX_TITLE_LENGTH = 1000
MAX_ID_LENGTH = 512
MAX_DURATION_SECONDS = 7 * 24 * 60 * 60
SUPPORTED_SOURCE_KINDS = frozenset(
    {"youtube_channel", "podcast_rss", "public_creator_accounts"}
)
_BLOCKED_CATEGORIES = frozenset(
    {
        "UNSUPPORTED",
        "ACCESS_RESTRICTED",
        "POLICY_REJECTED",
        "MISSING_ID",
        "SSRF_REJECTED",
    }
)


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
    source_kind: str | None = None

    @property
    def source_family(self) -> str | None:
        return self.source_kind

    @property
    def family(self) -> str | None:
        return self.source_kind


def _legacy_filter_discovered_content(
    source: dict[str, Any], items: list[DiscoveredContent]
) -> list[DiscoveredContent]:
    from dichiarazioni_pubbliche.source_watcher import filter_discovered_content

    return filter_discovered_content(source, items)


def _legacy_parse_youtube_feed(xml_text: str, source_id: str) -> list[Any]:
    from dichiarazioni_pubbliche.source_watcher import parse_youtube_feed

    return parse_youtube_feed(xml_text, source_id)


def _legacy_parse_podcast_rss(xml_text: str, source_id: str) -> list[Any]:
    from dichiarazioni_pubbliche.source_watcher import parse_podcast_rss

    return parse_podcast_rss(xml_text, source_id)


def _legacy_validate_discovery_url(
    url: str, resolver: Callable[..., list[Any]] | None
) -> str:
    from dichiarazioni_pubbliche.source_watcher import validate_discovery_url

    if resolver is None:
        return _validate_public_url(url, field="discovery_url")
    return validate_discovery_url(url, resolver=resolver)


class DiscoveredContentBatch(list[DiscoveredContent]):
    def __init__(
        self,
        items: list[DiscoveredContent] | tuple[DiscoveredContent, ...] = (),
        *,
        omitted_items: int = 0,
    ) -> None:
        super().__init__(items)
        self.omitted_items = max(int(omitted_items), 0)


@dataclass(frozen=True)
class DiscoveryResult:
    items: tuple[DiscoveredContent, ...]
    status: str = "OK"
    error_category: str | None = None
    error: str | None = None
    omitted_items: int = 0

    @property
    def blocked(self) -> bool:
        return self.status == "BLOCKED"


class SourceAdapterError(ValueError):
    def __init__(self, category: str, detail: str = "") -> None:
        normalized = _category(category)
        self.category = normalized
        self.detail = _safe_detail(detail)
        super().__init__(normalized)

    @property
    def blocked(self) -> bool:
        return self.category in _BLOCKED_CATEGORIES


def _category(value: object) -> str:
    text = str(value or "SOURCE_FAILURE").strip().upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return (text or "SOURCE_FAILURE")[:80]


def _safe_detail(value: object) -> str:
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"[\r\n\t]+", " ", text)
    return text[:240]


def _text(value: object, limit: int, *, required: bool = False) -> str:
    if value is None:
        result = ""
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        result = str(value).strip()
    else:
        raise SourceAdapterError("MALFORMED_RESPONSE")
    if required and not result:
        raise SourceAdapterError("MISSING_ID")
    if len(result) > limit:
        result = result[:limit]
    return result


def _optional_text(value: object, limit: int = MAX_TEXT_LENGTH) -> str | None:
    if value is None:
        return None
    result = _text(value, limit)
    return result or None


def _duration(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SourceAdapterError("MALFORMED_RESPONSE")
    if not math.isfinite(number) or number < 0:
        raise SourceAdapterError("MALFORMED_RESPONSE")
    return min(int(number), MAX_DURATION_SECONDS)


def _media_values(record: dict[str, Any]) -> tuple[Any, Any]:
    media = record.get("media")
    if not isinstance(media, dict):
        media = {}
    media_url = record.get("media_url") or media.get("url")
    media_type = record.get("media_type") or media.get("type")
    return media_url, media_type


def _timestamp(value: object) -> str:
    raw = _text(value, 128)
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _validate_public_url(
    value: object,
    *,
    field: str,
    resolver: Callable[..., list[Any]] | None = None,
) -> str:
    raw = _text(value, 2048, required=True)
    parsed = urlsplit(raw)
    try:
        port = parsed.port
    except ValueError as exc:
        raise SourceAdapterError("SSRF_REJECTED", f"{field}:{exc}") from exc
    if parsed.scheme.lower() != "https":
        raise SourceAdapterError("SSRF_REJECTED", f"{field}:HTTPS_REQUIRED")
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise SourceAdapterError("SSRF_REJECTED", f"{field}:AUTHORITY_REFUSED")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise SourceAdapterError("SSRF_REJECTED", f"{field}:NONPUBLIC_IP")
    if resolver is not None:
        try:
            addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise SourceAdapterError("SSRF_REJECTED", f"{field}:DNS_FAILED") from exc
        if not addresses:
            raise SourceAdapterError("SSRF_REJECTED", f"{field}:DNS_EMPTY")
        for row in addresses:
            try:
                address = ipaddress.ip_address(row[4][0])
            except (IndexError, TypeError, ValueError) as exc:
                raise SourceAdapterError("SSRF_REJECTED", f"{field}:DNS_INVALID") from exc
            if not address.is_global:
                raise SourceAdapterError("SSRF_REJECTED", f"{field}:NONPUBLIC_IP")
    return raw


def _validate_feed_url(
    url: str,
    *,
    resolver: Callable[..., list[Any]] | None,
) -> None:
    if resolver is not None:
        try:
            _legacy_validate_discovery_url(url, resolver)
        except ValueError as exc:
            raise SourceAdapterError("SSRF_REJECTED", str(exc)) from exc
    else:
        _validate_public_url(url, field="discovery_url", resolver=None)


def _content(
    *,
    source: dict[str, Any],
    source_kind: str,
    platform: str,
    external_id: str,
    title: str,
    canonical_url: str,
    published_at: str,
    author: str | None = None,
    media_url: str | None = None,
    media_type: str | None = None,
    duration_seconds: int | None = None,
    description: str | None = None,
    resolver: Callable[..., list[Any]] | None = None,
) -> DiscoveredContent:
    source_id = _text(source.get("id"), MAX_ID_LENGTH, required=True)
    stable_id = _text(external_id, MAX_ID_LENGTH, required=True)
    platform_value = _text(platform, 64, required=True).lower()
    if platform_value not in {"youtube", "podcast_rss", "instagram", "tiktok"}:
        raise SourceAdapterError("UNSUPPORTED", f"platform:{platform_value}")
    title_value = _text(title, MAX_TITLE_LENGTH)
    canonical = _validate_public_url(
        canonical_url,
        field="canonical_url",
        resolver=resolver,
    )
    safe_media_url = None
    if media_url:
        safe_media_url = _validate_public_url(
            media_url,
            field="media_url",
            resolver=resolver,
        )
    return DiscoveredContent(
        source_id=source_id,
        platform=platform_value,
        external_id=stable_id,
        title=title_value,
        canonical_url=canonical,
        published_at=_timestamp(published_at),
        author=_optional_text(author, 512),
        media_url=safe_media_url,
        media_type=_optional_text(media_type, 128),
        duration_seconds=duration_seconds,
        description=_optional_text(description),
        source_kind=source_kind,
    )


def _deduplicate(items: list[DiscoveredContent]) -> list[DiscoveredContent]:
    seen: set[tuple[str, str, str]] = set()
    result: list[DiscoveredContent] = []
    for item in items:
        key = (item.source_id, item.platform, item.external_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _limited(
    items: list[DiscoveredContent], limit: int
) -> tuple[DiscoveredContentBatch, int]:
    deduped = _deduplicate(items)
    effective = min(max(int(limit), 0), MAX_DISCOVERED_ITEMS_PER_SOURCE)
    omitted = max(len(deduped) - effective, 0)
    return DiscoveredContentBatch(deduped[:effective], omitted_items=omitted), omitted


def _feed_text(
    url: str,
    *,
    feed_xml: str | None,
    fetcher: Callable[[str], str] | None,
    timeout: float,
    max_response_bytes: int,
) -> str:
    if feed_xml is not None:
        return feed_xml
    if fetcher is not None:
        return fetcher(url)
    from dichiarazioni_pubbliche import source_watcher

    return source_watcher.fetch_text(
        url,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )


class SourceAdapter:
    kind = ""

    def discover(
        self,
        source: dict[str, Any],
        *,
        limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
        feed_xml: str | None = None,
        metadata: Any = None,
        fetcher: Callable[[str], str] | None = None,
        resolver: Callable[..., list[Any]] | None = None,
        timeout: float = 15.0,
        max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
    ) -> list[DiscoveredContent]:
        raise NotImplementedError

    def plan(
        self,
        source: dict[str, Any],
        content: DiscoveredContent,
        *,
        youtube_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return scheduler_ingest_plan(content)


class YouTubeChannelAdapter(SourceAdapter):
    kind = "youtube_channel"

    def discover(
        self,
        source: dict[str, Any],
        *,
        limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
        feed_xml: str | None = None,
        metadata: Any = None,
        fetcher: Callable[[str], str] | None = None,
        resolver: Callable[..., list[Any]] | None = None,
        timeout: float = 15.0,
        max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
    ) -> list[DiscoveredContent]:
        podcast_url = _text(source.get("podcast_rss_url"), 2048)
        preference = source.get("discovery_preference") or []
        if podcast_url and preference and str(preference[0]).upper() == "PODCAST_RSS":
            return PodcastRssAdapter().discover(
                {**source, "discovery_url": podcast_url, "discovery_preference": []},
                limit=limit,
                feed_xml=feed_xml,
                metadata=metadata,
                fetcher=fetcher,
                resolver=resolver,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
                source_kind_override=self.kind,
            )
        url = _text(source.get("discovery_url"), 2048, required=True)
        _validate_feed_url(url, resolver=resolver)
        xml_text = _feed_text(
            url,
            feed_xml=feed_xml,
            fetcher=fetcher,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        try:
            raw = _legacy_parse_youtube_feed(
                xml_text, _text(source.get("id"), MAX_ID_LENGTH, required=True)
            )
        except ET.ParseError as exc:
            raise SourceAdapterError("MALFORMED_RESPONSE", str(exc)) from exc
        normalized: list[DiscoveredContent] = []
        for item in raw:
            if not item.external_id:
                raise SourceAdapterError("MISSING_ID", "youtube")
            canonical = item.canonical_url or (
                f"https://www.youtube.com/watch?v={item.external_id}"
            )
            normalized.append(
                _content(
                    source=source,
                    source_kind=self.kind,
                    platform="youtube",
                    external_id=item.external_id,
                    title=item.title,
                    canonical_url=canonical,
                    published_at=item.published_at,
                    author=item.author,
                    resolver=resolver,
                )
            )
        result, _ = _limited(
            _legacy_filter_discovered_content(source, normalized), limit
        )
        return result


class PodcastRssAdapter(SourceAdapter):
    kind = "podcast_rss"

    def discover(
        self,
        source: dict[str, Any],
        *,
        limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
        feed_xml: str | None = None,
        metadata: Any = None,
        fetcher: Callable[[str], str] | None = None,
        resolver: Callable[..., list[Any]] | None = None,
        timeout: float = 15.0,
        max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
        source_kind_override: str | None = None,
    ) -> list[DiscoveredContent]:
        url = _text(
            source.get("discovery_url") or source.get("feed_url") or source.get("podcast_rss_url"),
            2048,
            required=True,
        )
        _validate_feed_url(url, resolver=resolver)
        xml_text = _feed_text(
            url,
            feed_xml=feed_xml,
            fetcher=fetcher,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise SourceAdapterError("MALFORMED_RESPONSE", str(exc)) from exc
        channel = root.find("channel")
        if channel is None:
            raise SourceAdapterError("MALFORMED_RESPONSE", "RSS_CHANNEL_MISSING")
        expected: list[dict[str, str]] = []
        for node in channel.findall("item"):
            guid = (node.findtext("guid") or "").strip()
            enclosure = node.find("enclosure")
            enclosure_url = enclosure.attrib.get("url", "").strip() if enclosure is not None else ""
            if not guid and not enclosure_url:
                raise SourceAdapterError("MISSING_ID", "rss_item")
            expected.append(
                {
                    "external_id": guid or enclosure_url,
                    "canonical_url": (node.findtext("link") or "").strip() or enclosure_url,
                }
            )
        try:
            raw = _legacy_parse_podcast_rss(
                xml_text, _text(source.get("id"), MAX_ID_LENGTH, required=True)
            )
        except ET.ParseError as exc:
            raise SourceAdapterError("MALFORMED_RESPONSE", str(exc)) from exc
        if not expected and raw:
            raise SourceAdapterError("MALFORMED_RESPONSE", "RSS_ITEMS_MISSING")
        normalized: list[DiscoveredContent] = []
        for index, item in enumerate(raw):
            details = expected[index] if index < len(expected) else {}
            external_id = details.get("external_id") or item.external_id
            if not external_id or external_id == item.title and not item.media_url:
                raise SourceAdapterError("MISSING_ID", "rss_item")
            canonical = details.get("canonical_url") or item.canonical_url or item.media_url
            normalized.append(
                _content(
                    source=source,
                    source_kind=source_kind_override or self.kind,
                    platform="podcast_rss",
                    external_id=external_id,
                    title=item.title,
                    canonical_url=canonical,
                    published_at=item.published_at,
                    author=item.author,
                    media_url=item.media_url,
                    media_type=item.media_type,
                    duration_seconds=item.duration_seconds,
                    description=item.description,
                    resolver=resolver,
                )
            )
        result, _ = _limited(
            _legacy_filter_discovered_content(source, normalized), limit
        )
        return result


class PublicCreatorAccountsAdapter(SourceAdapter):
    kind = "public_creator_accounts"

    def discover(
        self,
        source: dict[str, Any],
        *,
        limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
        feed_xml: str | None = None,
        metadata: Any = None,
        fetcher: Callable[[str], str] | None = None,
        resolver: Callable[..., list[Any]] | None = None,
        timeout: float = 15.0,
        max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
    ) -> list[DiscoveredContent]:
        if fetcher is not None or feed_xml is not None:
            raise SourceAdapterError("POLICY_REJECTED", "CREATOR_FETCH_NOT_ALLOWED")
        payload = metadata if metadata is not None else _configured_metadata(source)
        records = _metadata_records(payload)
        normalized: list[DiscoveredContent] = []
        for record in records:
            if not isinstance(record, dict):
                raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_POST")
            status = str(
                record.get("access")
                or record.get("visibility")
                or record.get("status")
                or ""
            ).strip().lower()
            if (
                record.get("private") is True
                or record.get("restricted") is True
                or status in {"private", "restricted", "login_required", "unavailable", "deleted"}
            ):
                raise SourceAdapterError("ACCESS_RESTRICTED", "CREATOR_POST")
            if record.get("approved") is False or record.get("policy_approved") is False:
                raise SourceAdapterError("POLICY_REJECTED", "CREATOR_POST")
            platform = str(record.get("platform") or record.get("network") or "").strip().lower()
            if platform not in {"instagram", "tiktok"}:
                raise SourceAdapterError("UNSUPPORTED", "CREATOR_PLATFORM")
            post_id = record.get("post_id") or record.get("external_id") or record.get("id")
            if not post_id:
                raise SourceAdapterError("MISSING_ID", "CREATOR_POST")
            canonical_url = record.get("canonical_url") or record.get("url") or record.get("permalink")
            media_url, media_type = _media_values(record)
            normalized.append(
                _content(
                    source=source,
                    source_kind=self.kind,
                    platform=platform,
                    external_id=post_id,
                    title=record.get("title") or record.get("caption") or "",
                    canonical_url=canonical_url,
                    published_at=record.get("published_at")
                    or record.get("publication_timestamp")
                    or record.get("timestamp")
                    or "",
                    author=record.get("author") or record.get("creator"),
                    media_url=media_url,
                    media_type=media_type,
                    duration_seconds=_duration(record.get("duration_seconds")),
                    description=record.get("description") or record.get("caption"),
                    resolver=resolver,
                )
            )
        result, _ = _limited(
            _legacy_filter_discovered_content(source, normalized), limit
        )
        return result


def _configured_metadata(source: dict[str, Any]) -> Any:
    for key in (
        "public_metadata",
        "approved_metadata",
        "public_metadata_fixture",
        "approved_canary_fixture",
        "metadata",
        "public_posts",
        "posts",
    ):
        if key in source:
            return _load_metadata_value(source[key])
    discovery = source.get("discovery")
    if isinstance(discovery, dict):
        for key in ("public_metadata", "metadata_fixture", "posts"):
            if key in discovery:
                return _load_metadata_value(discovery[key])
    canary = source.get("approved_canary")
    if isinstance(canary, (dict, list)):
        if isinstance(canary, list):
            return canary
        for key in ("public_metadata", "metadata", "posts"):
            if key in canary:
                return _load_metadata_value(canary[key])
    raise SourceAdapterError("ACCESS_RESTRICTED", "CREATOR_METADATA_NOT_CONFIGURED")


def _load_metadata_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, Path)):
        path = Path(value)
        try:
            if path.stat().st_size > MAX_DISCOVERY_RESPONSE_BYTES:
                raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_FIXTURE_TOO_LARGE")
            raw = path.read_bytes()
        except SourceAdapterError:
            raise
        except (OSError, ValueError) as exc:
            raise SourceAdapterError("ACCESS_RESTRICTED", "CREATOR_FIXTURE_UNAVAILABLE") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_FIXTURE_JSON") from exc
    raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_METADATA")


def _metadata_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_require_record(record) for record in payload]
    if not isinstance(payload, dict):
        raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_METADATA")
    for key in ("posts", "items", "content"):
        value = payload.get(key)
        if isinstance(value, list):
            return [_require_record(record) for record in value]
    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        records: list[dict[str, Any]] = []
        for platform, values in platforms.items():
            if isinstance(values, dict) and not any(
                key in values for key in ("posts", "items", "content")
            ):
                values = [values]
            elif isinstance(values, dict):
                values = values.get("posts") or values.get("items") or values.get("content") or []
            if not isinstance(values, list):
                raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_PLATFORM_POSTS")
            for value in values:
                record = _require_record(value)
                if not record.get("platform"):
                    record = {**record, "platform": platform}
                records.append(record)
        return records
    if payload.get("platform") or payload.get("network"):
        return [payload]
    for platform in ("instagram", "tiktok"):
        if platform in payload:
            value = payload[platform]
            if isinstance(value, dict) and not any(
                key in value for key in ("posts", "items", "content")
            ):
                value = [value]
            elif isinstance(value, dict):
                value = value.get("posts") or value.get("items") or value.get("content") or []
            if not isinstance(value, list):
                raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_PLATFORM_POSTS")
            return [
                {**_require_record(record), "platform": platform}
                for record in value
            ]
    raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_POSTS_MISSING")


def _require_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceAdapterError("MALFORMED_RESPONSE", "CREATOR_POST")
    return value


def _legacy_discover(
    source: dict[str, Any],
    *,
    limit: int,
    feed_xml: str | None,
    metadata: Any,
    fetcher: Callable[[str], str] | None,
    resolver: Callable[..., list[Any]] | None,
    timeout: float,
    max_response_bytes: int,
) -> list[DiscoveredContent]:
    kind = str(source.get("kind") or "").strip().lower()
    adapter = get_source_adapter(kind)
    return adapter.discover(
        source,
        limit=limit,
        feed_xml=feed_xml,
        metadata=metadata,
        fetcher=fetcher,
        resolver=resolver,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )


def discover_source_result(
    source: dict[str, Any],
    *,
    limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
    feed_xml: str | None = None,
    metadata: Any = None,
    fetcher: Callable[[str], str] | None = None,
    resolver: Callable[..., list[Any]] | None = None,
    timeout: float = 15.0,
    max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
) -> DiscoveryResult:
    try:
        items = _legacy_discover(
            source,
            limit=limit,
            feed_xml=feed_xml,
            metadata=metadata,
            fetcher=fetcher,
            resolver=resolver,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        omitted = int(getattr(items, "omitted_items", 0))
        return DiscoveryResult(tuple(items), omitted_items=omitted)
    except SourceAdapterError as exc:
        return DiscoveryResult((), "BLOCKED" if exc.blocked else "FAILED", exc.category)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            category = "ACCESS_RESTRICTED"
            status = "BLOCKED"
        elif exc.code == 429 or exc.code >= 500:
            category = "TRANSIENT"
            status = "FAILED"
        else:
            category = "TRANSIENT"
            status = "FAILED"
        return DiscoveryResult((), status, category)
    except (ET.ParseError, ValueError) as exc:
        if isinstance(exc, SourceAdapterError):
            return DiscoveryResult((), "FAILED", exc.category)
        return DiscoveryResult((), "FAILED", "MALFORMED_RESPONSE")
    except TimeoutError:
        return DiscoveryResult((), "FAILED", "TRANSIENT")
    except Exception:
        return DiscoveryResult((), "FAILED", "SOURCE_FAILURE")


def discover_source(
    source: dict[str, Any],
    *,
    limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
    feed_xml: str | None = None,
    metadata: Any = None,
    fetcher: Callable[[str], str] | None = None,
    resolver: Callable[..., list[Any]] | None = None,
    timeout: float = 15.0,
    max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
) -> list[DiscoveredContent]:
    result = discover_source_result(
        source,
        limit=limit,
        feed_xml=feed_xml,
        metadata=metadata,
        fetcher=fetcher,
        resolver=resolver,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    if result.status != "OK":
        raise SourceAdapterError(result.error_category or "SOURCE_FAILURE")
    return DiscoveredContentBatch(result.items, omitted_items=result.omitted_items)


def get_source_adapter(kind: str) -> SourceAdapter:
    normalized = str(kind or "").strip().lower()
    adapters: dict[str, SourceAdapter] = {
        YouTubeChannelAdapter.kind: YouTubeChannelAdapter(),
        PodcastRssAdapter.kind: PodcastRssAdapter(),
        PublicCreatorAccountsAdapter.kind: PublicCreatorAccountsAdapter(),
    }
    try:
        return adapters[normalized]
    except KeyError as exc:
        raise SourceAdapterError("UNSUPPORTED", f"kind:{normalized}") from exc


def scheduler_ingest_plan(content: DiscoveredContent) -> dict[str, Any]:
    if content.platform == "podcast_rss":
        return {
            "action": "RESOLVE_PLATFORM_TRANSCRIPT_THEN_AUDIO",
            "download_media": False,
            "prefer_audio_only": True,
            "podcast_audio_url_available": bool(content.media_url),
            "duration_seconds": content.duration_seconds,
        }
    if content.platform == "youtube":
        return {
            "action": "PROBE_PLATFORM_TRANSCRIPT",
            "download_media": False,
        }
    return {
        "action": "DISCOVERY_ONLY",
        "download_media": False,
        "reason": "PUBLIC_CREATOR_METADATA_ONLY",
    }


def plan_ingest(
    source: dict[str, Any],
    content: DiscoveredContent,
    *,
    youtube_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    if youtube_metadata is not None and content.platform == "youtube":
        from dichiarazioni_pubbliche.source_watcher import plan_ingest as legacy_plan

        return legacy_plan(source, content, youtube_metadata=youtube_metadata)
    return scheduler_ingest_plan(content)


def filter_content(source: dict[str, Any], items: list[DiscoveredContent]) -> list[DiscoveredContent]:
    return _legacy_filter_discovered_content(source, items)


__all__ = [
    "DiscoveredContent",
    "DiscoveredContentBatch",
    "DiscoveryResult",
    "MAX_DISCOVERY_RESPONSE_BYTES",
    "MAX_DISCOVERED_ITEMS_PER_SOURCE",
    "SUPPORTED_SOURCE_KINDS",
    "SourceAdapter",
    "SourceAdapterError",
    "YouTubeChannelAdapter",
    "PodcastRssAdapter",
    "PublicCreatorAccountsAdapter",
    "discover_source",
    "discover_source_result",
    "filter_content",
    "get_source_adapter",
    "plan_ingest",
    "scheduler_ingest_plan",
]
