"""DP-201: a subscription-only route permits one meaningful, receipt-backed canary."""

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
        self.receipt_path = self.root / "canary-receipt.json"
        self.catalog_calls = []

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

    def run_canary(self, http_get=None, client=None, **overrides):
        options = {
            "base_url": "http://127.0.0.1:20128",
            "api_key": "opaque-key",
            "subscription_gateway_verified": True,
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

    def test_unverified_gateway_or_untrusted_endpoint_blocks_before_network(self):
        receipt = self.run_canary(subscription_gateway_verified=False)
        self.assertBlocked("SUBSCRIPTION_GATEWAY_UNVERIFIED", receipt=receipt)
        receipt = self.run_canary(base_url="https://api.example.com")
        self.assertBlocked("UNTRUSTED_GATEWAY_ENDPOINT", receipt=receipt)
        self.assertEqual(self.catalog_calls, [])

    def test_route_is_pinned_to_exact_antigravity_subscription_model(self):
        current = canary.CANARY_MODEL
        self.addCleanup(setattr, canary, "CANARY_MODEL", current)
        canary.CANARY_MODEL = "opencode-go/deepseek-v4-flash"
        receipt = self.run_canary()
        self.assertBlocked("NON_SUBSCRIPTION_MODEL", receipt=receipt)
        self.assertEqual(self.catalog_calls, [])

    def test_catalog_does_not_hide_a_working_explicit_route(self):
        client = FakeClient(result=claim_result())
        receipt = self.run_canary(
            http_get=self.catalog([MODEL + "-high", "opencode-go/deepseek-v4-flash"]),
            client=client,
        )
        self.assertEqual(receipt["status"], "CANARY_PASSED")
        self.assertFalse(receipt["exact_model_in_catalog"])
        self.assertEqual(receipt["catalog_models_count"], 2)
        self.assertEqual(client.calls, 1)

        def failed(url, headers, timeout):
            return 502, b"upstream unavailable"

        receipt = self.run_canary(http_get=failed)
        self.assertBlocked("CATALOG_READBACK_FAILED", receipt=receipt)

    def test_canary_passes_only_with_model_schema_usage_and_meaningful_claim(self):
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
        self.assertTrue(receipt["subscription_gateway_verified"])
        self.assertEqual(receipt["latency_seconds"], 0.4)
        written = json.loads(self.receipt_path.read_text())
        self.assertEqual(written, receipt)
        serialized = json.dumps(receipt)
        self.assertNotIn("10 euro", serialized)
        self.assertNotIn("TRANSCRIPT", serialized)
        self.assertNotIn("opaque-key", serialized)

    def test_gateway_wire_model_without_provider_prefix_matches_tiered_route(self):
        client = FakeClient(
            result=claim_result(returned_model="gemini-3.8-flash-tiered")
        )
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=client)
        self.assertEqual(receipt["status"], "CANARY_PASSED")
        self.assertTrue(receipt["model_identity_exact"])
        self.assertEqual(receipt["model_returned"], "gemini-3.8-flash-tiered")

    def test_missing_cost_field_is_reported_as_unknown_without_fake_zero(self):
        client = FakeClient(result=claim_result(observed_cost_usd=None))
        receipt = self.run_canary(http_get=self.catalog([]), client=client)
        self.assertEqual(receipt["status"], "CANARY_PASSED")
        self.assertIsNone(receipt["observed_cost_usd"])

    def test_claim_count_alone_cannot_pass_a_meaningful_numeric_canary(self):
        original = claim_result().claims[0]
        irrelevant_claim = ExtractedAtomicClaim(
            normalized_claim="Il cielo è limpido.",
            claim_type=original.claim_type,
            check_worthy=True,
            numeric_sensitive=False,
            speaker=original.speaker,
            source_timestamp=original.source_timestamp,
            source_segment_indices=(0,),
        )
        client = FakeClient(result=claim_result(claims=(irrelevant_claim,)))
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=client)
        self.assertBlocked(
            "CANARY_NO_MEANINGFUL_CLAIMS", receipt=receipt, executed=True
        )

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

    def test_subscription_exhaustion_remains_blocked(self):
        client = FakeClient(error=RuntimeError("OMNIROUTE_HTTP_429:QUOTA_EXHAUSTED"))
        receipt = self.run_canary(http_get=self.catalog([MODEL]), client=client)
        self.assertBlocked("SUBSCRIPTION_QUOTA_EXHAUSTED", receipt=receipt, executed=True)

    def test_no_api_key_or_api_url_from_arguments_is_required_as_secret(self):
        receipt = self.run_canary(
            api_key="",
            http_get=self.catalog([MODEL]),
            client=FakeClient(result=claim_result()),
        )
        self.assertBlocked("OMNIROUTE_API_KEY_MISSING", receipt=receipt)


if __name__ == "__main__":
    unittest.main()
