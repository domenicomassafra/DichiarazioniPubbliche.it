import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
