"""DP-201 regression: the live canary is meaningful, schema-bound and cost-gated.

Every refusal here happens before a model call. A missing, stale or unpinned
cost/quota attestation, or a catalog without the exact model, must abort with
zero calls: an unknown quota is NO-GO, never an inferred free call.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

import dp201_route_canary as canary  # noqa: E402
from dichiarazioni_pubbliche.claim_runtime import (  # noqa: E402
    ClaimExtractionResult,
    ExtractedAtomicClaim,
)


MODEL = "antigravity/gemini-3.8-flash-tiered"
NOW = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


def attestation(**overrides):
    payload = {
        "schema_version": 1,
        "model": MODEL,
        "entitlement": "included_subscription",
        "marginal_cost_usd_per_request": "0",
        "hard_cap_usd": "0.25",
        "quota_total": 1000,
        "quota_remaining": 900,
        "observed_at": "2026-10-23T08:30:00Z",
        "source": "OmniRoute key usage-limits readback, private channel",
    }
    payload.update(overrides)
    return payload


def claim_result(**overrides):
    result = ClaimExtractionResult(
        claims=(
            ExtractedAtomicClaim(
                normalized_claim="Il prezzo è 10 euro.",
                claim_type="PRICE_STATISTIC",
                check_worthy=True,
                numeric_sensitive=True,
                speaker="",
                source_timestamp="0:00",
                source_segment_indices=(0,),
            ),
        ),
        request_id="req-abc123",
        latency_seconds=0.4,
        usage={"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
        observed_cost_usd=0.0,
        returned_model=MODEL,
    )
    for key, value in overrides.items():
        result = ClaimExtractionResult(**{**result.__dict__, key: value})
    return result


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def extract(self, *, window_text, allowed_segment_indices):
        self.calls += 1
        self.window_text = window_text
        self.allowed_segment_indices = allowed_segment_indices
        if self.error is not None:
            raise self.error
        return self.result


class CanaryGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.attestation_path = self.root / "cost-attestation.json"
        self.receipt_path = self.root / "canary-receipt.json"
        self.write_attestation()
        self.catalog_calls = []

    def write_attestation(self, **overrides):
        self.attestation_path.write_text(json.dumps(attestation(**overrides)))
        return hashlib.sha256(self.attestation_path.read_bytes()).hexdigest()

    def catalog(self, models):
        def http_get(url, headers, timeout):
            self.catalog_calls.append(url)
            self.assertIn("/v1/models", url)
            self.assertEqual(headers["Authorization"], "Bearer opaque-key")
            body = {"data": [{"id": model} for model in models]}
            return 200, json.dumps(body).encode()

        return http_get

    def refuse_network(self, *_args, **_kwargs):
        raise AssertionError("NETWORK_FORBIDDEN")

    def refuse_client(self, *_args, **_kwargs):
        raise AssertionError("MODEL_CALL_FORBIDDEN")

    def run_canary(self, pin=None, http_get=None, client=None, **overrides):
        options = {
            "base_url": "http://127.0.0.1:20128",
            "api_key": "opaque-key",
            "attestation_path": self.attestation_path,
            "trusted_attestation_sha256": pin if pin is not None else (
                hashlib.sha256(self.attestation_path.read_bytes()).hexdigest()
                if self.attestation_path.exists() else "0" * 64
            ),
            "http_get": http_get or self.refuse_network,
            "client_factory": (lambda *_: client) if client is not None else self.refuse_client,
            "now": NOW,
            "receipt_path": self.receipt_path,
        }
        options.update(overrides)
        return canary.run_canary(**options)

    def assertBlocked(self, reason_code, *, receipt, executed=False):
        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertEqual(receipt["reason_code"], reason_code)
        self.assertEqual(receipt["live_canary_executed"], executed)
        self.assertEqual(receipt["model_calls"], 1 if executed else 0)

    def test_missing_or_unpinned_attestation_blocks_before_any_network(self):
        self.attestation_path.unlink()
        receipt = self.run_canary()
        self.assertBlocked("COST_ATTESTATION_MISSING", receipt=receipt)

        self.write_attestation()
        receipt = self.run_canary(pin="0" * 64)
        self.assertBlocked("COST_ATTESTATION_PIN_MISMATCH", receipt=receipt)

        receipt = self.run_canary(pin="not-a-sha256")
        self.assertBlocked("COST_ATTESTATION_PIN_MISMATCH", receipt=receipt)
        self.assertEqual(self.catalog_calls, [])

    def test_attestation_requires_exact_model_included_zero_cost_and_fresh_quota(self):
        cases = (
            ({"model": "antigravity/gemini-3.8-flash"}, "COST_ATTESTATION_MODEL_MISMATCH"),
            ({"entitlement": "paid_api"}, "COST_ATTESTATION_ENTITLEMENT_INVALID"),
            ({"marginal_cost_usd_per_request": "0.001"}, "COST_ATTESTATION_COST_NOT_ZERO"),
            ({"hard_cap_usd": "0"}, "COST_ATTESTATION_CAP_INVALID"),
            ({"hard_cap_usd": "0.30"}, "COST_ATTESTATION_CAP_EXCEEDS_JOB_LIMIT"),
            ({"quota_total": None}, "COST_ATTESTATION_QUOTA_UNKNOWN"),
            ({"quota_total": 10, "quota_remaining": 0}, "COST_ATTESTATION_QUOTA_EXHAUSTED"),
            ({"quota_total": 10, "quota_remaining": 11}, "COST_ATTESTATION_QUOTA_UNKNOWN"),
            ({"observed_at": "2026-09-22T20:32:09Z"}, "COST_ATTESTATION_STALE"),
            ({"observed_at": "yesterday"}, "COST_ATTESTATION_INVALID"),
            ({"source": ""}, "COST_ATTESTATION_INVALID"),
            ({"schema_version": 2}, "COST_ATTESTATION_INVALID"),
        )
        for overrides, code in cases:
            with self.subTest(overrides=overrides):
                self.write_attestation(**overrides)
                receipt = self.run_canary()
                self.assertBlocked(code, receipt=receipt)
        self.assertEqual(self.catalog_calls, [])

    def test_exact_model_must_be_exposed_by_the_key_catalog_or_no_call(self):
        receipt = self.run_canary(
            http_get=self.catalog([MODEL + "-high", "opencode-go/deepseek-v4-flash"]),
        )
        self.assertBlocked("MODEL_NOT_EXPOSED_FOR_KEY", receipt=receipt)
        self.assertFalse(receipt["exact_model_in_catalog"])
        self.assertEqual(receipt["catalog_models_count"], 2)

        def failed(url, headers, timeout):
            return 502, b"upstream unavailable"

        receipt = self.run_canary(http_get=failed)
        self.assertBlocked("CATALOG_READBACK_FAILED", receipt=receipt)

    def test_canary_passes_only_with_exact_model_schema_usage_and_zero_cost(self):
        client = FakeClient(result=claim_result())
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=client)
        self.assertEqual(receipt["status"], "CANARY_PASSED")
        self.assertEqual(receipt["model_calls"], 1)
        self.assertTrue(receipt["live_canary_executed"])
        self.assertTrue(receipt["model_identity_exact"])
        self.assertTrue(receipt["schema_constrained"])
        self.assertEqual(receipt["model_requested"], MODEL)
        self.assertEqual(receipt["model_returned"], MODEL)
        self.assertEqual(receipt["request_id"], "req-abc123")
        self.assertEqual(receipt["claims_count"], 1)
        self.assertEqual(receipt["observed_cost_usd"], 0.0)
        self.assertEqual(client.allowed_segment_indices, (0,))
        self.assertEqual(
            receipt["attestation_sha256"],
            hashlib.sha256(self.attestation_path.read_bytes()).hexdigest(),
        )
        written = json.loads(self.receipt_path.read_text())
        self.assertEqual(written, receipt)
        serialized = json.dumps(receipt)
        self.assertNotIn("10 euro", serialized)
        self.assertNotIn("TRANSCRIPT", serialized)
        self.assertNotIn("opaque-key", serialized)

    def test_substitution_and_incomplete_receipts_never_pass(self):
        substituted = FakeClient(
            error=RuntimeError("OMNIROUTE_MODEL_SUBSTITUTED:opencode-go/deepseek-v4-flash")
        )
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=substituted)
        self.assertBlocked("MODEL_SUBSTITUTED", receipt=receipt, executed=True)

        mismatched = FakeClient(result=claim_result(returned_model="openai/gpt-6"))
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=mismatched)
        self.assertBlocked("MODEL_SUBSTITUTED", receipt=receipt, executed=True)

        for overrides, code in (
            ({"usage": None}, "PROVIDER_USAGE_RECEIPT_MISSING"),
            ({"usage": {"prompt_tokens": 120}}, "PROVIDER_USAGE_RECEIPT_MISSING"),
            ({"request_id": None}, "PROVIDER_REQUEST_ID_MISSING"),
            ({"observed_cost_usd": 0.01}, "UNEXPECTED_PROVIDER_COST"),
            ({"claims": ()}, "CANARY_NO_CLAIMS"),
        ):
            with self.subTest(overrides=overrides):
                client = FakeClient(result=claim_result(**overrides))
                receipt = self.run_canary(http_get=self.catalog([MODEL]), client=client)
                self.assertBlocked(code, receipt=receipt, executed=True)

    def test_no_api_key_or_api_url_from_arguments_is_required_as_secret(self):
        receipt = self.run_canary(
            api_key="",
            http_get=self.catalog([MODEL]),
            client=FakeClient(result=claim_result()),
        )
        self.assertBlocked("OMNIROUTE_API_KEY_MISSING", receipt=receipt)


if __name__ == "__main__":
    unittest.main()
