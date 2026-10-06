from __future__ import annotations

import hashlib
import json
import math
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


def _numeric_input(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
    *,
    metric: str,
    reference_period: str | None,
    required_dimensions: dict[str, Any] | None = None,
) -> tuple[str, VerificationEvidence | None, float | None, tuple[str, ...], str | None]:
    cutoff = _parse_date(request.statement_date, "STATEMENT_DATE")
    matched = [
        item
        for item in _approved(evidence)
        if item.metric == metric
        and item.value_numeric is not None
        and (reference_period is None or item.reference_period == reference_period)
    ]
    if required_dimensions:
        dimension_matched = [
            item
            for item in matched
            if isinstance(item.metadata.get("dimensions"), dict)
            and all(
                item.metadata["dimensions"].get(key) == value
                for key, value in required_dimensions.items()
            )
        ]
        if not dimension_matched:
            return (
                "INSUFFICIENT",
                None,
                None,
                _evidence_ids(matched),
                "NUMERIC_DIMENSION_MISMATCH",
            )
        matched = dimension_matched
    before = [
        item
        for item in matched
        if _parse_date(item.publication_date, "EVIDENCE_PUBLICATION_DATE") <= cutoff
    ]
    if not before:
        reason = "POST_STATEMENT_EVIDENCE_ONLY" if matched else "NO_APPROVED_MATCHING_EVIDENCE"
        return "INSUFFICIENT", None, None, _evidence_ids(matched), reason
    suitable = [item for item in before if item.suitable]
    if not suitable:
        return "INSUFFICIENT", None, None, _evidence_ids(before), "NO_SUITABLE_EVIDENCE"
    distinct = {
        (round(float(item.value_numeric), 12), str(item.unit or ""))
        for item in suitable
    }
    if len(distinct) != 1:
        return "CONFLICT", None, None, _evidence_ids(suitable), "CONFLICTING_NUMERIC_INPUT"
    selected = sorted(suitable, key=lambda item: (item.evidence_id, item.observation_id or ""))[0]
    return "OK", selected, float(selected.value_numeric), _evidence_ids(suitable), None


def _numeric_pair_inputs(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
    *,
    left_metric: str,
    right_metric: str,
    left_reference_period: str | None,
    right_reference_period: str | None,
    left_dimensions: dict[str, Any] | None = None,
    right_dimensions: dict[str, Any] | None = None,
) -> tuple[
    VerificationEvidence | None,
    float | None,
    VerificationEvidence | None,
    float | None,
    VerificationResult | None,
]:
    left_state, left_item, left_value, left_ids, left_reason = _numeric_input(
        request,
        evidence,
        metric=left_metric,
        reference_period=left_reference_period,
        required_dimensions=left_dimensions,
    )
    right_state, right_item, right_value, right_ids, right_reason = _numeric_input(
        request,
        evidence,
        metric=right_metric,
        reference_period=right_reference_period,
        required_dimensions=right_dimensions,
    )
    combined_ids = tuple(dict.fromkeys((*left_ids, *right_ids)))
    if left_state == "CONFLICT" or right_state == "CONFLICT":
        return None, None, None, None, VerificationResult(
            request.claim_id,
            VerificationAssessment.UNRESOLVED,
            combined_ids,
            tuple(
                reason
                for reason in (left_reason, right_reason)
                if reason is not None
            ),
            tuple(
                reason
                for reason in (left_reason, right_reason)
                if reason is not None
            ),
            {},
            request.statement_date,
        )
    if left_state != "OK" or right_state != "OK":
        reasons = tuple(
            dict.fromkeys(
                reason
                for reason in (left_reason, right_reason)
                if reason is not None
            )
        )
        blocker = reasons[0] if reasons else "NUMERIC_PAIR_INPUT_REQUIRED"
        return None, None, None, None, _insufficient(
            request,
            blocker,
            evidence_ids=combined_ids,
            result={"input_blockers": list(reasons)},
        )
    return left_item, left_value, right_item, right_value, None


def _rounded_numeric_pair(
    request: VerificationRequest,
    *,
    observed: float,
    expected: float,
) -> tuple[float, float, dict[str, Any] | None]:
    policy = request.rule.get("rounding")
    if policy is None:
        return observed, expected, None
    if not isinstance(policy, dict):
        raise ValueError("NUMERIC_ROUNDING_POLICY_INVALID")
    mode = str(policy.get("mode") or "").strip().upper()
    if mode == "DECIMAL_PLACES":
        places = policy.get("places")
        if not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 12:
            raise ValueError("NUMERIC_ROUNDING_PLACES_INVALID")
        return (
            round(observed, places),
            round(expected, places),
            {"mode": mode, "places": places},
        )
    if mode == "SIGNIFICANT_FIGURES":
        digits = policy.get("digits")
        if not isinstance(digits, int) or isinstance(digits, bool) or not 1 <= digits <= 15:
            raise ValueError("NUMERIC_SIGNIFICANT_FIGURES_INVALID")

        def significant(value: float) -> float:
            if value == 0:
                return 0.0
            places = digits - 1 - int(math.floor(math.log10(abs(value))))
            return round(value, places)

        return (
            significant(observed),
            significant(expected),
            {"mode": mode, "digits": digits},
        )
    raise ValueError("NUMERIC_ROUNDING_MODE_INVALID")


