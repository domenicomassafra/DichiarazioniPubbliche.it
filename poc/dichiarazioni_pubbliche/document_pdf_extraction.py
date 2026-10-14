"""DP-238: opt-in isolated PDF-born-digital text extraction into private candidates.

Uses an optional installed pypdf backend in a bounded subprocess, not a regex
decoder or OCR system. Every character remains UNREVIEWED, not VERBATIM or an
approved public quotation. Upstream must authorize capture and PARSE_TEXT and
store only private rights-bound records. Mixed image/text, unsupported PDF
features, missing pages, oversized records and worker failure are held.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys

from dichiarazioni_pubbliche.capture_pipeline import MAX_PARSED_TEXT_CHARS, ParseResult
from dichiarazioni_pubbliche.document_text_extraction import (
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENT_PAGES,
    _DocumentHold,
    _page_selectors,
    _role_hints,
    _sha,
    _spans,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


PDF_TEXT_VERSION = "isolated-pypdf-text-candidate-v1"
_MAX_RESULT_BYTES = MAX_PARSED_TEXT_CHARS * 6 + 32_768
# The worker is launched via ``python -m``. Resolve the package root when this
# module loads so a caller's later chdir/PYTHONPATH changes cannot hide it.
_WORKER_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


class BornDigitalPDFTextParser:
    """Isolated, deterministic and explicitly non-authoritative PDF parser."""

    parser_method = "NATIVE_PDF_TEXT_CANDIDATE"
    parser_version = PDF_TEXT_VERSION

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        def failed(code: str) -> ParseResult:
            return ParseResult(
                "FAILED", self.parser_method, self.parser_version, error_category=code
            )

        if (
            not isinstance(fetched, FetchedBytes)
            or not isinstance(fetched.body, bytes)
            or type(fetched.content_length) is not int
        ):
            return failed("DOCUMENT_BODY_INVALID")
        if fetched.content_length != len(fetched.body):
            return failed("DOCUMENT_LENGTH_MISMATCH")
        if type(fetched.status_code) is not int or not 200 <= fetched.status_code < 300:
            return failed("DOCUMENT_SOURCE_STATUS_INVALID")
        if len(fetched.body) > MAX_DOCUMENT_BYTES:
            return failed("DOCUMENT_BODY_OVERSIZE")
        if (
            str(fetched.media_type or "").split(";", 1)[0].strip().lower()
            != "application/pdf"
        ):
            return failed("DOCUMENT_FORMAT_UNSUPPORTED")
        if (
            not fetched.body.startswith(b"%PDF-")
            or b"%%EOF" not in fetched.body[-1024:]
        ):
            return failed("DOCUMENT_PDF_CORRUPT")
        if os.name != "posix":
            return failed("DOCUMENT_PDF_WORKER_UNAVAILABLE")
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dichiarazioni_pubbliche.document_pdf_extraction",
                    "--extract-worker",
                ],
                input=fetched.body,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=_WORKER_PACKAGE_ROOT,
                timeout=5,
                check=False,
            )
        except (OSError, TimeoutError, subprocess.TimeoutExpired):
            return failed("DOCUMENT_PDF_WORKER_UNAVAILABLE")
        if process.returncode or len(process.stdout) > _MAX_RESULT_BYTES:
            return failed("DOCUMENT_PDF_WORKER_UNAVAILABLE")
        try:
            response = json.loads(process.stdout)
            if not isinstance(response, dict):
                return failed("DOCUMENT_PDF_WORKER_INVALID")
            if response.get("status") == "FAILED":
                code = response.get("code")
                if code in {
                    "DOCUMENT_PDF_BACKEND_UNAVAILABLE",
                    "DOCUMENT_PDF_CORRUPT",
                    "DOCUMENT_PDF_UNSUPPORTED",
                    "DOCUMENT_PDF_OCR_REQUIRED",
                    "DOCUMENT_INCOMPLETE_PAGE",
                    "DOCUMENT_PDF_TOO_MANY_PAGES",
                    "DOCUMENT_PDF_READING_ORDER_UNSAFE",
                    "DOCUMENT_PDF_COMPLEXITY_LIMIT",
                }:
                    return failed(code)
                return failed("DOCUMENT_PDF_WORKER_INVALID")
            pages = response.get("pages")
            if (
                response.get("status") != "SUCCEEDED"
                or not isinstance(pages, list)
                or not 1 <= len(pages) <= MAX_DOCUMENT_PAGES
                or any(not isinstance(page, str) for page in pages)
                # A worker page must never smuggle new page boundaries into
                # the parent's canonical text and provenance selectors.
                or any("\f" in page for page in pages)
                or sum(len(page) for page in pages) > MAX_PARSED_TEXT_CHARS
            ):
                return failed("DOCUMENT_PDF_WORKER_INVALID")
            canonical = "\f".join(pages)
            selectors = _page_selectors(canonical)
            spans = _spans(canonical, selectors)
            hints = _role_hints(canonical, selectors)
        except (
            ValueError,
            TypeError,
            KeyError,
            UnicodeDecodeError,
            _DocumentHold,
        ) as exc:
            if isinstance(exc, _DocumentHold):
                return failed(str(exc))
            return failed("DOCUMENT_PDF_WORKER_INVALID")
        return ParseResult(
            status="SUCCEEDED",
            parser_method=self.parser_method,
            parser_version=self.parser_version,
            canonical_text=canonical,
            spans=spans,
            metadata={
                "source_sha256": _sha(fetched.body),
                "canonical_text_sha256": _sha(canonical),
                "page_count": len(selectors),
                "page_selectors": list(selectors),
                "role_hint_candidates": list(hints),
                "role_hints_authoritative": False,
                "ocr_applied": False,
                "source_byte_offsets": False,
                "verbatim_reviewed": False,
                "reading_order_assurance": "UNREVIEWED",
                "source_semantic_fidelity": "REQUIRES_INDEPENDENT_REVIEW",
            },
        )


def _pdf_text_worker() -> None:
    """Private bounded child: output only short JSON, no logging/source bytes."""

    def emit(code: str) -> None:
        sys.stdout.write(json.dumps({"status": "FAILED", "code": code}))

    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
        # RLIMIT_AS may be unsupported on some POSIX kernels; timeout still
        # enforces a wall-clock limit. Never fail open to quote approval.
        try:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        except (OSError, ValueError):
            pass
        try:
            from pypdf import PdfReader
            from pypdf.generic import ContentStream
        except ImportError:
            emit("DOCUMENT_PDF_BACKEND_UNAVAILABLE")
            return
        body = sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1)
        if len(body) > MAX_DOCUMENT_BYTES:
            emit("DOCUMENT_PDF_COMPLEXITY_LIMIT")
            return
        reader = PdfReader(io.BytesIO(body), strict=True)
        if reader.is_encrypted:
            emit("DOCUMENT_PDF_UNSUPPORTED")
            return
        root = reader.trailer.get("/Root")
        if root and any(
            key in root
            for key in ("/OpenAction", "/AA", "/Names", "/AcroForm", "/EmbeddedFiles")
        ):
            emit("DOCUMENT_PDF_UNSUPPORTED")
            return
        if not 1 <= len(reader.pages) <= MAX_DOCUMENT_PAGES:
            emit("DOCUMENT_PDF_TOO_MANY_PAGES")
            return
        pages: list[str] = []
        total = 0
        for page in reader.pages:
            if "/Annots" in page or "/AA" in page:
                emit("DOCUMENT_PDF_UNSUPPORTED")
                return
            # Images (including mixed image+text pages) need an OCR/reading-
            # order review. Never infer text completeness from existing text.
            resources = page.get("/Resources", {})
            if hasattr(resources, "get_object"):
                resources = resources.get_object()
            objects = resources.get("/XObject", {}) if resources else {}
            if hasattr(objects, "get_object"):
                objects = objects.get_object()
            for reference in (objects or {}).values():
                xobject = reference.get_object()
                if xobject.get("/Subtype") == "/Image":
                    emit("DOCUMENT_PDF_OCR_REQUIRED")
                    return
                # Form XObjects may contain nested rasterized pages or
                # unrecoverable reading order; do not silently trust them.
                if xobject.get("/Subtype") == "/Form":
                    emit("DOCUMENT_PDF_READING_ORDER_UNSAFE")
                    return
            # BI/ID/EI images live directly in a page content stream and do
            # not appear in /Resources /XObject. Parse PDF operators rather
            # than searching bytes inside strings or compressed streams.
            contents = page.get_contents()
            if contents is not None and any(
                operator == b"INLINE IMAGE"
                for _, operator in ContentStream(contents, reader).operations
            ):
                emit("DOCUMENT_PDF_OCR_REQUIRED")
                return
            text = page.extract_text(extraction_mode="plain")
            if not isinstance(text, str) or not text.strip():
                emit("DOCUMENT_INCOMPLETE_PAGE")
                return
            text = text.strip("\r\n")
            total += len(text)
            if total > MAX_PARSED_TEXT_CHARS or "\f" in text:
                emit("DOCUMENT_PDF_COMPLEXITY_LIMIT")
                return
            pages.append(text)
        sys.stdout.write(
            json.dumps(
                {"status": "SUCCEEDED", "pages": pages},
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
    except Exception:
        emit("DOCUMENT_PDF_CORRUPT")


if __name__ == "__main__" and sys.argv[1:] == ["--extract-worker"]:
    _pdf_text_worker()


__all__ = ["PDF_TEXT_VERSION", "BornDigitalPDFTextParser"]
