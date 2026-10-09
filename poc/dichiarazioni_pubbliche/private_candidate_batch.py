"""DP-211/214: provenance- and rights-gated operator Passage -> private Candidates.

This is a bounded operator execution seam, not a grant of source rights, an
attribution review, a model approval, or any publication authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from dichiarazioni_pubbliche.capture_authorization import (
    PrivateCaptureAuthorizationBlocked,
    private_capture_rights_guard,
    require_private_capture_rights,
)
from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.private_capture_batch import require_persisted_discovery, CaptureBatchItem
from dichiarazioni_pubbliche.rights_registry import RightsSubject

VERSION = "private-research-candidate-batch-v1"
MAX_ITEMS = 16
MODEL_USE = "OMNIROUTE_MODEL_EXTRACTION_PRIVATE"
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class CandidateBatchItem:
    passage_id: str
    content_id: str
    capture_id: str
    passage_sha256: str
    canonical_url: str
    source_family: str
    rights_record_id: str


@dataclass(frozen=True)
class CandidateBatch:
    collection_id: str
    items: tuple[CandidateBatchItem, ...]
    sha256: str


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("CANDIDATE_BATCH_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _batch_digest(batch: CandidateBatch) -> str:
    payload = {
        "version": VERSION,
        "collection_id": batch.collection_id,
        "items": [vars(item) for item in batch.items],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_batch(batch: CandidateBatch) -> None:
    """The file loader and direct preflight enforce the same bounded identities."""
    if not isinstance(batch, CandidateBatch):
        raise ValueError("CANDIDATE_BATCH_SCHEMA_INVALID")
    if not isinstance(batch.collection_id, str) or not _REF.fullmatch(batch.collection_id):
        raise ValueError("CANDIDATE_BATCH_COLLECTION_INVALID")
    if not isinstance(batch.items, tuple) or not 1 <= len(batch.items) <= MAX_ITEMS:
        raise ValueError("CANDIDATE_BATCH_SIZE_INVALID")
    passages: set[str] = set()
    urls_by_content: dict[str, str] = {}
    contents_by_url: dict[str, str] = {}
    for item in batch.items:
        if not isinstance(item, CandidateBatchItem):
            raise ValueError("CANDIDATE_BATCH_ITEM_SCHEMA_INVALID")
        for key, value in vars(item).items():
            if not isinstance(value, str) or not value or len(value) > 2048:
                raise ValueError("CANDIDATE_BATCH_ITEM_VALUE_INVALID")
            if key.endswith("_id") and not _REF.fullmatch(value):
                raise ValueError("CANDIDATE_BATCH_ITEM_REF_INVALID")
        if not _SHA.fullmatch(item.passage_sha256):
            raise ValueError("CANDIDATE_BATCH_PASSAGE_HASH_INVALID")
        try:
            canonical = canonical_content_url(item.canonical_url)
        except ValueError as exc:
            raise ValueError("CANDIDATE_BATCH_URL_INVALID") from exc
        if canonical != item.canonical_url:
            raise ValueError("CANDIDATE_BATCH_URL_NONCANONICAL")
        if item.passage_id in passages:
            raise ValueError("CANDIDATE_BATCH_PASSAGE_DUPLICATE")
        if (item.content_id in urls_by_content
                and urls_by_content[item.content_id] != canonical):
            raise ValueError("CANDIDATE_BATCH_CONTENT_URL_COLLISION")
        if canonical in contents_by_url and contents_by_url[canonical] != item.content_id:
            raise ValueError("CANDIDATE_BATCH_URL_CONTENT_COLLISION")
        passages.add(item.passage_id)
        urls_by_content[item.content_id] = canonical
        contents_by_url[canonical] = item.content_id
    if not isinstance(batch.sha256, str) or batch.sha256 != _batch_digest(batch):
        raise ValueError("CANDIDATE_BATCH_MANIFEST_HASH_MISMATCH")


def load_candidate_batch(path: Path) -> CandidateBatch:
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(payload, dict) or set(payload) != {"version", "collection_id", "items"}:
        raise ValueError("CANDIDATE_BATCH_SCHEMA_INVALID")
    if payload["version"] != VERSION:
        raise ValueError("CANDIDATE_BATCH_VERSION_INVALID")
    raw_items = payload["items"]
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= MAX_ITEMS:
        raise ValueError("CANDIDATE_BATCH_SIZE_INVALID")
    required = set(CandidateBatchItem.__dataclass_fields__)
    for raw in raw_items:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("CANDIDATE_BATCH_ITEM_SCHEMA_INVALID")
    batch = CandidateBatch(payload["collection_id"], tuple(CandidateBatchItem(**raw) for raw in raw_items), "")
    batch = CandidateBatch(batch.collection_id, batch.items, _batch_digest(batch))
    _validate_batch(batch)
    return batch


def require_private_passage_state(row: Mapping[str, Any] | None, item: CandidateBatchItem) -> None:
    if not row or row.get("passage_id") != item.passage_id or row.get("content_id") != item.content_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_PASSAGE_MISSING")
    if row.get("capture_id") != item.capture_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_BINDING_MISMATCH")
    if row.get("passage_sha256") != item.passage_sha256:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_PASSAGE_HASH_STALE")
    if row.get("capture_status") != "CAPTURED" or row.get("capture_hold_status") != "NONE":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_HELD")
    if row.get("capture_rights_status") != "CLEARED":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_RIGHTS_NOT_CLEARED")
    if row.get("capture_retention_class") not in {"EPHEMERAL", "DURABLE_PRIVATE", "DURABLE_PROVENANCE"}:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RETENTION_POLICY_PENDING")
    if not row.get("body_ref"):
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_BODY_UNAVAILABLE")


def preflight_candidate_batch(batch: CandidateBatch, *, capture_store: Any, candidate_store: Any, rights_store: Any) -> tuple[Callable[[], None], ...]:
    """No provider I/O, no database mutation, no private text printed."""
    try:
        _validate_batch(batch)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked(str(exc)) from exc
    guards = []
    for item in batch.items:
        source_item = CaptureBatchItem(item.content_id, item.canonical_url, item.source_family, item.rights_record_id)
        rights_guard = private_capture_rights_guard(
            read_current=rights_store.read_current,
            read_content_state=capture_store.read_operator_capture_content_state,
            rights_record_id=item.rights_record_id,
            content_id=item.content_id,
            canonical_url=item.canonical_url,
            source_family=item.source_family,
        )
        subject = RightsSubject(source_family=item.source_family, locator_kind="URL", locator_value=item.canonical_url, content_id=item.content_id)

        def check(item=item, source_item=source_item, rights_guard=rights_guard, subject=subject):
            require_persisted_discovery(
                capture_store.read_research_capture_context(batch.collection_id, item.content_id),
                collection_id=batch.collection_id,
                item=source_item,
            )
            # A capture's historical ingestion permit does not grant perpetual
            # privacy relevance for downstream model processing.
            try:
                capture_store.require_current_ingestion_relevance(
                    content_ref=item.content_id,
                    canonical_url=item.canonical_url,
                )
            except RuntimeError as exc:
                raise PrivateCaptureAuthorizationBlocked(
                    "PRIVATE_ANALYSIS_RELEVANCE_MISSING_OR_STALE"
                ) from exc
            rights_guard()
            rights = rights_store.read_current(subject)
            require_private_capture_rights(
                rights,
                rights_record_id=item.rights_record_id,
                content_id=item.content_id,
                canonical_url=item.canonical_url,
                source_family=item.source_family,
            )
            if MODEL_USE not in rights.permitted_uses:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_MODEL_USE_NOT_AUTHORIZED")
            require_private_passage_state(candidate_store.read_operator_passage_state(item.passage_id), item)

        check()
        guards.append(check)
    return tuple(guards)
