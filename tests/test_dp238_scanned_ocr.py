"""DP-238 scanned OCR candidates: strict replay and no false quote authority.

The isolated command's actual OCR fidelity is evaluated separately against a
frozen, independent image transcription on the native consumer.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from dataclasses import replace
from unittest.mock import patch

from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
from dichiarazioni_pubbliche.document_text_extraction import (
    document_passages_from_capture,
)
from tests.test_dp238_document_extraction import capture, fetched, sha


PDF = b"%PDF-1.4\nmocked scan pixels\n%%EOF"


def _success() -> bytes:
    return json.dumps(
        {
            "status": "SUCCEEDED",
            "engine": "tesseract 5.5.0",
            "pages": [
                {
                    "text": "Il testimone non conferma 42.",
                    "pixels": [500, 600],
                    "words": [
                        [0, 2, 10, 20, 20, 25, 100],
                        [3, 12, 32, 20, 90, 25, 100],
                        [13, 16, 130, 20, 25, 25, 90],
                        [17, 25, 160, 20, 80, 25, 54],
                        [26, 29, 245, 20, 30, 25, 92],
                    ],
                },
                {
                    "text": 'Citazione: "Non sono stato io".',
                    "pixels": [500, 600],
                    "words": [
                        [0, 10, 10, 20, 90, 25, 98],
                        [11, 15, 110, 20, 40, 25, 91],
                    ],
                },
            ],
        },
        ensure_ascii=True,
    ).encode()


class ScannedOCRTests(unittest.TestCase):
    def setUp(self):
        self.parser = ScannedPDFOCRParser()

    def _parse(self, blob: bytes = PDF):
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=_success()),
        ):
            return self.parser.parse(fetched(blob, media="application/pdf"))

    def test_two_pages_and_word_boxes_replay_without_quote_authority(self):
        result = self._parse()
        self.assertEqual(result.status, "SUCCEEDED", result.error_category)
        self.assertEqual(result.metadata["page_count"], 2)
        self.assertEqual(result.metadata["source_sha256"], sha(PDF))
        self.assertTrue(result.parser_version.endswith("/tesseract-5.5.0"))
        self.assertEqual(
            result.metadata["ocr_profile"], "ita+eng/psm3/120dpi/scale2500"
        )
        self.assertEqual(result.metadata["ocr_word_count"], 7)
        self.assertTrue(result.metadata["ocr_applied"])
        self.assertFalse(result.metadata["verbatim_reviewed"])
        self.assertEqual(
            result.metadata["critical_spans"], "HELD_INDEPENDENT_REVIEW_REQUIRED"
        )
        source = replace(
            capture(PDF, media="application/pdf"),
            parser_method=result.parser_method,
            parser_version=result.parser_version,
        )
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=_success()),
        ):
            passages = document_passages_from_capture(
                capture=source,
                fetched=fetched(PDF, media="application/pdf"),
                parsed=result,
                parser=self.parser,
                language="it",
            )
        self.assertEqual(len(passages), 2)
        self.assertEqual([p.metadata["page_number"] for p in passages], [1, 2])
        self.assertEqual([len(p.metadata["ocr_word_boxes"]) for p in passages], [5, 2])
        for passage in passages:
            self.assertEqual(
                passage.private_text,
                result.canonical_text[passage.start_char : passage.end_char],
            )
            self.assertEqual(sha(passage.private_text), passage.text_sha256)
            self.assertEqual(
                passage.metadata["pdf_text_fidelity"], "UNREVIEWED_OCR_EXTRACTION"
            )
            self.assertFalse(passage.metadata["verbatim_reviewed"])
            self.assertEqual(
                passage.metadata["ocr_critical_span_state"],
                "HELD_INDEPENDENT_REVIEW_REQUIRED",
            )
        self.assertEqual(
            passages[0].metadata["ocr_word_boxes"][3]["confidence_percent"], 54
        )

    def test_actual_http_partial_corruption_and_wrong_media_refused_without_worker(
        self,
    ):
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run"
        ) as spawn:
            for item, expected in (
                (
                    replace(fetched(PDF, media="application/pdf"), status_code=206),
                    "DOCUMENT_SOURCE_STATUS_INVALID",
                ),
                (fetched(PDF, media="text/plain"), "DOCUMENT_FORMAT_UNSUPPORTED"),
                (fetched(b"bad", media="application/pdf"), "DOCUMENT_PDF_CORRUPT"),
            ):
                with self.subTest(expected=expected):
                    result = self.parser.parse(item)
                    self.assertEqual(result.status, "FAILED")
                    self.assertEqual(result.error_category, expected)
            spawn.assert_not_called()

    def test_worker_cannot_invent_coordinates_or_cross_page_text(self):
        variants = []
        for alteration in (
            [-1, 2, 5, 5, 5, 5, 70],
            [0, 200, 5, 5, 5, 5, 70],
            [0, 2, 500, 5, 5, 5, 70],
            [0, 2, 5, 5, 5, 5, 101],
        ):
            data = json.loads(_success())
            data["pages"][0]["words"][0] = alteration
            variants.append(data)
        data = json.loads(_success())
        data["pages"][0]["text"] += "\fFORGED PAGE"
        variants.append(data)
        data = json.loads(_success())
        data["pages"][0]["pixels"] = [True, 600]
        variants.append(data)
        for payload in variants:
            with self.subTest(payload=str(payload)[:90]):
                with patch(
                    "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout=json.dumps(payload).encode()
                    ),
                ):
                    result = self.parser.parse(fetched(PDF, media="application/pdf"))
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error_category, "DOCUMENT_OCR_WORKER_INVALID")

    def test_revoked_rights_and_changed_source_cannot_reuse_ocr_derivation(self):
        result = self._parse()
        source = replace(
            capture(PDF, media="application/pdf"),
            parser_method=result.parser_method,
            parser_version=result.parser_version,
        )
        for change in (
            {"capture": replace(source, rights_status="REVOKED")},
            {"fetched": fetched(PDF + b"tampered", media="application/pdf")},
            {"parsed": replace(result, canonical_text="forged")},
        ):
            with self.subTest(changed=list(change)):
                params = {
                    "capture": source,
                    "fetched": fetched(PDF, media="application/pdf"),
                    "parsed": result,
                    "parser": self.parser,
                }
                params.update(change)
                with patch(
                    "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, stdout=_success()),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"
                    ):
                        document_passages_from_capture(**params)

    def test_revoked_rights_and_mismatched_source_do_not_start_ocr_worker(self):
        # A rejected source must never reach the native PDF/OCR subprocess.
        result = self._parse()
        source = replace(
            capture(PDF, media="application/pdf"),
            parser_method=result.parser_method,
            parser_version=result.parser_version,
        )
        for denied in (
            replace(source, rights_status="REVOKED"),
            replace(source, content_sha256=sha(b"different PDF")),
            replace(source, final_url="https://source.example/other"),
            replace(source, hold_status="LEGAL_HOLD"),
            replace(source, hold_status="RIGHTS_HOLD"),
            replace(source, hold_status="PRIVACY_HOLD"),
        ):
            with self.subTest(denied=denied):
                with patch(
                    "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run"
                ) as spawned:
                    with self.assertRaisesRegex(
                        ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"
                    ):
                        document_passages_from_capture(
                            capture=denied,
                            fetched=fetched(PDF, media="application/pdf"),
                            parsed=result,
                            parser=self.parser,
                        )
                    spawned.assert_not_called()

    def test_missing_engine_is_an_explicit_hold(self):
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess(
                [],
                0,
                stdout=b'{"status":"FAILED","code":"DOCUMENT_OCR_BACKEND_UNAVAILABLE"}',
            ),
        ):
            result = self.parser.parse(fetched(PDF, media="application/pdf"))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_category, "DOCUMENT_OCR_BACKEND_UNAVAILABLE")
        self.assertFalse(result.spans)


if __name__ == "__main__":
    unittest.main()
