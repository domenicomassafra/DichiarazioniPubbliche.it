"""Authenticated private Studio source jump from a persisted, reviewed quote.

One collection-scoped PostgreSQL snapshot, a read-only Capture body and an
independent bounded HTTPS observation are needed. Never returns private text.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import fields
from typing import Protocol

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
)
from dichiarazioni_pubbliche.document_text_extraction import DocumentTextParser
from dichiarazioni_pubbliche.original_source_resolver import (
    ExactSourceLocator,
    resolve_exact_source_locator,
    resolve_reviewed_original_source,
)
from dichiarazioni_pubbliche.private_source_jump import (
    _safe_external_url,
    private_written_source_jump,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes, fetch_bytes

_REF = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
STUDIO_EXACT_JUMP_VERSION = "studio-exact-source-jump-v1"
MAX_SOURCE_BYTES = 1_048_576

_SNAPSHOT_SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object(
 'source_id', item.source_id, 'content_rights', item.rights_status,
 'collection_status', collection.status,
 'rights_leaf_count', (
   SELECT count(*) FROM private_source_rights_record rr
   WHERE rr.content_id=item.id
     AND NOT EXISTS (SELECT 1 FROM private_source_rights_record next
                     WHERE next.supersedes_id=rr.id)
 ),
 'rights_ready', (
   SELECT coalesce(rr.rights_status='CLEARED'
     AND rr.rights_receipt_ref IS NOT NULL
     AND rr.reviewed_at IS NOT NULL AND rr.reviewer_ref IS NOT NULL
     AND rr.expires_at>current_timestamp
     AND rr.locator_kind='URL' AND rr.locator_value=capture.final_url
     AND rr.evidence_id IS NULL AND rr.passage_id IS NULL
     AND rr.transcript_segment_id IS NULL AND rr.canonical_segment_id IS NULL
     AND rr.permitted_uses @> (CASE
       WHEN capture.parser_method='SCANNED_PDF_OCR_CANDIDATE'
         THEN ARRAY['FETCH','STORE_BODY','PARSE_OCR']::text[]
       ELSE ARRAY['FETCH','STORE_BODY','PARSE_TEXT']::text[] END),false)
   FROM private_source_rights_record rr
   WHERE rr.content_id=item.id
     AND NOT EXISTS (SELECT 1 FROM private_source_rights_record next
                     WHERE next.supersedes_id=rr.id)
   ORDER BY rr.id LIMIT 1
 ),
 'capture', row_to_json(capture), 'passage', row_to_json(passage),
 'families', (
   SELECT coalesce(json_agg(json_build_object(
     'id', family.id, 'root_content_id', family.root_content_id,
     'status', family.status) ORDER BY family.id), '[]'::json)
   FROM content_derivation_family family
   WHERE family.status='APPROVED'
     AND (family.root_content_id=item.id OR EXISTS (
       SELECT 1 FROM content_derivation_candidate edge
       WHERE edge.family_id=family.id
         AND (edge.derived_content_id=item.id OR edge.origin_content_id=item.id)))
 ),
 'edges', (
   SELECT coalesce(json_agg(json_build_object(
     'id', edge.id, 'family_id', edge.family_id,
     'derived_content_id', edge.derived_content_id,
     'origin_content_id', edge.origin_content_id,
     'relation_type', edge.relation_type, 'status', edge.status)
     ORDER BY edge.id), '[]'::json)
   FROM content_derivation_candidate edge
   JOIN content_derivation_family family ON family.id=edge.family_id
   WHERE family.status='APPROVED' AND edge.status='APPROVED'
     AND (family.root_content_id=item.id
       OR edge.derived_content_id=item.id OR edge.origin_content_id=item.id)
 )
)::text
FROM research_collection_content member
JOIN research_collection collection ON collection.id=member.collection_id
JOIN content_item item ON item.id=member.content_id
JOIN source source ON source.id=item.source_id
JOIN content_capture capture
  ON capture.id=:'capture_id' AND capture.content_id=item.id
JOIN passage passage ON passage.id=:'passage_id'
  AND passage.content_id=item.id AND passage.capture_id=capture.id
WHERE member.collection_id=:'collection_id'
  AND member.content_id=:'content_id' AND member.status='INCLUDED';
COMMIT;
""".strip()


