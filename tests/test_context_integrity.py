import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.context_integrity import (  # noqa: E402
    assess_context_integrity,
    assess_structured_context_integrity,
    curated_context_approval,
    verify_structured_context_integrity_metadata,
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

    def test_discontinuous_excerpt_is_explicit_and_never_auto_clears(self):
        text = "Prima frase completa. Contesto necessario. Seconda frase completa."
        first = "Prima frase completa."
        second = "Seconda frase completa."
        result = assess_structured_context_integrity(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            spans=(
                (text.index(first), text.index(first) + len(first)),
                (text.index(second), text.index(second) + len(second)),
            ),
        )
        self.assertFalse(result.clear)
        self.assertEqual(result.omission_count, 1)
        self.assertIn("DISCONTINUOUS_EXCERPT_REQUIRES_REVIEW", result.signal_codes)
        self.assertNotIn(first, repr(result.to_metadata()))
        self.assertNotIn(second, repr(result.to_metadata()))

    def test_cross_talk_and_montage_boundaries_cannot_inherit_neighbor_context(self):
        text = "Speaker A: dato uno. Speaker B: dato due."
        first = "dato uno."
        second = "dato due."
        result = assess_structured_context_integrity(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            spans=(
                (text.index(first), text.index(first) + len(first)),
                (text.index(second), text.index(second) + len(second)),
            ),
            speaker_refs=("person:a", "person:b"),
            source_part_refs=("clip:live", "clip:archive"),
        )
        self.assertEqual(result.state, "NEEDS_CONTEXT_REVIEW")
        self.assertIn("CROSS_TALK_OR_SPEAKER_BOUNDARY", result.signal_codes)
        self.assertIn("MONTAGE_OR_SOURCE_BOUNDARY", result.signal_codes)

    def test_structured_span_order_fails_closed(self):
        text = "abc def ghi"
        with self.assertRaisesRegex(ValueError, "SPAN_ORDER_INVALID"):
            assess_structured_context_integrity(
                source_text=text,
                source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                spans=((8, 11), (0, 3)),
            )

    def test_structured_optional_refs_do_not_turn_none_into_literal_text(self):
        text = "uno ... due"
        result = assess_structured_context_integrity(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            spans=((0, 3), (8, 11)),
            speaker_refs=(None, "person:b"),
            source_part_refs=(None, "clip:b"),
        )
        self.assertIsNone(result.spans[0].speaker_ref)
        self.assertIsNone(result.spans[0].source_part_ref)

    def test_structured_metadata_binding_rejects_stale_span_or_hash(self):
        text = "uno ... due"
        metadata = assess_structured_context_integrity(
            source_text=text,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            spans=((0, 3), (8, 11)),
            speaker_refs=("person:a", "person:a"),
            source_part_refs=("part:a", "part:a"),
        ).to_metadata()
        verified = verify_structured_context_integrity_metadata(metadata)
        self.assertEqual(verified.binding_sha256, metadata["binding_sha256"])

        for field, value in (("start_char", 9), ("text_sha256", "f" * 64)):
            with self.subTest(field=field):
                tampered = dict(metadata)
                tampered["spans"] = [dict(span) for span in metadata["spans"]]
                tampered["spans"][1][field] = value
                with self.assertRaisesRegex(ValueError, "CONTEXT_STRUCTURED_BINDING_MISMATCH"):
                    verify_structured_context_integrity_metadata(tampered)

        tampered_binding = dict(metadata)
        tampered_binding["binding_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "CONTEXT_STRUCTURED_BINDING_MISMATCH"):
            verify_structured_context_integrity_metadata(tampered_binding)


if __name__ == "__main__":
    unittest.main()
