"""Independent, original-text lexical gold through DP-312 and real consumers.

The gold labels live in a separately authored static fixture and are never
computed from classifier outputs. They are not a qualified real-source review.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.context_integrity import (
    assess_context_integrity,
    assess_speech_act_context,
    verify_speech_act_context_metadata,
)
from dichiarazioni_pubbliche.relation_runtime import (
    ScopedStatementRelationInput,
    StatementRelationKind,
    StatementRelationScope,
    evaluate_scoped_statement_relation,
)
from dichiarazioni_pubbliche.wording_contract import (
    TranslationReviewState,
    assess_translation,
)


GOLD = json.loads((Path(__file__).parent / "fixtures/dp312_multilingual_gold_v1.json").read_text(encoding="utf-8"))


def classify(row: dict, *, source: str | None = None):
    words = row["text"] if source is None else source
    return assess_speech_act_context(
        source_text=words,
        source_sha256=hashlib.sha256(words.encode("utf-8")).hexdigest(),
        quote_start=0,
        quote_end=len(words),
        turn_start=0,
        turn_end=len(words),
        utterer_id="person:fictional-utterer",
        quoted_author_id=row.get("quoted_author_id"),
        turn_speaker_ids=("person:fictional-utterer",),
        source_part_ref="fixture:" + row["id"],
        turn_complete=True,
        language=row["language"],
    )


class MultilingualSpeechActGoldNext(unittest.TestCase):
    def test_annotated_lexical_gold_against_real_preflight(self):
        self.assertEqual(GOLD["version"], "dp312-independent-contrast-gold-v1")
        self.assertFalse(GOLD["rights"]["third_party_content"])
        self.assertFalse(GOLD["rights"]["human_independent_review"])
        ids = [row["id"] for row in GOLD["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 20)
        self.assertTrue({"it", "de", "en", "fr"}.issubset({row["language"] for row in GOLD["cases"]}))
        for row in GOLD["cases"]:
            with self.subTest(case=row["id"]):
                outcome = classify(row)
                self.assertEqual(
                    (outcome.state, outcome.speech_act, outcome.stance),
                    (row["state"], row["speech_act"], row["stance"]),
                )
                if "risk" in row:
                    self.assertIn(row["risk"], outcome.signal_codes)
                self.assertFalse(outcome.publication_authority)
                self.assertEqual(
                    verify_speech_act_context_metadata(outcome.to_metadata(), source_text=row["text"]).binding_sha256,
                    outcome.binding_sha256,
                )
                with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
                    verify_speech_act_context_metadata(outcome.to_metadata(), source_text=row["text"] + "!")

    def test_translation_negative_quantifier_loss_is_review_required(self):
        for row in GOLD["translation_contrasts"]:
            with self.subTest(contrast=row["id"]):
                assessment = assess_translation(
                    source_text=row["source"], translated_text=row["translation"],
                    source_language=row["source_language"], target_language=row["target_language"],
                    method="HUMAN", human_reviewed=True,
                )
                self.assertIn(row["risk"], assessment.signal_codes)
                self.assertEqual(assessment.state, TranslationReviewState.NEEDS_REVIEW)
                self.assertFalse(assessment.public_quote_eligible)

    def test_real_relation_consumer_refuses_negative_false_agreement(self):
        cases = {row["id"]: row for row in GOLD["cases"]}
        scope = StatementRelationScope(
            jurisdiction_ref="jurisdiction:it", subject_ref="measure:1",
            period_start="2026-01-01", period_end="2026-12-31",
            modality="ASSERTED", condition_ref="NONE", location_ref="location:it",
        )

        def statement(case_id: str, identifier: str) -> ScopedStatementRelationInput:
            return ScopedStatementRelationInput(
                statement_id=identifier, person_id="person:fictional-utterer",
                statement_date="2026-03-01" if identifier.endswith("1") else "2026-04-01",
                proposition_key="proposition:plan", equivalence_review_ref="equivalence:review",
                statement_kind="FACTUAL", position="SUPPORT", scope=scope,
                speech_act=classify(cases[case_id]),
            )

        positive = statement("it-direct", "statement:1")
        for case_id in ("it-nessun", "it-niente", "it-nulla", "it-quote", "it-report"):
            with self.subTest(case=case_id):
                negative = statement(case_id, "statement:2")
                outcome = evaluate_scoped_statement_relation(positive, negative)
                self.assertEqual(outcome.kind, StatementRelationKind.HOLD)
                self.assertIn("NON_ENDORSED_OR_REPORTED_SPEECH", outcome.rationale_codes)
                self.assertFalse(outcome.publication_authority)

        # The same source part after correction is a distinct private decision.
        # A consumer must re-evaluate the revision, not reuse its former receipt.
        previous = classify(cases["it-direct"])
        revised = classify(cases["it-nessun"])
        self.assertNotEqual(previous.source_sha256, revised.source_sha256)
        self.assertNotEqual(previous.binding_sha256, revised.binding_sha256)
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
            verify_speech_act_context_metadata(
                previous.to_metadata(), source_text=cases["it-nessun"]["text"]
            )

    def test_changed_utterer_or_turn_source_holds_even_with_positive_words(self):
        words = "Io sostengo il piano."
        outcome = assess_speech_act_context(
            source_text=words, source_sha256=hashlib.sha256(words.encode()).hexdigest(),
            quote_start=0, quote_end=len(words), turn_start=0, turn_end=len(words),
            utterer_id="person:fictional-utterer", turn_speaker_ids=("person:other",),
            source_part_ref="fixture:it-direct", turn_complete=True, language="it",
        )
        self.assertEqual(outcome.state, "HOLD_FOR_CONTEXT")
        self.assertEqual(outcome.stance, "UNKNOWN")
        self.assertIn("SPEAKER_TURN_CONFLICT", outcome.signal_codes)

    def test_original_context_window_flags_negative_outside_clipped_span(self):
        for tail in (" niente.", " nulla."):
            with self.subTest(tail=tail):
                original = "Io sostengo" + tail
                fragment = assess_context_integrity(
                    source_text=original,
                    source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                    quote_start=0, quote_end=len("Io sostengo"),
                )
                self.assertIn("NEGATION_NEAR_BOUNDARY_OMITTED", fragment.signal_codes)
                self.assertEqual(fragment.state, "NEEDS_CONTEXT_REVIEW")


if __name__ == "__main__":
    unittest.main()
