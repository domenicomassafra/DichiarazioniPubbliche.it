"""Bounded private operator batch: persisted discovery -> Capture -> Passage.

Real URLs are inputs supplied by an authorized operator, never invented by
this module. A dry run performs only metadata/rights reads. Execution never
creates/promotes a Statement, Claim, Finding or public projection.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dichiarazioni_pubbliche.capture_authorization import (
    PrivateCaptureAuthorizationBlocked,
    private_capture_rights_guard,
)
from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.discovery_provenance import accepted_discovery_family_counts

BATCH_VERSION = "private-research-capture-batch-v1"
MAX_BATCH_SIZE = 25


@dataclass(frozen=True)
class CaptureBatchItem:
    content_id: str
    canonical_url: str
    source_family: str
    rights_record_id: str


@dataclass(frozen=True)
class CaptureBatch:
    collection_id: str
    items: tuple[CaptureBatchItem, ...]
    version: str = BATCH_VERSION
    manifest_sha256: str = ""


def load_private_capture_batch(path: Path) -> CaptureBatch:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "collection_id", "items"}:
        raise ValueError("PRIVATE_CAPTURE_BATCH_SCHEMA_INVALID")
    if raw["version"] != BATCH_VERSION:
        raise ValueError("PRIVATE_CAPTURE_BATCH_VERSION_INVALID")
    collection_id = raw["collection_id"]
    if not isinstance(collection_id, str) or not collection_id.strip() or len(collection_id) > 256:
        raise ValueError("PRIVATE_CAPTURE_BATCH_COLLECTION_INVALID")
    items_raw = raw["items"]
    if not isinstance(items_raw, list) or not 1 <= len(items_raw) <= MAX_BATCH_SIZE:
        raise ValueError("PRIVATE_CAPTURE_BATCH_BOUNDS_INVALID")
    items: list[CaptureBatchItem] = []
    seen: set[str] = set()
    required = {"content_id", "canonical_url", "source_family", "rights_record_id"}
    for raw_item in items_raw:
        if not isinstance(raw_item, dict) or set(raw_item) != required:
            raise ValueError("PRIVATE_CAPTURE_BATCH_ITEM_SCHEMA_INVALID")
        if any(not isinstance(raw_item[key], str) or not raw_item[key].strip()
               or len(raw_item[key]) > 2048 for key in required):
            raise ValueError("PRIVATE_CAPTURE_BATCH_ITEM_INVALID")
        canonical_url = canonical_content_url(raw_item["canonical_url"])
        if canonical_url != raw_item["canonical_url"]:
            raise ValueError("PRIVATE_CAPTURE_BATCH_URL_NONCANONICAL")
        if raw_item["content_id"] in seen:
            raise ValueError("PRIVATE_CAPTURE_BATCH_DUPLICATE_CONTENT")
        seen.add(raw_item["content_id"])
        items.append(CaptureBatchItem(**raw_item))
    canonical = {
        "version": BATCH_VERSION,
        "collection_id": collection_id,
        "items": [vars(item) for item in items],
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CaptureBatch(collection_id=collection_id, items=tuple(items), manifest_sha256=digest)


def require_persisted_discovery(
    context: Mapping[str, Any] | None,
    *,
    collection_id: str,
    item: CaptureBatchItem,
) -> None:
    if not context or context.get("collection_id") != collection_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_COLLECTION_MISSING")
    if context.get("collection_status") != "ACTIVE":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_COLLECTION_NOT_ACTIVE")
    if context.get("membership_status") != "INCLUDED":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_MEMBERSHIP_NOT_INCLUDED")
    if context.get("capture_authorized") is not True:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_MEMBERSHIP_NOT_AUTHORIZED")
    if context.get("content_id") != item.content_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_MISMATCH")
    try:
        if canonical_content_url(context.get("canonical_url")) != item.canonical_url:
            raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_URL_MISMATCH")
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_CONTENT_URL_INVALID") from exc
    try:
        groups = accepted_discovery_family_counts(context)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked(
            "PRIVATE_CAPTURE_DISCOVERY_PROVENANCE_INVALID"
        ) from exc
    reported_count = context.get("accepted_discovery_hits")
    if type(reported_count) is not int or reported_count < 0 or sum(groups.values()) != reported_count:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_DISCOVERY_PROVENANCE_INCONSISTENT")
    if groups.get(item.source_family, 0) < 1:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_CAPTURE_DISCOVERY_PROVENANCE_MISSING")


def preflight_capture_batch(batch: CaptureBatch, *, capture_store: Any, rights_store: Any):
    """Precheck all members before executing the first remote network request."""
    guards = []
    for item in batch.items:
        def context_check(item=item) -> None:
            require_persisted_discovery(
                capture_store.read_research_capture_context(
                    batch.collection_id, item.content_id
                ),
                collection_id=batch.collection_id,
                item=item,
            )

        guard = private_capture_rights_guard(
            read_current=rights_store.read_current,
            read_content_state=capture_store.read_operator_capture_content_state,
            rights_record_id=item.rights_record_id,
            content_id=item.content_id,
            canonical_url=item.canonical_url,
            source_family=item.source_family,
        )

        def combined(guard=guard, context_check=context_check) -> None:
            context_check()
            guard()

        combined()
        guards.append(combined)
    return tuple(guards)
