"""Private, offline faster-whisper CPU adapter for explicitly authorized WAV files.

Model weights and audio are operator supplied. No acquisition, automatic model
download, publication, or implicit fallback is performed here.
"""
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
from pathlib import Path

from dichiarazioni_pubbliche.local_asr import (
    MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, _RIGHTS_BASES, _RECEIPT_ID,
    _SHA256, _digest_file, _strict_file,
)
from dichiarazioni_pubbliche.local_inference_guard import LocalInferenceBusy, local_inference_slot
from dichiarazioni_pubbliche.remote_asr import (
    AsrRequestRejected, AsrResult, AsrSegment, AsrTransientError,
)


PROVIDER_ID = "faster-whisper-small-local"
ROUTE = "local/faster-whisper-small"
DONOR_VERSION = "1.2.1"
MAX_MODEL_BYTES = 950 * 1024 * 1024
MAX_MODEL_FILES = 96
MAX_CPU_SECONDS = 100
MAX_WALL_SECONDS = 120
MAX_ADDRESS_SPACE_BYTES = 6 * 1024**3
MAX_OUTPUT_BYTES = 256_000
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"})
_FILE_EXT = frozenset({".bin", ".json", ".txt", ".model", ".vocab", ".md"})


def _verified_model_receipt(receipt_path: Path) -> tuple[dict, str]:
    if (not receipt_path.is_absolute() or ".." in receipt_path.parts
            or any(part.is_symlink() for part in (receipt_path, *receipt_path.parents))
            or not receipt_path.is_file() or receipt_path.stat().st_size > 16_384):
        raise AsrRequestRejected("FASTER_WHISPER_RECEIPT_INVALID")
    raw = receipt_path.read_bytes()
    try:
        receipt = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AsrRequestRejected("FASTER_WHISPER_RECEIPT_INVALID") from exc
    if (not isinstance(receipt, dict)
            or receipt.get("model_id") != "Systran/faster-whisper-small"
            or not isinstance(receipt.get("revision"), str)
            or not _COMMIT.fullmatch(receipt["revision"])
            or receipt.get("license_reviewed") is not True
            or receipt.get("license_spdx") not in _LICENSES
            or not isinstance(receipt.get("license_source_url"), str)
            or not receipt["license_source_url"].startswith("https://")
            or not isinstance(receipt.get("model_dir"), str)):
        raise AsrRequestRejected("FASTER_WHISPER_MODEL_RIGHTS_UNVERIFIED")
    root = Path(receipt["model_dir"])
    files = receipt.get("files")
    if (not root.is_absolute() or ".." in root.parts
            or any(part.is_symlink() for part in (root, *root.parents))
            or not root.is_dir()
            or not isinstance(files, dict) or not 2 <= len(files) <= MAX_MODEL_FILES
            or "model.bin" not in files or "LICENSE" not in files
            or "config.json" not in files):
        raise AsrRequestRejected("FASTER_WHISPER_MODEL_INVENTORY_INVALID")
    total = 0
    for name, digest in files.items():
        if (not isinstance(name, str) or not name or name.startswith("/")
                or "\\" in name or any(p in {"", ".", ".."} for p in name.split("/"))
                or (Path(name).suffix not in _FILE_EXT and name != "LICENSE")
                or not isinstance(digest, str) or not _SHA256.fullmatch(digest)):
            raise AsrRequestRejected("FASTER_WHISPER_MODEL_INVENTORY_INVALID")
        item = root / name
        if item.is_symlink() or not item.is_file():
            raise AsrRequestRejected("FASTER_WHISPER_MODEL_INVENTORY_INVALID")
        actual, size = _digest_file(item, max_bytes=MAX_MODEL_BYTES, label="MODEL")
        total += size
        if total > MAX_MODEL_BYTES or actual != digest:
            raise AsrRequestRejected("FASTER_WHISPER_MODEL_HASH_OR_BUDGET_INVALID")
    actual_names: set[str] = set()
    for folder, dirs, names in os.walk(root, followlinks=False):
        if any((Path(folder) / name).is_symlink() for name in dirs):
            raise AsrRequestRejected("FASTER_WHISPER_MODEL_INVENTORY_INVALID")
        actual_names.update((Path(folder) / name).relative_to(root).as_posix() for name in names)
    if actual_names != set(files):
        raise AsrRequestRejected("FASTER_WHISPER_MODEL_INVENTORY_INVALID")
    return receipt, hashlib.sha256(raw).hexdigest()


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _worker() -> None:
    if (os.getenv("DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_ENABLED") != "1"
            or platform.system() != "Linux" or platform.node() != "udodo"):
        raise AsrRequestRejected("FASTER_WHISPER_OPT_IN_OR_HOST_REQUIRED")
    request = json.loads(sys.stdin.read(4096))
    if not isinstance(request, dict) or not isinstance(request.get("receipt"), str):
        raise AsrRequestRejected("FASTER_WHISPER_WORKER_INPUT_INVALID")
    receipt, _ = _verified_model_receipt(Path(request["receipt"]))
    if importlib.metadata.version("faster-whisper") != DONOR_VERSION:
        raise AsrRequestRejected("FASTER_WHISPER_VERSION_MISMATCH")
    # Offline before importing upstream. Only an operator-pinned local directory.
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1", "OMP_NUM_THREADS": "4"})
    from faster_whisper import WhisperModel

    model = WhisperModel(receipt["model_dir"], device="cpu", compute_type="int8",
                         cpu_threads=4, num_workers=1, local_files_only=True)
    # Silero VAD is built into upstream, but its separately bundled weights
    # require their own license review. Avoid another segmentation pipeline.
    segments, info = model.transcribe(request["audio"], language=request["language"],
                                      beam_size=5, vad_filter=False,
                                      condition_on_previous_text=False)
    entries = [{"start": item.start, "end": item.end, "text": item.text}
               for item in segments]
    print(json.dumps({"segments": entries, "language": info.language},
                     ensure_ascii=False, separators=(",", ":")))


