from __future__ import annotations

from datetime import date

from .domain_vocabulary import EvaluationOutcome
from .models import ClaimCase, FindingCandidate


def evaluate_case(case: ClaimCase) -> FindingCandidate:
    kind = case.rule["kind"]
    if kind == "numeric_exact":
        return _numeric_exact(case)
    if kind == "historical_minimum":
        return _historical_minimum(case)
    if kind == "historical_peak":
        return _historical_peak(case)
    if kind == "temporal_stance":
        return _temporal_stance(case)
    raise ValueError(f"Unsupported rule kind: {kind}")


def _usable_metric_evidence(case: ClaimCase):
    metric = case.rule["metric"]
    return [
        item
        for item in case.evidence
        if item.fetched and item.metric == metric and item.value is not None
    ]


def _available_by_statement(case: ClaimCase, evidence):
    statement_date = date.fromisoformat(case.statement_date)
    return [
        item
        for item in evidence
        if date.fromisoformat(item.publication_date) <= statement_date
    ]


def _numeric_exact(case: ClaimCase) -> FindingCandidate:
    expected = float(case.rule["value"])
    period = case.rule.get("reference_period")
    tolerance = float(case.rule.get("tolerance", 0.0))
    evidence = [
        item
        for item in _usable_metric_evidence(case)
        if period is None or item.reference_period == period
    ]
    if not evidence:
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.INSUFFICIENT_EVIDENCE,
            "No fetched evidence matches the requested metric/reference period.",
            (),
            False,
            ("NO_MATCHING_EVIDENCE",),
        )
    best = evidence[0]
    if abs(float(best.value) - expected) <= tolerance:
        evaluation_outcome = EvaluationOutcome.SUPPORTED
        rationale = f"Primary evidence reports {best.value} {best.unit or ''} for {best.reference_period}."
    else:
        evaluation_outcome = EvaluationOutcome.FACTUALLY_FALSE
        rationale = (
            f"Claimed value {expected} does not match fetched evidence "
            f"({best.value} {best.unit or ''}, {best.reference_period})."
        )
    return FindingCandidate(
        case.case_id, evaluation_outcome, rationale, (best.evidence_id,), True
    )


def _historical_minimum(case: ClaimCase) -> FindingCandidate:
    claimed = float(case.rule["value"])
    evidence = _available_by_statement(case, _usable_metric_evidence(case))
    if not evidence:
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.INSUFFICIENT_EVIDENCE,
            "No fetched evidence is available to test the historical-minimum claim.",
            (),
            False,
            ("NO_MATCHING_EVIDENCE",),
        )
    lower = [item for item in evidence if float(item.value) < claimed]
    if lower:
        strongest = min(lower, key=lambda item: float(item.value))
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.FACTUALLY_FALSE,
            (
                f"The claim calls {claimed} a historical minimum, but evidence already records "
                f"a lower value ({strongest.value}) in {strongest.reference_period}."
            ),
            tuple(item.evidence_id for item in evidence),
            True,
        )
    return FindingCandidate(
        case.case_id,
        EvaluationOutcome.SUPPORTED,
        f"No lower value than {claimed} is present in the supplied benchmark evidence.",
        tuple(item.evidence_id for item in evidence),
        True,
    )


def _historical_peak(case: ClaimCase) -> FindingCandidate:
    claimed = float(case.rule["value"])
    evidence = _available_by_statement(case, _usable_metric_evidence(case))
    if not evidence:
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.INSUFFICIENT_EVIDENCE,
            "No fetched evidence is available to test the historical-peak claim.",
            (),
            False,
            ("NO_MATCHING_EVIDENCE",),
        )
    higher = [item for item in evidence if float(item.value) > claimed]
    if higher:
        strongest = max(higher, key=lambda item: float(item.value))
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.OUTDATED_DATA,
            (
                f"The claim calls {claimed} the historical peak, but a higher published value "
                f"({strongest.value}) exists for {strongest.reference_period}."
            ),
            tuple(item.evidence_id for item in evidence),
            True,
        )
    return FindingCandidate(
        case.case_id,
        EvaluationOutcome.SUPPORTED,
        f"No higher value than {claimed} is present in the supplied benchmark evidence.",
        tuple(item.evidence_id for item in evidence),
        True,
    )


def _temporal_stance(case: ClaimCase) -> FindingCandidate:
    prior_stance = case.rule.get("prior_stance")
    later_stance = case.rule.get("later_stance")
    same_proposition = bool(case.rule.get("same_proposition", False))
    if not same_proposition or prior_stance is None or later_stance is None:
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.NO_CONTRADICTION_ESTABLISHED,
            (
                "The records are related in topic, but the earlier record does not establish "
                "an opposite stance on the same proposition."
            ),
            tuple(item.evidence_id for item in case.evidence if item.fetched),
            True,
        )
    if prior_stance != later_stance:
        return FindingCandidate(
            case.case_id,
            EvaluationOutcome.FACTUALLY_FALSE,
            "The structured records express opposite stances on the same proposition.",
            tuple(item.evidence_id for item in case.evidence if item.fetched),
            True,
        )
    return FindingCandidate(
        case.case_id,
        EvaluationOutcome.NO_CONTRADICTION_ESTABLISHED,
        "The structured records express the same stance.",
        tuple(item.evidence_id for item in case.evidence if item.fetched),
        True,
    )
