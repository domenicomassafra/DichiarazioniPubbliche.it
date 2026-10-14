"""DP231 private, offline source candidate metadata coverage inspection.

Reads a separately pinned public-v2 Content/dossier release plus independently
pinned private metadata inventories. No origin is an official source simply
because it claims that role. Results contain opaque Content digests and generic
reason/counts only. No HTTP/oEmbed/body/capture/provider or publication path.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .private_source_metadata_review_v1 import (
    _canonical_digest,
    _frozen_public_projection,
    _validated,
)
from .source_metadata_enrichment import MetadataEnrichment, _safe_https_url

VERSION = "dp231-private-official-source-candidate-coverage-v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_INVENTORY = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_POLICY = frozenset({"APPROVED", "REVOKED", "PENDING", "EXPIRED", "DENIED"})
_ROLE = frozenset({"OFFICIAL_SOURCE", "PRIMARY_SOURCE", "SECONDARY_SOURCE", "UNKNOWN"})


@dataclass(frozen=True)
class CoverageReviewItem:
    opaque_content_ref: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PrivateSourceCoverageAudit:
    version: str
    status: str
    content_count: int
    linked_content_count: int
    standalone_content_count: int
    missing_count: int
    stale_count: int
    held_count: int
    items: tuple[CoverageReviewItem, ...]
    private_only: bool = True
    source_approval_authority: bool = False
    publication_authority: bool = False
    factual_verification: bool = False
    absence_of_original_established: bool = False
    identity_mutation_allowed: bool = False
    capture_calls: int = 0
    provider_calls: int = 0


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def coverage_policy_manifest_sha256(source_policies: dict[str, tuple[str, str]]) -> str:
    """Digest to compare with a separately authenticated policy-owner receipt."""
    if (
        type(source_policies) is not dict
        or len(source_policies) > 256
        or any(
            not _id(identifier)
            or type(pair) is not tuple
            or len(pair) != 2
            or any(type(status) is not str or status not in _POLICY for status in pair)
            for identifier, pair in source_policies.items()
        )
    ):
        raise ValueError("COVERAGE_POLICY_INVALID")
    return _canonical_digest({key: list(pair) for key, pair in source_policies.items()})


def coverage_inventory_manifest_sha256(
    pins: dict[str, dict[str, str]], observed_at: dict[str, str]
) -> str:
    """Hash pinned inventory boundaries, never metadata values or private IDs in output."""
    if (
        type(pins) is not dict
        or type(observed_at) is not dict
        or not 1 <= len(pins) <= 8
        or set(pins) != set(observed_at)
        or any(
            type(name) is not str
            or _INVENTORY.fullmatch(name) is None
            or type(records) is not dict
            or len(records) > 256
            or type(observed_at[name]) is not str
            or not 1 <= len(observed_at[name]) <= 40
            or any(
                not _id(identifier) or not _sha(digest)
                for identifier, digest in records.items()
            )
            for name, records in pins.items()
        )
    ):
        raise ValueError("COVERAGE_INVENTORY_MANIFEST_INVALID")
    return _canonical_digest(
        {
            name: {"observed_at": observed_at[name], "pins": records}
            for name, records in pins.items()
        }
    )


def _utc(value: str) -> datetime:
    try:
        if type(value) is not str or not 1 <= len(value) <= 40:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("COVERAGE_INVENTORY_TIME_INVALID") from exc


def plan_private_source_coverage(
    *,
    public_projection: dict[str, Any],
    expected_public_sha256: str,
    expected_public_generated_at: str,
    metadata_inventories: dict[str, dict[str, MetadataEnrichment]],
    expected_metadata_pins: dict[str, dict[str, str]],
    inventory_observed_at: dict[str, str],
    expected_inventory_manifest_sha256: str,
    source_policies: dict[str, tuple[str, str]],
    expected_source_policy_sha256: str,
    source_role_claims: dict[str, str],
    as_of: datetime,
    max_inventory_age_days: int = 30,
    private_opt_in: bool = False,
) -> PrivateSourceCoverageAudit:
    """Audit complete public Content scope across N private metadata inventories.

    Every digest and policy must be obtained from an independent authenticated
    owner; local hashing cannot issue a permission. An inventory's observed-at
    timestamp measures *inventory observation freshness*, not original metadata
    age or evidence/current-source rights. All outputs remain manual candidates.
    """
    if private_opt_in is not True:
        raise ValueError("COVERAGE_PRIVATE_OPT_IN_REQUIRED")
    if (
        type(as_of) is not datetime
        or as_of.tzinfo is None
        or as_of.utcoffset() is None
        or not 2000 <= as_of.year <= 2200
        or type(max_inventory_age_days) is not int
        or not 0 <= max_inventory_age_days <= 366
    ):
        raise ValueError("COVERAGE_TIME_INVALID")
    as_of_utc = as_of.astimezone(timezone.utc)
    if (
        not _sha(expected_public_sha256)
        or type(expected_public_generated_at) is not str
    ):
        raise ValueError("COVERAGE_PUBLIC_PIN_MISMATCH")
    # Snapshot and schema-validate BEFORE ANY derived URL/Content read.
    projection = _frozen_public_projection(public_projection)
    if (
        projection["dataset_sha256"] != expected_public_sha256
        or projection["generated_at"] != expected_public_generated_at
        or _utc(projection["generated_at"]) > as_of_utc
    ):
        raise ValueError("COVERAGE_PUBLIC_PIN_MISMATCH")

    # Snapshot caller-owned policy data before any inventory/url computation.
    # Reject dict subclasses: they can return different rows at validation/read.
    if type(source_policies) is not dict:
        raise ValueError("COVERAGE_POLICY_INVALID")
    policies = dict(source_policies.items())
    if (
        not _sha(expected_source_policy_sha256)
        or coverage_policy_manifest_sha256(policies) != expected_source_policy_sha256
    ):
        raise ValueError("COVERAGE_POLICY_PIN_MISMATCH")
    if type(source_role_claims) is not dict or len(source_role_claims) > 256:
        raise ValueError("COVERAGE_ROLE_CLAIMS_INVALID")
    claims = dict(source_role_claims.items())
    if any(
        not _id(identifier) or type(role) is not str or role not in _ROLE
        for identifier, role in claims.items()
    ):
        raise ValueError("COVERAGE_ROLE_CLAIMS_INVALID")

    # Each inventory is snapshotted once into validated primitive material,
    # bound to its independently supplied per-record and whole-manifest pins.
    # Do not dereference caller dictionaries or metadata objects afterwards.
    if (
        type(metadata_inventories) is not dict
        or type(expected_metadata_pins) is not dict
        or not 1 <= len(metadata_inventories) <= 8
        or len(expected_metadata_pins) != len(metadata_inventories)
        or any(
            type(items) is not dict or len(items) > 256
            for items in metadata_inventories.values()
        )
        or any(
            type(items) is not dict or len(items) > 256
            for items in expected_metadata_pins.values()
        )
    ):
        raise ValueError("COVERAGE_INVENTORY_INVALID")
    try:
        inventory_snapshot = {
            name: dict(records.items()) if type(records) is dict else None
            for name, records in metadata_inventories.items()
        }
        pinned_snapshot = {
            name: dict(records.items()) if type(records) is dict else None
            for name, records in expected_metadata_pins.items()
        }
        observed_snapshot = (
            dict(inventory_observed_at.items())
            if type(inventory_observed_at) is dict
            else None
        )
    except RuntimeError as exc:
        raise ValueError("COVERAGE_INVENTORY_INVALID") from exc
    if (
        observed_snapshot is None
        or any(records is None for records in inventory_snapshot.values())
        or any(records is None for records in pinned_snapshot.values())
        or set(inventory_snapshot) != set(pinned_snapshot)
        or set(inventory_snapshot) != set(observed_snapshot)
        or not _sha(expected_inventory_manifest_sha256)
        or coverage_inventory_manifest_sha256(pinned_snapshot, observed_snapshot)
        != expected_inventory_manifest_sha256
    ):
        raise ValueError("COVERAGE_INVENTORY_PIN_MISMATCH")

    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    stale_inventories: set[str] = set()
    for name in sorted(inventory_snapshot):
        observed = _utc(observed_snapshot[name])
        if observed > as_of_utc:
            raise ValueError("COVERAGE_INVENTORY_IN_FUTURE")
        if as_of_utc - observed > timedelta(days=max_inventory_age_days):
            stale_inventories.add(name)
        records = inventory_snapshot[name]
        pins = pinned_snapshot[name]
        if set(records) != set(pins):
            raise ValueError("COVERAGE_INVENTORY_PIN_MISMATCH")
        decoded: dict[str, dict[str, Any]] = {}
        for identifier, record in records.items():
            try:
                material = _validated(record)
                digest = _canonical_digest(material)
            except (TypeError, ValueError, AttributeError) as exc:
                raise ValueError("COVERAGE_METADATA_INVALID") from exc
            if material["content_id"] != identifier or digest != pins[identifier]:
                raise ValueError("COVERAGE_METADATA_PIN_MISMATCH")
            decoded[identifier] = {"sha256": digest, **material}
        normalized[name] = decoded

    # First-class Content may have no Finding/dossier. Linked dossier sources
    # are equally authoritative identity inputs for the SAME public Content ID.
    public_urls: dict[str, set[str | None]] = {}
    linked_ids: set[str] = set()
    for dossier in projection["dossiers"]:
        source = dossier["source"]
        identifier = source["content_id"]
        linked_ids.add(identifier)
        public_urls.setdefault(identifier, set()).add(_safe_https_url(source["url"]))
    for content in projection.get("contents", []):
        public_urls.setdefault(content["content_id"], set()).add(
            _safe_https_url(content["url"])
        )
    if any(None in urls or len(urls) != 1 for urls in public_urls.values()):
        raise ValueError("COVERAGE_PUBLIC_CANONICAL_DISCORDANCE")
    # Distinct public Content IDs may share a source URL. Never join them by
    # locator: only same-ID dossier/first-class discordance is ambiguous.
    identifiers = set(public_urls) | set(policies) | set(claims)
    for records in normalized.values():
        identifiers.update(records)
    if len(identifiers) > 256:
        raise ValueError("COVERAGE_SCOPE_TOO_LARGE")

    items: list[CoverageReviewItem] = []
    missing_count = stale_count = held_count = 0
    for identifier in sorted(identifiers):
        reasons: set[str] = set()
        available = {
            name: entries[identifier]
            for name, entries in normalized.items()
            if identifier in entries
        }
        if identifier not in public_urls:
            reasons.add("PRIVATE_INVENTORY_WITHOUT_PUBLIC_CONTENT_HOLD")
        else:
            if not available:
                reasons.add("METADATA_ABSENT_ALL_INVENTORIES")
            elif len(available) != len(normalized):
                reasons.add("METADATA_MISSING_IN_INVENTORY")
            # A valid, hash-pinned DTO with zero actual metadata or conflict
            # evidence is still NO coverage. Inventory presence and digest
            # verification alone cannot establish candidate enrichment.
            # Conflict-only captures are useful review evidence and remain
            # represented by PRIVATE_METADATA_CONFLICT_REVIEW below.
            if any(
                not any(
                    entry[field]
                    for field in (
                        "candidates",
                        "canonical_url_candidates",
                        "oembed_endpoint_candidates",
                        "conflicts",
                    )
                )
                for entry in available.values()
            ):
                reasons.add("METADATA_EMPTY_RECORD_REVIEW")
            if available and len({entry["sha256"] for entry in available.values()}) > 1:
                reasons.add("METADATA_INVENTORY_DISCORDANCE")
            # A stale inventory's *absence* of a record is also stale coverage:
            # looking only at records it contains would hide that gap.
            if stale_inventories:
                reasons.add("STALE_METADATA_INVENTORY")
            canonical = next(iter(public_urls[identifier]))
            # Two canonical candidates (whether within one record or across
            # different inventories) cannot silently update public identity.
            if any(
                url != canonical
                for entry in available.values()
                for url in entry["canonical_url_candidates"]
            ):
                reasons.add("PRIVATE_CANONICAL_DISCORDANCE")
            if any(entry["conflicts"] for entry in available.values()):
                reasons.add("PRIVATE_METADATA_CONFLICT_REVIEW")
        if policies.get(identifier, ("PENDING", "PENDING")) != ("APPROVED", "APPROVED"):
            reasons.add("SOURCE_RIGHTS_OR_REVIEW_HOLD")
        if identifier in claims:
            # Self-attested role is NEVER promoted into a rights/review status.
            reasons.add("SELF_ATTESTED_SOURCE_ROLE_NO_AUTHORITY")
        if not reasons:
            reasons.add("MANUAL_SOURCE_COVERAGE_REVIEW")
        if any(
            reason.startswith("METADATA_ABSENT")
            or reason
            in {"METADATA_MISSING_IN_INVENTORY", "METADATA_EMPTY_RECORD_REVIEW"}
            for reason in reasons
        ):
            missing_count += 1
        if "STALE_METADATA_INVENTORY" in reasons:
            stale_count += 1
        if reasons - {
            "MANUAL_SOURCE_COVERAGE_REVIEW",
            "SELF_ATTESTED_SOURCE_ROLE_NO_AUTHORITY",
        }:
            held_count += 1
        items.append(
            CoverageReviewItem(
                opaque_content_ref="sha256:"
                + hashlib.sha256(identifier.encode()).hexdigest(),
                reason_codes=tuple(sorted(reasons)),
            )
        )
    items.sort(key=lambda item: item.opaque_content_ref)
    return PrivateSourceCoverageAudit(
        version=VERSION,
        status="PRIVATE_COVERAGE_HOLDS" if held_count else "PRIVATE_REVIEW_ONLY",
        content_count=len(identifiers),
        linked_content_count=len(linked_ids),
        standalone_content_count=len(set(public_urls) - linked_ids),
        missing_count=missing_count,
        stale_count=stale_count,
        held_count=held_count,
        items=tuple(items),
    )


__all__ = [
    "CoverageReviewItem",
    "PrivateSourceCoverageAudit",
    "coverage_policy_manifest_sha256",
    "coverage_inventory_manifest_sha256",
    "plan_private_source_coverage",
]
