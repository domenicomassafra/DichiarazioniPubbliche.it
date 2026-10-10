"""Opt-in, offline whisper.cpp transcription of already authorized bounded WAVs.

This adapter never discovers, downloads, or approves audio/model files. The caller
must supply a private local audio root, a trusted CLI, and an expected model hash.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.remote_asr import AsrRequestRejected, AsrResult, AsrSegment


PROVIDER_ID = "whisper-cpp-local"
ROUTE = "local/whisper.cpp"
MAX_AUDIO_SECONDS = 30.0
MAX_AUDIO_BYTES = 1_000_044  # 30 seconds of 16 kHz, mono, 16-bit PCM plus WAV header.
MAX_MODEL_BYTES = 600 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_ID = re.compile(r"[A-Za-z0-9:_./-]{8,160}\Z")
_RIGHTS_BASES = frozenset({"PUBLIC_DOMAIN", "LICENSED", "OWNER_AUTHORIZED", "EXPLICIT_CONSENT"})


def _digest_file(path: Path, *, max_bytes: int, label: str) -> tuple[str, int]:
    size = path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise AsrRequestRejected(f"LOCAL_ASR_{label}_SIZE_INVALID")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest(), size


def _strict_file(path: Path, root: Path, *, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AsrRequestRejected(f"LOCAL_ASR_{label}_PATH_INVALID")
    resolved = path.resolve(strict=True)
    if resolved == root or not resolved.is_relative_to(root):
        raise AsrRequestRejected(f"LOCAL_ASR_{label}_PATH_INVALID")
    return resolved


def parse_whisper_cpp_json(
    payload: dict[str, Any], *, duration_seconds: float, language: str,
    model_sha256: str, input_sha256: str,
) -> AsrResult:
    raw = payload.get("transcription")
    if not isinstance(raw, list) or not raw:
        raise AsrRequestRejected("LOCAL_ASR_SEGMENTS_MISSING")
    segments: list[AsrSegment] = []
    last_end = 0
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("offsets"), dict):
            raise AsrRequestRejected("LOCAL_ASR_TIMESTAMPS_INVALID")
        offsets = item["offsets"]
        start, end = offsets.get("from"), offsets.get("to")
        if (type(start) is not int or type(end) is not int or start < last_end
                or end <= start or end > duration_seconds * 1000 + 250):
            raise AsrRequestRejected("LOCAL_ASR_TIMESTAMPS_INVALID")
        value = item.get("text")
        if not isinstance(value, str) or not value.strip():
            raise AsrRequestRejected("LOCAL_ASR_EMPTY_SEGMENT")
        segments.append(AsrSegment(len(segments), start, end, value.strip()))
        last_end = end
    text = " ".join(s.text for s in segments)
    return AsrResult(
        provider_id=PROVIDER_ID,
        model_id=f"ggml-sha256:{model_sha256}",
        request_id="local:" + hashlib.sha256(
            (input_sha256 + model_sha256 + language).encode()
        ).hexdigest(),
        language=language,
        duration_seconds=duration_seconds,
        text=text,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        segments=tuple(segments),
        raw_response=payload,
    )


class WhisperCppLocalTranscriber:
    def __init__(
        self, *, audio_root: Path | None, cli_path: Path | None,
        model_path: Path | None, model_sha256: str | None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.audio_root = audio_root
        self.cli_path = cli_path
        self.model_path = model_path
        self.model_sha256 = model_sha256
        self.timeout_seconds = timeout_seconds

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
        if (type(duration_seconds) not in {int, float} or not 0 < duration_seconds <= MAX_AUDIO_SECONDS):
            raise AsrRequestRejected("LOCAL_ASR_DURATION_INVALID")
        if not isinstance(input_sha256, str) or not _SHA256.fullmatch(input_sha256):
            raise AsrRequestRejected("LOCAL_ASR_INPUT_HASH_INVALID")
        if (self.audio_root is None or self.cli_path is None or self.model_path is None
                or not isinstance(self.model_sha256, str)
                or not _SHA256.fullmatch(self.model_sha256)):
            raise AsrRequestRejected("LOCAL_ASR_RUNTIME_NOT_CONFIGURED")
        try:
            root = self.audio_root.resolve(strict=True)
            wav_path = _strict_file(Path(audio_path), root, label="AUDIO")
            model = self.model_path.resolve(strict=True)
            cli = self.cli_path.resolve(strict=True)
            if not cli.is_file() or not cli.stat().st_mode & 0o111 or not model.is_file():
                raise AsrRequestRejected("LOCAL_ASR_RUNTIME_NOT_CONFIGURED")
            digest, count = _digest_file(wav_path, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")
            if digest != input_sha256:
                raise AsrRequestRejected("LOCAL_ASR_INPUT_HASH_MISMATCH")
            model_digest, _ = _digest_file(model, max_bytes=MAX_MODEL_BYTES, label="MODEL")
            if model_digest != self.model_sha256:
                raise AsrRequestRejected("LOCAL_ASR_MODEL_HASH_MISMATCH")
            with wave.open(str(wav_path), "rb") as audio:
                observed_seconds = audio.getnframes() / audio.getframerate()
                if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                        or audio.getframerate() != 16000 or audio.getcomptype() != "NONE"
                        or not 0 < observed_seconds <= MAX_AUDIO_SECONDS
                        or abs(observed_seconds - duration_seconds) > 0.25):
                    raise AsrRequestRejected("LOCAL_ASR_WAV_CONTRACT_INVALID")
            # Immutable job-local copy prevents concurrent modification of the original
            # private audio after hash validation; all derived artifacts are transient.
            with tempfile.TemporaryDirectory(prefix="dp-local-asr-") as tmp:
                staged = Path(tmp) / "input.wav"
                shutil.copyfile(wav_path, staged)
                staged_digest, _ = _digest_file(staged, max_bytes=MAX_AUDIO_BYTES, label="AUDIO")
                if staged_digest != input_sha256:
                    raise AsrRequestRejected("LOCAL_ASR_INPUT_CHANGED")
                output = Path(tmp) / "result"
                try:
                    finished = subprocess.run(
                        [str(cli), "-m", str(model), "-f", str(staged),
                         "-l", language, "-ojf", "-of", str(output),
                         "-ng", "-t", "4", "-np"],
                        timeout=self.timeout_seconds, capture_output=True, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise AsrRequestRejected("LOCAL_ASR_TIMEOUT") from exc
                if finished.returncode != 0:
                    raise AsrRequestRejected("LOCAL_ASR_ENGINE_FAILED")
                data_path = output.with_suffix(".json")
                if not data_path.is_file() or data_path.stat().st_size > 256_000:
                    raise AsrRequestRejected("LOCAL_ASR_OUTPUT_MISSING_OR_OVERSIZED")
                try:
                    payload = json.loads(data_path.read_text(encoding="utf-8"))
                except (UnicodeError, ValueError) as exc:
                    raise AsrRequestRejected("LOCAL_ASR_OUTPUT_INVALID") from exc
            if not isinstance(payload, dict):
                raise AsrRequestRejected("LOCAL_ASR_OUTPUT_INVALID")
            return parse_whisper_cpp_json(
                payload, duration_seconds=observed_seconds, language=language,
                model_sha256=model_digest, input_sha256=staged_digest,
            )
        except (OSError, EOFError, wave.Error, ZeroDivisionError) as exc:
            raise AsrRequestRejected("LOCAL_ASR_INPUT_OR_RUNTIME_INVALID") from exc
