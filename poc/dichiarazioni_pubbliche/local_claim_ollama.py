"""Opt-in, private, loopback-only Ollama claim extraction candidate provider.

This is NOT an official OmniRoute canary (DP-201). No claim is accepted as
true, attributed to a person or publishable by using this transport.
The host must already have a deliberately approved, digest-pinned local model.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from dichiarazioni_pubbliche.local_inference_guard import local_inference_slot
from dichiarazioni_pubbliche.claim_runtime import (
    ClaimRuntimeProbe, OmniRouteClaimClient, load_claim_config,
)


_MODEL = "qwen3:4b"
_URL = "http://127.0.0.1:11434"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESPONSE = 1_048_576
LOCAL_CLAIM_PROMPT_VERSION = "local-ollama-qwen3-4b-quote-guard-v1"
_SEGMENT_MARKER = re.compile(r"(?m)^\[seg=([0-9]+)\s+[^\]\r\n]+\] ")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("LOCAL_CLAIM_REDIRECT_REFUSED")


def _request(path: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if path not in {"/api/tags", "/api/chat"}:
        raise RuntimeError("LOCAL_CLAIM_DESTINATION_INVALID")
    req = urllib.request.Request(
        _URL + path,
        data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(req, timeout=40 if payload is not None else 5) as response:
            if response.status != 200:
                raise RuntimeError("LOCAL_CLAIM_HTTP_UNEXPECTED")
            raw = response.read(_MAX_RESPONSE + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("LOCAL_CLAIM_LOOPBACK_UNAVAILABLE") from exc
    if len(raw) > _MAX_RESPONSE:
        raise RuntimeError("LOCAL_CLAIM_RESPONSE_TOO_LARGE")
    try:
        decoded = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("LOCAL_CLAIM_RESPONSE_NOT_JSON") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("LOCAL_CLAIM_RESPONSE_INVALID")
    return decoded


def _strict_schema(allowed_types: list[str], limit: int) -> dict[str, Any]:
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "source_timestamp", "source_segment_indices", "speaker",
            "claim_type", "claim_text", "check_worthy", "numeric_sensitive",
            "source_quote",
        ],
        "properties": {
            "source_timestamp": {"type": "string"},
            "source_segment_indices": {
                "type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 32,
            },
            "speaker": {"type": "string"},
            "claim_type": {"type": "string", "enum": allowed_types},
            "claim_text": {"type": "string"},
            "check_worthy": {"type": "boolean"},
            "numeric_sensitive": {"type": "boolean"},
            "source_quote": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {"claims": {"type": "array", "items": claim, "maxItems": limit}},
    }


def _indexed_source_segments(source: str) -> dict[int, str]:
    """Bind each candidate's exact quote to its own canonical segment(s)."""
    matches = list(_SEGMENT_MARKER.finditer(source))
    if not matches or matches[0].start() != 0 or len(matches) > 64:
        raise ValueError("LOCAL_CLAIM_SEGMENT_SOURCE_INVALID")
    segments: dict[int, str] = {}
    for index, match in enumerate(matches):
        segment_number = int(match.group(1))
        if segment_number in segments:
            raise ValueError("LOCAL_CLAIM_SEGMENT_DUPLICATE")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        text = source[match.end():end].strip()
        if not text:
            raise ValueError("LOCAL_CLAIM_SEGMENT_EMPTY")
        segments[segment_number] = text
    return segments


