import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.context_integrity import (  # noqa: E402
    assess_context_integrity,
    curated_context_approval,
)


def assess(text, start, end, **kwargs):
    return assess_context_integrity(
        source_text=text,
        source_sha256=hashlib.sha256(text.encode()).hexdigest(),
        quote_start=start,
        quote_end=end,
        **kwargs,
    )


class ContextIntegrityTests(unittest.TestCase):
    def test_complete_autonomous_sentence_is_clear(self):
        text = "Il dato ufficiale è 10."
        result = assess(text, 0, len(text))
        self.assertTrue(result.clear)
        self.assertEqual(result.signal_codes, ())

    def test_omitted_negation_near_boundary_is_held(self):
        text = "Non aumenteremo le tasse."
        quote = "aumenteremo le tasse."
        start = text.index(quote)
        result = assess(text, start, start + len(quote))
        self.assertFalse(result.clear)
        self.assertIn("NEGATION_NEAR_BOUNDARY_OMITTED", result.signal_codes)

    def test_conditional_statement_is_held_for_context_review(self):
        text = "Se l'economia rallenta, potremmo intervenire."
        result = assess(text, 0, len(text))
        self.assertIn("CONDITIONAL_OR_HYPOTHETICAL", result.signal_codes)
        self.assertFalse(result.clear)

    def test_yes_no_answer_requires_question_context(self):
        text = "Aumenterete le tasse? No."
        quote = "No."
        start = text.index(quote)
        result = assess(text, start, start + len(quote))
        self.assertIn("ANSWER_REQUIRES_QUESTION_CONTEXT", result.signal_codes)
        self.assertFalse(result.clear)

    def test_immediate_qualification_outside_quote_is_held(self):
        text = "Il piano funziona, ma solo nel breve periodo."
        quote = "Il piano funziona"
        result = assess(text, 0, len(quote))
        self.assertIn("IMMEDIATE_QUALIFICATION_OMITTED", result.signal_codes)

    def test_non_direct_speech_is_context_dependent(self):
        text = "Ha detto che il piano funziona."
        result = assess(
            text,
            0,
            len(text),
            speech_mode="REPORTED_SPEECH",
        )
        self.assertIn("NON_DIRECT_SPEECH_MODE", result.signal_codes)

    def test_metadata_contains_hashes_and_offsets_not_raw_context(self):
        text = "Il dato ufficiale è 10."
        metadata = assess(text, 0, len(text)).to_metadata()
        encoded = repr(metadata)
        self.assertNotIn(text, encoded)
        self.assertIn("context_sha256", metadata)
        self.assertEqual(metadata["quote_start"], 0)
        self.assertEqual(metadata["quote_end"], len(text))

    def test_source_hash_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, "CONTEXT_SOURCE_HASH_MISMATCH"):
            assess_context_integrity(
                source_text="testo",
                source_sha256="a" * 64,
                quote_start=0,
                quote_end=5,
            )

    def test_curated_review_is_explicit_and_versioned(self):
        metadata = curated_context_approval(
            source_sha256="a" * 64,
            quote_sha256="b" * 64,
            quote_start=10,
            quote_end=20,
        )
        self.assertEqual(metadata["state"], "APPROVED_CURATED")
        self.assertEqual(metadata["review_method"], "CURATED_SOURCE_REVIEW")


if __name__ == "__main__":
    unittest.main()
