from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


HIGH_RISK_ASSERTION_VERSION = "high-risk-assertion-v1"


class RiskClass(StrEnum):
    LEGAL_STATUS = "LEGAL_STATUS"
    SERIOUS_WRONGDOING_ALLEGATION = "SERIOUS_WRONGDOING_ALLEGATION"
    IDENTITY_SENSITIVE_ACCUSATION = "IDENTITY_SENSITIVE_ACCUSATION"
    SENSITIVE_PRIVATE = "SENSITIVE_PRIVATE"
    MINOR_VICTIM_PRIVATE_PERSON = "MINOR_VICTIM_PRIVATE_PERSON"


class ProceduralStatus(StrEnum):
    INVESTIGATED = "INVESTIGATED"
    CHARGED = "CHARGED"
    PROSECUTED = "PROSECUTED"
    CONVICTED = "CONVICTED"
    ACQUITTED = "ACQUITTED"
    DISMISSED = "DISMISSED"


_PROCEDURAL_PATTERNS = {
    ProceduralStatus.INVESTIGATED: re.compile(r"\b(?:indagat[oa]|investigat[eo]d?)\b", re.I),
    ProceduralStatus.CHARGED: re.compile(r"\b(?:imputat[oa]|charged|accused)\b", re.I),
    ProceduralStatus.PROSECUTED: re.compile(r"\b(?:processat[oa]|prosecuted|prosecution)\b", re.I),
    ProceduralStatus.CONVICTED: re.compile(r"\b(?:condannat[oa]|convicted)\b", re.I),
    ProceduralStatus.ACQUITTED: re.compile(r"\b(?:assolt[oa]|acquitted)\b", re.I),
    ProceduralStatus.DISMISSED: re.compile(r"\b(?:archiviat[oa]|dismissed)\b", re.I),
}
_ALLEGATION = re.compile(
    r"\b(?:allega|allegano|accusa|accusano|sostiene|sostengono|secondo|"
    r"alleges?|accuses?|according\s+to|reportedly)\b",
    re.I,
)
_SERIOUS_WRONGDOING = re.compile(
    r"\b(?:omicidio|corruzione|frode|violenza|abuso|criminale|reato|"
    r"murder|corruption|fraud|violence|abuse|crime)\b",
    re.I,
)


@dataclass(frozen=True)
class HighRiskSignals:
    risk_classes: tuple[RiskClass, ...]
    procedural_statuses: tuple[ProceduralStatus, ...]
    allegation_framing: bool
    version: str = HIGH_RISK_ASSERTION_VERSION

    @property
    def requires_escalation(self) -> bool:
        return bool(self.risk_classes or self.procedural_statuses)


@dataclass(frozen=True)
class HighRiskDecision:
    disposition: str
    reason_codes: tuple[str, ...]
    signals: HighRiskSignals
    policy_decision_ref: str | None
    version: str = HIGH_RISK_ASSERTION_VERSION

    @property
    def publication_allowed(self) -> bool:
        return self.disposition == "ELIGIBLE_HIGH_RISK"


def classify_high_risk(
    *,
    source_text: str,
    normalized_text: str,
    legal_status_claim: bool = False,
    identity_sensitive: bool = False,
    sensitive_private: bool = False,
    minor_victim_private_person: bool = False,
) -> HighRiskSignals:
    source = str(source_text or "")
    normalized = str(normalized_text or "")
    combined = f"{source}\n{normalized}"
    statuses = tuple(
        status for status, pattern in _PROCEDURAL_PATTERNS.items() if pattern.search(combined)
    )
    classes: list[RiskClass] = []
    if legal_status_claim or statuses:
        classes.append(RiskClass.LEGAL_STATUS)
    if _SERIOUS_WRONGDOING.search(combined):
        classes.append(RiskClass.SERIOUS_WRONGDOING_ALLEGATION)
    if identity_sensitive:
        classes.append(RiskClass.IDENTITY_SENSITIVE_ACCUSATION)
    if sensitive_private:
        classes.append(RiskClass.SENSITIVE_PRIVATE)
    if minor_victim_private_person:
        classes.append(RiskClass.MINOR_VICTIM_PRIVATE_PERSON)
    return HighRiskSignals(
        risk_classes=tuple(dict.fromkeys(classes)),
        procedural_statuses=statuses,
        allegation_framing=bool(_ALLEGATION.search(source)),
    )


