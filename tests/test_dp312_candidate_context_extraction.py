"""Source-bound candidate and translation safety regressions (DP-312)."""

import hashlib
import unittest
from dataclasses import replace

from tests.test_candidate_extraction import TEXT, media_context, valid_payload, written_context
from dichiarazioni_pubbliche.candidate_extraction import (
    load_candidate_extraction_config,
    prepare_extraction_batch,
    validate_provider_payload,
)
from dichiarazioni_pubbliche.context_integrity import verify_speech_act_context_metadata
from dichiarazioni_pubbliche.wording_contract import TranslationReviewState, assess_translation


class CandidateSpeechActBoundaryTests(unittest.TestCase):
    def test_candidate_stores_source_bound_private_speech_act_without_endorsement_authority(self):
        examples = (
            ("Io sostengo che il piano funziona.", "ASSERTION"),
            ("Secondo Luca, «Io sostengo che il piano funziona».", "REPORT"),
            ("Critico «Io sostengo che il piano funziona».", "CRITIQUE"),
        )
        for source, expected_act in examples:
            with self.subTest(source=source):
                # An approved segment speaker identifies the current utterer,
                # not the quoted author or a complete context review.
                context = replace(
                    media_context(), text=source,
                    text_sha256=hashlib.sha256(source.encode()).hexdigest(),
                )
                payload = {
                    "statements": [{
                        "start_char": 0, "end_char": len(source),
                        "normalized_statement": source,
                        "speaker_mention": None,
                        "entity_mentions": [], "claims": [],
                    }],
                }
                parsed = validate_provider_payload(
                    payload, passage_text=source,
                    config=load_candidate_extraction_config(),
                )
                batch = prepare_extraction_batch(
                    run_id="run:speech-act", context=context,
                    provider_statements=parsed, alias_matches=(),
                    provider_model="model", provider_version="v1",
                )
                metadata = batch.statements[0].statement.metadata["speech_act_context"]
                self.assertEqual(metadata["speech_act"], expected_act)
                self.assertEqual(metadata["utterer_id"], "person:speaker")
                self.assertIsNone(metadata["quoted_author_id"])
                self.assertEqual(metadata["state"], "HOLD_FOR_CONTEXT")
                self.assertFalse(verify_speech_act_context_metadata(
                    metadata, source_text=source,
                ).publication_authority)
                self.assertIn("TURN_COMPLETENESS_UNVERIFIED", metadata["signal_codes"])
                with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
                    verify_speech_act_context_metadata(
                        metadata, source_text=source + " Modificato.",
                    )

    def test_written_candidate_cannot_assign_reported_words_to_quoted_person(self):
        parsed = validate_provider_payload(
            valid_payload(), passage_text=TEXT,
            config=load_candidate_extraction_config(),
        )
        batch = prepare_extraction_batch(
            run_id="run:written-attribution", context=written_context(),
            provider_statements=parsed, alias_matches=(),
            provider_model="model", provider_version="v1",
        )
        statement = batch.statements[0].statement
        semantic = statement.metadata["speech_act_context"]
        self.assertEqual(semantic["utterer_id"], "")
        self.assertEqual(semantic["state"], "HOLD_FOR_CONTEXT")
        self.assertEqual(semantic["stance"], "UNKNOWN")
        self.assertIn("UTTERER_PROVENANCE_REQUIRED", semantic["signal_codes"])
        self.assertEqual(batch.claims[0].metadata["speech_act_context"], semantic)

    def test_german_translation_checks_negation_and_holds_ambiguous_nouns(self):
        translation = assess_translation(
            source_text="Ich unterstütze den Plan nicht.",
            translated_text="Non sostengo il piano.",
            source_language="de",
            target_language="it",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertEqual(translation.state, TranslationReviewState.NEEDS_REVIEW)
        self.assertNotIn("LANGUAGE_RISK_RULE_UNAVAILABLE", translation.signal_codes)
        self.assertNotIn("NEGATION_CHANGED", translation.signal_codes)
        # German capitalizes nouns; lexical name checks cannot assert that
        # 'Plan' and 'piano' are equivalent without independent review.
        self.assertIn("PROPER_NAME_CHANGED", translation.signal_codes)
        self.assertFalse(translation.public_quote_eligible)
