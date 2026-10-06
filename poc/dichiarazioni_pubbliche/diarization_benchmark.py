from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


DIARIZATION_BENCHMARK_VERSION = "diarization-benchmark-v1"
BOUNDARY_COLLAR_MS = 250
ALLOWED_DECISIONS = frozenset({"GO", "GO_BOUNDED", "NO_GO"})


@dataclass(frozen=True)
class Turn:
    start_ms: int
    end_ms: int
    speaker_label: str
    input_sha256: str
    timebase: str = "MEDIA_MS"

    def __post_init__(self) -> None:
        if isinstance(self.start_ms, bool) or isinstance(self.end_ms, bool):
            raise ValueError("DIARIZATION_TIMESTAMP_INVALID")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("DIARIZATION_TIMESTAMP_INVALID")
        if not str(self.speaker_label or "").startswith("TURN_"):
            raise ValueError("DIARIZATION_ANONYMOUS_LABEL_REQUIRED")
        if self.timebase != "MEDIA_MS":
            raise ValueError("DIARIZATION_TIMEBASE_UNSUPPORTED")
        if len(self.input_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.input_sha256.lower()
        ):
            raise ValueError("DIARIZATION_INPUT_HASH_INVALID")


@dataclass(frozen=True)
class SensitiveSpan:
    start_ms: int
    end_ms: int
    kind: str

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("DIARIZATION_SENSITIVE_SPAN_INVALID")
        if self.kind not in {"NUMBER", "NEGATION", "DATE", "NAME", "DIRECT_QUOTE"}:
            raise ValueError("DIARIZATION_SENSITIVE_KIND_INVALID")


@dataclass(frozen=True)
class Metrics:
    collar_ms: int
    reference_speech_ms: int
    missed_speech_ms: int
    false_alarm_ms: int
    confusion_ms: int
    der: float
    speaker_change_precision: float
    speaker_change_recall: float
    speaker_change_f1: float
    boundary_mean_abs_error_ms: float | None
    matched_boundary_count: int
    reference_boundary_count: int
    hypothesis_boundary_count: int


@dataclass(frozen=True)
class SafetyResult:
    inserted_clip_separate: bool
    sensitive_span_hold_required: bool
    sensitive_span_codes: tuple[str, ...]


@dataclass(frozen=True)
class ResourceReceipt:
    engine_id: str
    engine_version: str
    model_id: str
    model_sha256: str
    config_sha256: str
    input_sha256: str
    elapsed_ms: int
    peak_rss_bytes: int
    cache_bytes: int
    license_status: str
    network_calls: int = 0
    identity_features_present: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.elapsed_ms, "elapsed_ms"),
            (self.peak_rss_bytes, "peak_rss_bytes"),
            (self.cache_bytes, "cache_bytes"),
            (self.network_calls, "network_calls"),
        ):
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"DIARIZATION_{name.upper()}_INVALID")
        for value, name in (
            (self.model_sha256, "model_sha256"),
            (self.config_sha256, "config_sha256"),
            (self.input_sha256, "input_sha256"),
        ):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise ValueError(f"DIARIZATION_{name.upper()}_INVALID")
        if self.identity_features_present:
            raise ValueError("DIARIZATION_BIOMETRIC_IDENTITY_FORBIDDEN")


@dataclass(frozen=True)
class Decision:
    decision: str
    failed_gates: tuple[str, ...]
    rationale_codes: tuple[str, ...]
    version: str = DIARIZATION_BENCHMARK_VERSION

    def __post_init__(self) -> None:
        if self.decision not in ALLOWED_DECISIONS:
            raise ValueError("DIARIZATION_DECISION_INVALID")


def _active_label(turns: Sequence[Turn], start: int, end: int) -> str | None:
    labels = {
        turn.speaker_label
        for turn in turns
        if turn.start_ms < end and turn.end_ms > start
    }
    if not labels:
        return None
    if len(labels) > 1:
        return "__OVERLAP__"
    return next(iter(labels))


