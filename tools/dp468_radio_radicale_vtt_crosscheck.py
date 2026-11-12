#!/usr/bin/env python3
"""Compare held Senato quote pins with Radio Radicale's timed video captions.

Captions are an imperfect, potentially machine-generated transcription of a
Senato video feed. Even an exact token match is evidence only, never approval.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

from dichiarazioni_pubbliche.senato_akoma_stenographic import import_senato_akoma_stenographic
from tools.dp468_radio_radicale_crosscheck import PROFILES, crosscheck, fetch_index
from tools.dp468_senato_profile_crosscheck import MANIFEST, _ROW, read_batch
from tools.dp468_senato_stenogram_crosscheck import (
    SOURCE_BLOB_SHA1,
    SOURCE_URL,
    fetch_html_or_xml,
)

_VTT_LIST = re.compile(r'"vtt":(\[[^\]]+\])')
_CUE_TIME = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})"
)


def _seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _tokens(value: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKD", value.casefold()))


def _longest_consecutive(quote: list[str], captions: list[str]) -> int:
    # Contiguous evidence is inspectable; generic word overlap is too weak.
    longest = 0
    locations: dict[tuple[str, ...], list[int]] = {}
    for j in range(len(captions) - 2):
        locations.setdefault(tuple(captions[j:j + 3]), []).append(j)
    for i in range(len(quote) - 2):
        for j in locations.get(tuple(quote[i:i + 3]), ()):
            size = 3
            while (
                i + size < len(quote)
                and j + size < len(captions)
                and quote[i + size] == captions[j + size]
            ):
                size += 1
            longest = max(longest, size)
    return longest


def _caption_urls(html: str) -> list[str]:
    match = _VTT_LIST.search(html)
    if match is None:
        raise ValueError("DP468_VTT_PLAYLIST_MISSING")
    try:
        values = json.loads(match[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("DP468_VTT_PLAYLIST_INVALID") from exc
    if (
        not isinstance(values, list) or not 1 <= len(values) <= 12
        or any(not isinstance(url, str) for url in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("DP468_VTT_PLAYLIST_INVALID")
    for url in values:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.radioradicale.it"
            or not re.fullmatch(r"/trascrizioni/(?:[0-9]+/)+[0-9]+\.vtt", parsed.path)
            or parsed.query or parsed.fragment
        ):
            raise ValueError("DP468_VTT_URL_INVALID")
    return values


def _segment_window(html: str, segment_url: str) -> tuple[int, float, float]:
    if not segment_url.startswith("https://www.radioradicale.it/scheda/760686/seduta-310a-xix-legislatura#i="):
        raise ValueError("DP468_VTT_SEGMENT_INVALID")
    intervention_id = segment_url.rsplit("#i=", 1)[-1]
    if re.fullmatch(r"[0-9]+", intervention_id) is None:
        raise ValueError("DP468_VTT_SEGMENT_INVALID")
    segment = re.search(
        r'<li class="[^"]*\bintervento\b[^"]*\bint' + intervention_id +
        r'\b[^"]*">(.*?)</li>', html, re.S,
    )
    player = re.search(
        r'"int' + intervention_id + r'":\{"file":([0-9]+),"offset":([0-9]+)',
        html,
    )
    if segment is None or player is None:
        raise ValueError("DP468_VTT_SEGMENT_MISSING")
    duration = re.search(r'<span class="duration">(\d{1,2}:\d{2}:\d{2})</span>', segment[1])
    if duration is None or segment_url not in segment[1]:
        raise ValueError("DP468_VTT_SEGMENT_MISSING")
    seconds = _seconds(duration[1])
    offset = float(int(player[2]))
    if not 0 < seconds <= 3600 or not 0 <= offset <= 86400:
        raise ValueError("DP468_VTT_SEGMENT_WINDOW_INVALID")
    return int(player[1]), offset, seconds


def _caption_cues(body: bytes) -> list[tuple[float, float, str]]:
    text = body.decode("utf-8-sig").replace("\r\n", "\n")
    if not text.startswith("WEBVTT\n"):
        raise ValueError("DP468_VTT_FORMAT_INVALID")
    cues: list[tuple[float, float, str]] = []
    for block in text.split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) < 3 or not lines[0].isdigit():
            continue
        match = _CUE_TIME.fullmatch(lines[1])
        if match is None:
            raise ValueError("DP468_VTT_CUE_INVALID")
        start, end = _seconds(match[1]), _seconds(match[2])
        if end <= start:
            raise ValueError("DP468_VTT_CUE_INVALID")
        cues.append((start, end, " ".join(lines[2:])))
    if not cues:
        raise ValueError("DP468_VTT_CUES_MISSING")
    return cues


def compare_captions(
    *,
    html: bytes,
    index_receipt: dict,
    source: bytes,
    captions: dict[str, bytes],
    manifest: str,
) -> dict:
    source_hash, batch = read_batch(manifest)
    if (
        hashlib.sha256(source).hexdigest() != source_hash
        or index_receipt.get("original_senato_source_sha256") != source_hash
        or index_receipt.get("matched") != len(batch)
        or index_receipt.get("identity_approved") is not False
        or index_receipt.get("publication_authorized") is not False
    ):
        raise ValueError("DP468_VTT_SOURCE_OR_INDEX_INVALID")
    imported = import_senato_akoma_stenographic(
        source, source_raw_url=SOURCE_URL, expected_blob_sha1=SOURCE_BLOB_SHA1,
    )
    page = html.decode("utf-8")
    urls = _caption_urls(page)
    by_ordinal = {speech.ordinal: speech for speech in imported.speeches}
    span_rows = manifest.split("## New first-batch text selection", 1)[1].split("\n## ", 1)[0]
    pins = {
        int(ordinal): (int(start), int(end), digest)
        for ordinal, _, _, start, end, digest in _ROW.findall(span_rows)
    }
    observations = index_receipt["observations"]
    if len(pins) != len(batch) or len(observations) != len(batch):
        raise ValueError("DP468_VTT_MANIFEST_INVALID")
    rows: list[dict] = []
    for (ordinal, _, did), observation in zip(batch, observations, strict=True):
        if observation["ordinal"] != ordinal or observation["person_did"] != did:
            raise ValueError("DP468_VTT_INDEX_ORDER_INVALID")
        source_speech = by_ordinal[ordinal]
        start, end, expected_sha = pins[ordinal]
        quote = source_speech.review_text[start:end]
        if (
            source_speech.official_person_uri.rsplit("/", 1)[-1] != str(did)
            or hashlib.sha256(quote.encode("utf-8")).hexdigest() != expected_sha
        ):
            raise ValueError("DP468_VTT_QUOTE_PIN_MISMATCH")
        file_index, offset, duration = _segment_window(page, observation["segment_url"])
        if file_index >= len(urls) or urls[file_index] not in captions:
            raise ValueError("DP468_VTT_CAPTION_FILE_MISSING")
        cues = _caption_cues(captions[urls[file_index]])
        caption_words = _tokens(" ".join(
            value for cue_start, cue_end, value in cues
            if cue_end >= offset - 3 and cue_start <= offset + duration + 3
        ))
        quote_words = _tokens(quote)
        longest = _longest_consecutive(quote_words, caption_words)
        exact = bool(quote_words) and longest == len(quote_words)
        status = (
            "VTT_EXACT_TOKENS_ONLY" if exact else
            "VTT_PARTIAL_TOKENS_ONLY" if longest >= 3 else
            "VTT_NO_CONTIGUOUS_ALIGNMENT"
        )
        rows.append({
            "ordinal": ordinal,
            "person_did": did,
            "segment_url": observation["segment_url"],
            "quote_sha256": expected_sha,
            "caption_file_index": file_index,
            "quote_token_count": len(quote_words),
            "longest_consecutive_tokens": longest,
            "status": status,
            "wording_approved": False,
            "publication_authorized": False,
        })
    used_files = sorted({row["caption_file_index"] for row in rows})
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "original_senato_source_sha256": source_hash,
        "radio_radicale_index_sha256": hashlib.sha256(html).hexdigest(),
        "caption_files": [{
            "file_index": i,
            "url": urls[i],
            "sha256": hashlib.sha256(captions[urls[i]]).hexdigest(),
        } for i in used_files],
        "candidates": len(rows),
        "exact_token_matches": sum(r["status"] == "VTT_EXACT_TOKENS_ONLY" for r in rows),
        "partial_token_matches": sum(r["status"] == "VTT_PARTIAL_TOKENS_ONLY" for r in rows),
        "unaligned": sum(r["status"] == "VTT_NO_CONTIGUOUS_ALIGNMENT" for r in rows),
        "wording_approved": False,
        "publication_authorized": False,
        "observations": rows,
    }


def real_readback() -> dict:
    manifest = MANIFEST.read_text(encoding="utf-8")
    source_hash, batch = read_batch(manifest)
    final, page = fetch_index()
    index_receipt = crosscheck(
        source_hash, batch, json.loads(PROFILES.read_text(encoding="utf-8")),
        final, page,
    )
    actual_url, source, mime = fetch_html_or_xml(SOURCE_URL, max_bytes=3_000_000)
    if actual_url != SOURCE_URL or mime not in {"application/xml", "text/plain", "text/xml"}:
        raise ValueError("DP468_VTT_SOURCE_HTTP_INVALID")
    urls = _caption_urls(page.decode("utf-8"))
    file_indices = {
        _segment_window(page.decode("utf-8"), row["segment_url"])[0]
        for row in index_receipt["observations"]
    }
    captions: dict[str, bytes] = {}
    for i in sorted(file_indices):
        if i >= len(urls):
            raise ValueError("DP468_VTT_CAPTION_FILE_MISSING")
        url = urls[i]
        final, body, content_type = fetch_html_or_xml(url, max_bytes=2_000_000)
        if final != url or content_type not in {"text/vtt", "text/plain"}:
            raise ValueError("DP468_VTT_CAPTION_HTTP_INVALID")
        captions[url] = body
    return compare_captions(
        html=page, index_receipt=index_receipt,
        source=source, captions=captions, manifest=manifest,
    )


def main() -> int:
    try:
        result = real_readback()
    except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_HOLD",
            "reason": str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
            "publication_authorized": False,
        }))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
