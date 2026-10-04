from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Iterable

from dichiarazioni_pubbliche.domain_vocabulary import (
    VERIFICATION_ASSESSMENT_VERSION,
    VerificationAssessment,
)

VERIFICATION_VERSION = VERIFICATION_ASSESSMENT_VERSION


@dataclass(frozen=True)
class VerificationEvidence:
    evidence_id: str
    publication_date: str
    observation_id: str | None = None
    metric: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reference_period: str | None = None
    suitable: bool = False
    # Legacy transport field retained while old Evidence rows/configs are
    # migrated. It is intentionally ignored by verification semantics.
    authoritative: bool = False
    status: str = "APPROVED"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationRequest:
    claim_id: str
    statement_date: str
    kind: str
    rule: dict[str, Any]
    source_intelligence_status: str | None = None
    source_intelligence_assessment_id: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    claim_id: str
    assessment: VerificationAssessment
    evidence_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    rationale_codes: tuple[str, ...]
    result: dict[str, Any]
    statement_cutoff: str
    verification_version: str = VERIFICATION_VERSION


def deterministic_evidence_observation_id(
    *,
    evidence_id: str,
    observation_type: str,
    metric: str | None,
    value_numeric: float | None,
    value_text: str | None,
    unit: str | None,
    reference_period: str | None,
    dimensions: dict[str, Any],
    extraction_method: str,
    extraction_version: str,
    source_pointer: dict[str, Any],
) -> str:
    payload = {
        "evidence_id": evidence_id,
        "observation_type": observation_type,
        "metric": metric,
        "value_numeric": value_numeric,
        "value_text": value_text,
        "unit": unit,
        "reference_period": reference_period,
        "dimensions": dimensions,
        "extraction_method": extraction_method,
        "extraction_version": extraction_version,
        "source_pointer": source_pointer,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "evidence-observation:" + hashlib.sha256(encoded).hexdigest()


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name}_INVALID") from exc


def _approved(evidence: Iterable[VerificationEvidence]) -> list[VerificationEvidence]:
    return [item for item in evidence if item.status == "APPROVED"]


def _metric_evidence(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> tuple[list[VerificationEvidence], list[VerificationEvidence]]:
    metric = str(request.rule.get("metric") or "").strip()
    if not metric:
        raise ValueError("VERIFICATION_METRIC_REQUIRED")
    period = request.rule.get("reference_period")
    matched = [
        item
        for item in _approved(evidence)
        if item.metric == metric
        and (period is None or item.reference_period == str(period))
    ]
    cutoff = _parse_date(request.statement_date, "STATEMENT_DATE")
    before = [
        item
        for item in matched
        if _parse_date(item.publication_date, "EVIDENCE_PUBLICATION_DATE") <= cutoff
    ]
    after = [item for item in matched if item not in before]
    return before, after


def _numeric_values(
    evidence: Iterable[VerificationEvidence],
) -> list[tuple[VerificationEvidence, float]]:
    output: list[tuple[VerificationEvidence, float]] = []
    for item in evidence:
        if item.value_numeric is not None:
            output.append((item, float(item.value_numeric)))
    return output


def _evidence_ids(
    evidence: Iterable[VerificationEvidence],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.evidence_id for item in evidence))


def _insufficient(
    request: VerificationRequest,
    blocker: str,
    *,
    evidence_ids: tuple[str, ...] = (),
    result: dict[str, Any] | None = None,
) -> VerificationResult:
    return VerificationResult(
        claim_id=request.claim_id,
        assessment=VerificationAssessment.INSUFFICIENT_EVIDENCE,
        evidence_ids=evidence_ids,
        blockers=(blocker,),
        rationale_codes=(blocker,),
        result=result or {},
        statement_cutoff=request.statement_date,
    )


