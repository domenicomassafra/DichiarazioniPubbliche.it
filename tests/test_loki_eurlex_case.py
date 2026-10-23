"""Real EUR-Lex OJ article 113, offline structural comparison for DP-160."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.candidate_extraction import (
    load_candidate_extraction_config, validate_provider_payload,
)
from dichiarazioni_pubbliche.loki_private_poc import LokiPrivatePOC


CASES = json.loads((Path(__file__).parent / "fixtures" /
                    "dp160_eurlex_article113_v1.json").read_text(encoding="utf-8"))


def payload(case: dict, claim: str) -> dict:
    return {
        "doc": case["doc"],
        "language": case["language"],
        "claim_types": {claim: "LEGAL_POLICY_STATUS"},
        "decomposition": json.dumps({"claims": [claim]}),
        "restoration": json.dumps({claim: case["doc"].rstrip(".")}),
        "checkworthiness": json.dumps({claim: "Yes"}),
        "queries": json.dumps({claim: {"Questions": [case["question"]]}}),
    }


class EurLexArticle113Tests(unittest.TestCase):
    def setUp(self):
        self.loki = LokiPrivatePOC(enabled=True)

    def test_official_italian_and_english_application_texts_are_span_bound(self):
        self.assertEqual(len(CASES["cases"]), 2)
        for case in CASES["cases"]:
            with self.subTest(source=case["id"]):
                outcome = self.loki.compare(**payload(case, case["claim"]))
                self.assertEqual(outcome.reason_code, "LOKI_PROPOSALS_REQUIRE_REVIEW")
                self.assertEqual(outcome.status, "HOLD")
                self.assertEqual(len(outcome.proposals), 1)
                proposal = outcome.proposals[0]
                self.assertEqual(case["doc"][proposal.source_start:proposal.source_end],
                                 case["doc"].rstrip("."))
                self.assertEqual(proposal.query_suggestions, (case["question"],))
                self.assertEqual(outcome.receipt["provider_calls"], 0)
                self.assertFalse(outcome.receipt["publication_authority"])

    def test_changed_legal_event_cannot_be_represented_as_same_claim(self):
        for case in CASES["cases"]:
            with self.subTest(source=case["id"]):
                outcome = self.loki.compare(**payload(case, case["invalid_claim"]))
                self.assertEqual(outcome.reason_code, "LOKI_LEGAL_EVENT_MISMATCH")
                self.assertEqual(outcome.proposals, ())
                self.assertEqual(outcome.status, "HOLD")

    def test_current_extractor_contract_is_structural_not_legal_entailment(self):
        for case in CASES["cases"]:
            with self.subTest(source=case["id"]):
                source = case["doc"]
                current = {"statements": [{
                    "start_char": 0, "end_char": len(source),
                    "normalized_statement": source,
                    "speech_mode": "DIRECT_UTTERANCE",
                    "claims": [{"normalized_claim": case["invalid_claim"],
                                "claim_type": "LEGAL_POLICY_STATUS", "check_worthy": True}],
                }]}
                validated = validate_provider_payload(
                    current, passage_text=source,
                    config=load_candidate_extraction_config(),
                )
                self.assertEqual(validated[0]["quote"], source)
                self.assertEqual(validated[0]["claims"][0]["normalized_claim"],
                                 case["invalid_claim"])


if __name__ == "__main__":
    unittest.main()