def _normalize_comparable_units(
    request: VerificationRequest,
    left: VerificationEvidence,
    left_value: float,
    right: VerificationEvidence,
    right_value: float,
) -> tuple[
    float | None,
    float | None,
    str | None,
    dict[str, Any] | None,
    VerificationResult | None,
]:
    left_unit = str(left.unit or "").strip()
    right_unit = str(right.unit or "").strip()
    if left_unit == right_unit:
        return left_value, right_value, left.unit or right.unit, None, None

    policy = request.rule.get("unit_conversion")
    if policy is None:
        return None, None, None, None, _insufficient(
            request,
            "NUMERIC_UNIT_MISMATCH",
            evidence_ids=_evidence_ids((left, right)),
            result={"left_unit": left.unit, "right_unit": right.unit},
        )
    if not isinstance(policy, dict):
        return None, None, None, None, _insufficient(
            request,
            "NUMERIC_UNIT_CONVERSION_POLICY_INVALID",
            evidence_ids=_evidence_ids((left, right)),
        )

    target_unit = str(policy.get("target_unit") or "").strip()
    factors = policy.get("factor_to_target")
    if not target_unit or not isinstance(factors, dict):
        return None, None, None, None, _insufficient(
            request,
            "NUMERIC_UNIT_CONVERSION_POLICY_INVALID",
            evidence_ids=_evidence_ids((left, right)),
        )

    converted: list[tuple[str, float]] = []
    for unit, value in ((left_unit, left_value), (right_unit, right_value)):
        raw_factor = factors.get(unit)
        try:
            factor = float(raw_factor)
        except (TypeError, ValueError):
            return None, None, None, None, _insufficient(
                request,
                "NUMERIC_UNIT_CONVERSION_UNAVAILABLE",
                evidence_ids=_evidence_ids((left, right)),
                result={
                    "left_unit": left.unit,
                    "right_unit": right.unit,
                    "target_unit": target_unit,
                },
            )
        if factor <= 0 or not math.isfinite(factor):
            return None, None, None, None, _insufficient(
                request,
                "NUMERIC_UNIT_CONVERSION_POLICY_INVALID",
                evidence_ids=_evidence_ids((left, right)),
            )
        converted.append((unit, value * factor))

    conversion = {
        "target_unit": target_unit,
        "left_unit": left.unit,
        "right_unit": right.unit,
        "left_factor": float(factors[left_unit]),
        "right_factor": float(factors[right_unit]),
    }
    return converted[0][1], converted[1][1], target_unit, conversion, None


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


def verify_numeric_delta(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
) -> VerificationResult:
    left_metric = str(request.rule.get("left_metric") or "").strip()
    right_metric = str(request.rule.get("right_metric") or "").strip()
    if not left_metric or not right_metric:
        raise ValueError("NUMERIC_DELTA_METRICS_REQUIRED")
    left, left_value, right, right_value, blocked = _numeric_pair_inputs(
        request,
        evidence,
        left_metric=left_metric,
        right_metric=right_metric,
        left_reference_period=(
            str(request.rule["left_reference_period"])
            if request.rule.get("left_reference_period") is not None
            else None
        ),
        right_reference_period=(
            str(request.rule["right_reference_period"])
            if request.rule.get("right_reference_period") is not None
            else None
        ),
        left_dimensions=(
            dict(request.rule["left_dimensions"])
            if isinstance(request.rule.get("left_dimensions"), dict)
            else None
        ),
        right_dimensions=(
            dict(request.rule["right_dimensions"])
            if isinstance(request.rule.get("right_dimensions"), dict)
            else None
        ),
    )
    if blocked is not None:
        return blocked
    assert left is not None and right is not None
    assert left_value is not None and right_value is not None
    left_value, right_value, output_unit, conversion, blocked = _normalize_comparable_units(
        request,
        left,
        left_value,
        right,
        right_value,
    )
    if blocked is not None:
        return blocked
    assert left_value is not None and right_value is not None
    expected = float(request.rule["value"])
    tolerance = float(request.rule.get("tolerance", 0.0))
    if tolerance < 0:
        raise ValueError("NEGATIVE_TOLERANCE")
    observed = left_value - right_value
    observed_for_compare, expected_for_compare, rounding = _rounded_numeric_pair(
        request,
        observed=observed,
        expected=expected,
    )
    assessment = (
        VerificationAssessment.SUPPORTED
        if abs(observed_for_compare - expected_for_compare) <= tolerance
        else VerificationAssessment.FACTUALLY_FALSE
    )
    result = {
        "expected": expected,
        "observed": observed,
        "tolerance": tolerance,
        "left_metric": left_metric,
        "right_metric": right_metric,
        "unit": output_unit,
    }
    if rounding is not None:
        result["rounding"] = rounding
        result["observed_compared"] = observed_for_compare
        result["expected_compared"] = expected_for_compare
    if conversion is not None:
        result["unit_conversion"] = conversion
    return VerificationResult(
        request.claim_id,
        assessment,
        _evidence_ids((left, right)),
        (),
        ("NUMERIC_DELTA_MATCH" if assessment == VerificationAssessment.SUPPORTED else "NUMERIC_DELTA_MISMATCH",),
        result,
        request.statement_date,
    )