def _source_intelligence_gate(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult | None:
    status = str(request.source_intelligence_status or "").strip()
    evidence_ids = _evidence_ids(item for item in evidence if item.status == "APPROVED")
    if not status:
        return _insufficient(
            request,
            "SOURCE_INTELLIGENCE_ASSESSMENT_REQUIRED",
            evidence_ids=evidence_ids,
        )
    if status == "SUFFICIENT_FOR_RULE":
        return None
    if status == "CONFLICTING_EVIDENCE":
        return VerificationResult(
            claim_id=request.claim_id,
            assessment=VerificationAssessment.UNRESOLVED,
            evidence_ids=evidence_ids,
            blockers=("SOURCE_INTELLIGENCE_CONFLICTING_EVIDENCE",),
            rationale_codes=("SOURCE_INTELLIGENCE_CONFLICTING_EVIDENCE",),
            result={
                "source_intelligence_assessment_id": request.source_intelligence_assessment_id,
                "source_intelligence_status": status,
            },
            statement_cutoff=request.statement_date,
        )
    return _insufficient(
        request,
        f"SOURCE_INTELLIGENCE_{status}",
        evidence_ids=evidence_ids,
        result={
            "source_intelligence_assessment_id": request.source_intelligence_assessment_id,
            "source_intelligence_status": status,
        },
    )


def verify_numeric_exact(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult:
    expected = float(request.rule["value"])
    tolerance = float(request.rule.get("tolerance", 0.0))
    if tolerance < 0:
        raise ValueError("NEGATIVE_TOLERANCE")
    before, after = _metric_evidence(request, evidence)
    numeric = _numeric_values(before)
    if not numeric:
        blocker = (
            "POST_STATEMENT_EVIDENCE_ONLY"
            if _numeric_values(after)
            else "NO_APPROVED_MATCHING_EVIDENCE"
        )
        return _insufficient(request, blocker)
    suitable = [(item, value) for item, value in numeric if item.suitable]
    if not suitable:
        return _insufficient(
            request,
            "NO_SUITABLE_EVIDENCE",
            evidence_ids=_evidence_ids(item for item, _ in numeric),
        )
    distinct = {
        round(value, 12)
        for _, value in suitable
    }
    if len(distinct) > 1:
        return VerificationResult(
            request.claim_id,
            VerificationAssessment.UNRESOLVED,
            _evidence_ids(item for item, _ in suitable),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            {
                "expected": expected,
                "observed_values": sorted(distinct),
                "tolerance": tolerance,
            },
            request.statement_date,
        )
    observed = suitable[0][1]
    assessment = (
        VerificationAssessment.SUPPORTED
        if abs(observed - expected) <= tolerance
        else VerificationAssessment.FACTUALLY_FALSE
    )
    return VerificationResult(
        request.claim_id,
        assessment,
        _evidence_ids(item for item, _ in suitable),
        (),
        (
            "NUMERIC_EXACT_MATCH"
            if assessment == VerificationAssessment.SUPPORTED
            else "NUMERIC_EXACT_MISMATCH"
        ,),
        {
            "expected": expected,
            "observed": observed,
            "tolerance": tolerance,
            "metric": request.rule["metric"],
            "reference_period": request.rule.get("reference_period"),
        },
        request.statement_date,
    )


def verify_numeric_range(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult:
    minimum = request.rule.get("minimum")
    maximum = request.rule.get("maximum")
    if minimum is None and maximum is None:
        raise ValueError("NUMERIC_RANGE_BOUND_REQUIRED")
    before, after = _metric_evidence(request, evidence)
    numeric = _numeric_values(before)
    suitable = [(item, value) for item, value in numeric if item.suitable]
    if not suitable:
        blocker = (
            "POST_STATEMENT_EVIDENCE_ONLY"
            if _numeric_values(after)
            else "NO_SUITABLE_EVIDENCE"
        )
        return _insufficient(request, blocker)
    values = {round(value, 12) for _, value in suitable}
    if len(values) > 1:
        return VerificationResult(
            request.claim_id,
            VerificationAssessment.UNRESOLVED,
            _evidence_ids(item for item, _ in suitable),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            {"observed_values": sorted(values)},
            request.statement_date,
        )
    observed = suitable[0][1]
    within = True
    if minimum is not None:
        within = within and observed >= float(minimum)
    if maximum is not None:
        within = within and observed <= float(maximum)
    return VerificationResult(
        request.claim_id,
        (
            VerificationAssessment.SUPPORTED
            if within
            else VerificationAssessment.FACTUALLY_FALSE
        ),
        _evidence_ids(item for item, _ in suitable),
        (),
        ("NUMERIC_RANGE_MATCH" if within else "NUMERIC_RANGE_MISMATCH",),
        {
            "minimum": minimum,
            "maximum": maximum,
            "observed": observed,
        },
        request.statement_date,
    )


def verify_historical_extreme(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
    *,
    mode: str,
) -> VerificationResult:
    if mode not in {"minimum", "maximum"}:
        raise ValueError("HISTORICAL_EXTREME_MODE_INVALID")
    claimed = float(request.rule["value"])
    before, after = _metric_evidence(request, evidence)
    numeric = [
        (item, value)
        for item, value in _numeric_values(before)
        if item.suitable
    ]
    if not numeric:
        blocker = (
            "POST_STATEMENT_EVIDENCE_ONLY"
            if _numeric_values(after)
            else "NO_AUTHORITATIVE_EVIDENCE"
        )
        return _insufficient(request, blocker)
    counterexamples = [
        (item, value)
        for item, value in numeric
        if (value < claimed if mode == "minimum" else value > claimed)
    ]
    if counterexamples:
        strongest = (
            min(counterexamples, key=lambda pair: pair[1])
            if mode == "minimum"
            else max(counterexamples, key=lambda pair: pair[1])
        )
        return VerificationResult(
            request.claim_id,
            VerificationAssessment.FACTUALLY_FALSE,
            _evidence_ids(item for item, _ in numeric),
            (),
            (
                "HISTORICAL_MINIMUM_COUNTEREXAMPLE"
                if mode == "minimum"
                else "HISTORICAL_MAXIMUM_COUNTEREXAMPLE"
            ,),
            {
                "claimed": claimed,
                "counterexample": strongest[1],
                "counterexample_reference_period": strongest[0].reference_period,
            },
            request.statement_date,
        )

    coverage_complete = bool(request.rule.get("coverage_complete", False))
    explicit_record = any(
        bool(item.metadata.get("explicit_record_attestation"))
        for item, _ in numeric
    )
    if not coverage_complete and not explicit_record:
        return _insufficient(
            request,
            "HISTORICAL_COVERAGE_INCOMPLETE",
            evidence_ids=_evidence_ids(item for item, _ in numeric),
            result={"claimed": claimed, "observations_checked": len(numeric)},
        )
    return VerificationResult(
        request.claim_id,
        VerificationAssessment.SUPPORTED,
        _evidence_ids(item for item, _ in numeric),
        (),
        (
            "HISTORICAL_COVERAGE_COMPLETE"
            if coverage_complete
            else "EXPLICIT_RECORD_ATTESTATION"
        ,),
        {"claimed": claimed, "observations_checked": len(numeric)},
        request.statement_date,
    )


def verify_text_exact(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult:
    expected = str(request.rule.get("value_text") or "").strip()
    metric = str(request.rule.get("metric") or "").strip()
    if not expected or not metric:
        raise ValueError("TEXT_EXACT_RULE_INVALID")
    before, after = _metric_evidence(request, evidence)
    usable = [
        item
        for item in before
        if item.suitable and item.value_text is not None
    ]
    if not usable:
        blocker = (
            "POST_STATEMENT_EVIDENCE_ONLY"
            if any(item.value_text is not None for item in after)
            else "NO_SUITABLE_EVIDENCE"
        )
        return _insufficient(request, blocker)
    observed_values = {str(item.value_text).strip() for item in usable}
    if len(observed_values) > 1:
        return VerificationResult(
            request.claim_id,
            VerificationAssessment.UNRESOLVED,
            _evidence_ids(usable),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            ("CONFLICTING_AUTHORITATIVE_EVIDENCE",),
            {"observed_values": sorted(observed_values)},
            request.statement_date,
        )
    observed = next(iter(observed_values))
    match = observed.casefold() == expected.casefold()
    return VerificationResult(
        request.claim_id,
        (
            VerificationAssessment.SUPPORTED
            if match
            else VerificationAssessment.FACTUALLY_FALSE
        ),
        _evidence_ids(usable),
        (),
        ("TEXT_EXACT_MATCH" if match else "TEXT_EXACT_MISMATCH",),
        {"expected": expected, "observed": observed},
        request.statement_date,
    )


def verify(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult:
    evidence = tuple(evidence)
    gate = _source_intelligence_gate(request, evidence)
    if gate is not None:
        return gate
    if request.kind == "numeric_exact":
        return verify_numeric_exact(request, evidence)
    if request.kind == "numeric_range":
        return verify_numeric_range(request, evidence)
    if request.kind == "historical_minimum":
        return verify_historical_extreme(request, evidence, mode="minimum")
    if request.kind == "historical_peak":
        return verify_historical_extreme(request, evidence, mode="maximum")
    if request.kind in {"legal_status_exact", "text_exact"}:
        return verify_text_exact(request, evidence)
    raise ValueError(f"UNSUPPORTED_VERIFICATION_KIND:{request.kind}")


def verification_input_fingerprint(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> str:
    payload = {
        "request": asdict(request),
        "evidence": [
            asdict(item)
            for item in sorted(
                evidence,
                key=lambda row: (row.evidence_id, row.observation_id or ""),
            )
        ],
        "verification_version": VERIFICATION_VERSION,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def deterministic_verification_run_id(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> str:
    fingerprint = verification_input_fingerprint(request, evidence)
    return "verification:" + hashlib.sha256(
        (request.claim_id + "\0" + VERIFICATION_VERSION + "\0" + fingerprint).encode()
    ).hexdigest()
