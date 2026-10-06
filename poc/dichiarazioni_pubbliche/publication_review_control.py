from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Iterable

from dichiarazioni_pubbliche.high_risk_assertion import (
    HIGH_RISK_ASSERTION_VERSION,
    HighRiskDecision,
    RiskClass,
)
from dichiarazioni_pubbliche.publication_safety import (
    PUBLICATION_SAFETY_VERSION,
    PublicationSafetyResult,
)


PUBLICATION_REVIEW_CONTROL_VERSION = "publication-review-control-v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_APPROVAL_ACTION = "APPROVED"
_REVIEW_ACTIONS = frozenset({_APPROVAL_ACTION, "REJECTED", "SUPERSEDED"})


class ReviewRiskClass(StrEnum):
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    LEGAL = "LEGAL"


class ReviewStage(StrEnum):
    PRIMARY = "PRIMARY"
    INDEPENDENT = "INDEPENDENT"


class ReviewRole(StrEnum):
    # DECISION_REVIEWER reuses the existing DP-303/DP-304 review-role vocabulary.
    DECISION_REVIEWER = "DECISION_REVIEWER"
    INDEPENDENT_PUBLICATION_REVIEWER = "INDEPENDENT_PUBLICATION_REVIEWER"


@dataclass(frozen=True)
class PublicationReviewEvent:
    event_id: str
    sequence: int
    previous_event_id: str | None
    previous_integrity_sha256: str | None
    record_id: str
    record_version: str
    stage: ReviewStage | str
    role: ReviewRole | str
    action: str
    actor_ref: str
    credential_fingerprint: str
    reviewed_at: str
    publication_safety_version: str
    publication_safety_binding_sha256: str
    high_risk_version: str
    high_risk_binding_sha256: str
    review_risk_class: ReviewRiskClass | str
    reason_codes: tuple[str, ...] = ()
    separation_exception_ref: str | None = None
    policy_version: str = PUBLICATION_REVIEW_CONTROL_VERSION
    integrity_sha256: str = ""


@dataclass(frozen=True)
class PublicationReviewResult:
    disposition: str
    risk_class: ReviewRiskClass
    review_complete: bool
    dual_control_required: bool
    dual_control_satisfied: bool
    counted_event_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]
    policy_version: str = PUBLICATION_REVIEW_CONTROL_VERSION


@dataclass(frozen=True)
class AttestedReviewSeparationResult:
    risk_class: ReviewRiskClass
    review_complete: bool
    dual_control_required: bool
    dual_control_satisfied: bool
    counted_event_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    policy_version: str = PUBLICATION_REVIEW_CONTROL_VERSION


def _required_text(value: str | None, code: str, *, limit: int = 256) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError(code)
    return text


def _sha256(value: str, code: str) -> str:
    text = _required_text(value, code, limit=64).lower()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(code)
    return text


