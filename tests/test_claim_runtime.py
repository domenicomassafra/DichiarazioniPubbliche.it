import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_runtime import (  # noqa: E402
    ExtractedAtomicClaim,
    OmniRouteClaimClient,
    deterministic_claim_id,
    estimate_claim_request_cost,
    load_claim_config,
)


class ClaimRuntimeTests(unittest.TestCase):
    def test_cost_estimate_requires_explicit_rate(self):
        self.assertIsNone(
            estimate_claim_request_cost(
                estimated_input_tokens=1000,
                max_output_tokens=1000,
                max_usd_per_1k_total_tokens=None,
            )
        )
        self.assertEqual(
            estimate_claim_request_cost(
                estimated_input_tokens=1000,
                max_output_tokens=1000,
                max_usd_per_1k_total_tokens=0.01,
            ),
            0.02,
        )

    def test_deterministic_claim_id_uses_source_mapping(self):
        claim = ExtractedAtomicClaim(
            normalized_claim="Il prezzo è 10 euro.",
            claim_type="PRICE_STATISTIC",
            check_worthy=True,
            numeric_sensitive=True,
            speaker="",
            source_timestamp="0:00",
            source_segment_indices=(2,),
        )
        left = deterministic_claim_id(
            content_id="content:a",
            window_sha256="a" * 64,
            prompt_version="v1",
            model="model",
            claim=claim,
        )
        right = deterministic_claim_id(
            content_id="content:a",
            window_sha256="a" * 64,
            prompt_version="v1",
            model="model",
            claim=claim,
        )
        self.assertEqual(left, right)
        changed = ExtractedAtomicClaim(
            normalized_claim=claim.normalized_claim,
            claim_type=claim.claim_type,
            check_worthy=claim.check_worthy,
            numeric_sensitive=claim.numeric_sensitive,
            speaker=claim.speaker,
            source_timestamp=claim.source_timestamp,
            source_segment_indices=(3,),
        )
        self.assertNotEqual(
            left,
            deterministic_claim_id(
                content_id="content:a",
                window_sha256="a" * 64,
                prompt_version="v1",
                model="model",
                claim=changed,
            ),
        )

    def test_parser_rejects_segment_outside_window(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"claims":[{"source_timestamp":"0:00",'
                            '"source_segment_indices":[99],"speaker":"",'
                            '"claim_type":"CURRENT_POLICY",'
                            '"claim_text":"Una misura è in vigore.",'
                            '"check_worthy":true,"numeric_sensitive":false}]}'
                        )
                    }
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "OUTSIDE_WINDOW"):
            client._parse_claims(response, allowed_segment_indices={1, 2})

    def test_parser_rejects_string_booleans(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"claims":[{"source_timestamp":"0:00",'
                            '"source_segment_indices":[1],"speaker":"",'
                            '"claim_type":"CURRENT_POLICY",'
                            '"claim_text":"Una misura è in vigore.",'
                            '"check_worthy":"false","numeric_sensitive":false}]}'
                        )
                    }
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "BAD_CHECK_WORTHY"):
            client._parse_claims(response, allowed_segment_indices={1, 2})

    def test_parser_rejects_fractional_segment_indices(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"claims":[{"source_timestamp":"0:00",'
                            '"source_segment_indices":[1.5],"speaker":"",'
                            '"claim_type":"CURRENT_POLICY",'
                            '"claim_text":"Una misura è in vigore.",'
                            '"check_worthy":true,"numeric_sensitive":false}]}'
                        )
                    }
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "BAD_SEGMENTS"):
            client._parse_claims(response, allowed_segment_indices={1, 2})

    def test_parser_rejects_check_worthy_value_judgment(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        response = {
            "choices": [{"message": {"content": (
                '{"claims":[{"source_timestamp":"0:00",'
                '"source_segment_indices":[1],"speaker":"",'
                '"claim_type":"VALUE_JUDGMENT",'
                '"claim_text":"La politica è positiva.",'
                '"check_worthy":true,"numeric_sensitive":false}]}'
            )}}]
        }
        with self.assertRaisesRegex(ValueError, "NON_FACTUAL"):
            client._parse_claims(response, allowed_segment_indices={1, 2})

    def test_config_taxonomy_drift_fails_closed(self):
        config = load_claim_config()
        config["allowed_claim_types"] = config["allowed_claim_types"][:-1]
        client = OmniRouteClaimClient(api_key="x", config=config)
        with self.assertRaisesRegex(RuntimeError, "TAXONOMY_DRIFT"):
            client._parse_claims({"choices": [{"message": {"content": '{"claims":[]}'}}]}, allowed_segment_indices={1})

    def test_request_payload_carries_native_json_schema_bound_to_window(self):
        config = load_claim_config()
        client = OmniRouteClaimClient(api_key="x", config=config)
        payload = client.build_request_payload(
            prompt="prompt",
            max_tokens=256,
            allowed_segment_indices=(4, 2),
        )
        self.assertEqual(payload["model"], config["model"])
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_tokens"], 256)
        self.assertIs(payload["stream"], False)
        self.assertNotIn("tools", payload)
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]
        self.assertIs(schema["strict"], True)
        item = schema["schema"]["properties"]["claims"]["items"]
        self.assertIs(item["additionalProperties"], False)
        self.assertEqual(
            set(item["required"]),
            {"source_timestamp", "source_segment_indices", "speaker",
             "claim_type", "claim_text", "check_worthy", "numeric_sensitive"},
        )
        self.assertEqual(
            item["properties"]["claim_type"]["enum"],
            list(config["allowed_claim_types"]),
        )
        self.assertEqual(
            item["properties"]["source_segment_indices"]["items"]["enum"],
            [2, 4],
        )
        self.assertEqual(
            schema["schema"]["properties"]["claims"]["maxItems"],
            int(config["max_claims_per_window"]),
        )

    def test_empty_window_cannot_build_a_schema(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        with self.assertRaisesRegex(ValueError, "CLAIM_SCHEMA_EMPTY_WINDOW"):
            client.build_request_payload(
                prompt="prompt", max_tokens=1, allowed_segment_indices=()
            )

    def test_provider_model_substitution_is_rejected_not_accepted(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())

        class Reply:
            status = 200

            def read(self, _limit):
                return (
                    b'{"id":"req-1","model":"opencode-go/deepseek-v4-flash",'
                    b'"choices":[{"message":{"content":"{\\"claims\\":[]}"}}]}'
                )

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        with patch("urllib.request.urlopen", return_value=Reply()):
            with self.assertRaisesRegex(RuntimeError, "MODEL_SUBSTITUTED"):
                client._post(
                    "prompt", max_tokens=256, allowed_segment_indices=(0,)
                )

    def test_extract_records_returned_model_usage_and_request_id(self):
        client = OmniRouteClaimClient(api_key="x", config=load_claim_config())
        response = {
            "id": "req-9",
            "model": client.model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"message": {"content": (
                '{"claims":[{"source_timestamp":"0:00",'
                '"source_segment_indices":[0],"speaker":"",'
                '"claim_type":"PRICE_STATISTIC",'
                '"claim_text":"Il prezzo è 10 euro.",'
                '"check_worthy":true,"numeric_sensitive":true}]}'
            )}}],
        }
        with patch.object(client, "_post", return_value=(response, 0.1)):
            result = client.extract(window_text="[seg=0] testo", allowed_segment_indices=(0,))
        self.assertEqual(result.returned_model, client.model)
        self.assertEqual(result.request_id, "req-9")
        self.assertEqual(result.usage, {"prompt_tokens": 10, "completion_tokens": 5})


if __name__ == "__main__":
    unittest.main()
