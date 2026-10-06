import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    DERIVED_REPRESENTATION_ROLE,
    SOURCE_OCCURRENCE_ROLE,
    TranslationReviewState,
    WordingType,
    assert_direct_quote_eligible,
    assess_translation,
    make_derived_wording,
    make_normalized_claim_wording,
    make_source_occurrence_wording,
    make_summary_wording,
    make_translation_wording,
    validate_wording_contract_metadata,
    wording_contract_metadata,
)


class WordingContractTests(unittest.TestCase):
    def test_source_occurrence_is_only_direct_quote_eligible_type(self):
        source = make_source_occurrence_wording(
            occurrence_id="statement:1",
            text_sha256="a" * 64,
            language="it",
            derivation_version="test-v1",
        )
        normalized = make_normalized_claim_wording(
            occurrence_id="statement:1",
            normalized_claim="Le tasse non aumenteranno.",
            language="it",
            derivation_version="test-v1",
        )
        self.assertEqual(source.wording_type, WordingType.VERBATIM_ORIGINAL)
        self.assertTrue(source.direct_quote_eligible)
        self.assertEqual(normalized.wording_type, WordingType.PARAPHRASE)
        self.assertFalse(normalized.direct_quote_eligible)
        with self.assertRaisesRegex(ValueError, "WORDING_DIRECT_QUOTE_FORBIDDEN"):
            assert_direct_quote_eligible(normalized)

    def test_normalized_claim_is_paraphrase_even_if_text_matches_source_wording(self):
        text = "Non aumenteremo le tasse."
        metadata = wording_contract_metadata(
            occurrence_id="statement:1",
            source_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            normalized_claim=text,
            language="it",
            derivation_version="test-v1",
        )
        self.assertEqual(
            metadata["source_occurrence"]["wording_type"],
            "VERBATIM_ORIGINAL",
        )
        self.assertEqual(
            metadata["normalized_claim"]["wording_type"],
            "PARAPHRASE",
        )
        self.assertFalse(metadata["normalized_claim"]["direct_quote_eligible"])

    def test_cleanup_and_summary_are_derived_not_quote_authority(self):
        cleanup = make_derived_wording(
            wording_type=WordingType.PARAPHRASE,
            occurrence_id="statement:1",
            text="Non aumenteremo le tasse.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_method="EDITORIAL_CLEANUP",
            derivation_version="test-v1",
            author_ref="editor:1",
        )
        summary = make_summary_wording(
            occurrence_id="statement:1",
            summary="Promessa di non aumentare le tasse.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
            reviewer_ref="reviewer:1",
        )
        for representation in (cleanup, summary):
            with self.subTest(wording_type=representation.wording_type):
                self.assertEqual(
                    representation.representation_role,
                    DERIVED_REPRESENTATION_ROLE,
                )
                self.assertFalse(representation.direct_quote_eligible)
                with self.assertRaisesRegex(
                    ValueError,
                    "WORDING_DIRECT_QUOTE_FORBIDDEN",
                ):
                    assert_direct_quote_eligible(representation)

    def test_translation_retains_source_occurrence_languages_review_and_signals(self):
        translation = make_translation_wording(
            occurrence_id="statement:foreign:1",
            source_text="We will not raise taxes.",
            translated_text="Non aumenteremo le tasse.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="en",
            target_language="it",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
            reviewer_ref="reviewer:1",
        )
        metadata = wording_contract_metadata(
            occurrence_id="statement:foreign:1",
            source_text_sha256=hashlib.sha256(
                b"We will not raise taxes."
            ).hexdigest(),
            normalized_claim="Non saranno aumentate le tasse.",
            language="en",
            derivation_version="test-v1",
            source_provenance={
                "passage_id": "passage:foreign:1",
                "selector_type": "MEDIA_SEGMENT_REF",
                "canonical_segment_id": "segment:1",
                "quote_local_start_char": 0,
                "quote_local_end_char": 24,
            },
            representations=(translation,),
        )
        clean = validate_wording_contract_metadata(metadata)
        translated = clean["representations"][0]
        self.assertEqual(translated["wording_type"], "TRANSLATION")
        self.assertEqual(translated["source_language"], "en")
        self.assertEqual(translated["language"], "it")
        self.assertEqual(translated["review_state"], "HUMAN_REVIEWED")
        self.assertFalse(translated["direct_quote_eligible"])
        self.assertEqual(
            translated["representation_role"],
            DERIVED_REPRESENTATION_ROLE,
        )
        self.assertEqual(
            clean["source_provenance"]["canonical_segment_id"],
            "segment:1",
        )

    def test_summary_or_translation_cannot_claim_direct_quote_authority(self):
        for representation in (
            make_summary_wording(
                occurrence_id="statement:1",
                summary="Sintesi editoriale.",
                source_wording_type=WordingType.VERBATIM_ORIGINAL,
                language="it",
                derivation_version="test-v1",
            ),
            make_translation_wording(
                occurrence_id="statement:1",
                source_text="Non aumenteremo le tasse.",
                translated_text="We will not raise taxes.",
                source_wording_type=WordingType.VERBATIM_ORIGINAL,
                source_language="it",
                target_language="en",
                method="HUMAN",
                derivation_version="test-v1",
                human_reviewed=True,
            ),
        ):
            with self.subTest(wording_type=representation.wording_type):
                metadata = wording_contract_metadata(
                    occurrence_id="statement:1",
                    source_text_sha256="a" * 64,
                    normalized_claim="Le tasse non aumenteranno.",
                    language="it",
                    derivation_version="test-v1",
                    representations=(representation,),
                )
                metadata["representations"][0]["direct_quote_eligible"] = True
                with self.assertRaisesRegex(
                    ValueError,
                    "WORDING_DERIVED_DIRECT_QUOTE_FORBIDDEN",
                ):
                    validate_wording_contract_metadata(metadata)

    def test_reported_quote_stays_reported_through_paraphrase_summary_and_translation(self):
        source = make_source_occurrence_wording(
            occurrence_id="statement:reported:1",
            text_sha256="b" * 64,
            language="it",
            derivation_version="test-v1",
            wording_type=WordingType.REPORTED_QUOTE,
        )
        self.assertEqual(source.representation_role, SOURCE_OCCURRENCE_ROLE)
        self.assertFalse(source.direct_quote_eligible)
        summary = make_summary_wording(
            occurrence_id="statement:reported:1",
            summary="Il giornale riassume una dichiarazione attribuita.",
            source_wording_type=WordingType.REPORTED_QUOTE,
            language="it",
            derivation_version="test-v1",
        )
        translation = make_translation_wording(
            occurrence_id="statement:reported:1",
            source_text="Il giornale riporta che non aumenterà le tasse.",
            translated_text="The newspaper reports that taxes will not increase.",
            source_wording_type=WordingType.REPORTED_QUOTE,
            source_language="it",
            target_language="en",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
        )
        metadata = wording_contract_metadata(
            occurrence_id="statement:reported:1",
            source_text_sha256="b" * 64,
            normalized_claim="Una dichiarazione è riportata dal giornale.",
            language="it",
            derivation_version="test-v1",
            source_wording_type=WordingType.REPORTED_QUOTE,
            representations=(summary, translation),
        )
        clean = validate_wording_contract_metadata(metadata)
        self.assertEqual(
            clean["source_occurrence"]["wording_type"],
            "REPORTED_QUOTE",
        )
        self.assertEqual(
            clean["normalized_claim"]["source_wording_type"],
            "REPORTED_QUOTE",
        )
        self.assertEqual(
            clean["representations"][0]["source_wording_type"],
            "REPORTED_QUOTE",
        )
        self.assertEqual(
            clean["representations"][1]["source_wording_type"],
            "REPORTED_QUOTE",
        )
        self.assertEqual(clean["representations"][1]["wording_type"], "TRANSLATION")
        self.assertFalse(clean["source_occurrence"]["direct_quote_eligible"])

    def test_machine_translation_always_requires_review(self):
        result = assess_translation(
            source_text="Non aumenteremo le tasse.",
            translated_text="We will not raise taxes.",
            source_language="it",
            target_language="en",
            method="MACHINE",
        )
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)
        self.assertIn("MACHINE_TRANSLATION_REQUIRES_REVIEW", result.signal_codes)
        self.assertFalse(result.public_quote_eligible)

    def test_human_reviewed_translation_can_clear_without_becoming_quote(self):
        result = assess_translation(
            source_text="Non aumenteremo le tasse.",
            translated_text="We will not raise taxes.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertEqual(result.state, TranslationReviewState.HUMAN_REVIEWED)
        self.assertEqual(result.signal_codes, ())
        self.assertFalse(result.public_quote_eligible)

    def test_changed_number_is_held(self):
        result = assess_translation(
            source_text="Il valore è 13.",
            translated_text="The value is 30.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("NUMBER_CHANGED", result.signal_codes)
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)

    def test_changed_date_is_held(self):
        result = assess_translation(
            source_text="La scadenza è 2026-10-05.",
            translated_text="The deadline is 2026-10-06.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("DATE_CHANGED", result.signal_codes)
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)

    def test_dropped_negation_is_held(self):
        result = assess_translation(
            source_text="Non aumenteremo le tasse.",
            translated_text="We will raise taxes.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("NEGATION_CHANGED", result.signal_codes)
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)

    def test_changed_modality_is_held(self):
        result = assess_translation(
            source_text="Il governo deve intervenire.",
            translated_text="The government may intervene.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("MODALITY_CHANGED", result.signal_codes)
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)

    def test_changed_legal_status_is_held(self):
        result = assess_translation(
            source_text="Mario Rossi è indagato.",
            translated_text="Mario Rossi was convicted.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("LEGAL_STATUS_TERM_CHANGED", result.signal_codes)
        self.assertEqual(result.state, TranslationReviewState.NEEDS_REVIEW)

    def test_changed_proper_name_is_held(self):
        result = assess_translation(
            source_text="Mario Rossi ha parlato.",
            translated_text="Mario Bianchi spoke.",
            source_language="it",
            target_language="en",
            method="HUMAN",
            human_reviewed=True,
        )
        self.assertIn("PROPER_NAME_CHANGED", result.signal_codes)

    def test_public_wording_contract_requires_linked_verbatim_and_paraphrase_channels(self):
        metadata = wording_contract_metadata(
            occurrence_id="statement:1",
            source_text_sha256="a" * 64,
            normalized_claim="Le tasse non aumenteranno.",
            language="it",
            derivation_version="test-v1",
        )
        clean = validate_wording_contract_metadata(metadata)
        self.assertTrue(clean["source_occurrence"]["direct_quote_eligible"])
        self.assertFalse(clean["normalized_claim"]["direct_quote_eligible"])

        tampered = dict(metadata)
        tampered["normalized_claim"] = dict(metadata["normalized_claim"])
        tampered["normalized_claim"]["wording_type"] = "VERBATIM_ORIGINAL"
        with self.assertRaisesRegex(
            ValueError,
            "WORDING_NORMALIZED_CLAIM_MUST_BE_PARAPHRASE",
        ):
            validate_wording_contract_metadata(tampered)


if __name__ == "__main__":
    unittest.main()
