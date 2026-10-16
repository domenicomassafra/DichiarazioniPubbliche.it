"""DP-238 scanned OCR candidates: strict replay and no false quote authority.

The isolated command's actual OCR fidelity is evaluated separately against a
frozen, independent image transcription on the native consumer.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
from dichiarazioni_pubbliche.capture_pipeline import (
    MAX_PASSAGE_CHARS,
    CaptureBodyStore,
    CapturePipelineError,
    capture_content,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked
from dichiarazioni_pubbliche.document_text_extraction import (
    document_passages_from_capture,
)
from tests.test_dp238_document_extraction import capture, fetched, sha
from tests.test_capture_pipeline import FakeCaptureStore


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

    def test_long_ocr_word_straddling_passage_boundary_keeps_page_coordinates(self):
        # The native page can be longer than MAX_PASSAGE_CHARS. A word may cross
        # a character-based private Passage split; its pixel box must not vanish.
        text = "x" * (MAX_PASSAGE_CHARS - 2) + "nonconfermo" + " fine"
        start = MAX_PASSAGE_CHARS - 2
        word = [start, start + len("nonconfermo"), 5, 8, 110, 20, 51]
        payload = json.dumps({
            "status": "SUCCEEDED", "engine": "tesseract 5.5.0",
            "pages": [{"text": text, "pixels": [500, 600], "words": [word]}],
        }).encode()
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=payload),
        ):
            parsed = self.parser.parse(fetched(PDF, media="application/pdf"))
        self.assertEqual(parsed.status, "SUCCEEDED")
        source = replace(
            capture(PDF, media="application/pdf"),
            parser_method=parsed.parser_method,
            parser_version=parsed.parser_version,
        )
        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=payload),
        ):
            passages = document_passages_from_capture(
                capture=source,
                fetched=fetched(PDF, media="application/pdf"),
                parsed=parsed,
                parser=self.parser,
            )
        self.assertEqual(len(passages), 2)
        for passage in passages:
            self.assertEqual(len(passage.metadata["ocr_word_boxes"]), 1)
            box = passage.metadata["ocr_word_boxes"][0]
            self.assertEqual(box["page_number"], 1)
            self.assertEqual((box["start_char"], box["end_char"]), (start, word[1]))
            self.assertTrue(box["crosses_passage_boundary"])

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


class CanonicalPersistedScannedOCRTests(unittest.TestCase):
    """Exercise the canonical capture_content writer, not just the DP238 helper."""

    class CompletePrivateCaptureStore(FakeCaptureStore):
        """Fake store with the same safety columns as PostgreSQL readback."""

        def insert_private_document_passages(self, *, capture, passages, use_fingerprint):
            # In-memory model of the guarded batch; PostgreSQL implements the
            # actual row-locked, one-statement transaction separately.
            current = self.find_capture(capture.content_id, capture.content_sha256)
            if (current is None or current["status"] != "CAPTURED"
                or current["hold_status"] != "NONE"
                or current["rights_status"] != "CLEARED"
                or current["body_purged_at"] is not None):
                raise CapturePipelineError("DOCUMENT_CAPTURE_HELD")
            return tuple(self.insert_passage(p) for p in passages)

        def find_capture(self, content_id, content_sha256):
            row = super().find_capture(content_id, content_sha256)
            if row is not None:
                persisted = self.captures[(content_id, content_sha256)]["record"]
                row.update(
                    rights_status=persisted.rights_status,
                    body_purged_at=persisted.body_purged_at,
                )
            return row

        def upsert_capture(self, record):
            row = super().upsert_capture(record)
            persisted = self.captures[(record.content_id, record.content_sha256)]["record"]
            row.update(
                rights_status=persisted.rights_status,
                body_purged_at=persisted.body_purged_at,
                parser_method=persisted.parser_method,
                parser_version=persisted.parser_version,
                final_url=persisted.final_url,
                media_type=persisted.media_type,
                metadata=persisted.metadata,
            )
            return row

    class ApprovedOwnerSourceGuard:
        def __init__(self):
            self.operations = []

        def bind_capture(self, *, content_id, url):
            assert content_id == "content:owner-product-ocr"
            assert url == "https://source.example/document"

        def bind_fetched(self, *, final_url):
            assert final_url == "https://source.example/document"

        def require(self, operation, **kwargs):
            self.operations.append(operation)
            assert operation in {"FETCH", "STORE_BODY", "PARSE_OCR"}
            return SimpleNamespace(decision_fingerprint="a" * 64)

    def _capture(self, store, body_store, *, rights="CLEARED", guard=None, on_replay=None):
        src = self.ApprovedOwnerSourceGuard() if guard is None else guard
        calls = 0

        def worker(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2 and on_replay is not None:
                on_replay()
            return subprocess.CompletedProcess([], 0, stdout=_success())

        with patch(
            "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
            side_effect=worker,
        ) as ocr:
            self.last_ocr_mock = ocr
            receipt = capture_content(
                content_id="content:owner-product-ocr",
                url="https://source.example/document",
                store=store,
                body_store=body_store,
                observed_at="2026-10-16T12:00:00+00:00",
                fetcher=lambda url, **kwargs: fetched(PDF, media="application/pdf"),
                parser=ScannedPDFOCRParser(),
                rights_status=rights,
                rights_guard=lambda: None,
                source_use_guard=src,
                enrichment_policy=None,
            )
        return receipt, src, ocr.call_count

    def test_persisted_private_passages_keep_page_boxes_and_critical_hold_on_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.CompletePrivateCaptureStore()
            body_store = CaptureBodyStore(Path(tmp))
            first, guard, count = self._capture(store, body_store)
            self.assertEqual(count, 2)  # extraction and immutable source replay
            self.assertEqual(first.parse_status, "SUCCEEDED")
            self.assertIn("PARSE_OCR", guard.operations)
            persisted = store.list_passages(first.selected_capture_id)
            self.assertEqual(len(persisted), 2)
            for page, passage in enumerate(sorted(persisted, key=lambda p: p.start_char), 1):
                self.assertEqual(passage.metadata["page_number"], page)
                self.assertEqual(passage.metadata["source_sha256"], sha(PDF))
                self.assertEqual(passage.metadata["pdf_text_fidelity"], "UNREVIEWED_OCR_EXTRACTION")
                self.assertFalse(passage.metadata["verbatim_reviewed"])
                self.assertEqual(passage.metadata["ocr_critical_span_state"], "HELD_INDEPENDENT_REVIEW_REQUIRED")
                self.assertTrue(passage.metadata["ocr_word_boxes"])
            self.assertEqual(len(persisted[0].metadata["ocr_word_boxes"]), 5)
            second, _, count2 = self._capture(store, body_store)
            self.assertEqual(count2, 2)
            self.assertEqual(first.passage_ids, second.passage_ids)
            self.assertEqual(second.capture_state, "EXISTING")
            self.assertEqual(set(second.passage_states), {"EXISTING"})

    def test_rights_unknown_and_existing_held_capture_refuse_ocr_and_insert(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.CompletePrivateCaptureStore()
            body_store = CaptureBodyStore(Path(tmp))
            with self.assertRaisesRegex(CapturePipelineError, "DOCUMENT_SOURCE_RIGHTS_NOT_CLEARED"):
                capture_content(
                    content_id="content:owner-product-ocr",
                    url="https://source.example/document",
                    store=store,
                    body_store=body_store,
                    parser=ScannedPDFOCRParser(),
                    rights_status="CLEARED",
                    source_use_guard=None,
                    fetcher=lambda *args, **kwargs: self.fail("must hold before fetch"),
                )
            with self.assertRaisesRegex(CapturePipelineError, "DOCUMENT_.*(RIGHTS|AUTH)"):
                self._capture(store, body_store, rights="UNKNOWN")
            self.last_ocr_mock.assert_not_called()
            self.assertEqual(store.captures, {})
            self.assertEqual(store.passages, {})
            first, _, _ = self._capture(store, body_store)
            key = ("content:owner-product-ocr", sha(PDF))
            held = replace(store.captures[key]["record"], hold_status="RIGHTS_HOLD")
            store.captures[key]["record"] = held
            with self.assertRaisesRegex(CapturePipelineError, "DOCUMENT_CAPTURE_HELD"):
                self._capture(store, body_store)
            self.last_ocr_mock.assert_not_called()
            self.assertEqual(len(store.passages), 2)

    def test_source_revoked_during_second_ocr_replay_blocks_all_passage_inserts(self):
        class RevocableGuard(self.ApprovedOwnerSourceGuard):
            revoked = False

            def require(self, operation, **kwargs):
                if self.revoked:
                    raise SourceUseBlocked("SOURCE_USE_REVOKED")
                return super().require(operation, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            store = self.CompletePrivateCaptureStore()
            guard = RevocableGuard()
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_REVOKED"):
                self._capture(
                    store, CaptureBodyStore(Path(tmp)), guard=guard,
                    on_replay=lambda: setattr(guard, "revoked", True),
                )
            self.assertEqual(self.last_ocr_mock.call_count, 2)
            self.assertEqual(store.passages, {})

    def test_persisted_legal_hold_during_second_ocr_replay_blocks_all_passages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.CompletePrivateCaptureStore()

            def hold_capture():
                key = ("content:owner-product-ocr", sha(PDF))
                row = store.captures[key]
                row["record"] = replace(row["record"], hold_status="LEGAL_HOLD")

            with self.assertRaisesRegex(CapturePipelineError, "DOCUMENT_CAPTURE_HELD"):
                self._capture(
                    store, CaptureBodyStore(Path(tmp)), on_replay=hold_capture,
                )
            self.assertEqual(self.last_ocr_mock.call_count, 2)
            self.assertEqual(store.passages, {})


if __name__ == "__main__":
    unittest.main()
