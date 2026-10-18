"""DP-519: bounded PRIVATE Studio visual-only queue and time-receipt reconciliation.

Pure opt-in contract: no database, clock access, network, image processing, or
operator authentication. Neither an operator click, rights-state string, nor a
hash authorizes image publication or editorial/text/factual review. The future
DP-518 withdrawal/readback and qualified external policies remain mandatory.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal


VERSION = "visual-operator-capacity-v1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REASONS = frozenset(
    {
        "IMAGE_IDENTITY",
        "IMAGE_LICENSE",
        "IMAGE_MISSING",
        "VISUAL_CAPTION",
        "IMAGE_STALE",
    }
)
_RIGHTS = frozenset({"CLEARED", "UNKNOWN", "DENIED", "EXPIRED", "REVOKED"})
_IDENTITIES = frozenset({"MATCH_REVIEWED", "UNKNOWN", "AMBIGUOUS", "CONFLICT"})
_ACTIONS = frozenset({"NO_IMAGE", "CHOOSE_CANDIDATE", "DEFER", "WITHDRAW_IMAGE"})
_EXCEPTION_QUESTIONS = frozenset(
    {
        "SOURCE_RIGHTS_REVIEW_NEEDED",
        "PERSON_IDENTITY_CONFLICT",
        "IMAGE_LICENSE_CLARIFICATION",
        "VISUAL_CAPTION_SOURCE",
        "EVIDENCE_POLICY_UNRESOLVED",
        "HIGH_RISK_EXTERNAL_AUTHORITY",
    }
)
_MAX_ITEMS = 64
_MAX_EVENTS = 128
_MAX_EXCEPTIONS = 8


def _id(value: object, code: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"DP519_{code}_INVALID")
    return value


def _hash(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError(f"DP519_{code}_HASH_INVALID")
    return value


def _stamp(value: object, code: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"DP519_{code}_TIMEZONE_REQUIRED")
    return value.astimezone(timezone.utc)


def _small_int(value: object, code: str, maximum: int = 300) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"DP519_{code}_INVALID")
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class VisualWorkItem:
    work_key: str
    content_id: str
    person_id: str
    reason_code: str
    asset_sha256: str | None
    source_version_sha256: str
    preview_ref: str | None  # opaque PRIVATE reference, no URL/body/image bytes
    source_rights_state: str
    person_identity_state: str
    created_at: datetime
    expires_at: datetime
    estimated_minutes: int
    automated_attempt_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisualDecisionEvent:
    event_id: str
    work_key: str
    actor_id: str
    action: str
    source_version_sha256: str
    asset_sha256: str | None
    started_at: datetime
    completed_at: datetime
    prior_event_id: str | None = None


@dataclass(frozen=True)
class VisualException:
    exception_id: str
    work_key: str
    question_code: str
    prior_attempt_hashes: tuple[str, ...]
    estimated_minutes: int
    authority_state: str  # UNRESOLVED only; no signer fabricated


@dataclass(frozen=True)
class VisualQueueRow:
    work_key: str
    reason_code: str
    state: str
    priority: int
    age_days: int
    estimated_minutes: int
    last_action: str | None
    image_eligible: bool = False
    public_alt_text: str = ""
    text_only_record_unblocked_by_missing_image: bool = True
    withdrawal_review_required: bool = False


@dataclass(frozen=True)
class VisualExceptionRow:
    exception_id: str
    work_key: str
    question_code: str
    state: str
    estimated_minutes: int
    text_review_authority: bool = False


@dataclass(frozen=True)
class VisualCapacityReport:
    version: str
    rows: tuple[VisualQueueRow, ...]
    exceptions: tuple[VisualExceptionRow, ...]
    actual_minutes_by_week: dict[str, Decimal]
    actual_minutes_this_week: Decimal
    median_minutes_by_reason: dict[str, Decimal]
    future_estimated_minutes: int
    exception_estimated_minutes: int
    weekly_planning_minutes: int
    available_planning_minutes: Decimal
    older_unresolved_count: int
    ledger_event_count: int
    ledger_fingerprint: str
    publication_authority: bool = False
    text_review_authority: bool = False
    image_approval_authority: bool = False


def _check_work(row: VisualWorkItem, now: datetime) -> None:
    if type(row) is not VisualWorkItem:
        raise ValueError("DP519_WORK_ITEM_INVALID")
    for code in ("work_key", "content_id", "person_id"):
        _id(getattr(row, code), code.upper())
    if row.reason_code not in _REASONS:
        raise ValueError("DP519_REASON_INVALID")
    _hash(row.source_version_sha256, "VERSION")
    if row.asset_sha256 is not None:
        _hash(row.asset_sha256, "ASSET")
        _id(row.preview_ref, "PRIVATE_PREVIEW_REF")
        if not row.preview_ref.startswith("private:"):
            raise ValueError("DP519_PRIVATE_PREVIEW_REQUIRED")
    elif row.preview_ref is not None:
        raise ValueError("DP519_NO_IMAGE_PREVIEW_FORBIDDEN")
    if (
        row.source_rights_state not in _RIGHTS
        or row.person_identity_state not in _IDENTITIES
    ):
        raise ValueError("DP519_RIGHTS_OR_IDENTITY_INVALID")
    if _stamp(row.created_at, "CREATED") > now:
        raise ValueError("DP519_FUTURE_WORK_INVALID")
    if _stamp(row.expires_at, "EXPIRES") <= _stamp(row.created_at, "CREATED"):
        raise ValueError("DP519_EXPIRY_INVALID")
    _small_int(row.estimated_minutes, "ESTIMATE", 60)
    if (
        not isinstance(row.automated_attempt_hashes, tuple)
        or len(row.automated_attempt_hashes) > 8
        or len(set(row.automated_attempt_hashes)) != len(row.automated_attempt_hashes)
    ):
        raise ValueError("DP519_AUTOMATED_ATTEMPTS_INVALID")
    for digest in row.automated_attempt_hashes:
        _hash(digest, "AUTOMATED_ATTEMPT")


def _check_event(row: VisualDecisionEvent, item: VisualWorkItem, now: datetime) -> None:
    if type(row) is not VisualDecisionEvent:
        raise ValueError("DP519_EVENT_INVALID")
    for key in ("event_id", "work_key", "actor_id"):
        _id(getattr(row, key), key.upper())
    if row.action not in _ACTIONS:
        raise ValueError("DP519_EVENT_ACTION_INVALID")
    _hash(row.source_version_sha256, "EVENT_VERSION")
    if row.asset_sha256 is not None:
        _hash(row.asset_sha256, "EVENT_ASSET")
    if row.action == "CHOOSE_CANDIDATE":
        if row.asset_sha256 is None or (
            row.source_version_sha256 == item.source_version_sha256
            and row.asset_sha256 != item.asset_sha256
        ):
            raise ValueError("DP519_EVENT_SELECTED_ASSET_MISMATCH")
    elif row.asset_sha256 is not None:
        raise ValueError("DP519_EVENT_ASSET_FORBIDDEN")
    if row.prior_event_id is not None:
        _id(row.prior_event_id, "PRIOR_EVENT_ID")
    start, stop = (
        _stamp(row.started_at, "STARTED"),
        _stamp(row.completed_at, "COMPLETED"),
    )
    if not start < stop <= now or (stop - start).total_seconds() > 360 * 60:
        raise ValueError("DP519_EVENT_TIME_INVALID")


def _check_exception(
    row: VisualException, work_items: dict[str, VisualWorkItem]
) -> None:
    if type(row) is not VisualException:
        raise ValueError("DP519_EXCEPTION_INVALID")
    _id(row.exception_id, "EXCEPTION_ID")
    if row.work_key not in work_items:
        raise ValueError("DP519_EXCEPTION_FOREIGN_WORK")
    if (
        not isinstance(row.question_code, str)
        or _CODE.fullmatch(row.question_code) is None
        or row.question_code not in _EXCEPTION_QUESTIONS
    ):
        raise ValueError("DP519_EXCEPTION_QUESTION_INVALID")
    if (
        not isinstance(row.prior_attempt_hashes, tuple)
        or not 1 <= len(row.prior_attempt_hashes) <= 8
        or len(set(row.prior_attempt_hashes)) != len(row.prior_attempt_hashes)
    ):
        raise ValueError("DP519_EXCEPTION_PRIOR_ATTEMPTS_REQUIRED")
    for attempt in row.prior_attempt_hashes:
        _hash(attempt, "EXCEPTION_ATTEMPT")
    # An arbitrary well-formed digest is not proof that automated investigation
    # happened for this work item. The exception must refer to actual recorded
    # attempt receipts for this work, never another case's attempts.
    if not set(row.prior_attempt_hashes).issubset(
        work_items[row.work_key].automated_attempt_hashes
    ):
        raise ValueError("DP519_EXCEPTION_ATTEMPT_NOT_IN_WORK")
    _small_int(row.estimated_minutes, "EXCEPTION_ESTIMATE", 20)
    if row.authority_state != "UNRESOLVED":
        raise ValueError("DP519_EXCEPTION_UNQUALIFIED_AUTHORITY")


def _iso_week(value: datetime) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def reconcile_visual_capacity(
    items: tuple[VisualWorkItem, ...],
    events: tuple[VisualDecisionEvent, ...],
    exceptions: tuple[VisualException, ...],
    *,
    now: datetime,
    weekly_planning_minutes: int = 300,
) -> VisualCapacityReport:
    """Pure deterministic worklist and immutable replay of *reported* operator time.

    The five-hour default is planning capacity only; no SLA/availability proof.
    Caller authenticates actor, dates, rights and identity externally.
    No approval or publication authority is granted.
    """
    stamp = _stamp(now, "NOW")
    _small_int(weekly_planning_minutes, "WEEKLY_PLAN", 10080)
    if (
        type(items) is not tuple
        or len(items) > _MAX_ITEMS
        or type(events) is not tuple
        or len(events) > _MAX_EVENTS
        or type(exceptions) is not tuple
        or len(exceptions) > _MAX_EXCEPTIONS
    ):
        raise ValueError(
            "DP519_INPUT_UNBOUNDED"
            if len(items) > _MAX_ITEMS or len(events) > _MAX_EVENTS
            else "DP519_EXCEPTION_UNBOUNDED"
        )
    by_key: dict[str, VisualWorkItem] = {}
    for row in items:
        _check_work(row, stamp)
        old = by_key.get(row.work_key)
        if old is not None and old != row:
            raise ValueError("DP519_WORK_KEY_CONFLICT")
        by_key[row.work_key] = row

    by_event: dict[str, VisualDecisionEvent] = {}
    for event in events:
        if type(event) is not VisualDecisionEvent:
            raise ValueError("DP519_EVENT_INVALID")
        if event.work_key not in by_key:
            raise ValueError("DP519_EVENT_FOREIGN_WORK")
        _check_event(event, by_key[event.work_key], stamp)
        old = by_event.get(event.event_id)
        if old is not None and old != event:
            raise ValueError("DP519_EVENT_REPLAY_CONFLICT")
        by_event[event.event_id] = event
    journal = tuple(
        sorted(
            by_event.values(),
            key=lambda row: (_stamp(row.completed_at, "COMPLETED"), row.event_id),
        )
    )
    last_by_work: dict[str, VisualDecisionEvent] = {}
    actor_intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    totals: dict[str, Decimal] = {}
    minutes_by_case: dict[str, Decimal] = {}
    for event in journal:
        prior = last_by_work.get(event.work_key)
        if prior is None and event.prior_event_id is not None:
            raise ValueError("DP519_EVENT_CHAIN_INVALID")
        if prior is not None and (
            event.prior_event_id != prior.event_id
            or event.started_at < prior.completed_at
        ):
            raise ValueError("DP519_EVENT_CHAIN_INVALID")
        last_by_work[event.work_key] = event
        start, stop = (
            _stamp(event.started_at, "STARTED"),
            _stamp(event.completed_at, "COMPLETED"),
        )
        spans = actor_intervals.setdefault(event.actor_id, [])
        if any(start < end and stop > beginning for beginning, end in spans):
            raise ValueError("DP519_ACTOR_TIME_OVERLAP")
        spans.append((start, stop))
        minutes = Decimal(str((stop - start).total_seconds())) / Decimal(60)
        cursor = start
        while cursor < stop:
            # Attribute measured time to actual ISO-week intervals, including
            # work crossing midnight Sunday/Monday. No time is double-counted.
            next_monday = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
            next_monday += timedelta(days=7 - cursor.weekday())
            end_part = min(stop, next_monday)
            fraction = Decimal(str((end_part - cursor).total_seconds())) / Decimal(60)
            week = _iso_week(cursor)
            totals[week] = totals.get(week, Decimal(0)) + fraction
            cursor = end_part
        minutes_by_case[event.work_key] = (
            minutes_by_case.get(event.work_key, Decimal(0)) + minutes
        )
    current_actual = totals.get(_iso_week(stamp), Decimal(0))
    remaining = max(Decimal(0), Decimal(weekly_planning_minutes) - current_actual)

    seen_exception: dict[str, VisualException] = {}
    seen_question: set[tuple[str, str]] = set()
    for row in exceptions:
        _check_exception(row, by_key)
        old = seen_exception.get(row.exception_id)
        if old is not None and old != row:
            raise ValueError("DP519_EXCEPTION_REPLAY_CONFLICT")
        if old is None:
            question_key = (row.work_key, row.question_code)
            if question_key in seen_question:
                raise ValueError("DP519_EXCEPTION_DUPLICATE_QUESTION")
            seen_question.add(question_key)
        seen_exception[row.exception_id] = row
    projected_exceptions = tuple(
        VisualExceptionRow(
            row.exception_id,
            row.work_key,
            row.question_code,
            "WAIT_QUALIFIED_EXTERNAL_AUTHORITY",
            row.estimated_minutes,
        )
        for row in sorted(seen_exception.values(), key=lambda row: row.exception_id)
    )

    def priority_for(item: VisualWorkItem) -> tuple[int, int]:
        age_days = max(0, (stamp - _stamp(item.created_at, "CREATED")).days)
        weight = {
            "IMAGE_STALE": 500,
            "IMAGE_LICENSE": 400,
            "IMAGE_IDENTITY": 300,
            "VISUAL_CAPTION": 200,
            "IMAGE_MISSING": 100,
        }[item.reason_code]
        urgency = (
            100
            if (_stamp(item.expires_at, "EXPIRES") - stamp).total_seconds() <= 86400
            else 0
        )
        return weight + urgency + min(age_days, 60), age_days

    rows: list[VisualQueueRow] = []
    reserved = Decimal(0)
    ordered = sorted(
        by_key.values(), key=lambda item: (-priority_for(item)[0], item.work_key)
    )
    for item in ordered:
        previous = last_by_work.get(item.work_key)
        priority, age = priority_for(item)
        expiring = _stamp(item.expires_at, "EXPIRES") <= stamp
        selected_previous = (
            previous is not None and previous.action == "CHOOSE_CANDIDATE"
        )
        previously_proposed = any(
            e.work_key == item.work_key and e.action == "CHOOSE_CANDIDATE"
            for e in journal
        )
        withdrawal = previously_proposed and (
            item.source_rights_state != "CLEARED"
            or item.person_identity_state != "MATCH_REVIEWED"
            or any(
                e.source_version_sha256 != item.source_version_sha256
                for e in journal
                if e.work_key == item.work_key and e.action == "CHOOSE_CANDIDATE"
            )
            or item.asset_sha256 is None
            or expiring
        )
        if item.asset_sha256 is None:
            state = "NO_IMAGE_FALLBACK"
        elif item.source_rights_state != "CLEARED":
            state = "HELD_RIGHTS_NO_IMAGE"
        elif item.person_identity_state != "MATCH_REVIEWED":
            state = "HELD_IDENTITY_NO_IMAGE"
        elif (
            previous is not None
            and previous.source_version_sha256 != item.source_version_sha256
        ):
            state = "STALE_IMAGE_VERSION_HOLD"
            withdrawal = True
        elif previous is not None and previous.action == "NO_IMAGE":
            state = "NO_IMAGE_SELECTED"
        elif previous is not None and previous.action == "WITHDRAW_IMAGE":
            state = "WITHDRAWAL_PENDING_EXTERNAL_READBACK"
            withdrawal = True
        elif expiring and selected_previous:
            state = "EXPIRED_IMAGE_HOLD"
        elif selected_previous:
            state = "PRIVATE_IMAGE_CANDIDATE_ONLY"
        elif expiring:
            state = "EXPIRED_NO_IMAGE_OPTION"
        elif (
            current_actual >= weekly_planning_minutes
            or Decimal(item.estimated_minutes) > remaining - reserved
        ):
            state = "CAPACITY_NO_IMAGE_OPTION"
        elif not item.automated_attempt_hashes:
            state = "AWAIT_AUTOMATED_ATTEMPT_PROOF"
        else:
            state = "WAIT_VISUAL_OPERATOR"
            reserved += Decimal(item.estimated_minutes)
        rows.append(
            VisualQueueRow(
                item.work_key,
                item.reason_code,
                state,
                priority,
                age,
                item.estimated_minutes
                if state in {"WAIT_VISUAL_OPERATOR", "CAPACITY_NO_IMAGE_OPTION"}
                else 0,
                previous.action if previous else None,
                withdrawal_review_required=withdrawal,
            )
        )
    rows.sort(key=lambda row: (-row.priority, row.work_key))
    unresolved = frozenset(
        {
            "WAIT_VISUAL_OPERATOR",
            "AWAIT_AUTOMATED_ATTEMPT_PROOF",
            "HELD_RIGHTS_NO_IMAGE",
            "HELD_IDENTITY_NO_IMAGE",
            "STALE_IMAGE_VERSION_HOLD",
            "CAPACITY_NO_IMAGE_OPTION",
            "EXPIRED_IMAGE_HOLD",
            "WITHDRAWAL_PENDING_EXTERNAL_READBACK",
        }
    )
    # A case may have several chained sessions (defer, resume, choose/none).
    # Each work item contributes one total to the per-reason handling median.
    # The week ledger above still attributes each minute to the actual week.
    reason_times: dict[str, list[Decimal]] = {}
    for work_key, minutes in minutes_by_case.items():
        reason_times.setdefault(by_key[work_key].reason_code, []).append(minutes)
    medians = {
        reason: Decimal(str(statistics.median(values)))
        for reason, values in sorted(reason_times.items())
    }
    metadata = {
        "version": VERSION,
        "items": [asdict(by_key[key]) for key in sorted(by_key)],
        "events": [asdict(entry) for entry in journal],
        "exceptions": [asdict(seen_exception[key]) for key in sorted(seen_exception)],
        "now": stamp.isoformat(),
        "weekly_plan": weekly_planning_minutes,
    }
    return VisualCapacityReport(
        version=VERSION,
        rows=tuple(rows),
        exceptions=projected_exceptions,
        actual_minutes_by_week={key: totals[key] for key in sorted(totals)},
        actual_minutes_this_week=current_actual,
        median_minutes_by_reason=medians,
        future_estimated_minutes=sum(row.estimated_minutes for row in rows),
        exception_estimated_minutes=sum(
            row.estimated_minutes for row in projected_exceptions
        ),
        weekly_planning_minutes=weekly_planning_minutes,
        available_planning_minutes=remaining,
        older_unresolved_count=sum(
            row.age_days >= 7 and row.state in unresolved for row in rows
        ),
        ledger_event_count=len(journal),
        ledger_fingerprint=_digest(metadata),
    )


__all__ = [
    "VERSION",
    "VisualWorkItem",
    "VisualDecisionEvent",
    "VisualException",
    "VisualQueueRow",
    "VisualExceptionRow",
    "VisualCapacityReport",
    "reconcile_visual_capacity",
]