class LocalOllamaClaimClient(OmniRouteClaimClient):
    """Uses the existing bounded atomic-claim parser, with extra source quote checks."""

    provider_id = "ollama-local"

    def __init__(self, *, expected_model_digest: str) -> None:
        if not isinstance(expected_model_digest, str) or not _DIGEST.fullmatch(expected_model_digest):
            raise ValueError("LOCAL_CLAIM_PINNED_MODEL_DIGEST_REQUIRED")
        config = dict(load_claim_config())
        config.update({
            "model": _MODEL, "prompt_version": LOCAL_CLAIM_PROMPT_VERSION,
            "max_output_tokens": 512, "request_timeout_seconds": 40,
            "max_claims_per_window": 12,
        })
        # The overridden local transport never sends authentication headers:
        # do not fabricate or retain a credential solely for class reuse.
        super().__init__(api_key="", base_url=_URL, config=config)
        self.expected_model_digest = expected_model_digest

    def _verify_model_pin(self) -> None:
        tags = _request("/api/tags")
        rows = tags.get("models")
        if not isinstance(rows, list):
            raise RuntimeError("LOCAL_CLAIM_MODEL_CATALOG_INVALID")
        matches = [x for x in rows if isinstance(x, dict) and x.get("name") == self.model]
        if len(matches) != 1 or matches[0].get("digest") != self.expected_model_digest:
            raise RuntimeError("LOCAL_CLAIM_MODEL_NOT_PINNED_OR_CHANGED")

    def probe(self) -> ClaimRuntimeProbe:
        """Meaningful synthetic canary; catalog presence alone is insufficient.

        Quality and quote-binding failures continue to block this optional lane.
        No personal transcript is sent during the canary.
        """
        sample = "[seg=0 0:00.000-0:03.000] Il prezzo dichiarato è 10 euro."
        started = time.monotonic()
        try:
            self._verify_model_pin()
            result = self.extract(window_text=sample, allowed_segment_indices=(0,))
            if not any("10" in c.normalized_claim and "euro" in c.normalized_claim.lower()
                       and c.source_segment_indices == (0,) for c in result.claims):
                return ClaimRuntimeProbe(False, "LOCAL_CLAIM_MEANINGFUL_CANARY_FAILED",
                                         time.monotonic() - started, 200)
            return ClaimRuntimeProbe(True, "LOCAL_CLAIM_SYNTHETIC_CANARY_OK",
                                     time.monotonic() - started, 200)
        except (RuntimeError, ValueError) as exc:
            # Never include transcript/model outputs or network response bodies.
            reason = str(exc).splitlines()[0][:120]
            return ClaimRuntimeProbe(False, reason, time.monotonic() - started, None)

    def _post(self, prompt: str, *, max_tokens: int) -> tuple[dict[str, Any], float]:
        # Never submit private transcript bytes until the exact operator-pinned
        # model is present locally. An updated/mismatched tag refuses processing.
        start_marker, end_marker = "TRANSCRIPT WINDOW:\n---BEGIN---\n", "\n---END---"
        if prompt.count(start_marker) != 1 or not prompt.endswith(end_marker):
            raise RuntimeError("LOCAL_CLAIM_WINDOW_MARKER_MISMATCH")
        source = prompt.split(start_marker, 1)[1][:-len(end_marker)]
        if not source.strip() or len(source.encode("utf-8")) > 32_768:
            raise RuntimeError("LOCAL_CLAIM_WINDOW_SIZE_INVALID")
        segment_texts = _indexed_source_segments(source)
        limit = min(self.max_output_tokens, int(max_tokens))
        if not 1 <= limit <= 512:
            raise RuntimeError("LOCAL_CLAIM_TOKEN_LIMIT_INVALID")
        schema = _strict_schema(
            list(self.config["allowed_claim_types"]), int(self.config["max_claims_per_window"])
        )
        started = time.monotonic()
        with local_inference_slot():
            self._verify_model_pin()
            result = _request("/api/chat", payload={
                "model": self.model, "stream": False, "think": False, "format": schema,
                "messages": [
                    {"role": "system", "content": (
                        "/no_think\nExtract ONLY explicitly supported atomic claims from the "
                        "source. Return JSON only. Every source_quote MUST be a nonempty "
                        "verbatim substring of the source window and the segment IDs must "
                        "belong to the allowed list. Do not invent speakers, dates or facts."
                    )},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0, "num_predict": limit, "num_ctx": 4096},
            })
        elapsed = time.monotonic() - started
        if (result.get("model") != self.model or result.get("done") is not True
                or result.get("done_reason") != "stop"):
            raise RuntimeError("LOCAL_CLAIM_RESPONSE_INCOMPLETE")
        message = result.get("message")
        raw = message.get("content") if isinstance(message, dict) else None
        if not isinstance(raw, str) or len(raw) > _MAX_RESPONSE:
            raise ValueError("LOCAL_CLAIM_RESPONSE_TEXT_INVALID")
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise ValueError("LOCAL_CLAIM_RESPONSE_NOT_JSON") from exc
        rows = payload.get("claims") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) > self.config["max_claims_per_window"]:
            raise ValueError("LOCAL_CLAIM_RESPONSE_CLAIMS_INVALID")
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(schema["properties"]["claims"]["items"]["required"]):
                raise ValueError("LOCAL_CLAIM_RESPONSE_FIELDS_INVALID")
            quote = row["source_quote"]
            indexes = row["source_segment_indices"]
            if (not isinstance(indexes, list) or not indexes
                or any(type(number) is not int or number not in segment_texts
                       for number in indexes)):
                raise ValueError("LOCAL_CLAIM_SEGMENT_OUTSIDE_SOURCE")
            cited_text = "\n".join(segment_texts[number] for number in indexes)
            if not isinstance(quote, str) or not quote.strip() or quote not in cited_text:
                raise ValueError("LOCAL_CLAIM_SOURCE_QUOTE_UNBOUND")
            # A speaker identity is not authorized by a model guess. Any
            # suggested speaker must at least literally occur in cited text;
            # downstream attribution approval is still independently required.
            speaker = row["speaker"]
            if not isinstance(speaker, str) or (speaker.strip() and speaker.strip() not in cited_text):
                raise ValueError("LOCAL_CLAIM_SPEAKER_UNBOUND")
        # The shared strict parser separately enforces types, claim taxonomy,
        # allowed segment indices, non-factual check-worthy and replay identity.
        return {
            "id": "local:" + hashlib.sha256(
                (self.expected_model_digest + prompt + raw).encode("utf-8")
            ).hexdigest(),
            "choices": [{"message": {"content": raw}}],
            "usage": {
                "prompt_tokens": int(result.get("prompt_eval_count") or 0),
                "completion_tokens": int(result.get("eval_count") or 0),
            },
        }, elapsed


__all__ = ["LOCAL_CLAIM_PROMPT_VERSION", "LocalOllamaClaimClient"]
