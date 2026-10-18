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

    def test_negated_criticism_does_not_ascribe_dissent_to_utterer(self):
        # Synthetic, source-independent contrast pairs. A negated critical verb
        # is not evidence that the speaker actually criticized the proposal.
        cases = (
            ("Critico questa misura.", "Non critico questa misura.", "it"),
            ("I condemn the measure.", "I do not condemn the measure.", "en"),
            ("Ich kritisiere diese Maßnahme.", "Ich kritisiere diese Maßnahme nicht.", "de"),
        )
        for affirmative, negated, language in cases:
            with self.subTest(language=language):
                def run(text):
                    return assess_speech_act_context(
                        source_text=text,
                        source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        quote_start=0, quote_end=len(text), turn_start=0,
                        turn_end=len(text), utterer_id="person:a",
                        turn_speaker_ids=("person:a",), source_part_ref="part:a",
                        turn_complete=True, language=language,
                    )

                direct = run(affirmative)
                self.assertEqual((direct.speech_act, direct.stance, direct.state),
                                 ("CRITIQUE", "DISTANCE", "CANDIDATE_PRIVATE"))
                result = run(negated)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertEqual(result.speech_act, "UNKNOWN")
                self.assertIn("CRITIQUE_NEGATION_SCOPE_UNRESOLVED", result.signal_codes)
                self.assertNotEqual(result.binding_sha256, direct.binding_sha256)
                self.assertEqual(
                    verify_speech_act_context_metadata(
                        result.to_metadata(), source_text=negated
                    ).binding_sha256,
                    result.binding_sha256,
                )

    def test_negative_quantifiers_cannot_create_false_support_endorsement(self):
        # A negative direct object invalidates an apparent support cue. These
        # local controls do not stand in for source-licensed multilingual gold.
        cases = (
            ("I support the proposal.", "I support none of these proposals.", "en"),
            ("I support the proposal.", "I support neither proposal.", "en"),
            ("I support the proposal.", "I support nobody.", "en"),
            (
                "Ich unterstütze den Vorschlag.",
                "Ich unterstütze weder Vorschlag A noch Vorschlag B.",
                "de",
            ),
            (
                "Ich unterstütze den Vorschlag.",
                "Ich unterstütze niemanden.",
                "de",
            ),
        )

        def evaluate(source, language):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
                quote_start=0, quote_end=len(source), turn_start=0,
                turn_end=len(source), utterer_id="person:a",
                turn_speaker_ids=("person:a",), source_part_ref="capture:a",
                turn_complete=True, language=language,
            )

        for positive_source, negative_source, language in cases:
            with self.subTest(source=negative_source):
                direct = evaluate(positive_source, language)
                negative = evaluate(negative_source, language)
                self.assertEqual(
                    (direct.state, direct.speech_act, direct.stance),
                    ("CANDIDATE_PRIVATE", "ASSERTION", "ENDORSE"),
                )
                self.assertEqual(
                    (negative.state, negative.speech_act, negative.stance),
                    ("HOLD_FOR_CONTEXT", "UNKNOWN", "UNKNOWN"),
                )
                self.assertIn("NEGATION_SCOPE_UNRESOLVED", negative.signal_codes)
                self.assertNotEqual(direct.binding_sha256, negative.binding_sha256)
                self.assertEqual(
                    verify_speech_act_context_metadata(
                        negative.to_metadata(), source_text=negative_source
                    ).binding_sha256,
                    negative.binding_sha256,
                )
                with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
                    verify_speech_act_context_metadata(
                        negative.to_metadata(), source_text=positive_source
                    )

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

    def test_unbalanced_curly_single_quote_does_not_endorse_quoted_words(self):
        def classify(source):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language="en",
            )

        for fragment in (
            "‘I support the policy.",
            "’I support the policy.",
            "’I support the policy.‘",
            "‘I support the ‘policy’ today.’",
            "‘I’m certain I support the policy.",
        ):
            with self.subTest(fragment=fragment):
                result = classify(fragment)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertFalse(result.publication_authority)
                self.assertEqual(
                    verify_speech_act_context_metadata(
                        result.to_metadata(), source_text=fragment
                    ).binding_sha256,
                    result.binding_sha256,
                )

        for quoted in ("‘I support the policy.’", "‘I’m certain I support the policy.’"):
            with self.subTest(quoted=quoted):
                complete = classify(quoted)
                self.assertEqual((complete.speech_act, complete.stance),
                                 ("QUOTE", "NON_COMMITTAL"))
                self.assertEqual(complete.state, "CANDIDATE_PRIVATE")
        for plain in ("I support the policy.", "I’m certain I support the policy."):
            with self.subTest(plain=plain):
                direct = classify(plain)
                self.assertEqual((direct.speech_act, direct.stance, direct.state),
                                 ("ASSERTION", "ENDORSE", "CANDIDATE_PRIVATE"))

    def test_cjk_typographic_quote_delimiters_never_create_false_endorsement(self):
        def classify(source):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language="en",
            )

        # Quotation characters can surround an English translated/source
        # utterance; the English language tag cannot erase their semantics.
        for opening, closing in (("「", "」"), ("『", "』"), ("《", "》"), ("【", "】")):
            with self.subTest(style=opening):
                quoted = f"{opening}I support this policy.{closing}"
                result = classify(quoted)
                self.assertEqual((result.speech_act, result.stance), ("QUOTE", "NON_COMMITTAL"))
                self.assertFalse(result.publication_authority)
                self.assertEqual(
                    verify_speech_act_context_metadata(result.to_metadata(), source_text=quoted).binding_sha256,
                    result.binding_sha256,
                )
                for fragment in (
                    f"{opening}I support this policy.",
                    f"I support this policy.{closing}",
                    f"{closing}I support this policy.{opening}",
                    f"{opening}{opening}I support this policy.{closing}{closing}",
                ):
                    with self.subTest(fragment=fragment):
                        held = classify(fragment)
                        self.assertEqual(held.state, "HOLD_FOR_CONTEXT")
                        self.assertNotEqual(held.stance, "ENDORSE")
                        self.assertIn("UNBALANCED_QUOTATION", held.signal_codes)

        direct = classify("I support this policy.")
        self.assertEqual(
            (direct.state, direct.speech_act, direct.stance),
            ("CANDIDATE_PRIVATE", "ASSERTION", "ENDORSE"),
        )

    def test_curly_possessives_and_decade_elisions_are_not_broken_quotes(self):
        def classify(source):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language="en",
            )

        direct = (
            "I support workers’ rights.",
            "I support James’ plan.",
            "I support the ’90s policy.",
        )
        for source in direct:
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual((result.state, result.speech_act, result.stance),
                                 ("CANDIDATE_PRIVATE", "ASSERTION", "ENDORSE"))
                self.assertNotIn("UNBALANCED_QUOTATION", result.signal_codes)

        quoted = (
            "“I support workers’ rights.”",
            "‘I support workers’ rights.’",
            "‘I support James’ plan.’",
            "‘I support the ’90s policy.’",
        )
        for source in quoted:
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual((result.state, result.speech_act, result.stance),
                                 ("CANDIDATE_PRIVATE", "QUOTE", "NON_COMMITTAL"))
                self.assertNotIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertFalse(result.publication_authority)

        for fragment in (
            "‘I support workers’ rights.",
            "‘I support the ’90s policy.",
            "‘I support the ‘workers’ rights.’",
            "’I support James’ plan.",
        ):
            with self.subTest(fragment=fragment):
                result = classify(fragment)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)

    def test_curly_s_final_quote_closer_requires_explicit_pair_or_hold(self):
        def classify(source, language="en"):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language=language,
            )

        reported_quotes = (
            ("He said ‘I support this’ yesterday.", "en"),
            ("‘I support this’ she said.", "en"),
            ("Er sagte ‘Ich unterstütze das’ gestern.", "de"),
        )
        for source, language in reported_quotes:
            with self.subTest(source=source):
                result = classify(source, language)
                self.assertEqual(
                    (result.state, result.speech_act, result.stance),
                    ("CANDIDATE_PRIVATE", "REPORT", "NON_COMMITTAL"),
                )
                self.assertNotIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertFalse(result.publication_authority)
                self.assertEqual(
                    verify_speech_act_context_metadata(
                        result.to_metadata(), source_text=source
                    ).binding_sha256,
                    result.binding_sha256,
                )

        for source in (
            "I support this’ policy.",
            "I support THIS’ policy.",
            "I support his’ policy.",
            # A word-final s plus following word remains ambiguous with
            # a legitimate possessive; without independent scope, hold.
            "He said ‘I support James’ yesterday.",
            "He said ‘I support workers’ yesterday.",
        ):
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)

    def test_curly_quote_pairing_handles_unlisted_s_final_terms_without_endorsement(self):
        def classify(source, language="en"):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language=language,
            )

        reported = (
            ("He said ‘I support us’ today.", "en"),
            ("He said ‘I vote yes’ today.", "en"),
            ("He said ‘I support you always’ yesterday.", "en"),
            ("Er sagte ‘Ich unterstütze uns’ gestern.", "de"),
        )
        for source, language in reported:
            with self.subTest(source=source):
                result = classify(source, language)
                self.assertEqual(
                    (result.state, result.speech_act, result.stance),
                    ("CANDIDATE_PRIVATE", "REPORT", "NON_COMMITTAL"),
                )
                self.assertNotIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertEqual(
                    verify_speech_act_context_metadata(
                        result.to_metadata(), source_text=source
                    ).binding_sha256,
                    result.binding_sha256,
                )

        for source in (
            "I support us’ policy.",
            "I support yes’ policy.",
            "I support always’ policy.",
            "I support this’ policy.",
            "He said ‘I support workers’ yesterday.",
            "He said ‘I support James’ yesterday.",
            "He said ‘I support us’ yesterday.’",
            "‘I support us ‘always’ today.’",
            "’I support us’ today.",
        ):
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)

    def test_reversed_or_nested_double_curly_quotes_cannot_endorse(self):
        samples = (
            ("”I support the policy“", "en"),
            ("”Io sostengo che il piano funziona“", "it"),
            ("”Ich unterstütze die Maßnahme“", "de"),
            ("“I support the “policy”", "en"),
        )
        for source, language in samples:
            with self.subTest(source=source):
                result = assess_speech_act_context(
                    source_text=source,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source),
                    turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True,
                    language=language,
                )
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertFalse(result.publication_authority)

    def test_incomplete_low_double_and_nested_angle_quotes_never_endorse(self):
        cases = (
            ("„Ich unterstütze die Maßnahme.", "de"),
            ("„Ich unterstütze die Maßnahme„", "de"),
            ("‟I support the policy.", "en"),
            ("„I support the policy.", "en"),
            ("«I support «the policy»»", "en"),
            ("‹I support ‹the policy››", "en"),
        )
        for source, language in cases:
            with self.subTest(source=source):
                result = assess_speech_act_context(
                    source_text=source,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source),
                    turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True,
                    language=language,
                )
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertFalse(result.publication_authority)
        for source, language in (
            ("„Ich unterstütze die Maßnahme“", "de"),
            ("“I support the policy”", "en"),
        ):
            with self.subTest(source=source):
                result = assess_speech_act_context(
                    source_text=source,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source),
                    turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True,
                    language=language,
                )
                self.assertEqual((result.state, result.speech_act, result.stance),
                                 ("CANDIDATE_PRIVATE", "QUOTE", "NON_COMMITTAL"))

    def test_dangling_ascii_single_quotes_hold_without_harming_contractions(self):
        def classify(source):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language="en",
            )
        for source in (
            "'I support the policy.",
            "I support the policy.'",
            "He said 'I support the policy.",
            "He said I support the policy.'",
        ):
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
        for source in ("'I support the policy.'", "He said 'I support the policy' yesterday."):
            with self.subTest(source=source):
                result = classify(source)
                self.assertNotIn("UNBALANCED_QUOTATION", result.signal_codes)
                self.assertNotEqual(result.stance, "ENDORSE")
        plain = classify("I'm certain I support the policy.")
        self.assertEqual((plain.speech_act, plain.stance), ("ASSERTION", "ENDORSE"))

    def test_german_low_single_and_unsupported_quote_marks_cannot_endorse(self):
        def classify(source):
            return assess_speech_act_context(
                source_text=source,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                quote_start=0, quote_end=len(source),
                turn_start=0, turn_end=len(source),
                utterer_id="person:a", turn_speaker_ids=("person:a",),
                source_part_ref="part:a", turn_complete=True, language="de",
            )
        for source in (
            "‚Ich unterstütze die Maßnahme.",
            "‚Ich unterstütze die Maßnahme‚",
            "‛Ich unterstütze die Maßnahme.",
            "❛Ich unterstütze die Maßnahme.",
        ):
            with self.subTest(source=source):
                result = classify(source)
                self.assertEqual((result.state, result.stance),
                                 ("HOLD_FOR_CONTEXT", "UNKNOWN"))
                self.assertIn("UNBALANCED_QUOTATION", result.signal_codes)
        complete = classify("‚Ich unterstütze die Maßnahme‘")
        self.assertEqual((complete.state, complete.speech_act, complete.stance),
                         ("CANDIDATE_PRIVATE", "QUOTE", "NON_COMMITTAL"))

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
