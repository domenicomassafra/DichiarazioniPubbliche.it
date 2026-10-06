from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dichiarazioni_pubbliche.policy.privacy_policy import (
    PRIVACY_POLICY_VERSION,
    ProjectionDecision,
    ProjectionInput,
    PublicationDecision,
    decide_projection,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION = "privacy-publication-decision-v1"
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_AUDIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_ref(value: object, code: str) -> str:
    text = str(value or "")
    if not _REF.fullmatch(text):
        raise ValueError(code)
    return text


def _bounded_audit_ref(value: object, code: str) -> str:
    text = str(value or "")
    if not _AUDIT_REF.fullmatch(text):
        raise ValueError(code)
    return text


def _bounded_exact_text(
    value: object,
    code: str,
    *,
    limit: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or "\x00" in value or len(value) > limit:
        raise ValueError(code)
    if not allow_empty and not value:
        raise ValueError(code)
    return value


def _reviewed_at(value: object) -> str:
    text = _bounded_exact_text(value, "PRIVACY_DECISION_REVIEWED_AT_INVALID", limit=64)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("PRIVACY_DECISION_REVIEWED_AT_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError("PRIVACY_DECISION_REVIEWED_AT_INVALID")
    return parsed.isoformat()


def _projection_input_material(inputs: ProjectionInput) -> dict[str, object]:
    field_name = _bounded_exact_text(
        inputs.field_name,
        "PRIVACY_DECISION_FIELD_NAME_INVALID",
        limit=128,
    )
    data_class = _bounded_exact_text(
        str(inputs.data_class),
        "PRIVACY_DECISION_DATA_CLASS_INVALID",
        limit=64,
    )
    relevance_reason: str | None
    if inputs.relevance_reason is None:
        relevance_reason = None
    else:
        relevance_reason = _bounded_exact_text(
            inputs.relevance_reason,
            "PRIVACY_DECISION_RELEVANCE_REASON_INVALID",
            limit=128,
        )
    if inputs.text_value is not None and not isinstance(inputs.text_value, str):
        raise ValueError("PRIVACY_DECISION_TEXT_VALUE_INVALID")
    for flag_name in ("explicitly_approved", "is_published_version", "is_ephemeral"):
        if not isinstance(getattr(inputs, flag_name), bool):
            raise ValueError(f"PRIVACY_DECISION_{flag_name.upper()}_INVALID")
    text_value_sha256 = (
        None
        if inputs.text_value is None
        else hashlib.sha256(inputs.text_value.encode("utf-8")).hexdigest()
    )
    return {
        "input_contract_version": "privacy-projection-input-v1",
        "field_name": field_name,
        "data_class": data_class,
        "text_value_sha256": text_value_sha256,
        "relevance_reason": relevance_reason,
        "explicitly_approved": inputs.explicitly_approved,
        "is_published_version": inputs.is_published_version,
        "is_ephemeral": inputs.is_ephemeral,
    }


def projection_input_sha256(inputs: ProjectionInput) -> str:
    """Digest the exact bounded ProjectionInput without persisting its text body."""

    return _json_sha256(_projection_input_material(inputs))


def privacy_decision_binding_ref(input_sha256: str) -> str:
    digest = str(input_sha256 or "").lower()
    if not _HEX64.fullmatch(digest):
        raise ValueError("PRIVACY_DECISION_INPUT_SHA256_INVALID")
    return f"privacy-input-sha256:{digest}"


@dataclass(frozen=True)
class PrivacyPublicationDecisionRecord:
    decision_id: str
    contract_version: str
    subject_ref: str
    record_ref: str
    record_version: str
    field_name: str
    data_class: str
    relevance_reason: str | None
    explicitly_approved: bool
    is_published_version: bool
    is_ephemeral: bool
    text_value_sha256: str | None
    input_sha256: str
    privacy_policy_version: str
    decision_action: str
    decision_reasons: tuple[str, ...]
    reviewer_ref: str
    audit_ref: str
    reviewed_at: str
    review_sequence: int
    supersedes_decision_id: str | None
    decision_integrity_sha256: str


@dataclass(frozen=True)
class PrivacyDecisionReplay:
    decision: ProjectionDecision
    decision_ref: str | None
    input_sha256: str
    blockers: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.decision.allowed and not self.blockers


def _input_material_from_record(record: PrivacyPublicationDecisionRecord) -> dict[str, object]:
    return {
        "input_contract_version": "privacy-projection-input-v1",
        "field_name": record.field_name,
        "data_class": record.data_class,
        "text_value_sha256": record.text_value_sha256,
        "relevance_reason": record.relevance_reason,
        "explicitly_approved": record.explicitly_approved,
        "is_published_version": record.is_published_version,
        "is_ephemeral": record.is_ephemeral,
    }


def _decision_integrity_material(
    *,
    contract_version: str,
    subject_ref: str,
    record_ref: str,
    record_version: str,
    input_material: dict[str, object],
    input_sha256: str,
    privacy_policy_version: str,
    decision: ProjectionDecision,
    reviewer_ref: str,
    audit_ref: str,
    reviewed_at: str,
    review_sequence: int,
    supersedes_decision_id: str | None,
) -> dict[str, object]:
    return {
        "contract_version": contract_version,
        "subject_ref": subject_ref,
        "record_ref": record_ref,
        "record_version": record_version,
        **input_material,
        "input_sha256": input_sha256,
        "privacy_policy_version": privacy_policy_version,
        "decision_action": decision.decision.value,
        "decision_reasons": list(decision.reasons),
        "reviewer_ref": reviewer_ref,
        "audit_ref": audit_ref,
        "reviewed_at": reviewed_at,
        "review_sequence": review_sequence,
        "supersedes_decision_id": supersedes_decision_id,
    }


def _record_integrity_valid(record: PrivacyPublicationDecisionRecord) -> bool:
    input_material = _input_material_from_record(record)
    if _json_sha256(input_material) != record.input_sha256:
        return False
    try:
        decision = ProjectionDecision(
            PublicationDecision(record.decision_action),
            record.decision_reasons,
        )
    except ValueError:
        return False
    material = _decision_integrity_material(
        contract_version=record.contract_version,
        subject_ref=record.subject_ref,
        record_ref=record.record_ref,
        record_version=record.record_version,
        input_material=input_material,
        input_sha256=record.input_sha256,
        privacy_policy_version=record.privacy_policy_version,
        decision=decision,
        reviewer_ref=record.reviewer_ref,
        audit_ref=record.audit_ref,
        reviewed_at=record.reviewed_at,
        review_sequence=record.review_sequence,
        supersedes_decision_id=record.supersedes_decision_id,
    )
    expected = _json_sha256(material)
    return (
        record.decision_integrity_sha256 == expected
        and record.decision_id == f"privacy-decision:{expected}"
    )


def _record_from_row(row: object) -> PrivacyPublicationDecisionRecord:
    if not isinstance(row, dict):
        raise ValueError("PRIVACY_DECISION_ROW_INVALID")
    reasons = row.get("decision_reasons")
    if not isinstance(reasons, list) or not reasons or len(reasons) > 32:
        raise ValueError("PRIVACY_DECISION_REASONS_INVALID")
    clean_reasons: list[str] = []
    for reason in reasons:
        clean_reasons.append(
            _bounded_exact_text(
                reason,
                "PRIVACY_DECISION_REASONS_INVALID",
                limit=128,
            )
        )
    sequence = row.get("review_sequence")
    if not isinstance(sequence, int) or sequence < 1:
        raise ValueError("PRIVACY_DECISION_SEQUENCE_INVALID")
    text_hash = row.get("text_value_sha256")
    if text_hash is not None and (not isinstance(text_hash, str) or not _HEX64.fullmatch(text_hash)):
        raise ValueError("PRIVACY_DECISION_TEXT_HASH_INVALID")
    input_hash = str(row.get("input_sha256") or "")
    integrity_hash = str(row.get("decision_integrity_sha256") or "")
    if not _HEX64.fullmatch(input_hash) or not _HEX64.fullmatch(integrity_hash):
        raise ValueError("PRIVACY_DECISION_DIGEST_INVALID")
    for flag_name in ("explicitly_approved", "is_published_version", "is_ephemeral"):
        if not isinstance(row.get(flag_name), bool):
            raise ValueError(f"PRIVACY_DECISION_{flag_name.upper()}_INVALID")
    return PrivacyPublicationDecisionRecord(
        decision_id=_bounded_exact_text(
            row.get("decision_id"), "PRIVACY_DECISION_ID_INVALID", limit=96
        ),
        contract_version=_bounded_exact_text(
            row.get("contract_version"), "PRIVACY_DECISION_CONTRACT_INVALID", limit=128
        ),
        subject_ref=_bounded_ref(row.get("subject_ref"), "PRIVACY_DECISION_SUBJECT_REF_INVALID"),
        record_ref=_bounded_ref(row.get("record_ref"), "PRIVACY_DECISION_RECORD_REF_INVALID"),
        record_version=_bounded_ref(
            row.get("record_version"), "PRIVACY_DECISION_RECORD_VERSION_INVALID"
        ),
        field_name=_bounded_exact_text(
            row.get("field_name"), "PRIVACY_DECISION_FIELD_NAME_INVALID", limit=128
        ),
        data_class=_bounded_exact_text(
            row.get("data_class"), "PRIVACY_DECISION_DATA_CLASS_INVALID", limit=64
        ),
        relevance_reason=(
            None
            if row.get("relevance_reason") is None
            else _bounded_exact_text(
                row.get("relevance_reason"),
                "PRIVACY_DECISION_RELEVANCE_REASON_INVALID",
                limit=128,
            )
        ),
        explicitly_approved=bool(row.get("explicitly_approved")),
        is_published_version=bool(row.get("is_published_version")),
        is_ephemeral=bool(row.get("is_ephemeral")),
        text_value_sha256=text_hash,
        input_sha256=input_hash,
        privacy_policy_version=_bounded_exact_text(
            row.get("privacy_policy_version"),
            "PRIVACY_DECISION_POLICY_VERSION_INVALID",
            limit=128,
        ),
        decision_action=_bounded_exact_text(
            row.get("decision_action"), "PRIVACY_DECISION_ACTION_INVALID", limit=32
        ),
        decision_reasons=tuple(clean_reasons),
        reviewer_ref=_bounded_audit_ref(
            row.get("reviewer_ref"), "PRIVACY_DECISION_REVIEWER_REF_INVALID"
        ),
        audit_ref=_bounded_audit_ref(
            row.get("audit_ref"), "PRIVACY_DECISION_AUDIT_REF_INVALID"
        ),
        reviewed_at=_reviewed_at(row.get("reviewed_at_text")),
        review_sequence=sequence,
        supersedes_decision_id=(
            None
            if row.get("supersedes_decision_id") is None
            else _bounded_exact_text(
                row.get("supersedes_decision_id"),
                "PRIVACY_DECISION_SUPERSEDES_INVALID",
                limit=96,
            )
        ),
        decision_integrity_sha256=integrity_hash,
    )


def _hold(canonical: ProjectionDecision, code: str) -> ProjectionDecision:
    if canonical.decision is PublicationDecision.PROHIBIT:
        return ProjectionDecision(
            PublicationDecision.PROHIBIT,
            tuple(dict.fromkeys((*canonical.reasons, code))),
        )
    if canonical.decision is PublicationDecision.HOLD_FOR_REVIEW:
        return ProjectionDecision(
            PublicationDecision.HOLD_FOR_REVIEW,
            tuple(dict.fromkeys((*canonical.reasons, code))),
        )
    return ProjectionDecision(PublicationDecision.HOLD_FOR_REVIEW, (code,))


def _prohibit(code: str) -> ProjectionDecision:
    return ProjectionDecision(PublicationDecision.PROHIBIT, (code,))


class PrivacyPublicationDecisionStore(PsqlRuntime):
    """Private DP-304 review ledger; record_version is a caller-supplied binding only."""

    def _load_lineage(
        self,
        *,
        subject_ref: str,
        record_ref: str,
        field_name: str,
    ) -> tuple[PrivacyPublicationDecisionRecord, ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'decision_id', decision_id,
                'contract_version', contract_version,
                'subject_ref', subject_ref,
                'record_ref', record_ref,
                'record_version', record_version,
                'field_name', field_name,
                'data_class', data_class,
                'relevance_reason', relevance_reason,
                'explicitly_approved', explicitly_approved,
                'is_published_version', is_published_version,
                'is_ephemeral', is_ephemeral,
                'text_value_sha256', text_value_sha256,
                'input_sha256', input_sha256,
                'privacy_policy_version', privacy_policy_version,
                'decision_action', decision_action,
                'decision_reasons', decision_reasons,
                'reviewer_ref', reviewer_ref,
                'audit_ref', audit_ref,
                'reviewed_at_text', reviewed_at_text,
                'review_sequence', review_sequence,
                'supersedes_decision_id', supersedes_decision_id,
                'decision_integrity_sha256', decision_integrity_sha256
            ) ORDER BY review_sequence)::text, '[]')
            FROM privacy_publication_decision
            WHERE subject_ref = :'subject_ref'
              AND record_ref = :'record_ref'
              AND field_name = :'field_name';
            """,
            subject_ref=subject_ref,
            record_ref=record_ref,
            field_name=field_name,
        )
        rows = json.loads(raw or "[]")
        return tuple(_record_from_row(row) for row in rows)

    @staticmethod
    def _lineage_blockers(
        records: tuple[PrivacyPublicationDecisionRecord, ...],
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        previous: PrivacyPublicationDecisionRecord | None = None
        for index, record in enumerate(records, start=1):
            if record.review_sequence != index:
                blockers.append("PRIVACY_DECISION_CHAIN_SEQUENCE_INVALID")
            if not _record_integrity_valid(record):
                blockers.append("PRIVACY_DECISION_TAMPERED")
            if previous is None:
                if record.supersedes_decision_id is not None:
                    blockers.append("PRIVACY_DECISION_CHAIN_ROOT_INVALID")
            else:
                if record.supersedes_decision_id != previous.decision_id:
                    blockers.append("PRIVACY_DECISION_CHAIN_SUPERSESSION_INVALID")
                if (
                    record.subject_ref != previous.subject_ref
                    or record.record_ref != previous.record_ref
                    or record.field_name != previous.field_name
                ):
                    blockers.append("PRIVACY_DECISION_CHAIN_BINDING_INVALID")
            previous = record
        return tuple(dict.fromkeys(blockers))

    def append_review(
        self,
        *,
        subject_ref: str,
        record_ref: str,
        record_version: str,
        inputs: ProjectionInput,
        reviewer_ref: str,
        audit_ref: str,
        reviewed_at: str,
        supersedes_decision_id: str | None = None,
    ) -> PrivacyPublicationDecisionRecord:
        clean_subject = _bounded_ref(subject_ref, "PRIVACY_DECISION_SUBJECT_REF_INVALID")
        clean_record = _bounded_ref(record_ref, "PRIVACY_DECISION_RECORD_REF_INVALID")
        clean_version = _bounded_ref(
            record_version, "PRIVACY_DECISION_RECORD_VERSION_INVALID"
        )
        clean_reviewer = _bounded_audit_ref(
            reviewer_ref, "PRIVACY_DECISION_REVIEWER_REF_INVALID"
        )
        clean_audit = _bounded_audit_ref(audit_ref, "PRIVACY_DECISION_AUDIT_REF_INVALID")
        clean_reviewed_at = _reviewed_at(reviewed_at)
        input_material = _projection_input_material(inputs)
        field_name = str(input_material["field_name"])
        input_digest = _json_sha256(input_material)
        decision = decide_projection(inputs)

        existing = self._load_lineage(
            subject_ref=clean_subject,
            record_ref=clean_record,
            field_name=field_name,
        )
        blockers = self._lineage_blockers(existing)
        if blockers:
            raise ValueError(blockers[0])
        if existing:
            latest = existing[-1]
            if supersedes_decision_id is None:
                raise ValueError("PRIVACY_DECISION_SUPERSESSION_REQUIRED")
            if supersedes_decision_id != latest.decision_id:
                raise ValueError("PRIVACY_DECISION_SUPERSEDES_NOT_LATEST")
            sequence = latest.review_sequence + 1
        else:
            if supersedes_decision_id is not None:
                raise ValueError("PRIVACY_DECISION_SUPERSEDES_MISSING")
            sequence = 1

        integrity_material = _decision_integrity_material(
            contract_version=PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION,
            subject_ref=clean_subject,
            record_ref=clean_record,
            record_version=clean_version,
            input_material=input_material,
            input_sha256=input_digest,
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            decision=decision,
            reviewer_ref=clean_reviewer,
            audit_ref=clean_audit,
            reviewed_at=clean_reviewed_at,
            review_sequence=sequence,
            supersedes_decision_id=supersedes_decision_id,
        )
        integrity = _json_sha256(integrity_material)
        record = PrivacyPublicationDecisionRecord(
            decision_id=f"privacy-decision:{integrity}",
            contract_version=PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION,
            subject_ref=clean_subject,
            record_ref=clean_record,
            record_version=clean_version,
            field_name=field_name,
            data_class=str(input_material["data_class"]),
            relevance_reason=input_material["relevance_reason"],  # type: ignore[arg-type]
            explicitly_approved=bool(input_material["explicitly_approved"]),
            is_published_version=bool(input_material["is_published_version"]),
            is_ephemeral=bool(input_material["is_ephemeral"]),
            text_value_sha256=input_material["text_value_sha256"],  # type: ignore[arg-type]
            input_sha256=input_digest,
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            decision_action=decision.decision.value,
            decision_reasons=decision.reasons,
            reviewer_ref=clean_reviewer,
            audit_ref=clean_audit,
            reviewed_at=clean_reviewed_at,
            review_sequence=sequence,
            supersedes_decision_id=supersedes_decision_id,
            decision_integrity_sha256=integrity,
        )
        self.run(
            """
            INSERT INTO privacy_publication_decision (
                decision_id, contract_version, subject_ref, record_ref, record_version,
                field_name, data_class, relevance_reason, explicitly_approved,
                is_published_version, is_ephemeral, text_value_sha256, input_sha256,
                privacy_policy_version, decision_action, decision_reasons,
                reviewer_ref, audit_ref, reviewed_at_text, review_sequence,
                supersedes_decision_id, decision_integrity_sha256
            ) VALUES (
                :'decision_id', :'contract_version', :'subject_ref', :'record_ref', :'record_version',
                :'field_name', :'data_class', NULLIF(:'relevance_reason',''), :'explicitly_approved'::boolean,
                :'is_published_version'::boolean, :'is_ephemeral'::boolean,
                NULLIF(:'text_value_sha256',''), :'input_sha256', :'privacy_policy_version',
                :'decision_action', :'decision_reasons'::jsonb, :'reviewer_ref', :'audit_ref',
                :'reviewed_at_text', :'review_sequence'::integer,
                NULLIF(:'supersedes_decision_id',''), :'decision_integrity_sha256'
            );
            """,
            decision_id=record.decision_id,
            contract_version=record.contract_version,
            subject_ref=record.subject_ref,
            record_ref=record.record_ref,
            record_version=record.record_version,
            field_name=record.field_name,
            data_class=record.data_class,
            relevance_reason=record.relevance_reason or "",
            explicitly_approved=str(record.explicitly_approved).lower(),
            is_published_version=str(record.is_published_version).lower(),
            is_ephemeral=str(record.is_ephemeral).lower(),
            text_value_sha256=record.text_value_sha256 or "",
            input_sha256=record.input_sha256,
            privacy_policy_version=record.privacy_policy_version,
            decision_action=record.decision_action,
            decision_reasons=json.dumps(list(record.decision_reasons), separators=(",", ":")),
            reviewer_ref=record.reviewer_ref,
            audit_ref=record.audit_ref,
            reviewed_at_text=record.reviewed_at,
            review_sequence=record.review_sequence,
            supersedes_decision_id=record.supersedes_decision_id or "",
            decision_integrity_sha256=record.decision_integrity_sha256,
        )
        return record

    def replay_current(
        self,
        *,
        subject_ref: str,
        record_ref: str,
        current_record_version: str,
        inputs: ProjectionInput,
    ) -> PrivacyDecisionReplay:
        clean_subject = _bounded_ref(subject_ref, "PRIVACY_DECISION_SUBJECT_REF_INVALID")
        clean_record = _bounded_ref(record_ref, "PRIVACY_DECISION_RECORD_REF_INVALID")
        clean_version = _bounded_ref(
            current_record_version, "PRIVACY_DECISION_RECORD_VERSION_INVALID"
        )
        input_material = _projection_input_material(inputs)
        input_digest = _json_sha256(input_material)
        canonical = decide_projection(inputs)
        field_name = str(input_material["field_name"])
        try:
            records = self._load_lineage(
                subject_ref=clean_subject,
                record_ref=clean_record,
                field_name=field_name,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            code = "PRIVACY_DECISION_ROW_INVALID"
            return PrivacyDecisionReplay(_prohibit(code), None, input_digest, (code,))

        if not records:
            code = "PRIVACY_DECISION_MISSING"
            return PrivacyDecisionReplay(_hold(canonical, code), None, input_digest, (code,))

        chain_blockers = self._lineage_blockers(records)
        if chain_blockers:
            return PrivacyDecisionReplay(
                _prohibit(chain_blockers[0]),
                None,
                input_digest,
                chain_blockers,
            )

        latest = records[-1]
        if latest.contract_version != PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION:
            code = "PRIVACY_DECISION_CONTRACT_STALE"
            return PrivacyDecisionReplay(_hold(canonical, code), None, input_digest, (code,))
        if latest.record_version != clean_version:
            code = "PRIVACY_DECISION_RECORD_VERSION_STALE"
            return PrivacyDecisionReplay(_hold(canonical, code), None, input_digest, (code,))
        if latest.privacy_policy_version != PRIVACY_POLICY_VERSION:
            code = "PRIVACY_DECISION_POLICY_VERSION_STALE"
            return PrivacyDecisionReplay(_hold(canonical, code), None, input_digest, (code,))
        if latest.input_sha256 != input_digest:
            code = "PRIVACY_DECISION_INPUT_STALE"
            return PrivacyDecisionReplay(_hold(canonical, code), None, input_digest, (code,))
        if (
            latest.decision_action != canonical.decision.value
            or latest.decision_reasons != canonical.reasons
        ):
            code = "PRIVACY_DECISION_POLICY_REPLAY_MISMATCH"
            return PrivacyDecisionReplay(_prohibit(code), None, input_digest, (code,))
        return PrivacyDecisionReplay(canonical, latest.decision_id, input_digest, ())

    def replay_current_text_field(
        self,
        *,
        subject_ref: str,
        record_ref: str,
        current_record_version: str,
        field_name: str,
        current_text_value: str,
    ) -> PrivacyDecisionReplay:
        """Replay the persisted reviewer classification against the current field text.

        Projection owns the current text, while data class, relevance reason and approval
        flags are reviewer decisions.  Reusing those integrity-protected inputs avoids
        silently inventing a new privacy/legal conclusion at publication time.
        """

        clean_subject = _bounded_ref(subject_ref, "PRIVACY_DECISION_SUBJECT_REF_INVALID")
        clean_record = _bounded_ref(record_ref, "PRIVACY_DECISION_RECORD_REF_INVALID")
        clean_field = _bounded_exact_text(
            field_name, "PRIVACY_DECISION_FIELD_NAME_INVALID", limit=128
        )
        records = self._load_lineage(
            subject_ref=clean_subject,
            record_ref=clean_record,
            field_name=clean_field,
        )
        if not records:
            return self.replay_current(
                subject_ref=clean_subject,
                record_ref=clean_record,
                current_record_version=current_record_version,
                inputs=ProjectionInput(
                    field_name=clean_field,
                    data_class="UNKNOWN",
                    text_value=current_text_value,
                ),
            )
        latest = records[-1]
        return self.replay_current(
            subject_ref=clean_subject,
            record_ref=clean_record,
            current_record_version=current_record_version,
            inputs=ProjectionInput(
                field_name=latest.field_name,
                data_class=latest.data_class,
                text_value=current_text_value,
                relevance_reason=latest.relevance_reason,
                explicitly_approved=latest.explicitly_approved,
                is_published_version=latest.is_published_version,
                is_ephemeral=latest.is_ephemeral,
            ),
        )


__all__ = [
    "PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION",
    "PrivacyDecisionReplay",
    "PrivacyPublicationDecisionRecord",
    "PrivacyPublicationDecisionStore",
    "privacy_decision_binding_ref",
    "projection_input_sha256",
]
