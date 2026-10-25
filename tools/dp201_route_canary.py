"""DP-201: single, schema-constrained canary through a verified subscription gateway.

Only the owner's pinned Antigravity route is eligible. The operator verifies the
local gateway's account scope and paid-route guard before opting into one POST.
Quota exhaustion fails closed; absent billing metadata is never reported as zero.
No source text or credentials are included in the public-safe receipt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.claim_runtime import (  # noqa: E402
    OmniRouteClaimClient, load_claim_config, matches_returned_model,
)


SUBSCRIPTION_MODEL = "antigravity/gemini-3.8-flash-tiered"
LOCAL_GATEWAY_URLS = frozenset({
    "http://127.0.0.1:19128", "http://127.0.0.1:20128",
})
SYNTHETIC_WINDOW = "[seg=0 0:00.000-0:03.000] Il prezzo dichiarato è 10 euro."
CANARY_MODEL = load_claim_config()["model"]


class GateBlocked(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _amount(value: Any) -> Decimal | None:
    try:
        if isinstance(value, bool) or value is None:
            return None
        amount = Decimal(str(value))
        return amount if amount.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def _get_json(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(2_000_001)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2_000_001)


def _claim_client(api_key: str, base_url: str) -> OmniRouteClaimClient:
    return OmniRouteClaimClient(api_key=api_key, base_url=base_url)


def run_canary(
    *,
    base_url: str,
    api_key: str,
    subscription_gateway_verified: bool,
    receipt_path: Path,
    http_get: Callable[..., tuple[int, bytes]] = _get_json,
    client_factory: Callable[..., Any] = _claim_client,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a minimal receipt, including on failure; no automatic retry."""
    now = now or datetime.now(timezone.utc)
    model = CANARY_MODEL
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "BLOCKED",
        "reason_code": "",
        "model_requested": model,
        "live_canary_executed": False,
        "model_calls": 0,
        "subscription_gateway_verified": bool(subscription_gateway_verified),
        "exact_model_in_catalog": False,
        "schema_constrained": False,
        "model_identity_exact": False,
        "observed_at": now.isoformat(),
    }
    try:
        if model != SUBSCRIPTION_MODEL:
            raise GateBlocked("NON_SUBSCRIPTION_MODEL")
        if base_url.rstrip("/") not in LOCAL_GATEWAY_URLS:
            raise GateBlocked("UNTRUSTED_GATEWAY_ENDPOINT")
        if not subscription_gateway_verified:
            raise GateBlocked("SUBSCRIPTION_GATEWAY_UNVERIFIED")
        if not api_key:
            raise GateBlocked("OMNIROUTE_API_KEY_MISSING")
        try:
            status, body = http_get(
                base_url.rstrip("/") + "/v1/models",
                {"Authorization": f"Bearer {api_key}"},
                8,
            )
            if status != 200 or len(body) > 2_000_000:
                raise ValueError("catalog readback failed")
            parsed = json.loads(body)
            data = parsed["data"]
            if not isinstance(data, list):
                raise ValueError("not a model list")
            models = {
                item["id"] for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
        except Exception:
            raise GateBlocked("CATALOG_READBACK_FAILED") from None
        receipt["catalog_models_count"] = len(data)
        receipt["exact_model_in_catalog"] = model in models
        # OmniRoute 3.8.52 can serve its pinned tiered Antigravity route
        # even when the key-scoped /v1/models catalog does not list it.
        # The actual completion must still return the exact wire model.

        client = client_factory(api_key, base_url)
        receipt["live_canary_executed"] = True
        receipt["model_calls"] = 1
        try:
            result = client.extract(
                window_text=SYNTHETIC_WINDOW,
                allowed_segment_indices=(0,),
            )
        except Exception as exc:
            if "MODEL_SUBSTITUTED" in str(exc):
                raise GateBlocked("MODEL_SUBSTITUTED") from None
            if any(token in str(exc).upper() for token in (
                "HTTP_429", "QUOTA_EXHAUSTED", "RESOURCE_EXHAUSTED",
            )):
                raise GateBlocked("SUBSCRIPTION_QUOTA_EXHAUSTED") from None
            raise GateBlocked("CANARY_MODEL_CALL_FAILED") from None

        receipt["model_returned"] = result.returned_model
        if not matches_returned_model(model, result.returned_model):
            raise GateBlocked("MODEL_SUBSTITUTED")
        receipt["model_identity_exact"] = True
        receipt["schema_constrained"] = True
        receipt["request_id"] = result.request_id
        if not isinstance(result.request_id, str) or not result.request_id:
            raise GateBlocked("PROVIDER_REQUEST_ID_MISSING")
        usage = result.usage
        if (
            not isinstance(usage, dict)
            or type(usage.get("prompt_tokens")) is not int
            or type(usage.get("completion_tokens")) is not int
            or usage["prompt_tokens"] <= 0
            or usage["completion_tokens"] < 0
        ):
            raise GateBlocked("PROVIDER_USAGE_RECEIPT_MISSING")
        receipt["usage"] = {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
        }
        if type(usage.get("total_tokens")) is int:
            receipt["usage"]["total_tokens"] = usage["total_tokens"]
        receipt["observed_cost_usd"] = result.observed_cost_usd
        if result.observed_cost_usd is not None and _amount(result.observed_cost_usd) != 0:
            raise GateBlocked("UNEXPECTED_PROVIDER_COST")
        receipt["claims_count"] = len(result.claims)
        receipt["latency_seconds"] = result.latency_seconds
        if not result.claims:
            raise GateBlocked("CANARY_NO_CLAIMS")
        # This tiny approved fixture tests numeric extraction tied to segment 0,
        # not merely a valid but irrelevant sentence.
        if not any(
            claim.check_worthy
            and claim.numeric_sensitive
            and claim.source_segment_indices == (0,)
            and re.search(r"\b10\b", claim.normalized_claim)
            and ("euro" in claim.normalized_claim.casefold()
                 or "€" in claim.normalized_claim)
            for claim in result.claims
        ):
            raise GateBlocked("CANARY_NO_MEANINGFUL_CLAIMS")
        receipt["status"] = "CANARY_PASSED"
        receipt["reason_code"] = "OK"
    except GateBlocked as exc:
        receipt["reason_code"] = exc.code
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--subscription-gateway-verified", action="store_true",
        help="Operator has checked Antigravity Pro account-only routing and paid-route guard",
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:20128")
    args = parser.parse_args()
    receipt = run_canary(
        base_url=args.base_url,
        api_key=os.environ.get("OMNIROUTE_API_KEY", ""),
        subscription_gateway_verified=args.subscription_gateway_verified,
        receipt_path=args.receipt,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "CANARY_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
