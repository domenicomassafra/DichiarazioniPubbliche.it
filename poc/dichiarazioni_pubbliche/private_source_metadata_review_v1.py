"""Private DP-231 metadata reconciliation against an existing public Content ID.

Retrieved metadata is only a candidate, never source approval, factual
verification, publication authority or permission to contact an oEmbed host.
There are NO HTTP, filesystem, database, archive or provider operations here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from .public_schema import projection_dataset_sha256, validate_public_bundle
from .source_metadata_enrichment import (
    MAX_CANDIDATES_PER_FIELD,
    MAX_URL_CHARS,
    MAX_VALUE_CHARS,
    METADATA_ENRICHMENT_VERSION,
    MetadataCandidate,
    MetadataConflict,
    MetadataEnrichment,
    _safe_https_url,
)

VERSION = "private-source-metadata-recheck-v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_ORIGIN = re.compile(
    r"(?:page_meta:[A-Za-z0-9:._-]{1,80}|jsonld:[0-7](?::(?:author|publisher))?|content|source_registry)\Z"
)
_FIELDS = frozenset({"title", "description", "author", "publisher"})
_CONFLICT_CODES = frozenset(
    {
        "CONTENT_TITLE_CONFLICT",
        "CONTENT_AUTHOR_CONFLICT",
        "CONTENT_PUBLISHER_CONFLICT",
        "SOURCE_REGISTRY_TITLE_CONFLICT",
        "SOURCE_REGISTRY_AUTHOR_CONFLICT",
        "SOURCE_REGISTRY_PUBLISHER_CONFLICT",
        "CONTENT_CANONICAL_URL_CONFLICT",
        "SOURCE_REGISTRY_CANONICAL_URL_CONFLICT",
        "CONTENT_SOURCE_REGISTRY_CANONICAL_CONFLICT",
        "PAGE_CANONICAL_AMBIGUOUS",
        "UNSAFE_CANONICAL_CANDIDATE",
        "UNSAFE_OEMBED_ENDPOINT",
    }
)
_POLICY = frozenset({"APPROVED", "REVOKED", "PENDING", "EXPIRED", "DENIED"})


@dataclass(frozen=True)
class PrivateMetadataRecheck:
    version: str
    status: str
    previous_sha256: str
    current_sha256: str
    public_projection_sha256: str
    changed_fields: tuple[str, ...]
    new_conflict_codes: tuple[str, ...]
    removed_conflict_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    snapshot_sha256: str
    private_only: bool = True
    absence_of_original_established: bool = False
    approved_official_source: bool = False
    source_approval_authority: bool = False
    publication_authority: bool = False
    factual_verification: bool = False
    identity_mutation_allowed: bool = False
    provider_calls: int = 0
    capture_calls: int = 0


def _fail(code: str = "METADATA_SNAPSHOT_INVALID") -> None:
    raise ValueError(code)


def _canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _validated(value: MetadataEnrichment) -> dict[str, Any]:
    if (
        type(value) is not MetadataEnrichment
        or type(value.content_id) is not str
        or not _ID.fullmatch(value.content_id)
        or value.contract_version != METADATA_ENRICHMENT_VERSION
        or value.publication_authority is not False
        or value.identity_mutation_allowed is not False
        or type(value.candidates) is not tuple
        or len(value.candidates) > 40
        or type(value.conflicts) is not tuple
        or len(value.conflicts) > 48
        or type(value.canonical_url_candidates) is not tuple
        or type(value.oembed_endpoint_candidates) is not tuple
        or len(value.canonical_url_candidates) > MAX_CANDIDATES_PER_FIELD
        or len(value.oembed_endpoint_candidates) > MAX_CANDIDATES_PER_FIELD
    ):
        _fail()
    for candidate in value.candidates:
        if (
            type(candidate) is not MetadataCandidate
            or type(candidate.field) is not str
            or candidate.field not in _FIELDS
            or type(candidate.value) is not str
            or not 0 < len(candidate.value) <= MAX_VALUE_CHARS
            or type(candidate.origin) is not str
            or not _ORIGIN.fullmatch(candidate.origin)
            or candidate.publication_authority is not False
        ):
            _fail()
    if any(
        sum(item.field == field for item in value.candidates)
        > 3 * MAX_CANDIDATES_PER_FIELD
        for field in _FIELDS
    ):
        _fail()
    for urls in (value.canonical_url_candidates, value.oembed_endpoint_candidates):
        if len(set(urls)) != len(urls):
            _fail()
        for url in urls:
            if (
                type(url) is not str
                or len(url) > MAX_URL_CHARS
                or _safe_https_url(url) != url
            ):
                _fail()
    for conflict in value.conflicts:
        if (
            type(conflict) is not MetadataConflict
            or type(conflict.code) is not str
            or conflict.code not in _CONFLICT_CODES
            or type(conflict.field) is not str
            or conflict.field not in _FIELDS | {"canonical_url", "oembed_endpoint"}
            or type(conflict.expected_origin) is not str
            or conflict.expected_origin
            not in {"content", "source_registry", "page", "capture_policy"}
            or type(conflict.expected_value) is not str
            or len(conflict.expected_value) > MAX_URL_CHARS
            or type(conflict.observed_values) is not tuple
            or len(conflict.observed_values) > MAX_CANDIDATES_PER_FIELD
            or any(
                type(item) is not str or len(item) > MAX_URL_CHARS
                for item in conflict.observed_values
            )
        ):
            _fail()
    return {
        "contract_version": value.contract_version,
        "content_id": value.content_id,
        "candidates": sorted(
            (asdict(item) for item in value.candidates),
            key=lambda item: (item["field"], item["origin"], item["value"]),
        ),
        "canonical_url_candidates": sorted(value.canonical_url_candidates),
        "oembed_endpoint_candidates": sorted(value.oembed_endpoint_candidates),
        "conflicts": sorted(
            (asdict(item) for item in value.conflicts),
            key=lambda item: (
                item["code"],
                item["field"],
                item["expected_origin"],
                item["expected_value"],
                item["observed_values"],
            ),
        ),
    }


def metadata_snapshot_sha256(value: MetadataEnrichment) -> str:
    """Change detector, NOT an independent signature or source approval."""
    return _canonical_digest(_validated(value))


def _frozen_public_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    if type(bundle) is not dict:
        _fail("PUBLIC_PROJECTION_INVALID")
    try:
        encoded = json.dumps(
            bundle,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(encoded.encode()) > 4_000_000:
            _fail("PUBLIC_PROJECTION_INVALID")
        frozen = json.loads(encoded)
        validate_public_bundle(frozen)
        if projection_dataset_sha256(frozen) != frozen["dataset_sha256"]:
            _fail("PUBLIC_PROJECTION_INVALID")
        return frozen
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise ValueError("PUBLIC_PROJECTION_INVALID") from exc


def plan_private_metadata_recheck(
    *,
    previous: MetadataEnrichment,
    current: MetadataEnrichment,
    expected_previous_sha256: str,
    expected_current_sha256: str,
    public_projection: dict[str, Any],
    expected_public_projection_sha256: str,
    expected_public_generated_at: str,
    content_id: str,
    source_use_status: str,
    source_review_status: str,
    allow_private_preview: bool = False,
) -> PrivateMetadataRecheck:
    """Reconcile candidate changes without exposing URLs, titles or provider data.

    The expected hashes/date and policy statuses must come from separately
    authenticated *owner* receipts. Self-rehashing untrusted input or labelling
    a source APPROVED locally cannot satisfy real authority or provenance.
    """
    if allow_private_preview is not True:
        _fail("PRIVATE_OPT_IN_REQUIRED")
    if (
        type(content_id) is not str
        or not _ID.fullmatch(content_id)
        or type(source_use_status) is not str
        or source_use_status not in _POLICY
        or type(source_review_status) is not str
        or source_review_status not in _POLICY
    ):
        _fail("METADATA_POLICY_INVALID")
    older, newer = _validated(previous), _validated(current)
    if older["content_id"] != content_id or newer["content_id"] != content_id:
        _fail("METADATA_CONTENT_ID_MISMATCH")
    old_hash, new_hash = _canonical_digest(older), _canonical_digest(newer)
    if (
        type(expected_previous_sha256) is not str
        or type(expected_current_sha256) is not str
        or not _SHA.fullmatch(expected_previous_sha256)
        or not _SHA.fullmatch(expected_current_sha256)
        or old_hash != expected_previous_sha256
        or new_hash != expected_current_sha256
    ):
        _fail("METADATA_PIN_MISMATCH")
    projection = _frozen_public_projection(public_projection)
    if (
        type(expected_public_projection_sha256) is not str
        or not _SHA.fullmatch(expected_public_projection_sha256)
        or projection["dataset_sha256"] != expected_public_projection_sha256
        or type(expected_public_generated_at) is not str
        or projection["generated_at"] != expected_public_generated_at
    ):
        _fail("PUBLIC_PROJECTION_PIN_MISMATCH")
    public_sources = [
        dossier["source"]
        for dossier in projection["dossiers"]
        if dossier["source"]["content_id"] == content_id
    ]
    # DP-434 permits independently reviewed public Content with no Finding.
    # Its canonical `contents` identity is as material as legacy dossier
    # source identity. Never silently prefer one when both name the same
    # Content ID with different locators in the same pinned projection.
    public_sources.extend(
        content
        for content in projection.get("contents", [])
        if content["content_id"] == content_id
    )
    if not public_sources:
        _fail("PUBLIC_CONTENT_NOT_FOUND")
    urls = {_safe_https_url(source["url"]) for source in public_sources}
    if None in urls or len(urls) != 1:
        _fail("PUBLIC_CONTENT_IDENTITY_AMBIGUOUS")
    public_url = next(iter(urls))
    changed = set()
    for field in _FIELDS:
        before = {
            (item["origin"], item["value"])
            for item in older["candidates"]
            if item["field"] == field
        }
        after = {
            (item["origin"], item["value"])
            for item in newer["candidates"]
            if item["field"] == field
        }
        if before != after:
            changed.add(field)
    if older["canonical_url_candidates"] != newer["canonical_url_candidates"]:
        changed.add("canonical_url")
    if older["oembed_endpoint_candidates"] != newer["oembed_endpoint_candidates"]:
        changed.add("oembed_endpoint")
    if (
        older["candidates"]
        or older["canonical_url_candidates"]
        or older["oembed_endpoint_candidates"]
    ) and not (
        newer["candidates"]
        or newer["canonical_url_candidates"]
        or newer["oembed_endpoint_candidates"]
    ):
        changed.add("metadata_removed")
    before_codes = {item["code"] for item in older["conflicts"]}
    after_codes = {item["code"] for item in newer["conflicts"]}
    added_codes, removed_codes = (
        tuple(sorted(after_codes - before_codes)),
        tuple(sorted(before_codes - after_codes)),
    )

    # A conflict code alone is not an identity for its observed evidence.
    # E.g. two different blocked private URLs both produce
    # UNSAFE_CANONICAL_CANDIDATE while their safe digest-only observations
    # differ. Compare full private snapshots here but expose ONLY a typed
    # changed-field flag, never raw values, URLs or per-candidate content.
    def conflict_identity(item: dict[str, Any]) -> tuple:
        return (
            item["code"],
            item["field"],
            item["expected_origin"],
            item["expected_value"],
            tuple(item["observed_values"]),
        )

    # Preserve cardinality: a repeated blocked candidate is still a change
    # in the pinned private evidence, even when every typed conflict code
    # and observed fingerprint is otherwise identical. Order is immaterial.
    if tuple(sorted(conflict_identity(item) for item in older["conflicts"])) != tuple(
        sorted(conflict_identity(item) for item in newer["conflicts"])
    ):
        changed.add("metadata_conflict_evidence")
    reasons: set[str] = set()
    if source_use_status != "APPROVED":
        reasons.add("SOURCE_USE_NOT_APPROVED")
    if source_review_status != "APPROVED":
        reasons.add("SOURCE_REVIEW_NOT_APPROVED")
    locator_conflict = bool(
        newer["canonical_url_candidates"]
        and public_url not in newer["canonical_url_candidates"]
    )
    if locator_conflict:
        reasons.add("PUBLIC_CONTENT_LOCATOR_MISMATCH")
    if changed:
        reasons.add("METADATA_CHANGED")
    if "metadata_conflict_evidence" in changed:
        reasons.add("METADATA_CONFLICT_EVIDENCE_CHANGED")
    if added_codes:
        reasons.add("NEW_METADATA_CONFLICT")
    if source_use_status != "APPROVED" or source_review_status != "APPROVED":
        status = "WITHHELD_SOURCE_POLICY"
    elif locator_conflict:
        status = "WITHHELD_IDENTITY_REVIEW"
    elif reasons:
        status = "REVIEW_REQUIRED"
    else:
        status = "UNCHANGED_REVIEW_PENDING"
    outcome = dict(
        version=VERSION,
        status=status,
        before=old_hash,
        after=new_hash,
        projection=projection["dataset_sha256"],
        changed_fields=sorted(changed),
        new_conflicts=added_codes,
        removed_conflicts=removed_codes,
        reasons=sorted(reasons),
    )
    return PrivateMetadataRecheck(
        version=VERSION,
        status=status,
        previous_sha256=old_hash,
        current_sha256=new_hash,
        public_projection_sha256=projection["dataset_sha256"],
        changed_fields=tuple(sorted(changed)),
        new_conflict_codes=added_codes,
        removed_conflict_codes=removed_codes,
        reason_codes=tuple(sorted(reasons)),
        snapshot_sha256=_canonical_digest(outcome),
    )
