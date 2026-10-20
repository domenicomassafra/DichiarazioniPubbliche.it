"""DP-237: conservative, private browser jumps from already verified locators.

This module never retrieves, approves or publishes a Capture. The caller must
first resolve the exact quote against its immutable bytes and separately check
the current URL bytes. Browsers may ignore text fragments; PDF jumps identify
the page, not an exact pixel box or an independently reviewed quotation.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import asdict, dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord
from dichiarazioni_pubbliche.original_source_resolver import (
    EXACT_SOURCE_LOCATOR_VERSION,
    ExactSourceLocator,
    ExactSourceLocatorResolution,
    OriginalSourceResolution,
)

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_HOST = re.compile(r"(?=.{4,253}\Z)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z", re.IGNORECASE)


@dataclass(frozen=True)
class PrivateSourceJump:
    status: str  # READY_PAGE, BEST_EFFORT_TEXT, UNAVAILABLE
    reason: str
    url: str | None
    precision: str | None
    capture_sha256: str | None


def _safe_external_url(value: object) -> str | None:
    """Accept ordinary public HTTPS links, with no local endpoint or URL secret."""
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(ord(c) < 33 for c in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not host
        or not _HOST.fullmatch(host)
        or "." not in host
        or not host.rsplit(".", 1)[1].isalpha()
        or len(host.rsplit(".", 1)[1]) < 2
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or "\\" in value
        or "@" in host
        or ".." in host
    ):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    if host.startswith("localhost.") or host.endswith(
        (".localhost", ".local", ".internal")
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def private_written_source_jump(
    *,
    locator: ExactSourceLocator,
    resolution: ExactSourceLocatorResolution,
    capture: ContentCaptureRecord,
    observed_live_sha256: str | None,
    observed_live_url: str | None,
    original_source: OriginalSourceResolution,
    quote_text: str,
    verified_document_pages: list[dict[str, object]] | None = None,
) -> PrivateSourceJump:
    """Propose a navigable page or browser text fragment, never an authority grant.

    `observed_live_sha256` and `observed_live_url` identify one independently
    retrieved HTTPS response at the captured original address. `original_source`
    must come from the approved original/derivation family resolver. If the
    original is a local/derived OCR crop, the external URL's different hash
    deliberately prevents a forged exact jump to the full parent document.
    """

    def unavailable(reason: str) -> PrivateSourceJump:
        return PrivateSourceJump(
            "UNAVAILABLE", reason, None, None, capture.content_sha256
        )

    expected_fingerprint = hashlib.sha256(
        json.dumps(
            {"version": EXACT_SOURCE_LOCATOR_VERSION, "locator": asdict(locator)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if (
        resolution.status != "LOCATED"
        or not resolution.locator_fingerprint
        or resolution.locator_fingerprint != expected_fingerprint
        or resolution.content_id != locator.content_id
        or resolution.passage_id != locator.passage_id
        or resolution.selector_type != locator.selector_type
    ):
        return unavailable("EXACT_LOCATOR_NOT_VERIFIED")
    if (
        locator.capture_id != capture.id
        or locator.content_id != capture.content_id
        or locator.capture_sha256 != capture.content_sha256
        or resolution.source_version_sha256 != capture.content_sha256
    ):
        return unavailable("CAPTURE_VERSION_MISMATCH")
    if (
        not isinstance(original_source, OriginalSourceResolution)
        or original_source.content_id != locator.content_id
        or original_source.status != "SELF_ORIGINAL"
        or original_source.root_content_id != locator.content_id
        or original_source.path_content_ids != (locator.content_id,)
        or original_source.path_edge_ids
        or original_source.blockers
    ):
        return unavailable("REVIEWED_ORIGINAL_SOURCE_NOT_VERIFIED")
    if (
        not isinstance(observed_live_sha256, str)
        or not _SHA.fullmatch(observed_live_sha256)
        or observed_live_sha256 != capture.content_sha256
    ):
        return unavailable("LIVE_SOURCE_VERSION_UNCONFIRMED")
    if (
        capture.status != "CAPTURED"
        or capture.hold_status != "NONE"
        or capture.rights_status != "CLEARED"
        or capture.body_ref is None
    ):
        return unavailable("CAPTURE_NOT_AVAILABLE")
    origin = _safe_external_url(capture.final_url)
    if origin is None:
        return unavailable("SOURCE_URL_NOT_SAFE_FOR_NAVIGATION")
    if _safe_external_url(observed_live_url) != origin:
        return unavailable("LIVE_SOURCE_URL_MISMATCH")
    if locator.selector_type == "PAGE_RANGE":
        if (
            capture.media_type != "application/pdf"
            or type(locator.page_number) is not int
            or locator.page_number < 1
            or type(capture.metadata.get("page_count")) is not int
            or locator.page_number > capture.metadata["page_count"]
        ):
            return unavailable("PDF_PAGE_NOT_VERIFIED")
        return PrivateSourceJump(
            "READY_PAGE",
            "PDF_PAGE_ONLY",
            f"{origin}#page={locator.page_number}",
            "PAGE",
            capture.content_sha256,
        )
    if locator.selector_type == "TEXT_POSITION" and capture.media_type == "application/pdf":
        # DP-238 stores exact extracted-character offsets and original PDF page
        # selectors in one private Passage. A PDF page is navigable only after
        # the source bytes and independently replayed page map have matched.
        source = capture.metadata.get("source_metadata")
        if (
            capture.parser_method not in {
                "NATIVE_PDF_TEXT_CANDIDATE", "SCANNED_PDF_OCR_CANDIDATE"
            }
            or not isinstance(source, dict)
            or source.get("source_sha256") != capture.content_sha256
            or type(source.get("page_count")) is not int
            or not isinstance(verified_document_pages, list)
            or source.get("page_selectors") != verified_document_pages
            or len(verified_document_pages) != source["page_count"]
            or not isinstance(quote_text, str)
            or hashlib.sha256(quote_text.encode("utf-8")).hexdigest()
            != locator.quote_sha256
        ):
            return unavailable("PDF_TEXT_PAGE_NOT_VERIFIED")
        matches = [
            page for page in verified_document_pages
            if isinstance(page, dict)
            and type(page.get("page_number")) is int
            and type(page.get("start_char")) is int
            and type(page.get("end_char")) is int
            and page["page_number"] >= 1
            and page["page_number"] <= source["page_count"]
            and isinstance(page.get("page_text_sha256"), str)
            and _SHA.fullmatch(page["page_text_sha256"])
            and page["start_char"] <= locator.quote_start
            < locator.quote_end <= page["end_char"]
        ]
        if len(matches) != 1:
            return unavailable("PDF_TEXT_PAGE_NOT_VERIFIED")
        return PrivateSourceJump(
            "READY_PAGE", "PDF_PAGE_ONLY",
            f"{origin}#page={matches[0]['page_number']}", "PAGE",
            capture.content_sha256,
        )
    if locator.selector_type == "TEXT_POSITION":
        # Browser text-fragment directives are deliberately labelled best effort:
        # the DOM may not expose the parser's canonicalized original characters.
        if (
            not isinstance(quote_text, str)
            or not 1 <= len(quote_text) <= 160
            or any(ord(c) < 32 for c in quote_text)
            or hashlib.sha256(quote_text.encode("utf-8")).hexdigest()
            != locator.quote_sha256
            or capture.media_type
            not in {"text/html", "application/xhtml+xml", "text/plain"}
        ):
            return unavailable("TEXT_FRAGMENT_UNSUPPORTED")
        return PrivateSourceJump(
            "BEST_EFFORT_TEXT",
            "BROWSER_TEXT_FRAGMENT_UNCONFIRMED",
            f"{origin}#:~:text={quote(quote_text, safe='')}",
            "BROWSER_TEXT_FRAGMENT",
            capture.content_sha256,
        )
    return unavailable("SELECTOR_NOT_NAVIGABLE")


__all__ = ["PrivateSourceJump", "private_written_source_jump"]
