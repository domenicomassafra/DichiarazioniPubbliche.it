#!/usr/bin/env python3
"""Private, source-pinned DP238 real-scan OCR gold and Passage readback.

The BHL WebP is the real scanned page. The PDF produced here is explicitly a
local image-only *derivative*. The IMPACT-BHL PAGE XML is an earlier, separately
expert-corrected transcription, not text produced by the OCR under evaluation.
This is an isolated technical canary, not an operational rights-registry grant.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord
from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
from dichiarazioni_pubbliche.document_text_extraction import document_passages_from_capture
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/dp238_bhl_8992356_gold_v1.json").read_text())
GOLD_TEXT_SHA256 = "24f0fcd6ed46aa20ed7658833606a7bf318921df7e80e7ce571aa5205881a039"
PAGE_URL = "https://www.biodiversitylibrary.org/page/8992356"


def sha(body: bytes | str) -> str:
    return hashlib.sha256(body.encode("utf-8") if isinstance(body, str) else body).hexdigest()


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def distance(a: list[str] | str, b: list[str] | str) -> int:
    """Levenshtein distance; gold is always the denominator."""
    previous = list(range(len(b) + 1))
    for i, token in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            current.append(min(current[j - 1] + 1, previous[j] + 1,
                               previous[j - 1] + (token != other)))
        previous = current
    return previous[-1]


def render_image_only_pdf(image_bytes: bytes) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as original:
        derived = io.BytesIO()
        # Pillow defaults PDF CreationDate/ModDate to the clock, changing
        # Capture identity for identical source pixels on every replay.
        fixed_date = time.struct_time((1970, 1, 1, 0, 0, 0, 3, 1, 0))
        original.convert("RGB").save(
            derived, "PDF", resolution=120.0,
            creationDate=fixed_date, modDate=fixed_date,
        )
    return derived.getvalue()


def checked_inputs(scan: Path, gold: Path):
    from PIL import Image

    provenance = FIXTURE["provenance"]
    image_bytes, xml_bytes = scan.read_bytes(), gold.read_bytes()
    if (sha(image_bytes) != provenance["raster_sha256"]
            or len(image_bytes) != provenance["raster_bytes"]
            or sha(xml_bytes) != provenance["gold_sha256"]
            or len(xml_bytes) != provenance["gold_bytes"]):
        raise ValueError("DP356_PINNED_SOURCE_OR_INDEPENDENT_GOLD_MISMATCH")
    tree = ET.fromstring(xml_bytes)
    page = tree.find(".//{*}Page")
    if page is None or (int(page.attrib["imageWidth"]), int(page.attrib["imageHeight"])) != tuple(provenance["raster_pixels"]):
        raise ValueError("DP356_GOLD_PAGE_GEOMETRY_MISMATCH")
    regions = page.findall("{*}TextRegion")
    lines = [r.find("{*}TextEquiv/{*}Unicode") for r in regions]
    if len(regions) != 81 or any(line is None or line.text is None for line in lines):
        raise ValueError("DP356_GOLD_REGION_STRUCTURE_MISMATCH")
    gold_text = "\n\n".join(line.text for line in lines)
    if sha(gold_text) != GOLD_TEXT_SHA256:
        raise ValueError("DP356_INDEPENDENT_TRANSCRIPTION_MISMATCH")
    for target in FIXTURE["critical_gold"]:
        if normalize(target["expected"]) not in normalize(gold_text):
            raise ValueError("DP356_GOLD_CRITICAL_SPAN_MISSING")

    with Image.open(io.BytesIO(image_bytes)) as original:
        if original.format != "WEBP" or original.size != tuple(provenance["raster_pixels"]):
            raise ValueError("DP356_SCANNED_IMAGE_GEOMETRY_MISMATCH")
    pdf = render_image_only_pdf(image_bytes)
    if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-1024:]:
        raise ValueError("DP356_PDF_DERIVATION_INVALID")
    return pdf, gold_text


def compare(parsed_text: str, gold_text: str) -> dict[str, object]:
    reference, predicted = normalize(gold_text), normalize(parsed_text)
    reference_words, predicted_words = reference.split(), predicted.split()
    cer = 100 * distance(reference, predicted) / len(reference)
    wer = 100 * distance(reference_words, predicted_words) / len(reference_words)
    critical = {}
    for target in FIXTURE["critical_gold"]:
        expected = normalize(target["expected"])
        if expected.isdigit():
            found = expected in re.findall(r"\b\d+\b", predicted)
        else:
            found = expected in predicted
        critical[target["id"]] = found
    limits = FIXTURE["predeclared_experimental_limits"]
    quality_pass = (cer <= limits["character_error_rate_max_percent"]
                    and wer <= limits["word_error_rate_max_percent"]
                    and all(critical.values()))
    return {
        "gold_characters": len(reference), "gold_words": len(reference_words),
        "ocr_characters": len(predicted), "ocr_words": len(predicted_words),
        "cer_percent": round(cer, 4), "wer_percent": round(wer, 4),
        "critical_exact": critical, "quality_pass": quality_pass,
        "verdict": "TECHNICAL_GOLD_PASS_RIGHTS_HOLD" if quality_pass else "HOLD_PRIVATE_GOLD_FAILURE",
    }


def run(scan: Path, gold: Path, storage: Path) -> dict[str, object]:
    pdf, gold_text = checked_inputs(scan, gold)
    digest = sha(pdf)
    content_id = "content:dp356:bhl-page-8992356-local-pdf-derivative"
    capture_id = "capture:dp356:" + digest[:24]
    fetched = FetchedBytes(body=pdf, final_url=PAGE_URL, status_code=200,
                           media_type="application/pdf", charset=None,
                           content_length=len(pdf))
    parser = ScannedPDFOCRParser()
    result: dict[str, object] = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "PRIVATE_TECHNICAL_ONLY", "publication_authority": False,
        "source_use_current_operational_record": False,
        "source_rights": "BHL_VOLUME_2_NOT_IN_COPYRIGHT",
        "gold_license": "CC-BY-3.0_IMPACT_BHL_ATTRIBUTION_REQUIRED",
        "original_scan_url": FIXTURE["provenance"]["raster_url"],
        "original_scan_sha256": FIXTURE["provenance"]["raster_sha256"],
        "independent_page_xml_sha256": FIXTURE["provenance"]["gold_sha256"],
        "independent_transcription_sha256": GOLD_TEXT_SHA256,
        "derivation": "LOCAL_PILLOW_IMAGE_ONLY_PDF_NOT_ORIGINAL_BHL_PDF",
        "derived_pdf_sha256": digest, "derived_pdf_bytes": len(pdf),
        "capture_id": capture_id, "content_id": content_id,
        "consumer": "native-dp238-scanned-pdf-ocr-private-passage-v1",
    }
    started = time.monotonic()
    parsed = parser.parse(fetched)
    result["ocr_elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["ocr_status"] = parsed.status
    if parsed.status != "SUCCEEDED":
        result.update(verdict="HOLD_OCR_UNAVAILABLE", ocr_error=parsed.error_category,
                      page_count=0, passage_count=0)
        return result
    if (parsed.metadata["source_sha256"] != digest
            or parsed.metadata["page_count"] != 1
            or parsed.metadata["page_selectors"][0]["page_number"] != 1):
        raise ValueError("DP356_NATIVE_PAGE_LOCATOR_MISMATCH")
    stored = CaptureBodyStore(storage).write(capture_id=capture_id, body=pdf, content_sha256=digest)
    reopened = CaptureBodyStore(storage).read(stored.body_ref, expected_sha256=digest)
    if reopened != pdf:
        raise ValueError("DP356_PRIVATE_CAPTURE_READBACK_MISMATCH")
    cap = ContentCaptureRecord(
        id=capture_id, content_id=content_id,
        observed_at=datetime.now(timezone.utc).isoformat(), final_url=PAGE_URL,
        media_type="application/pdf", content_sha256=digest,
        retrieval_method="LOCAL_DERIVATION_FROM_AUTHENTIC_BHL_WEBP",
        retrieval_version="dp356-pillow-image-only-pdf-v1",
        parser_method=parsed.parser_method, parser_version=parsed.parser_version,
        rights_status="CLEARED", retention_class="DURABLE_PRIVATE",
        body_ref=stored.body_ref,
        metadata={"parse_status": "SUCCEEDED", "source_metadata": parsed.metadata,
                  "original_webp_sha256": FIXTURE["provenance"]["raster_sha256"],
                  "technical_only": True},
    )
    # This public seam performs its own native re-extraction, so the returned
    # Passages cannot be substituted from the benchmark's expected text.
    replay_started = time.monotonic()
    try:
        passages = document_passages_from_capture(
            capture=cap, fetched=replace(fetched, body=reopened),
            parsed=parsed, parser=parser, language="en",
        )
    except ValueError as error:
        if str(error) != "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH":
            raise
        # An independently rerun native worker can time out even after the
        # first run succeeded. That is a held replay, never accepted evidence.
        result.update(verdict="HOLD_OCR_REPLAY_UNAVAILABLE", page_count=1,
                      passage_count=0, private_body_readback=True,
                      replay_elapsed_seconds=round(time.monotonic() - replay_started, 3),
                      replay_error="DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH")
        return result
    result["replay_elapsed_seconds"] = round(time.monotonic() - replay_started, 3)
    if not passages or any(
        p.metadata["page_number"] != 1
        or p.metadata["source_sha256"] != digest
        or p.metadata["page_text_sha256"] != parsed.metadata["page_selectors"][0]["page_text_sha256"]
        or p.metadata["verbatim_reviewed"] is not False
        or p.metadata["ocr_critical_span_state"] != "HELD_INDEPENDENT_REVIEW_REQUIRED"
        or parsed.canonical_text[p.start_char:p.end_char] != p.private_text
        or sha(p.private_text) != p.text_sha256
        for p in passages
    ):
        raise ValueError("DP356_PAGE_PASSAGE_HASH_READBACK_FAILED")
    try:
        document_passages_from_capture(
            capture=cap, fetched=replace(fetched, body=pdf + b"\n", content_length=len(pdf) + 1),
            parsed=parsed, parser=parser, language="en",
        )
    except ValueError as error:
        if str(error) != "DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH":
            raise
    else:
        raise ValueError("DP356_CHANGED_DERIVATIVE_NOT_REJECTED")
    result.update(compare(parsed.canonical_text, gold_text))
    result.update(
        page_count=1, page_locator=parsed.metadata["page_selectors"][0],
        page_text_sha256=parsed.metadata["page_selectors"][0]["page_text_sha256"],
        passage_count=len(passages), passage_ids=[p.id for p in passages],
        passage_sha256=[p.text_sha256 for p in passages],
        passage_locators=[{
            "id": p.id, "page_number": p.metadata["page_number"],
            "selector_type": p.selector_type, "start_char": p.start_char,
            "end_char": p.end_char, "text_sha256": p.text_sha256,
        } for p in passages],
        ocr_word_boxes_sha256=sha(json.dumps(
            parsed.metadata["ocr_word_boxes"], sort_keys=True, separators=(",", ":"),
        )),
        private_body_readback=True, changed_source_rejected=True,
        ocr_word_count=parsed.metadata["ocr_word_count"],
        ocr_engine_version=parsed.metadata["ocr_engine_version"],
        verbatim_reviewed=False,
    )
    return result


def main() -> int:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--scan", required=True, type=Path)
    arg.add_argument("--gold-xml", required=True, type=Path)
    arg.add_argument("--private-store", required=True, type=Path)
    arg.add_argument("--receipt", type=Path)
    options = arg.parse_args()
    receipt = run(options.scan, options.gold_xml, options.private_store)
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if options.receipt:
        if options.receipt.exists() and options.receipt.is_symlink():
            raise ValueError("DP356_RECEIPT_SYMLINK_DISALLOWED")
        options.receipt.write_text(rendered)
        options.receipt.chmod(0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
