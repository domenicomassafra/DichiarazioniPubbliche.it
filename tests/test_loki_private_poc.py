"""Synthetic multilingual Loki POC comparison; no model/network/storage."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    load_candidate_extraction_config, validate_provider_payload,
)
from dichiarazioni_pubbliche.claim_contract import validate_atomic_claim  # noqa: E402
from dichiarazioni_pubbliche.claim_research_plan import compile_claim_research_plan  # noqa: E402
from dichiarazioni_pubbliche.loki_private_poc import (  # noqa: E402
    LokiPrivatePOC, DONOR_COMMIT, ADAPTER_VERSION,
)


def fixture(doc, spans, types, votes, questions, *, language="it", reported=False):
    return dict(
        doc=doc, language=language, claim_types=types,
        decomposition=json.dumps({"claims": list(spans)}, ensure_ascii=False),
        restoration=json.dumps(spans, ensure_ascii=False),
        checkworthiness=json.dumps(votes, ensure_ascii=False),
        queries=json.dumps({c: {"Questions": questions[c]} for c in spans},
                           ensure_ascii=False),
        reported_speech=reported,
    )


class LokiPrivatePOCTests(unittest.TestCase):
    def setUp(self):
        self.poc = LokiPrivatePOC(enabled=True)

    def test_disabled_by_default_does_not_run(self):
        with self.assertRaisesRegex(ValueError, "LOKI_POC_DISABLED"):
            LokiPrivatePOC(enabled=False).compare(**self._italian())

    @staticmethod
    def _italian():
        return fixture(
            "Nel 2025 il Comune ha aperto 12 sportelli e 6 uffici.",
            {"Il Comune ha aperto 12 sportelli nel 2025": "Nel 2025 il Comune ha aperto 12 sportelli",
             "Il Comune ha aperto 6 uffici": "6 uffici"},
            {"Il Comune ha aperto 12 sportelli nel 2025": "NUMERIC_STATISTIC",
             "Il Comune ha aperto 6 uffici": "NUMERIC_STATISTIC"},
            {"Il Comune ha aperto 12 sportelli nel 2025": "Yes",
             "Il Comune ha aperto 6 uffici": "Yes"},
            {"Il Comune ha aperto 12 sportelli nel 2025": [
                "Quale documento ufficiale attesta 12 sportelli nel 2025?"],
             "Il Comune ha aperto 6 uffici": [
                "Quale documento ufficiale attesta 6 uffici?"]},
        )

    def test_italian_compound_claims_are_span_bound_and_private(self):
        payload = self._italian()
        left = self.poc.compare(**payload)
        right = self.poc.compare(**payload)
        self.assertEqual(left, right)
        self.assertEqual(left.status, "HOLD")
        self.assertEqual(len(left.proposals), 2)
        self.assertEqual(left.proposals[0].source_start, 0)
        self.assertEqual(left.proposals[0].source_end,
                         len("Nel 2025 il Comune ha aperto 12 sportelli"))
        self.assertTrue(all(item.check_worthy for item in left.proposals))
        self.assertEqual(left.receipt["provider_calls"], 0)
        self.assertEqual(left.receipt["provider_cost_usd"], "0")
        self.assertFalse(left.receipt["publication_authority"])
        self.assertFalse(left.receipt["persisted"])
        self.assertEqual(left.receipt["donor_commit"], DONOR_COMMIT)
        self.assertEqual(left.receipt["adapter"], ADAPTER_VERSION)
        self.assertNotIn(payload["doc"], str(left.receipt))

    def test_english_german_french_multilingual_private_fixture_parity(self):
        cases = [
            ("In 2024 the city opened 8 clinics.", "en",
             "The city opened 8 clinics in 2024", "In 2024 the city opened 8 clinics"),
            ("Im Jahr 2024 wurden 8 Kliniken eröffnet.", "de",
             "Im Jahr 2024 wurden 8 Kliniken eröffnet", "Im Jahr 2024 wurden 8 Kliniken eröffnet"),
            ("En 2024, la ville a ouvert 8 cliniques.", "fr",
             "La ville a ouvert 8 cliniques en 2024", "En 2024, la ville a ouvert 8 cliniques"),
        ]
        for doc, lang, claim, quote in cases:
            with self.subTest(lang=lang):
                payload = fixture(doc, {claim: quote}, {claim: "NUMERIC_STATISTIC"},
                                  {claim: "Yes"},
                                  {claim: ["Quelle source officielle confirme 8 en 2024?"]},
                                  language=lang)
                result = self.poc.compare(**payload)
                self.assertEqual(result.status, "HOLD")
                self.assertEqual(len(result.proposals), 1)
                self.assertEqual(doc[result.proposals[0].source_start:
                                     result.proposals[0].source_end], quote)

    def test_non_factual_is_never_checkworthy_or_researched(self):
        claim = "Questo servizio è meraviglioso"
        payload = fixture(claim + ".", {claim: claim}, {claim: "VALUE_JUDGMENT"},
                          {claim: "No"}, {claim: []})
        result = self.poc.compare(**payload)
        self.assertEqual(result.proposals[0].check_worthy, False)
        self.assertEqual(result.proposals[0].query_suggestions, ())
        baseline = compile_claim_research_plan(
            claim_id="claim:synthetic", claim_type="VALUE_JUDGMENT",
            coverage_needs=[], lane_adapters={},
        )
        self.assertEqual(baseline.status, "BLOCKED")
        self.assertIn("CLAIM_TYPE_NON_FACTUAL", baseline.blockers)
        payload["checkworthiness"] = json.dumps({claim: "Yes"})
        self.assertEqual(self.poc.compare(**payload).proposals, ())
        self.assertEqual(self.poc.compare(**payload).reason_code,
                         "LOKI_NON_FACTUAL_CHECKWORTHY")

    def test_reported_speech_requires_attribution_hold(self):
        claim = "Nel 2025 sono stati aperti 5 uffici"
        payload = fixture(
            "Il portavoce ha riferito che nel 2025 sono stati aperti 5 uffici.",
            {claim: "nel 2025 sono stati aperti 5 uffici"},
            {claim: "NUMERIC_STATISTIC"}, {claim: "Yes"},
            {claim: ["Dove è pubblicato il dato dei 5 uffici nel 2025?"]},
            reported=True,
        )
        result = self.poc.compare(**payload)
        self.assertEqual(result.reason_code, "LOKI_REPORTED_SPEECH_REQUIRES_ATTRIBUTION")
        self.assertEqual(result.proposals, ())

    def test_malformed_or_unbound_outputs_hold_without_query_fallback(self):
        base = self._italian()
        mutations = [
            ("decomposition", "__import__('os').system('echo unsafe')", "LOKI_OUTPUT_JSON_INVALID"),
            ("restoration", "{}", "LOKI_RESTORATION_INCOMPLETE"),
            ("checkworthiness", "{}", "LOKI_CHECKWORTHY_INCOMPLETE"),
            ("queries", "{}", "LOKI_QUERY_MAPPING_INVALID"),
            ("language", "xx", "LOKI_LANGUAGE_UNSUPPORTED"),
        ]
        for key, value, reason in mutations:
            with self.subTest(key=key):
                altered = dict(base, **{key: value})
                result = self.poc.compare(**altered)
                self.assertEqual(result.proposals, ())
                self.assertEqual(result.reason_code, reason)
                self.assertEqual(result.receipt["status"], "HOLD")

    def test_untrusted_time_quantity_and_queries_hold(self):
        base = self._italian()
        wrong_claim = "Il Comune ha aperto 99 sportelli nel 2025"
        wrong = dict(
            base,
            decomposition=json.dumps({"claims": [wrong_claim]}),
            restoration=json.dumps({
                wrong_claim: "Nel 2025 il Comune ha aperto 12 sportelli"}),
        )
        self.assertEqual(self.poc.compare(**wrong).reason_code,
                         "LOKI_QUANTITY_NOT_IN_SOURCE")
        bad_query = json.loads(base["queries"])
        bad_query["Il Comune ha aperto 6 uffici"]["Questions"] = [
            "Quale fonte conferma 900 uffici?"]
        result = self.poc.compare(**dict(base, queries=json.dumps(bad_query)))
        self.assertEqual(result.reason_code, "LOKI_QUERY_QUANTITY_NOT_IN_CLAIM")
        self.assertEqual(result.proposals, ())
        repeated = fixture("8 uffici e 8 uffici", {"8 uffici": "8 uffici"},
                           {"8 uffici": "NUMERIC_STATISTIC"},
                           {"8 uffici": "Yes"},
                           {"8 uffici": ["Quale fonte conferma 8 uffici?"]})
        self.assertEqual(self.poc.compare(**repeated).reason_code,
                         "LOKI_SOURCE_SPAN_AMBIGUOUS")

    def test_existing_schema_and_provenance_requirements_win(self):
        payload = self._italian()
        current = {
            "statements": [{
                "start_char": 0, "end_char": len(payload["doc"]),
                "normalized_statement": payload["doc"], "speech_mode": "DIRECT_UTTERANCE",
                "claims": [{"normalized_claim": "Il Comune ha aperto 12 sportelli nel 2025",
                            "claim_type": "NUMERIC_STATISTIC", "check_worthy": True}],
            }],
        }
        validated = validate_provider_payload(
            current, passage_text=payload["doc"],
            config=load_candidate_extraction_config(),
        )
        self.assertEqual(validated[0]["quote"], payload["doc"])
        with self.assertRaisesRegex(ValueError, "CLAIM_SEGMENT_PROVENANCE_REQUIRED"):
            validate_atomic_claim(
                claim_id="claim:test", content_id="content:test",
                normalized_claim="Il Comune ha aperto 12 sportelli nel 2025",
                claim_type="NUMERIC_STATISTIC", statement_date="2025-01-01",
                check_worthy=True,
            )
        self.assertEqual(self.poc.compare(**payload).status, "HOLD")


if __name__ == "__main__":
    unittest.main()