def _speaker_mapping(reference: Sequence[Turn], hypothesis: Sequence[Turn]) -> dict[str, str]:
    ref_labels = sorted({t.speaker_label for t in reference})
    hyp_labels = sorted({t.speaker_label for t in hypothesis})
    if not ref_labels or not hyp_labels:
        return {}
    points = sorted({x for turn in (*reference, *hypothesis) for x in (turn.start_ms, turn.end_ms)})
    overlap: dict[tuple[str, str], int] = {}
    for left, right in zip(points, points[1:]):
        if right <= left:
            continue
        ref = _active_label(reference, left, right)
        hyp = _active_label(hypothesis, left, right)
        if ref and hyp and ref != "__OVERLAP__" and hyp != "__OVERLAP__":
            overlap[(hyp, ref)] = overlap.get((hyp, ref), 0) + right - left
    best_score = -1
    best: dict[str, str] = {}
    targets = ref_labels + [f"__UNMAPPED_{i}" for i in range(max(0, len(hyp_labels) - len(ref_labels)))]
    for permutation in itertools.permutations(targets, len(hyp_labels)):
        score = sum(
            overlap.get((hyp, ref), 0)
            for hyp, ref in zip(hyp_labels, permutation)
            if ref in ref_labels
        )
        if score > best_score:
            best_score = score
            best = {
                hyp: ref
                for hyp, ref in zip(hyp_labels, permutation)
                if ref in ref_labels
            }
    return best


def _change_boundaries(turns: Sequence[Turn]) -> tuple[int, ...]:
    ordered = sorted(turns, key=lambda t: (t.start_ms, t.end_ms, t.speaker_label))
    changes: list[int] = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end_ms == current.start_ms and previous.speaker_label != current.speaker_label:
            changes.append(current.start_ms)
    return tuple(changes)


def _boundary_metrics(
    reference: Sequence[Turn],
    hypothesis: Sequence[Turn],
    collar_ms: int,
) -> tuple[float, float, float, float | None, int, int, int]:
    ref = list(_change_boundaries(reference))
    hyp = list(_change_boundaries(hypothesis))
    remaining = set(range(len(hyp)))
    errors: list[int] = []
    for ref_boundary in ref:
        candidates = sorted(
            (
                (abs(hyp[index] - ref_boundary), index)
                for index in remaining
                if abs(hyp[index] - ref_boundary) <= collar_ms
            ),
            key=lambda item: (item[0], hyp[item[1]], item[1]),
        )
        if not candidates:
            continue
        error, index = candidates[0]
        remaining.remove(index)
        errors.append(error)
    matched = len(errors)
    precision = matched / len(hyp) if hyp else (1.0 if not ref else 0.0)
    recall = matched / len(ref) if ref else (1.0 if not hyp else 0.0)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    mae = sum(errors) / matched if matched else None
    return precision, recall, f1, mae, matched, len(ref), len(hyp)


def compute_metrics(
    reference: Sequence[Turn],
    hypothesis: Sequence[Turn],
    *,
    collar_ms: int = BOUNDARY_COLLAR_MS,
) -> Metrics:
    if not reference:
        raise ValueError("DIARIZATION_REFERENCE_REQUIRED")
    input_hashes = {turn.input_sha256 for turn in (*reference, *hypothesis)}
    if len(input_hashes) != 1:
        raise ValueError("DIARIZATION_INPUT_HASH_MISMATCH")
    if collar_ms < 0:
        raise ValueError("DIARIZATION_COLLAR_INVALID")
    mapping = _speaker_mapping(reference, hypothesis)
    points = sorted({x for turn in (*reference, *hypothesis) for x in (turn.start_ms, turn.end_ms)})
    ref_speech = miss = false_alarm = confusion = 0
    for left, right in zip(points, points[1:]):
        duration = right - left
        if duration <= 0:
            continue
        ref = _active_label(reference, left, right)
        hyp = _active_label(hypothesis, left, right)
        if ref is not None:
            ref_speech += duration
        if ref is not None and hyp is None:
            miss += duration
        elif ref is None and hyp is not None:
            false_alarm += duration
        elif ref is not None and hyp is not None:
            if ref == "__OVERLAP__" or hyp == "__OVERLAP__":
                if ref != hyp:
                    confusion += duration
            elif mapping.get(hyp) != ref:
                confusion += duration
    der = (miss + false_alarm + confusion) / ref_speech if ref_speech else math.inf
    precision, recall, f1, mae, matched, ref_count, hyp_count = _boundary_metrics(
        reference, hypothesis, collar_ms
    )
    return Metrics(
        collar_ms=collar_ms,
        reference_speech_ms=ref_speech,
        missed_speech_ms=miss,
        false_alarm_ms=false_alarm,
        confusion_ms=confusion,
        der=der,
        speaker_change_precision=precision,
        speaker_change_recall=recall,
        speaker_change_f1=f1,
        boundary_mean_abs_error_ms=mae,
        matched_boundary_count=matched,
        reference_boundary_count=ref_count,
        hypothesis_boundary_count=hyp_count,
    )


