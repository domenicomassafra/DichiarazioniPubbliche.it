"""DP-165: private opt-in WhisperX forced alignment; suggestions only, never authority."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dichiarazioni_pubbliche.local_asr import (
    MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, _RIGHTS_BASES, _RECEIPT_ID,
    _SHA256, _digest_file, _strict_file,
)
from dichiarazioni_pubbliche.local_inference_guard import LocalInferenceBusy, local_inference_slot
from dichiarazioni_pubbliche.parliamentary_alignment import (
    MediaSegment, ParliamentaryAlignment, ParliamentaryIntervention,
    align_parliamentary_intervention,
)
from dichiarazioni_pubbliche.transcript_contract import TranscriptCandidate

DONOR_VERSION = "3.8.6"
DONOR_COMMIT = "3ccc17b8de34f305300f8a3fd3c9f76ba820c0d0"
VERSION = "dp165-whisperx-alignment-v1"
PROVIDER = "whisperx-alignment-candidate"
ENABLE = "DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED"
MAX_MODEL_BYTES = 1024 * 1024 * 1024
MAX_MODEL_FILES = 128
MAX_WORDS = 240
MIN_SCORE = 0.70  # heuristic, NOT a calibrated probability
_COMMIT = re.compile(r"[a-f0-9]{40}\Z")
_ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"}
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", flags=re.UNICODE)


class AlignmentHold(ValueError):
    """A private alignment cannot be trusted or executed."""


@dataclass(frozen=True)
class WordTime:
    word: str
    start_ms: int
    end_ms: int
    score: float


@dataclass(frozen=True)
class AlignmentProposal:
    status: str
    blockers: tuple[str, ...]
    words: tuple[WordTime, ...]
    candidate: TranscriptCandidate | None
    fallback: ParliamentaryAlignment
    provenance: dict[str, str]
    publication_blocked: bool = True

    @property
    def source_span_review_ready(self) -> bool:
        # Only a fresh human audio review may create HUMAN_AUDIO_VERIFIED evidence.
        return False


def _receipt(path: Path) -> tuple[dict[str, Any], str]:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or path.stat().st_size > 16_384):
        raise AlignmentHold("WHISPERX_MODEL_RECEIPT_MISSING")
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AlignmentHold("WHISPERX_MODEL_RECEIPT_INVALID") from exc
    if (not isinstance(data, dict) or data.get("license_reviewed") is not True
            or data.get("native_notices_reviewed") is not True
            or data.get("license_spdx") not in _ALLOWED_LICENSES
            or not isinstance(data.get("license_source_url"), str)
            or not data["license_source_url"].startswith("https://")
            or not isinstance(data.get("model_id"), str)
            or not isinstance(data.get("revision"), str)
            or not _COMMIT.fullmatch(data["revision"])
            or not isinstance(data.get("model_dir"), str)):
        raise AlignmentHold("WHISPERX_MODEL_OR_NATIVE_RIGHTS_UNVERIFIED")
    root = Path(data["model_dir"])
    files = data.get("files")
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or not isinstance(files, dict) or not 3 <= len(files) <= MAX_MODEL_FILES
            or "config.json" not in files or not any(n.endswith(".safetensors") for n in files)
            or not any(n.upper().startswith("LICENSE") for n in files)):
        raise AlignmentHold("WHISPERX_MODEL_INVENTORY_INVALID")
    total = 0
    for name, expected in files.items():
        if (not isinstance(name, str) or not name or name.startswith("/")
                or "\\" in name or any(p in {"", ".", ".."} for p in name.split("/"))
                or not isinstance(expected, str) or not _SHA256.fullmatch(expected)):
            raise AlignmentHold("WHISPERX_MODEL_INVENTORY_INVALID")
        item = root / name
        if item.is_symlink() or not item.is_file():
            raise AlignmentHold("WHISPERX_MODEL_INVENTORY_INVALID")
        digest, size = _digest_file(item, max_bytes=MAX_MODEL_BYTES, label="MODEL")
        total += size
        if total > MAX_MODEL_BYTES or digest != expected:
            raise AlignmentHold("WHISPERX_MODEL_HASH_MISMATCH")
    seen: set[str] = set()
    for folder, dirs, names in os.walk(root, followlinks=False):
        if any((Path(folder) / n).is_symlink() for n in (*dirs, *names)):
            raise AlignmentHold("WHISPERX_MODEL_INVENTORY_INVALID")
        seen.update((Path(folder) / n).relative_to(root).as_posix() for n in names)
    if seen != set(files):
        raise AlignmentHold("WHISPERX_MODEL_INVENTORY_INVALID")
    return data, hashlib.sha256(raw).hexdigest()


def _parse_words(payload: dict[str, Any], *, text: str, duration_ms: int) -> tuple[WordTime, ...]:
    raw = payload.get("word_segments")
    expected = _WORD.findall(text.casefold())
    if not isinstance(raw, list) or not expected or len(raw) != len(expected) or len(raw) > MAX_WORDS:
        raise AlignmentHold("WHISPERX_WORD_COVERAGE_UNCERTAIN")
    words: list[WordTime] = []
    last_end = 0
    for source, target in zip(raw, expected):
        if not isinstance(source, dict) or not isinstance(source.get("word"), str):
            raise AlignmentHold("WHISPERX_WORD_SHAPE_INVALID")
        actual = _WORD.findall(source["word"].casefold())
        if len(actual) != 1 or actual[0] != target:
            raise AlignmentHold("WHISPERX_WORD_TEXT_MISMATCH")
        begin, end, score = source.get("start"), source.get("end"), source.get("score")
        if (type(begin) not in {float, int} or type(end) not in {float, int}
                or type(score) not in {float, int}
                or not all(math.isfinite(v) for v in (begin, end, score))):
            raise AlignmentHold("WHISPERX_WORD_UNTIMED_OR_UNSCORED")
        start_ms, end_ms = round(begin * 1000), round(end * 1000)
        if (start_ms < last_end or end_ms <= start_ms or end_ms > duration_ms + 100
                or score < MIN_SCORE or score > 1):
            raise AlignmentHold("WHISPERX_WORD_DRIFT_OR_LOW_SCORE")
        words.append(WordTime(source["word"], start_ms, end_ms, float(score)))
        last_end = end_ms
    return tuple(words)


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (6 * 1024**3, 6 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Child stdout is a private regular file: the OS enforces the output cap.
    resource.setrlimit(resource.RLIMIT_FSIZE, (256_000, 256_000))


def _worker() -> None:
    """Run only an operator-provisioned local HF model; upstream inference reused."""
    if os.getenv(ENABLE) != "1" or platform.system() != "Linux":
        raise AlignmentHold("WHISPERX_HOST_OR_OPT_IN_REQUIRED")
    job = json.loads(sys.stdin.read(32768))
    receipt, _ = _receipt(Path(job["receipt"]))
    if importlib.metadata.version("whisperx") != DONOR_VERSION:
        raise AlignmentHold("WHISPERX_VERSION_MISMATCH")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1", "OMP_NUM_THREADS": "4",
                       "TORCH_HOME": receipt["model_dir"]})
    # WhisperX alignment.py otherwise downloads punkt_tab when absent.
    import nltk
    def no_download(*_args: object, **_kw: object) -> None:
        raise AlignmentHold("WHISPERX_NLTK_ASSET_MISSING")
    nltk.download = no_download
    from whisperx import align, load_align_model
    import numpy as np
    with wave.open(job["audio"], "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    samples = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
    model, meta = load_align_model(
        language_code=job["language"], device="cpu",
        model_name=receipt["model_dir"], model_cache_only=True,
    )
    outcome = align(
        [{"start": 0.0, "end": job["duration"], "text": job["text"]}],
        model, meta, samples, "cpu", interpolate_method="ignore",
        return_char_alignments=False,
    )
    print(json.dumps({"word_segments": outcome["word_segments"]}, ensure_ascii=False))


def propose_whisperx_alignment(
    intervention: ParliamentaryIntervention, *,
    segments: tuple[MediaSegment, ...] = (),
    audio_path: str,
    audio_root: Path,
    audio_sha256: str,
    duration_seconds: float,
    rights_basis: str,
    rights_receipt_id: str,
    authorization: bool,
    consent_confirmed: bool,
    authorization_guard: Callable[[], None] | None = None,
    model_receipt_path: Path,
    source_variant_id: str,
    source_segment_id: str,
    source_variant_sha256: str,
    source_segment_sha256: str,
    language: str = "it",
    overlap_observed: bool = False,
    timeout_seconds: int = 120,
) -> AlignmentProposal:
    fallback = align_parliamentary_intervention(intervention, segments)
    if intervention.official_start_ms is not None:
        return AlignmentProposal("OFFICIAL_PRECEDENCE", fallback.blockers, (), None,
                                 fallback, {"method": "OFFICIAL_MEDIA_RANGE"})
    if (authorization is not True or rights_basis not in _RIGHTS_BASES
            or not isinstance(rights_receipt_id, str)
            or not _RECEIPT_ID.fullmatch(rights_receipt_id)
            or (rights_basis == "EXPLICIT_CONSENT" and consent_confirmed is not True)):
        raise AlignmentHold("WHISPERX_AUDIO_RIGHTS_UNVERIFIED")
    if (os.getenv(ENABLE) != "1" or platform.system() != "Linux"):
        raise AlignmentHold("WHISPERX_HOST_OR_OPT_IN_REQUIRED")
    # A boolean/receipt ID is historical evidence, not current source-use
    # authority. Recheck the caller's live rights decision around inference.
    if not callable(authorization_guard):
        raise AlignmentHold("WHISPERX_CURRENT_RIGHTS_GUARD_REQUIRED")

    def require_current_rights() -> None:
        try:
            if authorization_guard() is False:
                raise AlignmentHold("WHISPERX_SOURCE_RIGHTS_REVOKED")
        except Exception:
            # Do not leak an operator, policy or private-source error message.
            raise AlignmentHold("WHISPERX_SOURCE_RIGHTS_REVOKED") from None

    require_current_rights()
    if language not in {"it", "en"}:
        raise AlignmentHold("WHISPERX_LANGUAGE_UNSUPPORTED")
    if (type(duration_seconds) not in {float, int} or not math.isfinite(duration_seconds)
            or not 0 < duration_seconds <= MAX_AUDIO_SECONDS):
        raise AlignmentHold("WHISPERX_DURATION_INVALID")
    if (not isinstance(audio_sha256, str) or not _SHA256.fullmatch(audio_sha256)
            or not isinstance(audio_path, str) or not audio_path):
        raise AlignmentHold("WHISPERX_AUDIO_HASH_OR_PATH_INVALID")
    if (not source_variant_id or not source_segment_id
            or any(not isinstance(d, str) or not _SHA256.fullmatch(d)
                   for d in (source_variant_sha256, source_segment_sha256))):
        raise AlignmentHold("WHISPERX_SOURCE_BINDING_INVALID")
    if not 0 < timeout_seconds <= 120:
        raise AlignmentHold("WHISPERX_TIMEOUT_INVALID")
    try:
        model, receipt_sha = _receipt(model_receipt_path)
        if importlib.metadata.version("whisperx") != DONOR_VERSION:
            raise AlignmentHold("WHISPERX_VERSION_MISMATCH")
        root = audio_root.resolve(strict=True)
        source = _strict_file(Path(audio_path), root, label="AUDIO")
        observed_sha, _ = _digest_file(source, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")
        if observed_sha != audio_sha256:
            raise AlignmentHold("WHISPERX_AUDIO_HASH_MISMATCH")
        with wave.open(str(source), "rb") as wav:
            observed = wav.getnframes() / wav.getframerate()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2
                    or wav.getframerate() != 16000 or wav.getcomptype() != "NONE"
                    or not 0 < observed <= MAX_AUDIO_SECONDS
                    or abs(observed - duration_seconds) > .25):
                raise AlignmentHold("WHISPERX_WAV_CONTRACT_INVALID")
        with tempfile.TemporaryDirectory(prefix="dp-whisperx-") as temp:
            staged = Path(temp) / "input.wav"
            shutil.copyfile(source, staged)
            if _digest_file(staged, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")[0] != audio_sha256:
                raise AlignmentHold("WHISPERX_AUDIO_CHANGED")
            require_current_rights()  # rights may have changed during WAV staging
            env = {k: os.environ[k] for k in ("PATH", "HOME", "VIRTUAL_ENV", "PYTHONPATH",
                                             "LANG", "TMPDIR") if k in os.environ}
            env.update({ENABLE: "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1", "OMP_NUM_THREADS": "4"})
            # Pipes with capture_output=True collect unlimited child output in
            # the parent before any size check. Use a private, capped file and
            # discard stderr, which can contain private transcript/model data.
            with (Path(temp) / "worker.stdout").open("w+b") as out:
                with local_inference_slot():
                    child = subprocess.run(
                        [sys.executable, "-m", "dichiarazioni_pubbliche.whisperx_alignment_private",
                         "--worker"],
                        input=json.dumps({"receipt": str(model_receipt_path),
                                          "audio": str(staged), "duration": observed,
                                          "text": intervention.transcript_text, "language": language}),
                        stdout=out, stderr=subprocess.DEVNULL,
                        text=True, env=env, check=False,
                        preexec_fn=_limits, timeout=timeout_seconds,
                    )
                require_current_rights()  # no proposal if rights revoked mid-inference
                if child.returncode or os.fstat(out.fileno()).st_size > 256_000:
                    raise AlignmentHold("WHISPERX_ENGINE_FAILED")
                out.seek(0)
                payload = json.loads(out.read(256_001).decode("utf-8"))
        if not isinstance(payload, dict):
            raise AlignmentHold("WHISPERX_OUTPUT_INVALID")
        words = _parse_words(payload, text=intervention.transcript_text,
                             duration_ms=round(observed * 1000))
        sensitive = any(char.isdigit() for char in intervention.transcript_text)
        blockers = ["ACOUSTIC_ALIGNMENT_REQUIRES_HUMAN_AUDIO_REVIEW"]
        if sensitive:
            blockers.append("NUMERAL_REQUIRES_REVIEW")
        if overlap_observed:
            blockers.append("OVERLAPPING_SPEECH_REQUIRES_REVIEW")
        if fallback.status == "UNRESOLVED":
            blockers.extend(fallback.blockers)
        # Bind candidate replay identity to the actual accepted word alignment.
        # Inputs and model can be identical while word boundaries or scores differ.
        alignment_output_sha256 = hashlib.sha256(json.dumps(
            [(word.word, word.start_ms, word.end_ms, word.score) for word in words],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        provenance = {
            "adapter_version": VERSION, "donor_version": DONOR_VERSION,
            "donor_commit": DONOR_COMMIT, "model_id": model["model_id"],
            "model_revision": model["revision"], "model_sha256": model["files"][next(
                n for n in model["files"] if n.endswith(".safetensors"))],
            "model_receipt_sha256": receipt_sha, "audio_sha256": audio_sha256,
            "transcript_sha256": intervention.transcript_sha256,
            "source_variant_id": source_variant_id,
            "source_segment_id": source_segment_id,
            "source_variant_sha256": source_variant_sha256,
            "source_segment_sha256": source_segment_sha256,
            "rights_receipt_id": rights_receipt_id, "rights_basis": rights_basis,
            "score_kind": "upstream_ctc_heuristic_unvalidated",
            "alignment_output_sha256": alignment_output_sha256,
        }
        digest = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
        candidate = TranscriptCandidate(
            candidate_id="alignment-candidate:" + digest,
            provider_id=PROVIDER, text=intervention.transcript_text,
            start_ms=words[0].start_ms, end_ms=words[-1].end_ms,
            source_kind="UNVERIFIED",
        )
        return AlignmentProposal("REVIEW_CANDIDATE", tuple(dict.fromkeys(blockers)),
                                 words, candidate, fallback, provenance)
    except LocalInferenceBusy as exc:
        raise AlignmentHold("WHISPERX_LOCAL_INFERENCE_BUSY") from exc
    except subprocess.TimeoutExpired as exc:
        raise AlignmentHold("WHISPERX_TIMEOUT") from exc
    except (OSError, EOFError, ZeroDivisionError, wave.Error,
            importlib.metadata.PackageNotFoundError, json.JSONDecodeError,
            UnicodeError) as exc:
        raise AlignmentHold("WHISPERX_INPUT_OR_RUNTIME_INVALID") from exc


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
