"""DP-233 pure normalizer for official parliamentary speech records.

The adapter consumes already-fetched/offline official records. It performs no network
I/O, no biometric or account-based speaker inference, and grants no publication
authority. Official transcript wording stays an independent source version; platform
caption/ASR variant identifiers are preserved only as references.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


PARLIAMENTARY_OFFICIAL_ADAPTER_VERSION = "parliamentary-official-adapter-v1"
MAX_TRANSCRIPT_CHARS = 250_000
MAX_STATEMENT_CHARS = 20_000
MAX_TEXT_FIELD_CHARS = 1_000
MAX_VARIANT_REFS = 32
MAX_ID_CHARS = 240
MAX_VIDEO_MS = 24 * 60 * 60 * 1000

_ID_RE = re.compile(r"^[A-Za-z0-9_.:@/-]{1,240}$")
_CHAMBER_PREFIX = {"CAMERA": "camera:", "SENATO": "senato:"}
_CHAMBER_HOSTS = {
    "CAMERA": ("camera.it",),
    "SENATO": ("senato.it",),
}


@dataclass(frozen=True)
class ParliamentarySessionContext:
    chamber: str
    sitting_id: str
    sitting_date: str
    agenda_item_id: str | None
    agenda_label: str | None


@dataclass(frozen=True)
class OfficialSpeakerRef:
    speaker_id: str
    speaker_name: str
    speaker_role: str | None


@dataclass(frozen=True)
class OfficialTranscriptSource:
    source_url: str
    source_version: str
    transcript_sha256: str
    statement_start_char: int
    statement_end_char: int
    statement_text: str
    variant_refs: tuple[str, ...]


@dataclass(frozen=True)
class OfficialVideoLocator:
    source_url: str
    source_version: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class ParliamentaryOfficialRecord:
    record_id: str
    provenance_id: str
    statement_id: str
    statement_date: str
    session: ParliamentarySessionContext
    speaker: OfficialSpeakerRef
    transcript: OfficialTranscriptSource
    video: OfficialVideoLocator | None
    adapter_version: str = PARLIAMENTARY_OFFICIAL_ADAPTER_VERSION


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _text(value: object, *, field: str, maximum: int, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"PARLIAMENTARY_{field}_REQUIRED")
        return None
    if not isinstance(value, str):
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID")
    text = value.strip()
    if required and not text:
        raise ValueError(f"PARLIAMENTARY_{field}_REQUIRED")
    if len(text) > maximum or "\x00" in text:
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID")
    return text or None


def _identifier(value: object, *, field: str, prefix: str | None = None) -> str:
    text = _text(value, field=field, maximum=MAX_ID_CHARS)
    assert text is not None
    if not _ID_RE.fullmatch(text):
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID")
    if prefix is not None and not text.casefold().startswith(prefix.casefold()):
        raise ValueError(f"PARLIAMENTARY_{field}_CHAMBER_MISMATCH")
    return text


def _iso_date(value: object, *, field: str) -> str:
    text = _text(value, field=field, maximum=10)
    assert text is not None
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID") from exc
    return parsed.isoformat()


def _safe_official_https_url(value: object, *, chamber: str, field: str) -> str:
    text = _text(value, field=field, maximum=2048)
    assert text is not None
    parsed = urlsplit(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ValueError(f"PARLIAMENTARY_{field}_HTTPS_REQUIRED")
    host = parsed.hostname.rstrip(".").casefold()
    allowed = _CHAMBER_HOSTS[chamber]
    if not any(host == suffix or host.endswith("." + suffix) for suffix in allowed):
        raise ValueError(f"PARLIAMENTARY_{field}_CHAMBER_MISMATCH")
    return text


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PARLIAMENTARY_{field}_INVALID")
    return dict(value)


def _video_locator(value: object, *, chamber: str) -> OfficialVideoLocator | None:
    if value is None:
        return None
    raw = _mapping(value, field="VIDEO")
    source_url = _safe_official_https_url(raw.get("url"), chamber=chamber, field="VIDEO_URL")
    source_version = _text(
        raw.get("source_version"), field="VIDEO_SOURCE_VERSION", maximum=MAX_TEXT_FIELD_CHARS
    )
    assert source_version is not None
    start = raw.get("start_ms")
    end = raw.get("end_ms")
    if (start is None) != (end is None):
        raise ValueError("PARLIAMENTARY_VIDEO_RANGE_INCOMPLETE")
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("PARLIAMENTARY_VIDEO_RANGE_REQUIRED")
    if not isinstance(end, int) or isinstance(end, bool):
        raise ValueError("PARLIAMENTARY_VIDEO_RANGE_REQUIRED")
    if start < 0 or end <= start or end > MAX_VIDEO_MS:
        raise ValueError("PARLIAMENTARY_VIDEO_RANGE_INVALID")
    return OfficialVideoLocator(
        source_url=source_url,
        source_version=source_version,
        start_ms=start,
        end_ms=end,
    )


def normalize_parliamentary_official_record(raw: Mapping[str, Any]) -> ParliamentaryOfficialRecord:
    """Normalize one official parliamentary statement from an offline source record.

    The statement span must be explicitly supplied and must exactly select the official
    statement text from the supplied official transcript source version. Video timing is
    emitted only when an explicit complete range is present in the official input.
    """

    data = _mapping(raw, field="RECORD")
    chamber_raw = _text(data.get("chamber"), field="CHAMBER", maximum=16)
    assert chamber_raw is not None
    chamber = chamber_raw.upper()
    if chamber not in _CHAMBER_PREFIX:
        raise ValueError("PARLIAMENTARY_CHAMBER_INVALID")
    prefix = _CHAMBER_PREFIX[chamber]

    sitting = _mapping(data.get("sitting"), field="SITTING")
    speaker = _mapping(data.get("speaker"), field="SPEAKER")
    statement = _mapping(data.get("statement"), field="STATEMENT")
    transcript = _mapping(data.get("transcript"), field="TRANSCRIPT")

    sitting_id = _identifier(sitting.get("id"), field="SITTING_ID", prefix=prefix)
    sitting_date = _iso_date(sitting.get("date"), field="SITTING_DATE")
    speaker_id = _identifier(speaker.get("id"), field="SPEAKER_ID", prefix=prefix)
    speaker_name = _text(
        speaker.get("name"), field="SPEAKER_NAME", maximum=MAX_TEXT_FIELD_CHARS
    )
    assert speaker_name is not None
    speaker_role = _text(
        speaker.get("role"), field="SPEAKER_ROLE", maximum=MAX_TEXT_FIELD_CHARS, required=False
    )

    statement_id = _identifier(statement.get("id"), field="STATEMENT_ID", prefix=prefix)
    statement_speaker_id = _identifier(
        statement.get("speaker_id"), field="STATEMENT_SPEAKER_ID", prefix=prefix
    )
    if statement_speaker_id != speaker_id:
        raise ValueError("PARLIAMENTARY_STATEMENT_SPEAKER_MISMATCH")
    statement_date = _iso_date(statement.get("date"), field="STATEMENT_DATE")
    if statement_date != sitting_date:
        raise ValueError("PARLIAMENTARY_STATEMENT_DATE_MISMATCH")
    statement_text = _text(
        statement.get("text"), field="STATEMENT_TEXT", maximum=MAX_STATEMENT_CHARS
    )
    assert statement_text is not None
    start = statement.get("start_char")
    end = statement.get("end_char")
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("PARLIAMENTARY_STATEMENT_SPAN_INVALID")
    if not isinstance(end, int) or isinstance(end, bool):
        raise ValueError("PARLIAMENTARY_STATEMENT_SPAN_INVALID")

    transcript_text = _text(
        transcript.get("text"), field="TRANSCRIPT_TEXT", maximum=MAX_TRANSCRIPT_CHARS
    )
    assert transcript_text is not None
    if start < 0 or end <= start or end > len(transcript_text):
        raise ValueError("PARLIAMENTARY_STATEMENT_SPAN_INVALID")
    if transcript_text[start:end] != statement_text:
        raise ValueError("PARLIAMENTARY_STATEMENT_SPAN_MISMATCH")

    transcript_url = _safe_official_https_url(
        transcript.get("url"), chamber=chamber, field="TRANSCRIPT_URL"
    )
    transcript_version = _text(
        transcript.get("source_version"),
        field="TRANSCRIPT_SOURCE_VERSION",
        maximum=MAX_TEXT_FIELD_CHARS,
    )
    assert transcript_version is not None
    transcript_hash = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()

    raw_variants = data.get("transcript_variant_refs") or ()
    if not isinstance(raw_variants, (list, tuple)) or len(raw_variants) > MAX_VARIANT_REFS:
        raise ValueError("PARLIAMENTARY_TRANSCRIPT_VARIANTS_INVALID")
    variants = tuple(
        dict.fromkeys(
            _identifier(value, field="TRANSCRIPT_VARIANT_REF") for value in raw_variants
        )
    )

    context = ParliamentarySessionContext(
        chamber=chamber,
        sitting_id=sitting_id,
        sitting_date=sitting_date,
        agenda_item_id=(
            _identifier(sitting.get("agenda_item_id"), field="AGENDA_ITEM_ID", prefix=prefix)
            if sitting.get("agenda_item_id") is not None
            else None
        ),
        agenda_label=_text(
            sitting.get("agenda_label"),
            field="AGENDA_LABEL",
            maximum=MAX_TEXT_FIELD_CHARS,
            required=False,
        ),
    )
    official_speaker = OfficialSpeakerRef(
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        speaker_role=speaker_role,
    )
    official_transcript = OfficialTranscriptSource(
        source_url=transcript_url,
        source_version=transcript_version,
        transcript_sha256=transcript_hash,
        statement_start_char=start,
        statement_end_char=end,
        statement_text=statement_text,
        variant_refs=variants,
    )
    video = _video_locator(data.get("video"), chamber=chamber)

    provenance_material = {
        "chamber": chamber,
        "sitting_id": sitting_id,
        "sitting_date": sitting_date,
        "speaker_id": speaker_id,
        "statement_id": statement_id,
        "statement_date": statement_date,
        "transcript_url": transcript_url,
        "transcript_version": transcript_version,
        "transcript_sha256": transcript_hash,
        "statement_span": [start, end],
        "video": (
            None
            if video is None
            else {
                "url": video.source_url,
                "source_version": video.source_version,
                "start_ms": video.start_ms,
                "end_ms": video.end_ms,
            }
        ),
        "adapter_version": PARLIAMENTARY_OFFICIAL_ADAPTER_VERSION,
    }
    provenance_id = "parliamentary-provenance:" + _sha(provenance_material)
    record_material = {
        **provenance_material,
        "statement_text_sha256": hashlib.sha256(statement_text.encode("utf-8")).hexdigest(),
        "agenda_item_id": context.agenda_item_id,
        "variant_refs": list(variants),
    }
    record_id = "parliamentary-record:" + _sha(record_material)

    return ParliamentaryOfficialRecord(
        record_id=record_id,
        provenance_id=provenance_id,
        statement_id=statement_id,
        statement_date=statement_date,
        session=context,
        speaker=official_speaker,
        transcript=official_transcript,
        video=video,
    )


def normalize_parliamentary_official_records(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[ParliamentaryOfficialRecord, ...]:
    """Normalize, deterministically dedupe exact replays, and reject collisions."""

    by_statement: dict[tuple[str, str], ParliamentaryOfficialRecord] = {}
    for raw in rows:
        record = normalize_parliamentary_official_record(raw)
        key = (record.session.chamber, record.statement_id)
        existing = by_statement.get(key)
        if existing is None:
            by_statement[key] = record
            continue
        if existing.record_id != record.record_id:
            raise ValueError("PARLIAMENTARY_REPLAY_CONFLICT")
    return tuple(
        sorted(
            by_statement.values(),
            key=lambda row: (
                row.session.sitting_date,
                row.session.chamber,
                row.session.sitting_id,
                row.statement_id,
            ),
        )
    )


__all__ = [
    "MAX_STATEMENT_CHARS",
    "MAX_TRANSCRIPT_CHARS",
    "PARLIAMENTARY_OFFICIAL_ADAPTER_VERSION",
    "OfficialSpeakerRef",
    "OfficialTranscriptSource",
    "OfficialVideoLocator",
    "ParliamentaryOfficialRecord",
    "ParliamentarySessionContext",
    "normalize_parliamentary_official_record",
    "normalize_parliamentary_official_records",
]
