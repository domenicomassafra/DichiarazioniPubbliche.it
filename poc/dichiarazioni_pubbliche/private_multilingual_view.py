"""DP-239 opt-in, rights-checked private original / Italian derivative reader.

The independently stored Capture and Passage are the authority for source words.
No view produced here grants translation review or public quotation rights.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord
from dichiarazioni_pubbliche.multilingual_derivation import (
    ImmutableOriginalReadback,
    PrivateTranslationDerivation,
    read_immutable_original_consumer,
    read_private_translation_consumer,
)
from dichiarazioni_pubbliche.private_capture_rights import (
    SourceFamilyUseGuard,
    SourceUseBlocked,
)
from dichiarazioni_pubbliche.original_source_resolver import ExactSourceLocator


@dataclass(frozen=True)
class PrivateMultilingualView:
    status: str  # CURRENT_ORIGINAL / CURRENT_HELD / STALE / BLOCKED
    reason_codes: tuple[str, ...]
    source_url: str | None = None
    content_id: str | None = None
    passage_id: str | None = None
    original_text: str | None = None
    original_language: str | None = None
    original_quote_sha256: str | None = None
    source_version_sha256: str | None = None
    original_selector: str | None = None
    translated_text: str | None = None
    translated_language: str | None = None
    translation_id: str | None = None
    translation_method: str | None = None
    translation_reviewed: bool = False
    public_quote_eligible: bool = False


def read_private_multilingual_view(
    passage_id: str,
    *,
    originals_by_passage: Mapping[str, ImmutableOriginalReadback],
    current_versions_by_content: Mapping[str, str],
    rights_guard: SourceFamilyUseGuard,
    translation: PrivateTranslationDerivation | None = None,
) -> PrivateMultilingualView:
    """Read original independently, display its source, optionally show held IT.

    The rights guard must be backed by a current, independently reviewed exact
    artifact record. Rights checks are repeated for every access. Source URI is
    read from the original Capture, never from the translation payload.
    """
    def blocked(code: str) -> PrivateMultilingualView:
        return PrivateMultilingualView("BLOCKED", (code,))

    if not isinstance(originals_by_passage, Mapping) or not isinstance(
        current_versions_by_content, Mapping
    ) or not isinstance(rights_guard, SourceFamilyUseGuard):
        return blocked("DP239_PRIVATE_SOURCE_RIGHTS_REQUIRED")
    row = originals_by_passage.get(passage_id)
    if (not isinstance(row, ImmutableOriginalReadback)
            or not isinstance(row.locator, ExactSourceLocator)
            or not isinstance(row.passage, PassageRecord)
            or not isinstance(row.capture, ContentCaptureRecord)):
        # A media segment without its independently pinned Capture URL is not
        # a sufficient visible source reference. Add that binding before use.
        return blocked("DP239_SOURCE_CAPTURE_REFERENCE_UNAVAILABLE")
    locator, capture = row.locator, row.capture
    if (not isinstance(capture.final_url, str) or not capture.final_url.startswith(
        ("https://", "http://")
    ) or capture.content_id != locator.content_id):
        return blocked("DP239_SOURCE_URL_INVALID")
    try:
        rights_guard.bind_capture(content_id=locator.content_id, url=capture.final_url)
        rights_guard.bind_fetched(final_url=capture.final_url)
        for use in ("FETCH", "STORE_BODY", "PARSE_TEXT"):
            rights_guard.require(use, content_sha256=capture.content_sha256)
        if translation is not None:
            rights_guard.require("TRANSLATE", content_sha256=capture.content_sha256)
    except SourceUseBlocked as exc:
        return blocked(exc.code)
    original = read_immutable_original_consumer(
        passage_id, originals_by_passage=originals_by_passage,
        current_versions_by_content=current_versions_by_content,
    )
    if original.status == "BLOCKED":
        return blocked(original.reason_codes[0])
    if not isinstance(row.passage.language, str) or not row.passage.language:
        # 'und' remains an explicit supported original-language label.
        return blocked("DP239_ORIGINAL_LANGUAGE_UNBOUND")
    base = dict(
        source_url=capture.final_url,
        content_id=locator.content_id,
        passage_id=passage_id,
        original_text=original.original_text,
        original_language=row.passage.language,
        original_quote_sha256=original.quote_sha256,
        source_version_sha256=original.source_version_sha256,
        original_selector=locator.selector_type,
    )
    if original.status == "STALE":
        return PrivateMultilingualView("STALE", original.reason_codes, **base)
    if translation is None:
        return PrivateMultilingualView("CURRENT_ORIGINAL", (), **base)
    if (not isinstance(translation, PrivateTranslationDerivation)
            or not isinstance(translation.target_language, str)
            or translation.target_language.split("-", 1)[0] != "it"):
        return blocked("DP239_DERIVATIVE_NOT_ITALIAN")
    derivative = read_private_translation_consumer(
        translation, originals_by_passage=originals_by_passage,
        current_versions_by_content=current_versions_by_content,
    )
    if derivative.status != "CURRENT_HELD":
        return blocked(derivative.reason_codes[0] if derivative.reason_codes else "DP239_DERIVATIVE_UNAVAILABLE")
    if derivative.original_sha256 != original.quote_sha256 or derivative.original_text != original.original_text:
        return blocked("DP239_DERIVATIVE_ORIGINAL_BINDING_CHANGED")
    return PrivateMultilingualView(
        "CURRENT_HELD", (), **base,
        translated_text=derivative.translation_text,
        translated_language=translation.target_language,
        translation_id=derivative.translation_id,
        translation_method=derivative.method,
    )


__all__ = ["PrivateMultilingualView", "read_private_multilingual_view"]
