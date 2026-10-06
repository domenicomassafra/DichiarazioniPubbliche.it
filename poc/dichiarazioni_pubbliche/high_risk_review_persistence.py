from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dichiarazioni_pubbliche.high_risk_assertion import (
    HIGH_RISK_ASSERTION_VERSION,
    HighRiskDecision,
    HighRiskSignals,
    ProceduralStatus,
    RiskClass,
    classify_high_risk,
    evaluate_high_risk_candidate,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION = "high-risk-reviewed-packet-v1"
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_OFFICIAL_RECORD_STATES = frozenset({"APPROVED", "NOT_APPROVED", "UNRESOLVED"})
_MATCH_STATES = frozenset({"MATCH", "MISMATCH", "UNRESOLVED"})


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_ref(value: object, code: str) -> str:
    text = str(value or "")
    if not _REF_RE.fullmatch(text):
        raise ValueError(code)
    return text


def _optional_ref(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _required_ref(value, code)


def _required_exact_text(value: object, code: str, *, limit: int) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or len(value) > limit:
        raise ValueError(code)
    return value


def _reviewed_at(value: object) -> str:
    text = _required_exact_text(value, "HIGH_RISK_PACKET_REVIEWED_AT_INVALID", limit=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("HIGH_RISK_PACKET_REVIEWED_AT_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("HIGH_RISK_PACKET_REVIEWED_AT_TIMEZONE_REQUIRED")
    return parsed.isoformat()


def _required_bool(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(code)
    return value


def _state(value: object, allowed: frozenset[str], code: str) -> str:
    text = str(value or "")
    if text not in allowed:
        raise ValueError(code)
    return text


@dataclass(frozen=True)
class HighRiskReviewedPacketInput:
    source_text: str
    normalized_text: str
    identity_resolved: bool
    privacy_allows: bool
    legal_status_claim: bool = False
    identity_sensitive: bool = False
    sensitive_private: bool = False
    minor_victim_private_person: bool = False
    privacy_decision_ref: str | None = None
    privacy_decision_binding_ref: str | None = None
    official_record_state: str = "UNRESOLVED"
    official_record_ref: str | None = None
    jurisdiction_state: str = "UNRESOLVED"
    jurisdiction_ref: str | None = None
    effective_time_state: str = "UNRESOLVED"
    effective_time_ref: str | None = None
    human_review_actor_ref: str | None = None
    human_review_ref: str | None = None
    human_reviewed_at: str | None = None
    human_review_approved: bool = False
    dual_control_approved: bool = False
    qualified_policy_accepted: bool = False
    policy_decision_ref: str | None = None


@dataclass(frozen=True)
class HighRiskReviewedPacketRecord:
    packet_id: str
    contract_version: str
    record_ref: str
    finding_ref: str
    record_version: str
    source_text_sha256: str
    normalized_text_sha256: str
    source_allegation_framing: bool
    normalized_allegation_framing: bool
    legal_status_claim: bool
    identity_sensitive: bool
    sensitive_private: bool
    minor_victim_private_person: bool
    identity_resolved: bool
    privacy_allows: bool
    privacy_decision_ref: str | None
    privacy_decision_binding_ref: str | None
    official_record_state: str
    official_record_ref: str | None
    official_record_approved: bool
    jurisdiction_state: str
    jurisdiction_ref: str | None
    jurisdiction_match: bool
    effective_time_state: str
    effective_time_ref: str | None
    effective_time_match: bool
    human_review_actor_ref: str | None
    human_review_ref: str | None
    human_reviewed_at: str | None
    human_review_approved: bool
    dual_control_approved: bool
    qualified_policy_accepted: bool
    policy_decision_ref: str | None
    high_risk_policy_version: str
    input_sha256: str
    decision_disposition: str
    decision_reason_codes: tuple[str, ...]
    risk_classes: tuple[str, ...]
    procedural_statuses: tuple[str, ...]
    decision_policy_ref: str | None
    decision_binding_sha256: str
    packet_sequence: int
    supersedes_packet_id: str | None
    packet_integrity_sha256: str


@dataclass(frozen=True)
class HighRiskPacketReplay:
    decision: HighRiskDecision
    packet_ref: str | None
    input_sha256: str
    decision_binding_sha256: str
    blockers: tuple[str, ...]

    @property
    def publication_allowed(self) -> bool:
        return self.decision.publication_allowed and not self.blockers


def _framing_signal(text: str) -> bool:
    return classify_high_risk(source_text=text, normalized_text="").allegation_framing


def _input_material(inputs: HighRiskReviewedPacketInput) -> dict[str, object]:
    source_text = _required_exact_text(
        inputs.source_text,
        "HIGH_RISK_PACKET_SOURCE_TEXT_INVALID",
        limit=200_000,
    )
    normalized_text = _required_exact_text(
        inputs.normalized_text,
        "HIGH_RISK_PACKET_NORMALIZED_TEXT_INVALID",
        limit=100_000,
    )
    identity_resolved = _required_bool(
        inputs.identity_resolved, "HIGH_RISK_PACKET_IDENTITY_RESOLVED_INVALID"
    )
    privacy_allows = _required_bool(
        inputs.privacy_allows, "HIGH_RISK_PACKET_PRIVACY_ALLOWS_INVALID"
    )
    legal_status_claim = _required_bool(
        inputs.legal_status_claim, "HIGH_RISK_PACKET_LEGAL_STATUS_CLAIM_INVALID"
    )
    identity_sensitive = _required_bool(
        inputs.identity_sensitive, "HIGH_RISK_PACKET_IDENTITY_SENSITIVE_INVALID"
    )
    sensitive_private = _required_bool(
        inputs.sensitive_private, "HIGH_RISK_PACKET_SENSITIVE_PRIVATE_INVALID"
    )
    minor_victim_private_person = _required_bool(
        inputs.minor_victim_private_person,
        "HIGH_RISK_PACKET_MINOR_VICTIM_PRIVATE_PERSON_INVALID",
    )
    dual_control_approved = _required_bool(
        inputs.dual_control_approved, "HIGH_RISK_PACKET_DUAL_CONTROL_INVALID"
    )
    human_review_approved = _required_bool(
        inputs.human_review_approved, "HIGH_RISK_PACKET_HUMAN_REVIEW_APPROVED_INVALID"
    )
    qualified_policy_accepted = _required_bool(
        inputs.qualified_policy_accepted,
        "HIGH_RISK_PACKET_QUALIFIED_POLICY_ACCEPTED_INVALID",
    )

    privacy_ref = _optional_ref(
        inputs.privacy_decision_ref, "HIGH_RISK_PACKET_PRIVACY_DECISION_REF_INVALID"
    )
    privacy_binding = _optional_ref(
        inputs.privacy_decision_binding_ref,
        "HIGH_RISK_PACKET_PRIVACY_DECISION_BINDING_INVALID",
    )
    if (privacy_ref is None) != (privacy_binding is None):
        raise ValueError("HIGH_RISK_PACKET_PRIVACY_DECISION_BINDING_INCOMPLETE")

    official_state = _state(
        inputs.official_record_state,
        _OFFICIAL_RECORD_STATES,
        "HIGH_RISK_PACKET_OFFICIAL_RECORD_STATE_INVALID",
    )
    official_ref = _optional_ref(
        inputs.official_record_ref, "HIGH_RISK_PACKET_OFFICIAL_RECORD_REF_INVALID"
    )
    if official_state == "APPROVED" and official_ref is None:
        raise ValueError("HIGH_RISK_PACKET_OFFICIAL_RECORD_REF_REQUIRED")

    jurisdiction_state = _state(
        inputs.jurisdiction_state,
        _MATCH_STATES,
        "HIGH_RISK_PACKET_JURISDICTION_STATE_INVALID",
    )
    jurisdiction_ref = _optional_ref(
        inputs.jurisdiction_ref, "HIGH_RISK_PACKET_JURISDICTION_REF_INVALID"
    )
    if jurisdiction_state == "MATCH" and jurisdiction_ref is None:
        raise ValueError("HIGH_RISK_PACKET_JURISDICTION_REF_REQUIRED")

    effective_time_state = _state(
        inputs.effective_time_state,
        _MATCH_STATES,
        "HIGH_RISK_PACKET_EFFECTIVE_TIME_STATE_INVALID",
    )
    effective_time_ref = _optional_ref(
        inputs.effective_time_ref, "HIGH_RISK_PACKET_EFFECTIVE_TIME_REF_INVALID"
    )
    if effective_time_state == "MATCH" and effective_time_ref is None:
        raise ValueError("HIGH_RISK_PACKET_EFFECTIVE_TIME_REF_REQUIRED")

    review_values = (
        inputs.human_review_actor_ref,
        inputs.human_review_ref,
        inputs.human_reviewed_at,
    )
    if any(value is not None for value in review_values) and not all(
        value is not None for value in review_values
    ):
        raise ValueError("HIGH_RISK_PACKET_HUMAN_REVIEW_BINDING_INCOMPLETE")
    if all(value is not None for value in review_values):
        human_actor = _required_ref(
            inputs.human_review_actor_ref,
            "HIGH_RISK_PACKET_HUMAN_REVIEW_ACTOR_REF_INVALID",
        )
        human_ref = _required_ref(
            inputs.human_review_ref,
            "HIGH_RISK_PACKET_HUMAN_REVIEW_REF_INVALID",
        )
        human_reviewed_at = _reviewed_at(inputs.human_reviewed_at)
        human_review_approved = True
    else:
        human_actor = None
        human_ref = None
        human_reviewed_at = None
    if human_review_approved and human_actor is None:
        raise ValueError("HIGH_RISK_PACKET_HUMAN_REVIEW_APPROVAL_REF_REQUIRED")

    policy_ref = _optional_ref(
        inputs.policy_decision_ref, "HIGH_RISK_PACKET_POLICY_DECISION_REF_INVALID"
    )
    if qualified_policy_accepted and policy_ref is None:
        raise ValueError("HIGH_RISK_PACKET_QUALIFIED_POLICY_REF_REQUIRED")
    if not qualified_policy_accepted and policy_ref is not None:
        raise ValueError("HIGH_RISK_PACKET_UNACCEPTED_POLICY_REF_FORBIDDEN")

    return {
        "input_contract_version": HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION,
        "source_text_sha256": _text_sha256(source_text),
        "normalized_text_sha256": _text_sha256(normalized_text),
        "source_allegation_framing": _framing_signal(source_text),
        "normalized_allegation_framing": _framing_signal(normalized_text),
        "legal_status_claim": legal_status_claim,
        "identity_sensitive": identity_sensitive,
        "sensitive_private": sensitive_private,
        "minor_victim_private_person": minor_victim_private_person,
        "identity_resolved": identity_resolved,
        "privacy_allows": privacy_allows,
        "privacy_decision_ref": privacy_ref,
        "privacy_decision_binding_ref": privacy_binding,
        "official_record_state": official_state,
        "official_record_ref": official_ref,
        "official_record_approved": official_state == "APPROVED",
        "jurisdiction_state": jurisdiction_state,
        "jurisdiction_ref": jurisdiction_ref,
        "jurisdiction_match": jurisdiction_state == "MATCH",
        "effective_time_state": effective_time_state,
        "effective_time_ref": effective_time_ref,
        "effective_time_match": effective_time_state == "MATCH",
        "human_review_actor_ref": human_actor,
        "human_review_ref": human_ref,
        "human_reviewed_at": human_reviewed_at,
        "human_review_approved": human_review_approved,
        "dual_control_approved": dual_control_approved,
        "qualified_policy_accepted": qualified_policy_accepted,
        "policy_decision_ref": policy_ref,
        "high_risk_policy_version": HIGH_RISK_ASSERTION_VERSION,
    }


def high_risk_packet_input_sha256(inputs: HighRiskReviewedPacketInput) -> str:
    """Bind the exact reviewed input without persisting source/public text bodies."""

    return _json_sha256(_input_material(inputs))


def _evaluate(
    inputs: HighRiskReviewedPacketInput,
    material: dict[str, object],
) -> HighRiskDecision:
    return evaluate_high_risk_candidate(
        source_text=inputs.source_text,
        normalized_text=inputs.normalized_text,
        legal_status_claim=bool(material["legal_status_claim"]),
        identity_sensitive=bool(material["identity_sensitive"]),
        sensitive_private=bool(material["sensitive_private"]),
        minor_victim_private_person=bool(material["minor_victim_private_person"]),
        identity_resolved=bool(material["identity_resolved"]),
        privacy_allows=bool(material["privacy_allows"]),
        official_record_approved=bool(material["official_record_approved"]),
        jurisdiction_match=bool(material["jurisdiction_match"]),
        effective_time_match=bool(material["effective_time_match"]),
        human_review_approved=bool(material["human_review_approved"]),
        dual_control_approved=bool(material["dual_control_approved"]),
        qualified_policy_accepted=bool(material["qualified_policy_accepted"]),
        policy_decision_ref=material["policy_decision_ref"],  # type: ignore[arg-type]
    )


def _decision_material(decision: HighRiskDecision) -> dict[str, object]:
    return {
        "high_risk_policy_version": str(decision.version),
        "decision_disposition": str(decision.disposition),
        "decision_reason_codes": list(decision.reason_codes),
        "risk_classes": [str(value) for value in decision.signals.risk_classes],
        "procedural_statuses": [str(value) for value in decision.signals.procedural_statuses],
        "source_allegation_framing": bool(decision.signals.allegation_framing),
        "decision_policy_ref": decision.policy_decision_ref,
    }


def _decision_binding(input_sha256: str, decision: HighRiskDecision) -> str:
    return _json_sha256(
        {
            "input_sha256": input_sha256,
            "decision": _decision_material(decision),
        }
    )


def _input_material_from_record(record: HighRiskReviewedPacketRecord) -> dict[str, object]:
    return {
        "input_contract_version": record.contract_version,
        "source_text_sha256": record.source_text_sha256,
        "normalized_text_sha256": record.normalized_text_sha256,
        "source_allegation_framing": record.source_allegation_framing,
        "normalized_allegation_framing": record.normalized_allegation_framing,
        "legal_status_claim": record.legal_status_claim,
        "identity_sensitive": record.identity_sensitive,
        "sensitive_private": record.sensitive_private,
        "minor_victim_private_person": record.minor_victim_private_person,
        "identity_resolved": record.identity_resolved,
        "privacy_allows": record.privacy_allows,
        "privacy_decision_ref": record.privacy_decision_ref,
        "privacy_decision_binding_ref": record.privacy_decision_binding_ref,
        "official_record_state": record.official_record_state,
        "official_record_ref": record.official_record_ref,
        "official_record_approved": record.official_record_approved,
        "jurisdiction_state": record.jurisdiction_state,
        "jurisdiction_ref": record.jurisdiction_ref,
        "jurisdiction_match": record.jurisdiction_match,
        "effective_time_state": record.effective_time_state,
        "effective_time_ref": record.effective_time_ref,
        "effective_time_match": record.effective_time_match,
        "human_review_actor_ref": record.human_review_actor_ref,
        "human_review_ref": record.human_review_ref,
        "human_reviewed_at": record.human_reviewed_at,
        "human_review_approved": record.human_review_approved,
        "dual_control_approved": record.dual_control_approved,
        "qualified_policy_accepted": record.qualified_policy_accepted,
        "policy_decision_ref": record.policy_decision_ref,
        "high_risk_policy_version": record.high_risk_policy_version,
    }


def _decision_material_from_record(record: HighRiskReviewedPacketRecord) -> dict[str, object]:
    return {
        "high_risk_policy_version": record.high_risk_policy_version,
        "decision_disposition": record.decision_disposition,
        "decision_reason_codes": list(record.decision_reason_codes),
        "risk_classes": list(record.risk_classes),
        "procedural_statuses": list(record.procedural_statuses),
        "source_allegation_framing": record.source_allegation_framing,
        "decision_policy_ref": record.decision_policy_ref,
    }


def _packet_integrity_material(record: HighRiskReviewedPacketRecord) -> dict[str, object]:
    return {
        "contract_version": record.contract_version,
        "record_ref": record.record_ref,
        "finding_ref": record.finding_ref,
        "record_version": record.record_version,
        "input": _input_material_from_record(record),
        "input_sha256": record.input_sha256,
        "decision": _decision_material_from_record(record),
        "decision_binding_sha256": record.decision_binding_sha256,
        "packet_sequence": record.packet_sequence,
        "supersedes_packet_id": record.supersedes_packet_id,
    }


def _record_integrity_valid(record: HighRiskReviewedPacketRecord) -> bool:
    input_material = _input_material_from_record(record)
    if _json_sha256(input_material) != record.input_sha256:
        return False
    expected_decision_binding = _json_sha256(
        {
            "input_sha256": record.input_sha256,
            "decision": _decision_material_from_record(record),
        }
    )
    if expected_decision_binding != record.decision_binding_sha256:
        return False
    expected_integrity = _json_sha256(_packet_integrity_material(record))
    return (
        expected_integrity == record.packet_integrity_sha256
        and record.packet_id == f"high-risk-packet:{expected_integrity}"
    )


def _string_tuple(value: object, code: str, *, limit: int = 32) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > limit:
        raise ValueError(code)
    cleaned: list[str] = []
    for item in value:
        cleaned.append(_required_exact_text(item, code, limit=128))
    return tuple(cleaned)


def _optional_string_tuple(value: object, code: str, *, limit: int = 16) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(code)
    cleaned: list[str] = []
    for item in value:
        cleaned.append(_required_exact_text(item, code, limit=128))
    return tuple(cleaned)


def _row_record(row: object) -> HighRiskReviewedPacketRecord:
    if not isinstance(row, dict):
        raise ValueError("HIGH_RISK_PACKET_ROW_INVALID")
    source_hash = str(row.get("source_text_sha256") or "")
    normalized_hash = str(row.get("normalized_text_sha256") or "")
    input_hash = str(row.get("input_sha256") or "")
    decision_binding = str(row.get("decision_binding_sha256") or "")
    integrity = str(row.get("packet_integrity_sha256") or "")
    if not all(
        _HEX64_RE.fullmatch(value)
        for value in (source_hash, normalized_hash, input_hash, decision_binding, integrity)
    ):
        raise ValueError("HIGH_RISK_PACKET_DIGEST_INVALID")
    sequence = row.get("packet_sequence")
    if not isinstance(sequence, int) or sequence < 1:
        raise ValueError("HIGH_RISK_PACKET_SEQUENCE_INVALID")
    bool_fields = (
        "source_allegation_framing",
        "normalized_allegation_framing",
        "legal_status_claim",
        "identity_sensitive",
        "sensitive_private",
        "minor_victim_private_person",
        "identity_resolved",
        "privacy_allows",
        "official_record_approved",
        "jurisdiction_match",
        "effective_time_match",
        "human_review_approved",
        "dual_control_approved",
        "qualified_policy_accepted",
    )
    for name in bool_fields:
        if not isinstance(row.get(name), bool):
            raise ValueError(f"HIGH_RISK_PACKET_{name.upper()}_INVALID")
    return HighRiskReviewedPacketRecord(
        packet_id=_required_exact_text(row.get("packet_id"), "HIGH_RISK_PACKET_ID_INVALID", limit=96),
        contract_version=_required_exact_text(
            row.get("contract_version"), "HIGH_RISK_PACKET_CONTRACT_INVALID", limit=128
        ),
        record_ref=_required_ref(row.get("record_ref"), "HIGH_RISK_PACKET_RECORD_REF_INVALID"),
        finding_ref=_required_ref(row.get("finding_ref"), "HIGH_RISK_PACKET_FINDING_REF_INVALID"),
        record_version=_required_ref(
            row.get("record_version"), "HIGH_RISK_PACKET_RECORD_VERSION_INVALID"
        ),
        source_text_sha256=source_hash,
        normalized_text_sha256=normalized_hash,
        source_allegation_framing=bool(row["source_allegation_framing"]),
        normalized_allegation_framing=bool(row["normalized_allegation_framing"]),
        legal_status_claim=bool(row["legal_status_claim"]),
        identity_sensitive=bool(row["identity_sensitive"]),
        sensitive_private=bool(row["sensitive_private"]),
        minor_victim_private_person=bool(row["minor_victim_private_person"]),
        identity_resolved=bool(row["identity_resolved"]),
        privacy_allows=bool(row["privacy_allows"]),
        privacy_decision_ref=_optional_ref(
            row.get("privacy_decision_ref"), "HIGH_RISK_PACKET_PRIVACY_DECISION_REF_INVALID"
        ),
        privacy_decision_binding_ref=_optional_ref(
            row.get("privacy_decision_binding_ref"),
            "HIGH_RISK_PACKET_PRIVACY_DECISION_BINDING_INVALID",
        ),
        official_record_state=_state(
            row.get("official_record_state"),
            _OFFICIAL_RECORD_STATES,
            "HIGH_RISK_PACKET_OFFICIAL_RECORD_STATE_INVALID",
        ),
        official_record_ref=_optional_ref(
            row.get("official_record_ref"), "HIGH_RISK_PACKET_OFFICIAL_RECORD_REF_INVALID"
        ),
        official_record_approved=bool(row["official_record_approved"]),
        jurisdiction_state=_state(
            row.get("jurisdiction_state"),
            _MATCH_STATES,
            "HIGH_RISK_PACKET_JURISDICTION_STATE_INVALID",
        ),
        jurisdiction_ref=_optional_ref(
            row.get("jurisdiction_ref"), "HIGH_RISK_PACKET_JURISDICTION_REF_INVALID"
        ),
        jurisdiction_match=bool(row["jurisdiction_match"]),
        effective_time_state=_state(
            row.get("effective_time_state"),
            _MATCH_STATES,
            "HIGH_RISK_PACKET_EFFECTIVE_TIME_STATE_INVALID",
        ),
        effective_time_ref=_optional_ref(
            row.get("effective_time_ref"), "HIGH_RISK_PACKET_EFFECTIVE_TIME_REF_INVALID"
        ),
        effective_time_match=bool(row["effective_time_match"]),
        human_review_actor_ref=_optional_ref(
            row.get("human_review_actor_ref"),
            "HIGH_RISK_PACKET_HUMAN_REVIEW_ACTOR_REF_INVALID",
        ),
        human_review_ref=_optional_ref(
            row.get("human_review_ref"), "HIGH_RISK_PACKET_HUMAN_REVIEW_REF_INVALID"
        ),
        human_reviewed_at=(
            None if row.get("human_reviewed_at_text") is None else _reviewed_at(row.get("human_reviewed_at_text"))
        ),
        human_review_approved=bool(row["human_review_approved"]),
        dual_control_approved=bool(row["dual_control_approved"]),
        qualified_policy_accepted=bool(row["qualified_policy_accepted"]),
        policy_decision_ref=_optional_ref(
            row.get("policy_decision_ref"), "HIGH_RISK_PACKET_POLICY_DECISION_REF_INVALID"
        ),
        high_risk_policy_version=_required_exact_text(
            row.get("high_risk_policy_version"),
            "HIGH_RISK_PACKET_POLICY_VERSION_INVALID",
            limit=128,
        ),
        input_sha256=input_hash,
        decision_disposition=_required_exact_text(
            row.get("decision_disposition"), "HIGH_RISK_PACKET_DISPOSITION_INVALID", limit=64
        ),
        decision_reason_codes=_string_tuple(
            row.get("decision_reason_codes"), "HIGH_RISK_PACKET_REASON_CODES_INVALID"
        ),
        risk_classes=_optional_string_tuple(
            row.get("risk_classes"), "HIGH_RISK_PACKET_RISK_CLASSES_INVALID"
        ),
        procedural_statuses=_optional_string_tuple(
            row.get("procedural_statuses"), "HIGH_RISK_PACKET_PROCEDURAL_STATUSES_INVALID"
        ),
        decision_policy_ref=_optional_ref(
            row.get("decision_policy_ref"), "HIGH_RISK_PACKET_DECISION_POLICY_REF_INVALID"
        ),
        decision_binding_sha256=decision_binding,
        packet_sequence=sequence,
        supersedes_packet_id=(
            None
            if row.get("supersedes_packet_id") is None
            else _required_exact_text(
                row.get("supersedes_packet_id"),
                "HIGH_RISK_PACKET_SUPERSEDES_INVALID",
                limit=96,
            )
        ),
        packet_integrity_sha256=integrity,
    )


def _held(decision: HighRiskDecision, code: str) -> HighRiskDecision:
    if not decision.signals.requires_escalation:
        return decision
    reasons = (
        tuple(dict.fromkeys((*decision.reason_codes, code)))
        if decision.disposition == "HOLD_HIGH_RISK"
        else (code,)
    )
    return HighRiskDecision(
        disposition="HOLD_HIGH_RISK",
        reason_codes=reasons,
        signals=decision.signals,
        policy_decision_ref=decision.policy_decision_ref,
        version=decision.version,
    )


class HighRiskReviewedPacketStore(PsqlRuntime):
    """Private DP-309 packet store; it records review, never reviewer/legal authority."""

    def _load_lineage(
        self,
        *,
        record_ref: str,
        finding_ref: str,
    ) -> tuple[HighRiskReviewedPacketRecord, ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'packet_id', packet_id,
                'contract_version', contract_version,
                'record_ref', record_ref,
                'finding_ref', finding_ref,
                'record_version', record_version,
                'source_text_sha256', source_text_sha256,
                'normalized_text_sha256', normalized_text_sha256,
                'source_allegation_framing', source_allegation_framing,
                'normalized_allegation_framing', normalized_allegation_framing,
                'legal_status_claim', legal_status_claim,
                'identity_sensitive', identity_sensitive,
                'sensitive_private', sensitive_private,
                'minor_victim_private_person', minor_victim_private_person,
                'identity_resolved', identity_resolved,
                'privacy_allows', privacy_allows,
                'privacy_decision_ref', privacy_decision_ref,
                'privacy_decision_binding_ref', privacy_decision_binding_ref,
                'official_record_state', official_record_state,
                'official_record_ref', official_record_ref,
                'official_record_approved', official_record_approved,
                'jurisdiction_state', jurisdiction_state,
                'jurisdiction_ref', jurisdiction_ref,
                'jurisdiction_match', jurisdiction_match,
                'effective_time_state', effective_time_state,
                'effective_time_ref', effective_time_ref,
                'effective_time_match', effective_time_match,
                'human_review_actor_ref', human_review_actor_ref,
                'human_review_ref', human_review_ref,
                'human_reviewed_at_text', human_reviewed_at_text,
                'human_review_approved', human_review_approved,
                'dual_control_approved', dual_control_approved,
                'qualified_policy_accepted', qualified_policy_accepted,
                'policy_decision_ref', policy_decision_ref,
                'high_risk_policy_version', high_risk_policy_version,
                'input_sha256', input_sha256,
                'decision_disposition', decision_disposition,
                'decision_reason_codes', decision_reason_codes,
                'risk_classes', risk_classes,
                'procedural_statuses', procedural_statuses,
                'decision_policy_ref', decision_policy_ref,
                'decision_binding_sha256', decision_binding_sha256,
                'packet_sequence', packet_sequence,
                'supersedes_packet_id', supersedes_packet_id,
                'packet_integrity_sha256', packet_integrity_sha256
            ) ORDER BY packet_sequence)::text, '[]')
            FROM private_high_risk_review_packet
            WHERE record_ref = :'record_ref' AND finding_ref = :'finding_ref';
            """,
            record_ref=record_ref,
            finding_ref=finding_ref,
        )
        rows = json.loads(raw or "[]")
        return tuple(_row_record(row) for row in rows)

    def replay_current_hash_bound(
        self,
        *,
        record_ref: str,
        finding_ref: str,
        current_record_version: str,
        current_source_text_sha256: str,
        current_normalized_text: str,
        privacy_decision_ref: str | None,
        privacy_decision_binding_ref: str | None,
    ) -> HighRiskPacketReplay:
        """Revalidate a reviewed packet when the source body is intentionally unavailable.

        Public projection stores the source occurrence as a SHA-256 binding rather than a
        retained quote body.  This path therefore requires the exact current source hash,
        current normalized text, current Finding record version, and current DP-304 decision
        references to match the integrity-protected packet.  It never upgrades a held packet
        or infers qualified policy; it only reconstructs the already-reviewed decision for the
        DP-310 binding when every persisted input identity is still current.
        """

        clean_record = _required_ref(record_ref, "HIGH_RISK_PACKET_RECORD_REF_INVALID")
        clean_finding = _required_ref(finding_ref, "HIGH_RISK_PACKET_FINDING_REF_INVALID")
        clean_version = _required_ref(
            current_record_version, "HIGH_RISK_PACKET_RECORD_VERSION_INVALID"
        )
        source_hash = str(current_source_text_sha256 or "").lower()
        if not _HEX64_RE.fullmatch(source_hash):
            raise ValueError("HIGH_RISK_PACKET_SOURCE_TEXT_SHA256_INVALID")
        normalized = _required_exact_text(
            current_normalized_text,
            "HIGH_RISK_PACKET_NORMALIZED_TEXT_INVALID",
            limit=200_000,
        )
        normalized_hash = _text_sha256(normalized)
        privacy_ref = _optional_ref(
            privacy_decision_ref, "HIGH_RISK_PACKET_PRIVACY_DECISION_REF_INVALID"
        )
        privacy_binding = _optional_ref(
            privacy_decision_binding_ref,
            "HIGH_RISK_PACKET_PRIVACY_DECISION_BINDING_INVALID",
        )
        if (privacy_ref is None) != (privacy_binding is None):
            raise ValueError("HIGH_RISK_PACKET_PRIVACY_BINDING_INCOMPLETE")

        records = self._load_lineage(record_ref=clean_record, finding_ref=clean_finding)
        if not records:
            empty = evaluate_high_risk_candidate(
                source_text="",
                normalized_text=normalized,
                identity_resolved=False,
                privacy_allows=False,
                official_record_approved=False,
                jurisdiction_match=False,
                effective_time_match=False,
                human_review_approved=False,
                dual_control_approved=False,
                qualified_policy_accepted=False,
            )
            return HighRiskPacketReplay(
                empty,
                None,
                "0" * 64,
                _decision_binding("0" * 64, empty),
                ("HIGH_RISK_PACKET_MISSING",),
            )

        blockers = list(self._lineage_blockers(records))
        latest = records[-1]
        if latest.contract_version != HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION:
            blockers.append("HIGH_RISK_PACKET_CONTRACT_VERSION_STALE")
        if latest.high_risk_policy_version != HIGH_RISK_ASSERTION_VERSION:
            blockers.append("HIGH_RISK_PACKET_POLICY_VERSION_STALE")
        if latest.record_version != clean_version:
            blockers.append("HIGH_RISK_PACKET_RECORD_VERSION_STALE")
        if latest.source_text_sha256 != source_hash:
            blockers.append("HIGH_RISK_PACKET_SOURCE_TEXT_STALE")
        if latest.normalized_text_sha256 != normalized_hash:
            blockers.append("HIGH_RISK_PACKET_NORMALIZED_TEXT_STALE")
        if latest.privacy_decision_ref != privacy_ref:
            blockers.append("HIGH_RISK_PACKET_PRIVACY_DECISION_STALE")
        if latest.privacy_decision_binding_ref != privacy_binding:
            blockers.append("HIGH_RISK_PACKET_PRIVACY_BINDING_STALE")
        if not latest.privacy_allows:
            blockers.append("HIGH_RISK_PACKET_PRIVACY_NOT_ALLOWED")

        try:
            signals = HighRiskSignals(
                risk_classes=tuple(RiskClass(value) for value in latest.risk_classes),
                procedural_statuses=tuple(
                    ProceduralStatus(value) for value in latest.procedural_statuses
                ),
                allegation_framing=latest.source_allegation_framing,
            )
            decision = HighRiskDecision(
                disposition=latest.decision_disposition,
                reason_codes=latest.decision_reason_codes,
                signals=signals,
                policy_decision_ref=latest.decision_policy_ref,
                version=latest.high_risk_policy_version,
            )
        except ValueError:
            blockers.append("HIGH_RISK_PACKET_DECISION_ENUM_INVALID")
            decision = evaluate_high_risk_candidate(
                source_text="",
                normalized_text=normalized,
                identity_resolved=False,
                privacy_allows=False,
                official_record_approved=False,
                jurisdiction_match=False,
                effective_time_match=False,
                human_review_approved=False,
                dual_control_approved=False,
                qualified_policy_accepted=False,
            )

        if _decision_binding(latest.input_sha256, decision) != latest.decision_binding_sha256:
            blockers.append("HIGH_RISK_PACKET_DECISION_BINDING_MISMATCH")
        blockers = list(dict.fromkeys(blockers))
        return HighRiskPacketReplay(
            decision=decision,
            packet_ref=None if blockers else latest.packet_id,
            input_sha256=latest.input_sha256,
            decision_binding_sha256=latest.decision_binding_sha256,
            blockers=tuple(blockers),
        )

    @staticmethod
    def _lineage_blockers(
        records: tuple[HighRiskReviewedPacketRecord, ...],
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        previous: HighRiskReviewedPacketRecord | None = None
        for index, record in enumerate(records, start=1):
            if record.packet_sequence != index:
                blockers.append("HIGH_RISK_PACKET_CHAIN_SEQUENCE_INVALID")
            if not _record_integrity_valid(record):
                blockers.append("HIGH_RISK_PACKET_TAMPERED")
            if previous is None:
                if record.supersedes_packet_id is not None:
                    blockers.append("HIGH_RISK_PACKET_CHAIN_ROOT_INVALID")
            else:
                if record.supersedes_packet_id != previous.packet_id:
                    blockers.append("HIGH_RISK_PACKET_CHAIN_SUPERSESSION_INVALID")
                if (
                    record.record_ref != previous.record_ref
                    or record.finding_ref != previous.finding_ref
                ):
                    blockers.append("HIGH_RISK_PACKET_CHAIN_BINDING_INVALID")
            previous = record
        return tuple(dict.fromkeys(blockers))

    def append_reviewed_packet(
        self,
        *,
        record_ref: str,
        finding_ref: str,
        record_version: str,
        inputs: HighRiskReviewedPacketInput,
        supersedes_packet_id: str | None = None,
    ) -> HighRiskReviewedPacketRecord:
        clean_record_ref = _required_ref(record_ref, "HIGH_RISK_PACKET_RECORD_REF_INVALID")
        clean_finding_ref = _required_ref(finding_ref, "HIGH_RISK_PACKET_FINDING_REF_INVALID")
        clean_record_version = _required_ref(
            record_version, "HIGH_RISK_PACKET_RECORD_VERSION_INVALID"
        )
        material = _input_material(inputs)
        input_digest = _json_sha256(material)
        decision = _evaluate(inputs, material)
        decision_material = _decision_material(decision)
        decision_binding = _decision_binding(input_digest, decision)

        existing = self._load_lineage(
            record_ref=clean_record_ref,
            finding_ref=clean_finding_ref,
        )
        blockers = self._lineage_blockers(existing)
        if blockers:
            raise ValueError(blockers[0])
        if existing:
            latest = existing[-1]
            if supersedes_packet_id is None:
                raise ValueError("HIGH_RISK_PACKET_SUPERSESSION_REQUIRED")
            if supersedes_packet_id != latest.packet_id:
                raise ValueError("HIGH_RISK_PACKET_SUPERSEDES_NOT_LATEST")
            sequence = latest.packet_sequence + 1
        else:
            if supersedes_packet_id is not None:
                raise ValueError("HIGH_RISK_PACKET_SUPERSEDES_MISSING")
            sequence = 1

        base = HighRiskReviewedPacketRecord(
            packet_id="pending",
            contract_version=HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION,
            record_ref=clean_record_ref,
            finding_ref=clean_finding_ref,
            record_version=clean_record_version,
            source_text_sha256=str(material["source_text_sha256"]),
            normalized_text_sha256=str(material["normalized_text_sha256"]),
            source_allegation_framing=bool(material["source_allegation_framing"]),
            normalized_allegation_framing=bool(material["normalized_allegation_framing"]),
            legal_status_claim=bool(material["legal_status_claim"]),
            identity_sensitive=bool(material["identity_sensitive"]),
            sensitive_private=bool(material["sensitive_private"]),
            minor_victim_private_person=bool(material["minor_victim_private_person"]),
            identity_resolved=bool(material["identity_resolved"]),
            privacy_allows=bool(material["privacy_allows"]),
            privacy_decision_ref=material["privacy_decision_ref"],  # type: ignore[arg-type]
            privacy_decision_binding_ref=material["privacy_decision_binding_ref"],  # type: ignore[arg-type]
            official_record_state=str(material["official_record_state"]),
            official_record_ref=material["official_record_ref"],  # type: ignore[arg-type]
            official_record_approved=bool(material["official_record_approved"]),
            jurisdiction_state=str(material["jurisdiction_state"]),
            jurisdiction_ref=material["jurisdiction_ref"],  # type: ignore[arg-type]
            jurisdiction_match=bool(material["jurisdiction_match"]),
            effective_time_state=str(material["effective_time_state"]),
            effective_time_ref=material["effective_time_ref"],  # type: ignore[arg-type]
            effective_time_match=bool(material["effective_time_match"]),
            human_review_actor_ref=material["human_review_actor_ref"],  # type: ignore[arg-type]
            human_review_ref=material["human_review_ref"],  # type: ignore[arg-type]
            human_reviewed_at=material["human_reviewed_at"],  # type: ignore[arg-type]
            human_review_approved=bool(material["human_review_approved"]),
            dual_control_approved=bool(material["dual_control_approved"]),
            qualified_policy_accepted=bool(material["qualified_policy_accepted"]),
            policy_decision_ref=material["policy_decision_ref"],  # type: ignore[arg-type]
            high_risk_policy_version=HIGH_RISK_ASSERTION_VERSION,
            input_sha256=input_digest,
            decision_disposition=str(decision_material["decision_disposition"]),
            decision_reason_codes=tuple(decision.reason_codes),
            risk_classes=tuple(str(value) for value in decision.signals.risk_classes),
            procedural_statuses=tuple(
                str(value) for value in decision.signals.procedural_statuses
            ),
            decision_policy_ref=decision.policy_decision_ref,
            decision_binding_sha256=decision_binding,
            packet_sequence=sequence,
            supersedes_packet_id=supersedes_packet_id,
            packet_integrity_sha256="0" * 64,
        )
        integrity = _json_sha256(_packet_integrity_material(base))
        record = HighRiskReviewedPacketRecord(
            **{
                **base.__dict__,
                "packet_id": f"high-risk-packet:{integrity}",
                "packet_integrity_sha256": integrity,
            }
        )
        self.run(
            """
            INSERT INTO private_high_risk_review_packet (
                packet_id, contract_version, record_ref, finding_ref, record_version,
                source_text_sha256, normalized_text_sha256,
                source_allegation_framing, normalized_allegation_framing,
                legal_status_claim, identity_sensitive, sensitive_private,
                minor_victim_private_person, identity_resolved, privacy_allows,
                privacy_decision_ref, privacy_decision_binding_ref,
                official_record_state, official_record_ref, official_record_approved,
                jurisdiction_state, jurisdiction_ref, jurisdiction_match,
                effective_time_state, effective_time_ref, effective_time_match,
                human_review_actor_ref, human_review_ref, human_reviewed_at_text,
                human_review_approved, dual_control_approved,
                qualified_policy_accepted, policy_decision_ref, high_risk_policy_version,
                input_sha256, decision_disposition, decision_reason_codes, risk_classes,
                procedural_statuses, decision_policy_ref, decision_binding_sha256,
                packet_sequence, supersedes_packet_id, packet_integrity_sha256
            ) VALUES (
                :'packet_id', :'contract_version', :'record_ref', :'finding_ref', :'record_version',
                :'source_text_sha256', :'normalized_text_sha256',
                :'source_allegation_framing'::boolean, :'normalized_allegation_framing'::boolean,
                :'legal_status_claim'::boolean, :'identity_sensitive'::boolean,
                :'sensitive_private'::boolean, :'minor_victim_private_person'::boolean,
                :'identity_resolved'::boolean, :'privacy_allows'::boolean,
                NULLIF(:'privacy_decision_ref',''), NULLIF(:'privacy_decision_binding_ref',''),
                :'official_record_state', NULLIF(:'official_record_ref',''),
                :'official_record_approved'::boolean,
                :'jurisdiction_state', NULLIF(:'jurisdiction_ref',''), :'jurisdiction_match'::boolean,
                :'effective_time_state', NULLIF(:'effective_time_ref',''), :'effective_time_match'::boolean,
                NULLIF(:'human_review_actor_ref',''), NULLIF(:'human_review_ref',''),
                NULLIF(:'human_reviewed_at_text',''), :'human_review_approved'::boolean,
                :'dual_control_approved'::boolean, :'qualified_policy_accepted'::boolean,
                NULLIF(:'policy_decision_ref',''), :'high_risk_policy_version', :'input_sha256',
                :'decision_disposition', :'decision_reason_codes'::jsonb, :'risk_classes'::jsonb,
                :'procedural_statuses'::jsonb, NULLIF(:'decision_policy_ref',''),
                :'decision_binding_sha256', :'packet_sequence'::integer,
                NULLIF(:'supersedes_packet_id',''), :'packet_integrity_sha256'
            );
            """,
            **{
                **record.__dict__,
                "source_allegation_framing": str(record.source_allegation_framing).lower(),
                "normalized_allegation_framing": str(record.normalized_allegation_framing).lower(),
                "legal_status_claim": str(record.legal_status_claim).lower(),
                "identity_sensitive": str(record.identity_sensitive).lower(),
                "sensitive_private": str(record.sensitive_private).lower(),
                "minor_victim_private_person": str(record.minor_victim_private_person).lower(),
                "identity_resolved": str(record.identity_resolved).lower(),
                "privacy_allows": str(record.privacy_allows).lower(),
                "official_record_approved": str(record.official_record_approved).lower(),
                "jurisdiction_match": str(record.jurisdiction_match).lower(),
                "effective_time_match": str(record.effective_time_match).lower(),
                "human_review_approved": str(record.human_review_approved).lower(),
                "dual_control_approved": str(record.dual_control_approved).lower(),
                "qualified_policy_accepted": str(record.qualified_policy_accepted).lower(),
                "privacy_decision_ref": record.privacy_decision_ref or "",
                "privacy_decision_binding_ref": record.privacy_decision_binding_ref or "",
                "official_record_ref": record.official_record_ref or "",
                "jurisdiction_ref": record.jurisdiction_ref or "",
                "effective_time_ref": record.effective_time_ref or "",
                "human_review_actor_ref": record.human_review_actor_ref or "",
                "human_review_ref": record.human_review_ref or "",
                "human_reviewed_at_text": record.human_reviewed_at or "",
                "policy_decision_ref": record.policy_decision_ref or "",
                "decision_policy_ref": record.decision_policy_ref or "",
                "decision_reason_codes": json.dumps(list(record.decision_reason_codes), separators=(",", ":")),
                "risk_classes": json.dumps(list(record.risk_classes), separators=(",", ":")),
                "procedural_statuses": json.dumps(list(record.procedural_statuses), separators=(",", ":")),
                "supersedes_packet_id": record.supersedes_packet_id or "",
            },
        )
        return record

    def replay_current(
        self,
        *,
        record_ref: str,
        finding_ref: str,
        current_record_version: str,
        inputs: HighRiskReviewedPacketInput,
    ) -> HighRiskPacketReplay:
        clean_record_ref = _required_ref(record_ref, "HIGH_RISK_PACKET_RECORD_REF_INVALID")
        clean_finding_ref = _required_ref(finding_ref, "HIGH_RISK_PACKET_FINDING_REF_INVALID")
        clean_record_version = _required_ref(
            current_record_version, "HIGH_RISK_PACKET_RECORD_VERSION_INVALID"
        )
        material = _input_material(inputs)
        input_digest = _json_sha256(material)
        canonical = _evaluate(inputs, material)
        canonical_binding = _decision_binding(input_digest, canonical)
        try:
            records = self._load_lineage(
                record_ref=clean_record_ref,
                finding_ref=clean_finding_ref,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            code = "HIGH_RISK_PACKET_ROW_INVALID"
            return HighRiskPacketReplay(
                _held(canonical, code), None, input_digest, canonical_binding, (code,)
            )
        if not records:
            code = "HIGH_RISK_PACKET_MISSING"
            return HighRiskPacketReplay(
                _held(canonical, code), None, input_digest, canonical_binding, (code,)
            )
        chain_blockers = self._lineage_blockers(records)
        if chain_blockers:
            return HighRiskPacketReplay(
                _held(canonical, chain_blockers[0]),
                None,
                input_digest,
                canonical_binding,
                chain_blockers,
            )
        latest = records[-1]
        if latest.contract_version != HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION:
            code = "HIGH_RISK_PACKET_CONTRACT_STALE"
        elif latest.record_version != clean_record_version:
            code = "HIGH_RISK_PACKET_RECORD_VERSION_STALE"
        elif latest.high_risk_policy_version != HIGH_RISK_ASSERTION_VERSION:
            code = "HIGH_RISK_PACKET_POLICY_VERSION_STALE"
        elif latest.input_sha256 != input_digest:
            code = "HIGH_RISK_PACKET_INPUT_STALE"
        else:
            canonical_material = _decision_material(canonical)
            persisted_material = _decision_material_from_record(latest)
            if persisted_material != canonical_material or latest.decision_binding_sha256 != canonical_binding:
                code = "HIGH_RISK_PACKET_POLICY_REPLAY_MISMATCH"
            else:
                return HighRiskPacketReplay(
                    canonical,
                    latest.packet_id,
                    input_digest,
                    canonical_binding,
                    (),
                )
        return HighRiskPacketReplay(
            _held(canonical, code), None, input_digest, canonical_binding, (code,)
        )


__all__ = [
    "HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION",
    "HighRiskPacketReplay",
    "HighRiskReviewedPacketInput",
    "HighRiskReviewedPacketRecord",
    "HighRiskReviewedPacketStore",
    "high_risk_packet_input_sha256",
]