class _SnapshotReader(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


def _model(cls: type, data: object):
    if not isinstance(data, dict):
        raise TypeError("STUDIO_EXACT_PERSISTED_ROW_INVALID")
    return cls(**{field.name: data[field.name] for field in fields(cls) if field.name in data})


def read_studio_exact_source_jump(
    reader: _SnapshotReader,
    body_store: CaptureBodyStore,
    *,
    collection_id: str,
    content_id: str,
    capture_id: str,
    passage_id: str,
    quote_start: int | None = None,
    quote_end: int | None = None,
    quote_sha256: str | None = None,
    quote_text: str | None = None,
    fetch: Callable[..., FetchedBytes] = fetch_bytes,
) -> dict[str, object]:
    """Return only a safe viewer link, or an explicit refusal with no link."""
    if any(not isinstance(ref, str) or not _REF.fullmatch(ref) or ".." in ref
           for ref in (collection_id, content_id, capture_id, passage_id)):
        raise ValueError("STUDIO_EXACT_REF_INVALID")
    if quote_text is None:
        if (type(quote_start) is not int or type(quote_end) is not int
                or not 0 <= quote_start < quote_end <= 1_048_576
                or not isinstance(quote_sha256, str) or not _SHA.fullmatch(quote_sha256)):
            raise ValueError("STUDIO_EXACT_QUOTE_INVALID")
    elif (any(value is not None for value in (quote_start, quote_end, quote_sha256))
          or not isinstance(quote_text, str) or not 1 <= len(quote_text) <= 160
          or any(ord(c) < 32 for c in quote_text)):
        raise ValueError("STUDIO_EXACT_QUOTE_INVALID")

    def refuse(reason: str) -> dict[str, object]:
        return {
            "contract_version": STUDIO_EXACT_JUMP_VERSION,
            "private_only": True, "publication_authority": False,
            "rights_clearance": False, "status": "UNAVAILABLE",
            "reason": reason, "url": None, "precision": None,
        }

    if not isinstance(body_store, CaptureBodyStore):
        return refuse("PRIVATE_CAPTURE_BODY_STORE_NOT_CONFIGURED")
    raw = reader.run(
        _SNAPSHOT_SQL, collection_id=collection_id, content_id=content_id,
        capture_id=capture_id, passage_id=passage_id,
    )
    if not raw:
        return refuse("PERSISTED_COLLECTION_SOURCE_NOT_FOUND")
    try:
        row = json.loads(raw)
        if (not isinstance(row, dict) or set(row) != {
            "source_id", "content_rights", "collection_status",
            "rights_leaf_count", "rights_ready", "capture", "passage", "families", "edges",
        } or not isinstance(row["families"], list)
                or not isinstance(row["edges"], list)):
            raise ValueError("STUDIO_EXACT_SNAPSHOT_INVALID")
        capture = _model(ContentCaptureRecord, row["capture"])
        passage = _model(PassageRecord, row["passage"])
    except (ValueError, TypeError, KeyError):
        return refuse("PERSISTED_SOURCE_SNAPSHOT_INVALID")
    if (capture.id != capture_id or capture.content_id != content_id
            or passage.id != passage_id or passage.content_id != content_id
            or passage.capture_id != capture_id or row["content_rights"] != "CLEARED"
            or row["collection_status"] != "ACTIVE"
            or row["rights_leaf_count"] != 1 or row["rights_ready"] is not True
            or not isinstance(row["source_id"], str)
            or not _REF.fullmatch(row["source_id"])):
        return refuse("SOURCE_BINDING_OR_RIGHTS_INVALID")
    if passage.selector_type == "MEDIA_SEGMENT_REF":
        return refuse("MEDIA_PLAYER_SEEK_UNAVAILABLE")
    if (capture.status != "CAPTURED" or capture.hold_status != "NONE"
            or capture.rights_status != "CLEARED" or not capture.body_ref):
        return refuse("CAPTURE_RIGHTS_OR_BODY_BLOCKED")
    if quote_text is not None:
        persisted = passage.private_text
        if (not isinstance(persisted, str) or persisted.count(quote_text) != 1):
            return refuse("QUOTE_NOT_UNIQUE_IN_PASSAGE")
        offset = persisted.index(quote_text)
        quote_start = (passage.start_char + offset
                       if passage.selector_type == "TEXT_POSITION" and type(passage.start_char) is int
                       else offset)
        quote_end = quote_start + len(quote_text)
        quote_sha256 = hashlib.sha256(quote_text.encode("utf-8")).hexdigest()

    origin = resolve_reviewed_original_source(
        content_id, families=row["families"], edges=row["edges"],
    )
    if (origin.status != "SELF_ORIGINAL" or origin.root_content_id != content_id
            or any(isinstance(edge, dict) and edge.get("derived_content_id") == content_id
                   for edge in row["edges"])):
        return refuse("REVIEWED_ORIGINAL_SOURCE_NOT_VERIFIED")
    if _safe_external_url(capture.final_url) is None:
        return refuse("SOURCE_URL_NOT_SAFE_FOR_NAVIGATION")
    try:
        saved = body_store.read(
            capture.body_ref, expected_sha256=capture.content_sha256,
            max_bytes=MAX_SOURCE_BYTES,
        )
    except (OSError, ValueError, RuntimeError):
        return refuse("CAPTURE_BODY_UNAVAILABLE")

    if capture.parser_method == DocumentTextParser.parser_method:
        parser = DocumentTextParser()
    elif capture.parser_method == "SCANNED_PDF_OCR_CANDIDATE" and capture.media_type == "application/pdf":
        from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
        parser = ScannedPDFOCRParser()
    elif capture.parser_method == "NATIVE_PDF_TEXT_CANDIDATE" and capture.media_type == "application/pdf":
        from dichiarazioni_pubbliche.document_pdf_extraction import (
            BornDigitalPDFTextParser,
        )
        parser = BornDigitalPDFTextParser()
    else:
        return refuse("SOURCE_PARSER_UNSUPPORTED")
    saved_fetched = FetchedBytes(
        body=saved, final_url=capture.final_url, status_code=200,
        media_type=capture.media_type or "", charset="utf-8", content_length=len(saved),
    )
    parsed = parser.parse(saved_fetched)
    if (parsed.status != "SUCCEEDED" or parsed.parser_method != capture.parser_method
            or parsed.parser_version != capture.parser_version):
        return refuse("SOURCE_PARSER_VERSION_UNVERIFIED")
    options: dict[str, object] = {}
    page_number: int | None = None
    if passage.selector_type == "TEXT_POSITION":
        text = parsed.canonical_text
        if not isinstance(text, str) or quote_end > len(text):
            return refuse("QUOTE_RANGE_INVALID")
        options["canonical_text"] = text
        quote_text = text[quote_start:quote_end]
    elif passage.selector_type == "PAGE_RANGE":
        page_number = passage.page_start
        if (type(page_number) is not int or passage.page_end != page_number
                or not isinstance(parsed.metadata.get("page_selectors"), list)):
            return refuse("PDF_PAGE_UNVERIFIED")
        pages = [p for p in parsed.metadata["page_selectors"]
                 if p.get("page_number") == page_number]
        if len(pages) != 1:
            return refuse("PDF_PAGE_UNVERIFIED")
        page = pages[0]
        text = parsed.canonical_text[page["start_char"]:page["end_char"]]
        if quote_end > len(text):
            return refuse("QUOTE_RANGE_INVALID")
        options["page_text"] = text
        quote_text = text[quote_start:quote_end]
    else:
        return refuse("SELECTOR_NOT_NAVIGABLE")
    locator = ExactSourceLocator(
        content_id=content_id, passage_id=passage_id, selector_type=passage.selector_type,
        quote_start=quote_start, quote_end=quote_end, quote_sha256=quote_sha256,
        capture_id=capture_id, capture_sha256=capture.content_sha256,
        page_number=page_number,
    )
    resolution = resolve_exact_source_locator(
        locator, passage=passage, capture=capture, source_body=saved,
        quote_text=quote_text, **options,
    )
    if not resolution.located:
        return refuse(resolution.blockers[0] if resolution.blockers else resolution.status)
    try:
        live = fetch(capture.final_url, timeout=8, max_response_bytes=MAX_SOURCE_BYTES)
    except (OSError, RuntimeError, ValueError):
        return refuse("LIVE_SOURCE_UNAVAILABLE")
    if (not isinstance(live, FetchedBytes) or live.status_code != 200
            or live.media_type != capture.media_type):
        return refuse("LIVE_SOURCE_UNAVAILABLE")
    # A revoked right, removed collection membership or changed approved
    # original during the external request must not mint a stale navigation link.
    after = reader.run(
        _SNAPSHOT_SQL, collection_id=collection_id, content_id=content_id,
        capture_id=capture_id, passage_id=passage_id,
    )
    if not after or json.loads(after) != row:
        return refuse("SOURCE_STATE_CHANGED_DURING_FETCH")
    jump = private_written_source_jump(
        locator=locator, resolution=resolution, capture=capture,
        observed_live_sha256=hashlib.sha256(live.body).hexdigest(),
        observed_live_url=live.final_url, original_source=origin,
        quote_text=quote_text,
        verified_document_pages=(parsed.metadata.get("page_selectors")
                                 if capture.media_type == "application/pdf" else None),
    )
    return {
        "contract_version": STUDIO_EXACT_JUMP_VERSION,
        "private_only": True, "publication_authority": False,
        "rights_clearance": False, "status": jump.status,
        "reason": jump.reason, "url": jump.url, "precision": jump.precision,
    }


__all__ = ["STUDIO_EXACT_JUMP_VERSION", "read_studio_exact_source_jump"]
