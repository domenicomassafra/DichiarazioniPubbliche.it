import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

import dichiarazioni_pubbliche.local_claim_ollama as local  # noqa: E402
from dichiarazioni_pubbliche.local_claim_ollama import LocalOllamaClaimClient  # noqa: E402

DIGEST = "3" * 64
SOURCE = "[seg=4 0:00.000-0:03.000] Il costo previsto è 10 euro."


def response(source_quote, *, indices=None, worthy=True, done=True):
    body = {"claims": [{
        "source_timestamp": "0:00",
        "source_segment_indices": indices if indices is not None else [4],
        "speaker": "",
        "claim_type": "PRICE_STATISTIC",
        "claim_text": "Il costo previsto è 10 euro.",
        "check_worthy": worthy,
        "numeric_sensitive": True,
        "source_quote": source_quote,
    }]}
    return {
        "model": "qwen3:4b", "done": done, "done_reason": "stop",
        "message": {"content": json.dumps(body)},
        "prompt_eval_count": 20, "eval_count": 45,
    }


class LocalOllamaClaimClientTests(unittest.TestCase):
    def setUp(self):
        self.client = LocalOllamaClaimClient(expected_model_digest=DIGEST)
        self.calls = []

    def fake_request(self, path, *, payload=None):
        self.calls.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": "qwen3:4b", "digest": DIGEST}]}
        return response("Il costo previsto è 10 euro.")

    def test_bound_local_candidate_uses_strict_schema_and_is_not_omniroute(self):
        with patch.object(local, "_request", self.fake_request):
            result = self.client.extract(window_text=SOURCE, allowed_segment_indices=(4,))
        self.assertEqual(len(result.claims), 1)
        self.assertEqual(result.claims[0].source_segment_indices, (4,))
        self.assertEqual(result.claims[0].normalized_claim, "Il costo previsto è 10 euro.")
        self.assertEqual(self.client.provider_id, "ollama-local")
        self.assertNotEqual(self.client.prompt_version, "claim-extract-v1")
        self.assertEqual(self.client.model, "qwen3:4b")
        self.assertEqual(self.calls[0], ("/api/tags", None))
        request = self.calls[1][1]
        self.assertEqual(self.calls[1][0], "/api/chat")
        self.assertFalse(request["stream"])
        self.assertFalse(request["think"])
        self.assertEqual(request["options"]["temperature"], 0)
        self.assertEqual(request["format"]["additionalProperties"], False)
        self.assertEqual(result.usage, {"prompt_tokens": 20, "completion_tokens": 45})
        self.assertIsNone(result.observed_cost_usd)

    def test_drifted_model_never_receives_source_transcript(self):
        def mismatched(path, *, payload=None):
            self.calls.append(path)
            return {"models": [{"name": "qwen3:4b", "digest": "4" * 64}]}
        with patch.object(local, "_request", mismatched), self.assertRaisesRegex(RuntimeError, "NOT_PINNED"):
            self.client.extract(window_text=SOURCE, allowed_segment_indices=(4,))
        self.assertEqual(self.calls, ["/api/tags"])

    def test_unbound_or_malformed_response_refuses_candidate(self):
        for altered in (
            response("Un testo completamente inventato."),
            response("Il costo previsto è 10 euro.", indices=[99]),
            response("Il costo previsto è 10 euro.", worthy="true"),
            response("Il costo previsto è 10 euro.", done=False),
            {**response("Il costo previsto è 10 euro."), "done_reason": "length"},
        ):
            with self.subTest(altered=altered):
                def fake(path, *, payload=None):
                    return ({"models": [{"name": "qwen3:4b", "digest": DIGEST}]}
                            if path == "/api/tags" else altered)
                with patch.object(local, "_request", fake), self.assertRaises((ValueError, RuntimeError)):
                    self.client.extract(window_text=SOURCE, allowed_segment_indices=(4,))

    def test_quote_from_other_segment_does_not_bind_to_fabricated_citation(self):
        source = (SOURCE + "\n"
                  "[seg=5 0:03.000-0:06.000] La strada è chiusa.")
        attacker = response("La strada è chiusa.", indices=[4])
        def fake(path, *, payload=None):
            return ({"models": [{"name": "qwen3:4b", "digest": DIGEST}]}
                    if path == "/api/tags" else attacker)
        with patch.object(local, "_request", fake), self.assertRaisesRegex(ValueError, "QUOTE_UNBOUND"):
            self.client.extract(window_text=source, allowed_segment_indices=(4, 5))

    def test_fabricated_or_duplicate_source_segment_identity_fails_closed(self):
        source = SOURCE + "\n" + SOURCE
        with patch.object(local, "_request", self.fake_request), self.assertRaisesRegex(ValueError, "SEGMENT_DUPLICATE"):
            self.client.extract(window_text=source, allowed_segment_indices=(4,))

    def test_local_endpoint_and_pin_validation_fail_closed(self):
        for invalid in ("", "not-a-sha", "x" * 64):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "DIGEST_REQUIRED"):
                LocalOllamaClaimClient(expected_model_digest=invalid)
        with self.assertRaisesRegex(RuntimeError, "DESTINATION_INVALID"):
            local._request("http://evil.example/admin")
        with self.assertRaisesRegex(RuntimeError, "WINDOW_SIZE_INVALID"), patch.object(local, "_request", self.fake_request):
            self.client.extract(window_text="   ", allowed_segment_indices=(4,))
        self.assertEqual(self.client.max_output_tokens, 512)


if __name__ == "__main__":
    unittest.main()
