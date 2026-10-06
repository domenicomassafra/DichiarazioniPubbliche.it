from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable

from dichiarazioni_pubbliche.public_intake_abuse import (
    INTAKE_ABUSE_GUARD_VERSION,
    IntakeAbuseProfile,
    IntakeGuardReceipt,
    IntakeRateStore,
    guard_validated_intake,
)
from dichiarazioni_pubbliche.policy.intake_policy import IntakeValidationResult
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


ABUSE_EVENT_VERSION = "private-intake-abuse-event-v1"
RETENTION_EVENT_VERSION = "private-reply-retention-event-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CODE = re.compile(r"^[A-Z0-9_]{1,96}$")


class ReplyGovernanceError(ValueError):
    pass


class RetentionAction(StrEnum):
    RETAIN = "RETAIN"
    LEGAL_HOLD_SET = "LEGAL_HOLD_SET"
    LEGAL_HOLD_RELEASE = "LEGAL_HOLD_RELEASE"
    PURGE_APPROVED = "PURGE_APPROVED"
    PURGE_EXECUTED = "PURGE_EXECUTED"


@dataclass(frozen=True)
class AbuseAuditRecord:
    event_id: str
    subject_digest_sha256: str
    actor_ref: str
    decision_state: str
    reason_code: str
    decision_time: str
    signal_count: int
    event_integrity_sha256: str


@dataclass(frozen=True)
class RetentionEventRecord:
    event_id: str
    reply_id: str
    finding_id: str
    sequence: int
    action: RetentionAction
    actor_ref: str
    policy_decision_ref: str | None
    reason_code: str
    previous_event_id: str | None
    previous_integrity_sha256: str | None
    event_integrity_sha256: str


