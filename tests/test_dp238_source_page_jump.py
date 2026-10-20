"""A private OCR/PDF Passage opens its original page only after exact replay."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.document_pdf_extraction import BornDigitalPDFTextParser
from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
from dichiarazioni_pubbliche.document_text_extraction import (
    document_passages_from_capture,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes
from dichiarazioni_pubbliche.studio_exact_source_jump import (
    read_studio_exact_source_jump,
)

from tests.test_dp237_studio_exact_source_jump import Snapshot
from tests.test_dp238_document_extraction import capture, fetched, sha
from tests.test_dp238_scanned_ocr import PDF, _success


class OCRSourcePageJumpTests(unittest.TestCase):
    def setUp(self):
        private = tempfile.TemporaryDirectory()
        self.addCleanup(private.cleanup)
        self.body_store = CaptureBodyStore(Path(private.name))
        stored = self.body_store.write(
            capture_id="capture:ocr", body=PDF, content_sha256=sha(PDF),
        )
        self.parser = ScannedPDFOCRParser()
        self.saved = fetched(PDF, media="application/pdf")
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=_success()),
        ):
            self.parsed = self.parser.parse(self.saved)
        self.assertEqual(self.parsed.status, "SUCCEEDED")
        self.capture = replace(
            capture(PDF, media="application/pdf", ident="capture:ocr"),
            body_ref=stored.body_ref,
            parser_method=self.parsed.parser_method,
            parser_version=self.parsed.parser_version,
            metadata={
                "parse_status": "SUCCEEDED", "source_metadata": self.parsed.metadata,
            },
        )
        with patch.object(self.parser, "parse", return_value=self.parsed):
            self.passage = document_passages_from_capture(
                capture=self.capture, fetched=self.saved, parsed=self.parsed,
                parser=self.parser, language="it",
            )[1]
        self.record = {
            "source_id": "source:ocr", "content_rights": "CLEARED",
            "collection_status": "ACTIVE", "rights_leaf_count": 1,
            "rights_ready": True, "capture": asdict(self.capture),
            "passage": asdict(self.passage),
            "families": [{"id": "family:ocr", "status": "APPROVED",
                          "root_content_id": self.capture.content_id}],
            "edges": [],
        }
        self.reader = Snapshot(self.record)

    def jump(self, live_body: bytes = PDF):
        def fetch(_url, **_kwargs):
            return FetchedBytes(
                body=live_body, final_url=self.capture.final_url,
                status_code=200, media_type="application/pdf",
                charset="utf-8", content_length=len(live_body),
            )

        parser_type = (ScannedPDFOCRParser if self.capture.parser_method
                       == ScannedPDFOCRParser.parser_method else BornDigitalPDFTextParser)
        with patch.object(parser_type, "parse", return_value=self.parsed):
            return read_studio_exact_source_jump(
                self.reader, self.body_store, collection_id="collection:ocr",
                content_id=self.capture.content_id, capture_id=self.capture.id,
                passage_id=self.passage.id, quote_text="Non sono stato io",
                fetch=fetch,
            )

    def test_ocr_passage_navigates_original_pdf_page_without_quote_authority(self):
        result = self.jump()
        self.assertEqual(result["status"], "READY_PAGE", result)
        self.assertEqual(result["url"], self.capture.final_url + "#page=2")
        self.assertEqual(result["precision"], "PAGE")
        self.assertTrue(result["private_only"])
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["rights_clearance"])
        self.assertNotIn("Non sono stato io", json.dumps(result))
        self.assertIn("PARSE_OCR", self.reader.calls[0][0])
        self.assertIn("capture.parser_method='SCANNED_PDF_OCR_CANDIDATE'", self.reader.calls[0][0])

    def test_changed_live_pdf_and_unverified_page_map_are_held(self):
        self.assertEqual(self.jump(PDF + b"\n")["status"], "UNAVAILABLE")
        source = self.record["capture"]["metadata"]["source_metadata"]
        pages = source["page_selectors"]
        source["page_selectors"] = [{**p, "page_number": 1} for p in pages]
        result = self.jump()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "PDF_TEXT_PAGE_NOT_VERIFIED")
        self.assertIsNone(result["url"])

    def test_page_map_json_type_drift_remains_held(self):
        source = self.record["capture"]["metadata"]["source_metadata"]
        source["page_selectors"] = [dict(page) for page in source["page_selectors"]]
        # In Python True == 1, but a JSON boolean is not an integer page ID.
        source["page_selectors"][0]["page_number"] = True
        result = self.jump()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "PDF_TEXT_PAGE_NOT_VERIFIED")

    def test_wrong_role_or_rights_cannot_mint_pdf_source_navigation(self):
        for field, changed in (
            ("rights_ready", False),
            ("content_rights", "UNKNOWN"),
        ):
            original = self.record[field]
            self.record[field] = changed
            with self.subTest(field=field):
                self.assertIsNone(self.jump()["url"])
            self.record[field] = original

    @unittest.skipUnless(
        importlib.util.find_spec("pypdf") and importlib.util.find_spec("reportlab"),
        "Optional native-PDF donor dependencies unavailable",
    )
    def test_actual_born_digital_pdf_worker_navigates_page_two(self):
        from tests.test_dp238_born_digital_pdf import _pdf

        original = _pdf(("The first page is exact.", "Non sono stato io."))
        parser = BornDigitalPDFTextParser()
        observed = fetched(original, media="application/pdf")
        parsed = parser.parse(observed)
        self.assertEqual(parsed.status, "SUCCEEDED", parsed.error_category)
        saved = self.body_store.write(
            capture_id="capture:pdf-native", body=original,
            content_sha256=sha(original),
        )
        self.capture = replace(
            capture(original, media="application/pdf", ident="capture:pdf-native"),
            body_ref=saved.body_ref, parser_method=parser.parser_method,
            parser_version=parsed.parser_version,
            metadata={"parse_status": "SUCCEEDED", "source_metadata": parsed.metadata},
        )
        self.parsed = parsed
        passages = document_passages_from_capture(
            capture=self.capture, fetched=observed, parsed=parsed, parser=parser,
        )
        self.assertEqual(len(passages), 2)
        self.passage = passages[1]
        self.record["capture"] = asdict(self.capture)
        self.record["passage"] = asdict(self.passage)
        self.assertEqual(self.jump(original)["url"], self.capture.final_url + "#page=2")


if __name__ == "__main__":
    unittest.main()
