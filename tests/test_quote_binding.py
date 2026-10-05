import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.quote_binding import (  # noqa: E402
    QUOTE_BINDING_VERSION,
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


if __name__ == "__main__":
    unittest.main()
