from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.caption_adapter import (
    CaptionSegment,
    Chapter,
    caption_stats,
    parse_chapters,
    parse_youtube_json3,
)
from dichiarazioni_pubbliche.source_watcher import fetch_text, parse_podcast_rss
from dichiarazioni_pubbliche.transcript_contract import sensitive_signature


DEFAULT_MAX_WINDOW_SECONDS = 45

_DECLARATIVE_CUE = re.compile(
    r"\b(?:è|era|sono|siamo|ha|hanno|aveva|avevano|sarà|sarebbe|"
    r"deve|dovrebbe|può|potrebbe|vuole|vogliono|dice|dicono|"
    r"esiste|esistono|c['’]è|ci sono|abbiamo|avremo|fa|fanno)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PreparedWindow:
    window_index: int
    chapter_index: int | None
    start_ms: int
    end_ms: int
    first_segment_index: int
    last_segment_index: int
    segment_count: int
    text_characters: int
    text_sha256: str
    sensitive_signature: tuple[str, ...]
    cue_score: int
    priority: str


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _chapter_index(start_ms: int, chapters: list[Chapter]) -> int | None:
    if not chapters:
        return None
    start_seconds = start_ms / 1000
    selected = 0
    for index, chapter in enumerate(chapters):
        if chapter.start_seconds <= start_seconds:
            selected = index
        else:
            break
    return selected


def _priority(text: str, signature: tuple[str, ...]) -> tuple[int, str]:
    score = 0
    if signature:
        score += 2
    if _DECLARATIVE_CUE.search(text):
        score += 1
    if len(text) >= 160:
        score += 1
    if re.search(r"\d", text):
        score += 1
    if score >= 4:
        return score, "HIGH"
    if score >= 2:
        return score, "MEDIUM"
    return score, "LOW"


def build_candidate_windows(
    segments: list[CaptionSegment],
    *,
    chapters: list[Chapter] | None = None,
    max_window_seconds: int = DEFAULT_MAX_WINDOW_SECONDS,
) -> list[PreparedWindow]:
    if not segments:
        return []
    chapters = chapters or []
    max_window_ms = max(max_window_seconds, 1) * 1000
    groups: list[list[CaptionSegment]] = []
    current: list[CaptionSegment] = []
    current_chapter: int | None = None
    window_start = 0

    for segment in segments:
        chapter = _chapter_index(segment.start_ms, chapters)
        should_split = bool(
            current
            and (
                chapter != current_chapter
                or segment.start_ms - window_start >= max_window_ms
            )
        )
        if should_split:
            groups.append(current)
            current = []
        if not current:
            current_chapter = chapter
            window_start = segment.start_ms
        current.append(segment)
    if current:
        groups.append(current)

    windows: list[PreparedWindow] = []
    for index, group in enumerate(groups):
        text = " ".join(item.text for item in group).strip()
        signature = tuple(sorted(sensitive_signature(text)))
        score, priority = _priority(text, signature)
        windows.append(
            PreparedWindow(
                window_index=index,
                chapter_index=_chapter_index(group[0].start_ms, chapters),
                start_ms=group[0].start_ms,
                end_ms=max(item.end_ms for item in group),
                first_segment_index=group[0].segment_index,
                last_segment_index=group[-1].segment_index,
                segment_count=len(group),
                text_characters=len(text),
                text_sha256=_sha256_text(text),
                sensitive_signature=signature,
                cue_score=score,
                priority=priority,
            )
        )
    return windows


def _private_segments_payload(segments: list[CaptionSegment]) -> dict[str, Any]:
    rows = []
    for item in segments:
        rows.append(
            {
                "segment_index": item.segment_index,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "text": item.text,
                "sensitive_signature": list(sensitive_signature(item.text)),
            }
        )
    return {"schema_version": 1, "segments": rows}


def _normalized_segments_sha256(segments: list[CaptionSegment]) -> str:
    canonical = json.dumps(
        [
            {
                "segment_index": item.segment_index,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "text": item.text,
            }
            for item in segments
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(canonical)


def _public_sensitive_categories(signature: tuple[str, ...]) -> list[str]:
    return sorted({item.split(":", 1)[0] for item in signature if item})


def _display_private_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    home = Path.home().resolve()
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return "<private-runtime>"
    return f"~/{relative.as_posix()}"


def prepare_longform_caption(
    *,
    caption_path: Path,
    private_dir: Path,
    public_output: Path,
    source_id: str,
    external_id: str,
    canonical_url: str,
    title: str,
    published_at: str,
    duration_seconds: int | None = None,
    chapters: list[Chapter] | None = None,
    registry_caption_sha256: str | None = None,
    max_window_seconds: int = DEFAULT_MAX_WINDOW_SECONDS,
    audit_id: str | None = None,
) -> dict[str, Any]:
    raw_bytes = caption_path.read_bytes()
    raw_sha256 = _sha256_bytes(raw_bytes)
    raw = json.loads(raw_bytes)
    segments = parse_youtube_json3(raw)
    stats = caption_stats(segments)
    chapters = chapters or []
    windows = build_candidate_windows(
        segments,
        chapters=chapters,
        max_window_seconds=max_window_seconds,
    )
    normalized_sha256 = _normalized_segments_sha256(segments)
    acquired_at = datetime.now(timezone.utc).isoformat()

    private_dir.mkdir(parents=True, exist_ok=True)
    private_segments = _private_segments_payload(segments)
    (private_dir / "youtube-auto-it-orig.segments.json").write_text(
        json.dumps(private_segments, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    private_receipt = {
        "schema_version": 1,
        "source_id": source_id,
        "external_id": external_id,
        "canonical_url": canonical_url,
        "caption_kind": "YOUTUBE_AUTO_CAPTION",
        "language": "it-orig",
        "acquired_at": acquired_at,
        "raw_caption_sha256": raw_sha256,
        "raw_caption_bytes": len(raw_bytes),
        "normalized_segments_sha256": normalized_sha256,
        "segment_count": stats["segment_count"],
        "text_characters": stats["text_characters"],
        "coverage_ms": stats["duration_ms"],
        "sensitive_segment_count": stats["sensitive_segment_count"],
    }
    (private_dir / "receipt.json").write_text(
        json.dumps(private_receipt, ensure_ascii=False, indent=2) + "\n"
    )

    priority_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for window in windows:
        priority_counts[window.priority] += 1

    audit_id = audit_id or f"{source_id}-{external_id}"
    scaffold: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": audit_id,
        "content": {
            "source_id": source_id,
            "platform": "youtube",
            "external_id": external_id,
            "canonical_url": canonical_url,
            "title": title,
            "published_at": published_at,
            "duration_seconds": duration_seconds,
        },
        "transcript_provenance": {
            "source_kind": "YOUTUBE_AUTO_CAPTION",
            "language": "it-orig",
            "public_full_transcript_committed": False,
            "private_runtime_dir": _display_private_path(private_dir),
            "raw_caption_format": "json3",
            "raw_caption_sha256": raw_sha256,
            "raw_caption_bytes": len(raw_bytes),
            "normalized_segments_sha256": normalized_sha256,
            "segment_count": stats["segment_count"],
            "text_characters": stats["text_characters"],
            "coverage_seconds": round(stats["duration_ms"] / 1000, 3),
            "sensitive_segment_count": stats["sensitive_segment_count"],
            "acquired_at": acquired_at,
            "source_mutability": {
                "registry_proof_sha256": registry_caption_sha256,
                "matches_registry_proof": (
                    raw_sha256 == registry_caption_sha256
                    if registry_caption_sha256
                    else None
                ),
                "policy": "VERSION_EACH_PLATFORM_CAPTION_CAPTURE_BY_HASH_AND_TIME",
            },
        },
        "chapters": [
            {"chapter_index": index, **asdict(chapter)}
            for index, chapter in enumerate(chapters)
        ],
        "claim_candidate_windows": {
            "strategy": "chapter-aware bounded windows",
            "max_window_seconds": max_window_seconds,
            "window_count": len(windows),
            "priority_counts": priority_counts,
            "contains_text": False,
            "windows": [
                {
                    **asdict(window),
                    "sensitive_signature": _public_sensitive_categories(
                        window.sensitive_signature
                    ),
                }
                for window in windows
            ],
        },
        "pipeline": {
            "discovery": "DONE",
            "platform_caption_acquisition": "DONE",
            "caption_normalization": "DONE",
            "claim_candidate_windowing": "DONE",
            "claim_extraction": "BLOCKED",
            "claim_extraction_blocker": (
                "Official OmniRoute 3.8.50 production route "
                "antigravity/gemini-3.8-flash-tiered rejects non-trivial chat "
                "requests; local-fork runtime is not permitted by runtime policy."
            ),
            "secondary_asr": "NOT_STARTED_UNTIL_MATERIAL_CLAIMS_EXIST",
            "evidence_retrieval": "NOT_STARTED",
            "verification": "NOT_STARTED",
            "publication": "POLICY_HOLD",
        },
        "claims": [],
        "findings": [],
        "policy": {
            "aggregate_person_score": False,
            "overall_person_verdict": False,
            "no_finding_without_claim_extraction": True,
            "sensitive_span_requires_independent_transcript_check": True,
        },
    }

    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_text(json.dumps(scaffold, ensure_ascii=False, indent=2) + "\n")
    return scaffold


def _rss_metadata(
    *,
    rss_url: str,
    source_id: str,
    title_contains: str,
) -> tuple[str, str, int | None, list[Chapter]]:
    items = parse_podcast_rss(fetch_text(rss_url), source_id)
    for item in items:
        if title_contains.casefold() in item.title.casefold():
            return (
                item.title,
                item.published_at,
                item.duration_seconds,
                parse_chapters(item.description or ""),
            )
    raise ValueError(f"No RSS item contains: {title_contains}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a long-form caption for claim extraction without publishing transcript text."
    )
    parser.add_argument("--caption-json3", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--canonical-url", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--published-at", default="")
    parser.add_argument("--duration-seconds", type=int)
    parser.add_argument("--rss-url")
    parser.add_argument("--rss-title-contains")
    parser.add_argument("--registry-caption-sha256")
    parser.add_argument("--max-window-seconds", type=int, default=DEFAULT_MAX_WINDOW_SECONDS)
    parser.add_argument("--audit-id")
    args = parser.parse_args()

    title = args.title
    published_at = args.published_at
    duration_seconds = args.duration_seconds
    chapters: list[Chapter] = []
    if args.rss_url and args.rss_title_contains:
        rss_title, rss_published, rss_duration, chapters = _rss_metadata(
            rss_url=args.rss_url,
            source_id=args.source_id,
            title_contains=args.rss_title_contains,
        )
        title = title or rss_title
        published_at = published_at or rss_published
        duration_seconds = duration_seconds or rss_duration

    scaffold = prepare_longform_caption(
        caption_path=args.caption_json3,
        private_dir=args.private_dir,
        public_output=args.public_output,
        source_id=args.source_id,
        external_id=args.external_id,
        canonical_url=args.canonical_url,
        title=title,
        published_at=published_at,
        duration_seconds=duration_seconds,
        chapters=chapters,
        registry_caption_sha256=args.registry_caption_sha256,
        max_window_seconds=args.max_window_seconds,
        audit_id=args.audit_id,
    )
    summary = {
        "audit_id": scaffold["audit_id"],
        "segment_count": scaffold["transcript_provenance"]["segment_count"],
        "coverage_seconds": scaffold["transcript_provenance"]["coverage_seconds"],
        "sensitive_segment_count": scaffold["transcript_provenance"][
            "sensitive_segment_count"
        ],
        "window_count": scaffold["claim_candidate_windows"]["window_count"],
        "priority_counts": scaffold["claim_candidate_windows"]["priority_counts"],
        "caption_matches_registry_proof": scaffold["transcript_provenance"][
            "source_mutability"
        ]["matches_registry_proof"],
        "claim_extraction": scaffold["pipeline"]["claim_extraction"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
