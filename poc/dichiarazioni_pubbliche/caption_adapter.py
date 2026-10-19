from __future__ import annotations

import html
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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


def parse_transcript_api_snippets(rows: list[dict[str, Any]]) -> list[CaptionSegment]:
    """Validate the donor timebase before converting seconds to integer ms.

    A malformed, reordered or overlapping result cannot be used as quotation
    evidence. The resolver can still try the independent JSON3 capture path.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("TRANSCRIPT_API_EMPTY")
    segments: list[CaptionSegment] = []
    previous_end = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            raise ValueError("TRANSCRIPT_API_INVALID_SNIPPET")
        try:
            start = Decimal(str(row["start"]))
            duration = Decimal(str(row["duration"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise ValueError("TRANSCRIPT_API_INVALID_TIME") from exc
        if not start.is_finite() or not duration.is_finite() or start < 0 or duration <= 0:
            raise ValueError("TRANSCRIPT_API_INVALID_TIME")
        start_ms = int((start * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        end_ms = int(((start + duration) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if start_ms < previous_end or end_ms <= start_ms or end_ms >= 2**63:
            raise ValueError("TRANSCRIPT_API_TIME_CONFLICT")
        text = re.sub(r"\s+", " ", html.unescape(row["text"])).strip()
        if not text:
            raise ValueError("TRANSCRIPT_API_EMPTY_TEXT")
        segments.append(CaptionSegment(len(segments), start_ms, end_ms, text))
        previous_end = end_ms
    return segments


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