def evaluate_safety(
    reference: Sequence[Turn],
    hypothesis: Sequence[Turn],
    *,
    inserted_clip_start_ms: int,
    inserted_clip_end_ms: int,
    sensitive_spans: Iterable[SensitiveSpan] = (),
    collar_ms: int = BOUNDARY_COLLAR_MS,
) -> SafetyResult:
    reference_label = _active_label(reference, inserted_clip_start_ms, inserted_clip_end_ms)
    hypothesis_label = _active_label(hypothesis, inserted_clip_start_ms, inserted_clip_end_ms)
    before = _active_label(hypothesis, max(0, inserted_clip_start_ms - collar_ms - 1), inserted_clip_start_ms)
    after = _active_label(hypothesis, inserted_clip_end_ms, inserted_clip_end_ms + collar_ms + 1)
    separate = bool(
        reference_label
        and hypothesis_label
        and hypothesis_label != "__OVERLAP__"
        and hypothesis_label != before
        and hypothesis_label != after
    )
    codes: list[str] = []
    for span in sensitive_spans:
        ref = _active_label(reference, span.start_ms, span.end_ms)
        hyp = _active_label(hypothesis, span.start_ms, span.end_ms)
        if ref is None or hyp is None or ref == "__OVERLAP__" or hyp == "__OVERLAP__":
            codes.append(f"{span.kind}_TURN_UNCERTAIN")
            continue
        mapping = _speaker_mapping(reference, hypothesis)
        if mapping.get(hyp) != ref:
            codes.append(f"{span.kind}_SPEAKER_CONFUSION")
    return SafetyResult(
        inserted_clip_separate=separate,
        sensitive_span_hold_required=bool(codes),
        sensitive_span_codes=tuple(sorted(set(codes))),
    )


def decide(
    *,
    baseline: Metrics,
    candidate: Metrics,
    safety: SafetyResult,
    resources: ResourceReceipt,
    resource_budget_ok: bool,
    license_approved: bool,
) -> Decision:
    failed: list[str] = []
    bounded: list[str] = []
    if resources.network_calls != 0:
        failed.append("UNAPPROVED_NETWORK_CALL")
    if not license_approved or resources.license_status != "APPROVED":
        failed.append("LICENSE_NOT_APPROVED")
    if not resource_budget_ok:
        failed.append("RESOURCE_BUDGET_FAILED")
    if not safety.inserted_clip_separate:
        failed.append("CRITICAL_INSERTED_CLIP_MERGED")
    if safety.sensitive_span_hold_required:
        bounded.append("SENSITIVE_SPAN_UNCERTAIN")
    der_gate = candidate.der <= 0.20 or (
        baseline.der > 0 and candidate.der <= baseline.der * 0.80
    )
    if not der_gate:
        failed.append("DER_GATE_FAILED")
    if candidate.speaker_change_f1 < 0.90:
        failed.append("SPEAKER_CHANGE_F1_FAILED")
    if failed:
        return Decision("NO_GO", tuple(failed), tuple(bounded))
    if bounded:
        return Decision("GO_BOUNDED", (), tuple(bounded))
    return Decision("GO", (), ("ALL_PRE_REGISTERED_GATES_PASS",))


def receipt_fingerprint(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ALLOWED_DECISIONS",
    "BOUNDARY_COLLAR_MS",
    "DIARIZATION_BENCHMARK_VERSION",
    "Decision",
    "Metrics",
    "ResourceReceipt",
    "SafetyResult",
    "SensitiveSpan",
    "Turn",
    "compute_metrics",
    "decide",
    "evaluate_safety",
    "receipt_fingerprint",
]
