"""Offline selection of authorized models for PRIVATE Passage candidates only.

Every model identifier, entitlement, benchmark result, remaining quota and rate
is supplied by an operator-verifiable sanitized catalog. A connected app or a
listed model is not proof of usable API quota. This planner makes no API calls,
cannot switch the governed DP-201 claim model, and never silently retries on a
different provider. The batch caller still enforces its own actual cost fence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping


_ALLOWED_PROVIDER_FAMILIES = frozenset({
    "local", "openrouter", "cerebras", "cloudflare-ai", "cohere", "groq",
    "gemini-api", "mistral", "moonshot", "nvidia", "opencode-go", "omniroute",
})
_MODEL_ID = re.compile(r"[A-Za-z0-9._:/+@-]{3,160}\Z")
_MAX_MODELS = 128
_MODEL_FIELDS = frozenset({
    "model_id", "family", "billing_tier", "catalog_model_verified",
    "schema_canary_passed", "operator_enabled", "terms_accepted",
    "confidentiality_approved", "separate_api_entitlement_verified",
    "quota_remaining_requests", "quota_remaining_tokens",
    "usd_per_1k_total_tokens", "paid_owner_authorized",
})


@dataclass(frozen=True)
class ModelChoice:
    model_id: str
    family: str
    billing_tier: str
    rate_usd_per_1k_total_tokens: Decimal
    estimated_upper_usd: Decimal


@dataclass(frozen=True)
class OptionalModelPlan:
    selected: ModelChoice | None
    blocked: tuple[dict[str, str], ...]
    receipt_id: str
    publication_authorized: bool = False
    provider_calls: int = 0


def _money(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def read_sanitized_catalog(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    """Require an independently pinned operator catalog receipt before selection."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("OPTIONAL_CATALOG_RECEIPT_REQUIRED")
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 128_000:
        raise ValueError("OPTIONAL_CATALOG_FILE_INVALID")
    try:
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ValueError("OPTIONAL_CATALOG_RECEIPT_MISMATCH")
        payload = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        if str(exc) == "OPTIONAL_CATALOG_RECEIPT_MISMATCH":
            raise
        raise ValueError("OPTIONAL_CATALOG_JSON_INVALID") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("OPTIONAL_CATALOG_JSON_INVALID") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("OPTIONAL_CATALOG_VERSION_INVALID")
    if set(payload) != {"schema_version", "catalog_origin", "models", "approved_paid_model_ids"}:
        raise ValueError("OPTIONAL_CATALOG_FIELDS_INVALID")
    if payload["catalog_origin"] != "OWNER_VERIFIED_SANITIZED_OMNIROUTE_CATALOG":
        raise ValueError("OPTIONAL_CATALOG_PROVENANCE_MISSING")
    rows = payload["models"]
    if not isinstance(rows, list) or not 0 < len(rows) <= _MAX_MODELS:
        raise ValueError("OPTIONAL_CATALOG_MODELS_INVALID")
    paid = payload["approved_paid_model_ids"]
    if not isinstance(paid, list) or any(not isinstance(x, str) for x in paid):
        raise ValueError("OPTIONAL_CATALOG_PAID_ALLOWLIST_INVALID")
    # Reject credential-bearing exports, even if a caller promises to hide it.
    sensitive = ("secret", "api_key", "password", "credential", "token",
                 "access_token", "refresh_token")
    for row in rows:
        if not isinstance(row, dict) or any(
            str(key).lower() in sensitive
            or any(str(key).lower().endswith("_" + part) for part in sensitive)
            for key in row
        ):
            raise ValueError("OPTIONAL_CATALOG_SENSITIVE_FIELD_FORBIDDEN")
        if set(row) - _MODEL_FIELDS:
            raise ValueError("OPTIONAL_CATALOG_FIELDS_INVALID")
    return payload


