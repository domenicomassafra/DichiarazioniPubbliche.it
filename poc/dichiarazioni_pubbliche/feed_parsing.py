"""Strict, bounded XML feed decoding with an optional feedparser 6.0.14 backend.

The stdlib path preserves the contributor install without optional dependencies.
ElementTree is deliberately retained as a structural gate: feedparser is permissive
of broken XML and must never turn a malformed response into a valid discovery.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

try:
    import feedparser as _feedparser
except ImportError:  # The default installation is intentionally stdlib-only.
    _feedparser = None


ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
RSS1 = "{http://purl.org/rss/1.0/}"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
DC = "{http://purl.org/dc/elements/1.1/}"
MAX_FEED_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class FeedEntry:
    stable_id: str
    link: str
    title: str
    published: str
    author: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    duration_seconds: int | None = None
    description: str | None = None
    youtube_id: str | None = None


def _duration(value: str) -> int | None:
    """Support iTunes seconds and HH:MM:SS without changing existing seconds."""
    value = value.strip()
    if value.isdecimal():
        return int(value)
    fields = value.split(":")
    if len(fields) in {2, 3} and all(part.isdecimal() for part in fields):
        if any(int(part) >= 60 for part in fields[1:]):
            return None
        result = 0
        for part in fields:
            result = result * 60 + int(part)
        return result
    return None


def _podcast_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError, OverflowError):
        return raw


def _feedparser_entries(xml_text: str, count: int, family: str):
    if _feedparser is None:
        return None
    parsed = _feedparser.parse(xml_text)
    expected = {"youtube": {"atom10"}, "podcast": {"rss20"}, "public": {"rss20", "rss10", "atom10"}}
    if parsed.get("bozo") or parsed.get("version") not in expected[family]:
        raise ValueError("FEEDPARSER_MALFORMED")
    if len(parsed.entries) != count:
        raise ValueError("FEEDPARSER_ENTRY_MISMATCH")
    return parsed.entries


def parse_feed(xml_text: str, family: str) -> list[FeedEntry]:
    """Parse only known RSS1/RSS2/Atom/YouTube formats without fetching links."""
    if family not in {"youtube", "podcast", "public"}:
        raise ValueError("UNSUPPORTED_FEED_FAMILY")
    if not isinstance(xml_text, str) or len(xml_text.encode("utf-8")) > MAX_FEED_BYTES:
        raise ValueError("FEED_TOO_LARGE")
    # No DTDs are needed by these feeds; refuse entity declarations before parsing.
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml_text, flags=re.IGNORECASE):
        raise ValueError("FEED_DTD_REJECTED")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError("FEED_XML_INVALID") from exc

    rows: list[FeedEntry] = []
    if family == "youtube":
        if root.tag != f"{ATOM}feed":
            raise ValueError("YOUTUBE_ATOM_EXPECTED")
        titles_by_id: dict[str, str] = {}
        for node in root.findall(f"{ATOM}entry"):
            video_ids = node.findall(f"{YT}videoId")
            if len(video_ids) > 1:
                raise ValueError("YOUTUBE_ENTRY_VIDEO_ID_AMBIGUOUS")
            video_id = ((video_ids[0].text if video_ids else "") or "").strip()
            if not video_id:
                continue
            title = node.findtext(f"{ATOM}title") or ""
            if video_id in titles_by_id and titles_by_id[video_id] != title:
                raise ValueError("YOUTUBE_ENTRY_TITLE_CONFLICT")
            titles_by_id[video_id] = title
            alternate = node.find(f"{ATOM}link[@rel='alternate']")
            href = alternate.attrib.get("href") if alternate is not None else None
            rows.append(FeedEntry(
                stable_id=video_id,
                youtube_id=video_id,
                link=href or f"https://www.youtube.com/watch?v={video_id}",
                title=node.findtext(f"{ATOM}title") or "",
                published=node.findtext(f"{ATOM}published") or "",
                author=node.findtext(f"{ATOM}author/{ATOM}name"),
            ))
    elif family == "podcast":
        if root.tag != "rss":
            raise ValueError("RSS_EXPECTED")
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS_CHANNEL_MISSING")
        author = channel.findtext(f"{ITUNES}author") or channel.findtext("title")
        for node in channel.findall("item"):
            enclosure = node.find("enclosure")
            media_url = enclosure.attrib.get("url") if enclosure is not None else None
            media_type = enclosure.attrib.get("type") if enclosure is not None else None
            guid = (node.findtext("guid") or "").strip()
            rows.append(FeedEntry(
                stable_id=guid or (media_url or "").strip(),
                link=(node.findtext("link") or "").strip() or (media_url or "").strip(),
                title=(node.findtext("title") or "").strip(),
                published=_podcast_date((node.findtext("pubDate") or "").strip()),
                author=author,
                media_url=media_url,
                media_type=media_type,
                duration_seconds=_duration(node.findtext(f"{ITUNES}duration") or ""),
                description=(node.findtext("description") or "").strip(),
            ))
    elif root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS_CHANNEL_MISSING")
        author = channel.findtext("title")
        for node in channel.findall("item"):
            rows.append(FeedEntry(
                stable_id=(node.findtext("guid") or "").strip(),
                link=(node.findtext("link") or "").strip(),
                title=node.findtext("title") or "",
                published=(node.findtext("pubDate") or "").strip(),
                author=author,
            ))
    elif root.tag == f"{RDF}RDF":
        author = root.findtext(f"{RSS1}channel/{RSS1}title")
        for node in root.findall(f"{RSS1}item"):
            rows.append(FeedEntry(
                stable_id=node.attrib.get(f"{RDF}about", "").strip(),
                link=(node.findtext(f"{RSS1}link") or "").strip(),
                title=node.findtext(f"{RSS1}title") or "",
                published=(node.findtext(f"{DC}date") or "").strip(),
                author=author,
            ))
    elif root.tag == f"{ATOM}feed":
        author = root.findtext(f"{ATOM}title")
        for node in root.findall(f"{ATOM}entry"):
            alternate = next((
                link.attrib.get("href", "") for link in node.findall(f"{ATOM}link")
                if link.attrib.get("rel", "alternate") == "alternate"
            ), "")
            rows.append(FeedEntry(
                stable_id=(node.findtext(f"{ATOM}id") or "").strip(),
                link=alternate.strip(),
                title=node.findtext(f"{ATOM}title") or "",
                published=(node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated") or "").strip(),
                author=node.findtext(f"{ATOM}author/{ATOM}name") or author,
            ))
    else:
        raise ValueError("RSS_OR_ATOM_EXPECTED")

    # XML supplies the stable identity and original timezone; feedparser provides
    # feed-aware metadata decoding, especially iTunes duration and Atom authors.
    parsed_entries = _feedparser_entries(xml_text, len(rows), family)
    if parsed_entries is None:
        return rows
    enriched: list[FeedEntry] = []
    for row, entry in zip(rows, parsed_entries):
        duration = row.duration_seconds
        if family == "podcast" and duration is None:
            duration = _duration(str(entry.get("itunes_duration") or ""))
        # A missing original link may be recovered only from explicit alternate links;
        # opaque GUIDs alone never authorize inventing or following a locator.
        enriched.append(FeedEntry(
            stable_id=row.stable_id,
            link=row.link,
            title=entry.get("title") or row.title,
            published=row.published or entry.get("published") or entry.get("updated") or "",
            author=row.author or entry.get("author"),
            media_url=row.media_url,
            media_type=row.media_type,
            duration_seconds=duration,
            description=row.description,
            youtube_id=row.youtube_id,
        ))
    return enriched
