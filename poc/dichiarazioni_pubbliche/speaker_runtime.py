from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


SPEAKER_ATTRIBUTION_VERSION = "speaker-attribution-v1"
ALLOWED_ATTRIBUTION_METHODS = {
    "MANUAL_REVIEW",
    "SOURCE_METADATA",
    "TRANSCRIPT_LABEL",
    "PLATFORM_CREDIT",
    "OFFICIAL_RECORD",
}
PUBLICATION_CAPABLE_ATTRIBUTION_METHODS = frozenset(
    {
        "MANUAL_REVIEW",
        "TRANSCRIPT_LABEL",
        "OFFICIAL_RECORD",
    }
)


def speaker_method_is_publication_capable(method: str) -> bool:
    return str(method or "").strip() in PUBLICATION_CAPABLE_ATTRIBUTION_METHODS


@dataclass(frozen=True)
class SpeakerIdentityCandidate:
    candidate_id: str
    content_id: str
    person_id: str
    start_ms: int
    end_ms: int
    attribution_method: str
    attribution_version: str
    speaker_label: str | None
    source_ref: dict[str, Any]
    confidence: float | None


def deterministic_speaker_candidate_id(
    *,
    content_id: str,
    person_id: str,
    start_ms: int,
    end_ms: int,
    attribution_method: str,
    attribution_version: str = SPEAKER_ATTRIBUTION_VERSION,
    source_ref: dict[str, Any] | None = None,
) -> str:
    if attribution_method not in ALLOWED_ATTRIBUTION_METHODS:
        raise ValueError("speaker attribution method is not allowed")
    if start_ms < 0 or end_ms < start_ms:
        raise ValueError("invalid speaker attribution interval")
    material = {
        "content_id": content_id,
        "person_id": person_id,
        "start_ms": int(start_ms),
        "end_ms": int(end_ms),
        "attribution_method": attribution_method,
        "attribution_version": attribution_version,
        "source_ref": source_ref or {},
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "speaker-candidate:" + hashlib.sha256(encoded).hexdigest()


def make_speaker_candidate(
    *,
    content_id: str,
    person_id: str,
    start_ms: int,
    end_ms: int,
    attribution_method: str,
    speaker_label: str | None = None,
    source_ref: dict[str, Any] | None = None,
    confidence: float | None = None,
    attribution_version: str = SPEAKER_ATTRIBUTION_VERSION,
) -> SpeakerIdentityCandidate:
    if confidence is not None and not 0 <= float(confidence) <= 1:
        raise ValueError("speaker confidence must be in [0,1]")
    candidate_id = deterministic_speaker_candidate_id(
        content_id=content_id,
        person_id=person_id,
        start_ms=start_ms,
        end_ms=end_ms,
        attribution_method=attribution_method,
        attribution_version=attribution_version,
        source_ref=source_ref,
    )
    return SpeakerIdentityCandidate(
        candidate_id=candidate_id,
        content_id=content_id,
        person_id=person_id,
        start_ms=start_ms,
        end_ms=end_ms,
        attribution_method=attribution_method,
        attribution_version=attribution_version,
        speaker_label=speaker_label,
        source_ref=source_ref or {},
        confidence=None if confidence is None else float(confidence),
    )
