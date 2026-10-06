import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.quote_binding import (  # noqa: E402
    EXPLICIT_OMISSION_MARKER,
    QUOTE_BINDING_VERSION,
    verify_discontinuous_written_quote_binding,
    verify_written_quote_binding,
)


class QuoteBindingTests(unittest.TestCase):
    def verify(self, text="Non aumenteremo le tasse.", **overrides):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        values = {
            "statement_text_sha256": digest,
            "passage_text_sha256": digest,
            "private_text": text,
            "selector_type": "TEXT_POSITION",
            "start_char": 20,
            "end_char": 20 + len(text),
            "source_sha256": "a" * 64,
        }
        values.update(overrides)
        return verify_written_quote_binding(**values)

    def test_exact_source_span_verifies(self):
        result = self.verify()
        self.assertTrue(result.verified)
        self.assertEqual(result.reason_code, "EXACT_SOURCE_SPAN_VERIFIED")
        self.assertEqual(result.version, QUOTE_BINDING_VERSION)

    def test_cleaned_or_invented_statement_hash_is_blocked(self):
        result = self.verify(
            statement_text_sha256=hashlib.sha256(
                b"Aumenteremo le tasse."
            ).hexdigest()
        )
        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "STATEMENT_NOT_EXACT_PASSAGE")

    def test_passage_body_tamper_is_blocked(self):
        original = "Non aumenteremo le tasse."
        digest = hashlib.sha256(original.encode()).hexdigest()
        changed = "Aumenteremo le tasse."
        result = self.verify(
            statement_text_sha256=digest,
            passage_text_sha256=digest,
            private_text=changed,
            end_char=20 + len(changed),
        )
        self.assertEqual(result.reason_code, "PASSAGE_TEXT_HASH_MISMATCH")

    def test_off_by_one_span_is_blocked(self):
        result = self.verify(end_char=20 + len("Non aumenteremo le tasse.") + 1)
        self.assertEqual(result.reason_code, "QUOTE_POSITION_LENGTH_MISMATCH")

    def test_hash_only_or_page_selector_is_not_enough_for_direct_quote(self):
        result = self.verify(
            selector_type="PAGE_RANGE",
            start_char=None,
            end_char=None,
        )
        self.assertEqual(result.reason_code, "QUOTE_SELECTOR_NOT_EXACT")

    def test_source_version_hash_is_mandatory(self):
        with self.assertRaisesRegex(ValueError, "QUOTE_BINDING_SOURCE_SHA256_INVALID"):
            self.verify(source_sha256="")

    def test_discontinuous_quote_reconstructs_only_with_explicit_omission(self):
        source = "Il piano costa dieci milioni. Nel 2027 sarà rivisto. La copertura è già stanziata."
        first = "Il piano costa dieci milioni."
        second = "La copertura è già stanziata."
        spans = (
            (source.index(first), source.index(first) + len(first)),
            (source.index(second), source.index(second) + len(second)),
        )
        rendered = first + EXPLICIT_OMISSION_MARKER + second
        result = verify_discontinuous_written_quote_binding(
            statement_text_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            spans=spans,
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.omission_count, 1)
        self.assertEqual(result.reason_code, "EXPLICIT_DISCONTINUOUS_SOURCE_SPANS_VERIFIED")
        self.assertNotIn(first, repr(result))
        self.assertNotIn(second, repr(result))

    def test_invisible_concatenation_of_non_adjacent_spans_is_refused(self):
        source = "Prima clausola. Contesto omesso. Seconda clausola."
        first = "Prima clausola."
        second = "Seconda clausola."
        spans = (
            (source.index(first), source.index(first) + len(first)),
            (source.index(second), source.index(second) + len(second)),
        )
        invisible = first + second
        result = verify_discontinuous_written_quote_binding(
            statement_text_sha256=hashlib.sha256(invisible.encode()).hexdigest(),
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            spans=spans,
        )
        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "DISCONTINUOUS_QUOTE_RENDER_MISMATCH")

    def test_discontinuous_spans_must_be_source_ordered_and_non_adjacent(self):
        source = "uno due tre"
        digest = hashlib.sha256(source.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "SPAN_ORDER_INVALID"):
            verify_discontinuous_written_quote_binding(
                statement_text_sha256=digest,
                source_text=source,
                source_sha256=digest,
                spans=((8, 11), (0, 3)),
            )
        with self.assertRaisesRegex(ValueError, "ADJACENT_SPANS_REFUSED"):
            verify_discontinuous_written_quote_binding(
                statement_text_sha256=digest,
                source_text=source,
                source_sha256=digest,
                spans=((0, 3), (3, 7)),
            )


if __name__ == "__main__":
    unittest.main()
