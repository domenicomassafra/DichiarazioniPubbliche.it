from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from dichiarazioni_pubbliche.finding_record_version import FindingRecordVersionStore
from dichiarazioni_pubbliche.policy.challenge_workflow import (
    ALLOWED_ACTOR_ROLES,
    CHALLENGE_WORKFLOW_VERSION,
    MAX_CORRECTION_REASON_CHARS,
    ChallengeContext,
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
    evaluate_transition,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


CHALLENGE_REQUEST_VERSION = "private-challenge-request-v1"
CHALLENGE_EVENT_VERSION = "private-challenge-event-v1"
MAX_CHALLENGE_ACTOR_REF_CHARS = 256
MAX_CHALLENGE_REF_CHARS = 256
MAX_TRANSITION_CONTEXT_BYTES = 8_192

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTEXT_KEYS = frozenset(
    {
        "target_record_exists",
        "target_is_leaf",
        "superseding_finding_id",
        "supersedes_chain_valid",
        "reanalysis_trigger_processed",
        "target_finding_review_approved",
        "challenge_review_approved",
        "review_is_stale",
        "original_reviewer_id",
        "separation_exception_recorded",
        "public_notice_text",
        "retention_hold_active",
    }
)


class ChallengePersistenceError(ValueError):
    pass


class ChallengeHoldDisposition(StrEnum):
    CLEAR = "CLEAR"
    HOLD = "HOLD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ChallengeRequestRecord:
    request_id: str
    request_version: str
    kind: ChallengeKind
    target_finding_id: str
    target_record_version: str
    source_request_ref: str
    prior_decision_ref: str | None
    initiated_by_actor_ref: str
    initiated_by_role: ChallengeRole
    reason: str
    policy_version: str
    request_integrity_sha256: str


@dataclass(frozen=True)
class ChallengeEventRecord:
    event_id: str
    event_version: str
    request_id: str
    kind: ChallengeKind
    sequence: int
    from_state: ChallengeState | None
    to_state: ChallengeState
    actor_ref: str
    actor_role: ChallengeRole
    reason: str
    policy_version: str
    target_record_version: str
    transition_context: dict[str, object]
    previous_event_id: str | None
    previous_integrity_sha256: str | None
    event_integrity_sha256: str


@dataclass(frozen=True)
class ChallengeAppendResult:
    request: ChallengeRequestRecord
    event: ChallengeEventRecord
    created: bool


@dataclass(frozen=True)
class ChallengeReplay:
    request: ChallengeRequestRecord | None
    events: tuple[ChallengeEventRecord, ...]
    blockers: tuple[str, ...]

    @property
    def current_state(self) -> ChallengeState | None:
        return self.events[-1].to_state if self.events and not self.blockers else None


@dataclass(frozen=True)
class ChallengeHoldResult:
    disposition: ChallengeHoldDisposition
    finding_id: str
    record_version: str | None
    request_id: str | None = None
    event_id: str | None = None
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.disposition is ChallengeHoldDisposition.UNKNOWN


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _bounded_text(value: object, code: str, *, limit: int = MAX_CHALLENGE_REF_CHARS) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or _CONTROL_CHARACTERS.search(text):
        raise ChallengePersistenceError(code)
    return text


def _reason(value: object) -> str:
    return _bounded_text(
        value,
        "CHALLENGE_REASON_INVALID",
        limit=MAX_CORRECTION_REASON_CHARS,
    )


def _optional_ref(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _bounded_text(value, code)


def _kind(value: ChallengeKind | str) -> ChallengeKind:
    try:
        return ChallengeKind(str(value))
    except ValueError as exc:
        raise ChallengePersistenceError("CHALLENGE_KIND_INVALID") from exc


def _role(value: ChallengeRole | str) -> ChallengeRole:
    try:
        return ChallengeRole(str(value))
    except ValueError as exc:
        raise ChallengePersistenceError("CHALLENGE_ACTOR_ROLE_INVALID") from exc


def _state(value: object, code: str) -> ChallengeState:
    try:
        return ChallengeState(str(value))
    except ValueError as exc:
        raise ChallengePersistenceError(code) from exc


def _bool(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise ChallengePersistenceError(code)
    return value


def _request_integrity_material(
    *,
    kind: ChallengeKind,
    target_finding_id: str,
    target_record_version: str,
    source_request_ref: str,
    prior_decision_ref: str | None,
    actor_ref: str,
    actor_role: ChallengeRole,
    reason: str,
) -> dict[str, object]:
    return {
        "request_version": CHALLENGE_REQUEST_VERSION,
        "kind": kind.value,
        "target_finding_id": target_finding_id,
        "target_record_version": target_record_version,
        "source_request_ref": source_request_ref,
        "prior_decision_ref": prior_decision_ref,
        "initiated_by_actor_ref": actor_ref,
        "initiated_by_role": actor_role.value,
        "reason": reason,
        "policy_version": CHALLENGE_WORKFLOW_VERSION,
    }


def _event_integrity_material(
    *,
    request_id: str,
    kind: ChallengeKind,
    sequence: int,
    from_state: ChallengeState | None,
    to_state: ChallengeState,
    actor_ref: str,
    actor_role: ChallengeRole,
    reason: str,
    target_record_version: str,
    transition_context: Mapping[str, object],
    previous_event_id: str | None,
    previous_integrity_sha256: str | None,
) -> dict[str, object]:
    return {
        "event_version": CHALLENGE_EVENT_VERSION,
        "request_id": request_id,
        "kind": kind.value,
        "sequence": sequence,
        "from_state": from_state.value if from_state is not None else None,
        "to_state": to_state.value,
        "actor_ref": actor_ref,
        "actor_role": actor_role.value,
        "reason": reason,
        "policy_version": CHALLENGE_WORKFLOW_VERSION,
        "target_record_version": target_record_version,
        "transition_context": dict(transition_context),
        "previous_event_id": previous_event_id,
        "previous_integrity_sha256": previous_integrity_sha256,
    }


def _request_from_row(row: Mapping[str, object]) -> ChallengeRequestRecord:
    integrity = _bounded_text(
        row.get("request_integrity_sha256"), "CHALLENGE_REQUEST_INTEGRITY_INVALID", limit=64
    ).lower()
    if not _SHA256_RE.fullmatch(integrity):
        raise ChallengePersistenceError("CHALLENGE_REQUEST_INTEGRITY_INVALID")
    request = ChallengeRequestRecord(
        request_id=_bounded_text(row.get("request_id"), "CHALLENGE_REQUEST_ID_INVALID"),
        request_version=_bounded_text(
            row.get("request_version"), "CHALLENGE_REQUEST_VERSION_INVALID"
        ),
        kind=_kind(str(row.get("challenge_kind") or "")),
        target_finding_id=_bounded_text(
            row.get("target_finding_id"), "CHALLENGE_TARGET_FINDING_ID_INVALID"
        ),
        target_record_version=_bounded_text(
            row.get("target_record_version"), "CHALLENGE_TARGET_RECORD_VERSION_INVALID"
        ),
        source_request_ref=_bounded_text(
            row.get("source_request_ref"), "CHALLENGE_SOURCE_REQUEST_REF_INVALID"
        ),
        prior_decision_ref=_optional_ref(
            row.get("prior_decision_ref"), "CHALLENGE_PRIOR_DECISION_REF_INVALID"
        ),
        initiated_by_actor_ref=_bounded_text(
            row.get("initiated_by_actor_ref"), "CHALLENGE_ACTOR_REF_INVALID"
        ),
        initiated_by_role=_role(str(row.get("initiated_by_role") or "")),
        reason=_reason(row.get("reason")),
        policy_version=_bounded_text(
            row.get("policy_version"), "CHALLENGE_POLICY_VERSION_INVALID", limit=128
        ),
        request_integrity_sha256=integrity,
    )
    return request


def _event_from_row(row: Mapping[str, object]) -> ChallengeEventRecord:
    context = row.get("transition_context")
    if not isinstance(context, dict) or set(context) - _CONTEXT_KEYS:
        raise ChallengePersistenceError("CHALLENGE_EVENT_CONTEXT_INVALID")
    if len(_canonical_json(context).encode("utf-8")) > MAX_TRANSITION_CONTEXT_BYTES:
        raise ChallengePersistenceError("CHALLENGE_EVENT_CONTEXT_INVALID")
    integrity = _bounded_text(
        row.get("event_integrity_sha256"), "CHALLENGE_EVENT_INTEGRITY_INVALID", limit=64
    ).lower()
    if not _SHA256_RE.fullmatch(integrity):
        raise ChallengePersistenceError("CHALLENGE_EVENT_INTEGRITY_INVALID")
    previous_integrity = _optional_ref(
        row.get("previous_integrity_sha256"), "CHALLENGE_PREVIOUS_INTEGRITY_INVALID"
    )
    if previous_integrity is not None and not _SHA256_RE.fullmatch(previous_integrity):
        raise ChallengePersistenceError("CHALLENGE_PREVIOUS_INTEGRITY_INVALID")
    raw_from = row.get("from_state")
    return ChallengeEventRecord(
        event_id=_bounded_text(row.get("event_id"), "CHALLENGE_EVENT_ID_INVALID"),
        event_version=_bounded_text(
            row.get("event_version"), "CHALLENGE_EVENT_VERSION_INVALID"
        ),
        request_id=_bounded_text(row.get("request_id"), "CHALLENGE_REQUEST_ID_INVALID"),
        kind=_kind(str(row.get("challenge_kind") or "")),
        sequence=int(row.get("event_sequence") or 0),
        from_state=(
            _state(raw_from, "CHALLENGE_FROM_STATE_INVALID") if raw_from is not None else None
        ),
        to_state=_state(row.get("to_state"), "CHALLENGE_TO_STATE_INVALID"),
        actor_ref=_bounded_text(row.get("actor_ref"), "CHALLENGE_ACTOR_REF_INVALID"),
        actor_role=_role(str(row.get("actor_role") or "")),
        reason=_reason(row.get("reason")),
        policy_version=_bounded_text(
            row.get("policy_version"), "CHALLENGE_POLICY_VERSION_INVALID", limit=128
        ),
        target_record_version=_bounded_text(
            row.get("target_record_version"), "CHALLENGE_TARGET_RECORD_VERSION_INVALID"
        ),
        transition_context=dict(context),
        previous_event_id=_optional_ref(
            row.get("previous_event_id"), "CHALLENGE_PREVIOUS_EVENT_ID_INVALID"
        ),
        previous_integrity_sha256=previous_integrity,
        event_integrity_sha256=integrity,
    )


def _transition_context(
    *,
    target_is_leaf: bool,
    superseding_finding_id: str | None,
    supersedes_chain_valid: bool,
    reanalysis_trigger_processed: bool,
    target_finding_review_approved: bool,
    challenge_review_approved: bool,
    original_reviewer_id: str | None,
    separation_exception_recorded: bool,
    public_notice_text: str | None,
    retention_hold_active: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "target_record_exists": True,
        "target_is_leaf": bool(target_is_leaf),
        "superseding_finding_id": superseding_finding_id,
        "supersedes_chain_valid": bool(supersedes_chain_valid),
        "reanalysis_trigger_processed": bool(reanalysis_trigger_processed),
        "target_finding_review_approved": bool(target_finding_review_approved),
        "challenge_review_approved": bool(challenge_review_approved),
        "review_is_stale": False,
        "original_reviewer_id": original_reviewer_id,
        "separation_exception_recorded": bool(separation_exception_recorded),
        "public_notice_text": public_notice_text,
        "retention_hold_active": bool(retention_hold_active),
    }
    if len(_canonical_json(payload).encode("utf-8")) > MAX_TRANSITION_CONTEXT_BYTES:
        raise ChallengePersistenceError("CHALLENGE_EVENT_CONTEXT_INVALID")
    return payload


def _context_from_event(event: ChallengeEventRecord) -> ChallengeContext:
    if event.from_state is None:
        raise ChallengePersistenceError("CHALLENGE_EVENT_ROOT_HAS_NO_TRANSITION")
    raw = event.transition_context
    return ChallengeContext(
        kind=event.kind,
        current_state=event.from_state,
        actor_role=event.actor_role,
        actor_id=event.actor_ref,
        reason=event.reason,
        target_record_exists=_bool(
            raw.get("target_record_exists", False), "CHALLENGE_CONTEXT_TARGET_EXISTS_INVALID"
        ),
        target_is_leaf=_bool(
            raw.get("target_is_leaf", False), "CHALLENGE_CONTEXT_TARGET_LEAF_INVALID"
        ),
        superseding_finding_id=_optional_ref(
            raw.get("superseding_finding_id"), "CHALLENGE_CONTEXT_SUPERSEDING_ID_INVALID"
        ),
        supersedes_chain_valid=_bool(
            raw.get("supersedes_chain_valid", False), "CHALLENGE_CONTEXT_CHAIN_INVALID"
        ),
        reanalysis_trigger_processed=_bool(
            raw.get("reanalysis_trigger_processed", False),
            "CHALLENGE_CONTEXT_REANALYSIS_INVALID",
        ),
        target_finding_review_approved=_bool(
            raw.get("target_finding_review_approved", False),
            "CHALLENGE_CONTEXT_FINDING_REVIEW_INVALID",
        ),
        challenge_review_approved=_bool(
            raw.get("challenge_review_approved", False),
            "CHALLENGE_CONTEXT_CHALLENGE_REVIEW_INVALID",
        ),
        review_is_stale=_bool(
            raw.get("review_is_stale", False), "CHALLENGE_CONTEXT_STALE_INVALID"
        ),
        original_reviewer_id=_optional_ref(
            raw.get("original_reviewer_id"), "CHALLENGE_CONTEXT_ORIGINAL_REVIEWER_INVALID"
        ),
        separation_exception_recorded=_bool(
            raw.get("separation_exception_recorded", False),
            "CHALLENGE_CONTEXT_SEPARATION_INVALID",
        ),
        public_notice_text=(
            _bounded_text(
                raw.get("public_notice_text"),
                "CHALLENGE_CONTEXT_PUBLIC_NOTICE_INVALID",
                limit=2_000,
            )
            if raw.get("public_notice_text") is not None
            else None
        ),
        retention_hold_active=_bool(
            raw.get("retention_hold_active", False),
            "CHALLENGE_CONTEXT_RETENTION_HOLD_INVALID",
        ),
    )


class PrivateChallengeLedgerStore(PsqlRuntime):
    """Private DP-303 event ledger. No method here publishes, deletes, or decides legality."""

    def _version_store(self) -> FindingRecordVersionStore:
        return FindingRecordVersionStore(self.database_url, self.psql)

    def _current_record_version(self, finding_id: str) -> str:
        return self._version_store().current_record_version(finding_id).record_version

    def _load_request(self, request_id: str) -> ChallengeRequestRecord | None:
        clean_id = _bounded_text(request_id, "CHALLENGE_REQUEST_ID_INVALID")
        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'request_id', request_id,
                'request_version', request_version,
                'challenge_kind', challenge_kind,
                'target_finding_id', target_finding_id,
                'target_record_version', target_record_version,
                'source_request_ref', source_request_ref,
                'prior_decision_ref', prior_decision_ref,
                'initiated_by_actor_ref', initiated_by_actor_ref,
                'initiated_by_role', initiated_by_role,
                'reason', reason,
                'policy_version', policy_version,
                'request_integrity_sha256', request_integrity_sha256
            )::text, '')
            FROM private_challenge_request
            WHERE request_id = :'request_id';
            """,
            request_id=clean_id,
        )
        if not raw:
            return None
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ChallengePersistenceError("CHALLENGE_REQUEST_ROW_INVALID")
        return _request_from_row(row)

    def _load_events(self, request_id: str) -> tuple[ChallengeEventRecord, ...]:
        clean_id = _bounded_text(request_id, "CHALLENGE_REQUEST_ID_INVALID")
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'event_id', event_id,
                'event_version', event_version,
                'request_id', request_id,
                'challenge_kind', challenge_kind,
                'event_sequence', event_sequence,
                'from_state', from_state,
                'to_state', to_state,
                'actor_ref', actor_ref,
                'actor_role', actor_role,
                'reason', reason,
                'policy_version', policy_version,
                'target_record_version', target_record_version,
                'transition_context', transition_context,
                'previous_event_id', previous_event_id,
                'previous_integrity_sha256', previous_integrity_sha256,
                'event_integrity_sha256', event_integrity_sha256
            ) ORDER BY event_sequence)::text, '[]')
            FROM private_challenge_event
            WHERE request_id = :'request_id';
            """,
            request_id=clean_id,
        )
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list):
            raise ChallengePersistenceError("CHALLENGE_EVENT_ROWS_INVALID")
        return tuple(_event_from_row(row) for row in rows)

    def replay_request(self, request_id: str) -> ChallengeReplay:
        try:
            request = self._load_request(request_id)
            if request is None:
                return ChallengeReplay(None, (), ("CHALLENGE_REQUEST_NOT_FOUND",))
            events = self._load_events(request.request_id)
        except (ChallengePersistenceError, TypeError, ValueError, json.JSONDecodeError):
            return ChallengeReplay(None, (), ("CHALLENGE_LEDGER_ROW_INVALID",))

        blockers: list[str] = []
        if request.request_version != CHALLENGE_REQUEST_VERSION:
            blockers.append("CHALLENGE_REQUEST_VERSION_STALE")
        if request.policy_version != CHALLENGE_WORKFLOW_VERSION:
            blockers.append("CHALLENGE_POLICY_VERSION_STALE")
        expected_request_integrity = _json_sha256(
            _request_integrity_material(
                kind=request.kind,
                target_finding_id=request.target_finding_id,
                target_record_version=request.target_record_version,
                source_request_ref=request.source_request_ref,
                prior_decision_ref=request.prior_decision_ref,
                actor_ref=request.initiated_by_actor_ref,
                actor_role=request.initiated_by_role,
                reason=request.reason,
            )
        )
        if request.request_integrity_sha256 != expected_request_integrity:
            blockers.append("CHALLENGE_REQUEST_INTEGRITY_INVALID")
        if request.request_id != f"challenge-request:{expected_request_integrity}":
            blockers.append("CHALLENGE_REQUEST_ID_INTEGRITY_INVALID")
        if request.initiated_by_role not in ALLOWED_ACTOR_ROLES[request.kind][
            ChallengeState.PRIVATE_RECEIVED
        ]:
            blockers.append("CHALLENGE_INITIATOR_ROLE_INVALID")
        if request.kind is ChallengeKind.APPEAL and request.prior_decision_ref is None:
            blockers.append("CHALLENGE_APPEAL_PRIOR_DECISION_MISSING")
        if request.kind is not ChallengeKind.APPEAL and request.prior_decision_ref is not None:
            blockers.append("CHALLENGE_PRIOR_DECISION_KIND_MISMATCH")
        if not events:
            blockers.append("CHALLENGE_EVENT_CHAIN_MISSING")
            return ChallengeReplay(request, (), tuple(dict.fromkeys(blockers)))

        previous: ChallengeEventRecord | None = None
        for index, event in enumerate(events, start=1):
            if event.sequence != index:
                blockers.append("CHALLENGE_EVENT_SEQUENCE_INVALID")
            if event.request_id != request.request_id or event.kind is not request.kind:
                blockers.append("CHALLENGE_EVENT_REQUEST_BINDING_INVALID")
            if event.target_record_version != request.target_record_version:
                blockers.append("CHALLENGE_EVENT_RECORD_VERSION_BINDING_INVALID")
            if event.event_version != CHALLENGE_EVENT_VERSION:
                blockers.append("CHALLENGE_EVENT_VERSION_STALE")
            if event.policy_version != CHALLENGE_WORKFLOW_VERSION:
                blockers.append("CHALLENGE_EVENT_POLICY_VERSION_STALE")
            expected_integrity = _json_sha256(
                _event_integrity_material(
                    request_id=event.request_id,
                    kind=event.kind,
                    sequence=event.sequence,
                    from_state=event.from_state,
                    to_state=event.to_state,
                    actor_ref=event.actor_ref,
                    actor_role=event.actor_role,
                    reason=event.reason,
                    target_record_version=event.target_record_version,
                    transition_context=event.transition_context,
                    previous_event_id=event.previous_event_id,
                    previous_integrity_sha256=event.previous_integrity_sha256,
                )
            )
            if event.event_integrity_sha256 != expected_integrity:
                blockers.append("CHALLENGE_EVENT_INTEGRITY_INVALID")
            if event.event_id != f"challenge-event:{expected_integrity}":
                blockers.append("CHALLENGE_EVENT_ID_INTEGRITY_INVALID")

            if previous is None:
                if (
                    event.sequence != 1
                    or event.from_state is not None
                    or event.to_state is not ChallengeState.PRIVATE_RECEIVED
                    or event.previous_event_id is not None
                    or event.previous_integrity_sha256 is not None
                    or event.transition_context
                ):
                    blockers.append("CHALLENGE_EVENT_ROOT_INVALID")
                if event.actor_role != request.initiated_by_role or event.actor_ref != request.initiated_by_actor_ref:
                    blockers.append("CHALLENGE_EVENT_ROOT_ACTOR_MISMATCH")
            else:
                if event.actor_role is ChallengeRole.PUBLIC_SUBMITTER:
                    blockers.append("CHALLENGE_PUBLIC_SUBMITTER_TRANSITION_FORBIDDEN")
                if event.previous_event_id != previous.event_id:
                    blockers.append("CHALLENGE_EVENT_PREVIOUS_ID_INVALID")
                if event.previous_integrity_sha256 != previous.event_integrity_sha256:
                    blockers.append("CHALLENGE_EVENT_PREVIOUS_INTEGRITY_INVALID")
                if event.from_state is not previous.to_state:
                    blockers.append("CHALLENGE_EVENT_STATE_CHAIN_INVALID")
                try:
                    context = _context_from_event(event)
                    decision = evaluate_transition(context)
                    if not decision.allowed or decision.next_state is not event.to_state:
                        blockers.append("CHALLENGE_EVENT_POLICY_REPLAY_INVALID")
                except (ChallengePersistenceError, TypeError, ValueError):
                    blockers.append("CHALLENGE_EVENT_CONTEXT_INVALID")
            previous = event
        return ChallengeReplay(request, events, tuple(dict.fromkeys(blockers)))

    def initiate_request(
        self,
        *,
        kind: ChallengeKind | str,
        target_finding_id: str,
        source_request_ref: str,
        actor_ref: str,
        actor_role: ChallengeRole | str,
        reason: str,
        prior_decision_ref: str | None = None,
    ) -> ChallengeAppendResult:
        canonical_kind = _kind(kind)
        canonical_role = _role(actor_role)
        clean_target = _bounded_text(
            target_finding_id, "CHALLENGE_TARGET_FINDING_ID_INVALID"
        )
        clean_source_ref = _bounded_text(
            source_request_ref, "CHALLENGE_SOURCE_REQUEST_REF_INVALID"
        )
        clean_actor = _bounded_text(
            actor_ref, "CHALLENGE_ACTOR_REF_INVALID", limit=MAX_CHALLENGE_ACTOR_REF_CHARS
        )
        clean_reason = _reason(reason)
        clean_prior = _optional_ref(
            prior_decision_ref, "CHALLENGE_PRIOR_DECISION_REF_INVALID"
        )
        if canonical_role not in ALLOWED_ACTOR_ROLES[canonical_kind][
            ChallengeState.PRIVATE_RECEIVED
        ]:
            raise ChallengePersistenceError("CHALLENGE_INITIATOR_ROLE_INVALID")
        if canonical_kind is ChallengeKind.APPEAL:
            if clean_prior is None:
                raise ChallengePersistenceError("CHALLENGE_APPEAL_PRIOR_DECISION_REQUIRED")
        elif clean_prior is not None:
            raise ChallengePersistenceError("CHALLENGE_PRIOR_DECISION_KIND_MISMATCH")

        target_record_version = self._current_record_version(clean_target)
        request_integrity = _json_sha256(
            _request_integrity_material(
                kind=canonical_kind,
                target_finding_id=clean_target,
                target_record_version=target_record_version,
                source_request_ref=clean_source_ref,
                prior_decision_ref=clean_prior,
                actor_ref=clean_actor,
                actor_role=canonical_role,
                reason=clean_reason,
            )
        )
        request_id = f"challenge-request:{request_integrity}"
        root_integrity = _json_sha256(
            _event_integrity_material(
                request_id=request_id,
                kind=canonical_kind,
                sequence=1,
                from_state=None,
                to_state=ChallengeState.PRIVATE_RECEIVED,
                actor_ref=clean_actor,
                actor_role=canonical_role,
                reason=clean_reason,
                target_record_version=target_record_version,
                transition_context={},
                previous_event_id=None,
                previous_integrity_sha256=None,
            )
        )
        root_event_id = f"challenge-event:{root_integrity}"
        raw = self.run(
            """
            WITH request_inserted AS (
                INSERT INTO private_challenge_request (
                    request_id, request_version, challenge_kind, target_finding_id,
                    target_record_version, source_request_ref, prior_decision_ref,
                    initiated_by_actor_ref, initiated_by_role, reason, policy_version,
                    request_integrity_sha256
                ) VALUES (
                    :'request_id', :'request_version', :'challenge_kind', :'target_finding_id',
                    :'target_record_version', :'source_request_ref',
                    NULLIF(:'prior_decision_ref',''), :'actor_ref', :'actor_role', :'reason',
                    :'policy_version', :'request_integrity_sha256'
                )
                ON CONFLICT DO NOTHING
                RETURNING request_id
            ), request_ready AS (
                SELECT request_id FROM request_inserted
                UNION ALL
                SELECT request_id FROM private_challenge_request
                WHERE request_id = :'request_id'
                  AND request_integrity_sha256 = :'request_integrity_sha256'
                LIMIT 1
            ), event_inserted AS (
                INSERT INTO private_challenge_event (
                    event_id, event_version, request_id, challenge_kind, event_sequence,
                    from_state, to_state, actor_ref, actor_role, reason, policy_version,
                    target_record_version, transition_context, previous_event_id,
                    previous_integrity_sha256, event_integrity_sha256
                )
                SELECT
                    :'event_id', :'event_version', request_ready.request_id, :'challenge_kind', 1,
                    NULL, 'PRIVATE_RECEIVED', :'actor_ref', :'actor_role', :'reason',
                    :'policy_version', :'target_record_version', '{}'::jsonb, NULL, NULL,
                    :'event_integrity_sha256'
                FROM request_ready
                ON CONFLICT DO NOTHING
                RETURNING event_id
            )
            SELECT json_build_object(
                'request_created', EXISTS(SELECT 1 FROM request_inserted),
                'event_created', EXISTS(SELECT 1 FROM event_inserted)
            )::text;
            """,
            request_id=request_id,
            request_version=CHALLENGE_REQUEST_VERSION,
            challenge_kind=canonical_kind.value,
            target_finding_id=clean_target,
            target_record_version=target_record_version,
            source_request_ref=clean_source_ref,
            prior_decision_ref=clean_prior or "",
            actor_ref=clean_actor,
            actor_role=canonical_role.value,
            reason=clean_reason,
            policy_version=CHALLENGE_WORKFLOW_VERSION,
            request_integrity_sha256=request_integrity,
            event_id=root_event_id,
            event_version=CHALLENGE_EVENT_VERSION,
            event_integrity_sha256=root_integrity,
        )
        result = json.loads(raw or "{}")
        replay = self.replay_request(request_id)
        if replay.blockers or replay.request is None or not replay.events:
            raise ChallengePersistenceError(
                replay.blockers[0] if replay.blockers else "CHALLENGE_INITIATION_REFUSED"
            )
        return ChallengeAppendResult(
            request=replay.request,
            event=replay.events[0],
            created=bool(result.get("request_created") or result.get("event_created")),
        )

    def transition_request(
        self,
        request_id: str,
        *,
        actor_ref: str,
        actor_role: ChallengeRole | str,
        reason: str,
        target_is_leaf: bool = True,
        superseding_finding_id: str | None = None,
        supersedes_chain_valid: bool = False,
        reanalysis_trigger_processed: bool = False,
        target_finding_review_approved: bool = False,
        challenge_review_approved: bool = False,
        original_reviewer_id: str | None = None,
        separation_exception_recorded: bool = False,
        public_notice_text: str | None = None,
        retention_hold_active: bool = False,
    ) -> ChallengeAppendResult:
        replay = self.replay_request(request_id)
        if replay.blockers or replay.request is None or not replay.events:
            raise ChallengePersistenceError(
                replay.blockers[0] if replay.blockers else "CHALLENGE_REQUEST_NOT_FOUND"
            )
        request = replay.request
        previous = replay.events[-1]
        clean_actor = _bounded_text(
            actor_ref, "CHALLENGE_ACTOR_REF_INVALID", limit=MAX_CHALLENGE_ACTOR_REF_CHARS
        )
        canonical_role = _role(actor_role)
        clean_reason = _reason(reason)
        current_version = self._current_record_version(request.target_finding_id)
        version_stale = current_version != request.target_record_version
        context_payload = _transition_context(
            target_is_leaf=target_is_leaf,
            superseding_finding_id=_optional_ref(
                superseding_finding_id, "CHALLENGE_CONTEXT_SUPERSEDING_ID_INVALID"
            ),
            supersedes_chain_valid=supersedes_chain_valid,
            reanalysis_trigger_processed=reanalysis_trigger_processed,
            target_finding_review_approved=target_finding_review_approved,
            challenge_review_approved=challenge_review_approved,
            original_reviewer_id=_optional_ref(
                original_reviewer_id, "CHALLENGE_CONTEXT_ORIGINAL_REVIEWER_INVALID"
            ),
            separation_exception_recorded=separation_exception_recorded,
            public_notice_text=public_notice_text,
            retention_hold_active=retention_hold_active,
        )
        context_payload["review_is_stale"] = version_stale
        if (
            previous.from_state is not None
            and previous.actor_ref == clean_actor
            and previous.actor_role is canonical_role
            and previous.reason == clean_reason
            and previous.target_record_version == request.target_record_version
            and previous.transition_context == context_payload
        ):
            # Exact retry of the last durable transition. Returning the already
            # replay-verified event makes request retries idempotent without
            # granting a caller control over the derived next state.
            return ChallengeAppendResult(request, previous, False)
        context = ChallengeContext(
            kind=request.kind,
            current_state=previous.to_state,
            actor_role=canonical_role,
            actor_id=clean_actor,
            reason=clean_reason,
            target_record_exists=True,
            target_is_leaf=target_is_leaf,
            superseding_finding_id=context_payload["superseding_finding_id"],  # type: ignore[arg-type]
            supersedes_chain_valid=supersedes_chain_valid,
            reanalysis_trigger_processed=reanalysis_trigger_processed,
            target_finding_review_approved=target_finding_review_approved,
            challenge_review_approved=challenge_review_approved,
            review_is_stale=version_stale,
            original_reviewer_id=context_payload["original_reviewer_id"],  # type: ignore[arg-type]
            separation_exception_recorded=separation_exception_recorded,
            public_notice_text=public_notice_text,
            retention_hold_active=retention_hold_active,
        )
        decision = evaluate_transition(context)
        if canonical_role is ChallengeRole.PUBLIC_SUBMITTER:
            raise ChallengePersistenceError("CHALLENGE_PUBLIC_SUBMITTER_TRANSITION_FORBIDDEN")
        if not decision.allowed:
            raise ChallengePersistenceError(decision.reason)

        sequence = previous.sequence + 1
        integrity = _json_sha256(
            _event_integrity_material(
                request_id=request.request_id,
                kind=request.kind,
                sequence=sequence,
                from_state=previous.to_state,
                to_state=decision.next_state,
                actor_ref=clean_actor,
                actor_role=canonical_role,
                reason=clean_reason,
                target_record_version=request.target_record_version,
                transition_context=context_payload,
                previous_event_id=previous.event_id,
                previous_integrity_sha256=previous.event_integrity_sha256,
            )
        )
        event_id = f"challenge-event:{integrity}"
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO private_challenge_event (
                    event_id, event_version, request_id, challenge_kind, event_sequence,
                    from_state, to_state, actor_ref, actor_role, reason, policy_version,
                    target_record_version, transition_context, previous_event_id,
                    previous_integrity_sha256, event_integrity_sha256
                ) VALUES (
                    :'event_id', :'event_version', :'request_id', :'challenge_kind',
                    :'event_sequence'::integer, :'from_state', :'to_state', :'actor_ref',
                    :'actor_role', :'reason', :'policy_version', :'target_record_version',
                    :'transition_context'::jsonb, :'previous_event_id',
                    :'previous_integrity_sha256', :'event_integrity_sha256'
                )
                ON CONFLICT DO NOTHING
                RETURNING event_id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            event_id=event_id,
            event_version=CHALLENGE_EVENT_VERSION,
            request_id=request.request_id,
            challenge_kind=request.kind.value,
            event_sequence=sequence,
            from_state=previous.to_state.value,
            to_state=decision.next_state.value,
            actor_ref=clean_actor,
            actor_role=canonical_role.value,
            reason=clean_reason,
            policy_version=CHALLENGE_WORKFLOW_VERSION,
            target_record_version=request.target_record_version,
            transition_context=_canonical_json(context_payload),
            previous_event_id=previous.event_id,
            previous_integrity_sha256=previous.event_integrity_sha256,
            event_integrity_sha256=integrity,
        )
        created = str(raw or "").lower() in {"t", "true", "1"}
        updated = self.replay_request(request.request_id)
        if updated.blockers or updated.request is None:
            raise ChallengePersistenceError(
                updated.blockers[0] if updated.blockers else "CHALLENGE_TRANSITION_REFUSED"
            )
        matching = next((event for event in updated.events if event.event_id == event_id), None)
        if matching is None:
            raise ChallengePersistenceError("CHALLENGE_CONCURRENT_TRANSITION")
        return ChallengeAppendResult(updated.request, matching, created)

    def current_hold_for_finding(self, finding_id: str) -> ChallengeHoldResult:
        clean_finding = _bounded_text(
            finding_id, "CHALLENGE_TARGET_FINDING_ID_INVALID"
        )
        try:
            current_version = self._current_record_version(clean_finding)
        except Exception:  # noqa: BLE001 - read-side gate must fail closed
            return ChallengeHoldResult(
                ChallengeHoldDisposition.UNKNOWN,
                clean_finding,
                None,
                blockers=("CHALLENGE_TARGET_VERSION_UNAVAILABLE",),
            )
        try:
            raw = self.run(
                """
                SELECT COALESCE(json_agg(request_id ORDER BY created_at, request_id)::text, '[]')
                FROM private_challenge_request
                WHERE target_finding_id = :'finding_id'
                  AND challenge_kind = 'TAKEDOWN';
                """,
                finding_id=clean_finding,
            )
            request_ids = json.loads(raw or "[]")
        except Exception:  # noqa: BLE001 - read-side gate must fail closed
            return ChallengeHoldResult(
                ChallengeHoldDisposition.UNKNOWN,
                clean_finding,
                current_version,
                blockers=("CHALLENGE_HOLD_LEDGER_UNAVAILABLE",),
            )
        if not isinstance(request_ids, list):
            return ChallengeHoldResult(
                ChallengeHoldDisposition.UNKNOWN,
                clean_finding,
                current_version,
                blockers=("CHALLENGE_HOLD_LEDGER_INVALID",),
            )
        if not request_ids:
            return ChallengeHoldResult(
                ChallengeHoldDisposition.CLEAR,
                clean_finding,
                current_version,
            )

        valid: list[ChallengeReplay] = []
        blockers: list[str] = []
        for request_id in request_ids:
            replay = self.replay_request(str(request_id))
            if replay.blockers or replay.request is None:
                blockers.extend(replay.blockers or ("CHALLENGE_HOLD_LEDGER_INVALID",))
                continue
            if replay.request.target_record_version != current_version:
                blockers.append("CHALLENGE_HOLD_RECORD_VERSION_STALE")
                continue
            valid.append(replay)
        if blockers:
            return ChallengeHoldResult(
                ChallengeHoldDisposition.UNKNOWN,
                clean_finding,
                current_version,
                blockers=tuple(dict.fromkeys(blockers)),
            )
        for replay in valid:
            if replay.current_state is ChallengeState.PUBLIC_HOLD_APPROVED:
                latest = replay.events[-1]
                return ChallengeHoldResult(
                    ChallengeHoldDisposition.HOLD,
                    clean_finding,
                    current_version,
                    request_id=replay.request.request_id if replay.request else None,
                    event_id=latest.event_id,
                )
        return ChallengeHoldResult(
            ChallengeHoldDisposition.CLEAR,
            clean_finding,
            current_version,
        )


__all__ = [
    "CHALLENGE_EVENT_VERSION",
    "CHALLENGE_REQUEST_VERSION",
    "ChallengeAppendResult",
    "ChallengeEventRecord",
    "ChallengeHoldDisposition",
    "ChallengeHoldResult",
    "ChallengePersistenceError",
    "ChallengeReplay",
    "ChallengeRequestRecord",
    "PrivateChallengeLedgerStore",
]
