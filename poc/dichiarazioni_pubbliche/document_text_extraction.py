"""DP-238 private, deterministic extraction of *native* written document text.

This is an opt-in ParserAdapter for already acquired, rights-checked bytes. The
source-file SHA is over the original bytes; character selectors address the
versioned canonical text, never fabricated byte offsets. No OCR, PDF font
decoding, legal role adjudication, rights grant, persistence or publication.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from dichiarazioni_pubbliche.capture_pipeline import (
    MAX_PASSAGE_CHARS,
    MAX_PASSAGES,
    MAX_PARSED_TEXT_CHARS,
    ParseResult,
    ParsedSpan,
    _VisibleTextHTMLParser,
)
from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
    deterministic_corpus_id,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


DOCUMENT_TEXT_VERSION = "document-native-text-v1"
MAX_DOCUMENT_BYTES = 1_048_576
MAX_DOCUMENT_PAGES = 64
MAX_XML_ELEMENTS = 8_192
MAX_XML_DEPTH = 48
MAX_ROLE_HINTS = 32

_XML_TYPES = frozenset({"application/xml", "text/xml", "application/akn+xml"})
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_BLOCK_TAGS = frozenset({"p", "paragraph", "div", "section", "article", "h1", "h2", "h3", "item", "li", "alinea", "comma"})
_XML_METADATA_TAGS = frozenset({"meta", "metadata", "teiheader"})
_INCOMPLETE_TAGS = frozenset({"gap", "damage", "unclear", "supplied", "del", "redacted"})
_INCOMPLETE_TEXT = re.compile(
    r"\[(?:omissis|illeggibile|pagina\s+mancante|redatt[oa]|redacted|missing\s+page|illegible|unreadable)\]", re.I
)
_ROLE_CUES = re.compile(
    r"(?im)^(?P<label>testimone|witness|autore\s+del\s+documento|"
    r"document\s+author|relatore|reporting\s+author|"
    r"dichiarazione\s+di\s+parte|party\s+allegation|"
    r"citazione\s+di|quoted\s+speaker)\s*:"
)
_ROLE_BY_LABEL = {
    "testimone": "WITNESS",
    "witness": "WITNESS",
    "autore del documento": "DOCUMENT_AUTHOR",
    "document author": "DOCUMENT_AUTHOR",
    "relatore": "REPORTING_AUTHOR",
    "reporting author": "REPORTING_AUTHOR",
    "dichiarazione di parte": "PARTY_ALLEGATION",
    "party allegation": "PARTY_ALLEGATION",
    "citazione di": "QUOTED_SPEAKER",
    "quoted speaker": "QUOTED_SPEAKER",
}


def _sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


class _DocumentHold(ValueError):
    pass


class _DocumentVisibleHTMLParser(_VisibleTextHTMLParser):
    # The baseline visible-text parser includes <head><title> text. A title
    # is document metadata, not a source quotation or a participant cue.
    _SKIP = _VisibleTextHTMLParser._SKIP | {"head"}


def _xml_pages(raw: bytes) -> str:
    # Reject entities/DTDs before invoking the stdlib tree builder. External
    # references and entity expansion have no place in a private text adapter.
    if re.search(rb"<!\s*(?:doctype|entity)\b", raw, re.I):
        raise _DocumentHold("DOCUMENT_XML_DTD_UNSUPPORTED")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise _DocumentHold("DOCUMENT_XML_CORRUPT") from exc
    parts: list[str] = []
    stack: list[tuple[ET.Element, bool, int]] = [(root, False, 1)]
    elements = 0
    saw_page_marker = False
    # Iterative walk preserves the source document order and bounds nesting.
    while stack:
        element, closing, depth = stack.pop()
        tag = _local_tag(element.tag)
        if not closing:
            elements += 1
            if elements > MAX_XML_ELEMENTS or depth > MAX_XML_DEPTH:
                raise _DocumentHold("DOCUMENT_XML_COMPLEXITY_LIMIT")
            if tag in _XML_METADATA_TAGS:
                # AKN/TEI metadata can name authors/subjects but is not a
                # documentary quotation. Ignore its subtree, retain its tail.
                if element.tail:
                    parts.append(element.tail)
                continue
            if tag in _INCOMPLETE_TAGS:
                raise _DocumentHold("DOCUMENT_INCOMPLETE_PAGE")
            if tag == "pb":
                if list(element) or (element.text or "").strip():
                    raise _DocumentHold("DOCUMENT_PAGE_MARKER_INVALID")
                # A page break at the start marks page 1, not a blank page 0.
                if "".join(parts).strip(" \r\n\t"):
                    parts.append("\f")
                elif saw_page_marker:
                    raise _DocumentHold("DOCUMENT_INCOMPLETE_PAGE")
                saw_page_marker = True
                if element.tail:
                    parts.append(element.tail)
                continue
            if tag == "lb":
                parts.append("\n")
                if element.tail:
                    parts.append(element.tail)
                continue
            if element.text:
                parts.append(element.text)
            stack.append((element, True, depth))
            for child in reversed(element):
                stack.append((child, False, depth + 1))
        else:
            if tag in _BLOCK_TAGS:
                parts.append("\n\n")
            if element.tail:
                parts.append(element.tail)
    return "".join(parts).strip(" \r\n\t")


def _page_selectors(canonical: str) -> tuple[dict[str, object], ...]:
    if not canonical or len(canonical) > MAX_PARSED_TEXT_CHARS:
        raise _DocumentHold("DOCUMENT_TEXT_EMPTY_OR_OVERSIZE")
    pages: list[dict[str, object]] = []
    offset = 0
    for number, page in enumerate(canonical.split("\f"), start=1):
        if number > MAX_DOCUMENT_PAGES:
            raise _DocumentHold("DOCUMENT_PAGE_LIMIT")
        if not page.strip() or "\ufffd" in page or _INCOMPLETE_TEXT.search(page):
            raise _DocumentHold("DOCUMENT_INCOMPLETE_PAGE")
        if any(ord(c) < 32 and c not in "\t\n\r" for c in page):
            raise _DocumentHold("DOCUMENT_CONTROL_CHARACTERS")
        pages.append({
            "page_number": number,
            "start_char": offset,
            "end_char": offset + len(page),
            "page_text_sha256": _sha(page),
            "reading_order": "NATIVE_DOCUMENT_ORDER_UNREVIEWED",
        })
        offset += len(page) + 1
    return tuple(pages)


def _spans(canonical: str, pages: tuple[dict[str, object], ...]) -> tuple[ParsedSpan, ...]:
    result: list[ParsedSpan] = []
    for page in pages:
        start, end = int(page["start_char"]), int(page["end_char"])
        # Every character is covered; no normalization may erase negation,
        # punctuation, reporting clauses, original script, or page separation.
        for offset in range(start, end, MAX_PASSAGE_CHARS):
            stop = min(end, offset + MAX_PASSAGE_CHARS)
            chunk = canonical[offset:stop]
            result.append(ParsedSpan(offset, stop, chunk, _sha(chunk)))
            if len(result) > MAX_PASSAGES:
                raise _DocumentHold("DOCUMENT_PASSAGE_LIMIT")
    return tuple(result)


def _role_hints(canonical: str, pages: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    hints: list[dict[str, object]] = []
    for page in pages:
        start, end = int(page["start_char"]), int(page["end_char"])
        for match in _ROLE_CUES.finditer(canonical[start:end]):
            label = " ".join(match.group("label").casefold().split())
            cue_start, cue_end = start + match.start(), start + match.end()
            hints.append({
                "role_candidate": _ROLE_BY_LABEL[label],
                "page_number": page["page_number"],
                "start_char": cue_start,
                "end_char": cue_end,
                "cue_sha256": _sha(canonical[cue_start:cue_end]),
                "identity": None,
                "evidentiary_status": "UNVERIFIED_PRIVATE_CANDIDATE",
            })
            if len(hints) > MAX_ROLE_HINTS:
                raise _DocumentHold("DOCUMENT_ROLE_HINT_LIMIT")
    return tuple(hints)


class DocumentTextParser:
    """Opt-in ParserAdapter. Upstream must independently enforce PARSE_TEXT rights."""

    parser_method = "NATIVE_DOCUMENT_TEXT"
    parser_version = DOCUMENT_TEXT_VERSION

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        def failed(code: str) -> ParseResult:
            return ParseResult("FAILED", self.parser_method, self.parser_version, error_category=code)

        if not isinstance(fetched.body, bytes) or type(fetched.content_length) is not int:
            return failed("DOCUMENT_BODY_INVALID")
        if len(fetched.body) != fetched.content_length:
            return failed("DOCUMENT_LENGTH_MISMATCH")
        if type(fetched.status_code) is not int or not 200 <= fetched.status_code < 300:
            return failed("DOCUMENT_SOURCE_STATUS_INVALID")
        if len(fetched.body) > MAX_DOCUMENT_BYTES:
            return failed("DOCUMENT_BODY_OVERSIZE")
        media = str(fetched.media_type or "").split(";", 1)[0].strip().lower()
        if media == "application/pdf":
            if not fetched.body.startswith(b"%PDF-") or b"%%EOF" not in fetched.body[-1024:]:
                return failed("DOCUMENT_PDF_CORRUPT")
            # A PDF text stream is not necessarily reading-order text or Unicode;
            # image content cannot be made into a native transcript by regex.
            if re.search(rb"/Subtype\s*/Image\b", fetched.body):
                return failed("DOCUMENT_PDF_OCR_REQUIRED")
            return failed("DOCUMENT_PDF_VERIFIED_TEXT_PARSER_REQUIRED")
        if media.startswith("image/"):
            return failed("DOCUMENT_OCR_REQUIRED")
        if media.startswith(("audio/", "video/")):
            return failed("DOCUMENT_MEDIA_UNSUPPORTED")
        if media not in _XML_TYPES | _HTML_TYPES | {"text/plain"}:
            return failed("DOCUMENT_FORMAT_UNSUPPORTED")
        charset = str(fetched.charset or "utf-8").strip().lower()
        if charset not in {"utf-8", "utf8", "utf-8-sig"}:
            return failed("DOCUMENT_CHARSET_UNSUPPORTED")
        try:
            # Even HTML is decoded strictly; malformed bytes cannot be silently
            # turned into quote-ready replacement characters.
            decoded = fetched.body.decode("utf-8-sig")
        except UnicodeDecodeError:
            return failed("DOCUMENT_ENCODING_CORRUPT")
        try:
            if media in _XML_TYPES:
                canonical = _xml_pages(fetched.body)
            elif media in _HTML_TYPES:
                html_parser = _DocumentVisibleHTMLParser()
                html_parser.feed(decoded)
                html_parser.close()
                canonical = html_parser.text()
            else:
                canonical = decoded
            pages = _page_selectors(canonical)
            spans = _spans(canonical, pages)
            hints = _role_hints(canonical, pages)
        except (_DocumentHold, ET.ParseError) as exc:
            return failed(str(exc) if isinstance(exc, _DocumentHold) else "DOCUMENT_XML_CORRUPT")
        return ParseResult(
            status="SUCCEEDED",
            parser_method=self.parser_method,
            parser_version=self.parser_version,
            canonical_text=canonical,
            spans=spans,
            metadata={
                "source_sha256": _sha(fetched.body),
                "canonical_text_sha256": _sha(canonical),
                "page_count": len(pages),
                "page_selectors": list(pages),
                "role_hint_candidates": list(hints),
                "role_hints_authoritative": False,
                "ocr_applied": False,
                "source_byte_offsets": False,
            },
        )


def document_passages_from_capture(
    *, capture: ContentCaptureRecord, fetched: FetchedBytes, parsed: ParseResult,
    language: str | None = None,
) -> tuple[PassageRecord, ...]:
    """Prepare private passage candidates after capture/use authorization upstream.

    Rerun the deterministic parser against immutable bytes: callers cannot attach
    forged page selectors or OCR-derived verbatim to a different capture.
    This function persists nothing and authorizes no publication or quotation.
    """
    media = str(fetched.media_type or "").split(";", 1)[0].strip().lower()
    replay = DocumentTextParser().parse(fetched)
    if (
        capture.status != "CAPTURED"
        or capture.rights_status != "CLEARED"
        or capture.content_sha256 != _sha(fetched.body)
        or capture.final_url != fetched.final_url
        or capture.media_type != media
        or capture.parser_method != replay.parser_method
        or capture.parser_version != replay.parser_version
        or capture.metadata.get("parse_status") not in {None, "SUCCEEDED"}
        or replay.status != "SUCCEEDED"
        or parsed != replay
    ):
        raise ValueError("DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH")
    pages = replay.metadata["page_selectors"]
    passages: list[PassageRecord] = []
    for span in replay.spans:
        page = next((p for p in pages if p["start_char"] <= span.start_char
                     and span.end_char <= p["end_char"]), None)
        if page is None:
            raise ValueError("DOCUMENT_SPAN_CROSSES_PAGE")
        passages.append(PassageRecord(
            id=deterministic_corpus_id(
                "passage", capture.id, replay.parser_version,
                str(span.start_char), str(span.end_char), span.text_sha256,
            ),
            content_id=capture.content_id,
            capture_id=capture.id,
            selector_type="TEXT_POSITION",
            start_char=span.start_char,
            end_char=span.end_char,
            text_sha256=span.text_sha256,
            private_text=span.text,
            language=language,
            extraction_method=replay.parser_method,
            extraction_version=replay.parser_version,
            metadata={
                "source_sha256": capture.content_sha256,
                "canonical_text_sha256": replay.metadata["canonical_text_sha256"],
                "page_number": page["page_number"],
                "page_text_sha256": page["page_text_sha256"],
                "reading_order": page["reading_order"],
                "original_byte_offset_available": False,
                "verbatim_reviewed": False,
            },
        ))
    return tuple(passages)


__all__ = [
    "DOCUMENT_TEXT_VERSION", "DocumentTextParser", "document_passages_from_capture",
]