def verify_numeric_ratio(
    request: VerificationRequest,
    evidence: Iterable[VerificationEvidence],
    *,
    percent_change: bool = False,
) -> VerificationResult:
    if percent_change:
        left_metric = str(request.rule.get("current_metric") or "").strip()
        right_metric = str(request.rule.get("baseline_metric") or "").strip()
        left_period_key = "current_reference_period"
        right_period_key = "baseline_reference_period"
    else:
        left_metric = str(request.rule.get("numerator_metric") or "").strip()
        right_metric = str(request.rule.get("denominator_metric") or "").strip()
        left_period_key = "numerator_reference_period"
        right_period_key = "denominator_reference_period"
    if not left_metric or not right_metric:
        raise ValueError("NUMERIC_RATIO_METRICS_REQUIRED")
    left, left_value, right, right_value, blocked = _numeric_pair_inputs(
        request,
        evidence,
        left_metric=left_metric,
        right_metric=right_metric,
        left_reference_period=(
            str(request.rule[left_period_key])
            if request.rule.get(left_period_key) is not None
            else None
        ),
        right_reference_period=(
            str(request.rule[right_period_key])
            if request.rule.get(right_period_key) is not None
            else None
        ),
        left_dimensions=(
            dict(request.rule["current_dimensions"])
            if percent_change and isinstance(request.rule.get("current_dimensions"), dict)
            else dict(request.rule["numerator_dimensions"])
            if not percent_change and isinstance(request.rule.get("numerator_dimensions"), dict)
            else None
        ),
        right_dimensions=(
            dict(request.rule["baseline_dimensions"])
            if percent_change and isinstance(request.rule.get("baseline_dimensions"), dict)
            else dict(request.rule["denominator_dimensions"])
            if not percent_change and isinstance(request.rule.get("denominator_dimensions"), dict)
            else None
        ),
    )
    if blocked is not None:
        return blocked
    assert left is not None and right is not None
    assert left_value is not None and right_value is not None
    if right_value == 0:
        return _insufficient(
            request,
            "NUMERIC_DENOMINATOR_ZERO",
            evidence_ids=_evidence_ids((left, right)),
        )
    conversion = None
    if percent_change:
        left_value, right_value, _output_unit, conversion, blocked = _normalize_comparable_units(
            request,
            left,
            left_value,
            right,
            right_value,
        )
        if blocked is not None:
            return blocked
        assert left_value is not None and right_value is not None
        if right_value == 0:
            return _insufficient(
                request,
                "NUMERIC_DENOMINATOR_ZERO",
                evidence_ids=_evidence_ids((left, right)),
            )
    expected = float(request.rule["value"])
    tolerance = float(request.rule.get("tolerance", 0.0))
    if tolerance < 0:
        raise ValueError("NEGATIVE_TOLERANCE")
    scale = 100.0 if percent_change else float(request.rule.get("scale", 1.0))
    if not percent_change and scale <= 0:
        raise ValueError("NUMERIC_RATIO_SCALE_INVALID")
    observed = (
        ((left_value - right_value) / right_value) * 100.0
        if percent_change
        else (left_value / right_value) * scale
    )
    observed_for_compare, expected_for_compare, rounding = _rounded_numeric_pair(
        request,
        observed=observed,
        expected=expected,
    )
    assessment = (
        VerificationAssessment.SUPPORTED
        if abs(observed_for_compare - expected_for_compare) <= tolerance
        else VerificationAssessment.FACTUALLY_FALSE
    )
    code = "NUMERIC_PERCENT_CHANGE" if percent_change else "NUMERIC_RATIO"
    result = {
        "expected": expected,
        "observed": observed,
        "tolerance": tolerance,
        "left_metric": left_metric,
        "right_metric": right_metric,
        "scale": scale,
    }
    if rounding is not None:
        result["rounding"] = rounding
        result["observed_compared"] = observed_for_compare
        result["expected_compared"] = expected_for_compare
    if conversion is not None:
        result["unit_conversion"] = conversion
    return VerificationResult(
        request.claim_id,
        assessment,
        _evidence_ids((left, right)),
        (),
        (f"{code}_MATCH" if assessment == VerificationAssessment.SUPPORTED else f"{code}_MISMATCH",),
        result,
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
    if request.kind == "numeric_delta":
        return verify_numeric_delta(request, evidence)
    if request.kind == "numeric_ratio":
        return verify_numeric_ratio(request, evidence)
    if request.kind == "numeric_percent_change":
        return verify_numeric_ratio(request, evidence, percent_change=True)
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
