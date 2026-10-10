"""Provider admission regression: no credential alone authorizes remote work."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.provider_optin import (  # noqa: E402
    configure_provider_clients,
)


P = "DICHIARAZIONI_PUBBLICHE_"


class ProviderAdmissionTests(unittest.TestCase):
    def test_default_denies_remote_even_when_key_is_present(self):
        result = configure_provider_clients({"GROQ_API_KEY": "present-but-unapproved"})
        self.assertIsNone(result.groq_api_key)
        self.assertIsNone(result.local_asr)
        self.assertIsNone(result.claim_client)

    def test_official_claim_route_is_unchanged_and_local_is_explicit(self):
        official = configure_provider_clients({"OMNIROUTE_API_KEY": "opaque"})
        self.assertEqual(official.claim_client.provider_id, "omniroute")
        self.assertEqual(official.claim_client.model, "antigravity/gemini-3.8-flash-tiered")
        self.assertIsNone(official.local_asr)
        local = configure_provider_clients({
            P + "LOCAL_CLAIM_ENABLED": "1",
            P + "LOCAL_CLAIM_MODEL_SHA256": "a" * 64,
            P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": "0",
        })
        self.assertEqual(local.claim_client.provider_id, "ollama-local")
        self.assertEqual(local.claim_client.model, "qwen3:4b")
        self.assertEqual(local.claim_rate, 0.0)

    def test_local_claim_requires_pin_zero_rate_and_no_official_substitution(self):
        valid = {P + "LOCAL_CLAIM_ENABLED": "1",
                 P + "LOCAL_CLAIM_MODEL_SHA256": "f" * 64,
                 P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": "0"}
        for change, error in (
            ({"OMNIROUTE_API_KEY": "secret"}, "CONFLICTS_WITH_OFFICIAL"),
            ({P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": "0.01"}, "EXPLICIT_ZERO"),
            ({P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": ""}, "EXPLICIT_ZERO"),
            ({P + "LOCAL_CLAIM_MODEL_SHA256": ""}, "DIGEST_REQUIRED"),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                configure_provider_clients(valid | change)

    def test_local_asr_four_runtime_inputs_and_separate_opt_in(self):
        fields = {P + "LOCAL_ASR_AUDIO_ROOT": "/tmp/audio",
                  P + "LOCAL_ASR_CLI": "/tmp/whisper-cli",
                  P + "LOCAL_ASR_MODEL": "/tmp/ggml.bin",
                  P + "LOCAL_ASR_MODEL_SHA256": "f" * 64}
        self.assertIsNone(configure_provider_clients(fields).local_asr)
        with self.assertRaisesRegex(ValueError, "LOCAL_ASR_RUNTIME_NOT_CONFIGURED"):
            configure_provider_clients({P + "LOCAL_ASR_ENABLED": "1"})
        configured = configure_provider_clients(fields | {P + "LOCAL_ASR_ENABLED": "1"})
        self.assertEqual(configured.local_asr.model_sha256, "f" * 64)

    def test_remote_opt_in_needs_separate_credential_terms_privacy_and_spend(self):
        base = {P + "GROQ_REMOTE_ASR_ENABLED": "1"}
        for update, error in (
            ({}, "TERMS_ACCEPTED_REQUIRED"),
            ({P + "GROQ_REMOTE_ASR_TERMS_ACCEPTED": "1"}, "CONFIDENTIALITY_APPROVED_REQUIRED"),
            ({P + "GROQ_REMOTE_ASR_TERMS_ACCEPTED": "1",
              P + "GROQ_REMOTE_ASR_CONFIDENTIALITY_APPROVED": "1"}, "SPEND_APPROVED_REQUIRED"),
            ({P + "GROQ_REMOTE_ASR_TERMS_ACCEPTED": "1",
              P + "GROQ_REMOTE_ASR_CONFIDENTIALITY_APPROVED": "1",
              P + "GROQ_REMOTE_ASR_SPEND_APPROVED": "1"}, "DEDICATED_CREDENTIAL_REQUIRED"),
        ):
            with self.subTest(update=update), self.assertRaisesRegex(ValueError, error):
                configure_provider_clients(base | update)
        approved = base | {
            P + "GROQ_REMOTE_ASR_TERMS_ACCEPTED": "1",
            P + "GROQ_REMOTE_ASR_CONFIDENTIALITY_APPROVED": "1",
            P + "GROQ_REMOTE_ASR_SPEND_APPROVED": "1", "GROQ_API_KEY": "separate-key",
        }
        self.assertEqual(configure_provider_clients(approved).groq_api_key, "separate-key")
        self.assertIsNone(configure_provider_clients(approved | {P + "GROQ_REMOTE_ASR_ENABLED": "0"}).groq_api_key)

    def test_invalid_flags_and_costs_fail_before_client_construction(self):
        for env, error in (
            ({P + "LOCAL_ASR_ENABLED": "yes"}, "EXPLICIT_0_OR_1"),
            ({P + "LOCAL_CLAIM_ENABLED": "true"}, "EXPLICIT_0_OR_1"),
            ({P + "GROQ_REMOTE_ASR_ENABLED": "maybe"}, "EXPLICIT_0_OR_1"),
            ({P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": "NaN"}, "COST_RATE_INVALID"),
            ({P + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS": "-1"}, "COST_RATE_INVALID"),
        ):
            with self.subTest(env=env), self.assertRaisesRegex(ValueError, error):
                configure_provider_clients(env)


if __name__ == "__main__":
    unittest.main()
