from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


CLAIM_WINDOW_SCHEMA_VERSION = "claim-window-v2"
DEFAULT_MAX_WINDOW_SECONDS = 45
DEFAULT_MAX_WINDOW_CHARS = 8000
DEFAULT_MAX_GAP_SECONDS = 15

_DECLARATIVE_CUE = re.compile(
    r"\b(?:è|era|sono|siamo|ha|hanno|aveva|avevano|sarà|sarebbe|"
    r"deve|dovrebbe|può|potrebbe|vuole|vogliono|dice|dicono|"
    r"esiste|esistono|c['’]è|ci sono|abbiamo|avremo|fa|fanno)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CanonicalSegmentInput:
    segment_id: str
    segment_index: int
    start_ms: int
    end_ms: int
    text: str
    transcript_status: str
    publication_blocked: bool
    sensitive_signature: tuple[str, ...]


@dataclass(frozen=True)
class ClaimWindow:
    window_index: int
    start_ms: int
    end_ms: int
    segment_ids: tuple[str, ...]
    segment_indices: tuple[int, ...]
    text: str
    input_sha256: str
    text_characters: int
    estimated_input_tokens: int
    contains_publication_blocked_segments: bool
    publication_blocked_segment_count: int
    sensitive_categories: tuple[str, ...]
    priority: str

    def queue_payload(
        self,
        *,
        source_id: str,
        variant_id: str,
        model: str,
        prompt_version: str,
    ) -> dict[str, Any]:
        return {
            "source_id": source_id,
            "variant_id": variant_id,
            "window_schema_version": CLAIM_WINDOW_SCHEMA_VERSION,
            "prompt_version": prompt_version,
            "window_index": self.window_index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "segment_ids": list(self.segment_ids),
            "segment_indices": list(self.segment_indices),
            "input_sha256": self.input_sha256,
            "text_characters": self.text_characters,
            "estimated_input_tokens": self.estimated_input_tokens,
            "contains_publication_blocked_segments": (
                self.contains_publication_blocked_segments
            ),
            "publication_blocked_segment_count": (
                self.publication_blocked_segment_count
            ),
            "sensitive_categories": list(self.sensitive_categories),
            "priority": self.priority,
            "model": model,
            "estimated_cost_usd": 0.0,
        }


def canonical_segment_from_row(row: dict[str, Any]) -> CanonicalSegmentInput:
    signature = row.get("sensitive_signature") or []
    if not isinstance(signature, list):
        signature = []
    return CanonicalSegmentInput(
        segment_id=str(row["id"]),
        segment_index=int(row["segment_index"]),
        start_ms=int(row["start_ms"]),
        end_ms=int(row["end_ms"]),
        text=str(row["canonical_text"]).strip(),
        transcript_status=str(row["transcript_status"]),
        publication_blocked=bool(row["publication_blocked"]),
        sensitive_signature=tuple(str(value) for value in signature),
    )


def _timestamp(ms: int) -> str:
    total_seconds, millis = divmod(max(ms, 0), 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def render_window_text(segments: list[CanonicalSegmentInput]) -> str:
    return "\n".join(
        (
            f"[seg={row.segment_index} "
            f"{_timestamp(row.start_ms)}-{_timestamp(row.end_ms)}] {row.text}"
        )
        for row in segments
        if row.text
    )


def _sensitive_categories(segments: list[CanonicalSegmentInput]) -> tuple[str, ...]:
    categories = set()
    for segment in segments:
        for value in segment.sensitive_signature:
            category = value.split(":", 1)[0].strip()
            if category:
                categories.add(category)
    return tuple(sorted(categories))


def _priority(
    text: str,
    *,
    contains_publication_blocked_segments: bool,
    sensitive_categories: tuple[str, ...],
) -> str:
    declarative = bool(_DECLARATIVE_CUE.search(text))
    has_numeric_signal = "NUMBER" in sensitive_categories or bool(re.search(r"\d", text))
    if declarative and (
        contains_publication_blocked_segments or has_numeric_signal
    ):
        return "HIGH"
    if declarative or contains_publication_blocked_segments or sensitive_categories:
        return "MEDIUM"
    return "LOW"


def _window_hash(segments: list[CanonicalSegmentInput], text: str) -> str:
    material = {
        "schema_version": CLAIM_WINDOW_SCHEMA_VERSION,
        "segments": [
            {
                "id": row.segment_id,
                "index": row.segment_index,
                "start_ms": row.start_ms,
                "end_ms": row.end_ms,
                "status": row.transcript_status,
                "publication_blocked": row.publication_blocked,
                "sensitive_signature": list(row.sensitive_signature),
            }
            for row in segments
        ],
        "text": text,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_claim_windows(
    segments: list[CanonicalSegmentInput],
    *,
    max_window_seconds: int = DEFAULT_MAX_WINDOW_SECONDS,
    max_window_chars: int = DEFAULT_MAX_WINDOW_CHARS,
    max_gap_seconds: int = DEFAULT_MAX_GAP_SECONDS,
) -> list[ClaimWindow]:
    ordered = sorted(segments, key=lambda row: (row.segment_index, row.start_ms))
    if not ordered:
        return []
    max_window_ms = max(max_window_seconds, 1) * 1000
    max_gap_ms = max(max_gap_seconds, 0) * 1000
    max_window_chars = max(max_window_chars, 256)

    groups: list[list[CanonicalSegmentInput]] = []
    current: list[CanonicalSegmentInput] = []
    current_chars = 0

    for segment in ordered:
        if not segment.text:
            continue
        prospective_chars = current_chars + len(segment.text) + (1 if current else 0)
        duration_exceeded = bool(
            current and segment.end_ms - current[0].start_ms > max_window_ms
        )
        gap_exceeded = bool(
            current and segment.start_ms - current[-1].end_ms > max_gap_ms
        )
        chars_exceeded = bool(current and prospective_chars > max_window_chars)
        if duration_exceeded or gap_exceeded or chars_exceeded:
            groups.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += len(segment.text) + (1 if len(current) > 1 else 0)
    if current:
        groups.append(current)

    windows: list[ClaimWindow] = []
    for index, group in enumerate(groups):
        text = render_window_text(group)
        categories = _sensitive_categories(group)
        blocked_count = sum(row.publication_blocked for row in group)
        contains_blocked = blocked_count > 0
        windows.append(
            ClaimWindow(
                window_index=index,
                start_ms=group[0].start_ms,
                end_ms=max(row.end_ms for row in group),
                segment_ids=tuple(row.segment_id for row in group),
                segment_indices=tuple(row.segment_index for row in group),
                text=text,
                input_sha256=_window_hash(group, text),
                text_characters=len(text),
                estimated_input_tokens=max(1, (len(text) + 3) // 4),
                contains_publication_blocked_segments=contains_blocked,
                publication_blocked_segment_count=blocked_count,
                sensitive_categories=categories,
                priority=_priority(
                    text,
                    contains_publication_blocked_segments=contains_blocked,
                    sensitive_categories=categories,
                ),
            )
        )
    return windows
