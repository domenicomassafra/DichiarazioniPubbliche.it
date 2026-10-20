"""#166: comparable private DER/F1/safety receipts using DP-208 metric functions.

Benchmark hints cannot become an owner GO/GO_BOUNDED decision or speaker identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from dichiarazioni_pubbliche.diarization_benchmark import (
    BOUNDARY_COLLAR_MS, Metrics, SensitiveSpan, Turn, compute_metrics,
    decide, evaluate_safety, receipt_fingerprint,
)
from dichiarazioni_pubbliche.diarization_candidate_adapter import AnonymousDiarizationReceipt


@dataclass(frozen=True)
class DiarizationCandidateComparison:
    status: str  # BLOCKED / CONTRACT_ONLY_HELD
    reason_codes: tuple[str, ...]
    candidate_sha256: str | None = None
    baseline_with_collar: Metrics | None = None
    candidate_with_collar: Metrics | None = None
    baseline_without_collar: Metrics | None = None
    candidate_without_collar: Metrics | None = None
    inserted_clip_separate: bool | None = None
    overlap_reference_ms: int = 0
    overlap_candidate_ms: int = 0
    sensitive_hold: bool = False
    proposed_decision: str | None = None
    receipt_sha256: str | None = None
    publication_authority: bool = False
    speaker_identity_authority: bool = False


def _overlap_ms(turns: Sequence[Turn]) -> int:
    points = sorted({x for row in turns for x in (row.start_ms, row.end_ms)})
    return sum(right - left for left, right in zip(points, points[1:])
               if len({r.speaker_label for r in turns
                       if r.start_ms < right and r.end_ms > left}) > 1)


def compare_private_candidate(
    *, reference: Sequence[Turn], baseline: Sequence[Turn],
    candidate: AnonymousDiarizationReceipt,
    inserted_clip_start_ms: int, inserted_clip_end_ms: int,
    sensitive_spans: Sequence[SensitiveSpan] = (),
    resource_budget_ok: bool = False,
) -> DiarizationCandidateComparison:
    """Use pre-registered DP-208 collar, report collar-free and critical holds."""
    if (not isinstance(candidate, AnonymousDiarizationReceipt)
            or candidate.status != "CURRENT_HELD"
            or candidate.resource is None or not candidate.turns
            or not resource_budget_ok):
        return DiarizationCandidateComparison("BLOCKED", ("CANDIDATE_HELD_OR_RESOURCE_UNVERIFIED",))
    if (not 0 <= inserted_clip_start_ms < inserted_clip_end_ms
            or len(reference) > 512 or len(baseline) > 512):
        return DiarizationCandidateComparison("BLOCKED", ("REFERENCE_BOUNDS_INVALID",))
    try:
        baseline_250 = compute_metrics(reference, baseline, collar_ms=BOUNDARY_COLLAR_MS)
        candidate_250 = compute_metrics(reference, candidate.turns, collar_ms=BOUNDARY_COLLAR_MS)
        baseline_0 = compute_metrics(reference, baseline, collar_ms=0)
        candidate_0 = compute_metrics(reference, candidate.turns, collar_ms=0)
        safety = evaluate_safety(
            reference, candidate.turns,
            inserted_clip_start_ms=inserted_clip_start_ms,
            inserted_clip_end_ms=inserted_clip_end_ms,
            sensitive_spans=sensitive_spans, collar_ms=BOUNDARY_COLLAR_MS,
        )
        decision = decide(
            baseline=baseline_250, candidate=candidate_250,
            safety=safety, resources=candidate.resource,
            resource_budget_ok=resource_budget_ok, license_approved=True,
        )
    except (ValueError, TypeError, AttributeError, OverflowError):
        return DiarizationCandidateComparison("BLOCKED", ("REFERENCE_OR_METRICS_INVALID",))
    ref_overlap = _overlap_ms(reference)
    hyp_overlap = _overlap_ms(candidate.turns)
    codes: list[str] = ["NO_PUBLICATION_OR_IDENTITY_AUTHORITY"]
    if ref_overlap and hyp_overlap == 0:
        codes.append("REFERENCE_OVERLAP_MISSED")
    if hyp_overlap:
        codes.append("OVERLAP_REVIEW_REQUIRED")
    if safety.sensitive_span_hold_required:
        codes.extend(safety.sensitive_span_codes)
    if not safety.inserted_clip_separate:
        codes.append("CRITICAL_INSERTED_CLIP_MERGED")
    proposed = "NO_GO" if "REFERENCE_OVERLAP_MISSED" in codes else decision.decision
    material = {
        "candidate": candidate.normalized_sha256,
        "baseline_250": asdict(baseline_250),
        "candidate_250": asdict(candidate_250),
        "baseline_0": asdict(baseline_0),
        "candidate_0": asdict(candidate_0),
        "codes": codes, "proposed": proposed,
        "reference_overlap_ms": ref_overlap, "candidate_overlap_ms": hyp_overlap,
    }
    return DiarizationCandidateComparison(
        status="CONTRACT_ONLY_HELD", reason_codes=tuple(codes),
        candidate_sha256=candidate.normalized_sha256,
        baseline_with_collar=baseline_250, candidate_with_collar=candidate_250,
        baseline_without_collar=baseline_0, candidate_without_collar=candidate_0,
        inserted_clip_separate=safety.inserted_clip_separate,
        overlap_reference_ms=ref_overlap, overlap_candidate_ms=hyp_overlap,
        sensitive_hold=safety.sensitive_span_hold_required,
        proposed_decision=proposed,
        receipt_sha256=receipt_fingerprint(material),
    )


__all__ = ["DiarizationCandidateComparison", "compare_private_candidate"]
