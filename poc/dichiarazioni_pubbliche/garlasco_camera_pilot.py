"""Pinned, bounded private text selectors in two real Camera transcripts.

The original, full HTML is retained as an immutable Capture. A Passage's
TEXT_POSITION offset addresses this parser's explicit excerpt projection,
not an offset into the original HTML bytes.
"""
from __future__ import annotations

import hashlib
import re

from dichiarazioni_pubbliche.capture_pipeline import (
    ParseResult, ParsedSpan, _VisibleTextHTMLParser,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes, fetch_bytes


CAMERA_SOURCES = (
    {
        "key": "sed0607",
        "date": "2026-02-03",
        "url": "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm",
        "speaker": "VITTORIA BALDINO (M5S).",
        "excerpt": ("Stanno strumentalizzando i casi di cronaca nera, come il caso "
                    "Garlasco, mentendo, dicendo che, una volta passata questa "
                    "riforma, non ci sarà più un caso Garlasco."),
        "sha256": "2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f",
    },
    {
        "key": "sed0703",
        "date": "2026-08-04",
        "url": "https://www.camera.it/leg19/410?idSeduta=0703&tipo=stenografico",
        "speaker": "ANDREA ORSINI (FI-PPE).",
        "excerpt": ("Onorevoli colleghi, l'opinione pubblica viene sollecitata molto, "
                    "forse anche troppo, su vicende drammatiche di cronaca come "
                    "l'assassinio a Garlasco della povera Chiara Poggi."),
        "sha256": "89433031d6366d30d6158c13a20e1fdc71cd88fc151d5fd4c5a769f759cb5700",
        # This HTML endpoint includes varying response bytes between requests.
        # Revalidate exact speech/sitting on every fetch; hash and retain the
        # *actually observed* full response as a new immutable Capture.
        "variable_html": True,
    },
)


def pinned_excerpt(source: dict[str, str], canonical_text: str) -> str:
    """Reject missing/duplicated quotation, speaker changes and nearby handoffs."""
    quote, speaker = source["excerpt"], source["speaker"]
    if canonical_text.count(quote) != 1:
        raise ValueError("DP426_ORIGINAL_QUOTATION_MISSING_OR_DUPLICATED")
    position = canonical_text.index(quote)
    speaker_at = canonical_text.rfind(speaker, 0, position)
    if speaker_at < 0 or position - speaker_at > 6000:
        raise ValueError("DP426_ORIGINAL_SPEAKER_UNVERIFIED")
    intervening = canonical_text[speaker_at + len(speaker):position]
    # A new floor speaker before the quote invalidates its attribution.
    if (
        "PRESIDENTE. Ha chiesto" in intervening
        or "\n\nPRESIDENTE." in intervening
        or re.search(
            r"(?:^|\n\n)[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ\x27’ -]{2,90}"
            r"\s+\([A-Z0-9+/\x27’ -]{2,32}\)\.",
            intervening,
        )
    ):
        raise ValueError("DP426_ORIGINAL_SPEAKER_CHANGED")
    return quote


class CameraSpeechParser:
    parser_method = "CAMERA_OFFICIAL_PINNED_EXCERPT"
    parser_version = "dp426-camera-garlasco-excerpt-v1"

    def __init__(self, source: dict[str, str]):
        self.source = source

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        if fetched.media_type.split(";", 1)[0] not in {"text/html", "application/xhtml+xml"}:
            return self._hold("DP426_ORIGINAL_HTML_REQUIRED")
        parser = _VisibleTextHTMLParser()
        try:
            parser.feed(fetched.body.decode(fetched.charset or "utf-8", errors="replace"))
            parser.close()
            quote = pinned_excerpt(self.source, parser.text())
        except (ValueError, UnicodeError):
            return self._hold("DP426_ORIGINAL_QUOTATION_OR_SPEAKER_MISMATCH")
        digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
        return ParseResult(
            status="SUCCEEDED", parser_method=self.parser_method,
            parser_version=self.parser_version, canonical_text=quote,
            spans=(ParsedSpan(0, len(quote), quote, digest),),
            metadata={
                "text_selector_scope": "ONE_PINNED_EXCERPT_NOT_FULL_PAGE",
                "original_body_sha256": hashlib.sha256(fetched.body).hexdigest(),
                "official_sitting": self.source["key"],
                "speaker_label_from_original": self.source["speaker"],
            },
        )

    def _hold(self, code: str) -> ParseResult:
        return ParseResult(status="FAILED", parser_method=self.parser_method,
                           parser_version=self.parser_version, error_category=code)


def original_versions(authority):
    """Independent bounded HTTPS acquisition, before any persistence."""
    observations = []
    for source in CAMERA_SOURCES:
        fetched = fetch_bytes(source["url"], max_response_bytes=3_000_000)
        sha = hashlib.sha256(fetched.body).hexdigest()
        if ((not source.get("variable_html") and sha != source["sha256"])
                or fetched.final_url != source["url"] or fetched.status_code != 200):
            raise ValueError("DP426_ORIGINAL_VERSION_CHANGED")
        content_id = f"content:garlasco:camera:{source['key']}"
        if authority.inspect(
            content_id=content_id, capture_sha256=sha, use="PARSE_TEXT",
        )["permitted"] is not True:
            raise ValueError("DP426_SIGNED_CAMERA_PARSE_AUTHORITY_REQUIRED")
        parsed = CameraSpeechParser(source).parse(fetched)
        if parsed.status != "SUCCEEDED" or len(parsed.spans) != 1:
            raise ValueError("DP426_VERBATIM_SPEAKER_CHECK_FAILED")
        observations.append(({**source, "sha256": sha}, fetched, parsed))
    return observations
