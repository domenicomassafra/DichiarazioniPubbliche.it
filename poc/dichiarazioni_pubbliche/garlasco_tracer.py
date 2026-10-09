from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url


GARLASCO_TRACER_VERSION = "garlasco-tracer-v1"
GARLASCO_COLLECTION_ID = "research:garlasco"
GARLASCO_PILOT_SIZE = 100
GARLASCO_EXPECTED_BASELINE_CLAIMS = 30
REQUIRED_SOURCE_FAMILIES = frozenset(
    {
        "DIRECT_INTERVIEW_ARTICLE",
        "VIDEO_PODCAST",
        "OFFICIAL_PROCEDURAL",
        "SECONDARY_REPORTING",
        "DUPLICATE_DERIVATION",
    }
)


@dataclass(frozen=True)
class PilotItem:
    item_id: str
    canonical_url: str
    discovery_ref: str
    source_family: str
    rights_status: str


@dataclass(frozen=True)
class TracerManifest:
    collection_id: str
    items: tuple[PilotItem, ...]
    baseline_claim_ids: tuple[str, ...]
    version: str = GARLASCO_TRACER_VERSION


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    blockers: tuple[str, ...]
    manifest_sha256: str
    item_count: int
    baseline_claim_count: int
    version: str = GARLASCO_TRACER_VERSION


@dataclass(frozen=True)
class ReplayReceipt:
    stable: bool
    blockers: tuple[str, ...]
    before_logical_items: int
    after_logical_items: int
    before_claim_count: int
    after_claim_count: int
    before_public_findings: int
    after_public_findings: int


def _safe_url(value: str) -> bool:
    try:
        raw = str(value or "")
        parsed = urlsplit(raw)
        port = parsed.port
        canonical = canonical_content_url(raw)
    except ValueError:
        return False
    try:
        literal = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        literal = None
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and raw == canonical
        and parsed.hostname != "localhost"
        and (literal is None or literal.is_global)
    )


def _canonical_manifest_payload(manifest: TracerManifest) -> dict[str, object]:
    return {
        "version": manifest.version,
        "collection_id": manifest.collection_id,
        "items": [
            {
                "item_id": row.item_id,
                "canonical_url": row.canonical_url,
                "discovery_ref": row.discovery_ref,
                "source_family": row.source_family,
                "rights_status": row.rights_status,
            }
            for row in sorted(manifest.items, key=lambda item: item.item_id)
        ],
        "baseline_claim_ids": sorted(manifest.baseline_claim_ids),
    }


def manifest_sha256(manifest: TracerManifest) -> str:
    encoded = json.dumps(
        _canonical_manifest_payload(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_preflight(
    manifest: TracerManifest,
    *,
    observed_baseline_claim_ids: Iterable[str],
) -> PreflightResult:
    blockers: list[str] = []
    if manifest.version != GARLASCO_TRACER_VERSION:
        blockers.append("MANIFEST_VERSION_INVALID")
    if manifest.collection_id != GARLASCO_COLLECTION_ID:
        blockers.append("COLLECTION_ID_INVALID")
    if len(manifest.items) != GARLASCO_PILOT_SIZE:
        blockers.append("PILOT_ITEM_COUNT_NOT_100")

    item_ids = [str(row.item_id or "").strip() for row in manifest.items]
    urls = [str(row.canonical_url or "") for row in manifest.items]
    normalized_urls = []
    for url in urls:
        try:
            normalized_urls.append(canonical_content_url(url))
        except ValueError:
            normalized_urls.append(url)
    discovery_refs = [str(row.discovery_ref or "").strip() for row in manifest.items]
    if any(not value for value in item_ids):
        blockers.append("ITEM_ID_MISSING")
    if len(set(item_ids)) != len(item_ids):
        blockers.append("ITEM_ID_DUPLICATE")
    if len(set(normalized_urls)) != len(normalized_urls):
        blockers.append("CANONICAL_URL_DUPLICATE")
    if any(not _safe_url(value) for value in urls):
        blockers.append("CANONICAL_URL_UNSAFE")
    if any(not value for value in discovery_refs):
        blockers.append("DISCOVERY_PROVENANCE_MISSING")
    families = {row.source_family for row in manifest.items}
    missing_families = sorted(REQUIRED_SOURCE_FAMILIES - families)
    if missing_families:
        blockers.append("SOURCE_FAMILY_COVERAGE_MISSING:" + ",".join(missing_families))
    if families - REQUIRED_SOURCE_FAMILIES:
        blockers.append("SOURCE_FAMILY_UNRECOGNIZED")
    if any(not str(row.rights_status or "").strip() for row in manifest.items):
        blockers.append("RIGHTS_STATUS_MISSING")

    expected_claims = tuple(sorted(set(manifest.baseline_claim_ids)))
    observed_claims = tuple(sorted(set(str(x) for x in observed_baseline_claim_ids)))
    if len(expected_claims) != GARLASCO_EXPECTED_BASELINE_CLAIMS:
        blockers.append("BASELINE_MANIFEST_CLAIMS_NOT_30")
    if observed_claims != expected_claims:
        blockers.append("BASELINE_CLAIM_SET_MISMATCH")
    return PreflightResult(
        ready=not blockers,
        blockers=tuple(blockers),
        manifest_sha256=manifest_sha256(manifest),
        item_count=len(manifest.items),
        baseline_claim_count=len(observed_claims),
    )


def evaluate_replay(
    *,
    before_logical_items: int,
    after_logical_items: int,
    before_claim_ids: Sequence[str],
    after_claim_ids: Sequence[str],
    before_public_findings: int,
    after_public_findings: int,
    intentionally_new_capture_versions: int = 0,
) -> ReplayReceipt:
    del intentionally_new_capture_versions  # capture versions may grow; logical counts may not.
    blockers: list[str] = []
    if before_logical_items != after_logical_items:
        blockers.append("LOGICAL_ITEM_COUNT_CHANGED_ON_REPLAY")
    if tuple(sorted(before_claim_ids)) != tuple(sorted(after_claim_ids)):
        blockers.append("BASELINE_CLAIM_SET_CHANGED")
    if after_public_findings != before_public_findings:
        blockers.append("PUBLIC_FINDING_COUNT_CHANGED_FROM_INGESTION")
    return ReplayReceipt(
        stable=not blockers,
        blockers=tuple(blockers),
        before_logical_items=before_logical_items,
        after_logical_items=after_logical_items,
        before_claim_count=len(before_claim_ids),
        after_claim_count=len(after_claim_ids),
        before_public_findings=before_public_findings,
        after_public_findings=after_public_findings,
    )


__all__ = [
    "GARLASCO_COLLECTION_ID",
    "GARLASCO_EXPECTED_BASELINE_CLAIMS",
    "GARLASCO_PILOT_SIZE",
    "GARLASCO_TRACER_VERSION",
    "PilotItem",
    "PreflightResult",
    "REQUIRED_SOURCE_FAMILIES",
    "ReplayReceipt",
    "TracerManifest",
    "evaluate_preflight",
    "evaluate_replay",
    "manifest_sha256",
]
