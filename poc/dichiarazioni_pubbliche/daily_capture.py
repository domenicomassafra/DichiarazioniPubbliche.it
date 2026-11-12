"""DP-638 — discovery over the source registry and capture of one item.

Discovery asks each configured feed for its public items; capture turns one item
into text: the article body, the platform captions, or a transcription.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.caption_adapter import CaptionSegment, parse_youtube_json3
from dichiarazioni_pubbliche.daily_config import DailyConfig, SourceSpec
from dichiarazioni_pubbliche.daily_model import ModelClient, ModelReply, fetch_text
from dichiarazioni_pubbliche.daily_text import DailyMachineError, html_to_text, sha256_text
from dichiarazioni_pubbliche.source_adapters import DiscoveredContent, discover_source

# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DiscoveredItem:
    source: SourceSpec
    content: DiscoveredContent

    @property
    def published_day(self) -> str:
        value = (self.content.published_at or "").strip()
        if not value:
            return date.today().isoformat()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return date.today().isoformat()


def discover(
    config: DailyConfig,
    *,
    fetcher: Callable[[str], str] | None = None,
    skip_sources: Iterable[str] = (),
) -> tuple[list[DiscoveredItem], list[dict[str, str]]]:
    skipped = set(skip_sources)
    cap = config.limit("max_items_per_source", 3)
    items: list[DiscoveredItem] = []
    failures: list[dict[str, str]] = []
    for source in config.sources:
        if source.id in skipped:
            continue
        try:
            discovered = discover_source(
                source.adapter_payload(),
                limit=max(min(source.max_items, cap), 1),
                fetcher=fetcher,
            )
        except Exception as exc:  # a single broken feed never stops the run
            failures.append({"source_id": source.id, "error": type(exc).__name__})
            continue
        for content in discovered:
            items.append(DiscoveredItem(source=source, content=content))
    # The processing budget must not discard discoveries before persistence.
    return items, failures



# --------------------------------------------------------------------------
_VTT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(?:\d{2}:\d{2}:\d{2}\.\d{3})?", re.MULTILINE)


def parse_vtt(payload: str) -> list[CaptionSegment]:
    segments: list[CaptionSegment] = []
    start_ms = 0
    seen: set[str] = set()
    for block in re.split(r"\r?\n\r?\n", payload or ""):
        match = _VTT_TIME.search(block)
        if not match:
            continue
        start_ms = (
            int(match.group(1)) * 3600_000
            + int(match.group(2)) * 60_000
            + int(match.group(3)) * 1000
            + int(match.group(4))
        )
        lines = [
            line
            for line in block[match.end() :].splitlines()
            if line.strip() and "-->" not in line and not _VTT_TIME.match(line)
        ]
        text = html.unescape(" ".join(" ".join(lines).split()))
        text = re.sub(r"<[^>]+>", "", text).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        segments.append(
            CaptionSegment(
                segment_index=len(segments),
                start_ms=start_ms,
                end_ms=start_ms,
                text=text,
            )
        )
    return segments


@dataclass(frozen=True)
class Capture:
    kind: str
    url: str
    body: str
    segments: tuple[CaptionSegment, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def moment_count(self) -> int:
        return len(self.segments)


def _run_command(command: Sequence[str], *, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def capture_youtube(
    item: DiscoveredItem,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run_command,
    workdir: Path | None = None,
    transcriber: Callable[[Path], str] | None = None,
) -> Capture:
    url = item.content.canonical_url
    temporary = Path(workdir or tempfile.mkdtemp(prefix="dp638-yt-"))
    temporary.mkdir(parents=True, exist_ok=True)
    template = str(temporary / "%(id)s.%(ext)s")
    captions: list[CaptionSegment] = []
    method = "captions"
    try:
        runner(
            [
                "yt-dlp",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                "it,it-orig,it.*,en",
                "--sub-format",
                "json3/vtt",
                "--no-warnings",
                "-o",
                template,
                url,
            ],
            timeout=300.0,
        )
        for path in sorted(temporary.glob("*.json3")):
            payload = json.loads(path.read_text("utf-8", "replace") or "{}")
            captions = parse_youtube_json3(payload)
            if captions:
                break
        if not captions:
            for path in sorted(temporary.glob("*.vtt")):
                captions = parse_vtt(path.read_text("utf-8", "replace"))
                if captions:
                    break
        body = "\n".join(segment.text for segment in captions)
        if not captions and transcriber is not None:
            method = "asr"
            audio = temporary / "audio.mp3"
            runner(
                [
                    "yt-dlp",
                    "-f",
                    "bestaudio",
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "5",
                    "--no-warnings",
                    "-o",
                    str(temporary / "audio.%(ext)s"),
                    url,
                ],
                timeout=1800.0,
            )
            body = transcriber(audio)
            captions = [
                CaptionSegment(segment_index=0, start_ms=0, end_ms=0, text=line)
                for line in body.splitlines()
                if line.strip()
            ]
        if not body.strip():
            raise DailyMachineError("CAPTURE_EMPTY_TRANSCRIPT")
        return Capture(
            kind=method,
            url=url,
            body=body,
            segments=tuple(captions),
            metadata={"segment_count": len(captions), "title": item.content.title},
        )
    finally:
        if workdir is None:
            shutil.rmtree(temporary, ignore_errors=True)


def capture_article(
    item: DiscoveredItem,
    *,
    fetcher: Callable[..., tuple[int, str]] = fetch_text,
) -> Capture:
    url = item.content.canonical_url
    status, markup = fetcher(url)
    if status != 200 or not markup:
        raise DailyMachineError(f"CAPTURE_HTTP_{status}")
    body = html_to_text(markup)
    if len(body) < 200:
        raise DailyMachineError("CAPTURE_EMPTY_TEXT")
    return Capture(kind="article", url=url, body=body, metadata={"title": item.content.title})


def capture_item(
    item: DiscoveredItem,
    *,
    article_fetcher: Callable[..., tuple[int, str]] = fetch_text,
    youtube_capture: Callable[..., Capture] = capture_youtube,
) -> Capture:
    if item.source.kind == "youtube_channel" or item.content.platform == "youtube":
        return youtube_capture(item)
    return capture_article(item, fetcher=article_fetcher)
