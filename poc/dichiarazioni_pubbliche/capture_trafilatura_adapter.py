"""Opt-in, offline Trafilatura adapter for already authorized HTML captures.

This module never retrieves URLs. CapturePipeline owns URL, body-size and rights
checks; its ParserAdapter protocol accepts this replaceable extractor explicitly.
"""

from __future__ import annotations

import re
from dataclasses import replace
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

from dichiarazioni_pubbliche.capture_pipeline import (
    CapturePipelineError,
    ParseResult,
    StdlibVisibleTextParser,
    _decode,
    _normalize_media_type,
    _split_canonical_text,
    extract_source_metadata,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


TRAFILATURA_VERSION = "2.3.1"
TRAFILATURA_PARSER_VERSION = f"trafilatura-{TRAFILATURA_VERSION}-dp1"


class TrafilaturaHTMLParser:
    """Optional ParserAdapter; missing/broken donor falls back to stdlib.

    A genuine *empty* extraction stays failed, rather than turning navigation,
    legal notices or cookie banners into publishable-looking passages.
    """

    parser_method = "TRAFILATURA_HTML"
    parser_version = TRAFILATURA_PARSER_VERSION

    def __init__(self, *, extract_metadata: bool = True) -> None:
        self.extract_metadata = bool(extract_metadata)

    def _fallback(self, fetched: FetchedBytes, reason: str) -> ParseResult:
        parsed = StdlibVisibleTextParser(extract_metadata=self.extract_metadata).parse(fetched)
        if not self.extract_metadata:
            return parsed
        return replace(parsed, metadata={
            **parsed.metadata,
            "html_extraction": {
                "requested_parser": self.parser_version,
                "actual_parser": parsed.parser_version,
                "fallback_reason": reason,
            },
        })

    def _failure(self, reason: str) -> ParseResult:
        return ParseResult(
            status="FAILED",
            parser_method=self.parser_method,
            parser_version=self.parser_version,
            error_category=reason,
        )

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        if _normalize_media_type(fetched.media_type) not in {
            "text/html", "application/xhtml+xml",
        }:
            return StdlibVisibleTextParser(extract_metadata=self.extract_metadata).parse(fetched)

        try:
            installed = version("trafilatura")
        except PackageNotFoundError:
            return self._fallback(fetched, "TRAFILATURA_UNAVAILABLE")
        if installed != TRAFILATURA_VERSION:
            return self._fallback(fetched, "TRAFILATURA_VERSION_MISMATCH")
        try:
            trafilatura = import_module("trafilatura")
        except (ImportError, RuntimeError, OSError):
            return self._fallback(fetched, "TRAFILATURA_IMPORT_FAILED")

        decoded = _decode(fetched.body, fetched.charset)
        try:
            extracted = trafilatura.extract(
                decoded,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
        except Exception:
            return self._fallback(fetched, "TRAFILATURA_EXTRACTION_FAILED")

        if not isinstance(extracted, str) or not extracted.strip():
            return self._failure("PARSER_EMPTY_TEXT")
        # Trafilatura outputs one paragraph per line. Canonical passages retain
        # their own source-capture-bound character spans and UTF-8 SHA-256.
        paragraphs = (re.sub(r"\s+", " ", line).strip() for line in extracted.splitlines())
        canonical = "\n\n".join(line for line in paragraphs if line)
        try:
            spans = _split_canonical_text(canonical)
        except CapturePipelineError as exc:
            return self._failure(exc.code)
        if not spans:
            return self._failure("PARSER_EMPTY_TEXT")

        metadata = {}
        if self.extract_metadata:
            try:
                metadata = extract_source_metadata(decoded, base_url=fetched.final_url)
            except CapturePipelineError:
                metadata = {"metadata_parse_status": "FAILED"}
            metadata["html_extraction"] = {
                "requested_parser": self.parser_version,
                "actual_parser": self.parser_version,
            }
        return ParseResult(
            status="SUCCEEDED",
            parser_method=self.parser_method,
            parser_version=self.parser_version,
            canonical_text=canonical,
            spans=spans,
            metadata=metadata,
        )


__all__ = ["TRAFILATURA_VERSION", "TRAFILATURA_PARSER_VERSION", "TrafilaturaHTMLParser"]
