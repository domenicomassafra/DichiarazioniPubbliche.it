"""DP-237 pure exact locator acceptance on deterministic source snapshots."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.corpus_repository import (  # noqa: E402
    ContentCaptureRecord, PassageRecord,
)
from dichiarazioni_pubbliche.original_source_resolver import (  # noqa: E402
    ExactSourceLocator, ObservedMediaSegment, resolve_exact_source_locator,
)


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


SOURCE_HTML = b"<article><p>Primo. No, non aumenta.</p><p>Ultimo.</p></article>"
CANONICAL = "Primo. No, non aumenta. Ultimo."
QUOTE = "No, non aumenta."
QUOTE_START = CANONICAL.index(QUOTE)
PASSAGE_TEXT = "Primo. No, non aumenta."
MEDIA_VARIANT_TEXT = "Benvenuti. Io non confermo. Fine."
MEDIA_SEGMENT_TEXT = "Io non confermo."
MEDIA_START = MEDIA_VARIANT_TEXT.index(MEDIA_SEGMENT_TEXT)


def capture(**updates) -> ContentCaptureRecord:
    base = ContentCaptureRecord(
        id="capture:original:v1",
        content_id="content:official-original",
        observed_at="2026-10-08T12:00:00+00:00",
        final_url="https://example.test/official-source",
        content_sha256=sha(SOURCE_HTML),
        retrieval_method="SAFE_HTTP",
        retrieval_version="safe-v1",
        media_type="text/html",
        body_ref="private:body-v1",
        parser_method="TEST_VISIBLE_TEXT",
        parser_version="text-v1",
    )
    return replace(base, **updates)


def written_passage(**updates) -> PassageRecord:
    base = PassageRecord(
        id="passage:original:1",
        content_id="content:official-original",
        capture_id="capture:original:v1",
        selector_type="TEXT_POSITION",
        start_char=0,
        end_char=len(PASSAGE_TEXT),
        private_text=PASSAGE_TEXT,
        text_sha256=sha(PASSAGE_TEXT),
        extraction_method="TEST_VISIBLE_TEXT",
        extraction_version="text-v1",
    )
    return replace(base, **updates)


def written_locator(**updates) -> ExactSourceLocator:
    base = ExactSourceLocator(
        content_id="content:official-original",
        passage_id="passage:original:1",
        selector_type="TEXT_POSITION",
        quote_start=QUOTE_START,
        quote_end=QUOTE_START + len(QUOTE),
        quote_sha256=sha(QUOTE),
        capture_id="capture:original:v1",
        capture_sha256=sha(SOURCE_HTML),
    )
    return replace(base, **updates)


def written(**kwargs):
    options = dict(
        passage=written_passage(), capture=capture(),
        source_body=SOURCE_HTML, canonical_text=CANONICAL, quote_text=QUOTE,
    )
    options.update(kwargs)
    return resolve_exact_source_locator(written_locator(), **options)


def page_fixture():
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    page_text = "La data e' 5 maggio, non 6 maggio."
    excerpt = "non 6 maggio"
    page = PassageRecord(
        id="passage:pdf:page2",
        content_id="content:official-original",
        capture_id="capture:pdf:1",
        selector_type="PAGE_RANGE", page_start=2, page_end=2,
        text_sha256=sha(page_text),
        private_text=page_text,
        extraction_method="TEST_PDF_TEXT", extraction_version="pdf-v1",
    )
    doc = capture(
        id="capture:pdf:1", content_sha256=sha(pdf),
        media_type="application/pdf", parser_method="TEST_PDF_TEXT",
        parser_version="pdf-v1", metadata={"page_count": 3},
    )
    start = page_text.index(excerpt)
    locator = ExactSourceLocator(
        content_id=doc.content_id, passage_id=page.id,
        selector_type="PAGE_RANGE", capture_id=doc.id,
        capture_sha256=sha(pdf), page_number=2, quote_start=start,
        quote_end=start+len(excerpt), quote_sha256=sha(excerpt),
    )
    return pdf, doc, page, locator, page_text, excerpt


def media_fixture():
    segment = ObservedMediaSegment(
        content_id="content:interview",
        canonical_segment_id="canonical:interview:2",
        transcript_variant_id="variant:interview:v3",
        transcript_variant_sha256=sha(MEDIA_VARIANT_TEXT),
        source_segment_id="segment:interview:2",
        source_segment_sha256=sha(MEDIA_SEGMENT_TEXT),
        variant_text=MEDIA_VARIANT_TEXT,
        segment_text=MEDIA_SEGMENT_TEXT,
        variant_start_char=MEDIA_START,
        variant_end_char=MEDIA_START+len(MEDIA_SEGMENT_TEXT),
        start_ms=2000,
        end_ms=4600,
        speaker_person_id="person:interviewee",
    )
    passage = PassageRecord(
        id="passage:interview:2", content_id=segment.content_id,
        selector_type="MEDIA_SEGMENT_REF",
        canonical_segment_id=segment.canonical_segment_id,
        text_sha256=sha(segment.segment_text),
        extraction_method="CANONICAL_TRANSCRIPT",
        extraction_version="canonical-v1",
    )
    quote = "non confermo"
    start = segment.segment_text.index(quote)
    locator = ExactSourceLocator(
        content_id=segment.content_id, passage_id=passage.id,
        selector_type="MEDIA_SEGMENT_REF",
        canonical_segment_id=segment.canonical_segment_id,
        transcript_variant_id=segment.transcript_variant_id,
        transcript_variant_sha256=segment.transcript_variant_sha256,
        source_segment_id=segment.source_segment_id,
        source_segment_sha256=segment.source_segment_sha256,
        quote_start=start, quote_end=start + len(quote),
        quote_sha256=sha(quote), start_ms=2000, end_ms=4600,
        speaker_person_id=segment.speaker_person_id,
    )
    return segment, passage, locator, quote


class ExactLocatorWrittenTests(unittest.TestCase):
    def test_real_original_html_bytes_bind_source_parser_passage_and_quote(self):
        result = written()
        self.assertTrue(result.located)
        self.assertEqual(result.blockers, ())
        self.assertEqual(result.source_version_sha256, sha(SOURCE_HTML))
        self.assertEqual(len(result.locator_fingerprint or ""), 64)
        self.assertNotIn(QUOTE, str(result))
        self.assertEqual(result, written())

    def test_stale_new_observation_does_not_destroy_historical_locator(self):
        result = written(current_source_sha256=sha(b"new archived HTML revision"))
        self.assertEqual(result.status, "STALE")
        self.assertFalse(result.located)
        self.assertIn("LOCATOR_NEWER_SOURCE_VERSION", result.blockers)
        self.assertEqual(result.source_version_sha256, sha(SOURCE_HTML))
        self.assertEqual(result.locator_fingerprint, written().locator_fingerprint)

    def test_wrong_source_and_old_locator_version_are_blocked(self):
        for options, code in (
            ({"passage": written_passage(content_id="content:other")}, "LOCATOR_PASSAGE_SOURCE_MISMATCH"),
            ({"capture": capture(content_id="content:other")}, "LOCATOR_CAPTURE_BINDING_MISMATCH"),
            ({"capture": capture(id="capture:other")}, "LOCATOR_CAPTURE_BINDING_MISMATCH"),
            ({"capture": capture(content_sha256=sha(b"updated"))}, "LOCATOR_CAPTURE_VERSION_MISMATCH"),
            ({"source_body": b"changed source words"}, "LOCATOR_SOURCE_BYTES_CHANGED"),
            ({"passage": written_passage(extraction_version="text-v2")}, "LOCATOR_PARSER_VERSION_MISMATCH"),
            ({"capture": capture(metadata={"parse_status": "FAILED"})}, "LOCATOR_PARSER_VERSION_MISMATCH"),
            ({"passage": written_passage(text_sha256=sha("altered"))}, "LOCATOR_PASSAGE_TEXT_CHANGED"),
            ({"canonical_text": "Updated. No, non aumenta. Ultimo."}, "LOCATOR_TEXT_SELECTOR_INVALID"),
        ):
            with self.subTest(options=options):
                result = written(**options)
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.blockers, (code,))

    def test_purged_body_stays_addressable_by_hash_but_excerpt_inaccessible(self):
        purged = capture(
            status="PURGED_BODY", body_ref=None,
            body_purged_at="2026-10-09T12:00:00Z",
            purge_reason="RETENTION_POLICY",
            purge_receipt={"state": "PURGED"},
        )
        result = written(capture=purged)
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertEqual(result.blockers, ("LOCATOR_BODY_UNAVAILABLE",))
        self.assertEqual(result.source_version_sha256, sha(SOURCE_HTML))
        result = written(source_body=None)
        self.assertEqual(result.status, "UNAVAILABLE")

    def test_stitched_discontinuous_quote_and_wrong_position_rejected(self):
        fake_quote = "Primo. Ultimo."
        result = resolve_exact_source_locator(
            written_locator(quote_sha256=sha(fake_quote)),
            passage=written_passage(), capture=capture(),
            source_body=SOURCE_HTML, canonical_text=CANONICAL,
            quote_text=fake_quote,
        )
        self.assertEqual(result.blockers, ("LOCATOR_QUOTE_SPAN_MISMATCH",))
        locator = written_locator(quote_start=0, quote_end=len(QUOTE))
        result = resolve_exact_source_locator(
            locator, passage=written_passage(), capture=capture(),
            source_body=SOURCE_HTML, canonical_text=CANONICAL,
            quote_text=QUOTE,
        )
        self.assertEqual(result.blockers, ("LOCATOR_QUOTE_SPAN_MISMATCH",))

    def test_out_of_range_and_mixed_media_selectors_are_blocked(self):
        for locator, code in (
            (written_locator(quote_end=90), "LOCATOR_TEXT_SELECTOR_INVALID"),
            (written_locator(quote_start=90, quote_end=91), "LOCATOR_TEXT_SELECTOR_INVALID"),
            (written_locator(page_number=2), "LOCATOR_TEXT_SELECTOR_INVALID"),
            (written_locator(start_ms=0, end_ms=1000), "LOCATOR_WRITTEN_MEDIA_FIELDS_FORBIDDEN"),
            (written_locator(locator_version="future-v9"), "LOCATOR_VERSION_UNSUPPORTED"),
        ):
            with self.subTest(locator=locator):
                result = resolve_exact_source_locator(
                    locator, passage=written_passage(), capture=capture(),
                    source_body=SOURCE_HTML, canonical_text=CANONICAL,
                    quote_text=QUOTE,
                )
                self.assertEqual(result.blockers, (code,))
        mixed = written(passage=written_passage(page_start=1, page_end=1))
        self.assertEqual(mixed.blockers, ("LOCATOR_TEXT_SELECTOR_INVALID",))


class ExactLocatorPageTests(unittest.TestCase):
    def test_page_two_excerpt_has_pdf_source_version_and_private_locator(self):
        body, capture, passage, locator, page_text, quote = page_fixture()
        result = resolve_exact_source_locator(
            locator, passage=passage, capture=capture, source_body=body,
            page_text=page_text, quote_text=quote,
        )
        self.assertTrue(result.located)
        self.assertEqual(result.source_version_sha256, sha(body))

    def test_wrong_page_cross_page_changed_ocr_and_fake_timestamps_block(self):
        body, capture, passage, locator, page_text, quote = page_fixture()
        base = dict(
            passage=passage, capture=capture, source_body=body,
            page_text=page_text, quote_text=quote,
        )
        for loc, overrides, code in (
            (replace(locator, page_number=3), {}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"passage": replace(passage, page_end=3)}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"page_text": page_text+" appended"}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"capture": replace(capture, media_type="text/html")}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"capture": replace(capture, metadata={"page_count": 1})}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"capture": replace(capture, metadata={})}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (locator, {"passage": replace(passage, start_char=0, end_char=5)}, "LOCATOR_PAGE_SELECTOR_INVALID"),
            (replace(locator, start_ms=0, end_ms=100), {}, "LOCATOR_WRITTEN_MEDIA_FIELDS_FORBIDDEN"),
        ):
            with self.subTest(code=code, locator=loc, overrides=overrides):
                result = resolve_exact_source_locator(loc, **{**base, **overrides})
                self.assertEqual(result.blockers, (code,))


class ExactLocatorMediaTests(unittest.TestCase):
    def test_variant_segment_text_time_and_speaker_bind_to_original(self):
        segment, passage, locator, quote = media_fixture()
        result = resolve_exact_source_locator(
            locator, passage=passage, media_segment=segment, quote_text=quote,
        )
        self.assertTrue(result.located)
        self.assertEqual(result.source_version_sha256, sha(MEDIA_VARIANT_TEXT))
        self.assertEqual(
            resolve_exact_source_locator(
                locator, passage=passage, media_segment=segment, quote_text=quote,
                current_source_sha256=sha("new transcription"),
            ).status, "STALE",
        )

    def test_wrong_speaker_segment_content_variant_and_timing_block(self):
        segment, passage, locator, quote = media_fixture()
        base = dict(passage=passage, media_segment=segment, quote_text=quote)
        for loc, overrides, code in (
            (locator, {"media_segment": replace(segment, speaker_person_id="person:host")}, "LOCATOR_MEDIA_SPEAKER_MISMATCH"),
            (locator, {"media_segment": replace(segment, content_id="content:other")}, "LOCATOR_MEDIA_VERSION_MISMATCH"),
            (locator, {"media_segment": replace(segment, source_segment_id="segment:other")}, "LOCATOR_MEDIA_VERSION_MISMATCH"),
            (locator, {"media_segment": replace(segment, transcript_variant_id="variant:other")}, "LOCATOR_MEDIA_VERSION_MISMATCH"),
            (locator, {"media_segment": replace(segment, variant_text="altered source")}, "LOCATOR_MEDIA_TEXT_MISMATCH"),
            (locator, {"media_segment": replace(segment, variant_start_char=0)}, "LOCATOR_MEDIA_TEXT_MISMATCH"),
            (locator, {"media_segment": replace(segment, start_ms=3000)}, "LOCATOR_MEDIA_TIME_OR_RANGE_MISMATCH"),
            (replace(locator, start_ms=0), {}, "LOCATOR_MEDIA_TIME_OR_RANGE_MISMATCH"),
            (replace(locator, capture_id="fake:written"), {}, "LOCATOR_MEDIA_SOURCE_MISMATCH"),
            (locator, {"passage": replace(passage, page_start=1, page_end=1)}, "LOCATOR_MEDIA_SOURCE_MISMATCH"),
            (replace(locator, start_ms=True), {}, "LOCATOR_MEDIA_TIME_OR_RANGE_MISMATCH"),
            (replace(locator, quote_end=999), {}, "LOCATOR_MEDIA_TIME_OR_RANGE_MISMATCH"),
        ):
            with self.subTest(code=code, locator=loc, overrides=overrides):
                result = resolve_exact_source_locator(loc, **{**base, **overrides})
                self.assertEqual(result.blockers, (code,))

    def test_rejected_media_source_and_stitched_quote_do_not_resolve(self):
        segment, passage, locator, quote = media_fixture()
        self.assertEqual(
            resolve_exact_source_locator(
                locator, passage=replace(passage, content_id="content:neighbor"),
                media_segment=segment, quote_text=quote,
            ).blockers, ("LOCATOR_PASSAGE_SOURCE_MISMATCH",),
        )
        self.assertEqual(
            resolve_exact_source_locator(
                replace(locator, quote_sha256=sha("Io Fine")),
                passage=passage, media_segment=segment, quote_text="Io Fine",
            ).blockers, ("LOCATOR_QUOTE_SPAN_MISMATCH",),
        )


if __name__ == "__main__":
    unittest.main()
