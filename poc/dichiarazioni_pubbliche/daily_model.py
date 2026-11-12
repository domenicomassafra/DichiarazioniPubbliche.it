"""DP-638 — the OmniRoute model client used for extraction and verdicts."""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.daily_text import DailyMachineError
from dichiarazioni_pubbliche.source_watcher import fetch_bytes, validate_discovery_url

DEFAULT_USER_AGENT = "DichiarazioniPubbliche/1.0 (+https://dichiarazionipubbliche.it)"

# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelReply:
    model: str
    text: str
    usage: dict[str, Any]
    latency_seconds: float
    operation: str


class ModelClient:
    """OpenAI-compatible client for the OmniRoute gateway on the MiniPC."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = 180.0,
        opener: Callable[[urllib.request.Request, float], tuple[int, bytes]] | None = None,
    ) -> None:
        if not api_key:
            raise DailyMachineError("OMNIROUTE_API_KEY_MISSING")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener or _http_open
        self.calls: list[ModelReply] = []

    def _post(self, path: str, payload: dict[str, Any], *, content_type: str = "application/json") -> tuple[int, bytes]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
            method="POST",
        )
        return self._opener(request, self.timeout)

    def complete(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
        *,
        operation: str,
        max_tokens: int = 1600,
        temperature: float = 0.0,
    ) -> ModelReply:
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        started = time.monotonic()
        last_error: Exception | None = None
        status, raw = 0, b""
        for attempt in range(2):
            try:
                status, raw = self._post("/chat/completions", payload)
            except DailyMachineError as exc:
                last_error = exc
                if attempt == 0:
                    continue
                raise
            if status in {502, 503, 504} and attempt == 0:
                continue
            break
        latency = time.monotonic() - started
        if status != 200:
            if last_error is not None:
                raise last_error
            raise DailyMachineError(f"MODEL_HTTP_{status}")
        try:
            body = json.loads(raw.decode("utf-8", "replace"))
        except ValueError as exc:
            raise DailyMachineError("MODEL_RESPONSE_NOT_JSON") from exc
        if isinstance(body, dict) and body.get("error"):
            raise DailyMachineError("MODEL_ERROR:" + str(body["error"])[:120])
        choices = body.get("choices") or []
        if not choices:
            raise DailyMachineError("MODEL_RESPONSE_NO_CHOICES")
        text = str((choices[0].get("message") or {}).get("content") or "")
        reply = ModelReply(
            model=str(body.get("model") or model),
            text=text,
            usage=dict(body.get("usage") or {}),
            latency_seconds=round(latency, 3),
            operation=operation,
        )
        self.calls.append(reply)
        return reply

    def transcribe(self, audio_path: Path, *, model: str, operation: str = "AUDIO_TRANSCRIPTION") -> str:
        boundary = "----dp638" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        payload = audio_path.read_bytes()
        parts: list[bytes] = []
        for name, value in (("model", model), ("response_format", "json")):
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
            )
        parts.append(
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"{audio_path.name}\"\r\nContent-Type: audio/mpeg\r\n\r\n"
            ).encode()
        )
        parts.append(payload)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)
        request = urllib.request.Request(
            f"{self.base_url}/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        started = time.monotonic()
        status, raw = self._opener(request, self.timeout)
        latency = time.monotonic() - started
        if status != 200:
            raise DailyMachineError(f"ASR_HTTP_{status}")
        try:
            decoded = json.loads(raw.decode("utf-8", "replace"))
        except ValueError as exc:
            raise DailyMachineError("ASR_RESPONSE_NOT_JSON") from exc
        text = str(decoded.get("text") or "").strip()
        self.calls.append(
            ModelReply(
                model=model,
                text=text,
                usage={"audio_seconds": None},
                latency_seconds=round(latency, 3),
                operation=operation,
            )
        )
        return text


def _http_open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()[:2000]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DailyMachineError(f"HTTP_UNAVAILABLE:{type(exc).__name__}") from exc


def fetch_text(
    url: str,
    *,
    timeout: float = 25.0,
    max_bytes: int = 3_000_000,
    opener: Callable[[urllib.request.Request, float], tuple[int, bytes]] | None = None,
) -> tuple[int, str]:
    try:
        if opener is not None:
            safe_url = validate_discovery_url(url)
            status, raw = opener(urllib.request.Request(safe_url), timeout)
            if len(raw) > max_bytes:
                raise DailyMachineError("HTTP_RESPONSE_TOO_LARGE")
            return status, raw.decode("utf-8", "replace") if status == 200 else ""
        fetched = fetch_bytes(url, timeout=timeout, max_response_bytes=max_bytes)
        return fetched.status_code, fetched.body.decode(fetched.charset or "utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except (ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DailyMachineError(f"PUBLIC_FETCH_REFUSED:{type(exc).__name__}") from exc
