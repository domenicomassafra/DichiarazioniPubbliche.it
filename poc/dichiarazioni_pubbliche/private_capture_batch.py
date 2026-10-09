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
from dichiarazioni_pubbliche.capture_pipeline import (
    CapturePipelineError,
    _validate_capture_target,
)
from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.discovery_provenance import accepted_discovery_family_counts

BATCH_VERSION = "private-research-capture-batch-v1"
MAX_BATCH_SIZE = 25
MAX_MANIFEST_BYTES = 256_000


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


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("PRIVATE_CAPTURE_BATCH_DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _manifest_digest(batch: CaptureBatch) -> str:
    canonical = {
        "version": batch.version,
        "collection_id": batch.collection_id,
        "items": [vars(item) for item in batch.items],
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_batch(batch: CaptureBatch) -> None:
    """Same input contract for file-backed CLI and directly constructed batches."""
    if not isinstance(batch, CaptureBatch):
        raise ValueError("PRIVATE_CAPTURE_BATCH_SCHEMA_INVALID")
    if batch.version != BATCH_VERSION:
        raise ValueError("PRIVATE_CAPTURE_BATCH_VERSION_INVALID")
    collection_id = batch.collection_id
    if not isinstance(collection_id, str) or not collection_id.strip() or len(collection_id) > 256:
        raise ValueError("PRIVATE_CAPTURE_BATCH_COLLECTION_INVALID")
    if not isinstance(batch.items, tuple) or not 1 <= len(batch.items) <= MAX_BATCH_SIZE:
        raise ValueError("PRIVATE_CAPTURE_BATCH_BOUNDS_INVALID")
    seen: set[str] = set()
    seen_urls: set[str] = set()
    for item in batch.items:
        if not isinstance(item, CaptureBatchItem):
            raise ValueError("PRIVATE_CAPTURE_BATCH_ITEM_SCHEMA_INVALID")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 2048
               for value in vars(item).values()):
            raise ValueError("PRIVATE_CAPTURE_BATCH_ITEM_INVALID")
        canonical_url = canonical_content_url(item.canonical_url)
        if canonical_url != item.canonical_url:
            raise ValueError("PRIVATE_CAPTURE_BATCH_URL_NONCANONICAL")
        # A successful operator preflight must not claim READY for a target
        # rejected by the same acquisition boundary during --execute.
        # This static check does not replace transport-level DNS/redirect
        # enforcement, which must still run for each connection.
        try:
            _validate_capture_target(canonical_url, final=False)
        except CapturePipelineError as exc:
            raise ValueError("PRIVATE_CAPTURE_BATCH_URL_UNSAFE") from exc
        if item.content_id in seen:
            raise ValueError("PRIVATE_CAPTURE_BATCH_DUPLICATE_CONTENT")
        # The logical Content identity is URL-bound. Two different IDs for
        # one canonical locator in the same execution batch would duplicate
        # network capture and produce ambiguous discovery/rights receipts.
        if canonical_url in seen_urls:
            raise ValueError("PRIVATE_CAPTURE_BATCH_DUPLICATE_URL")
        seen.add(item.content_id)
        seen_urls.add(canonical_url)
    if batch.manifest_sha256:
        if (not isinstance(batch.manifest_sha256, str)
                or batch.manifest_sha256 != _manifest_digest(batch)):
            raise ValueError("PRIVATE_CAPTURE_BATCH_MANIFEST_HASH_MISMATCH")


def load_private_capture_batch(path: Path) -> CaptureBatch:
    with path.open("rb") as manifest_file:
        encoded = manifest_file.read(MAX_MANIFEST_BYTES + 1)
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("PRIVATE_CAPTURE_BATCH_FILE_TOO_LARGE")
    raw = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(raw, dict) or set(raw) != {"version", "collection_id", "items"}:
        raise ValueError("PRIVATE_CAPTURE_BATCH_SCHEMA_INVALID")
    items_raw = raw["items"]
    if not isinstance(items_raw, list):
        raise ValueError("PRIVATE_CAPTURE_BATCH_BOUNDS_INVALID")
    required = {"content_id", "canonical_url", "source_family", "rights_record_id"}
    for raw_item in items_raw:
        if not isinstance(raw_item, dict) or set(raw_item) != required:
            raise ValueError("PRIVATE_CAPTURE_BATCH_ITEM_SCHEMA_INVALID")
    batch = CaptureBatch(
        collection_id=raw["collection_id"],
        items=tuple(CaptureBatchItem(**item) for item in items_raw),
        version=raw["version"],
    )
    _validate_batch(batch)
    return CaptureBatch(
        collection_id=batch.collection_id, items=batch.items,
        manifest_sha256=_manifest_digest(batch),
    )


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
    try:
        _validate_batch(batch)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked(str(exc)) from exc
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
