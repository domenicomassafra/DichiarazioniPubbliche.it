"""#166: opt-in, offline, *anonymous* diarization candidate adapter.

No weights/downloads/providers are bundled. An externally attested DP-208
GO/GO_BOUNDED, pinned local weights, source-use guard, and budget are mandatory.
Do not pass its TURN labels to SpeakerIdentityCandidate or public projection.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from dichiarazioni_pubbliche.diarization_benchmark import Decision, ResourceReceipt, Turn
from dichiarazioni_pubbliche.diarization_candidate_process import (
    RunnerIsolationError, execute_candidate,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked


CONTRACT = "dp166-anonymous-diarization-v1"
SUPPORTED = {"PYANNOTE_AUDIO": "4.0.7", "DIARIZE_CPU": "0.1.2"}
MAX_TURNS = 512
# The reused benchmark enumerates speaker-label permutations (factorial).
# Keep a small bound to prevent CPU exhaustion on malicious/many-speaker input.
MAX_SPEAKERS = 6
MAX_MODEL_FILES = 128


@dataclass(frozen=True)
class CandidateAuthorization:
    """Evidence *references*, never evidence of approval by themselves."""

    dp208_decision: Decision
    decision_receipt_sha256: str
    reference_sha256: str
    reviewer_ref: str
    source_rights_receipt_sha256: str
    model_terms_receipt_sha256: str
    engine_id: str
    engine_version: str
    model_id: str
    model_sha256: str
    model_license: str
    config_sha256: str
    input_sha256: str
    max_elapsed_ms: int
    max_peak_rss_bytes: int
    max_cache_bytes: int
    max_audio_duration_ms: int


@dataclass(frozen=True)
class AnonymousDiarizationReceipt:
    contract: str
    status: str  # BLOCKED / ERROR_HELD / CURRENT_HELD / ABSTAIN_HELD
    codes: tuple[str, ...]
    engine_id: str | None = None
    model_sha256: str | None = None
    input_sha256: str | None = None
    decision_receipt_sha256: str | None = None
    source_rights_receipt_sha256: str | None = None
    model_terms_receipt_sha256: str | None = None
    config_sha256: str | None = None
    normalized_sha256: str | None = None
    resource: ResourceReceipt | None = None
    turns: tuple[Turn, ...] = ()
    overlap_intervals_ms: tuple[tuple[int, int], ...] = ()
    abstention_intervals_ms: tuple[tuple[int, int], ...] = ()
    review_state: str = "POLICY_HOLD"
    speaker_person_id: None = None
    public_quote_eligible: bool = False


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _block(code: str) -> AnonymousDiarizationReceipt:
    return AnonymousDiarizationReceipt(CONTRACT, "BLOCKED", (code,))


def _tree_hash(model_dir: Path, *, max_bytes: int) -> tuple[str, int]:
    """Hash only an already present local model tree; refuse links and oversize."""
    if not model_dir.is_dir() or model_dir.is_symlink():
        raise ValueError("MODEL_NOT_LOCAL")
    files = sorted((p for p in model_dir.rglob("*") if p.is_file()), key=lambda p: p.relative_to(model_dir).as_posix())
    if not files or len(files) > MAX_MODEL_FILES:
        raise ValueError("MODEL_FILE_COUNT_INVALID")
    if any(p.is_symlink() for p in model_dir.rglob("*")):
        raise ValueError("MODEL_SYMLINK_FORBIDDEN")
    h = hashlib.sha256()
    total = 0
    for item in files:
        rel = item.relative_to(model_dir).as_posix()
        h.update(len(rel.encode()).to_bytes(4, "big"))
        h.update(rel.encode())
        with item.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("MODEL_CACHE_BUDGET_EXCEEDED")
                h.update(chunk)
    return h.hexdigest(), total


def _seconds_to_ms(seconds: object, *, duration_ms: int) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("ENGINE_TIMESTAMP_INVALID")
    value = float(seconds)
    if not math.isfinite(value) or value < 0 or value * 1000 > duration_ms + 0.5:
        raise ValueError("ENGINE_TIMESTAMP_INVALID")
    return int(round(value * 1000))


def _raw_rows(engine_id: str, result: object) -> list[tuple[object, object, object]]:
    """Extract timings/opaque cluster keys; no feature/embedding persisted."""
    if engine_id == "PYANNOTE_AUDIO":
        diarization = getattr(result, "speaker_diarization", None)
        # Regular annotation retains overlap; exclusive diarization erases it.
        if diarization is None or not callable(getattr(diarization, "itertracks", None)):
            raise ValueError("ENGINE_ANNOTATION_UNAVAILABLE")
        rows = []
        for item in diarization.itertracks(yield_label=True):
            if not isinstance(item, tuple) or len(item) != 3:
                raise ValueError("ENGINE_ANNOTATION_MALFORMED")
            segment, _track, speaker = item
            rows.append((segment.start, segment.end, speaker))
        return rows
    if engine_id == "DIARIZE_CPU":
        segments = getattr(result, "segments", None)
        if not isinstance(segments, (tuple, list)):
            raise ValueError("ENGINE_ANNOTATION_UNAVAILABLE")
        return [(row.start, row.end, row.speaker) for row in segments]
    raise ValueError("ENGINE_UNSUPPORTED")


def normalize_anonymous_turns(
    *, engine_id: str, raw_result: object, input_sha256: str, duration_ms: int,
) -> tuple[tuple[Turn, ...], tuple[tuple[int, int], ...]]:
    """No upstream speaker string leaves this function. Reject ambiguous times."""
    if not _sha(input_sha256) or type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("DIARIZATION_SOURCE_INVALID")
    rows = _raw_rows(engine_id, raw_result)
    if len(rows) > MAX_TURNS:
        raise ValueError("ENGINE_TURN_LIMIT_EXCEEDED")
    decoded: list[tuple[int, int, str]] = []
    for start, end, label in rows:
        a = _seconds_to_ms(start, duration_ms=duration_ms)
        b = _seconds_to_ms(end, duration_ms=duration_ms)
        if a >= b or not isinstance(label, str) or not label or len(label) > 120:
            raise ValueError("ENGINE_TURN_INVALID")
        decoded.append((a, b, label))
    decoded.sort(key=lambda x: (x[0], x[1], x[2]))
    # No persistent linkage to a person, previous recording or voiceprint.
    mapping: dict[str, str] = {}
    for _start, _end, speaker in decoded:
        if speaker not in mapping:
            if len(mapping) >= MAX_SPEAKERS:
                raise ValueError("ENGINE_SPEAKER_LIMIT_EXCEEDED")
            mapping[speaker] = f"TURN_{len(mapping):02d}"
    turns = tuple(Turn(start, end, mapping[speaker], input_sha256) for start, end, speaker in decoded)
    boundaries = sorted({t.start_ms for t in turns} | {t.end_ms for t in turns})
    overlap: list[tuple[int, int]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        active = {t.speaker_label for t in turns if t.start_ms < right and t.end_ms > left}
        if len(active) > 1:
            if overlap and overlap[-1][1] == left:
                overlap[-1] = (overlap[-1][0], right)
            else:
                overlap.append((left, right))
    return turns, tuple(overlap)


def run_offline_candidate(
    *, permit: CandidateAuthorization | None,
    approval_check: Callable[[CandidateAuthorization], bool] | None,
    media_path: Path, model_dir: Path, duration_ms: int,
    content_id: str, source_url: str,
    source_use_guard: SourceFamilyUseGuard | None,
    offline_runner: Callable[[Path, Path], object],
    observed_network_calls: int = 0,
) -> AnonymousDiarizationReceipt:
    """Execute an injected LOCAL runner only after all explicit gates succeed.

    A trusted operator must verify DP-208 decision/model rights independently;
    passing a locally supplied callback in unit tests never attests real GO.
    The runner must not fetch weights, create identities, or call paid services.
    """
    if not isinstance(permit, CandidateAuthorization):
        return _block("DP208_GO_DECISION_MISSING")
    if (not isinstance(permit.dp208_decision, Decision)
            or permit.dp208_decision.decision not in {"GO", "GO_BOUNDED"}
            or permit.dp208_decision.failed_gates):
        return _block("DP208_NO_GO_OR_UNAPPROVED")
    if (permit.engine_id not in SUPPORTED
            or permit.engine_version != SUPPORTED.get(permit.engine_id)):
        return _block("ENGINE_VERSION_UNSUPPORTED")
    if (not all(_sha(getattr(permit, key)) for key in (
            "decision_receipt_sha256", "reference_sha256",
            "source_rights_receipt_sha256", "model_terms_receipt_sha256",
            "model_sha256", "config_sha256", "input_sha256"))
            or not permit.reviewer_ref or not permit.model_id
            or permit.model_license not in {"CC-BY-4.0", "APACHE-2.0", "MIT"}
            or any(type(getattr(permit, key)) is not int or getattr(permit, key) <= 0
                   for key in ("max_elapsed_ms", "max_peak_rss_bytes", "max_cache_bytes", "max_audio_duration_ms"))):
        return _block("MODEL_OR_REFERENCE_APPROVAL_INVALID")
    if approval_check is None:
        return _block("INDEPENDENT_APPROVAL_UNAVAILABLE")
    try:
        approved = approval_check(permit)
    except Exception:
        approved = False
    if approved is not True:
        return _block("INDEPENDENT_APPROVAL_UNVERIFIED")
    if not isinstance(source_use_guard, SourceFamilyUseGuard):
        return _block("SOURCE_USE_GUARD_MISSING")
    if type(duration_ms) is not int or not 0 < duration_ms <= permit.max_audio_duration_ms:
        return _block("AUDIO_DURATION_BUDGET_FAILED")
    if type(observed_network_calls) is not int or observed_network_calls != 0:
        return _block("NETWORK_USE_FORBIDDEN")
    if not isinstance(media_path, Path) or not isinstance(model_dir, Path):
        return _block("LOCAL_PATH_REQUIRED")
    try:
        source_use_guard.bind_capture(content_id=content_id, url=source_url)
        source_use_guard.bind_fetched(final_url=source_url)
        source_use_guard.require("STORE_BODY", content_sha256=permit.input_sha256)
        source_use_guard.require("ASR_MEDIA", content_sha256=permit.input_sha256)
    except SourceUseBlocked as exc:
        return _block(exc.code)
    if not media_path.is_file() or media_path.is_symlink():
        return _block("AUDIO_NOT_LOCAL")
    try:
        digest = hashlib.sha256()
        with media_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != permit.input_sha256:
            return _block("AUDIO_HASH_DRIFT")
        model_sha, cache_bytes = _tree_hash(model_dir, max_bytes=permit.max_cache_bytes)
    except (OSError, ValueError):
        return _block("LOCAL_MODEL_UNAVAILABLE_OR_OVER_BUDGET")
    if model_sha != permit.model_sha256:
        return _block("MODEL_HASH_DRIFT")
    try:
        turns, overlaps, elapsed, peak = execute_candidate(
            offline_runner, media_path, model_dir, engine_id=permit.engine_id,
            input_sha256=permit.input_sha256, duration_ms=duration_ms,
            wall_ms=permit.max_elapsed_ms, address_bytes=permit.max_peak_rss_bytes,
        )
    except RunnerIsolationError as exc:
        return AnonymousDiarizationReceipt(CONTRACT, "ERROR_HELD", (exc.code,))
    except Exception:
        return AnonymousDiarizationReceipt(CONTRACT, "ERROR_HELD", ("ENGINE_FAILED_OR_UNSAFE_OUTPUT",))
    resource_receipt = ResourceReceipt(
        engine_id=permit.engine_id, engine_version=permit.engine_version,
        model_id=permit.model_id, model_sha256=model_sha,
        config_sha256=permit.config_sha256, input_sha256=permit.input_sha256,
        elapsed_ms=elapsed, peak_rss_bytes=peak, cache_bytes=cache_bytes,
        license_status="APPROVED", network_calls=observed_network_calls,
        identity_features_present=False,
    )
    codes = ["ANONYMOUS_ONLY", "NO_PERSON_IDENTITY_AUTHORITY"]
    if not turns:
        codes.append("NO_SPEAKER_TURNS_ABSTAIN")
    if overlaps:
        codes.append("OVERLAP_REVIEW_REQUIRED")
    if permit.dp208_decision.decision == "GO_BOUNDED":
        codes.append("DP208_BOUNDED_POLICY_HOLD")
    if elapsed > permit.max_elapsed_ms or peak > permit.max_peak_rss_bytes:
        return AnonymousDiarizationReceipt(CONTRACT, "ERROR_HELD", ("ENGINE_FAILED_OR_LIMIT",))
    normalized_hash = hashlib.sha256(json.dumps(
        [asdict(t) for t in turns], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return AnonymousDiarizationReceipt(
        contract=CONTRACT,
        status="ABSTAIN_HELD" if not turns else "CURRENT_HELD",
        codes=tuple(codes), engine_id=permit.engine_id,
        model_sha256=model_sha, input_sha256=permit.input_sha256,
        decision_receipt_sha256=permit.decision_receipt_sha256,
        source_rights_receipt_sha256=permit.source_rights_receipt_sha256,
        model_terms_receipt_sha256=permit.model_terms_receipt_sha256,
        config_sha256=permit.config_sha256,
        normalized_sha256=normalized_hash, resource=resource_receipt,
        turns=turns,
        overlap_intervals_ms=overlaps,
        abstention_intervals_ms=overlaps if overlaps else ((0, duration_ms),) if not turns else (),
    )


def pyannote_local_runner(media_path: Path, model_dir: Path) -> object:
    """Optional pyannote 4.0.7 entry point; caller must run approved preflight."""
    # env is intentionally process-scoped; use a single isolated MiniPC worker.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    from pyannote.audio import Pipeline  # type: ignore[import-not-found]  # noqa: PLC0415

    pipeline = Pipeline.from_pretrained(str(model_dir))
    return pipeline(str(media_path))


__all__ = [
    "AnonymousDiarizationReceipt", "CandidateAuthorization", "normalize_anonymous_turns",
    "pyannote_local_runner", "run_offline_candidate",
]
