"""Real generated PDF binary -> bounded private non-verbatim page passages."""

from __future__ import annotations

import io
import importlib.util
import unittest
from dataclasses import replace
from unittest.mock import patch

from dichiarazioni_pubbliche.document_pdf_extraction import BornDigitalPDFTextParser
from dichiarazioni_pubbliche.document_text_extraction import (
    document_passages_from_capture,
)
from tests.test_dp238_document_extraction import capture, fetched, sha


def _pdf(pages: tuple[str, ...], *, image: bool = False) -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(595, 842), pageCompression=1)
    for page in pages:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(70, 740, page)
        if image:
            # A true raster image XObject disqualifies born-digital-only paths.
            from reportlab.lib.utils import ImageReader
            from PIL import Image

            sample = io.BytesIO()
            Image.new("RGB", (2, 2), (255, 0, 0)).save(sample, format="PNG")
            sample.seek(0)
            pdf.drawImage(ImageReader(sample), 80, 600, 20, 20)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@unittest.skipUnless(
    all(
        importlib.util.find_spec(name) is not None
        for name in ("pypdf", "reportlab", "PIL")
    ),
    "Opt-in document-pdf-test backend not installed",
)
class BornDigitalPdfTests(unittest.TestCase):
    def setUp(self):
        self.parser = BornDigitalPDFTextParser()

    def test_real_two_page_pdf_roundtrip_and_explicit_unreviewed_fidelity(self):
        body = _pdf(
            ("The witness did not confirm 42.", "Party allegation: no guilty verdict.")
        )
        got = self.parser.parse(fetched(body, media="application/pdf"))
        self.assertEqual(got.status, "SUCCEEDED", got.error_category)
        self.assertEqual(got.metadata["page_count"], 2)
        self.assertIn("not confirm 42", got.canonical_text)
        self.assertIn("no guilty verdict", got.canonical_text)
        self.assertEqual(got.metadata["source_sha256"], sha(body))
        self.assertFalse(got.metadata["ocr_applied"])
        self.assertFalse(got.metadata["verbatim_reviewed"])
        self.assertEqual(got.metadata["reading_order_assurance"], "UNREVIEWED")
        source = replace(
            capture(body, media="application/pdf"),
            parser_method=got.parser_method,
            parser_version=got.parser_version,
        )
        spans = document_passages_from_capture(
            capture=source,
            fetched=fetched(body, media="application/pdf"),
            parsed=got,
            parser=self.parser,
            language="en",
        )
        self.assertEqual(len(spans), 2)
        self.assertTrue(all(not item.metadata["verbatim_reviewed"] for item in spans))
        self.assertEqual(tuple(p.metadata["page_number"] for p in spans), (1, 2))
        for p in spans:
            self.assertEqual(
                got.canonical_text[p.start_char : p.end_char], p.private_text
            )
            self.assertEqual(sha(p.private_text), p.text_sha256)
        self.assertEqual(
            spans,
            document_passages_from_capture(
                capture=source,
                fetched=fetched(body, media="application/pdf"),
                parsed=got,
                parser=self.parser,
                language="en",
            ),
        )

    def test_pdf_image_mixed_with_text_requires_ocr_or_independent_review(self):
        body = _pdf(("This is text beside scan.",), image=True)
        result = self.parser.parse(fetched(body, media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_PDF_OCR_REQUIRED")

    def test_blank_page_no_hidden_success(self):
        body = _pdf(("First page", ""))
        result = self.parser.parse(fetched(body, media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_INCOMPLETE_PAGE")

    def test_encrypted_document_needs_external_authority(self):
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        writer.append_pages_from_reader(PdfReader(io.BytesIO(_pdf(("Private page",)))))
        writer.encrypt("test_password")
        buffer = io.BytesIO()
        writer.write(buffer)
        result = self.parser.parse(fetched(buffer.getvalue(), media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_PDF_UNSUPPORTED")

    def test_annotations_and_document_actions_are_not_silent_text_authority(self):
        buffer = io.BytesIO()
        from reportlab.pdfgen import canvas

        pdf = canvas.Canvas(buffer)
        pdf.drawString(60, 740, "Visible text")
        pdf.linkURL("https://example.invalid/side-effect", (60, 700, 160, 760))
        pdf.save()
        result = self.parser.parse(fetched(buffer.getvalue(), media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_PDF_UNSUPPORTED")

    def test_page_count_limit_precedes_text_extraction(self):
        body = _pdf(tuple(f"Page {index}" for index in range(65)))
        result = self.parser.parse(fetched(body, media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_PDF_TOO_MANY_PAGES")

    def test_limits_malformed_and_backend_outage_hold_without_text(self):
        for blob, code in (
            (b"%PDF-1.7\n%%EOF", "DOCUMENT_PDF_CORRUPT"),
            (b"broken", "DOCUMENT_PDF_CORRUPT"),
            (b"%PDF-1.7" + b"A" * 1_048_576 + b"%%EOF", "DOCUMENT_BODY_OVERSIZE"),
        ):
            with self.subTest(code=code):
                result = self.parser.parse(fetched(blob, media="application/pdf"))
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error_category, code)
        real = _pdf(("One valid page",))
        with patch(
            "dichiarazioni_pubbliche.document_pdf_extraction.subprocess.run",
            side_effect=TimeoutError,
        ):
            result = self.parser.parse(fetched(real, media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_PDF_WORKER_UNAVAILABLE")

    def test_legacy_pdf_path_held_and_pdf_reader_rejects_spoofed_source(self):
        from dichiarazioni_pubbliche.document_text_extraction import DocumentTextParser

        body = _pdf(("Do not invert the negative.",))
        self.assertEqual(
            DocumentTextParser().parse(fetched(body, media="application/pdf")).status,
            "FAILED",
        )
        parsed = self.parser.parse(fetched(body, media="application/pdf"))
        source = replace(
            capture(body, media="application/pdf"),
            parser_method=parsed.parser_method,
            parser_version=parsed.parser_version,
        )
        altered = _pdf(("Do invert the negative.",))
        for kwargs in (
            {"fetched": fetched(altered, media="application/pdf")},
            {"capture": replace(source, rights_status="REVOKED")},
            {"parsed": replace(parsed, canonical_text="False wording")},
        ):
            with (
                self.subTest(kwargs=list(kwargs)),
                self.assertRaisesRegex(
                    ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"
                ),
            ):
                params = dict(
                    capture=source,
                    fetched=fetched(body, media="application/pdf"),
                    parsed=parsed,
                    parser=self.parser,
                )
                document_passages_from_capture(**(params | kwargs))


if __name__ == "__main__":
    unittest.main()
