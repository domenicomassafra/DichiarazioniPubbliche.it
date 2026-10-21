"""Regression: Tesseract TSV contains literal quotation marks, not CSV quoting.

Real independent-gold BHL page 8992356 exposed a quote-prefixed word which
caused the default CSV parser to consume the following TSV lines as one token.
"""

import subprocess
import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.document_scanned_ocr import (
    OCR_VERSION,
    _extract_ocr_pages,
)


PDF = b"%PDF-1.4\nmocked scan pixels\n%%EOF"
TSV_COLUMNS = (
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
)


class OCRTSVQuotingTests(unittest.TestCase):
    def test_unbalanced_and_balanced_quote_words_remain_literal(self):
        for first_word in ('"Non', '"Non"'):
            with self.subTest(first_word=first_word):
                words = (first_word, "conferma", "42")
                lines = ["\t".join(TSV_COLUMNS)]
                for number, word in enumerate(words, 1):
                    fields = (5, 1, 1, 1, 1, number, number * 25, 10, 20, 10, 90.0, word)
                    lines.append("\t".join(map(str, fields)))
                tsv = ("\n".join(lines) + "\n").encode()
                png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
                       + (400).to_bytes(4, "big") + (600).to_bytes(4, "big"))

                def run_backend(args, **_kwargs):
                    if args[0].endswith("pdfinfo"):
                        return b"Encrypted: no\nJavaScript: no\nForm: none\nSuspects: no\nPages: 1\n"
                    if args[0].endswith("pdftoppm"):
                        return png
                    self.assertTrue(args[0].endswith("tesseract"))
                    return tsv

                with (
                    patch(
                        "dichiarazioni_pubbliche.document_scanned_ocr.shutil.which",
                        side_effect=lambda name: f"/usr/bin/{name}",
                    ),
                    patch(
                        "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
                        return_value=subprocess.CompletedProcess(
                            [], 0, stdout=b"tesseract 5.5.0\n"
                        ),
                    ),
                    patch(
                        "dichiarazioni_pubbliche.document_scanned_ocr._run",
                        side_effect=run_backend,
                    ),
                ):
                    result = _extract_ocr_pages(PDF)

                self.assertEqual(result["pages"][0]["text"], f"{first_word} conferma 42")
                self.assertEqual(len(result["pages"][0]["words"]), 3)
                self.assertEqual(result["pages"][0]["words"][0][:2], [0, len(first_word)])
                self.assertTrue(OCR_VERSION.endswith("private-ocr-candidate-v2"))


if __name__ == "__main__":
    unittest.main()
