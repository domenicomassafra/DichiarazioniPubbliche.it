import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_extraction_benchmark import (  # noqa: E402
    ExtractedClaim,
    ReferenceClaim,
    build_prompt,
    evaluate_extraction,
    parse_model_payload,
    parse_timestamp,
)


def _ref(
    claim_id: str,
    timestamp: str,
    text: str,
    *,
    claim_type: str = "NUMERIC_STATISTIC",
) -> ReferenceClaim:
    return ReferenceClaim(
        claim_id=claim_id,
        timestamp=timestamp,
        seconds=parse_timestamp(timestamp),
        speaker="Speaker A",
        claim_type=claim_type,
        normalized_claim=text,
        assessment="SUPPORTED",
        check_worthy=True,
        numeric_sensitive="10" in text,
    )


def _pred(
    index: int,
    timestamp: str,
    text: str,
    *,
    claim_type: str = "NUMERIC_STATISTIC",
) -> ExtractedClaim:
    return ExtractedClaim(
        index=index,
        timestamp=timestamp,
        seconds=parse_timestamp(timestamp),
        speaker="Speaker A",
        claim_type=claim_type,
        claim_text=text,
        check_worthy=True,
        numeric_sensitive="10" in text,
        raw={},
    )


class ClaimExtractionBenchmarkTests(unittest.TestCase):
    def test_parse_timestamp(self):
        self.assertEqual(parse_timestamp("1:05"), 65)
        self.assertEqual(parse_timestamp("01:02:03"), 3723)

    def test_parse_fenced_json(self):
        fence = chr(96) * 3
        payload = parse_model_payload(
            fence + 'json\n{"claims":[{"claim_text":"Example"}]}\n' + fence
        )
        self.assertEqual(payload["claims"][0]["claim_text"], "Example")

    def test_exact_claims_match_with_full_precision_and_recall(self):
        refs = [
            _ref("C1", "0:10", "The budget is 10 million euro."),
            _ref("C2", "0:30", "The measure starts next year.", claim_type="CURRENT_POLICY"),
        ]
        preds = [
            _pred(1, "0:10", "The budget is 10 million euro."),
            _pred(2, "0:30", "The measure starts next year.", claim_type="CURRENT_POLICY"),
        ]
        report = evaluate_extraction(refs, preds)
        self.assertEqual(report["matched_claims"], 2)
        self.assertEqual(report["claim_recall"], 1.0)
        self.assertEqual(report["claim_precision"], 1.0)
        self.assertEqual(report["type_accuracy_on_matched"], 1.0)

    def test_extra_claim_reduces_precision(self):
        refs = [_ref("C1", "0:10", "The budget is 10 million euro.")]
        preds = [
            _pred(1, "0:10", "The budget is 10 million euro."),
            _pred(2, "2:10", "A separate unsupported claim."),
        ]
        report = evaluate_extraction(refs, preds)
        self.assertEqual(report["matched_claims"], 1)
        self.assertEqual(report["claim_recall"], 1.0)
        self.assertEqual(report["claim_precision"], 0.5)

    def test_prompt_contains_transcript_but_not_reference_claims(self):
        transcript = "[0:10] source words"
        prompt = build_prompt(transcript, ["CURRENT_POLICY", "NUMERIC_STATISTIC"])
        self.assertIn(transcript, prompt)
        self.assertIn("CURRENT_POLICY", prompt)
        self.assertNotIn("reference_claim", prompt)


if __name__ == "__main__":
    unittest.main()
