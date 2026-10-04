from __future__ import annotations

from .domain_vocabulary import EvaluationOutcome, FindingPublicationStatus
from .models import ClaimCase, FindingCandidate, GateDecision, SourceType


def apply_publication_gate(case: ClaimCase, candidate: FindingCandidate) -> GateDecision:
    reasons: list[str] = []
    fetched = [item for item in case.evidence if item.fetched]

    if case.claim_source_type == SourceType.SYNTHETIC:
        reasons.append("SYNTHETIC_BENCHMARK_CASE")
    if not fetched:
        reasons.append("NO_FETCHED_EVIDENCE")
    if candidate.blockers:
        reasons.extend(candidate.blockers)
    if not candidate.material_assertions_supported:
        reasons.append("ASSERTION_WITHOUT_EVIDENCE")

    if candidate.evaluation_outcome in {
        EvaluationOutcome.SUPPORTED,
        EvaluationOutcome.FACTUALLY_FALSE,
        EvaluationOutcome.OUTDATED_DATA,
    }:
        if not any(item.source_type == SourceType.PRIMARY_OFFICIAL for item in fetched):
            reasons.append("NO_PRIMARY_OFFICIAL_EVIDENCE")

    if candidate.evaluation_outcome == EvaluationOutcome.NO_CONTRADICTION_ESTABLISHED:
        return GateDecision(
            case.case_id,
            FindingPublicationStatus.NO_FINDING,
            candidate.evaluation_outcome,
            ("NO_MATERIAL_CONTRADICTION",),
            candidate.rationale,
        )

    if candidate.evaluation_outcome == EvaluationOutcome.INSUFFICIENT_EVIDENCE:
        return GateDecision(
            case.case_id,
            FindingPublicationStatus.NEEDS_MORE_EVIDENCE,
            candidate.evaluation_outcome,
            tuple(reasons or ["INSUFFICIENT_EVIDENCE"]),
            candidate.rationale,
        )

    if reasons:
        return GateDecision(
            case.case_id,
            FindingPublicationStatus.POLICY_HOLD,
            candidate.evaluation_outcome,
            tuple(dict.fromkeys(reasons)),
            candidate.rationale,
        )

    return GateDecision(
        case.case_id,
        FindingPublicationStatus.PUBLISH,
        candidate.evaluation_outcome,
        ("GATE_PASSED",),
        candidate.rationale,
    )
