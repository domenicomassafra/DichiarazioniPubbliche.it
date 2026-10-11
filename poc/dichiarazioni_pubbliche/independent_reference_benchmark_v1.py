"""DP-321: offline, SOURCE-ONLY reference metadata and error-rate contract.

No gold corpus is bundled. Neither a hash, an annotator ID nor a supplied
``external_attestation_check`` callback proves independent evidence by itself.
The callback is an integration seam for a *future separately trusted* verifier;
even when it accepts every case, this module reports CONTRACT_ONLY and NEVER
grants release or publication authority. Synthetic fixtures are not real gold.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Callable


VERSION = "independent-reference-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TAG = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,48}$")
_LANG = re.compile(r"^(?:[a-z]{2,3}|und)(?:-[A-Za-z0-9]{2,8})*$")
_SPLITS = frozenset({"CALIBRATION", "HOLDOUT"})
_SOURCES = frozenset({"WRITTEN", "AUDIO", "OCR"})
_CLAIMS = frozenset({"FACTUAL", "OPINION"})
_RIGHTS = frozenset({"CLEARED", "REVOKED", "DENIED", "UNKNOWN", "EXPIRED"})
_STATES = frozenset({"PUBLIC", "HELD", "ABSTAIN"})
_VERDICTS = frozenset({"SUPPORTED", "REFUTED", "INSUFFICIENT", "NOT_APPLICABLE"})
_DENIALS = frozenset({"CONFIRMED", "DENIED", "UNRESOLVED", "NOT_APPLICABLE"})
_METRICS = (
    "false_person",
    "false_quote",
    "false_endorsement",
    "false_factual_verdict",
    "false_denial",
    "rights_privacy_leak",
    "unsupported_publication",
    "abstention",
    "sample_coverage",
    "eligible_recall",
    "conditional_publishability",
)
_MAX_CASES = 256
_MAX_PREDICTIONS = 256


def _need(value: object, key: str, *, limit: int = 200) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > limit
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"DP321_{key}_INVALID")
    return value


def _digest(value: object, key: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError(f"DP321_{key}_HASH_INVALID")
    return value


def _money(value: object) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value < 0
        or value > Decimal("1000")
    ):
        raise ValueError("DP321_COST_INVALID")
    return value


@dataclass(frozen=True)
class ReferenceProof:
    """References to independently sourced proof; these are NOT signed receipts."""

    independent_source_receipt_sha256: str
    independent_adjudication_sha256: str
    adjudication_state: str  # FINAL | ABSTENTION_SCOPE_ONLY
    annotator_ids: tuple[str, ...]
    adjudicator_id: str
    verifier_receipt_id: str  # future external attestation lookup handle


@dataclass(frozen=True)
class ReferenceLabel:
    kind: str  # DECIDABLE | ABSTENTION_ONLY
    publication_allowed: bool
    person_id: str | None
    exact_quote_sha256: str | None
    endorsed: bool | None
    factual_verdict: str | None
    denial_relation: str | None
    # Explicit independent reference finding, NOT inferred from a mere risk tag.
    privacy_sensitive: bool | None = None


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    lineage_id: str
    split: str
    language: str
    source_type: str
    claim_type: str
    risk_tags: tuple[str, ...]
    source_role: str
    ambiguity: str
    source_version_sha256: str
    locator_type: str
    locator_start: int
    locator_end: int
    locator_sha256: str
    original_quote_sha256: str
    rights_state: str
    rights_receipt_sha256: str
    license_ref: str
    reference_version: str
    proof: ReferenceProof
    label: ReferenceLabel


@dataclass(frozen=True)
class ReferenceManifest:
    manifest_id: str
    schema_version: str
    corpus_sha256: str
    split_lock_sha256: str
    rights_policy_version: str
    generator_id: str
    evaluated_model_id: str
    holdout_blind: bool
    cases: tuple[ReferenceCase, ...]
    manifest_sha256: str


@dataclass(frozen=True)
class ReferencePrediction:
    case_id: str
    state: str
    person_id: str | None
    quote_sha256: str | None
    endorsed: bool | None
    factual_verdict: str | None
    denial_relation: str | None
    claimed_rights_clearance: bool
    latency_ms: int | None
    cost_usd: Decimal | None
    run_model_version: str
    source_version_sha256: str


@dataclass(frozen=True)
class MetricCount:
    numerator: int
    denominator: int
    rate: float | None
    ci95_lower: float | None
    ci95_upper: float | None


@dataclass(frozen=True)
class IndependentReferenceReport:
    status: str
    manifest_sha256: str
    report_sha256: str
    evaluated_model_id: str
    case_count: int
    reference_eligible_cases: int
    unverified_reference_cases: int
    missing_predictions: int
    metrics: dict[str, MetricCount]
    strata: dict[str, dict[str, MetricCount]]
    cost_total_usd: Decimal
    cost_observed_count: int
    latency_total_ms: int
    latency_observed_count: int
    drift_comparable_to: str | None = None
    release_eligible: bool = False
    publication_authority: bool = False
    admitted_case_ids_sha256: str | None = None  # legacy reports lack this scope proof

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cost_total_usd"] = str(self.cost_total_usd)
        return data


@dataclass(frozen=True)
class ReferenceDrift:
    status: str
    baseline_report_sha256: str
    current_report_sha256: str
    metric_rate_deltas: dict[str, float | None]
    owner_thresholds_accepted: bool = False
    release_eligible: bool = False


def benchmark_manifest_hash(manifest: ReferenceManifest) -> str:
    """Tamper *detection* of the in-memory metadata, NOT external authenticity."""
    if not isinstance(manifest, ReferenceManifest):
        raise ValueError("DP321_MANIFEST_INVALID")
    obj = asdict(manifest)
    obj.pop("manifest_sha256", None)
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _validate_proof(
    proof: ReferenceProof, manifest: ReferenceManifest, label: ReferenceLabel
) -> None:
    if not isinstance(proof, ReferenceProof):
        raise ValueError("DP321_PROOF_INVALID")
    _digest(proof.independent_source_receipt_sha256, "SOURCE_RECEIPT")
    _digest(proof.independent_adjudication_sha256, "ADJUDICATION")
    _need(proof.verifier_receipt_id, "VERIFIER_REF")
    if proof.adjudication_state not in {"FINAL", "ABSTENTION_SCOPE_ONLY"}:
        raise ValueError("DP321_ADJUDICATION_STATUS_INVALID")
    if (label.kind == "DECIDABLE") != (proof.adjudication_state == "FINAL"):
        raise ValueError("DP321_ADJUDICATION_LABEL_MISMATCH")
    if (
        not isinstance(proof.annotator_ids, tuple)
        or len(proof.annotator_ids) < 2
        or len(proof.annotator_ids) > 4
    ):
        raise ValueError("DP321_ANNOTATORS_INSUFFICIENT")
    ids = [*proof.annotator_ids, proof.adjudicator_id]
    for identifier in ids:
        _need(identifier, "ANNOTATOR")
    if (
        len(set(ids)) != len(ids)
        or manifest.generator_id in ids
        or manifest.evaluated_model_id in ids
    ):
        raise ValueError("DP321_INDEPENDENCE_CONFLICT")


def _validate_case(case: ReferenceCase, manifest: ReferenceManifest) -> None:
    if not isinstance(case, ReferenceCase):
        raise ValueError("DP321_CASE_INVALID")
    for key in (
        "case_id",
        "lineage_id",
        "source_role",
        "license_ref",
        "reference_version",
    ):
        _need(getattr(case, key), key.upper())
    if (
        case.split not in _SPLITS
        or case.source_type not in _SOURCES
        or case.claim_type not in _CLAIMS
        or case.rights_state not in _RIGHTS
        or case.ambiguity not in {"DECIDABLE", "CONTESTED"}
    ):
        raise ValueError("DP321_CASE_STRATIFICATION_INVALID")
    if not isinstance(case.language, str) or not _LANG.fullmatch(case.language):
        raise ValueError("DP321_LANGUAGE_INVALID")
    if (
        not isinstance(case.risk_tags, tuple)
        or not 1 <= len(case.risk_tags) <= 16
        or len(set(case.risk_tags)) != len(case.risk_tags)
        or any(
            not isinstance(tag, str) or _TAG.fullmatch(tag) is None
            for tag in case.risk_tags
        )
    ):
        raise ValueError("DP321_RISK_TAGS_INVALID")
    for key in (
        "source_version_sha256",
        "locator_sha256",
        "original_quote_sha256",
        "rights_receipt_sha256",
    ):
        _digest(getattr(case, key), key.upper())
    if (
        case.locator_type not in {"TEXT_POSITION", "PAGE_RANGE", "MEDIA_SEGMENT_REF"}
        or type(case.locator_start) is not int
        or type(case.locator_end) is not int
        or not 0 <= case.locator_start < case.locator_end <= 10_000_000
    ):
        raise ValueError("DP321_LOCATOR_INVALID")
    label = case.label
    if not isinstance(label, ReferenceLabel) or label.kind not in {
        "DECIDABLE",
        "ABSTENTION_ONLY",
    }:
        raise ValueError("DP321_LABEL_INVALID")
    if type(label.publication_allowed) is not bool:
        raise ValueError("DP321_PUBLICATION_LABEL_INVALID")
    if label.kind == "ABSTENTION_ONLY":
        if (
            case.ambiguity != "CONTESTED"
            or label.publication_allowed
            or any(
                x is not None
                for x in (
                    label.person_id,
                    label.exact_quote_sha256,
                    label.endorsed,
                    label.factual_verdict,
                    label.denial_relation,
                    label.privacy_sensitive,
                )
            )
        ):
            raise ValueError("DP321_ABSTENTION_ONLY_HAS_SEMANTIC_GOLD")
    else:
        if (
            case.ambiguity != "DECIDABLE"
            or not label.person_id
            or label.endorsed is None
            or type(label.endorsed) is not bool
            or label.factual_verdict not in _VERDICTS
            or label.denial_relation not in _DENIALS
        ):
            raise ValueError("DP321_DECIDABLE_LABEL_INCOMPLETE")
        _need(label.person_id, "PERSON_REF")
        _digest(label.exact_quote_sha256, "EXACT_QUOTE")
        if case.claim_type == "OPINION" and label.factual_verdict != "NOT_APPLICABLE":
            raise ValueError("DP321_OPINION_VERDICT_UNSUPPORTED")
        if case.claim_type == "FACTUAL" and label.factual_verdict == "NOT_APPLICABLE":
            raise ValueError("DP321_FACTUAL_VERDICT_REQUIRED")
        if (
            label.privacy_sensitive is not None
            and type(label.privacy_sensitive) is not bool
        ):
            raise ValueError("DP321_PRIVACY_REFERENCE_INVALID")
        if (
            "PRIVACY" in case.risk_tags
            and label.publication_allowed
            and label.privacy_sensitive is not False
        ):
            raise ValueError("DP321_PRIVACY_CLEARANCE_NOT_ATTESTED")
        if label.privacy_sensitive is True and label.publication_allowed:
            raise ValueError("DP321_PRIVACY_PUBLICATION_CONFLICT")
    if label.publication_allowed and case.rights_state != "CLEARED":
        raise ValueError("DP321_RIGHTS_PUBLICATION_CONFLICT")
    _validate_proof(case.proof, manifest, label)


def validate_reference_manifest(manifest: ReferenceManifest) -> None:
    """Structure and self-consistency only; DOES NOT attest independent gold."""
    if (
        not isinstance(manifest, ReferenceManifest)
        or manifest.schema_version != VERSION
    ):
        raise ValueError("DP321_MANIFEST_VERSION_INVALID")
    for key in (
        "manifest_id",
        "rights_policy_version",
        "generator_id",
        "evaluated_model_id",
    ):
        _need(getattr(manifest, key), key.upper())
    for key in ("corpus_sha256", "split_lock_sha256", "manifest_sha256"):
        _digest(getattr(manifest, key), key.upper())
    if type(manifest.holdout_blind) is not bool or not manifest.holdout_blind:
        raise ValueError("DP321_HOLDOUT_BLIND_REQUIRED")
    if manifest.generator_id == manifest.evaluated_model_id:
        raise ValueError("DP321_INDEPENDENCE_CONFLICT")
    if (
        not isinstance(manifest.cases, tuple)
        or not 1 <= len(manifest.cases) <= _MAX_CASES
    ):
        raise ValueError("DP321_CASE_COUNT_INVALID")
    if benchmark_manifest_hash(manifest) != manifest.manifest_sha256:
        raise ValueError("DP321_MANIFEST_HASH_MISMATCH")
    seen_ids: set[str] = set()
    split_by_lineage: dict[str, str] = {}
    for case in manifest.cases:
        _validate_case(case, manifest)
        if case.case_id in seen_ids:
            raise ValueError("DP321_CASE_ID_DUPLICATE")
        seen_ids.add(case.case_id)
        if case.lineage_id in split_by_lineage:
            if split_by_lineage[case.lineage_id] != case.split:
                raise ValueError("DP321_SPLIT_LINEAGE_LEAKAGE")
            raise ValueError("DP321_DUPLICATE_LINEAGE_NOT_INDEPENDENT")
        split_by_lineage[case.lineage_id] = case.split


def _metric(numerator: int, denominator: int) -> MetricCount:
    if denominator == 0:
        return MetricCount(0, 0, None, None, None)
    rate = numerator / denominator
    # Wilson 95% descriptive interval, not a release threshold or population guarantee.
    z = 1.959963984540054
    d = 1 + z * z / denominator
    center = (rate + z * z / (2 * denominator)) / d
    radius = (
        z
        * math.sqrt(rate * (1 - rate) / denominator + z * z / (4 * denominator**2))
        / d
    )
    return MetricCount(
        numerator,
        denominator,
        rate,
        max(0.0, center - radius),
        min(1.0, center + radius),
    )


def _counts(
    cases: tuple[ReferenceCase, ...],
    predictions: dict[str, ReferencePrediction],
    eligible: set[str],
) -> dict[str, MetricCount]:
    numerator = dict.fromkeys(_METRICS, 0)
    denominator = dict.fromkeys(_METRICS, 0)
    # Coverage and prediction-only abstention include every manifest case;
    # semantic/rights labels require independently admitted reference cases.
    denominator["sample_coverage"] = len(cases)
    for row in cases:
        p = predictions.get(row.case_id)
        state = p.state if p else "MISSING"
        denominator["abstention"] += 1
        numerator["abstention"] += state in {"ABSTAIN", "MISSING"}
        if row.case_id not in eligible:
            continue
        label = row.label
        published = state == "PUBLIC"
        decidable = label.kind == "DECIDABLE"
        safe_possible = (
            decidable and label.publication_allowed and row.rights_state == "CLEARED"
        )
        denominator["unsupported_publication"] += 1
        denominator["rights_privacy_leak"] += 1
        numerator["sample_coverage"] += published
        numerator["unsupported_publication"] += published and (
            not safe_possible or not p.claimed_rights_clearance
        )
        numerator["rights_privacy_leak"] += published and (
            row.rights_state != "CLEARED" or label.privacy_sensitive is True
        )
        if safe_possible:
            denominator["eligible_recall"] += 1
            denominator["conditional_publishability"] += 1
        if published and decidable:
            for key in ("false_person", "false_quote", "false_endorsement"):
                denominator[key] += 1
            numerator["false_person"] += p.person_id != label.person_id
            numerator["false_quote"] += p.quote_sha256 != label.exact_quote_sha256
            numerator["false_endorsement"] += p.endorsed != label.endorsed
            if row.claim_type == "FACTUAL":
                denominator["false_factual_verdict"] += 1
                numerator["false_factual_verdict"] += (
                    p.factual_verdict != label.factual_verdict
                )
            if "DENIAL" in row.risk_tags:
                denominator["false_denial"] += 1
                numerator["false_denial"] += p.denial_relation != label.denial_relation
        if safe_possible and published:
            accurate = (
                p.person_id == label.person_id
                and p.quote_sha256 == label.exact_quote_sha256
                and p.endorsed == label.endorsed
                and p.factual_verdict == label.factual_verdict
                and (
                    "DENIAL" not in row.risk_tags
                    or p.denial_relation == label.denial_relation
                )
            )
            numerator["eligible_recall"] += accurate
            numerator["conditional_publishability"] += accurate
    return {name: _metric(numerator[name], denominator[name]) for name in _METRICS}


def _validate_prediction(pred: ReferencePrediction, source: ReferenceCase) -> None:
    if not isinstance(pred, ReferencePrediction):
        raise ValueError("DP321_PREDICTION_INVALID")
    if pred.state not in _STATES:
        raise ValueError("DP321_PREDICTION_STATE_INVALID")
    if pred.source_version_sha256 != source.source_version_sha256:
        raise ValueError("DP321_PREDICTION_SOURCE_VERSION_DRIFT")
    if pred.quote_sha256 is not None:
        _digest(pred.quote_sha256, "PREDICTION_QUOTE")
    if pred.factual_verdict is not None and pred.factual_verdict not in _VERDICTS:
        raise ValueError("DP321_PREDICTION_VERDICT_INVALID")
    if pred.denial_relation is not None and pred.denial_relation not in _DENIALS:
        raise ValueError("DP321_PREDICTION_DENIAL_INVALID")
    if pred.endorsed is not None and type(pred.endorsed) is not bool:
        raise ValueError("DP321_PREDICTION_ENDORSEMENT_INVALID")
    if type(pred.claimed_rights_clearance) is not bool:
        raise ValueError("DP321_PREDICTION_RIGHTS_INVALID")
    if pred.latency_ms is not None and (
        type(pred.latency_ms) is not int or not 0 <= pred.latency_ms <= 3600000
    ):
        raise ValueError("DP321_PREDICTION_LATENCY_INVALID")
    if pred.cost_usd is not None:
        _money(pred.cost_usd)
    _need(pred.run_model_version, "PREDICTION_MODEL_VERSION")


def evaluate_independent_reference(
    manifest: ReferenceManifest,
    predictions: tuple[ReferencePrediction, ...],
    *,
    external_attestation_check: Callable[[ReferenceCase], bool] | None = None,
) -> IndependentReferenceReport:
    """Compute contract counts, never a release gate or genuine gold claim.

    `external_attestation_check` is a future trust boundary controlled by an
    independently approved verifier; locally supplied lambdas are TEST FAKES.
    A verifier refusal/outage excludes a case from semantic denominators,
    never from prediction-only abstention (ABSTAIN or missing prediction) or
    the manifest coverage denominator.
    """
    validate_reference_manifest(manifest)
    if not isinstance(predictions, tuple) or len(predictions) > _MAX_PREDICTIONS:
        raise ValueError("DP321_PREDICTIONS_UNBOUNDED")
    cases_by_id = {row.case_id: row for row in manifest.cases}
    seen: dict[str, ReferencePrediction] = {}
    for pred in predictions:
        if not isinstance(pred, ReferencePrediction):
            raise ValueError("DP321_PREDICTION_INVALID")
        if pred.case_id not in cases_by_id:
            raise ValueError("DP321_PREDICTION_FOREIGN")
        if pred.case_id in seen:
            raise ValueError("DP321_PREDICTION_DUPLICATE")
        _validate_prediction(pred, cases_by_id[pred.case_id])
        seen[pred.case_id] = pred
    admitted: set[str] = set()
    for case in manifest.cases:
        if external_attestation_check is None:
            continue
        try:
            verified = external_attestation_check(case)
        except Exception:
            verified = False
        if verified is True:
            admitted.add(case.case_id)
    global_metrics = _counts(manifest.cases, seen, admitted)
    group_cases: dict[str, list[ReferenceCase]] = {}
    for row in manifest.cases:
        groups = (
            "language:" + row.language,
            "source:" + row.source_type,
            "claim:" + row.claim_type,
            "split:" + row.split,
            "source_role:" + row.source_role,
            "ambiguity:" + row.ambiguity,
        ) + tuple("risk:" + risk for risk in row.risk_tags)
        for group in groups:
            group_cases.setdefault(group, []).append(row)
    strata = {
        key: _counts(tuple(group_cases[key]), seen, admitted)
        for key in sorted(group_cases)
    }
    received = tuple(seen.values())
    cost = sum((p.cost_usd for p in received if p.cost_usd is not None), Decimal("0"))
    latency = sum(p.latency_ms for p in received if p.latency_ms is not None)
    admitted_ids = sorted(admitted)
    admitted_scope_hash = hashlib.sha256(
        json.dumps(
            [manifest.manifest_sha256, admitted_ids], separators=(",", ":")
        ).encode()
    ).hexdigest()
    evaluation_material = {
        "version": VERSION,
        "manifest": manifest.manifest_sha256,
        "model": manifest.evaluated_model_id,
        "predictions": [
            {
                **asdict(seen[key]),
                "cost_usd": str(seen[key].cost_usd)
                if seen[key].cost_usd is not None
                else None,
            }
            for key in sorted(seen)
        ],
        "admitted_case_ids": admitted_ids,
        "contract_only": True,
    }
    report_hash = hashlib.sha256(
        json.dumps(evaluation_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return IndependentReferenceReport(
        status="BLOCKED_EXTERNAL_GOLD"
        if len(admitted) != len(manifest.cases)
        else "CONTRACT_ONLY_NO_ACCEPTED_THRESHOLDS_OR_LIVE_GOLD",
        manifest_sha256=manifest.manifest_sha256,
        report_sha256=report_hash,
        evaluated_model_id=manifest.evaluated_model_id,
        case_count=len(manifest.cases),
        reference_eligible_cases=len(admitted),
        unverified_reference_cases=len(manifest.cases) - len(admitted),
        missing_predictions=len(manifest.cases) - len(seen),
        metrics=global_metrics,
        strata=strata,
        cost_total_usd=cost,
        cost_observed_count=sum(p.cost_usd is not None for p in received),
        latency_total_ms=latency,
        latency_observed_count=sum(p.latency_ms is not None for p in received),
        admitted_case_ids_sha256=admitted_scope_hash,
    )


def compare_reference_reports(
    baseline: IndependentReferenceReport,
    current: IndependentReferenceReport,
) -> ReferenceDrift:
    """Descriptive drift on one immutable reference scope; never a cutover vote."""
    if not isinstance(baseline, IndependentReferenceReport) or not isinstance(
        current, IndependentReferenceReport
    ):
        raise ValueError("DP321_DRIFT_REPORT_INVALID")
    _digest(baseline.report_sha256, "BASELINE_REPORT")
    _digest(current.report_sha256, "CURRENT_REPORT")
    comparable = (
        baseline.manifest_sha256 == current.manifest_sha256
        and baseline.case_count == current.case_count
        and baseline.reference_eligible_cases == current.reference_eligible_cases
        and baseline.unverified_reference_cases == current.unverified_reference_cases
        and isinstance(baseline.admitted_case_ids_sha256, str)
        and _SHA.fullmatch(baseline.admitted_case_ids_sha256) is not None
        and baseline.admitted_case_ids_sha256 == current.admitted_case_ids_sha256
        and set(baseline.metrics) == set(current.metrics) == set(_METRICS)
    )
    return ReferenceDrift(
        status="CONTRACT_ONLY_COMPARABLE"
        if comparable
        else "BLOCKED_INCOMPARABLE_REFERENCE_SCOPE",
        baseline_report_sha256=baseline.report_sha256,
        current_report_sha256=current.report_sha256,
        metric_rate_deltas={
            name: (current.metrics[name].rate - baseline.metrics[name].rate)
            if baseline.metrics[name].denominator == current.metrics[name].denominator
            and baseline.metrics[name].rate is not None
            and current.metrics[name].rate is not None
            else None
            for name in _METRICS
        }
        if comparable
        else {},
    )


__all__ = [
    "VERSION",
    "ReferenceProof",
    "ReferenceLabel",
    "ReferenceCase",
    "ReferenceManifest",
    "ReferencePrediction",
    "MetricCount",
    "IndependentReferenceReport",
    "ReferenceDrift",
    "benchmark_manifest_hash",
    "validate_reference_manifest",
    "evaluate_independent_reference",
    "compare_reference_reports",
]