def _timestamp(value: str) -> str:
    text = _required_text(value, "PUBLICATION_REVIEW_TIMESTAMP_REQUIRED", limit=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("PUBLICATION_REVIEW_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("PUBLICATION_REVIEW_TIMESTAMP_TIMEZONE_REQUIRED")
    return text


def _stage(value: ReviewStage | str) -> ReviewStage:
    try:
        return value if isinstance(value, ReviewStage) else ReviewStage(str(value))
    except ValueError as exc:
        raise ValueError("PUBLICATION_REVIEW_STAGE_INVALID") from exc


def _role(value: ReviewRole | str) -> ReviewRole:
    try:
        return value if isinstance(value, ReviewRole) else ReviewRole(str(value))
    except ValueError as exc:
        raise ValueError("PUBLICATION_REVIEW_ROLE_INVALID") from exc


def _role_or_none(value: ReviewRole | str) -> ReviewRole | None:
    try:
        return _role(value)
    except ValueError:
        return None


def _canonical_reason_codes(values: Iterable[str]) -> tuple[str, ...]:
    cleaned = sorted(
        {
            _required_text(value, "PUBLICATION_REVIEW_REASON_CODE_INVALID", limit=120)
            for value in values
        }
    )
    return tuple(cleaned)


def review_risk_class(decision: HighRiskDecision) -> ReviewRiskClass:
    if RiskClass.LEGAL_STATUS in decision.signals.risk_classes:
        return ReviewRiskClass.LEGAL
    if decision.signals.requires_escalation:
        return ReviewRiskClass.HIGH
    return ReviewRiskClass.STANDARD


def _review_risk_class(value: ReviewRiskClass | str) -> ReviewRiskClass:
    try:
        return value if isinstance(value, ReviewRiskClass) else ReviewRiskClass(str(value))
    except ValueError as exc:
        raise ValueError("PUBLICATION_REVIEW_RISK_CLASS_INVALID") from exc


def high_risk_binding_sha256(
    decision: HighRiskDecision,
    *,
    input_binding_sha256: str,
) -> str:
    input_binding = _sha256(
        input_binding_sha256,
        "PUBLICATION_REVIEW_HIGH_RISK_INPUT_BINDING_INVALID",
    )
    payload = {
        "input_binding_sha256": input_binding,
        "version": str(decision.version),
        "disposition": str(decision.disposition),
        "reason_codes": list(decision.reason_codes),
        "policy_decision_ref": decision.policy_decision_ref,
        "signals": {
            "version": str(decision.signals.version),
            "risk_classes": [str(value) for value in decision.signals.risk_classes],
            "procedural_statuses": [
                str(value) for value in decision.signals.procedural_statuses
            ],
            "allegation_framing": bool(decision.signals.allegation_framing),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_payload(
    *,
    sequence: int,
    previous_event_id: str | None,
    previous_integrity_sha256: str | None,
    record_id: str,
    record_version: str,
    stage: ReviewStage,
    role: ReviewRole,
    action: str,
    actor_ref: str,
    credential_fingerprint: str,
    reviewed_at: str,
    publication_safety_version: str,
    publication_safety_binding_sha256: str,
    high_risk_version: str,
    high_risk_binding_sha256_value: str,
    review_risk_class_value: ReviewRiskClass,
    reason_codes: tuple[str, ...],
    separation_exception_ref: str | None,
    policy_version: str,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "previous_event_id": previous_event_id,
        "previous_integrity_sha256": previous_integrity_sha256,
        "record_id": record_id,
        "record_version": record_version,
        "stage": stage.value,
        "role": role.value,
        "action": action,
        "actor_ref": actor_ref,
        "credential_fingerprint": credential_fingerprint,
        "reviewed_at": reviewed_at,
        "publication_safety_version": publication_safety_version,
        "publication_safety_binding_sha256": publication_safety_binding_sha256,
        "high_risk_version": high_risk_version,
        "high_risk_binding_sha256": high_risk_binding_sha256_value,
        "review_risk_class": review_risk_class_value.value,
        "reason_codes": list(reason_codes),
        "separation_exception_ref": separation_exception_ref,
        "policy_version": policy_version,
    }


def _event_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_review_event(
    *,
    record_id: str,
    record_version: str,
    stage: ReviewStage | str,
    role: ReviewRole | str,
    action: str,
    actor_ref: str,
    credential_fingerprint: str,
    reviewed_at: str,
    publication_safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
    high_risk_input_binding_sha256: str,
    previous_event: PublicationReviewEvent | None = None,
    reason_codes: Iterable[str] = (),
    separation_exception_ref: str | None = None,
) -> PublicationReviewEvent:
    clean_record_id = _required_text(record_id, "PUBLICATION_REVIEW_RECORD_ID_REQUIRED")
    clean_record_version = _required_text(
        record_version, "PUBLICATION_REVIEW_RECORD_VERSION_REQUIRED"
    )
    clean_stage = _stage(stage)
    clean_role = _role(role)
    clean_action = _required_text(action, "PUBLICATION_REVIEW_ACTION_REQUIRED", limit=64)
    if clean_action not in _REVIEW_ACTIONS:
        raise ValueError("PUBLICATION_REVIEW_ACTION_INVALID")
    clean_actor = _required_text(actor_ref, "PUBLICATION_REVIEW_ACTOR_REQUIRED")
    clean_credential = _sha256(
        credential_fingerprint,
        "PUBLICATION_REVIEW_CREDENTIAL_FINGERPRINT_INVALID",
    )
    clean_reviewed_at = _timestamp(reviewed_at)
    clean_reasons = _canonical_reason_codes(reason_codes)
    exception_ref = (
        _required_text(
            separation_exception_ref,
            "PUBLICATION_REVIEW_SEPARATION_EXCEPTION_REF_INVALID",
        )
        if separation_exception_ref is not None
        else None
    )
    safety_binding = _sha256(
        publication_safety.binding_sha256,
        "PUBLICATION_REVIEW_SAFETY_BINDING_INVALID",
    )
    risk_binding = high_risk_binding_sha256(
        high_risk,
        input_binding_sha256=high_risk_input_binding_sha256,
    )
    risk_class = review_risk_class(high_risk)
    sequence = 1 if previous_event is None else previous_event.sequence + 1
    previous_event_id = None if previous_event is None else previous_event.event_id
    previous_integrity = (
        None if previous_event is None else previous_event.integrity_sha256
    )
    payload = _event_payload(
        sequence=sequence,
        previous_event_id=previous_event_id,
        previous_integrity_sha256=previous_integrity,
        record_id=clean_record_id,
        record_version=clean_record_version,
        stage=clean_stage,
        role=clean_role,
        action=clean_action,
        actor_ref=clean_actor,
        credential_fingerprint=clean_credential,
        reviewed_at=clean_reviewed_at,
        publication_safety_version=str(publication_safety.profile_version),
        publication_safety_binding_sha256=safety_binding,
        high_risk_version=str(high_risk.version),
        high_risk_binding_sha256_value=risk_binding,
        review_risk_class_value=risk_class,
        reason_codes=clean_reasons,
        separation_exception_ref=exception_ref,
        policy_version=PUBLICATION_REVIEW_CONTROL_VERSION,
    )
    digest = _event_digest(payload)
    return PublicationReviewEvent(
        event_id=f"publication-review-event:{digest}",
        integrity_sha256=digest,
        **payload,
    )


def _event_integrity_valid(event: PublicationReviewEvent) -> bool:
    try:
        payload = _event_payload(
            sequence=int(event.sequence),
            previous_event_id=event.previous_event_id,
            previous_integrity_sha256=event.previous_integrity_sha256,
            record_id=_required_text(
                event.record_id, "PUBLICATION_REVIEW_RECORD_ID_REQUIRED"
            ),
            record_version=_required_text(
                event.record_version, "PUBLICATION_REVIEW_RECORD_VERSION_REQUIRED"
            ),
            stage=_stage(event.stage),
            role=_role(event.role),
            action=_required_text(
                event.action, "PUBLICATION_REVIEW_ACTION_REQUIRED", limit=64
            ),
            actor_ref=_required_text(
                event.actor_ref, "PUBLICATION_REVIEW_ACTOR_REQUIRED"
            ),
            credential_fingerprint=_sha256(
                event.credential_fingerprint,
                "PUBLICATION_REVIEW_CREDENTIAL_FINGERPRINT_INVALID",
            ),
            reviewed_at=_timestamp(event.reviewed_at),
            publication_safety_version=_required_text(
                event.publication_safety_version,
                "PUBLICATION_REVIEW_SAFETY_VERSION_REQUIRED",
            ),
            publication_safety_binding_sha256=_sha256(
                event.publication_safety_binding_sha256,
                "PUBLICATION_REVIEW_SAFETY_BINDING_INVALID",
            ),
            high_risk_version=_required_text(
                event.high_risk_version,
                "PUBLICATION_REVIEW_HIGH_RISK_VERSION_REQUIRED",
            ),
            high_risk_binding_sha256_value=_sha256(
                event.high_risk_binding_sha256,
                "PUBLICATION_REVIEW_HIGH_RISK_BINDING_INVALID",
            ),
            review_risk_class_value=_review_risk_class(event.review_risk_class),
            reason_codes=_canonical_reason_codes(event.reason_codes),
            separation_exception_ref=(
                _required_text(
                    event.separation_exception_ref,
                    "PUBLICATION_REVIEW_SEPARATION_EXCEPTION_REF_INVALID",
                )
                if event.separation_exception_ref is not None
                else None
            ),
            policy_version=_required_text(
                event.policy_version, "PUBLICATION_REVIEW_POLICY_VERSION_REQUIRED"
            ),
        )
    except (TypeError, ValueError):
        return False
    if payload["action"] not in _REVIEW_ACTIONS:
        return False
    digest = _event_digest(payload)
    return (
        event.integrity_sha256 == digest
        and event.event_id == f"publication-review-event:{digest}"
    )


def review_event_integrity_valid(event: PublicationReviewEvent) -> bool:
    """Public fail-closed integrity check for persistence/identity boundaries."""

    return _event_integrity_valid(event)


def evaluate_attested_review_separation(
    *,
    record_id: str,
    record_version: str,
    events: Iterable[PublicationReviewEvent],
) -> AttestedReviewSeparationResult:
    """Evaluate reviewer separation from an already authority-verified durable chain.

    This intentionally does not replace DP-308/DP-309 revalidation. It proves only that the
    exact current record version carries the review stages required by the hash-bound risk
    class in its DP-310 event(s). Callers must independently require authority-verified replay
    and current publication-safety/high-risk eligibility before publication.
    """

    clean_record_id = _required_text(record_id, "PUBLICATION_REVIEW_RECORD_ID_REQUIRED")
    clean_record_version = _required_text(
        record_version, "PUBLICATION_REVIEW_RECORD_VERSION_REQUIRED"
    )
    rows = tuple(events)
    blockers = list(_validate_chain(rows))
    current: list[PublicationReviewEvent] = []
    for event in rows:
        if event.record_id != clean_record_id:
            _append_once(blockers, "REVIEW_TARGET_MISMATCH")
            continue
        if event.record_version != clean_record_version:
            continue
        if event.policy_version != PUBLICATION_REVIEW_CONTROL_VERSION:
            _append_once(blockers, "STALE_REVIEW_POLICY_VERSION")
            continue
        if event.publication_safety_version != PUBLICATION_SAFETY_VERSION:
            _append_once(blockers, "STALE_PUBLICATION_SAFETY_VERSION")
            continue
        if event.high_risk_version != HIGH_RISK_ASSERTION_VERSION:
            _append_once(blockers, "STALE_HIGH_RISK_VERSION")
            continue
        try:
            _review_risk_class(event.review_risk_class)
        except ValueError:
            _append_once(blockers, "REVIEW_RISK_CLASS_INVALID")
            continue
        current.append(event)

    latest_by_stage: dict[ReviewStage, PublicationReviewEvent] = {}
    for event in sorted(current, key=lambda row: row.sequence):
        try:
            latest_by_stage[_stage(event.stage)] = event
        except ValueError:
            _append_once(blockers, "REVIEW_ROLE_OR_STAGE_INVALID")

    primary = latest_by_stage.get(ReviewStage.PRIMARY)
    independent = latest_by_stage.get(ReviewStage.INDEPENDENT)
    risk = ReviewRiskClass.STANDARD
    if primary is None:
        _append_once(blockers, "PRIMARY_REVIEW_REQUIRED")
    else:
        try:
            risk = _review_risk_class(primary.review_risk_class)
        except ValueError:
            _append_once(blockers, "REVIEW_RISK_CLASS_INVALID")
        if _role_or_none(primary.role) is not ReviewRole.DECISION_REVIEWER:
            _append_once(blockers, "PRIMARY_REVIEW_ROLE_INVALID")
        if primary.action != _APPROVAL_ACTION:
            _append_once(blockers, "PRIMARY_REVIEW_NOT_APPROVED")

    dual_required = risk in {ReviewRiskClass.HIGH, ReviewRiskClass.LEGAL}
    if dual_required:
        if independent is None:
            _append_once(blockers, "REVIEW_SEPARATION_UNAVAILABLE")
        else:
            if _role_or_none(independent.role) is not ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER:
                _append_once(blockers, "INDEPENDENT_REVIEW_ROLE_INVALID")
            if independent.action != _APPROVAL_ACTION:
                _append_once(blockers, "INDEPENDENT_REVIEW_NOT_APPROVED")
            if independent.separation_exception_ref is not None:
                _append_once(blockers, "SEPARATION_EXCEPTION_NOT_DUAL_CONTROL")
            try:
                independent_risk = _review_risk_class(independent.review_risk_class)
            except ValueError:
                independent_risk = ReviewRiskClass.STANDARD
                _append_once(blockers, "REVIEW_RISK_CLASS_INVALID")
            if independent_risk is not risk:
                _append_once(blockers, "REVIEW_RISK_CLASS_DIVERGED")
            if primary is not None:
                if independent.actor_ref == primary.actor_ref:
                    _append_once(blockers, "DUPLICATE_REVIEWER_IDENTITY")
                if independent.credential_fingerprint == primary.credential_fingerprint:
                    _append_once(blockers, "DUPLICATE_REVIEWER_CREDENTIAL")
                if (
                    independent.publication_safety_binding_sha256
                    != primary.publication_safety_binding_sha256
                ):
                    _append_once(blockers, "REVIEW_SAFETY_BINDING_DIVERGED")
                if independent.high_risk_binding_sha256 != primary.high_risk_binding_sha256:
                    _append_once(blockers, "REVIEW_HIGH_RISK_BINDING_DIVERGED")

    primary_ok = (
        primary is not None
        and primary.action == _APPROVAL_ACTION
        and _role_or_none(primary.role) is ReviewRole.DECISION_REVIEWER
    )
    independent_ok = (
        not dual_required
        or (
            independent is not None
            and independent.action == _APPROVAL_ACTION
            and _role_or_none(independent.role)
            is ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER
            and independent.separation_exception_ref is None
            and primary is not None
            and independent.actor_ref != primary.actor_ref
            and independent.credential_fingerprint != primary.credential_fingerprint
            and _review_risk_class(independent.review_risk_class) is risk
            and independent.publication_safety_binding_sha256
            == primary.publication_safety_binding_sha256
            and independent.high_risk_binding_sha256 == primary.high_risk_binding_sha256
        )
    )
    complete = primary_ok and independent_ok and not blockers
    counted: tuple[str, ...] = ()
    if complete and primary is not None:
        counted = (
            (primary.event_id, independent.event_id)
            if dual_required and independent is not None
            else (primary.event_id,)
        )
    return AttestedReviewSeparationResult(
        risk_class=risk,
        review_complete=complete,
        dual_control_required=dual_required,
        dual_control_satisfied=bool(complete and dual_required),
        counted_event_ids=counted,
        blockers=tuple(blockers),
    )


def _validate_chain(events: tuple[PublicationReviewEvent, ...]) -> tuple[str, ...]:
    if not events:
        return ()
    blockers: list[str] = []
    if len({event.event_id for event in events}) != len(events):
        blockers.append("REVIEW_REPLAY_DETECTED")
    if len({event.sequence for event in events}) != len(events):
        blockers.append("REVIEW_SEQUENCE_DUPLICATE")
    ordered = sorted(events, key=lambda event: event.sequence)
    for index, event in enumerate(ordered, start=1):
        if event.sequence != index:
            if "REVIEW_SEQUENCE_GAP" not in blockers:
                blockers.append("REVIEW_SEQUENCE_GAP")
        if not _event_integrity_valid(event):
            if "REVIEW_EVENT_TAMPERED" not in blockers:
                blockers.append("REVIEW_EVENT_TAMPERED")
        prior = ordered[index - 2] if index > 1 else None
        expected_id = None if prior is None else prior.event_id
        expected_integrity = None if prior is None else prior.integrity_sha256
        if (
            event.previous_event_id != expected_id
            or event.previous_integrity_sha256 != expected_integrity
        ):
            if "REVIEW_CHAIN_BROKEN" not in blockers:
                blockers.append("REVIEW_CHAIN_BROKEN")
    return tuple(blockers)


def _upstream_high_risk_ready(decision: HighRiskDecision) -> bool:
    if not decision.signals.requires_escalation:
        return decision.disposition == "STANDARD_REVIEW"
    if decision.disposition == "ELIGIBLE_HIGH_RISK":
        return True
    return (
        decision.disposition == "HOLD_HIGH_RISK"
        and set(decision.reason_codes) == {"HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED"}
    )


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def evaluate_publication_review(
    *,
    record_id: str,
    record_version: str,
    publication_safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
    high_risk_input_binding_sha256: str,
    events: Iterable[PublicationReviewEvent],
    upstream_actor_refs: Iterable[str] = (),
    upstream_credential_fingerprints: Iterable[str] = (),
) -> PublicationReviewResult:
    clean_record_id = _required_text(record_id, "PUBLICATION_REVIEW_RECORD_ID_REQUIRED")
    clean_record_version = _required_text(
        record_version, "PUBLICATION_REVIEW_RECORD_VERSION_REQUIRED"
    )
    current_safety_binding = _sha256(
        publication_safety.binding_sha256,
        "PUBLICATION_REVIEW_SAFETY_BINDING_INVALID",
    )
    current_high_risk_binding = high_risk_binding_sha256(
        high_risk,
        input_binding_sha256=high_risk_input_binding_sha256,
    )
    risk = review_risk_class(high_risk)
    dual_required = risk in {ReviewRiskClass.HIGH, ReviewRiskClass.LEGAL}
    rows = tuple(events)
    blockers = list(_validate_chain(rows))
    next_actions: list[str] = []

    if publication_safety.profile_version != PUBLICATION_SAFETY_VERSION:
        _append_once(blockers, "STALE_PUBLICATION_SAFETY_VERSION")
    if not publication_safety.eligible:
        _append_once(blockers, "UPSTREAM_PUBLICATION_SAFETY_NOT_ELIGIBLE")
    if high_risk.version != HIGH_RISK_ASSERTION_VERSION:
        _append_once(blockers, "STALE_HIGH_RISK_VERSION")
    if not _upstream_high_risk_ready(high_risk):
        _append_once(blockers, "UPSTREAM_HIGH_RISK_GATE_NOT_READY")

    upstream_actors = {
        _required_text(value, "PUBLICATION_REVIEW_UPSTREAM_ACTOR_INVALID")
        for value in upstream_actor_refs
    }
    upstream_credentials = {
        _sha256(value, "PUBLICATION_REVIEW_UPSTREAM_CREDENTIAL_INVALID")
        for value in upstream_credential_fingerprints
    }

    current: list[PublicationReviewEvent] = []
    for event in rows:
        if event.record_id != clean_record_id:
            _append_once(blockers, "REVIEW_TARGET_MISMATCH")
            continue
        if event.record_version != clean_record_version:
            continue
        if event.policy_version != PUBLICATION_REVIEW_CONTROL_VERSION:
            _append_once(blockers, "STALE_REVIEW_POLICY_VERSION")
            continue
        if (
            event.publication_safety_version != publication_safety.profile_version
            or event.publication_safety_binding_sha256 != current_safety_binding
        ):
            _append_once(blockers, "STALE_PUBLICATION_SAFETY_BINDING")
            continue
        if (
            event.high_risk_version != high_risk.version
            or event.high_risk_binding_sha256 != current_high_risk_binding
        ):
            _append_once(blockers, "STALE_HIGH_RISK_BINDING")
            continue
        try:
            event_risk = _review_risk_class(event.review_risk_class)
        except ValueError:
            _append_once(blockers, "REVIEW_RISK_CLASS_INVALID")
            continue
        if event_risk is not risk:
            _append_once(blockers, "STALE_REVIEW_RISK_CLASS")
            continue
        current.append(event)

    latest_by_stage: dict[ReviewStage, PublicationReviewEvent] = {}
    for event in sorted(current, key=lambda row: row.sequence):
        try:
            latest_by_stage[_stage(event.stage)] = event
        except ValueError:
            _append_once(blockers, "REVIEW_ROLE_OR_STAGE_INVALID")

    primary = latest_by_stage.get(ReviewStage.PRIMARY)
    independent = latest_by_stage.get(ReviewStage.INDEPENDENT)

    if primary is None:
        _append_once(blockers, "PRIMARY_REVIEW_REQUIRED")
        _append_once(next_actions, "OBTAIN_PRIMARY_DECISION_REVIEW")
    else:
        primary_role = _role_or_none(primary.role)
        if primary_role is not ReviewRole.DECISION_REVIEWER:
            _append_once(blockers, "PRIMARY_REVIEW_ROLE_INVALID")
        if primary.action != _APPROVAL_ACTION:
            _append_once(blockers, "PRIMARY_REVIEW_NOT_APPROVED")

    if dual_required:
        if independent is None:
            _append_once(blockers, "REVIEW_SEPARATION_UNAVAILABLE")
            _append_once(next_actions, "OBTAIN_INDEPENDENT_PUBLICATION_REVIEW")
        else:
            independent_role = _role_or_none(independent.role)
            if independent_role is not ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER:
                _append_once(blockers, "INDEPENDENT_REVIEW_ROLE_INVALID")
            if independent.action != _APPROVAL_ACTION:
                _append_once(blockers, "INDEPENDENT_REVIEW_NOT_APPROVED")
            if independent.separation_exception_ref is not None:
                _append_once(blockers, "SEPARATION_EXCEPTION_NOT_DUAL_CONTROL")
                _append_once(next_actions, "OBTAIN_SEPARATE_REVIEWER")
            if primary is not None:
                if independent.actor_ref == primary.actor_ref:
                    _append_once(blockers, "DUPLICATE_REVIEWER_IDENTITY")
                    _append_once(next_actions, "OBTAIN_SEPARATE_REVIEWER")
                if independent.credential_fingerprint == primary.credential_fingerprint:
                    _append_once(blockers, "DUPLICATE_REVIEWER_CREDENTIAL")
                    _append_once(next_actions, "OBTAIN_SEPARATE_REVIEWER")
            if independent.actor_ref in upstream_actors:
                _append_once(blockers, "INDEPENDENT_REVIEWER_NOT_SEPARATE_FROM_UPSTREAM")
                _append_once(next_actions, "OBTAIN_SEPARATE_REVIEWER")
            if independent.credential_fingerprint in upstream_credentials:
                _append_once(
                    blockers,
                    "INDEPENDENT_REVIEWER_CREDENTIAL_NOT_SEPARATE_FROM_UPSTREAM",
                )
                _append_once(next_actions, "OBTAIN_SEPARATE_REVIEWER")

    primary_ok = (
        primary is not None
        and primary.action == _APPROVAL_ACTION
        and _role_or_none(primary.role) is ReviewRole.DECISION_REVIEWER
    )
    independent_ok = False
    if dual_required and independent is not None and primary is not None:
        independent_ok = (
            independent.action == _APPROVAL_ACTION
            and _role_or_none(independent.role)
            is ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER
            and independent.separation_exception_ref is None
            and independent.actor_ref != primary.actor_ref
            and independent.credential_fingerprint != primary.credential_fingerprint
            and independent.actor_ref not in upstream_actors
            and independent.credential_fingerprint not in upstream_credentials
        )

    # Structural/upstream blockers always defeat a locally complete-looking chain.
    blocking = bool(blockers)
    review_complete = primary_ok and (independent_ok if dual_required else True) and not blocking
    dual_satisfied = dual_required and independent_ok and primary_ok and not blocking
    counted: tuple[str, ...] = ()
    if review_complete:
        counted = (
            (primary.event_id, independent.event_id)
            if dual_required and independent is not None
            else (primary.event_id,)
        )

    if review_complete:
        disposition = (
            "DUAL_CONTROL_COMPLETE"
            if dual_required
            else "STANDARD_REVIEW_COMPLETE"
        )
    else:
        disposition = "REVIEW_HOLD"

    return PublicationReviewResult(
        disposition=disposition,
        risk_class=risk,
        review_complete=review_complete,
        dual_control_required=dual_required,
        dual_control_satisfied=dual_satisfied,
        counted_event_ids=counted,
        blockers=tuple(blockers),
        next_actions=tuple(next_actions),
    )


__all__ = [
    "AttestedReviewSeparationResult",
    "PUBLICATION_REVIEW_CONTROL_VERSION",
    "PublicationReviewEvent",
    "PublicationReviewResult",
    "ReviewRiskClass",
    "ReviewRole",
    "ReviewStage",
    "build_review_event",
    "evaluate_publication_review",
    "evaluate_attested_review_separation",
    "high_risk_binding_sha256",
    "review_event_integrity_valid",
    "review_risk_class",
]