def _parse_result(payload: dict, *, duration: float, language: str,
                  input_sha: str, receipt: dict, receipt_sha: str) -> AsrResult:
    entries = payload.get("segments")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 200:
        raise AsrRequestRejected("FASTER_WHISPER_SEGMENTS_INVALID")
    if payload.get("language") != language:
        raise AsrRequestRejected("FASTER_WHISPER_LANGUAGE_MISMATCH")
    parsed: list[AsrSegment] = []
    last_end = 0
    for value in entries:
        if not isinstance(value, dict):
            raise AsrRequestRejected("FASTER_WHISPER_SEGMENTS_INVALID")
        start, end, text = value.get("start"), value.get("end"), value.get("text")
        if (type(start) not in {float, int} or type(end) not in {float, int}
                or not math.isfinite(start) or not math.isfinite(end)
                or not isinstance(text, str) or not text.strip() or len(text) > 2000):
            raise AsrRequestRejected("FASTER_WHISPER_SEGMENTS_INVALID")
        begin_ms, end_ms = round(start * 1000), round(end * 1000)
        if begin_ms < last_end or end_ms <= begin_ms or end_ms > duration * 1000 + 250:
            raise AsrRequestRejected("FASTER_WHISPER_TIMESTAMPS_INVALID")
        parsed.append(AsrSegment(len(parsed), begin_ms, end_ms, text.strip()))
        last_end = end_ms
    text = " ".join(segment.text for segment in parsed)
    model_sha = receipt["files"]["model.bin"]
    return AsrResult(
        provider_id=PROVIDER_ID,
        model_id=f"{receipt['model_id']}@{receipt['revision']}#sha256:{model_sha}",
        request_id="local:" + hashlib.sha256(
            (input_sha + model_sha + receipt_sha + language).encode()).hexdigest(),
        language=language, duration_seconds=duration, text=text,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        segments=tuple(parsed),
        raw_response={"segments": entries, "language": language,
                      "model_receipt_sha256": receipt_sha,
                      "publication_approved": False},
    )