def plan_optional_private_candidate(
    catalog: Mapping[str, Any], *,
    input_bytes_sha256: str,
    max_total_tokens: int,
    requests_needed: int,
    max_batch_cost_usd: Decimal,
    source_approved_for_external_api: bool,
) -> OptionalModelPlan:
    """Return a deterministic, explainable *single* route with no side effects.

    `max_total_tokens` is the conservative aggregate token budget for all
    requests, including outputs. No remote fallback or duplicate account use.
    """
    if not isinstance(input_bytes_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", input_bytes_sha256):
        raise ValueError("OPTIONAL_INPUT_HASH_REQUIRED")
    if (type(max_total_tokens) is not int or not 0 < max_total_tokens <= 5_000_000
            or type(requests_needed) is not int or not 0 < requests_needed <= 100):
        raise ValueError("OPTIONAL_QUOTA_REQUIREMENTS_INVALID")
    if type(source_approved_for_external_api) is not bool:
        raise ValueError("OPTIONAL_REMOTE_APPROVAL_MUST_BE_BOOLEAN")
    budget = _money(max_batch_cost_usd)
    if budget is None or budget > Decimal("25"):
        raise ValueError("OPTIONAL_BUDGET_INVALID")
    if catalog.get("schema_version") != 1 or catalog.get("catalog_origin") != "OWNER_VERIFIED_SANITIZED_OMNIROUTE_CATALOG":
        raise ValueError("OPTIONAL_CATALOG_PROVENANCE_MISSING")
    rows = catalog.get("models")
    if not isinstance(rows, list) or not 0 < len(rows) <= _MAX_MODELS:
        raise ValueError("OPTIONAL_CATALOG_MODELS_INVALID")
    allowlist = catalog.get("approved_paid_model_ids")
    if not isinstance(allowlist, list) or any(not isinstance(s, str) for s in allowlist):
        raise ValueError("OPTIONAL_CATALOG_PAID_ALLOWLIST_INVALID")

    blocked: list[dict[str, str]] = []
    candidates: list[tuple[int, Decimal, str, ModelChoice]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("OPTIONAL_MODEL_ENTRY_INVALID")
        mid, family, tier = row.get("model_id"), row.get("family"), row.get("billing_tier")
        if (not isinstance(mid, str) or not _MODEL_ID.fullmatch(mid)
                or mid in seen or family not in _ALLOWED_PROVIDER_FAMILIES
                or tier not in {"LOCAL_ZERO_EXTERNAL", "API_FREE_VERIFIED", "API_PAID_APPROVED"}):
            raise ValueError("OPTIONAL_MODEL_ID_OR_TIER_INVALID")
        seen.add(mid)
        reason = None
        if row.get("catalog_model_verified") is not True:
            reason = "MODEL_NOT_VERIFIED_IN_OFFICIAL_CATALOG"
        elif row.get("schema_canary_passed") is not True:
            reason = "SCHEMA_QUALITY_CANARY_UNPROVEN"
        elif row.get("operator_enabled") is not True:
            reason = "MODEL_NOT_OPERATOR_ENABLED"
        elif tier == "LOCAL_ZERO_EXTERNAL" and family != "local":
            reason = "LOCAL_TIER_FAMILY_MISMATCH"
        elif tier != "LOCAL_ZERO_EXTERNAL" and not source_approved_for_external_api:
            reason = "SOURCE_NOT_APPROVED_FOR_REMOTE_MODEL"
        elif tier != "LOCAL_ZERO_EXTERNAL" and row.get("terms_accepted") is not True:
            reason = "PROVIDER_TERMS_NOT_ACCEPTED"
        elif tier != "LOCAL_ZERO_EXTERNAL" and row.get("confidentiality_approved") is not True:
            reason = "REMOTE_CONFIDENTIALITY_NOT_APPROVED"
        elif tier != "LOCAL_ZERO_EXTERNAL" and row.get("separate_api_entitlement_verified") is not True:
            reason = "SEPARATE_API_ENTITLEMENT_UNVERIFIED"
        elif tier != "LOCAL_ZERO_EXTERNAL" and (
            type(row.get("quota_remaining_requests")) is not int
            or row["quota_remaining_requests"] < requests_needed
            or type(row.get("quota_remaining_tokens")) is not int
            or row["quota_remaining_tokens"] < max_total_tokens
        ):
            reason = "VERIFIED_FREE_OR_PAID_QUOTA_INSUFFICIENT"
        rate = _money(row.get("usd_per_1k_total_tokens"))
        if reason is None and rate is None:
            reason = "MODEL_COST_RATE_UNVERIFIED"
        if reason is None and tier in {"LOCAL_ZERO_EXTERNAL", "API_FREE_VERIFIED"} and rate != 0:
            reason = "ZERO_EXTERNAL_COST_UNVERIFIED"
        if reason is None and tier == "API_PAID_APPROVED" and (
            mid not in allowlist or row.get("paid_owner_authorized") is not True
        ):
            reason = "PAID_MODEL_NOT_OWNER_WHITELISTED"
        estimated = ((rate or Decimal(0)) * max_total_tokens / Decimal(1000)).quantize(
            Decimal("0.000001"), rounding=ROUND_CEILING
        )
        if reason is None and estimated > budget:
            reason = "BATCH_COST_CAP_EXCEEDED"
        if reason is not None:
            blocked.append({"model_id": mid, "family": family, "reason": reason})
            continue
        assert rate is not None
        choice = ModelChoice(mid, family, tier, rate, estimated)
        priority = (0 if tier == "LOCAL_ZERO_EXTERNAL" else
                    1 if tier == "API_FREE_VERIFIED" and family == "openrouter" else
                    2 if tier == "API_FREE_VERIFIED" else 3)
        candidates.append((priority, estimated, mid, choice))
    selected = sorted(candidates, key=lambda x: (x[0], x[1], x[2]))[0][3] if candidates else None
    stable = {
        "scope": "PRIVATE_CANDIDATE_ONLY", "input_sha256": input_bytes_sha256,
        "tokens": max_total_tokens, "requests": requests_needed,
        "budget": str(budget), "external_approved": source_approved_for_external_api,
        "selected": selected.model_id if selected else None,
        "blocked": blocked,
    }
    fingerprint = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return OptionalModelPlan(selected, tuple(blocked), "provider-plan:" + fingerprint)


def validate_optional_omniroute_dispatch(choice: ModelChoice, base_url: str) -> None:
    """Optional local plans must never run through the remote OmniRoute transport."""
    if choice.billing_tier == "LOCAL_ZERO_EXTERNAL":
        raise ValueError("OPTIONAL_LOCAL_CANDIDATE_ADAPTER_UNAVAILABLE")
    # The local OmniRoute gateway must stay loopback and without URL tricks;
    # account/provider dispatch is still subject to its own credentials/grants.
    if base_url.rstrip("/") != "http://127.0.0.1:20128":
        raise ValueError("OPTIONAL_GATEWAY_NOT_PINNED_TO_LOOPBACK")
