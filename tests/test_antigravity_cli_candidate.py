"""Exact native CLI selection and quota-guarded private extraction failures."""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.antigravity_cli_candidate import (  # noqa: E402
    AntigravityCliCandidateExtractionClient, parse_antigravity_usage,
)
from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    CandidateExtractionError, ProviderExtractionRequest,
)


MODEL = "gemini-3.8-flash-low"
QUOTA = "provider-plan:" + "a" * 64


def client(**overrides):
    return AntigravityCliCandidateExtractionClient(**({
        "model_id": MODEL,
        "account_scope_sha256": "b" * 64,
        "quota_remaining_requests": 4,
        "quota_remaining_tokens": 180_000,
        "quota_receipt_id": QUOTA,
        "cli_path": "/usr/local/bin/agy",
    } | overrides))


def output(*, response='{"statements":[]}', status="SUCCESS", model=None, tokens=25700):
    item = {"status": status, "response": response, "num_turns": 1,
            "usage": {"total_tokens": tokens, "input_tokens": 25200, "output_tokens": 500}}
    if model is not None:
        item["model"] = model
    return json.dumps({"event": "init", "init": {"tools": []}}) + "\n" + json.dumps({
        "event": "result", "result": item,
    }) + "\n"


def usage(*, weekly=99, hourly=99, weekly_reset=None):
    week = weekly_reset or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    hour = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    return json.dumps({"status": "SUCCESS", "response": "\n".join((
        f"Gemini Models\tWeekly Limit Remaining\t{weekly}%\t{week}",
        f"Gemini Models\tFive Hour Limit Remaining\t{hourly}%\t{hour}",
        "Claude and GPT models\tWeekly Limit Remaining\t100%\t" + week,
    ))})


