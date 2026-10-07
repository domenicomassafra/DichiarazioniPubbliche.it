from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum

from dichiarazioni_pubbliche.policy.privacy_policy import (
    DataClass,
    PRIVACY_POLICY_VERSION,
    PrivateAccessDecision,
    PrivateAccessOutcome,
    PrivateAccessRequest,
    RightsRequestKind,
    build_private_access_audit,
    decide_private_access,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


RIGHTS_CASE_CONTRACT_VERSION = "privacy-rights-case-v1"
RIGHTS_EVENT_CONTRACT_VERSION = "privacy-rights-case-event-v1"
PRIVATE_ACCESS_AUDIT_CONTRACT_VERSION = "private-access-audit-v1"

_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class RightsCaseEventType(StrEnum):
    OPEN_PRIVATE = "OPEN_PRIVATE"
    REVIEW_PENDING = "REVIEW_PENDING"
    PUBLIC_HISTORY_HOLD_REQUIRED = "PUBLIC_HISTORY_HOLD_REQUIRED"


@dataclass(frozen=True)
class RightsCaseSnapshot:
    case_id: str
    subject_ref: str
    target_record_ref: str
    request_kind: str
    affects_published_version: bool
    privacy_policy_version: str
    latest_event_id: str
    latest_event_sequence: int
    latest_event_type: str


@dataclass(frozen=True)
class PrivateInspectionResult:
    allowed: bool
    found: bool
    value: str | None
    audit_event_id: str
    reasons: tuple[str, ...]


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_ref(value: object, code: str, *, limit: int = 256) -> str:
    text = str(value or "")
    if len(text) > limit or not _REF.fullmatch(text):
        raise ValueError(code)
    return text


def _timestamp(value: object, code: str) -> str:
    text = str(value or "")
    if not text or len(text) > 64:
        raise ValueError(code)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(code) from exc
    if parsed.tzinfo is None:
        raise ValueError(code)
    return parsed.isoformat()


def _requester_hash(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or len(text) > 2048 or "\x00" in text:
        raise ValueError("PRIVACY_RIGHTS_REQUESTER_REF_INVALID")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_persisted_row(
    raw: str,
    expected: dict[str, object],
    code: str,
) -> None:
    try:
        row = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(code) from exc
    if not isinstance(row, dict):
        raise RuntimeError(code)
    if any(row.get(key) != value for key, value in expected.items()):
        raise RuntimeError(code)


_PRIVATE_INSPECTION_FIELDS: dict[tuple[str, str], DataClass] = {
    ("transcript_variant", "raw_text"): DataClass.OPERATIONAL_PRIVATE,
    ("transcript_segment", "text"): DataClass.OPERATIONAL_PRIVATE,
    ("canonical_transcript_segment", "canonical_text"): DataClass.OPERATIONAL_PRIVATE,
    ("passage", "private_text"): DataClass.OPERATIONAL_PRIVATE,
    ("evidence", "excerpt"): DataClass.OPERATIONAL_PRIVATE,
    ("right_of_reply", "body"): DataClass.OPERATIONAL_PRIVATE,
    ("right_of_reply", "submitter_name"): DataClass.OPERATIONAL_PRIVATE,
    ("right_of_reply", "submitter_role"): DataClass.OPERATIONAL_PRIVATE,
}


class PrivacyRightsAccessStore(PsqlRuntime):
    """DP-304 private rights/access runtime.

    This store is deliberately narrow. It records private rights cases without
    deciding their legal outcome, and it exposes only a closed read-only inspection
    allowlist after the canonical privacy access policy authorizes the request.
    """

    def open_rights_case(
        self,
        *,
        subject_ref: str,
        target_record_ref: str,
        request_kind: RightsRequestKind | str,
        affects_published_version: bool,
        opened_at: str,
        requester_ref: str | None = None,
        actor_ref: str = "SYSTEM_INTAKE",
    ) -> RightsCaseSnapshot:
        subject = _bounded_ref(subject_ref, "PRIVACY_RIGHTS_SUBJECT_REF_INVALID")
        target = _bounded_ref(target_record_ref, "PRIVACY_RIGHTS_TARGET_REF_INVALID")
        try:
            kind = RightsRequestKind(str(request_kind))
        except ValueError as exc:
            raise ValueError("PRIVACY_RIGHTS_REQUEST_KIND_INVALID") from exc
        if not isinstance(affects_published_version, bool):
            raise ValueError("PRIVACY_RIGHTS_PUBLISHED_FLAG_INVALID")
        opened = _timestamp(opened_at, "PRIVACY_RIGHTS_OPENED_AT_INVALID")
        actor = _bounded_ref(actor_ref, "PRIVACY_RIGHTS_ACTOR_REF_INVALID", limit=128)
        requester_sha = _requester_hash(requester_ref)
        material = {
            "contract_version": RIGHTS_CASE_CONTRACT_VERSION,
            "subject_ref": subject,
            "target_record_ref": target,
            "request_kind": kind.value,
            "affects_published_version": affects_published_version,
            "requester_ref_sha256": requester_sha,
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
            "opened_at_text": opened,
        }
        digest = _json_sha256(material)
        case_id = f"privacy-rights-case:{digest}"
        event_material = {
            "contract_version": RIGHTS_EVENT_CONTRACT_VERSION,
            "case_id": case_id,
            "event_sequence": 1,
            "event_type": RightsCaseEventType.OPEN_PRIVATE.value,
            "actor_ref": actor,
            "purpose_ref": "RIGHTS_REQUEST",
            "occurred_at_text": opened,
            "previous_event_id": None,
        }
        event_digest = _json_sha256(event_material)
        event_id = f"privacy-rights-event:{event_digest}"
        self.run(
            """
            INSERT INTO privacy_rights_case (
                case_id, contract_version, subject_ref, target_record_ref,
                request_kind, affects_published_version, requester_ref_sha256,
                privacy_policy_version, opened_at_text, case_integrity_sha256
            ) VALUES (
                :'case_id', :'case_contract', :'subject_ref', :'target_record_ref',
                :'request_kind', :'affects_published_version'::boolean,
                NULLIF(:'requester_ref_sha256',''), :'privacy_policy_version',
                :'opened_at_text', :'case_integrity_sha256'
            ) ON CONFLICT (case_id) DO NOTHING;
            """,
            case_id=case_id,
            case_contract=RIGHTS_CASE_CONTRACT_VERSION,
            subject_ref=subject,
            target_record_ref=target,
            request_kind=kind.value,
            affects_published_version=str(affects_published_version).lower(),
            requester_ref_sha256=requester_sha or "",
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            opened_at_text=opened,
            case_integrity_sha256=digest,
        )
        persisted_case = self.run(
            """
            SELECT row_to_json(row_data)::text
            FROM (
                SELECT
                    case_id, contract_version, subject_ref, target_record_ref,
                    request_kind, affects_published_version, requester_ref_sha256,
                    privacy_policy_version, opened_at_text, case_integrity_sha256,
                    record_visibility
                FROM privacy_rights_case
                WHERE case_id = :'case_id'
            ) row_data;
            """,
            case_id=case_id,
        )
        _require_persisted_row(
            persisted_case,
            {
                "case_id": case_id,
                **material,
                "case_integrity_sha256": digest,
                "record_visibility": "PRIVATE",
            },
            "PRIVACY_RIGHTS_CASE_CONFLICT",
        )
        self.run(
            """
            INSERT INTO privacy_rights_case_event (
                event_id, contract_version, case_id, event_sequence, event_type,
                actor_ref, purpose_ref, occurred_at_text, previous_event_id,
                event_integrity_sha256
            ) VALUES (
                :'event_id', :'event_contract', :'case_id', 1, 'OPEN_PRIVATE',
                :'actor_ref', 'RIGHTS_REQUEST', :'opened_at_text', NULL,
                :'event_integrity_sha256'
            ) ON CONFLICT (event_id) DO NOTHING;
            """,
            event_id=event_id,
            event_contract=RIGHTS_EVENT_CONTRACT_VERSION,
            case_id=case_id,
            actor_ref=actor,
            opened_at_text=opened,
            event_integrity_sha256=event_digest,
        )
        persisted_event = self.run(
            """
            SELECT row_to_json(row_data)::text
            FROM (
                SELECT
                    event_id, contract_version, case_id, event_sequence, event_type,
                    actor_ref, purpose_ref, occurred_at_text, previous_event_id,
                    event_integrity_sha256, record_visibility
                FROM privacy_rights_case_event
                WHERE event_id = :'event_id'
            ) row_data;
            """,
            event_id=event_id,
        )
        _require_persisted_row(
            persisted_event,
            {
                "event_id": event_id,
                **event_material,
                "event_integrity_sha256": event_digest,
                "record_visibility": "PRIVATE",
            },
            "PRIVACY_RIGHTS_EVENT_CONFLICT",
        )
        snapshot = self.current_rights_case(case_id)
        if snapshot is None:
            raise RuntimeError("PRIVACY_RIGHTS_CASE_PERSISTENCE_FAILED")
        return snapshot

    def current_rights_case(self, case_id: str) -> RightsCaseSnapshot | None:
        case_ref = _bounded_ref(case_id, "PRIVACY_RIGHTS_CASE_ID_INVALID")
        raw = self.run(
            """
            SELECT COALESCE(row_to_json(row_data)::text, '')
            FROM (
                SELECT
                    rights.case_id,
                    rights.subject_ref,
                    rights.target_record_ref,
                    rights.request_kind,
                    rights.affects_published_version,
                    rights.privacy_policy_version,
                    event.event_id AS latest_event_id,
                    event.event_sequence AS latest_event_sequence,
                    event.event_type AS latest_event_type
                FROM privacy_rights_case rights
                JOIN LATERAL (
                    SELECT event_id, event_sequence, event_type
                    FROM privacy_rights_case_event
                    WHERE case_id = rights.case_id
                    ORDER BY event_sequence DESC, event_id DESC
                    LIMIT 1
                ) event ON true
                WHERE rights.case_id = :'case_id'
            ) row_data;
            """,
            case_id=case_ref,
        )
        if not raw:
            return None
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise RuntimeError("PRIVACY_RIGHTS_CASE_READ_INVALID")
        return RightsCaseSnapshot(
            case_id=str(row["case_id"]),
            subject_ref=str(row["subject_ref"]),
            target_record_ref=str(row["target_record_ref"]),
            request_kind=str(row["request_kind"]),
            affects_published_version=bool(row["affects_published_version"]),
            privacy_policy_version=str(row["privacy_policy_version"]),
            latest_event_id=str(row["latest_event_id"]),
            latest_event_sequence=int(row["latest_event_sequence"]),
            latest_event_type=str(row["latest_event_type"]),
        )

    def append_rights_review_hold(
        self,
        *,
        case_id: str,
        actor_ref: str,
        occurred_at: str,
    ) -> RightsCaseSnapshot:
        current = self.current_rights_case(case_id)
        if current is None:
            raise ValueError("PRIVACY_RIGHTS_CASE_NOT_FOUND")
        actor = _bounded_ref(actor_ref, "PRIVACY_RIGHTS_ACTOR_REF_INVALID", limit=128)
        occurred = _timestamp(occurred_at, "PRIVACY_RIGHTS_OCCURRED_AT_INVALID")
        event_type = (
            RightsCaseEventType.PUBLIC_HISTORY_HOLD_REQUIRED
            if current.affects_published_version
            else RightsCaseEventType.REVIEW_PENDING
        )
        if self._rights_event_matches_replay(
            event_id=current.latest_event_id,
            event_type=event_type,
            actor_ref=actor,
            occurred_at=occurred,
        ):
            return current
        sequence = current.latest_event_sequence + 1
        material = {
            "contract_version": RIGHTS_EVENT_CONTRACT_VERSION,
            "case_id": current.case_id,
            "event_sequence": sequence,
            "event_type": event_type.value,
            "actor_ref": actor,
            "purpose_ref": "RIGHTS_REQUEST",
            "occurred_at_text": occurred,
            "previous_event_id": current.latest_event_id,
        }
        digest = _json_sha256(material)
        event_id = f"privacy-rights-event:{digest}"
        try:
            self.run(
                """
                INSERT INTO privacy_rights_case_event (
                    event_id, contract_version, case_id, event_sequence, event_type,
                    actor_ref, purpose_ref, occurred_at_text, previous_event_id,
                    event_integrity_sha256
                ) VALUES (
                    :'event_id', :'contract_version', :'case_id', :'event_sequence'::integer,
                    :'event_type', :'actor_ref', 'RIGHTS_REQUEST', :'occurred_at_text',
                    :'previous_event_id', :'event_integrity_sha256'
                );
                """,
                event_id=event_id,
                contract_version=RIGHTS_EVENT_CONTRACT_VERSION,
                case_id=current.case_id,
                event_sequence=sequence,
                event_type=event_type.value,
                actor_ref=actor,
                occurred_at_text=occurred,
                previous_event_id=current.latest_event_id,
                event_integrity_sha256=digest,
            )
        except RuntimeError:
            concurrent = self.current_rights_case(current.case_id)
            if (
                concurrent is not None
                and concurrent.latest_event_id == event_id
                and concurrent.latest_event_sequence == sequence
                and concurrent.latest_event_type == event_type.value
            ):
                return concurrent
            raise
        updated = self.current_rights_case(current.case_id)
        if updated is None:
            raise RuntimeError("PRIVACY_RIGHTS_CASE_REPLAY_FAILED")
        return updated

    def _rights_event_matches_replay(
        self,
        *,
        event_id: str,
        event_type: RightsCaseEventType,
        actor_ref: str,
        occurred_at: str,
    ) -> bool:
        raw = self.run(
            """
            SELECT count(*)::text
            FROM privacy_rights_case_event
            WHERE event_id = :'event_id'
              AND event_type = :'event_type'
              AND actor_ref = :'actor_ref'
              AND purpose_ref = 'RIGHTS_REQUEST'
              AND occurred_at_text = :'occurred_at_text';
            """,
            event_id=event_id,
            event_type=event_type.value,
            actor_ref=actor_ref,
            occurred_at_text=occurred_at,
        )
        return raw == "1"

    def _persist_private_access_audit(
        self,
        *,
        request: PrivateAccessRequest,
        decision: PrivateAccessDecision,
        record_ref: str,
        occurred_at: str,
    ) -> str:
        receipt = build_private_access_audit(
            request,
            decision,
            record_ref=record_ref,
            occurred_at=occurred_at,
        )
        material = asdict(receipt)
        digest = _json_sha256(material)
        event_id = f"private-access-audit:{digest}"
        self.run(
            """
            INSERT INTO private_access_audit_event (
                event_id, contract_version, privacy_policy_version, actor_ref,
                record_ref, purpose_ref, outcome, occurred_at_text,
                requested_field_count, legal_hold_active, event_integrity_sha256
            ) VALUES (
                :'event_id', :'contract_version', :'privacy_policy_version', :'actor_ref',
                :'record_ref', :'purpose_ref', :'outcome', :'occurred_at_text',
                :'requested_field_count'::integer, :'legal_hold_active'::boolean,
                :'event_integrity_sha256'
            ) ON CONFLICT (event_id) DO NOTHING;
            """,
            event_id=event_id,
            contract_version=PRIVATE_ACCESS_AUDIT_CONTRACT_VERSION,
            privacy_policy_version=receipt.policy_version,
            actor_ref=receipt.actor_ref,
            record_ref=receipt.record_ref,
            purpose_ref=receipt.purpose,
            outcome=receipt.outcome,
            occurred_at_text=receipt.occurred_at,
            requested_field_count=receipt.requested_field_count,
            legal_hold_active=str(receipt.legal_hold_active).lower(),
            event_integrity_sha256=digest,
        )
        persisted_audit = self.run(
            """
            SELECT row_to_json(row_data)::text
            FROM (
                SELECT
                    event_id, contract_version, privacy_policy_version, actor_ref,
                    record_ref, purpose_ref, outcome, occurred_at_text,
                    requested_field_count, legal_hold_active, event_integrity_sha256,
                    record_visibility
                FROM private_access_audit_event
                WHERE event_id = :'event_id'
            ) row_data;
            """,
            event_id=event_id,
        )
        _require_persisted_row(
            persisted_audit,
            {
                "event_id": event_id,
                "contract_version": PRIVATE_ACCESS_AUDIT_CONTRACT_VERSION,
                "privacy_policy_version": receipt.policy_version,
                "actor_ref": receipt.actor_ref,
                "record_ref": receipt.record_ref,
                "purpose_ref": receipt.purpose,
                "outcome": receipt.outcome,
                "occurred_at_text": receipt.occurred_at,
                "requested_field_count": receipt.requested_field_count,
                "legal_hold_active": receipt.legal_hold_active,
                "event_integrity_sha256": digest,
                "record_visibility": "PRIVATE",
            },
            "PRIVATE_ACCESS_AUDIT_CONFLICT",
        )
        return event_id

    def inspect_private_field(
        self,
        *,
        table_name: str,
        field_name: str,
        record_ref: str,
        request: PrivateAccessRequest,
        occurred_at: str,
    ) -> PrivateInspectionResult:
        record = _bounded_ref(record_ref, "PRIVATE_ACCESS_RECORD_REF_INVALID", limit=128)
        occurred = _timestamp(occurred_at, "PRIVATE_ACCESS_OCCURRED_AT_INVALID")
        target = (str(table_name), str(field_name))
        required_class = _PRIVATE_INSPECTION_FIELDS.get(target)
        decision = decide_private_access(request)
        reasons = list(decision.reasons)
        if required_class is None:
            decision = PrivateAccessDecision(
                PrivateAccessOutcome.DENY,
                ("PRIVATE_FIELD_NOT_ALLOWLISTED",),
            )
        elif str(request.data_class) != required_class.value:
            decision = PrivateAccessDecision(
                PrivateAccessOutcome.DENY,
                ("PRIVATE_FIELD_CLASSIFICATION_MISMATCH",),
            )
        elif tuple(request.requested_fields) != (field_name,):
            decision = PrivateAccessDecision(
                PrivateAccessOutcome.DENY,
                ("PRIVATE_FIELD_REQUEST_MISMATCH",),
            )
        reasons = list(decision.reasons)
        event_id = self._persist_private_access_audit(
            request=request,
            decision=decision,
            record_ref=record,
            occurred_at=occurred,
        )
        if not decision.allowed or required_class is None:
            return PrivateInspectionResult(
                allowed=False,
                found=False,
                value=None,
                audit_event_id=event_id,
                reasons=tuple(reasons),
            )

        # table_name/field_name are selected exclusively from the closed static map
        # above; the record id remains a psql variable. No arbitrary SQL identifier
        # supplied by the caller reaches this query.
        value = self.run(
            f"SELECT COALESCE({field_name}, '') FROM {table_name} WHERE id=:'record_ref';",
            record_ref=record,
        )
        return PrivateInspectionResult(
            allowed=True,
            found=bool(value),
            value=value or None,
            audit_event_id=event_id,
            reasons=tuple(reasons),
        )


__all__ = [
    "PRIVATE_ACCESS_AUDIT_CONTRACT_VERSION",
    "RIGHTS_CASE_CONTRACT_VERSION",
    "RIGHTS_EVENT_CONTRACT_VERSION",
    "PrivateInspectionResult",
    "PrivacyRightsAccessStore",
    "RightsCaseEventType",
    "RightsCaseSnapshot",
]
