from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from dichiarazioni_pubbliche.domain_vocabulary import (
    EvaluationOutcome,
    FindingPublicationStatus,
)


class SourceType(StrEnum):
    PRIMARY_OFFICIAL = "PRIMARY_OFFICIAL"
    PRIMARY_STATEMENT = "PRIMARY_STATEMENT"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    FACT_CHECK = "FACT_CHECK"
    SYNTHETIC = "SYNTHETIC"


@dataclass(frozen=True)
class EvidenceReceipt:
    evidence_id: str
    source_url: str
    publisher: str
    source_type: SourceType
    publication_date: str
    observed_at: str
    reference_period: str | None = None
    metric: str | None = None
    value: float | None = None
    unit: str | None = None
    independence_group: str = ""
    fetched: bool = True
    quote_or_fact: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimCase:
    case_id: str
    subject: str
    statement_date: str
    claim_text: str
    claim_source_url: str
    claim_source_type: SourceType
    rule: dict[str, Any]
    evidence: tuple[EvidenceReceipt, ...]
    expected_evaluation_outcome: EvaluationOutcome
    expected_publication: FindingPublicationStatus
    notes: str = ""


@dataclass(frozen=True)
class FindingCandidate:
    case_id: str
    evaluation_outcome: EvaluationOutcome
    rationale: str
    evidence_ids: tuple[str, ...]
    material_assertions_supported: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    case_id: str
    publication: FindingPublicationStatus
    evaluation_outcome: EvaluationOutcome
    reason_codes: tuple[str, ...]
    rationale: str
