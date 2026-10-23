"""DP-201: explicit, fail-closed OmniRoute canary for an included-cost model.

An operator must independently verify the entitlement, quota and enforced cap,
then pin the SHA-256 of a private attestation. Unknown values mean zero POSTs.
No transcript or API key is stored in the public-safe receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.claim_runtime import (  # noqa: E402
    OmniRouteClaimClient, load_claim_config,
)


MAX_ATTESTATION_AGE_SECONDS = 7200
MAX_HARD_CAP_USD = Decimal("0.25")
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


def _verify_attestation(
    path: Path, pin: str, model: str, now: datetime
) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise GateBlocked("COST_ATTESTATION_MISSING")
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(pin) != 64 or pin.lower() != sha256:
        raise GateBlocked("COST_ATTESTATION_PIN_MISMATCH")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise GateBlocked("COST_ATTESTATION_INVALID") from None
    if not isinstance(obj, dict) or type(obj.get("schema_version")) is not int or obj["schema_version"] != 1:
        raise GateBlocked("COST_ATTESTATION_INVALID")
    if obj.get("model") != model:
        raise GateBlocked("COST_ATTESTATION_MODEL_MISMATCH")
    if obj.get("entitlement") != "included_subscription":
        raise GateBlocked("COST_ATTESTATION_ENTITLEMENT_INVALID")
    if _amount(obj.get("marginal_cost_usd_per_request")) != 0:
        raise GateBlocked("COST_ATTESTATION_COST_NOT_ZERO")
    cap = _amount(obj.get("hard_cap_usd"))
    if cap is None or cap <= 0:
        raise GateBlocked("COST_ATTESTATION_CAP_INVALID")
    if cap > MAX_HARD_CAP_USD:
        raise GateBlocked("COST_ATTESTATION_CAP_EXCEEDS_JOB_LIMIT")
    total, remaining = obj.get("quota_total"), obj.get("quota_remaining")
    if (
        type(total) is not int or type(remaining) is not int
        or total <= 0 or remaining < 0 or remaining > total
    ):
        raise GateBlocked("COST_ATTESTATION_QUOTA_UNKNOWN")
    if remaining == 0:
        raise GateBlocked("COST_ATTESTATION_QUOTA_EXHAUSTED")
    if not isinstance(obj.get("source"), str) or not obj["source"].strip():
        raise GateBlocked("COST_ATTESTATION_INVALID")
    try:
        observed = datetime.fromisoformat(obj["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("timezone missing")
        age = (now - observed).total_seconds()
    except (KeyError, TypeError, AttributeError, ValueError):
        raise GateBlocked("COST_ATTESTATION_INVALID") from None
    if age < 0 or age > MAX_ATTESTATION_AGE_SECONDS:
        raise GateBlocked("COST_ATTESTATION_STALE")
    return obj, sha256


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
    attestation_path: Path,
    trusted_attestation_sha256: str,
    receipt_path: Path,
    http_get: Callable[..., tuple[int, bytes]] = _get_json,
    client_factory: Callable[..., Any] = _claim_client,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a minimal receipt, including on failure; no request without preflight."""
    now = now or datetime.now(timezone.utc)
    model = CANARY_MODEL
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "BLOCKED",
        "reason_code": "",
        "model_requested": model,
        "live_canary_executed": False,
        "model_calls": 0,
        "exact_model_in_catalog": False,
        "schema_constrained": False,
        "model_identity_exact": False,
        "observed_at": now.isoformat(),
    }
    try:
        _, attestation_hash = _verify_attestation(
            attestation_path, trusted_attestation_sha256, model, now
        )
        receipt["attestation_sha256"] = attestation_hash
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
        if model not in models:
            raise GateBlocked("MODEL_NOT_EXPOSED_FOR_KEY")

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
            raise GateBlocked("CANARY_MODEL_CALL_FAILED") from None

        receipt["model_returned"] = result.returned_model
        if result.returned_model != model:
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
        if _amount(result.observed_cost_usd) != 0:
            raise GateBlocked("UNEXPECTED_PROVIDER_COST")
        receipt["claims_count"] = len(result.claims)
        if not result.claims:
            raise GateBlocked("CANARY_NO_CLAIMS")
        receipt["status"] = "CANARY_PASSED"
        receipt["reason_code"] = "OK"
    except GateBlocked as exc:
        receipt["reason_code"] = exc.code
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--attestation-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:20128")
    args = parser.parse_args()
    receipt = run_canary(
        base_url=args.base_url,
        api_key=os.environ.get("OMNIROUTE_API_KEY", ""),
        attestation_path=args.attestation,
        trusted_attestation_sha256=args.attestation_sha256,
        receipt_path=args.receipt,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "CANARY_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
