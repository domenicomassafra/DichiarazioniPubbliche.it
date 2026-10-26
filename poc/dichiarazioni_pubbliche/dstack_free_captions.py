"""Bounded, public-URL caption adapter selected by DStack's audited inventory.

Only the documented anonymous captions JSON interface is supported. Catalog
entries without a tested interface are never considered executable adapters.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dichiarazioni_pubbliche.caption_adapter import CaptionSegment


CATALOG_PATH = Path.home() / ".dstack" / "catalog" / "transcription-services.json"
_CATALOG_SOURCE = "https://github.com/domenicomassafra/dodo-services/issues/280"
_PROVIDER_NAME = "YTTranscript.dev"
_PROVIDER_ORIGIN = "https://yttranscript.dev/"
_CAPTION_ENDPOINT = "https://yttranscript.dev/api/transcript"
_MAX_BYTES = 1_048_576
_MAX_SEGMENTS = 512


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def eligible_youtube_provider(path: Path) -> dict | None:
    """Find a supported candidate in canonical rank order; fail closed."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128_000:
            return None
        raw = path.read_bytes()
        catalog = json.loads(raw)
        if (not isinstance(catalog, dict) or catalog.get("schema_version") != 1
                or catalog.get("source") != _CATALOG_SOURCE
                or not isinstance(catalog.get("services"), list)):
            return None
        candidates = sorted(
            (entry for entry in catalog["services"]
             if isinstance(entry, dict) and entry.get("platform") == "youtube"
             and type(entry.get("rank")) is int and entry["rank"] > 0),
            key=lambda entry: entry["rank"],
        )
        for row in candidates:
            if (row.get("name") == _PROVIDER_NAME
                    and row.get("url") == _PROVIDER_ORIGIN
                    and row.get("identity") == "resolved"
                    and row.get("evidence") == "http_captions_observed"):
                return {"name": _PROVIDER_NAME, "rank": row["rank"],
                        "catalog_sha256": hashlib.sha256(raw).hexdigest()}
    except (OSError, ValueError, TypeError):
        return None
    return None


def fetch_captions_json(video_url: str, *, timeout_seconds: int = 10) -> bytes:
    """GET captions only: never request the provider's ASR or account endpoints."""
    if not re.fullmatch(r"https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}", video_url):
        raise ValueError("FREE_CAPTION_URL_INVALID")
    query = urlencode({"url": video_url, "source": "captions", "format": "json"})
    request = Request(f"{_CAPTION_ENDPOINT}?{query}",
                      headers={"Accept": "application/json", "User-Agent": "DP-caption-reader/1"})
    with build_opener(_NoRedirect()).open(request, timeout=timeout_seconds) as response:
        if response.status != 200 or "json" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("FREE_CAPTION_NOT_JSON")
        body = response.read(_MAX_BYTES + 1)
    if len(body) > _MAX_BYTES:
        raise ValueError("FREE_CAPTION_OVERSIZED")
    return body


def parse_captions_json(raw: bytes, *, video_id: str,
                        expected_language: str) -> tuple[str, tuple[CaptionSegment, ...]]:
    if not isinstance(raw, bytes) or len(raw) > _MAX_BYTES:
        raise ValueError("FREE_CAPTION_BODY_INVALID")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("FREE_CAPTION_JSON_INVALID") from exc
    language = payload.get("language") if isinstance(payload, dict) else None
    if (not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", language)
            or language != expected_language
            or payload.get("videoId") != video_id):
        raise ValueError("FREE_CAPTION_ORIGIN_MISMATCH")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not 0 < len(rows) <= _MAX_SEGMENTS:
        raise ValueError("FREE_CAPTION_SEGMENTS_INVALID")
    parsed: list[CaptionSegment] = []
    previous_end = 0
    for entry in rows:
        if (not isinstance(entry, dict) or not isinstance(entry.get("text"), str)
                or entry.get("lang") != language
                or type(entry.get("offset")) is not int
                or type(entry.get("duration")) is not int):
            raise ValueError("FREE_CAPTION_SEGMENT_INVALID")
        start = entry["offset"]
        end = start + entry["duration"]
        content = " ".join(entry["text"].split())
        if (start < previous_end or start < 0 or end <= start
                or end >= 2**63 or not content):
            raise ValueError("FREE_CAPTION_TIME_OR_TEXT_INVALID")
        parsed.append(CaptionSegment(len(parsed), start, end, content))
        previous_end = end
    return language, tuple(parsed)


def attempt_capture(
    video_url: str, probe: Any, *, catalog_path: Path,
    validate_video_id: Callable[[str], str],
) -> tuple[Any | None, str]:
    """Resolve the single audited provider before native caption extraction.

    Return (caption, failure category). A missing DStack inventory disables this
    adapter; an invalid video URL fails before invoking either extraction path.
    """
    provider = eligible_youtube_provider(catalog_path)
    if provider is None:
        return None, ""
    video_id = validate_video_id(video_url)
    try:
        if probe.kind not in {"manual_caption", "automatic_caption"}:
            raise ValueError("FREE_CAPTION_PROBE_INVALID")
        language = probe.language.removesuffix("-orig")
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", language):
            raise ValueError("FREE_CAPTION_LANGUAGE_INVALID")
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        raw = fetch_captions_json(canonical_url)
        actual_language, segments = parse_captions_json(
            raw, video_id=video_id, expected_language=language,
        )
        raw_text = "\n".join(segment.text for segment in segments)
        # Late import leaves the resolver and its native fallback as the only
        # owners of the caption contract; this module owns provider semantics.
        from dichiarazioni_pubbliche.platform_transcript import CaptionCapture, CaptionProbe

        return CaptionCapture(
            raw_bytes=raw,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_text=raw_text,
            raw_text_sha256=hashlib.sha256(raw_text.encode()).hexdigest(),
            segments=segments,
            probe=CaptionProbe("automatic_caption", actual_language),
            provenance={
                "method": "yttranscript.dev",
                "method_version": "anonymous-captions-json-v1",
                "raw_format": "yttranscript.dev-json-v1",
                "access_path": "DSTACK_FREE_PUBLIC_CAPTION",
                "source_url": video_url,
                "video_id": video_id,
                "original_language": actual_language,
                "catalog_sha256": provider["catalog_sha256"],
                "catalog_rank": str(provider["rank"]),
            },
        ), ""
    except Exception as exc:
        # Never submit a paid job or retry around quota, 429 or a challenge.
        failure = (
            f"HTTP_{exc.code}" if isinstance(exc, HTTPError)
            else "TIMEOUT" if isinstance(exc, TimeoutError)
            else "INVALID_CAPTIONS" if isinstance(exc, ValueError)
            else "UNAVAILABLE"
        )
        return None, failure
