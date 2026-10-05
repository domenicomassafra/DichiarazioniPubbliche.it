from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


EFFECTIVE_TIME_VERSION = "effective-time-v1"


def _date(value: str | None, field_name: str) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name}_INVALID") from exc


@dataclass(frozen=True)
class EffectiveRecordVersion:
    version_id: str
    valid_from: str | None
    valid_to: str | None
    publication_date: str | None
    status: str = "APPROVED"
    superseded_at: str | None = None
    content_sha256: str | None = None

    def __post_init__(self) -> None:
        if not str(self.version_id or "").strip():
            raise ValueError("EFFECTIVE_VERSION_ID_REQUIRED")
        start = _date(self.valid_from, "VALID_FROM")
        end = _date(self.valid_to, "VALID_TO")
        published = _date(self.publication_date, "PUBLICATION_DATE")
        superseded = _date(self.superseded_at, "SUPERSEDED_AT")
        if start is not None and end is not None and end <= start:
            raise ValueError("EFFECTIVE_INTERVAL_INVALID")
        if superseded is not None and start is not None and superseded < start:
            raise ValueError("SUPERSEDED_BEFORE_VALID_FROM")
        if published is not None and end is not None and published > end:
            # Publication after the validity interval can be legitimate for historical
            # archives, so it is not rejected. Selection policy handles statement cutoff.
            pass


@dataclass(frozen=True)
class EffectiveTimeSelection:
    status: str
    as_of: str
    selected_version_id: str | None
    candidate_version_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    version: str = EFFECTIVE_TIME_VERSION

    @property
    def resolved(self) -> bool:
        return self.status == "EFFECTIVE"


def select_effective_version(
    versions: Iterable[EffectiveRecordVersion],
    *,
    as_of: str,
    publication_cutoff: str | None = None,
) -> EffectiveTimeSelection:
    """Select the single reviewed version effective at as_of.

    Intervals use [valid_from, valid_to): valid_from is inclusive and valid_to is
    exclusive. A reviewed superseded_at date acts as an additional exclusive upper bound.
    More than one applicable version is an unresolved conflict; no prestige/latest-row
    tie-break is allowed.
    """

    point = _date(as_of, "AS_OF")
    assert point is not None
    cutoff = _date(publication_cutoff, "PUBLICATION_CUTOFF")
    candidates: list[EffectiveRecordVersion] = []
    post_cutoff: list[EffectiveRecordVersion] = []

    for row in versions:
        if row.status != "APPROVED":
            continue
        start = _date(row.valid_from, "VALID_FROM")
        end = _date(row.valid_to, "VALID_TO")
        superseded = _date(row.superseded_at, "SUPERSEDED_AT")
        published = _date(row.publication_date, "PUBLICATION_DATE")
        if start is not None and point < start:
            continue
        if end is not None and point >= end:
            continue
        if superseded is not None and point >= superseded:
            continue
        if cutoff is not None and published is not None and published > cutoff:
            post_cutoff.append(row)
            continue
        candidates.append(row)

    ids = tuple(sorted(row.version_id for row in candidates))
    if len(candidates) == 1:
        return EffectiveTimeSelection(
            status="EFFECTIVE",
            as_of=as_of,
            selected_version_id=candidates[0].version_id,
            candidate_version_ids=ids,
        )
    if len(candidates) > 1:
        return EffectiveTimeSelection(
            status="UNRESOLVED",
            as_of=as_of,
            selected_version_id=None,
            candidate_version_ids=ids,
            blockers=("CONFLICTING_EFFECTIVE_VERSIONS",),
        )
    if post_cutoff:
        return EffectiveTimeSelection(
            status="UNRESOLVED",
            as_of=as_of,
            selected_version_id=None,
            candidate_version_ids=tuple(sorted(row.version_id for row in post_cutoff)),
            blockers=("POST_STATEMENT_VERSION_ONLY",),
        )
    return EffectiveTimeSelection(
        status="INSUFFICIENT",
        as_of=as_of,
        selected_version_id=None,
        candidate_version_ids=(),
        blockers=("NO_EFFECTIVE_VERSION",),
    )


__all__ = [
    "EFFECTIVE_TIME_VERSION",
    "EffectiveRecordVersion",
    "EffectiveTimeSelection",
    "select_effective_version",
]
