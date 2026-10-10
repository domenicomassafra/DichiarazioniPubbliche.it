from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_contract import ClaimType


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "claim-extraction.v1.json"
DEFAULT_BASE_URL = "http://127.0.0.1:20128"


@dataclass(frozen=True)
class ExtractedAtomicClaim:
    normalized_claim: str
    claim_type: str
    check_worthy: bool
    numeric_sensitive: bool
    speaker: str
    source_timestamp: str
    source_segment_indices: tuple[int, ...]


@dataclass(frozen=True)
class ClaimRuntimeProbe:
    healthy: bool
    reason: str
    latency_seconds: float
    http_status: int | None


@dataclass(frozen=True)
class ClaimExtractionResult:
    claims: tuple[ExtractedAtomicClaim, ...]
    request_id: str | None
    latency_seconds: float
    usage: dict[str, Any] | None
    observed_cost_usd: float | None


def load_claim_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text())


def deterministic_claim_id(
    *,
    content_id: str,
    window_sha256: str,
    prompt_version: str,
    model: str,
    claim: ExtractedAtomicClaim,
) -> str:
    material = {
        "content_id": content_id,
        "window_sha256": window_sha256,
        "prompt_version": prompt_version,
        "model": model,
        "normalized_claim": claim.normalized_claim,
        "claim_type": claim.claim_type,
        "check_worthy": claim.check_worthy,
        "numeric_sensitive": claim.numeric_sensitive,
        "speaker": claim.speaker,
        "source_timestamp": claim.source_timestamp,
        "source_segment_indices": list(claim.source_segment_indices),
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "claim:" + hashlib.sha256(encoded).hexdigest()


def estimate_claim_request_cost(
    *,
    estimated_input_tokens: int,
    max_output_tokens: int,
    max_usd_per_1k_total_tokens: float | None,
) -> float | None:
    if max_usd_per_1k_total_tokens is None:
        return None
    if max_usd_per_1k_total_tokens < 0:
        raise ValueError("claim cost rate must be >= 0")
    total = max(int(estimated_input_tokens), 0) + max(int(max_output_tokens), 0)
    return round(total / 1000.0 * max_usd_per_1k_total_tokens, 6)


def _extract_cost(response: dict[str, Any]) -> float | None:
    values: list[Any] = []
    usage = response.get("usage")
    if isinstance(usage, dict):
        values.extend(
            usage.get(key)
            for key in ("cost", "cost_usd", "total_cost", "total_cost_usd")
        )
    values.extend(
        response.get(key)
        for key in ("cost", "cost_usd", "total_cost", "total_cost_usd")
    )
    for value in values:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def _response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("CLAIM_RESPONSE_NO_CHOICES")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = [
            item["text"]
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if chunks:
            return "".join(chunks)
    raise ValueError("CLAIM_RESPONSE_NO_TEXT")


def _json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        value = re.sub(
            "^" + re.escape(fence) + r"(?:json)?\s*",
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"\s*" + re.escape(fence) + "$", "", value, count=1)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("CLAIM_RESPONSE_NOT_OBJECT")
    return parsed


class OmniRouteClaimClient:
    provider_id = "omniroute"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.config = config or load_claim_config()

    @property
    def model(self) -> str:
        return str(self.config["model"])

    @property
    def prompt_version(self) -> str:
        return str(self.config["prompt_version"])

    @property
    def max_output_tokens(self) -> int:
        return int(self.config["max_output_tokens"])

    def _post(self, prompt: str, *, max_tokens: int) -> tuple[dict[str, Any], float]:
        if not self.api_key:
            raise RuntimeError("OMNIROUTE_API_KEY_MISSING")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max(int(max_tokens), 1),
            "stream": False,
        }
        request = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        status = 0
        limit = int(self.config.get("max_response_bytes", 1_048_576))
        try:
            with urllib.request.urlopen(
                request,
                timeout=float(self.config.get("request_timeout_seconds", 60)),
            ) as response:
                status = response.status
                raw = response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read(min(limit + 1, 64_000))
        elapsed = time.monotonic() - started
        if len(raw) > limit:
            raise RuntimeError("OMNIROUTE_RESPONSE_TOO_LARGE")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OMNIROUTE_NON_JSON_HTTP_{status}") from exc
        if status != 200:
            error = decoded.get("error", decoded) if isinstance(decoded, dict) else decoded
            code = ""
            if isinstance(error, dict):
                code = str(error.get("code") or error.get("type") or "")
            raise RuntimeError(f"OMNIROUTE_HTTP_{status}:{code[:80]}")
        if not isinstance(decoded, dict):
            raise RuntimeError("OMNIROUTE_RESPONSE_NOT_OBJECT")
        return decoded, elapsed

    def _parse_claims(
        self,
        response: dict[str, Any],
        *,
        allowed_segment_indices: set[int],
    ) -> tuple[ExtractedAtomicClaim, ...]:
        payload = _json_object(_response_content(response))
        raw_claims = payload.get("claims")
        if not isinstance(raw_claims, list):
            raise ValueError("CLAIM_RESPONSE_MISSING_CLAIMS")
        max_claims = int(self.config.get("max_claims_per_window", 48))
        if len(raw_claims) > max_claims:
            raise ValueError("CLAIM_RESPONSE_TOO_MANY_CLAIMS")
        allowed_types = set(self.config["allowed_claim_types"])
        if allowed_types != {kind.value for kind in ClaimType}:
            raise RuntimeError("CLAIM_CONFIG_TAXONOMY_DRIFT")
        claims: list[ExtractedAtomicClaim] = []
        for raw in raw_claims:
            if not isinstance(raw, dict):
                raise ValueError("CLAIM_RESPONSE_BAD_ITEM")
            text = str(raw.get("claim_text") or "").strip()
            claim_type = str(raw.get("claim_type") or "").strip()
            if not text or len(text) > 2000:
                raise ValueError("CLAIM_RESPONSE_BAD_TEXT")
            if claim_type not in allowed_types:
                raise ValueError("CLAIM_RESPONSE_BAD_TYPE")
            indices_raw = raw.get("source_segment_indices")
            if not isinstance(indices_raw, list) or not indices_raw:
                raise ValueError("CLAIM_RESPONSE_MISSING_SEGMENTS")
            if any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in indices_raw
            ):
                raise ValueError("CLAIM_RESPONSE_BAD_SEGMENTS")
            indices = tuple(sorted(set(indices_raw)))
            if not set(indices).issubset(allowed_segment_indices):
                raise ValueError("CLAIM_RESPONSE_SEGMENT_OUTSIDE_WINDOW")
            check_worthy = raw.get("check_worthy")
            numeric_sensitive = raw.get("numeric_sensitive")
            if not isinstance(check_worthy, bool):
                raise ValueError("CLAIM_RESPONSE_BAD_CHECK_WORTHY")
            if not isinstance(numeric_sensitive, bool):
                raise ValueError("CLAIM_RESPONSE_BAD_NUMERIC_SENSITIVE")
            if claim_type in {"RHETORICAL_GENERALIZATION", "VALUE_JUDGMENT"} and check_worthy:
                raise ValueError("CLAIM_NON_FACTUAL_NOT_CHECK_WORTHY")
            claims.append(
                ExtractedAtomicClaim(
                    normalized_claim=text,
                    claim_type=claim_type,
                    check_worthy=check_worthy,
                    numeric_sensitive=numeric_sensitive,
                    speaker=str(raw.get("speaker") or "").strip()[:300],
                    source_timestamp=str(raw.get("source_timestamp") or "").strip()[:64],
                    source_segment_indices=indices,
                )
            )
        return tuple(claims)

    def build_prompt(
        self,
        *,
        window_text: str,
        allowed_segment_indices: tuple[int, ...],
    ) -> str:
        taxonomy = ", ".join(self.config["allowed_claim_types"])
        allowed = ", ".join(str(value) for value in allowed_segment_indices)
        return f"""Perform claim extraction only. Do not fact-check and do not use external knowledge.

The input is an Italian public-statement transcript window. Extract atomic claims only.

Rules:
- Keep independent propositions separate.
- Do not invent facts that are not in the transcript.
- Preserve speaker attribution when the text makes it clear.
- check_worthy=true for factual claims that should be tested against evidence; VALUE_JUDGMENT and RHETORICAL_GENERALIZATION MUST use check_worthy=false.
- numeric_sensitive=true when correctness materially depends on a number, rate, amount, date, threshold or arithmetic relation.
- Every claim MUST cite one or more source_segment_indices from this allowed set: [{allowed}].
- claim_text must be a concise neutral normalization, not a verdict.

Allowed claim_type values:
{taxonomy}

Return JSON only:
{{
  "claims": [
    {{
      "source_timestamp": "M:SS",
      "source_segment_indices": [0],
      "speaker": "",
      "claim_type": "ONE_ALLOWED_VALUE",
      "claim_text": "neutral atomic claim",
      "check_worthy": true,
      "numeric_sensitive": false
    }}
  ]
}}

TRANSCRIPT WINDOW:
---BEGIN---
{window_text}
---END---"""

    def probe(self) -> ClaimRuntimeProbe:
        sample = (
            "[seg=0 0:00.000-0:03.000] "
            "Nel segmento viene affermato che il prezzo è 10 euro."
        )
        prompt = self.build_prompt(
            window_text=sample,
            allowed_segment_indices=(0,),
        )
        started = time.monotonic()
        try:
            response, elapsed = self._post(prompt, max_tokens=256)
            claims = self._parse_claims(response, allowed_segment_indices={0})
            if not claims:
                return ClaimRuntimeProbe(
                    False,
                    "CLAIM_CANARY_EMPTY",
                    elapsed,
                    200,
                )
            return ClaimRuntimeProbe(True, "OK", elapsed, 200)
        except Exception as exc:
            reason = str(exc).splitlines()[0][:160] or type(exc).__name__
            match = re.search(r"HTTP_(\d+)", reason)
            return ClaimRuntimeProbe(
                False,
                reason,
                time.monotonic() - started,
                int(match.group(1)) if match else None,
            )

    def extract(
        self,
        *,
        window_text: str,
        allowed_segment_indices: tuple[int, ...],
    ) -> ClaimExtractionResult:
        prompt = self.build_prompt(
            window_text=window_text,
            allowed_segment_indices=allowed_segment_indices,
        )
        response, elapsed = self._post(prompt, max_tokens=self.max_output_tokens)
        claims = self._parse_claims(
            response,
            allowed_segment_indices=set(allowed_segment_indices),
        )
        usage = response.get("usage")
        return ClaimExtractionResult(
            claims=claims,
            request_id=str(response.get("id") or "") or None,
            latency_seconds=elapsed,
            usage=usage if isinstance(usage, dict) else None,
            observed_cost_usd=_extract_cost(response),
        )
