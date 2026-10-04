from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from dichiarazioni_pubbliche.transcript_contract import sensitive_signature


@dataclass(frozen=True)
class CaptionSegment:
    segment_index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class Chapter:
    start_seconds: int
    title: str


_CHAPTER_LINE = re.compile(
    r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+?)\s*$"
)


def _event_text(event: dict[str, Any]) -> str:
    parts = []
    for seg in event.get("segs") or []:
        text = seg.get("utf8")
        if text:
            parts.append(text)
    value = html.unescape("".join(parts))
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_youtube_json3(payload: dict[str, Any]) -> list[CaptionSegment]:
    rows: list[CaptionSegment] = []
    last_text = None
    for event in payload.get("events") or []:
        if "tStartMs" not in event:
            continue
        text = _event_text(event)
        if not text:
            continue
        start_ms = int(event["tStartMs"])
        duration_ms = int(event.get("dDurationMs") or 0)
        end_ms = start_ms + max(duration_ms, 0)

        # Auto captions can emit an identical event twice during rolling
        # updates. Exact consecutive duplicates do not add evidence.
        if text == last_text:
            continue
        rows.append(
            CaptionSegment(
                segment_index=len(rows),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )
        last_text = text
    return rows


def caption_stats(
    segments: list[CaptionSegment],
    *,
    gazetteer_terms: tuple[str, ...] = (),
) -> dict[str, int]:
    if not segments:
        return {
            "segment_count": 0,
            "text_characters": 0,
            "duration_ms": 0,
            "sensitive_segment_count": 0,
        }
    return {
        "segment_count": len(segments),
        "text_characters": sum(len(row.text) for row in segments),
        "duration_ms": max(row.end_ms for row in segments),
        "sensitive_segment_count": sum(
            bool(sensitive_signature(row.text, gazetteer_terms=gazetteer_terms))
            for row in segments
        ),
    }


def parse_chapters(description: str) -> list[Chapter]:
    chapters: list[Chapter] = []
    for raw_line in description.splitlines():
        match = _CHAPTER_LINE.match(raw_line)
        if not match:
            continue
        hours, minutes, seconds, title = match.groups()
        total = (int(hours) * 3600 if hours else 0) + int(minutes) * 60 + int(seconds)
        chapters.append(Chapter(start_seconds=total, title=title.strip()))
    return chapters
