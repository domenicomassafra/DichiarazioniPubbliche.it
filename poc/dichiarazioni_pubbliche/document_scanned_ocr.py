"""DP-238 opt-in, private scanned-PDF OCR candidates on a native MiniPC.

Requires installed Poppler and Tesseract (ita+eng). This is deliberately not
registered as the default PDF parser: rights must be checked by the caller and
OCR words always require independent source comparison before any quotation.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tempfile

from dichiarazioni_pubbliche.capture_pipeline import MAX_PARSED_TEXT_CHARS, ParseResult
from dichiarazioni_pubbliche.document_text_extraction import (
    MAX_DOCUMENT_BYTES,
    _DocumentHold,
    _page_selectors,
    _role_hints,
    _sha,
    _spans,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


OCR_VERSION = "poppler-tesseract-private-ocr-candidate-v1"
OCR_PROFILE = "ita+eng/psm3/120dpi/scale2500"
MAX_OCR_PAGES = 4
MAX_OCR_WORDS = 10_000
MAX_WORKER_OUTPUT = 4 * 1024 * 1024
_WORKER_CWD = str(Path(__file__).resolve().parents[1])


class ScannedPDFOCRParser:
    """Fail-closed scanned-page adapter, separate from born-digital extraction."""

    parser_method = "SCANNED_PDF_OCR_CANDIDATE"
    parser_version = OCR_VERSION

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        def fail(code: str) -> ParseResult:
            return ParseResult(
                "FAILED", self.parser_method, self.parser_version, error_category=code
            )

        if (
            not isinstance(fetched, FetchedBytes)
            or not isinstance(fetched.body, bytes)
            or type(fetched.content_length) is not int
        ):
            return fail("DOCUMENT_BODY_INVALID")
        if fetched.content_length != len(fetched.body):
            return fail("DOCUMENT_LENGTH_MISMATCH")
        if type(fetched.status_code) is not int or fetched.status_code != 200:
            return fail("DOCUMENT_SOURCE_STATUS_INVALID")
        if len(fetched.body) > MAX_DOCUMENT_BYTES:
            return fail("DOCUMENT_BODY_OVERSIZE")
        if (
            str(fetched.media_type or "").split(";", 1)[0].strip().lower()
            != "application/pdf"
        ):
            return fail("DOCUMENT_FORMAT_UNSUPPORTED")
        if (
            not fetched.body.startswith(b"%PDF-")
            or b"%%EOF" not in fetched.body[-1024:]
        ):
            return fail("DOCUMENT_PDF_CORRUPT")
        if os.name != "posix":
            return fail("DOCUMENT_OCR_WORKER_UNAVAILABLE")
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dichiarazioni_pubbliche.document_scanned_ocr",
                    "--worker",
                ],
                input=fetched.body,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=_WORKER_CWD,
                timeout=75,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return fail("DOCUMENT_OCR_WORKER_UNAVAILABLE")
        if process.returncode or len(process.stdout) > MAX_WORKER_OUTPUT:
            return fail("DOCUMENT_OCR_WORKER_UNAVAILABLE")
        try:
            response = json.loads(process.stdout)
            if not isinstance(response, dict):
                return fail("DOCUMENT_OCR_WORKER_INVALID")
            if response.get("status") == "FAILED":
                code = response.get("code")
                if code in {
                    "DOCUMENT_OCR_BACKEND_UNAVAILABLE",
                    "DOCUMENT_PDF_CORRUPT",
                    "DOCUMENT_PDF_UNSUPPORTED",
                    "DOCUMENT_OCR_PAGE_LIMIT",
                    "DOCUMENT_INCOMPLETE_PAGE",
                    "DOCUMENT_OCR_COMPLEXITY_LIMIT",
                    "DOCUMENT_OCR_PROCESS_FAILED",
                }:
                    return fail(code)
                return fail("DOCUMENT_OCR_WORKER_INVALID")
            pages = response.get("pages")
            engine = response.get("engine")
            if (
                response.get("status") != "SUCCEEDED"
                or not isinstance(pages, list)
                or not 1 <= len(pages) <= MAX_OCR_PAGES
                or not isinstance(engine, str)
                or not re.fullmatch(r"tesseract [0-9][0-9A-Za-z.+-]{1,55}", engine)
            ):
                return fail("DOCUMENT_OCR_WORKER_INVALID")
            texts = []
            boxes = []
            count = 0
            absolute_offset = 0
            for number, page in enumerate(pages, 1):
                if not isinstance(page, dict) or set(page) != {
                    "text",
                    "pixels",
                    "words",
                }:
                    return fail("DOCUMENT_OCR_WORKER_INVALID")
                content, pixels, words = page["text"], page["pixels"], page["words"]
                if (
                    not isinstance(content, str)
                    or not content.strip()
                    or "\f" in content
                    or not isinstance(pixels, list)
                    or len(pixels) != 2
                    or any(type(n) is not int or not 1 <= n <= 2500 for n in pixels)
                    or not isinstance(words, list)
                ):
                    return fail("DOCUMENT_OCR_WORKER_INVALID")
                for word in words:
                    if (
                        not isinstance(word, list)
                        or len(word) != 7
                        or any(type(n) is not int for n in word)
                    ):
                        return fail("DOCUMENT_OCR_WORKER_INVALID")
                    start, end, x, y, width, height, confidence = word
                    if (
                        not 0 <= start < end <= len(content)
                        or not 0 <= x < pixels[0]
                        or not 0 <= y < pixels[1]
                        or not 0 < width <= pixels[0] - x
                        or not 0 < height <= pixels[1] - y
                        or not 0 <= confidence <= 100
                        or not content[start:end].strip()
                    ):
                        return fail("DOCUMENT_OCR_WORKER_INVALID")
                    boxes.append(
                        {
                            "page_number": number,
                            "start_char": absolute_offset + start,
                            "end_char": absolute_offset + end,
                            "bbox_pixels": [x, y, width, height],
                            "confidence_percent": confidence,
                        }
                    )
                count += len(words)
                if count > MAX_OCR_WORDS:
                    return fail("DOCUMENT_OCR_COMPLEXITY_LIMIT")
                texts.append(content)
                absolute_offset += len(content) + 1
            canonical = "\f".join(texts)
            selectors = tuple(
                {
                    **selector,
                    "reading_order": "OCR_READING_ORDER_UNVERIFIED",
                    "page_pixels": pages[index]["pixels"],
                }
                for index, selector in enumerate(_page_selectors(canonical))
            )
            spans = _spans(canonical, selectors)
            hints = _role_hints(canonical, selectors)
        except (ValueError, TypeError, KeyError, _DocumentHold):
            return fail("DOCUMENT_OCR_WORKER_INVALID")
        # Changing the installed OCR engine produces a new derivation version,
        # even if the returned words happen to be identical. Old captures then
        # fail replay rather than silently replacing their extraction lineage.
        effective_version = (
            f"{OCR_VERSION}/tesseract-{engine.removeprefix('tesseract ')}"
        )
        return ParseResult(
            "SUCCEEDED",
            self.parser_method,
            effective_version,
            canonical_text=canonical,
            spans=spans,
            metadata={
                "source_sha256": _sha(fetched.body),
                "canonical_text_sha256": _sha(canonical),
                "page_count": len(pages),
                "page_selectors": list(selectors),
                "ocr_word_boxes": boxes,
                "ocr_word_count": count,
                "ocr_engine_version": engine,
                "ocr_profile": OCR_PROFILE,
                "role_hint_candidates": list(hints),
                "role_hints_authoritative": False,
                "ocr_applied": True,
                "source_byte_offsets": False,
                "verbatim_reviewed": False,
                "reading_order_assurance": "UNREVIEWED",
                "source_semantic_fidelity": "INDEPENDENT_IMAGE_GOLD_REQUIRED",
                "critical_spans": "HELD_INDEPENDENT_REVIEW_REQUIRED",
            },
        )


def _run(
    args: list[str], *, input_bytes: bytes | None = None, timeout: int = 12
) -> bytes:
    p = subprocess.run(
        args,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
    )
    if p.returncode or len(p.stdout) > MAX_WORKER_OUTPUT:
        raise RuntimeError("OCR command failed or exceeded output limit")
    return p.stdout


def _extract_ocr_pages(body: bytes) -> dict[str, object]:
    pdfinfo, rasterizer, engine = (
        shutil.which(cmd) for cmd in ("pdfinfo", "pdftoppm", "tesseract")
    )
    if not all((pdfinfo, rasterizer, engine)):
        raise FileNotFoundError("OCR backend absent")
    version_process = subprocess.run(
        [engine, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=4,
    )
    if version_process.returncode:
        raise RuntimeError("OCR engine version unavailable")
    version_lines = (
        (version_process.stdout or version_process.stderr)
        .decode("utf-8", "strict")
        .splitlines()
    )
    version = version_lines[0].strip() if version_lines else ""
    if not re.fullmatch(r"tesseract [0-9][0-9A-Za-z.+-]{1,55}", version):
        raise RuntimeError("Unrecognized OCR engine version")
    with tempfile.TemporaryDirectory(prefix="dp238-private-ocr-") as tmp:
        source = os.path.join(tmp, "input.pdf")
        fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
        info = _run([pdfinfo, source], timeout=8).decode("utf-8", "replace")
        encrypted = re.search(r"^Encrypted:\s*(\S+)", info, re.M | re.I)
        if not encrypted or encrypted.group(1).lower() != "no":
            raise PermissionError("PDF encrypted or encryption unclear")
        # Poppler's own flags provide an additional conservative hold on
        # script/action-bearing or suspect documents before any renderer runs.
        for field, accepted in (
            ("JavaScript", "no"),
            ("Form", "none"),
            ("Suspects", "no"),
        ):
            observed = re.search(rf"^{field}:\s*(\S+)", info, re.M | re.I)
            if not observed or observed.group(1).casefold() != accepted:
                raise PermissionError("PDF active or unsupported metadata")
        pages = re.search(r"^Pages:\s*(\d+)\s*$", info, re.M)
        if not pages:
            raise ValueError("PDF page count absent")
        count = int(pages.group(1))
        if count < 1 or count > MAX_OCR_PAGES:
            raise OverflowError("PDF page limit")
        result = []
        total_words = 0
        for page_number in range(1, count + 1):
            raster = _run(
                [
                    rasterizer,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-singlefile",
                    "-r",
                    "120",
                    "-scale-to",
                    "2500",
                    "-gray",
                    "-png",
                    source,
                ],
                timeout=12,
            )
            if len(raster) < 24 or raster[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("Missing raster page")
            pixels = [
                int.from_bytes(raster[16:20], "big"),
                int.from_bytes(raster[20:24], "big"),
            ]
            if any(not 1 <= dimension <= 2500 for dimension in pixels):
                raise OverflowError("Raster dimension limit")
            tsv = _run(
                [engine, "stdin", "stdout", "-l", "ita+eng", "--psm", "3", "tsv"],
                input_bytes=raster,
                timeout=12,
            ).decode("utf-8", "strict")
            rows = csv.DictReader(io.StringIO(tsv), delimiter="\t")
            lines: dict[tuple[int, int, int], list[tuple[str, list[int]]]] = {}
            for row in rows:
                if row.get("level") != "5":
                    continue
                token = str(row.get("text", "")).strip()
                if not token:
                    continue
                if any(ord(c) < 32 for c in token):
                    raise ValueError("Invalid OCR character")
                confidence = float(row["conf"])
                if not math.isfinite(confidence) or not 0 <= confidence <= 100:
                    raise ValueError("Invalid OCR confidence")
                group = tuple(int(row[k]) for k in ("block_num", "par_num", "line_num"))
                x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
                if (
                    not 0 <= x < pixels[0]
                    or not 0 <= y < pixels[1]
                    or not 0 < w <= pixels[0] - x
                    or not 0 < h <= pixels[1] - y
                ):
                    raise ValueError("OCR box outside page")
                lines.setdefault(group, []).append(
                    (token, [x, y, w, h, int(confidence)])
                )
                total_words += 1
                if total_words > MAX_OCR_WORDS:
                    raise OverflowError("OCR word limit")
            chunks = []
            words = []
            offset = 0
            for group in sorted(lines):
                if chunks:
                    offset += 1
                line_words = []
                for token, location in lines[group]:
                    if line_words:
                        offset += 1
                    words.append([offset, offset + len(token), *location])
                    line_words.append(token)
                    offset += len(token)
                chunks.append(" ".join(line_words))
            text = "\n".join(chunks)
            if not text.strip():
                raise EOFError("Empty scanned page")
            result.append({"text": text, "pixels": pixels, "words": words})
        return {"status": "SUCCEEDED", "engine": version, "pages": result}


def _worker() -> None:
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (55, 60))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
        except (OSError, ValueError):
            pass
        body = sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1)
        if len(body) > MAX_DOCUMENT_BYTES:
            code = "DOCUMENT_OCR_COMPLEXITY_LIMIT"
        else:
            payload = _extract_ocr_pages(body)
            encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            if (
                len(encoded) > MAX_WORKER_OUTPUT
                or sum(len(p["text"]) for p in payload["pages"]) > MAX_PARSED_TEXT_CHARS
            ):
                code = "DOCUMENT_OCR_COMPLEXITY_LIMIT"
            else:
                sys.stdout.write(encoded)
                return
    except FileNotFoundError:
        code = "DOCUMENT_OCR_BACKEND_UNAVAILABLE"
    except PermissionError:
        code = "DOCUMENT_PDF_UNSUPPORTED"
    except OverflowError:
        code = "DOCUMENT_OCR_PAGE_LIMIT"
    except EOFError:
        code = "DOCUMENT_INCOMPLETE_PAGE"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, RuntimeError):
        code = "DOCUMENT_OCR_PROCESS_FAILED"
    except Exception:
        code = "DOCUMENT_PDF_CORRUPT"
    sys.stdout.write(json.dumps({"status": "FAILED", "code": code}))


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()


__all__ = ["OCR_PROFILE", "OCR_VERSION", "ScannedPDFOCRParser"]
