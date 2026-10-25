"""Private Giuliani benchmark transport. Caller performs source and route preflight."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_runtime import LOCAL_GATEWAY_URLS, matches_returned_model


def _read_env_file(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def call_omniroute(
    *,
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    max_tokens: int = 4096,
    timeout_seconds: float = 120.0,
) -> tuple[dict[str, Any], float]:
    if base_url.rstrip("/") not in LOCAL_GATEWAY_URLS:
        raise RuntimeError("DP202_GATEWAY_UNAUTHORIZED")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Extract claims faithfully from the supplied transcript. Return JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    elapsed = time.monotonic() - started
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"OmniRoute returned HTTP {status} with non-JSON body: "
            f"{raw.decode('utf-8', 'replace')[:500]}"
        ) from exc
    if status != 200:
        error = decoded.get("error", decoded) if isinstance(decoded, dict) else decoded
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or error)
        else:
            message = str(error)
        raise RuntimeError(f"OmniRoute HTTP {status}: {message[:1000]}")
    if not isinstance(decoded, dict):
        raise RuntimeError("OmniRoute response is not a JSON object")
    if not matches_returned_model(model, decoded.get("model")):
        raise RuntimeError("DP202_MODEL_SUBSTITUTED")
    request_id = decoded.get("id")
    usage = decoded.get("usage")
    if not isinstance(request_id, str) or not request_id.strip():
        raise RuntimeError("DP202_REQUEST_ID_MISSING")
    if (
        not isinstance(usage, dict)
        or type(usage.get("prompt_tokens")) is not int
        or usage["prompt_tokens"] <= 0
        or type(usage.get("completion_tokens")) is not int
        or usage["completion_tokens"] < 0
    ):
        raise RuntimeError("DP202_USAGE_MISSING")
    cost = _cost_from_response(decoded)
    if cost is not None and cost != 0:
        raise RuntimeError("DP202_UNEXPECTED_PROVIDER_COST")
    return decoded, elapsed


def response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("OmniRoute response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        if chunks:
            return "".join(chunks)
    raise ValueError("OmniRoute response choice has no textual content")


def _cost_from_response(response: dict[str, Any]) -> float | None:
    candidates: list[Any] = []
    usage = response.get("usage")
    if isinstance(usage, dict):
        candidates.extend(
            usage.get(key)
            for key in ("cost", "cost_usd", "total_cost", "total_cost_usd")
        )
    candidates.extend(
        response.get(key)
        for key in ("cost", "cost_usd", "total_cost", "total_cost_usd")
    )
    observed: list[float] = []
    for value in candidates:
        if value is None:
            continue
        if type(value) not in (int, float, str):
            raise RuntimeError("DP202_COST_UNVERIFIABLE")
        try:
            amount = float(value)
        except ValueError:
            raise RuntimeError("DP202_COST_UNVERIFIABLE") from None
        if not math.isfinite(amount):
            raise RuntimeError("DP202_COST_UNVERIFIABLE")
        observed.append(amount)
    return next((amount for amount in observed if amount != 0), observed[0] if observed else None)