class AntigravityCliTests(unittest.TestCase):
    def test_pins_real_cli_model_and_sandboxes_private_prompt_without_secrets(self):
        instance = client()
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if "/usage" in cmd:
                return SimpleNamespace(returncode=0, stdout=usage(), stderr="")
            if cmd[1:] == ["models"]:
                return SimpleNamespace(returncode=0, stdout="Fetching available models...\n" + MODEL + "\tGemini Flash Low\n", stderr="")
            return SimpleNamespace(returncode=0, stdout=output(), stderr="")

        with patch("subprocess.run", fake_run), patch.dict("os.environ", {
                "OMNIROUTE_API_KEY": "DO_NOT_PASS", "GROQ_API_KEY": "DO_NOT_PASS",
                "PATH": "/usr/local/bin", "HOME": "/home/demo",
        }):
            response, seconds = instance._post("Generate one private candidate only.")
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[2][0][:4], ["/usr/local/bin/agy", "--model", MODEL, "--mode"])
        self.assertIn("--sandbox", calls[2][0])
        self.assertIn("--disable-slash-commands", calls[2][0])
        self.assertIn("--input-format", calls[2][0])
        self.assertIn("stream-json", calls[2][0])
        self.assertNotIn("Generate one private candidate only.", " ".join(calls[2][0]))
        self.assertIn("Generate one private candidate only.", calls[2][1]["input"])
        self.assertNotIn("stdin", calls[2][1])
        self.assertEqual(calls[2][1]["env"].get("HOME"), "/home/demo")
        self.assertNotIn("OMNIROUTE_API_KEY", calls[2][1]["env"])
        self.assertNotIn("GROQ_API_KEY", calls[2][1]["env"])
        self.assertEqual(instance.last_live_quota["weekly"]["remaining_percent"], 99)
        self.assertEqual(response["usage"]["total_tokens"], 25700)
        self.assertEqual(instance.quota_requests, 3)
        self.assertEqual(instance.quota_tokens, 154300)

    def test_block_missing_model_before_sending_source(self):
        instance = client()
        with patch.object(instance, "_run", side_effect=[usage(), "gemini-3.7-flash-low\tNot requested\n"]) as run:
            with self.assertRaisesRegex(CandidateExtractionError, "MODEL_NOT_ADVERTISED"):
                instance._post("private statement window")
        self.assertEqual(run.call_count, 2)

    def test_declared_serve_model_drift_blocks_without_retries(self):
        instance = client()
        with patch.object(instance, "_run", side_effect=[usage(), MODEL + "\tName\n",
               output(model="gemini-3.7-flash-low")]) as run:
            with self.assertRaisesRegex(CandidateExtractionError, "SERVED_MODEL_DRIFT"):
                instance._post("private synthetic text")
        self.assertEqual(run.call_count, 3)
        self.assertEqual(instance.quota_requests, 3)

    def test_conflicting_reported_model_fields_fail_closed(self):
        """A matching display model may not mask a different served-model field."""
        instance = client()
        conflicting = json.loads(output().splitlines()[-1])
        conflicting["result"].update({"model": MODEL, "served_model": "gemini-3.7-flash-low"})
        with patch.object(instance, "_run", side_effect=[
            usage(), MODEL + "\tName\n", json.dumps(conflicting) + "\n",
        ]) as run:
            with self.assertRaisesRegex(CandidateExtractionError, "SERVED_MODEL_DRIFT"):
                instance._post("synthetic private passage")
        self.assertEqual(run.call_count, 3)
        self.assertEqual(instance.quota_requests, 3)
        self.assertEqual(instance.quota_tokens, 0)

    def test_nonzero_failure_exhausts_local_admission_until_new_snapshot(self):
        instance = client()
        with patch.object(instance, "_run", side_effect=[usage(), MODEL + "\tName\n",
                  CandidateExtractionError("ANTIGRAVITY_CLI_NONZERO_EXIT")]):
            with self.assertRaisesRegex(CandidateExtractionError, "NONZERO_EXIT"):
                instance._post("private synthetic text")
        self.assertEqual(instance.quota_tokens, 0)
        self.assertEqual(instance.quota_requests, 3)

    def test_malformed_usage_status_and_overdraw_block(self):
        for data, error in (
            (output(status="FAILED"), "NOT_SUCCESS"),
            (output(tokens=200_001), "QUOTA_OVERRUN"),
            (json.dumps({"event": "result", "result": {
                "status": "SUCCESS", "response": "{}", "num_turns": 1,
            }}), "USAGE_MISSING"),
        ):
            with self.subTest(error=error):
                instance = client()
                with patch.object(instance, "_run", side_effect=[usage(), MODEL + "\tName\n", data]):
                    with self.assertRaisesRegex(CandidateExtractionError, error):
                        instance._post("private synthetic text")

    def test_underreported_or_malformed_component_usage_cannot_preserve_quota(self):
        base = json.loads(output().splitlines()[-1])
        for modifications in (
            {"total_tokens": 1},  # 25,700 reported component tokens
            {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0},
            {"input_tokens": -1},
            {"output_tokens": True},
            {"output_tokens": None},
        ):
            with self.subTest(changes=modifications):
                instance = client()
                event = json.loads(json.dumps(base))
                event["result"]["usage"].update(modifications)
                with patch.object(instance, "_run", side_effect=[
                    usage(), MODEL + "\tName\n", json.dumps(event) + "\n",
                ]) as run:
                    with self.assertRaisesRegex(CandidateExtractionError, "USAGE_INVALID"):
                        instance._post("synthetic private passage")
                self.assertEqual(run.call_count, 3)
                self.assertEqual(instance.quota_requests, 3)
                self.assertEqual(instance.quota_tokens, 0)

    def test_invalid_account_model_quota_or_executable_block(self):
        for update, error in (
            ({"model_id": "agy/gemini-2.5-flash-low"}, "MODEL_ID_INVALID"),
            ({"model_id": "gemini-3.8-flash-invented"}, "MODEL_ID_INVALID"),
            ({"account_scope_sha256": "not-a-hash"}, "ACCOUNT_SCOPE_INVALID"),
            ({"quota_remaining_tokens": 1}, "QUOTA_INSUFFICIENT"),
            ({"quota_remaining_requests": 0}, "QUOTA_INSUFFICIENT"),
            ({"cli_path": "./fake-binary"}, "EXECUTABLE_MISSING"),
        ):
            with self.subTest(update=update), self.assertRaisesRegex(CandidateExtractionError, error):
                client(**update)

    def test_real_candidate_result_has_explicit_billing_and_unverified_serve_identity(self):
        instance = client()
        req = ProviderExtractionRequest(
            operation_key="operation:synthetic", run_id="run:synthetic",
            passage_id="passage:synthetic", content_id="content:synthetic",
            text="La fonte dice dieci euro.", language="it", alias_hints=(),
            max_statements=1, max_claims_per_statement=1,
            max_entity_mentions_per_statement=1,
            cost_upper_bound_usd=Decimal("0"),
        )
        with patch.object(instance, "_post", return_value=({
            "id": "agy:test", "choices": [{"message": {"content": '{"statements":[]}'}}],
            "usage": {"total_tokens": 100},
        }, 0.12)):
            receipt = instance.extract(req)
        self.assertEqual(receipt.payload, {"statements": []})
        self.assertEqual(receipt.cost_usd, Decimal("0"))
        self.assertEqual(receipt.receipt["billing_basis"], "ANTIGRAVITY_CLI_QUOTA_OVERAGE_DISABLED")
        self.assertEqual(receipt.receipt["served_model_identity"], "CLI_DOES_NOT_REPORT_SIGNED_SERVED_MODEL")
        self.assertTrue(receipt.receipt["private_review_required"])

    def test_native_usage_parse_requires_two_fresh_gemini_windows(self):
        valid = parse_antigravity_usage(usage())
        self.assertEqual(valid["scope"], "Gemini Models")
        self.assertEqual(valid["weekly"]["remaining_percent"], 99)
        for blob, error in (
            (usage(weekly=0), "GEMINI_QUOTA_LOW"),
            (usage(hourly=4), "GEMINI_QUOTA_LOW"),
            (usage(weekly_reset=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()), "RESET_INVALID"),
            (json.dumps({"status": "SUCCESS", "response": "Claude Models\tWeekly Limit Remaining\t100%\t2030-01-01T00:00:00Z"}), "GEMINI_QUOTA_MISSING"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(CandidateExtractionError, error):
                parse_antigravity_usage(blob)

    def test_low_live_family_quota_blocks_before_any_candidate_prompt(self):
        instance = client()
        with patch.object(instance, "_run", return_value=usage(weekly=3)) as run:
            with self.assertRaisesRegex(CandidateExtractionError, "GEMINI_QUOTA_LOW"):
                instance._post("private synthetic text")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(instance.quota_requests, 4)


if __name__ == "__main__":
    unittest.main()
