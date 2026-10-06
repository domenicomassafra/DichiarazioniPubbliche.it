"""DP-303 callable edge/service for correction, takedown, and appeal intake.

The public HTTP surface is deliberately absent.  This module is a disabled-by-default
service boundary that composes the existing DP-303 pure state machine with the
canonical private correction persistence path in ``review_admin.record_correction``.

CORRECTION continues to use the canonical correction/re-analysis path. TAKEDOWN and APPEAL
use the private DP-303 append-only challenge ledger; neither path mutates a Finding or
publishes a hold/decision from intake.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Protocol

from dichiarazioni_pubbliche.challenge_persistence import (
    ChallengeAppendResult,
    ChallengeReplay,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.correction_runtime import MAX_CHANGED_FIELDS_BYTES
from dichiarazioni_pubbliche.policy.challenge_workflow import (
    CHALLENGE_WORKFLOW_VERSION,
    ChallengeContext,
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
    MAX_CORRECTION_REASON_CHARS,
    build_correction_record_id,
    evaluate_transition,
)
from dichiarazioni_pubbliche.policy.intake_policy import (
    IntakeDisposition,
    RateLimitProfile,
    RateLimitState,
    rate_limit_decision,
)
from dichiarazioni_pubbliche.review_admin import record_correction


MAX_CHALLENGE_ID_CHARS = 200
MAX_REQUEST_FIELDS = 6
MAX_REQUEST_BYTES = 48_000
MAX_ACK_BYTES = 640
MAX_LOGGABLE_RECEIPT_BYTES = 896

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ChallengeServiceState(StrEnum):
    REANALYSIS_PENDING_PRIVATE = "REANALYSIS_PENDING_PRIVATE"
    TRIAGE_PENDING_PRIVATE = "TRIAGE_PENDING_PRIVATE"
    INDEPENDENT_REVIEW_PENDING_PRIVATE = "INDEPENDENT_REVIEW_PENDING_PRIVATE"
    DEPENDENCY_BLOCKED_PRIVATE = "DEPENDENCY_BLOCKED_PRIVATE"
    NOT_RECEIVED = "NOT_RECEIVED"
    DEFERRED = "DEFERRED"


class ChallengeServiceReason(StrEnum):
    OK = "OK"
    LAUNCH_PROFILE_MISSING = "LAUNCH_PROFILE_MISSING"
    INTAKE_DISABLED = "INTAKE_DISABLED"
    KIND_DISABLED = "KIND_DISABLED"
    WRONG_TYPE = "WRONG_TYPE"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    UNKNOWN_KIND = "UNKNOWN_KIND"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    MISSING_FIELD = "MISSING_FIELD"
    IDENTIFIER_INVALID = "IDENTIFIER_INVALID"
    REASON_INVALID = "REASON_INVALID"
    CHANGED_FIELDS_INVALID = "CHANGED_FIELDS_INVALID"
    RATE_DECISION_MISSING = "RATE_DECISION_MISSING"
    CORRECTION_CHAIN_INVALID = "CORRECTION_CHAIN_INVALID"
    CORRECTION_PERSISTENCE_REFUSED = "CORRECTION_PERSISTENCE_REFUSED"
    CHALLENGE_PERSISTENCE_REFUSED = "CHALLENGE_PERSISTENCE_REFUSED"


class ChallengeReplayKind(StrEnum):
    NONE = "NONE"
    REPLAY_OR_CONCURRENT = "REPLAY_OR_CONCURRENT"


@dataclass(frozen=True)
class ChallengeLaunchProfile:
    """Explicit launch posture; defaults cannot admit any request."""

    configured: bool = False
    enabled: bool = False
    enabled_kinds: frozenset[ChallengeKind] = field(default_factory=frozenset)
    rate_profile: RateLimitProfile | None = None


@dataclass(frozen=True)
class ChallengeServiceReceipt:
    kind: ChallengeKind | None
    state: ChallengeServiceState
    reason: str
    receipt_time: str
    request_ref: str | None = None
    receipt_id: str | None = None
    replay: ChallengeReplayKind = ChallengeReplayKind.NONE

    @property
    def acknowledgement(self) -> dict[str, str]:
        ack = {"state": self.state.value}
        if self.kind is not None:
            ack["kind"] = self.kind.value
        if self.state in {
            ChallengeServiceState.REANALYSIS_PENDING_PRIVATE,
            ChallengeServiceState.TRIAGE_PENDING_PRIVATE,
            ChallengeServiceState.INDEPENDENT_REVIEW_PENDING_PRIVATE,
        } and self.receipt_id:
            ack.update(
                {
                    "receipt_id": self.receipt_id,
                    "policy_version": CHALLENGE_WORKFLOW_VERSION,
                    "receipt_time": self.receipt_time,
                }
            )
        return ack

    @property
    def loggable_receipt(self) -> dict[str, object]:
        return {
            "kind": self.kind.value if self.kind is not None else None,
            "state": self.state.value,
            "reason": self.reason,
            "receipt_time": self.receipt_time,
            "request_ref": self.request_ref,
            "receipt_id": self.receipt_id,
            "replay": self.replay.value,
        }

    def is_bounded(self) -> bool:
        ack = json.dumps(
            self.acknowledgement,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        loggable = json.dumps(
            self.loggable_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        combined = (ack + b" " + loggable).lower()
        forbidden = (b"accepted", b"approved", b"published", b"verified")
        return (
            len(ack) <= MAX_ACK_BYTES
            and len(loggable) <= MAX_LOGGABLE_RECEIPT_BYTES
            and not any(marker in combined for marker in forbidden)
        )


class ChallengeIntakeStore(Protocol):
    """Subset of the canonical store used by ``record_correction``."""

    def finding_context(self, finding_id: str) -> dict[str, Any]: ...

    def claim_context(self, claim_id: str) -> dict[str, Any]: ...

    def insert_correction(self, **kwargs: Any) -> bool: ...

    def enqueue_followup(self, **kwargs: Any) -> tuple[str, bool]: ...


class ChallengeLedger(Protocol):
    def initiate_request(self, **kwargs: Any) -> ChallengeAppendResult: ...

    def transition_request(self, request_id: str, **kwargs: Any) -> ChallengeAppendResult: ...

    def replay_request(self, request_id: str) -> ChallengeReplay: ...


class _ObservedStore:
    def __init__(self, delegate: ChallengeIntakeStore):
        self._delegate = delegate
        self.followup_inserted: bool | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def enqueue_followup(self, **kwargs: Any) -> tuple[str, bool]:
        result = self._delegate.enqueue_followup(**kwargs)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], str)
            or not isinstance(result[1], bool)
        ):
            raise RuntimeError("CHALLENGE_FOLLOWUP_RESULT_INVALID")
        self.followup_inserted = result[1]
        return result


_COMMON_FIELDS = frozenset({"kind", "reason"})
_FIELDS_BY_KIND: dict[ChallengeKind, frozenset[str]] = {
    ChallengeKind.CORRECTION: _COMMON_FIELDS
    | frozenset({"finding_id", "previous_finding_id", "changed_fields"}),
    ChallengeKind.TAKEDOWN: _COMMON_FIELDS | frozenset({"target_finding_id"}),
    ChallengeKind.APPEAL: _COMMON_FIELDS
    | frozenset({"target_finding_id", "prior_decision_id"}),
}
_REQUIRED_BY_KIND: dict[ChallengeKind, frozenset[str]] = {
    ChallengeKind.CORRECTION: frozenset(
        {"kind", "reason", "finding_id", "previous_finding_id", "changed_fields"}
    ),
    ChallengeKind.TAKEDOWN: frozenset({"kind", "reason", "target_finding_id"}),
    ChallengeKind.APPEAL: frozenset(
        {"kind", "reason", "target_finding_id", "prior_decision_id"}
    ),
}


@dataclass(frozen=True)
class _ValidatedChallenge:
    kind: ChallengeKind
    reason: str
    request_ref: str
    values: dict[str, object]


def _now_utc(clock: Callable[[], datetime] | None) -> str:
    current = clock() if clock is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def _request_ref(kind: ChallengeKind, normalized: dict[str, object]) -> str:
    encoded = json.dumps(
        {"kind": kind.value, "request": normalized, "policy": CHALLENGE_WORKFLOW_VERSION},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "challenge:" + hashlib.sha256(encoded).hexdigest()


def _identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_CHALLENGE_ID_CHARS:
        return None
    if _CONTROL_CHARACTERS.search(normalized):
        return None
    return normalized


def _validate_payload(payload: object) -> tuple[_ValidatedChallenge | None, ChallengeServiceReason]:
    if not isinstance(payload, dict):
        return None, ChallengeServiceReason.WRONG_TYPE
    if len(payload) > MAX_REQUEST_FIELDS:
        return None, ChallengeServiceReason.REQUEST_TOO_LARGE
    if any(not isinstance(key, str) for key in payload):
        return None, ChallengeServiceReason.UNKNOWN_FIELD

    raw_kind = payload.get("kind")
    if not isinstance(raw_kind, str):
        return None, ChallengeServiceReason.UNKNOWN_KIND
    try:
        kind = ChallengeKind(raw_kind.strip().upper())
    except ValueError:
        return None, ChallengeServiceReason.UNKNOWN_KIND

    allowed = _FIELDS_BY_KIND[kind]
    if set(payload) - allowed:
        return None, ChallengeServiceReason.UNKNOWN_FIELD
    if _REQUIRED_BY_KIND[kind] - set(payload):
        return None, ChallengeServiceReason.MISSING_FIELD

    reason_value = payload.get("reason")
    if not isinstance(reason_value, str):
        return None, ChallengeServiceReason.REASON_INVALID
    reason = reason_value.strip()
    if (
        not reason
        or len(reason) > MAX_CORRECTION_REASON_CHARS
        or _CONTROL_CHARACTERS.search(reason)
    ):
        return None, ChallengeServiceReason.REASON_INVALID

    normalized: dict[str, object] = {"reason": reason}
    id_fields = (
        ("finding_id", "previous_finding_id")
        if kind is ChallengeKind.CORRECTION
        else ("target_finding_id",)
    )
    if kind is ChallengeKind.APPEAL:
        id_fields = (*id_fields, "prior_decision_id")
    for field_name in id_fields:
        value = _identifier(payload.get(field_name))
        if value is None:
            return None, ChallengeServiceReason.IDENTIFIER_INVALID
        normalized[field_name] = value

    if kind is ChallengeKind.CORRECTION:
        changed_fields = payload.get("changed_fields")
        if not isinstance(changed_fields, dict):
            return None, ChallengeServiceReason.CHANGED_FIELDS_INVALID
        try:
            encoded_changed = json.dumps(
                changed_fields,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        except (TypeError, ValueError):
            return None, ChallengeServiceReason.CHANGED_FIELDS_INVALID
        if len(encoded_changed) > MAX_CHANGED_FIELDS_BYTES:
            return None, ChallengeServiceReason.CHANGED_FIELDS_INVALID
        normalized["changed_fields"] = changed_fields
        try:
            build_correction_record_id(
                finding_id=str(normalized["finding_id"]),
                previous_finding_id=str(normalized["previous_finding_id"]),
                reason=reason,
                changed_fields=changed_fields,
            )
        except (TypeError, ValueError):
            return None, ChallengeServiceReason.CHANGED_FIELDS_INVALID

    try:
        encoded_request = json.dumps(
            {"kind": kind.value, **normalized},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError):
        return None, ChallengeServiceReason.WRONG_TYPE
    if len(encoded_request) > MAX_REQUEST_BYTES:
        return None, ChallengeServiceReason.REQUEST_TOO_LARGE

    return (
        _ValidatedChallenge(
            kind=kind,
            reason=reason,
            request_ref=_request_ref(kind, normalized),
            values=normalized,
        ),
        ChallengeServiceReason.OK,
    )


def _receipt(
    *,
    kind: ChallengeKind | None,
    state: ChallengeServiceState,
    reason: str,
    receipt_time: str,
    request_ref: str | None = None,
    receipt_id: str | None = None,
    replay: ChallengeReplayKind = ChallengeReplayKind.NONE,
) -> ChallengeServiceReceipt:
    return ChallengeServiceReceipt(
        kind=kind,
        state=state,
        reason=reason,
        receipt_time=receipt_time,
        request_ref=request_ref,
        receipt_id=receipt_id,
        replay=replay,
    )


def _challenge_ledger_for_store(
    store: ChallengeIntakeStore,
    explicit: ChallengeLedger | None,
) -> ChallengeLedger | None:
    if explicit is not None:
        return explicit
    if not hasattr(store, "database_url"):
        return None
    return PrivateChallengeLedgerStore(
        getattr(store, "database_url", None),
        getattr(store, "psql", "psql"),
    )


def submit_challenge(
    store: ChallengeIntakeStore,
    payload: object,
    *,
    launch_profile: ChallengeLaunchProfile | None = None,
    rate_state: RateLimitState | None = None,
    clock: Callable[[], datetime] | None = None,
    challenge_ledger: ChallengeLedger | None = None,
) -> ChallengeServiceReceipt:
    """Process one private DP-303 challenge request without opening an HTTP listener.

    CORRECTION is persisted only through ``record_correction`` after exact local chain
    checks and therefore can create only the canonical private correction + reanalysis
    work. TAKEDOWN/APPEAL create only private challenge-ledger events. Intake advances
    those requests to their first private operator state through the canonical DP-303
    transition evaluator; it has no path to a public hold or appeal outcome.
    """

    profile = launch_profile or ChallengeLaunchProfile()
    receipt_time = _now_utc(clock)
    if not profile.configured:
        return _receipt(
            kind=None,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.LAUNCH_PROFILE_MISSING.value,
            receipt_time=receipt_time,
        )
    if not profile.enabled:
        return _receipt(
            kind=None,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.INTAKE_DISABLED.value,
            receipt_time=receipt_time,
        )

    validated, validation_reason = _validate_payload(payload)
    if validated is None:
        return _receipt(
            kind=None,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=validation_reason.value,
            receipt_time=receipt_time,
        )
    kind = validated.kind

    if kind not in profile.enabled_kinds:
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.KIND_DISABLED.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )
    if profile.rate_profile is None or rate_state is None:
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.RATE_DECISION_MISSING.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )

    rate_disposition, rate_reason = rate_limit_decision(profile.rate_profile, rate_state)
    if rate_disposition is not IntakeDisposition.ACCEPTED_PRIVATE:
        state = (
            ChallengeServiceState.DEFERRED
            if rate_disposition is IntakeDisposition.DEFERRED_RATE_LIMITED
            else ChallengeServiceState.NOT_RECEIVED
        )
        return _receipt(
            kind=kind,
            state=state,
            reason=rate_reason.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )

    if kind in {ChallengeKind.TAKEDOWN, ChallengeKind.APPEAL}:
        ledger = _challenge_ledger_for_store(store, challenge_ledger)
        if ledger is None:
            return _receipt(
                kind=kind,
                state=ChallengeServiceState.NOT_RECEIVED,
                reason=ChallengeServiceReason.CHALLENGE_PERSISTENCE_REFUSED.value,
                receipt_time=receipt_time,
                request_ref=validated.request_ref,
            )
        target_finding_id = str(validated.values["target_finding_id"])
        prior_decision_ref = (
            str(validated.values["prior_decision_id"])
            if kind is ChallengeKind.APPEAL
            else None
        )
        expected_state = (
            ChallengeState.TRIAGE_PENDING
            if kind is ChallengeKind.TAKEDOWN
            else ChallengeState.INDEPENDENT_REVIEW_PENDING
        )
        service_state = (
            ChallengeServiceState.TRIAGE_PENDING_PRIVATE
            if kind is ChallengeKind.TAKEDOWN
            else ChallengeServiceState.INDEPENDENT_REVIEW_PENDING_PRIVATE
        )
        try:
            initiated = ledger.initiate_request(
                kind=kind,
                target_finding_id=target_finding_id,
                source_request_ref=validated.request_ref,
                actor_ref="dp303-intake-adapter",
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason=validated.reason,
                prior_decision_ref=prior_decision_ref,
            )
            current = ledger.replay_request(initiated.request.request_id)
            if current.blockers:
                raise RuntimeError(current.blockers[0])
            transition_created = False
            if current.current_state is ChallengeState.PRIVATE_RECEIVED:
                transitioned = ledger.transition_request(
                    initiated.request.request_id,
                    actor_ref="dp303-intake-adapter",
                    actor_role=ChallengeRole.INTAKE_ADAPTER,
                    reason=validated.reason,
                )
                transition_created = transitioned.created
                if transitioned.event.to_state is not expected_state:
                    raise RuntimeError("CHALLENGE_INTAKE_TRANSITION_UNEXPECTED")
            elif current.current_state is not expected_state:
                # A later private/reviewed state is still an idempotent replay of intake;
                # intake never attempts to move it backwards or infer its outcome.
                transition_created = False
        except Exception:  # noqa: BLE001 - never reflect private ledger/store details
            return _receipt(
                kind=kind,
                state=ChallengeServiceState.NOT_RECEIVED,
                reason=ChallengeServiceReason.CHALLENGE_PERSISTENCE_REFUSED.value,
                receipt_time=receipt_time,
                request_ref=validated.request_ref,
            )
        replay = (
            ChallengeReplayKind.NONE
            if initiated.created or transition_created
            else ChallengeReplayKind.REPLAY_OR_CONCURRENT
        )
        return _receipt(
            kind=kind,
            state=service_state,
            reason=ChallengeServiceReason.OK.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
            receipt_id=initiated.request.request_id,
            replay=replay,
        )

    finding_id = str(validated.values["finding_id"])
    previous_finding_id = str(validated.values["previous_finding_id"])
    changed_fields = validated.values["changed_fields"]
    assert isinstance(changed_fields, dict)
    try:
        current = store.finding_context(finding_id)
        previous = store.finding_context(previous_finding_id)
    except Exception:  # noqa: BLE001 - never reflect private/store lookup details
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.CORRECTION_CHAIN_INVALID.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )

    chain_valid = (
        current.get("claim_id") == previous.get("claim_id")
        and current.get("supersedes_id") == previous_finding_id
    )
    decision = evaluate_transition(
        ChallengeContext(
            kind=kind,
            current_state=ChallengeState.PRIVATE_RECEIVED,
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            actor_id="dp303-intake-adapter",
            reason=validated.reason,
            target_record_exists=True,
            superseding_finding_id=finding_id,
            supersedes_chain_valid=chain_valid,
        )
    )
    if (
        not chain_valid
        or not decision.allowed
        or decision.next_state is not ChallengeState.REANALYSIS_PENDING
    ):
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.CORRECTION_CHAIN_INVALID.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )

    observed = _ObservedStore(store)
    try:
        correction_id = record_correction(
            observed,  # type: ignore[arg-type] - protocol-compatible transparent proxy
            finding_id=finding_id,
            previous_finding_id=previous_finding_id,
            reason=validated.reason,
            changed_fields=changed_fields,
        )
    except Exception:  # noqa: BLE001 - redact DB/chain/private failure details
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.CORRECTION_PERSISTENCE_REFUSED.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )
    if observed.followup_inserted is None:
        return _receipt(
            kind=kind,
            state=ChallengeServiceState.NOT_RECEIVED,
            reason=ChallengeServiceReason.CORRECTION_PERSISTENCE_REFUSED.value,
            receipt_time=receipt_time,
            request_ref=validated.request_ref,
        )

    replay = (
        ChallengeReplayKind.NONE
        if observed.followup_inserted
        else ChallengeReplayKind.REPLAY_OR_CONCURRENT
    )
    return _receipt(
        kind=kind,
        state=ChallengeServiceState.REANALYSIS_PENDING_PRIVATE,
        reason=ChallengeServiceReason.OK.value,
        receipt_time=receipt_time,
        request_ref=validated.request_ref,
        receipt_id=correction_id,
        replay=replay,
    )


__all__ = [
    "ChallengeIntakeStore",
    "ChallengeLedger",
    "ChallengeLaunchProfile",
    "ChallengeReplayKind",
    "ChallengeServiceReason",
    "ChallengeServiceReceipt",
    "ChallengeServiceState",
    "MAX_ACK_BYTES",
    "MAX_CHALLENGE_ID_CHARS",
    "MAX_LOGGABLE_RECEIPT_BYTES",
    "MAX_REQUEST_BYTES",
    "MAX_REQUEST_FIELDS",
    "submit_challenge",
]
