"""DP-202: the historical Giuliani benchmark cannot bypass the live gates."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_extraction_benchmark import run_live_benchmark  # noqa: E402
from dichiarazioni_pubbliche.claim_extraction_transport import call_omniroute  # noqa: E402


class GiulianiLivePreflightTests(unittest.TestCase):
    def test_without_parent_receipt_no_source_data_or_provider_is_read(self):
        with (
            patch("dichiarazioni_pubbliche.claim_extraction_benchmark.load_reference_claims") as gold,
            patch("dichiarazioni_pubbliche.claim_extraction_benchmark.call_omniroute") as provider,
        ):
            with self.assertRaisesRegex(RuntimeError, "DP202_PARENT_CANARY_UNVERIFIED"):
                run_live_benchmark()
            gold.assert_not_called()
            provider.assert_not_called()

    def test_parent_receipt_alone_never_authorizes_source_processing(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "canary.json"
            receipt.write_text(json.dumps({
                "status": "CANARY_PASSED",
                "reason_code": "OK",
                "model_requested": "antigravity/gemini-3.8-flash-tiered",
                "model_returned": "gemini-3.8-flash-tiered",
                "subscription_gateway_verified": True,
                "schema_constrained": True,
                "model_identity_exact": True,
                "model_calls": 1,
                "request_id": "req-test",
                "usage": {"prompt_tokens": 32, "completion_tokens": 16},
                "observed_cost_usd": None,
            }))
            with patch("dichiarazioni_pubbliche.claim_extraction_benchmark.call_omniroute") as provider:
                with self.assertRaisesRegex(RuntimeError, "DP202_SOURCE_RIGHTS_UNVERIFIED"):
                    run_live_benchmark(parent_canary_receipt=receipt)
                provider.assert_not_called()

    def test_transport_rejects_substituted_provider_model(self):
        response = {
            "id": "req-2", "model": "opencode-go/deepseek-v4-flash",
            "usage": {"prompt_tokens": 25, "completion_tokens": 12},
            "choices": [{"message": {"content": "{\"claims\":[]}"}}],
        }
        with patch("urllib.request.urlopen", return_value=self._reply(response)):
            with self.assertRaisesRegex(RuntimeError, "DP202_MODEL_SUBSTITUTED"):
                call_omniroute(prompt="synthetic", model="antigravity/gemini-3.8-flash-tiered",
                               base_url="http://127.0.0.1:20128", api_key="test")

    def test_transport_rejects_charge_on_subscription_route(self):
        response = {
            "id": "req-3", "model": "gemini-3.8-flash-tiered",
            "usage": {"prompt_tokens": 25, "completion_tokens": 12, "cost_usd": 0.01},
            "choices": [{"message": {"content": "{\"claims\":[]}"}}],
        }
        with patch("urllib.request.urlopen", return_value=self._reply(response)):
            with self.assertRaisesRegex(RuntimeError, "DP202_UNEXPECTED_PROVIDER_COST"):
                call_omniroute(prompt="synthetic", model="antigravity/gemini-3.8-flash-tiered",
                               base_url="http://127.0.0.1:20128", api_key="test")

    def test_transport_refuses_untrusted_gateway_before_post(self):
        with patch("urllib.request.urlopen") as post:
            with self.assertRaisesRegex(RuntimeError, "DP202_GATEWAY_UNAUTHORIZED"):
                call_omniroute(
                    prompt="synthetic", model="antigravity/gemini-3.8-flash-tiered",
                    base_url="https://untrusted.example", api_key="test",
                )
            post.assert_not_called()

    def test_transport_rejects_positive_charge_even_if_another_field_says_zero(self):
        response = {
            "id": "req-conflict", "model": "gemini-3.8-flash-tiered",
            "usage": {"prompt_tokens": 25, "completion_tokens": 12, "cost_usd": 0},
            "total_cost_usd": "0.03",
            "choices": [{"message": {"content": '{"claims":[]}'}}],
        }
        with patch("urllib.request.urlopen", return_value=self._reply(response)):
            with self.assertRaisesRegex(RuntimeError, "DP202_UNEXPECTED_PROVIDER_COST"):
                call_omniroute(
                    prompt="synthetic", model="antigravity/gemini-3.8-flash-tiered",
                    base_url="http://127.0.0.1:20128", api_key="test",
                )

    @staticmethod
    def _reply(value):
        body = json.dumps(value).encode("utf-8")

        class Reply:
            status = 200

            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        return Reply()


if __name__ == "__main__":
    unittest.main()