@dataclass(frozen=True)
class RetentionReplay:
    events: tuple[RetentionEventRecord, ...]
    blockers: tuple[str, ...]

    @property
    def legal_hold_active(self) -> bool:
        active = False
        for event in self.events:
            if event.action is RetentionAction.LEGAL_HOLD_SET:
                active = True
            elif event.action is RetentionAction.LEGAL_HOLD_RELEASE:
                active = False
        return active

    @property
    def purged(self) -> bool:
        return bool(self.events and self.events[-1].action is RetentionAction.PURGE_EXECUTED)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _text(value: object, code: str, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or "\x00" in text:
        raise ReplyGovernanceError(code)
    return text


def _reason(value: object) -> str:
    code = _text(value, "REPLY_GOVERNANCE_REASON_INVALID", 96).upper()
    if not _CODE.fullmatch(code):
        raise ReplyGovernanceError("REPLY_GOVERNANCE_REASON_INVALID")
    return code


def _utc(value: object, code: str) -> str:
    text = _text(value, code, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplyGovernanceError(code) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplyGovernanceError(code)
    return parsed.astimezone(timezone.utc).isoformat()


class ReplyGovernanceStore(PsqlRuntime):
    def guard_and_record_abuse_decision(
        self,
        *,
        validation: IntakeValidationResult,
        pseudonymous_bucket_key: str,
        profile: IntakeAbuseProfile,
        rate_store: IntakeRateStore,
        clock: Callable[[], datetime],
        actor_ref: str,
        launch_profile_enabled: bool,
    ) -> tuple[IntakeGuardReceipt, AbuseAuditRecord]:
        """Run the bounded abuse guard and persist its attributable decision."""

        receipt = guard_validated_intake(
            validation,
            pseudonymous_bucket_key=pseudonymous_bucket_key,
            profile=profile,
            rate_store=rate_store,
            clock=clock,
            launch_profile_enabled=launch_profile_enabled,
        )
        if not validation.source_hash:
            raise ReplyGovernanceError("ABUSE_VALIDATED_FINGERPRINT_MISSING")
        audit = self.record_abuse_decision(
            receipt=receipt,
            request_fingerprint_sha256=validation.source_hash,
            actor_ref=actor_ref,
        )
        return receipt, audit

    def record_abuse_decision(
        self,
        *,
        receipt: IntakeGuardReceipt,
        request_fingerprint_sha256: str,
        actor_ref: str,
    ) -> AbuseAuditRecord:
        fingerprint = _text(request_fingerprint_sha256, "ABUSE_FINGERPRINT_INVALID", 64).lower()
        if not _SHA256.fullmatch(fingerprint):
            raise ReplyGovernanceError("ABUSE_FINGERPRINT_INVALID")
        actor = _text(actor_ref, "ABUSE_ACTOR_INVALID", 256)
        decision_time = _utc(receipt.decision_time, "ABUSE_DECISION_TIME_INVALID")
        subject_digest = hashlib.sha256(
            ("dp302-abuse-subject-v1\x00" + fingerprint).encode()
        ).hexdigest()
        material = {
            "event_version": ABUSE_EVENT_VERSION,
            "subject_digest_sha256": subject_digest,
            "actor_ref": actor,
            "guard_version": INTAKE_ABUSE_GUARD_VERSION,
            "policy_version": str(receipt.private_log_receipt["policy_version"]),
            "decision_state": receipt.state.value,
            "reason_code": receipt.reason.value,
            "decision_time": decision_time,
            "signal_count": int(receipt.signal_count),
        }
        integrity = _digest(material)
        event_id = f"intake-abuse-event:{integrity}"
        self.run(
            """
            INSERT INTO private_intake_abuse_event (
                event_id,event_version,subject_digest_sha256,actor_ref,guard_version,
                policy_version,decision_state,reason_code,decision_time,signal_count,
                event_integrity_sha256,record_visibility
            ) VALUES (
                :'event_id',:'event_version',:'subject_digest',:'actor_ref',:'guard_version',
                :'policy_version',:'decision_state',:'reason_code',:'decision_time'::timestamptz,
                :'signal_count'::integer,:'integrity','PRIVATE'
            ) ON CONFLICT (event_id) DO NOTHING;
            """,
            event_id=event_id,
            event_version=ABUSE_EVENT_VERSION,
            subject_digest=subject_digest,
            actor_ref=actor,
            guard_version=INTAKE_ABUSE_GUARD_VERSION,
            policy_version=material["policy_version"],
            decision_state=receipt.state.value,
            reason_code=receipt.reason.value,
            decision_time=decision_time,
            signal_count=receipt.signal_count,
            integrity=integrity,
        )
        return AbuseAuditRecord(
            event_id, subject_digest, actor, receipt.state.value, receipt.reason.value,
            decision_time, receipt.signal_count, integrity
        )

    def _reply_context(self, reply_id: str) -> tuple[str, str, str] | None:
        raw = self.run(
            """
            SELECT COALESCE(json_build_array(finding_id,status,public_visibility)::text,'')
            FROM right_of_reply WHERE id=:'reply_id';
            """,
            reply_id=reply_id,
        )
        if not raw:
            return None
        value = json.loads(raw)
        return str(value[0]), str(value[1]), str(value[2])

    def _load_retention_events(self, reply_id: str) -> tuple[RetentionEventRecord, ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
              'event_id',event_id,'reply_id',reply_id,'finding_id',finding_id,
              'event_sequence',event_sequence,'action',action,'actor_ref',actor_ref,
              'policy_decision_ref',policy_decision_ref,'reason_code',reason_code,
              'previous_event_id',previous_event_id,'previous_integrity_sha256',previous_integrity_sha256,
              'event_integrity_sha256',event_integrity_sha256
            ) ORDER BY event_sequence)::text,'[]')
            FROM private_reply_retention_event WHERE reply_id=:'reply_id';
            """,
            reply_id=reply_id,
        )
        rows = json.loads(raw or "[]")
        return tuple(
            RetentionEventRecord(
                event_id=str(row["event_id"]), reply_id=str(row["reply_id"]),
                finding_id=str(row["finding_id"]), sequence=int(row["event_sequence"]),
                action=RetentionAction(str(row["action"])), actor_ref=str(row["actor_ref"]),
                policy_decision_ref=row.get("policy_decision_ref"), reason_code=str(row["reason_code"]),
                previous_event_id=row.get("previous_event_id"),
                previous_integrity_sha256=row.get("previous_integrity_sha256"),
                event_integrity_sha256=str(row["event_integrity_sha256"]),
            ) for row in rows
        )

    def replay_retention(self, reply_id: str) -> RetentionReplay:
        clean_reply = _text(reply_id, "REPLY_RETENTION_REPLY_ID_INVALID", 512)
        try:
            events = self._load_retention_events(clean_reply)
        except Exception:
            return RetentionReplay((), ("REPLY_RETENTION_LEDGER_INVALID",))
        blockers: list[str] = []
        previous: RetentionEventRecord | None = None
        hold = False
        for index, event in enumerate(events, start=1):
            material = {
                "event_version": RETENTION_EVENT_VERSION,
                "reply_id": event.reply_id,
                "finding_id": event.finding_id,
                "event_sequence": event.sequence,
                "action": event.action.value,
                "actor_ref": event.actor_ref,
                "policy_decision_ref": event.policy_decision_ref,
                "reason_code": event.reason_code,
                "previous_event_id": event.previous_event_id,
                "previous_integrity_sha256": event.previous_integrity_sha256,
            }
            expected = _digest(material)
            if event.sequence != index or event.event_integrity_sha256 != expected:
                blockers.append("REPLY_RETENTION_EVENT_INTEGRITY_INVALID")
            if event.event_id != f"reply-retention-event:{expected}":
                blockers.append("REPLY_RETENTION_EVENT_ID_INVALID")
            if previous is None:
                if event.previous_event_id is not None or event.previous_integrity_sha256 is not None:
                    blockers.append("REPLY_RETENTION_ROOT_INVALID")
            else:
                if event.finding_id != previous.finding_id or event.previous_event_id != previous.event_id:
                    blockers.append("REPLY_RETENTION_CHAIN_INVALID")
                if event.previous_integrity_sha256 != previous.event_integrity_sha256:
                    blockers.append("REPLY_RETENTION_CHAIN_INVALID")
            if event.action is RetentionAction.LEGAL_HOLD_SET:
                hold = True
            elif event.action is RetentionAction.LEGAL_HOLD_RELEASE:
                if not hold or not event.policy_decision_ref:
                    blockers.append("REPLY_RETENTION_HOLD_RELEASE_INVALID")
                hold = False
            elif event.action is RetentionAction.PURGE_APPROVED:
                if hold or not event.policy_decision_ref:
                    blockers.append("REPLY_RETENTION_PURGE_APPROVAL_INVALID")
            elif event.action is RetentionAction.PURGE_EXECUTED:
                if previous is None or previous.action is not RetentionAction.PURGE_APPROVED:
                    blockers.append("REPLY_RETENTION_PURGE_SEQUENCE_INVALID")
            previous = event
        return RetentionReplay(events, tuple(dict.fromkeys(blockers)))

    def record_retention_decision(
        self,
        *,
        reply_id: str,
        action: RetentionAction | str,
        actor_ref: str,
        reason_code: str,
        policy_decision_ref: str | None = None,
    ) -> RetentionEventRecord:
        clean_reply = _text(reply_id, "REPLY_RETENTION_REPLY_ID_INVALID", 512)
        actor = _text(actor_ref, "REPLY_RETENTION_ACTOR_INVALID", 256)
        reason = _reason(reason_code)
        try:
            canonical_action = RetentionAction(str(action))
        except ValueError as exc:
            raise ReplyGovernanceError("REPLY_RETENTION_ACTION_INVALID") from exc
        if canonical_action is RetentionAction.PURGE_EXECUTED:
            raise ReplyGovernanceError("REPLY_RETENTION_PURGE_EXECUTED_INTERNAL_ONLY")
        decision_ref = (
            _text(policy_decision_ref, "REPLY_RETENTION_POLICY_REF_INVALID", 512)
            if policy_decision_ref is not None else None
        )
        replay = self.replay_retention(clean_reply)
        if replay.blockers:
            raise ReplyGovernanceError(replay.blockers[0])
        if replay.events:
            latest = replay.events[-1]
            if (
                latest.action is canonical_action
                and latest.actor_ref == actor
                and latest.policy_decision_ref == decision_ref
                and latest.reason_code == reason
            ):
                return latest
        context = self._reply_context(clean_reply)
        if context is None:
            raise ReplyGovernanceError("REPLY_RETENTION_REPLY_NOT_FOUND")
        finding_id, status, visibility = context
        if visibility != "PRIVATE" or status == "PUBLISHED":
            raise ReplyGovernanceError("REPLY_RETENTION_PUBLISHED_REPLY_FORBIDDEN")
        if canonical_action is RetentionAction.LEGAL_HOLD_RELEASE and not replay.legal_hold_active:
            raise ReplyGovernanceError("REPLY_RETENTION_HOLD_NOT_ACTIVE")
        if canonical_action is RetentionAction.PURGE_APPROVED:
            if replay.legal_hold_active:
                raise ReplyGovernanceError("REPLY_RETENTION_LEGAL_HOLD_ACTIVE")
            if decision_ref is None:
                raise ReplyGovernanceError("REPLY_RETENTION_POLICY_REF_REQUIRED")
        previous = replay.events[-1] if replay.events else None
        sequence = len(replay.events) + 1
        material = {
            "event_version": RETENTION_EVENT_VERSION,
            "reply_id": clean_reply,
            "finding_id": finding_id,
            "event_sequence": sequence,
            "action": canonical_action.value,
            "actor_ref": actor,
            "policy_decision_ref": decision_ref,
            "reason_code": reason,
            "previous_event_id": previous.event_id if previous else None,
            "previous_integrity_sha256": previous.event_integrity_sha256 if previous else None,
        }
        integrity = _digest(material)
        event_id = f"reply-retention-event:{integrity}"
        raw = self.run(
            """
            WITH inserted AS (
              INSERT INTO private_reply_retention_event (
                event_id,event_version,reply_id,finding_id,event_sequence,action,actor_ref,
                policy_decision_ref,reason_code,previous_event_id,previous_integrity_sha256,
                event_integrity_sha256,record_visibility
              ) VALUES (
                :'event_id',:'event_version',:'reply_id',:'finding_id',:'sequence'::integer,
                :'action',:'actor_ref',NULLIF(:'policy_ref',''),:'reason_code',
                NULLIF(:'previous_event_id',''),NULLIF(:'previous_integrity',''),:'integrity','PRIVATE'
              ) ON CONFLICT DO NOTHING RETURNING event_id
            ) SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            event_id=event_id, event_version=RETENTION_EVENT_VERSION, reply_id=clean_reply,
            finding_id=finding_id, sequence=sequence, action=canonical_action.value,
            actor_ref=actor, policy_ref=decision_ref or "", reason_code=reason,
            previous_event_id=previous.event_id if previous else "",
            previous_integrity=previous.event_integrity_sha256 if previous else "", integrity=integrity,
        )
        updated = self.replay_retention(clean_reply)
        if updated.blockers:
            raise ReplyGovernanceError(updated.blockers[0])
        match = next((event for event in updated.events if event.event_id == event_id), None)
        if match is None:
            raise ReplyGovernanceError("REPLY_RETENTION_CONCURRENT_TRANSITION")
        return match

    def purge_unpublished_reply(
        self,
        *,
        reply_id: str,
        actor_ref: str,
        reason_code: str = "PURGE_EXECUTED",
    ) -> RetentionEventRecord:
        clean_reply = _text(reply_id, "REPLY_RETENTION_REPLY_ID_INVALID", 512)
        replay = self.replay_retention(clean_reply)
        if replay.blockers or not replay.events:
            raise ReplyGovernanceError(replay.blockers[0] if replay.blockers else "REPLY_RETENTION_PURGE_NOT_APPROVED")
        if replay.purged:
            return replay.events[-1]
        previous = replay.events[-1]
        if previous.action is not RetentionAction.PURGE_APPROVED or replay.legal_hold_active:
            raise ReplyGovernanceError("REPLY_RETENTION_PURGE_NOT_APPROVED")
        actor = _text(actor_ref, "REPLY_RETENTION_ACTOR_INVALID", 256)
        reason = _reason(reason_code)
        sequence = previous.sequence + 1
        material = {
            "event_version": RETENTION_EVENT_VERSION, "reply_id": clean_reply,
            "finding_id": previous.finding_id, "event_sequence": sequence,
            "action": RetentionAction.PURGE_EXECUTED.value, "actor_ref": actor,
            "policy_decision_ref": previous.policy_decision_ref, "reason_code": reason,
            "previous_event_id": previous.event_id,
            "previous_integrity_sha256": previous.event_integrity_sha256,
        }
        integrity = _digest(material)
        event_id = f"reply-retention-event:{integrity}"
        raw = self.run(
            """
            WITH target AS (
              SELECT id FROM right_of_reply
              WHERE id=:'reply_id' AND public_visibility='PRIVATE' AND status <> 'PUBLISHED'
              FOR UPDATE
            ), deleted AS (
              DELETE FROM right_of_reply reply USING target
              WHERE reply.id=target.id RETURNING reply.id
            ), inserted AS (
              INSERT INTO private_reply_retention_event (
                event_id,event_version,reply_id,finding_id,event_sequence,action,actor_ref,
                policy_decision_ref,reason_code,previous_event_id,previous_integrity_sha256,
                event_integrity_sha256,record_visibility
              ) SELECT :'event_id',:'event_version',:'reply_id',:'finding_id',:'sequence'::integer,
                'PURGE_EXECUTED',:'actor_ref',NULLIF(:'policy_ref',''),:'reason_code',
                :'previous_event_id',:'previous_integrity',:'integrity','PRIVATE'
              FROM deleted ON CONFLICT DO NOTHING RETURNING event_id
            ) SELECT json_build_object(
              'deleted',EXISTS(SELECT 1 FROM deleted),
              'inserted',EXISTS(SELECT 1 FROM inserted)
            )::text;
            """,
            event_id=event_id, event_version=RETENTION_EVENT_VERSION, reply_id=clean_reply,
            finding_id=previous.finding_id, sequence=sequence, actor_ref=actor,
            policy_ref=previous.policy_decision_ref or "", reason_code=reason,
            previous_event_id=previous.event_id, previous_integrity=previous.event_integrity_sha256,
            integrity=integrity,
        )
        result = json.loads(raw or "{}")
        if not result.get("deleted") and not result.get("inserted"):
            replay_after = self.replay_retention(clean_reply)
            if replay_after.purged:
                return replay_after.events[-1]
            raise ReplyGovernanceError("REPLY_RETENTION_PURGE_TARGET_UNAVAILABLE")
        verified = self.replay_retention(clean_reply)
        if verified.blockers or not verified.purged:
            raise ReplyGovernanceError(verified.blockers[0] if verified.blockers else "REPLY_RETENTION_PURGE_AUDIT_MISSING")
        return verified.events[-1]


__all__ = [
    "ABUSE_EVENT_VERSION", "RETENTION_EVENT_VERSION", "AbuseAuditRecord",
    "ReplyGovernanceError", "ReplyGovernanceStore", "RetentionAction",
    "RetentionEventRecord", "RetentionReplay",
]
