from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal


EFFECTIVE_TIME_VERSION = "effective-time-v1"
TemporalVerificationScope = Literal["HISTORICAL", "CURRENT", "LATER_OUTCOME"]

_STALE_RECORD_STATUSES = frozenset({"SUPERSEDED", "RETIRED", "EXPIRED"})
_RECORD_STATUSES = frozenset({"ACTIVE", *_STALE_RECORD_STATUSES})


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
    observation_date: str | None = None
    reference_period: str | None = None
    authority_id: str | None = None
    record_status: str = "ACTIVE"

    def __post_init__(self) -> None:
        if not str(self.version_id or "").strip():
            raise ValueError("EFFECTIVE_VERSION_ID_REQUIRED")
        start = _date(self.valid_from, "VALID_FROM")
        end = _date(self.valid_to, "VALID_TO")
        published = _date(self.publication_date, "PUBLICATION_DATE")
        superseded = _date(self.superseded_at, "SUPERSEDED_AT")
        _date(self.observation_date, "OBSERVATION_DATE")
        if self.record_status not in _RECORD_STATUSES:
            raise ValueError("RECORD_STATUS_INVALID")
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


@dataclass(frozen=True)
class TemporalVerificationSelection:
    status: str
    scope: TemporalVerificationScope
    statement_date: str
    as_of: str
    selected_version_id: str | None
    candidate_version_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    rejected_version_ids: tuple[str, ...] = ()
    version: str = EFFECTIVE_TIME_VERSION

    @property
    def resolved(self) -> bool:
        return self.status == "EFFECTIVE"


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def select_verification_version(
    versions: Iterable[EffectiveRecordVersion],
    *,
    statement_date: str,
    as_of: str,
    scope: TemporalVerificationScope,
) -> TemporalVerificationSelection:
    """Select one version for a specific temporal verification scope.

    ``HISTORICAL`` evaluates a state at or before the statement date and enforces the
    statement-date publication cutoff. ``CURRENT`` evaluates the state at ``as_of`` as a
    separate question, so a source that became available after the original statement can
    contribute, but stale/superseded records cannot masquerade as current. ``LATER_OUTCOME``
    is the explicit opt-in that permits post-statement evidence for an outcome after the
    statement date.

    Publication date, observation date, effective interval and reference period are kept as
    distinct metadata. Only publication date controls whether evidence existed by the
    relevant knowledge cutoff; observation date and reference period never backdate it.
    Effective intervals use start-inclusive/end-exclusive semantics.
    """

    if scope not in {"HISTORICAL", "CURRENT", "LATER_OUTCOME"}:
        raise ValueError("TEMPORAL_SCOPE_INVALID")
    statement = _date(statement_date, "STATEMENT_DATE")
    point = _date(as_of, "AS_OF")
    assert statement is not None
    assert point is not None
    if scope == "HISTORICAL" and point > statement:
        raise ValueError("HISTORICAL_AS_OF_AFTER_STATEMENT")
    if scope == "LATER_OUTCOME" and point <= statement:
        raise ValueError("LATER_OUTCOME_AS_OF_NOT_AFTER_STATEMENT")

    candidates: list[EffectiveRecordVersion] = []
    rejected_ids: list[str] = []
    blockers: list[str] = []

    for row in sorted(versions, key=lambda item: item.version_id):
        if row.status != "APPROVED":
            continue
        start = _date(row.valid_from, "VALID_FROM")
        end = _date(row.valid_to, "VALID_TO")
        published = _date(row.publication_date, "PUBLICATION_DATE")
        superseded = _date(row.superseded_at, "SUPERSEDED_AT")

        reason: str | None = None
        if published is None:
            reason = "PUBLICATION_DATE_REQUIRED"
        elif scope == "HISTORICAL" and published > statement:
            reason = "POST_STATEMENT_EVIDENCE"
        elif scope in {"CURRENT", "LATER_OUTCOME"} and published > point:
            reason = "POST_AS_OF_EVIDENCE"
        elif start is not None and point < start:
            reason = "VERSION_NOT_YET_EFFECTIVE"
        elif end is not None and point >= end:
            reason = "VERSION_EXPIRED"
        elif superseded is not None and point >= superseded:
            reason = "VERSION_SUPERSEDED"
        elif row.record_status in _STALE_RECORD_STATUSES:
            if end is None and superseded is None:
                reason = "STALE_VERSION_WITHOUT_EFFECTIVE_END"
            elif scope == "CURRENT":
                reason = "STALE_VERSION_NOT_CURRENT"

        if reason is not None:
            rejected_ids.append(row.version_id)
            _append_once(blockers, reason)
            continue
        candidates.append(row)

    candidate_ids = tuple(row.version_id for row in candidates)
    if len(candidates) == 1:
        return TemporalVerificationSelection(
            status="EFFECTIVE",
            scope=scope,
            statement_date=statement_date,
            as_of=as_of,
            selected_version_id=candidates[0].version_id,
            candidate_version_ids=candidate_ids,
            rejected_version_ids=tuple(sorted(rejected_ids)),
        )
    if len(candidates) > 1:
        authority_ids = {
            str(row.authority_id).strip()
            for row in candidates
            if row.authority_id is not None and str(row.authority_id).strip()
        }
        blocker = (
            "CONFLICTING_AUTHORITIES"
            if len(authority_ids) > 1
            else "CONFLICTING_EFFECTIVE_VERSIONS"
        )
        return TemporalVerificationSelection(
            status="UNRESOLVED",
            scope=scope,
            statement_date=statement_date,
            as_of=as_of,
            selected_version_id=None,
            candidate_version_ids=candidate_ids,
            blockers=(blocker,),
            rejected_version_ids=tuple(sorted(rejected_ids)),
        )

    if not blockers:
        blockers.append("NO_EFFECTIVE_VERSION")
    unresolved = "STALE_VERSION_WITHOUT_EFFECTIVE_END" in blockers
    return TemporalVerificationSelection(
        status="UNRESOLVED" if unresolved else "INSUFFICIENT",
        scope=scope,
        statement_date=statement_date,
        as_of=as_of,
        selected_version_id=None,
        candidate_version_ids=(),
        blockers=tuple(blockers),
        rejected_version_ids=tuple(sorted(rejected_ids)),
    )


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
    "TemporalVerificationScope",
    "TemporalVerificationSelection",
    "select_effective_version",
    "select_verification_version",
]
