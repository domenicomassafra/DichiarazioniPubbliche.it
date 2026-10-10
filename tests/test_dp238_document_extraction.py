"""Offline DP-238 native text provenance checks; no OCR/rights/public claims."""

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord  # noqa: E402
from dichiarazioni_pubbliche.document_text_extraction import (  # noqa: E402
    DOCUMENT_TEXT_VERSION,
    DocumentTextParser,
    document_passages_from_capture,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes  # noqa: E402


def sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def fetched(data: bytes, *, media: str = "text/plain", charset: str = "utf-8") -> FetchedBytes:
    return FetchedBytes(
        body=data, final_url="https://source.example/document", status_code=200,
        media_type=media, charset=charset, content_length=len(data),
    )


def capture(body: bytes, *, media: str = "text/plain", ident: str = "capture:first") -> ContentCaptureRecord:
    return ContentCaptureRecord(
        id=ident, content_id="content:document", observed_at="2026-10-11T00:00:00+00:00",
        final_url="https://source.example/document", media_type=media,
        content_sha256=sha(body), retrieval_method="TEST_FIXTURE",
        retrieval_version="test-v1", parser_method="NATIVE_DOCUMENT_TEXT",
        parser_version=DOCUMENT_TEXT_VERSION, rights_status="CLEARED",
    )


class DocumentExtractionTests(unittest.TestCase):
    def setUp(self):
        self.parser = DocumentTextParser()

    def test_plain_two_page_order_exact_quotation_negation_numeric_date(self):
        text = 'Il testimone non ha detto "sì".\nData: 10/11/2026.\fTestimone: "Non confermo 42".'
        body = text.encode("utf-8")
        parsed = self.parser.parse(fetched(body))
        self.assertEqual(parsed.status, "SUCCEEDED")
        self.assertEqual(parsed.canonical_text, text)
        self.assertEqual(parsed.metadata["source_sha256"], sha(body))
        self.assertEqual(parsed.metadata["page_count"], 2)
        self.assertEqual([row["page_number"] for row in parsed.metadata["page_selectors"]], [1, 2])
        self.assertEqual([row["start_char"] for row in parsed.metadata["page_selectors"]], [0, text.index("\f") + 1])
        self.assertEqual(parsed.metadata["role_hint_candidates"][0]["role_candidate"], "WITNESS")
        self.assertIsNone(parsed.metadata["role_hint_candidates"][0]["identity"])
        passages = document_passages_from_capture(capture=capture(body), fetched=fetched(body), parsed=parsed, language="it")
        self.assertEqual(len(passages), 2)
        self.assertTrue(all(p.selector_type == "TEXT_POSITION" for p in passages))
        self.assertEqual([p.metadata["page_number"] for p in passages], [1, 2])
        for passage in passages:
            self.assertEqual(text[passage.start_char:passage.end_char], passage.private_text)
            self.assertEqual(sha(passage.private_text), passage.text_sha256)
            self.assertFalse(passage.metadata["verbatim_reviewed"])

    def test_plain_replay_stable_and_mutated_source_gets_distinct_derivation(self):
        body = b"No, that did not happen.\fWitness: not confirmed."
        original = self.parser.parse(fetched(body))
        source = capture(body)
        first = document_passages_from_capture(capture=source, fetched=fetched(body), parsed=original)
        self.assertEqual(first, document_passages_from_capture(capture=source, fetched=fetched(body), parsed=original))
        changed = body.replace(b"not confirmed", b"confirmed")
        new_source = capture(changed, ident="capture:second")
        second = document_passages_from_capture(capture=new_source, fetched=fetched(changed), parsed=self.parser.parse(fetched(changed)))
        self.assertNotEqual([p.id for p in first], [p.id for p in second])
        with self.assertRaisesRegex(ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"):
            document_passages_from_capture(capture=source, fetched=fetched(changed), parsed=original)

    def test_xml_akoma_pagebreak_source_order_and_escaped_quote(self):
        body = (
            b'<akomaNtoso xmlns="urn:akn"><meta><title>Testimone: Mario</title></meta>'
            b'<body><p>Non e vero &amp; non affermato.</p>'
            b'<pb n="2"/><p>"Ha detto": solo citazione.</p></body></akomaNtoso>'
        )
        parsed = self.parser.parse(fetched(body, media="application/akn+xml"))
        self.assertEqual(parsed.status, "SUCCEEDED")
        self.assertEqual(parsed.metadata["page_count"], 2)
        self.assertIn("Non e vero & non affermato.", parsed.canonical_text)
        self.assertIn('"Ha detto": solo citazione.', parsed.canonical_text)
        self.assertEqual(parsed.metadata["role_hint_candidates"], [])
        self.assertNotIn("Mario", parsed.canonical_text)
        self.assertEqual(parsed.metadata["page_selectors"][1]["page_number"], 2)

    def test_html_visible_text_and_no_role_from_head_metadata(self):
        body = (
            b'<html><head><title>Testimone: Mario</title><script>WITNESS</script></head>'
            b'<body><p>Non sono stato io.</p><p>"Ha detto no".</p></body></html>'
        )
        parsed = self.parser.parse(fetched(body, media="text/html"))
        self.assertEqual(parsed.status, "SUCCEEDED")
        self.assertEqual(parsed.canonical_text, 'Non sono stato io.\n\n"Ha detto no".')
        self.assertEqual(parsed.metadata["page_count"], 1)
        self.assertEqual(parsed.metadata["role_hint_candidates"], [])

    def test_role_labels_are_unverified_hints_and_never_verdicts(self):
        text = "Dichiarazione di parte: imputato nega.\nCitazione di: altro dichiara no.\nLa corte respinge."
        parsed = self.parser.parse(fetched(text.encode()))
        self.assertEqual([x["role_candidate"] for x in parsed.metadata["role_hint_candidates"]],
                         ["PARTY_ALLEGATION", "QUOTED_SPEAKER"])
        self.assertNotIn("COURT_FINDING", str(parsed.metadata["role_hint_candidates"]))
        self.assertFalse(parsed.metadata["role_hints_authoritative"])

    def test_long_document_chunks_preserve_every_character_without_cross_page_span(self):
        text = "A" * 9_000 + "\f" + "B" * 4_200
        parsed = self.parser.parse(fetched(text.encode()))
        self.assertEqual(parsed.status, "SUCCEEDED")
        self.assertEqual("".join(x.text for x in parsed.spans[:3]), "A" * 9_000)
        self.assertEqual("".join(x.text for x in parsed.spans[3:]), "B" * 4_200)
        self.assertTrue(all(x.end_char <= text.index("\f") or x.start_char > text.index("\f") for x in parsed.spans))

    def test_corrupt_oversize_and_other_media_hold_without_passages(self):
        cases = [
            (fetched(b"A" * (1_048_576 + 1)), "DOCUMENT_BODY_OVERSIZE"),
            (fetched(b"\xffbad"), "DOCUMENT_ENCODING_CORRUPT"),
            (fetched(b"broken", charset="latin-1"), "DOCUMENT_CHARSET_UNSUPPORTED"),
            (fetched(b"%PDF-1.7 invalid", media="application/pdf"), "DOCUMENT_PDF_CORRUPT"),
            (fetched(b"%PDF-1.7\n1 0 obj<</Subtype /Image>>endobj\n%%EOF", media="application/pdf"), "DOCUMENT_PDF_OCR_REQUIRED"),
            (fetched(b"%PDF-1.7\n%%EOF", media="application/pdf"), "DOCUMENT_PDF_VERIFIED_TEXT_PARSER_REQUIRED"),
            (fetched(b"\x89PNG...", media="image/png"), "DOCUMENT_OCR_REQUIRED"),
            (fetched(b"foo", media="audio/mpeg"), "DOCUMENT_MEDIA_UNSUPPORTED"),
            (fetched(b"foo", media="application/octet-stream"), "DOCUMENT_FORMAT_UNSUPPORTED"),
        ]
        for document, code in cases:
            with self.subTest(code=code):
                result = self.parser.parse(document)
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error_category, code)
                self.assertFalse(result.spans)
                self.assertFalse(result.canonical_text)

    def test_xml_malformed_dtd_entity_bomb_and_missing_page_hold(self):
        bodies = [
            (b"<root><p>incomplete", "DOCUMENT_XML_CORRUPT"),
            (b'<!DOCTYPE root [<!ENTITY x "bomb">]><root>&x;</root>', "DOCUMENT_XML_DTD_UNSUPPORTED"),
            (b"<root><p>first</p><pb/><gap reason='lost'/><p>not verified</p></root>", "DOCUMENT_INCOMPLETE_PAGE"),
            (b"<root><p>page one</p><pb/><pb/><p>page three</p></root>", "DOCUMENT_INCOMPLETE_PAGE"),
            (b"<root><p>page one</p><pb/></root>", "DOCUMENT_INCOMPLETE_PAGE"),
        ]
        for body, code in bodies:
            with self.subTest(body=body[:24]):
                result = self.parser.parse(fetched(body, media="text/xml"))
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error_category, code)

    def test_xml_complexity_and_page_limits_are_held(self):
        for body, code in (
            (b"<r>" + b"<i/>" * 8_193 + b"</r>", "DOCUMENT_XML_COMPLEXITY_LIMIT"),
            (b"<r>" + b"<i>" * 49 + b"a" + b"</i>" * 49 + b"</r>", "DOCUMENT_XML_COMPLEXITY_LIMIT"),
            (b"first" + (b"\fnext" * 64), "DOCUMENT_PAGE_LIMIT"),
        ):
            with self.subTest(code=code):
                media = "text/plain" if b"\f" in body else "application/xml"
                result = self.parser.parse(fetched(body, media=media))
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error_category, code)

    def test_incomplete_text_pages_and_redaction_hold(self):
        for text in ("First\f", "\fSecond", "First\f \n \fThird", "First [omissis] continued", "One\x00two"):
            with self.subTest(text=text):
                self.assertNotEqual(self.parser.parse(fetched(text.encode())).status, "SUCCEEDED")

    def test_reject_tampered_selectors_capture_and_parser_version(self):
        body = b"Testimone: not guilty."
        parsed = self.parser.parse(fetched(body))
        valid_capture = capture(body)
        for bogus_capture in (
            replace(valid_capture, content_sha256="0" * 64),
            replace(valid_capture, media_type="application/pdf"),
            replace(valid_capture, final_url="https://different.example/original"),
            replace(valid_capture, parser_version="unreviewed-ocr-v1"),
            replace(valid_capture, parser_method=None),
            replace(valid_capture, metadata={"parse_status": "FAILED"}),
            replace(valid_capture, status="QUARANTINED"),
            replace(valid_capture, rights_status="UNKNOWN"),
            replace(valid_capture, rights_status="REVOKED"),
        ):
            with self.subTest(bogus_capture=bogus_capture):
                with self.assertRaisesRegex(ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"):
                    document_passages_from_capture(capture=bogus_capture, fetched=fetched(body), parsed=parsed)
        forged = replace(parsed, canonical_text="Document author confirms guilt.")
        with self.assertRaisesRegex(ValueError, "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH"):
            document_passages_from_capture(capture=valid_capture, fetched=fetched(body), parsed=forged)


if __name__ == "__main__":
    unittest.main()