class FasterWhisperLocalTranscriber:
    def __init__(self, *, audio_root: Path, model_receipt_path: Path,
                 timeout_seconds: float = MAX_WALL_SECONDS) -> None:
        self.audio_root = audio_root
        self.model_receipt_path = model_receipt_path
        self.timeout_seconds = min(timeout_seconds, MAX_WALL_SECONDS)
        self.model_sha256: str | None = None

    def transcribe(self, *, audio_path: str, input_sha256: str,
                   rights_basis: str, rights_receipt_id: str,
                   authorization: bool, consent_confirmed: bool,
                   duration_seconds: float, language: str = "it") -> AsrResult:
        if (authorization is not True or rights_basis not in _RIGHTS_BASES
                or not isinstance(rights_receipt_id, str)
                or not _RECEIPT_ID.fullmatch(rights_receipt_id)
                or (rights_basis == "EXPLICIT_CONSENT" and consent_confirmed is not True)):
            raise AsrRequestRejected("LOCAL_ASR_RIGHTS_NOT_AUTHORIZED")
        if language not in {"it", "en"}:
            raise AsrRequestRejected("LOCAL_ASR_LANGUAGE_NOT_ALLOWED")
        if (type(duration_seconds) not in {float, int}
                or not math.isfinite(duration_seconds)
                or not 0 < duration_seconds <= MAX_AUDIO_SECONDS):
            raise AsrRequestRejected("LOCAL_ASR_DURATION_INVALID")
        if not isinstance(input_sha256, str) or not _SHA256.fullmatch(input_sha256):
            raise AsrRequestRejected("LOCAL_ASR_INPUT_HASH_INVALID")
        if not isinstance(audio_path, str) or not audio_path:
            raise AsrRequestRejected("LOCAL_ASR_AUDIO_PATH_INVALID")
        if (os.getenv("DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_ENABLED") != "1"
                or platform.system() != "Linux" or platform.node() != "udodo"):
            raise AsrRequestRejected("FASTER_WHISPER_OPT_IN_OR_HOST_REQUIRED")
        try:
            receipt, receipt_sha = _verified_model_receipt(self.model_receipt_path)
            self.model_sha256 = receipt["files"]["model.bin"]
            root = self.audio_root.resolve(strict=True)
            source = _strict_file(Path(audio_path), root, label="AUDIO")
            digest, _ = _digest_file(source, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")
            if digest != input_sha256:
                raise AsrRequestRejected("LOCAL_ASR_INPUT_HASH_MISMATCH")
            with wave.open(str(source), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
                if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                        or audio.getframerate() != 16000 or audio.getcomptype() != "NONE"
                        or not 0 < duration <= MAX_AUDIO_SECONDS
                        or abs(duration - duration_seconds) > 0.25):
                    raise AsrRequestRejected("LOCAL_ASR_WAV_CONTRACT_INVALID")
            if importlib.metadata.version("faster-whisper") != DONOR_VERSION:
                raise AsrRequestRejected("FASTER_WHISPER_VERSION_MISMATCH")
            with tempfile.TemporaryDirectory(prefix="dp-faster-whisper-") as directory:
                staged = Path(directory) / "input.wav"
                shutil.copyfile(source, staged)
                if _digest_file(staged, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")[0] != input_sha256:
                    raise AsrRequestRejected("LOCAL_ASR_INPUT_CHANGED")
                child_env = {name: os.environ[name] for name in
                             ("PATH", "HOME", "VIRTUAL_ENV", "PYTHONPATH", "LANG", "TMPDIR")
                             if name in os.environ}
                child_env.update({"DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_ENABLED": "1",
                                  "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                                  "HF_HUB_DISABLE_TELEMETRY": "1", "OMP_NUM_THREADS": "4"})
                # The subprocess may emit untrusted transcript/error bytes.
                # Avoid capture_output pipes: they allocate unbounded memory
                # in the parent before any post-hoc size check can run.
                with tempfile.TemporaryFile(mode="w+b") as output:
                    try:
                        with local_inference_slot():
                            result = subprocess.run(
                                [sys.executable, "-m", "dichiarazioni_pubbliche.faster_whisper_local", "--worker"],
                                input=json.dumps({"audio": str(staged),
                                                  "receipt": str(self.model_receipt_path),
                                                  "language": language}),
                                stdout=output, stderr=subprocess.DEVNULL,
                                text=True, check=False, env=child_env,
                                preexec_fn=_limits, timeout=self.timeout_seconds,
                            )
                    except LocalInferenceBusy as exc:
                        raise AsrTransientError("LOCAL_INFERENCE_BUSY") from exc
                    except subprocess.TimeoutExpired as exc:
                        raise AsrRequestRejected("FASTER_WHISPER_TIMEOUT") from exc
                    if result.returncode != 0 or output.tell() > MAX_OUTPUT_BYTES:
                        raise AsrRequestRejected("FASTER_WHISPER_ENGINE_FAILED")
                    output.seek(0)
                    payload = json.loads(output.read(MAX_OUTPUT_BYTES + 1))
            if not isinstance(payload, dict):
                raise AsrRequestRejected("FASTER_WHISPER_OUTPUT_INVALID")
            return _parse_result(payload, duration=duration, language=language,
                                 input_sha=digest, receipt=receipt, receipt_sha=receipt_sha)
        except (OSError, EOFError, wave.Error, ZeroDivisionError, ValueError,
                subprocess.SubprocessError,
                importlib.metadata.PackageNotFoundError) as exc:
            raise AsrRequestRejected("FASTER_WHISPER_INPUT_OR_RUNTIME_INVALID") from exc


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
