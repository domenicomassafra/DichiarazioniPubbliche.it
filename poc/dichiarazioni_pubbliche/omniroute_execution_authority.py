"""Read-only OmniRoute execution witness for DP-413.

An authenticated management response authenticates one completed gateway
execution. It does not attest the upstream Google Pro subscription or quota:
the separate model-aware subscription gate must still run before every POST.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from dichiarazioni_pubbliche.autonomous_publication import (
    APPROVED_REVIEW_MODELS, AgentReview,
)
from dichiarazioni_pubbliche.autonomous_runner_v3 import _json
from dichiarazioni_pubbliche.claim_runtime import DEFAULT_BASE_URL, matches_returned_model

_TAG = re.compile(r"dp413-[a-f0-9]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def _management_read(base_url: str, token: str, path: str) -> object:
    request = urllib.request.Request(
        base_url + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    with urllib.request.build_opener(NoRedirect).open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("DP413_WITNESS_MANAGEMENT_RESPONSE")
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("DP413_WITNESS_MANAGEMENT_TOO_LARGE")
    return json.loads(raw)


class OmniRouteExecutionAuthority:
    """Verify a review against separate authenticated gateway request history.

    The configured key and connection IDs must come from an independently
    verified DP subscription admission. This checks only actual execution.
    """

    def __init__(
        self, *, management_token: str, dp_key_id: str,
        allowed_connection_ids: frozenset[str],
        base_url: str = DEFAULT_BASE_URL,
        read: Callable[[str], object] | None = None,
    ):
        if (base_url != DEFAULT_BASE_URL or not management_token
                or type(dp_key_id) is not str or not dp_key_id
                or not isinstance(allowed_connection_ids, frozenset)
                or not allowed_connection_ids
                or any(type(value) is not str or not value
                       for value in allowed_connection_ids)):
            raise ValueError("DP413_WITNESS_AUTHORITY_CONFIG_INVALID")
        self.dp_key_id = dp_key_id
        self.allowed_connection_ids = allowed_connection_ids
        self._read = read or (lambda path: _management_read(
            base_url, management_token, path,
        ))

    def __call__(self, review: AgentReview | Mapping[str, object]) -> bool:
        try:
            receipt = asdict(review) if is_dataclass(review) else dict(review)
            return self._verify(receipt)
        except (TypeError, ValueError, KeyError, IndexError, OSError, RuntimeError,
                AttributeError, json.JSONDecodeError):
            return False

    def _verify(self, receipt: Mapping[str, object]) -> bool:
        tag = receipt.get("session_tag")
        model = receipt.get("requested_model", receipt.get("model_id"))
        response_id = receipt.get("provider_request_id")
        prompt_sha256 = receipt.get("prompt_sha256")
        if ("requested_model" in receipt and "model_id" in receipt
                and receipt["requested_model"] != receipt["model_id"]):
            return False
        if (type(tag) is not str or not _TAG.fullmatch(tag)
                or type(model) is not str or model not in APPROVED_REVIEW_MODELS
                or receipt.get("provider") != "omniroute"
                or type(response_id) is not str or not response_id
                or type(prompt_sha256) is not str or not _SHA.fullmatch(prompt_sha256)
                or not matches_returned_model(model, receipt.get("returned_model"))
                or not isinstance(receipt.get("usage"), dict)
                or type(receipt.get("accepted")) is not bool):
            return False

        keys = self._read("/api/keys")
        if isinstance(keys, dict):
            keys = keys.get("keys")
        if not isinstance(keys, list):
            return False
        matching_keys = [k for k in keys if isinstance(k, dict)
                         and k.get("id") == self.dp_key_id]
        if len(matching_keys) != 1:
            return False
        key = matching_keys[0]
        if (key.get("isActive") is not True or key.get("revokedAt")
                or key.get("isBanned") is True
                or key.get("modelAccessMode") != "restricted"
                or type(key.get("allowedConnections")) is not list
                or set(key["allowedConnections"]) != self.allowed_connection_ids
                or type(key.get("allowedModels")) is not list
                or model not in key["allowedModels"]
                or any(value not in APPROVED_REVIEW_MODELS
                       for value in key["allowedModels"])
                or key.get("allowedCombos")):
            return False
        if key.get("expiresAt") is not None:
            expiry = datetime.fromisoformat(str(key["expiresAt"]).replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                return False

        query = urllib.parse.urlencode({"model": model, "limit": 100})
        rows = self._read("/api/usage/call-logs?" + query)
        # A full page cannot exclude a second execution with the same tag.
        if not isinstance(rows, list) or len(rows) >= 100:
            return False
        matches = []
        for row in rows:
            if not isinstance(row, dict) or type(row.get("id")) is not str:
                return False
            # The gateway's list response includes sessionTag. Fetch only
            # matching detail rows; unrelated traffic must not make a review
            # tick perform up to 99 authenticated requests.
            if row.get("sessionTag") != tag:
                continue
            if row.get("provider") != "antigravity" or row.get("status") != 200:
                return False
            detail = self._read("/api/usage/call-logs/" + urllib.parse.quote(
                row["id"], safe="",
            ))
            if not isinstance(detail, dict):
                return False
            if detail.get("sessionTag") == tag:
                matches.append(detail)
        if len(matches) != 1:
            return False
        detail = matches[0]
        request_id = detail["id"]
        request = detail.get("requestBody")
        response = detail.get("responseBody")
        if (detail.get("status") != 200 or detail.get("active")
                or detail.get("error") or detail.get("detailState") != "ready"
                or detail.get("apiKeyId") != self.dp_key_id
                or detail.get("connectionId") not in self.allowed_connection_ids
                or detail.get("requestedModel") != model
                or detail.get("provider") != "antigravity"
                or detail.get("comboName") or detail.get("resilienceActions")
                or detail.get("hasRequestBody") is not True
                or detail.get("hasResponseBody") is not True
                or not isinstance(request, dict)
                or not isinstance(response, dict)):
            return False
        requested = dict(request)
        requested.pop("_omniroute", None)  # OmniRoute's internal routing annotation.
        observed_usage = response.get("usage")
        if (requested.get("model") != model
                or hashlib.sha256(_json(requested).encode()).hexdigest() != prompt_sha256
                or response.get("id") != response_id
                or not matches_returned_model(model, response.get("model"))
                or detail.get("model") != model.split("/", 1)[1]
                or not isinstance(observed_usage, dict)
                or any(observed_usage.get(name) != receipt["usage"].get(name)
                       for name in ("prompt_tokens", "completion_tokens"))
                or type(observed_usage.get("prompt_tokens")) is not int
                or observed_usage["prompt_tokens"] <= 0
                or type(observed_usage.get("completion_tokens")) is not int
                or observed_usage["completion_tokens"] < 0):
            return False
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            return False
        raw_verdict = choices[0].get("message", {}).get("content")
        if type(raw_verdict) is not str:
            return False
        verdict = json.loads(raw_verdict)
        if (not isinstance(verdict, dict)
                or verdict.get("evidence_sha256") != receipt.get("evidence_sha256")
                or verdict.get("checked_stages") != list(receipt["checked_stages"])
                or type(verdict.get("accepted")) is not bool
                or (receipt.get("accepted") is True
                    and verdict["accepted"] is not True)
                or not isinstance(verdict.get("stage_citations"), dict)
                or verdict["stage_citations"] != receipt.get("stage_citations")
                or set(verdict["stage_citations"]) != set(receipt["checked_stages"])
                or any(not isinstance(values, list)
                       or any(type(value) is not str or not value for value in values)
                       for values in verdict["stage_citations"].values())
                or (receipt["accepted"] is True and any(
                    not values for values in verdict["stage_citations"].values()
                ))):
            return False

        explain = self._read("/api/usage/route-explain/" + urllib.parse.quote(
            request_id, safe="",
        ))
        if not isinstance(explain, dict):
            return False
        replay = explain.get("decisionReplay", {}).get("runtime", {})
        selected = explain.get("selectedTarget", {})
        decision = explain.get("decision", {})
        provider, unprefixed_model = model.split("/", 1)
        if (explain.get("requestId") != request_id
                or explain.get("request", {}).get("id") != request_id
                or explain.get("request", {}).get("requestedModel") != model
                or explain.get("routeType") != "direct"
                or explain.get("comboUsed")
                or replay.get("source") != "call_logs"
                or replay.get("exact") is not True
                or replay.get("selectedCallLogId") != request_id
                or any(entry.get("provider") != provider
                       or entry.get("model") != unprefixed_model
                       or entry.get("status") != 200
                       or entry.get("connectionId") != detail["connectionId"]
                       for entry in (replay, selected))
                or explain.get("providerSelected") != provider
                or explain.get("modelUsed") != unprefixed_model
                or decision.get("providerSelected") != provider
                or decision.get("modelUsed") != unprefixed_model
                or decision.get("status") != 200):
            return False
        # Route-explain can include neighboring failures. Authenticate their
        # session IDs; a fallback owned by this review or unreadable is HOLD.
        fallbacks = []
        for source in (explain, decision):
            values = source.get("fallbacksTriggered")
            if not isinstance(values, list):
                return False
            fallbacks.extend(values)
        for fallback_id in {item.get("id") for item in fallbacks
                            if isinstance(item, dict)}:
            if type(fallback_id) is not str or not fallback_id:
                return False
            other = self._read("/api/usage/call-logs/" + urllib.parse.quote(
                fallback_id, safe="",
            ))
            if (not isinstance(other, dict) or other.get("id") != fallback_id
                    or type(other.get("sessionTag")) is not str
                    or not other["sessionTag"] or other["sessionTag"] == tag):
                return False
        return len(fallbacks) == sum(isinstance(item, dict) for item in fallbacks)
