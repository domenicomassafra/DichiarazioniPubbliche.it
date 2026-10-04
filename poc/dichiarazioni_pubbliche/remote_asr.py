from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class AsrError(RuntimeError):
    pass


class AsrRateLimited(AsrError):
    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(retry_after_seconds, 1)


class AsrAccessDenied(AsrError):
    pass


class AsrRequestRejected(AsrError):
    pass


class AsrTransientError(AsrError):
    pass


@dataclass(frozen=True)
class AsrSegment:
    segment_index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class AsrResult:
    provider_id: str
    model_id: str
    request_id: str | None
    language: str
    duration_seconds: float
    text: str
    text_sha256: str
    segments: tuple[AsrSegment, ...]
    raw_response: dict[str, Any]


def _multipart_body(
    fields: list[tuple[str, str]],
    *,
    seed: str,
) -> tuple[bytes, str]:
    boundary = "dichiarazionipubbliche-" + hashlib.sha256(seed.encode()).hexdigest()[:24]
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                ).encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def _retry_after(headers) -> int:
    raw = headers.get("Retry-After") if headers else None
    if not raw:
        return 60
    try:
        return max(int(float(raw)), 1)
    except (TypeError, ValueError):
        return 60


def parse_groq_verbose_response(
    payload: dict[str, Any],
    *,
    provider_id: str,
    model_id: str,
) -> AsrResult:
    text = str(payload.get("text") or "").strip()
    raw_segments = payload.get("segments") or []
    if not text:
        raise AsrRequestRejected("ASR_RESPONSE_EMPTY_TEXT")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise AsrRequestRejected("ASR_RESPONSE_MISSING_SEGMENT_TIMESTAMPS")

    segments: list[AsrSegment] = []
    for index, item in enumerate(raw_segments):
        if not isinstance(item, dict):
            continue
        value = str(item.get("text") or "").strip()
        if not value:
            continue
        try:
            start = max(float(item.get("start") or 0), 0.0)
            end = max(float(item.get("end") or start), start)
        except (TypeError, ValueError) as exc:
            raise AsrRequestRejected("ASR_RESPONSE_INVALID_TIMESTAMPS") from exc
        segments.append(
            AsrSegment(
                segment_index=len(segments),
                start_ms=int(round(start * 1000)),
                end_ms=int(round(end * 1000)),
                text=value,
            )
        )
    if not segments:
        raise AsrRequestRejected("ASR_RESPONSE_NO_USABLE_SEGMENTS")

    duration_raw = payload.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError):
        duration = max(segment.end_ms for segment in segments) / 1000.0
    request_id = None
    x_groq = payload.get("x_groq")
    if isinstance(x_groq, dict) and x_groq.get("id"):
        request_id = str(x_groq["id"])
    return AsrResult(
        provider_id=provider_id,
        model_id=model_id,
        request_id=request_id,
        language=str(payload.get("language") or "it"),
        duration_seconds=max(duration, 0.0),
        text=text,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        segments=tuple(segments),
        raw_response=payload,
    )


class GroqUrlTranscriber:
    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = GROQ_TRANSCRIPTIONS_URL,
        timeout_seconds: float = 180.0,
    ) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY_MISSING")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def transcribe_url(
        self,
        audio_url: str,
        *,
        model_id: str = "whisper-large-v3-turbo",
        provider_id: str = "groq-whisper-large-v3-turbo",
        language: str = "it",
    ) -> AsrResult:
        fields = [
            ("url", audio_url),
            ("model", model_id),
            ("language", language),
            ("response_format", "verbose_json"),
            ("timestamp_granularities[]", "segment"),
            ("temperature", "0"),
        ]
        body, boundary = _multipart_body(
            fields, seed=f"{audio_url}\0{model_id}\0{language}"
        )
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "dichiarazioni-pubbliche/0.0.1",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status == 429:
                raise AsrRateLimited(
                    "GROQ_RATE_LIMITED",
                    retry_after_seconds=_retry_after(exc.headers),
                ) from exc
            if status in {401, 403}:
                raise AsrAccessDenied(f"GROQ_ACCESS_DENIED:{status}") from exc
            if 400 <= status < 500:
                raise AsrRequestRejected(f"GROQ_REQUEST_REJECTED:{status}") from exc
            raise AsrTransientError(f"GROQ_UPSTREAM_ERROR:{status}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise AsrTransientError(f"GROQ_NETWORK_ERROR:{type(exc).__name__}") from exc

        if status != 200:
            raise AsrTransientError(f"GROQ_UNEXPECTED_STATUS:{status}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AsrTransientError("GROQ_NON_JSON_RESPONSE") from exc
        if not isinstance(payload, dict):
            raise AsrTransientError("GROQ_INVALID_RESPONSE_SHAPE")
        return parse_groq_verbose_response(
            payload,
            provider_id=provider_id,
            model_id=model_id,
        )
