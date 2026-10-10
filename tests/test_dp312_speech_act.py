"""DP-312 private hypotheses; none of these receipts approve publication."""

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.context_integrity import (  # noqa: E402
    assess_speech_act_context,
    verify_speech_act_context_metadata,
)
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    TranslationReviewState,
    assess_translation,
)


def assess(text, *, target=None, utterer="person:presenter", **kwargs):
    target = target or text
    start = text.index(target)
    return assess_speech_act_context(
        source_text=text,
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        quote_start=start,
        quote_end=start + len(target),
        turn_start=0,
        turn_end=len(text),
        utterer_id=utterer,
        turn_speaker_ids=(utterer,),
        source_part_ref="capture:part-a",
        turn_complete=True,
        language="it",
        **kwargs,
    )


class SpeechActContextTests(unittest.TestCase):
    def test_explicit_direct_italian_english_german_assertion_is_only_private_candidate(self):
        cases = (
            ("Io sostengo che questa misura sia utile.", "it"),
            ("I support the measure.", "en"),
            ("Ich unterstütze diese Maßnahme.", "de"),
        )
        for source, language in cases:
            with self.subTest(language=language):
                result = assess_speech_act_context(
                    source_text=source,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0,
                    quote_end=len(source),
                    turn_start=0,
                    turn_end=len(source),
                    utterer_id="person:a",
                    turn_speaker_ids=("person:a",),
                    source_part_ref="capture:a",
                    turn_complete=True,
                    language=language,
                )
                self.assertEqual(result.speech_act, "ASSERTION")
                self.assertEqual(result.stance, "ENDORSE")
                self.assertEqual(result.state, "CANDIDATE_PRIVATE")
                self.assertFalse(result.publication_authority)

    def test_historical_quotation_criticized_is_not_endorsed(self):
        text = "Critico lo slogan «Io sostengo che questa misura sia utile»."
        result = assess(
            text,
            target="Io sostengo che questa misura sia utile",
            quoted_author_id="person:historic",
        )
        self.assertEqual(result.utterer_id, "person:presenter")
        self.assertEqual(result.quoted_author_id, "person:historic")
        self.assertEqual(result.speech_act, "CRITIQUE")
        self.assertEqual(result.stance, "DISTANCE")
        self.assertNotEqual(result.stance, "ENDORSE")
        self.assertNotIn(text, repr(result.to_metadata()))

    def test_reported_quote_and_performance_do_not_endorse(self):
        for source, act in (
            ("Secondo Ada, «Io sostengo che il piano è utile».", "REPORT"),
            ("Recito «Io sostengo che il piano è utile».", "PERFORMANCE"),
        ):
            with self.subTest(source=source):
                result = assess(
                    source,
                    target="Io sostengo che il piano è utile",
                    quoted_author_id="person:ada",
                )
                self.assertEqual(result.speech_act, act)
                self.assertNotEqual(result.stance, "ENDORSE")

    def test_explicit_first_person_opinion_is_not_report_of_somebody_else(self):
        for source, language in (
            ("Secondo me il piano è utile.", "it"),
            ("In my opinion the plan is useful.", "en"),
            ("Meiner Meinung nach ist der Plan sinnvoll.", "de"),
        ):
            with self.subTest(language=language):
                result = assess_speech_act_context(
                    source_text=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source), turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True, language=language,
                )
                self.assertEqual(result.speech_act, "OPINION")
                self.assertEqual(result.stance, "ENDORSE")
                self.assertFalse(result.publication_authority)

    def test_german_translation_stays_held_under_existing_wording_review(self):
        translation = assess_translation(
            source_text="Ich unterstütze den Plan nicht.",
            translated_text="Non sostengo il piano.",
            source_language="de",
            target_language="it",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertEqual(translation.state, TranslationReviewState.NEEDS_REVIEW)
        self.assertIn("LANGUAGE_RISK_RULE_UNAVAILABLE", translation.signal_codes)
        self.assertFalse(translation.public_quote_eligible)

    def test_direct_denial_preserves_negation_and_refusal_to_endorse(self):
        text = "Non sostengo che il piano funzioni."
        result = assess(text)
        self.assertEqual(result.speech_act, "DENIAL")
        self.assertEqual(result.stance, "REFUTE")
        self.assertEqual(result.polarity, "NEGATED")
        clipped = assess(text, target="sostengo che il piano funzioni.")
        self.assertEqual(clipped.state, "HOLD_FOR_CONTEXT")
        self.assertIn("NEGATION_OUTSIDE_QUOTE", clipped.signal_codes)

    def test_endorsing_a_negative_proposition_is_not_denial_of_endorsement(self):
        result = assess("Io sostengo che non aumenteremo le tasse.")
        self.assertEqual(result.speech_act, "ASSERTION")
        self.assertEqual(result.stance, "ENDORSE")
        self.assertEqual(result.polarity, "NEGATED")
        self.assertEqual(result.state, "CANDIDATE_PRIVATE")

    def test_ambiguous_german_negation_scope_holds_without_fake_endorsement(self):
        source = "Ich unterstütze diese Maßnahme nicht."
        result = assess_speech_act_context(
            source_text=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0, quote_end=len(source), turn_start=0, turn_end=len(source),
            utterer_id="person:a", turn_speaker_ids=("person:a",),
            source_part_ref="part:a", turn_complete=True, language="de",
        )
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
        self.assertEqual(result.stance, "UNKNOWN")
        self.assertIn("NEGATION_SCOPE_UNRESOLVED", result.signal_codes)

    def test_conditional_endorsement_requires_full_semantic_check(self):
        for source, language in (
            ("Io sostengo che il piano sia utile solo se il prezzo scende.", "it"),
            ("I support the measure if it is temporary.", "en"),
            ("Ich unterstütze den Plan, wenn die Kosten sinken.", "de"),
        ):
            with self.subTest(language=language):
                result = assess_speech_act_context(
                    source_text=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source), turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True, language=language,
                )
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertNotEqual(result.stance, "ENDORSE")
                self.assertIn("CONDITIONAL_CONTEXT_REQUIRES_INTERPRETATION", result.signal_codes)

    def test_quoted_author_metadata_cannot_relabel_direct_assertion(self):
        result = assess(
            "Io sostengo che il piano sia utile.",
            quoted_author_id="person:historic",
        )
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
        self.assertNotEqual(result.stance, "ENDORSE")
        self.assertIn("QUOTED_AUTHOR_WITHOUT_QUOTE", result.signal_codes)

    def test_unknown_sentence_does_not_become_endorsement(self):
        result = assess("Il piano avrà successo.")
        self.assertEqual(result.speech_act, "UNKNOWN")
        self.assertEqual(result.stance, "UNKNOWN")
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")

    def test_question_and_quoted_self_assertion_are_not_self_endorsement(self):
        question = assess("Sostieni che il piano funzioni?")
        self.assertEqual(question.speech_act, "QUESTION")
        self.assertNotEqual(question.stance, "ENDORSE")
        quote = assess("«Io sostengo che il piano funzioni.»", quoted_author_id="person:presenter")
        self.assertEqual(quote.speech_act, "QUOTE")
        self.assertNotEqual(quote.stance, "ENDORSE")

    def test_single_quoted_support_does_not_become_endorsement(self):
        for text in ("'I support the policy.'", "‘I support the policy.’"):
            with self.subTest(text=text):
                result = assess_speech_act_context(
                    source_text=text, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    quote_start=0, quote_end=len(text), turn_start=0, turn_end=len(text),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True, language="en",
                    quoted_author_id="person:historic",
                )
                self.assertEqual(result.speech_act, "QUOTE")
                self.assertNotEqual(result.stance, "ENDORSE")

    def test_multiple_sentences_cannot_be_collapsed_into_one_stance(self):
        source = "Io sostengo che il piano sia utile. Ma non sostengo che sia definitivo."
        result = assess(source)
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
        self.assertNotEqual(result.stance, "ENDORSE")
        self.assertIn("MULTI_SENTENCE_CONTEXT_REQUIRES_SPLIT", result.signal_codes)

    def test_unsupported_language_and_unconfirmed_complete_turn_hold(self):
        source = "Io sostengo che la misura è utile."
        unknown = assess_speech_act_context(
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0,
            quote_end=len(source),
            turn_start=0,
            turn_end=len(source),
            utterer_id="person:a",
            turn_speaker_ids=("person:a",),
            source_part_ref="part:a",
            turn_complete=True,
            language="fr",
        )
        self.assertIn("LANGUAGE_SEMANTICS_UNSUPPORTED", unknown.signal_codes)
        self.assertEqual(unknown.state, "HOLD_FOR_CONTEXT")
        self.assertEqual(unknown.stance, "UNKNOWN")
        incomplete = assess_speech_act_context(
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0,
            quote_end=len(source),
            turn_start=0,
            turn_end=len(source),
            utterer_id="person:a",
            turn_speaker_ids=("person:a",),
            source_part_ref="part:a",
            turn_complete=False,
            language="it",
        )
        self.assertIn("TURN_COMPLETENESS_UNVERIFIED", incomplete.signal_codes)
        self.assertEqual(incomplete.state, "HOLD_FOR_CONTEXT")

    def test_chopped_qualifier_after_turn_cannot_confirm_endorsement(self):
        text = "Io sostengo che il piano sia utile, ma solo fino a domani."
        end = text.index(", ma")
        result = assess_speech_act_context(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            quote_start=0,
            quote_end=end,
            turn_start=0,
            turn_end=end,
            utterer_id="person:a",
            turn_speaker_ids=("person:a",),
            source_part_ref="part:a",
            turn_complete=True,
            language="it",
        )
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
        self.assertIn("TURN_BOUNDARY_UNVERIFIED", result.signal_codes)

    def test_long_coherent_turn_beyond_legacy_window_is_not_truncated(self):
        source = "Io sostengo che " + ("la misura sia utile e concreta, " * 90) + "anche oggi."
        self.assertGreater(len(source), 2000)
        result = assess(source)
        self.assertEqual(result.context_start, 0)
        self.assertEqual(result.context_end, len(source))
        self.assertEqual(result.state, "CANDIDATE_PRIVATE")

    def test_montage_or_changed_speaker_holds(self):
        text = "Io sostengo che il piano sia utile."
        partial = assess_speech_act_context(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            quote_start=0,
            quote_end=len(text),
            turn_start=0,
            turn_end=len(text),
            utterer_id="person:a",
            turn_speaker_ids=("person:a", "person:b"),
            source_part_ref="part:a",
            context_parts=((0, 8, "part:a"), (8, len(text), "part:b")),
            turn_complete=True,
            language="it",
        )
        self.assertEqual(partial.state, "HOLD_FOR_CONTEXT")
        self.assertIn("SPEAKER_TURN_CONFLICT", partial.signal_codes)
        self.assertIn("MONTAGE_OR_SOURCE_BOUNDARY", partial.signal_codes)

    def test_unbalanced_quotation_and_unattributed_speaker_hold(self):
        text = "Io sostengo che «il piano sia utile."
        result = assess(text, utterer="person:a")
        self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
        self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
        unknown = assess_speech_act_context(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            quote_start=0, quote_end=len(text), turn_start=0, turn_end=len(text),
            utterer_id="", turn_speaker_ids=(), source_part_ref="part:a",
            turn_complete=True, language="it",
        )
        self.assertIn("UTTERER_PROVENANCE_REQUIRED", unknown.signal_codes)

    def test_metadata_replay_fails_if_source_or_stance_tampered(self):
        original = "Io sostengo che il piano sia utile."
        result = assess(original)
        metadata = result.to_metadata()
        self.assertEqual(
            verify_speech_act_context_metadata(metadata, source_text=original).binding_sha256,
            metadata["binding_sha256"],
        )
        altered = dict(metadata)
        altered["stance"] = "REFUTE"
        with self.assertRaisesRegex(ValueError, "SPEECH_ACT_BINDING_MISMATCH"):
            verify_speech_act_context_metadata(altered, source_text=original)
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
            verify_speech_act_context_metadata(metadata, source_text=original + " Ma ora nego.")

    def test_source_qualifier_change_invalidate_binding_and_stance(self):
        first = assess("Io sostengo che il piano sia utile.")
        second = assess("Io non sostengo che il piano sia utile.")
        self.assertNotEqual(first.binding_sha256, second.binding_sha256)
        self.assertEqual(first.stance, "ENDORSE")
        self.assertEqual(second.stance, "REFUTE")

    def test_invalid_hash_ranges_and_tampered_turn_are_refused(self):
        text = "Io sostengo che il piano sia utile."
        params = dict(
            source_text=text, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            quote_start=0, quote_end=len(text), turn_start=0, turn_end=len(text),
            utterer_id="person:a", turn_speaker_ids=("person:a",),
            source_part_ref="part:a", turn_complete=True, language="it",
        )
        for changes, code in (
            ({"source_sha256": "a" * 64}, "SOURCE_HASH_MISMATCH"),
            ({"quote_start": True}, "RANGE_INVALID"),
            ({"quote_end": len(text) + 1}, "RANGE_INVALID"),
            ({"turn_end": 5}, "RANGE_INVALID"),
            ({"turn_complete": "true"}, "TURN_COMPLETENESS_INVALID"),
            ({"turn_speaker_ids": None}, "SPEAKER_REFS_INVALID"),
            ({"context_parts": None}, "CONTEXT_PARTS_INVALID"),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, code):
                    assess_speech_act_context(**(params | changes))


if __name__ == "__main__":
    unittest.main()
