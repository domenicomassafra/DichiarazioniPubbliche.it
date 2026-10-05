from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable


PARLIAMENTARY_ALIGNMENT_VERSION = "parliamentary-alignment-v1"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


@dataclass(frozen=True)
class ParliamentaryIntervention:
    intervention_id: str
    session_id: str
    official_speaker_ref: str
    official_speaker_name: str
    transcript_text: str
    source_url: str
    source_version: str
    speaker_person_id: str | None = None
    speaker_resolution_approved: bool = False
    official_start_ms: int | None = None
    official_end_ms: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "intervention_id",
            "session_id",
            "official_speaker_ref",
            "official_speaker_name",
            "transcript_text",
            "source_url",
            "source_version",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"PARLIAMENTARY_{name.upper()}_REQUIRED")
        if (self.official_start_ms is None) != (self.official_end_ms is None):
            raise ValueError("PARLIAMENTARY_OFFICIAL_RANGE_INCOMPLETE")
        if self.official_start_ms is not None:
            if self.official_start_ms < 0 or self.official_end_ms <= self.official_start_ms:
                raise ValueError("PARLIAMENTARY_OFFICIAL_RANGE_INVALID")
        if self.speaker_resolution_approved and not self.speaker_person_id:
            raise ValueError("PARLIAMENTARY_APPROVED_SPEAKER_PERSON_REQUIRED")

    @property
    def transcript_sha256(self) -> str:
        return hashlib.sha256(self.transcript_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MediaSegment:
    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    source_version: str

    def __post_init__(self) -> None:
        if not str(self.segment_id or "").strip():
            raise ValueError("PARLIAMENTARY_SEGMENT_ID_REQUIRED")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("PARLIAMENTARY_SEGMENT_RANGE_INVALID")
        if not str(self.source_version or "").strip():
            raise ValueError("PARLIAMENTARY_SEGMENT_VERSION_REQUIRED")


@dataclass(frozen=True)
class ParliamentaryAlignment:
    intervention_id: str
    status: str
    method: str
    start_ms: int | None
    end_ms: int | None
    segment_ids: tuple[str, ...]
    speaker_person_id: str | None
    blockers: tuple[str, ...]
    intervention_transcript_sha256: str
    version: str = PARLIAMENTARY_ALIGNMENT_VERSION

    @property
    def direct_official(self) -> bool:
        return self.status == "DIRECT_OFFICIAL"


def align_parliamentary_intervention(
    intervention: ParliamentaryIntervention,
    segments: Iterable[MediaSegment] = (),
    *,
    max_window_segments: int = 8,
) -> ParliamentaryAlignment:
    """Align one official intervention to media without inventing identity or timing.

    Official start/end values are authoritative only as locators supplied by the official
    record. Without them, exact normalized text alignment may create a REVIEW_CANDIDATE,
    never an approved/public timestamp.
    """

    if not 1 <= int(max_window_segments) <= 32:
        raise ValueError("PARLIAMENTARY_WINDOW_LIMIT_INVALID")
    speaker_id = (
        intervention.speaker_person_id
        if intervention.speaker_resolution_approved
        else None
    )
    speaker_blockers = (
        ()
        if intervention.speaker_resolution_approved
        else ("SPEAKER_RESOLUTION_NOT_APPROVED",)
    )

    if intervention.official_start_ms is not None:
        return ParliamentaryAlignment(
            intervention_id=intervention.intervention_id,
            status="DIRECT_OFFICIAL" if not speaker_blockers else "ATTRIBUTION_HOLD",
            method="OFFICIAL_MEDIA_RANGE",
            start_ms=intervention.official_start_ms,
            end_ms=intervention.official_end_ms,
            segment_ids=(),
            speaker_person_id=speaker_id,
            blockers=speaker_blockers,
            intervention_transcript_sha256=intervention.transcript_sha256,
        )

    rows = tuple(sorted(segments, key=lambda row: (row.start_ms, row.end_ms, row.segment_id)))
    target = _norm(intervention.transcript_text)
    if not target:
        return ParliamentaryAlignment(
            intervention_id=intervention.intervention_id,
            status="UNRESOLVED",
            method="NO_ALIGNMENT",
            start_ms=None,
            end_ms=None,
            segment_ids=(),
            speaker_person_id=speaker_id,
            blockers=tuple((*speaker_blockers, "EMPTY_OFFICIAL_TRANSCRIPT")),
            intervention_transcript_sha256=intervention.transcript_sha256,
        )

    matches: list[tuple[int, int, tuple[str, ...]]] = []
    for left in range(len(rows)):
        parts: list[str] = []
        ids: list[str] = []
        for right in range(left, min(len(rows), left + int(max_window_segments))):
            parts.append(rows[right].text)
            ids.append(rows[right].segment_id)
            candidate = _norm(" ".join(parts))
            if candidate == target:
                matches.append((rows[left].start_ms, rows[right].end_ms, tuple(ids)))
            if len(candidate) > len(target) * 2 + 256:
                break

    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        start_ms, end_ms, segment_ids = unique[0]
        blockers = tuple((*speaker_blockers, "TEXT_ALIGNMENT_REQUIRES_REVIEW"))
        return ParliamentaryAlignment(
            intervention_id=intervention.intervention_id,
            status="REVIEW_CANDIDATE",
            method="EXACT_NORMALIZED_TRANSCRIPT_WINDOW",
            start_ms=start_ms,
            end_ms=end_ms,
            segment_ids=segment_ids,
            speaker_person_id=speaker_id,
            blockers=blockers,
            intervention_transcript_sha256=intervention.transcript_sha256,
        )
    blocker = (
        "AMBIGUOUS_TEXT_ALIGNMENT"
        if len(unique) > 1
        else "NO_TEXT_ALIGNMENT"
    )
    return ParliamentaryAlignment(
        intervention_id=intervention.intervention_id,
        status="UNRESOLVED",
        method="NO_ALIGNMENT",
        start_ms=None,
        end_ms=None,
        segment_ids=(),
        speaker_person_id=speaker_id,
        blockers=tuple((*speaker_blockers, blocker)),
        intervention_transcript_sha256=intervention.transcript_sha256,
    )


__all__ = [
    "PARLIAMENTARY_ALIGNMENT_VERSION",
    "MediaSegment",
    "ParliamentaryAlignment",
    "ParliamentaryIntervention",
    "align_parliamentary_intervention",
]