def evaluate_high_risk_candidate(
    *,
    source_text: str,
    normalized_text: str,
    legal_status_claim: bool = False,
    identity_sensitive: bool = False,
    sensitive_private: bool = False,
    minor_victim_private_person: bool = False,
    identity_resolved: bool,
    privacy_allows: bool,
    official_record_approved: bool,
    jurisdiction_match: bool,
    effective_time_match: bool,
    human_review_approved: bool,
    dual_control_approved: bool,
    qualified_policy_accepted: bool,
    policy_decision_ref: str | None = None,
) -> HighRiskDecision:
    signals = classify_high_risk(
        source_text=source_text,
        normalized_text=normalized_text,
        legal_status_claim=legal_status_claim,
        identity_sensitive=identity_sensitive,
        sensitive_private=sensitive_private,
        minor_victim_private_person=minor_victim_private_person,
    )
    if not signals.requires_escalation:
        return HighRiskDecision(
            disposition="STANDARD_REVIEW",
            reason_codes=("NO_HIGH_RISK_SIGNAL_DETECTED_NOT_A_SAFETY_CERTIFICATION",),
            signals=signals,
            policy_decision_ref=None,
        )

    reasons: list[str] = []
    if not identity_resolved:
        reasons.append("HOLD_HIGH_RISK_IDENTITY_UNRESOLVED")
    if not privacy_allows:
        reasons.append("HOLD_HIGH_RISK_PRIVACY")
    if RiskClass.LEGAL_STATUS in signals.risk_classes:
        if len(signals.procedural_statuses) > 1:
            reasons.append("HOLD_HIGH_RISK_PROCEDURAL_STATUS_CONFLICT")
        if not official_record_approved:
            reasons.append("HOLD_HIGH_RISK_OFFICIAL_RECORD_REQUIRED")
        if not jurisdiction_match:
            reasons.append("HOLD_HIGH_RISK_JURISDICTION_MISMATCH")
        if not effective_time_match:
            reasons.append("HOLD_HIGH_RISK_EFFECTIVE_TIME_MISMATCH")
    if signals.allegation_framing and not _ALLEGATION.search(normalized_text):
        reasons.append("HOLD_HIGH_RISK_ALLEGATION_FRAMING_LOST")
    if not qualified_policy_accepted or not str(policy_decision_ref or "").strip():
        reasons.append("HOLD_HIGH_RISK_QUALIFIED_POLICY_REQUIRED")
    if not human_review_approved:
        reasons.append("HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED")
    if not dual_control_approved:
        reasons.append("HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED")
    if reasons:
        return HighRiskDecision(
            disposition="HOLD_HIGH_RISK",
            reason_codes=tuple(dict.fromkeys(reasons)),
            signals=signals,
            policy_decision_ref=(
                str(policy_decision_ref).strip()
                if policy_decision_ref is not None and str(policy_decision_ref).strip()
                else None
            ),
        )
    return HighRiskDecision(
        disposition="ELIGIBLE_HIGH_RISK",
        reason_codes=("ALL_ACCEPTED_HIGH_RISK_GATES_PASS",),
        signals=signals,
        policy_decision_ref=str(policy_decision_ref).strip(),
    )


__all__ = [
    "HIGH_RISK_ASSERTION_VERSION",
    "HighRiskDecision",
    "HighRiskSignals",
    "ProceduralStatus",
    "RiskClass",
    "classify_high_risk",
    "evaluate_high_risk_candidate",
]
