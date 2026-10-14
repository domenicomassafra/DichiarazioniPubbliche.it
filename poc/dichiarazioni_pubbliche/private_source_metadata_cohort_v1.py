"""DP231 private multi-Content source metadata reconciliation across pinned releases.

This is a deterministic MANUAL WORK QUEUE, not a data source, a publisher, an
official-source permission, a content sync or an evidence fact checker. The
owner supplies two *separately authorized* public projection receipts and
private metadata pins; local SHA checks do not issue that authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .private_source_metadata_review_v1 import (
    PrivateMetadataRecheck,
    _frozen_public_projection,
    metadata_snapshot_sha256,
    plan_private_metadata_recheck,
)
from .source_metadata_enrichment import MetadataEnrichment, _safe_https_url

VERSION = "private-source-metadata-cohort-v1"
POLICY_STATUSES = frozenset({"APPROVED", "REVOKED", "PENDING", "EXPIRED", "DENIED"})


@dataclass(frozen=True)
class PrivateCohortReviewItem:
    opaque_content_ref: str
    status: str
    changed_fields: tuple[str, ...]
    reason_codes: tuple[str, ...]
    metadata_previous_sha256: str | None
    metadata_current_sha256: str | None
    source_approval_authority: bool = False
    publication_authority: bool = False
    provider_calls: int = 0


@dataclass(frozen=True)
class PrivateMetadataCohort:
    version: str
    status: str
    previous_public_sha256: str
    current_public_sha256: str
    cohort_count: int
    unchanged_count: int
    changed_count: int
    held_count: int
    added_count: int
    retired_count: int
    review_items: tuple[PrivateCohortReviewItem, ...]
    snapshot_sha256: str
    private_only: bool = True
    publication_authority: bool = False
    source_approval_authority: bool = False
    factual_verification: bool = False
    identity_mutation_allowed: bool = False
    absence_of_original_established: bool = False
    capture_calls: int = 0
    provider_calls: int = 0


def _fail(code: str) -> None:
    raise ValueError(code)


def _material_sha(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _canonical_url(projection: dict[str, Any], content_id: str) -> str:
    """All public representations of one Content must have one valid URL."""
    source_urls = [
        dossier["source"]["url"]
        for dossier in projection["dossiers"]
        if dossier["source"]["content_id"] == content_id
    ]
    source_urls += [
        content["url"]
        for content in projection.get("contents", [])
        if content["content_id"] == content_id
    ]
    if not source_urls:
        _fail("COHORT_PRIVATE_METADATA_NOT_PUBLIC")
    canonical = {_safe_https_url(url) for url in source_urls}
    if None in canonical or len(canonical) != 1:
        _fail("COHORT_PUBLIC_CONTENT_IDENTITY_AMBIGUOUS")
    return next(iter(canonical))


def _is_published_content(projection: dict[str, Any], content_id: str) -> bool:
    return any(
        dossier["source"]["content_id"] == content_id
        for dossier in projection["dossiers"]
    ) or any(
        content["content_id"] == content_id
        for content in projection.get("contents", [])
    )


def _public_content_ids(projection: dict[str, Any]) -> set[str]:
    return {dossier["source"]["content_id"] for dossier in projection["dossiers"]} | {
        content["content_id"] for content in projection.get("contents", [])
    }


def _public(
    projection: dict[str, Any], expected_hash: str, generated_at: str
) -> dict[str, Any]:
    try:
        frozen = _frozen_public_projection(projection)
        if (
            type(expected_hash) is not str
            or frozen["dataset_sha256"] != expected_hash
            or type(generated_at) is not str
            or frozen["generated_at"] != generated_at
        ):
            _fail("COHORT_PUBLIC_PIN_MISMATCH")
        return frozen
    except (TypeError, KeyError, ValueError) as exc:
        if str(exc) == "COHORT_PUBLIC_PIN_MISMATCH":
            raise
        raise ValueError("COHORT_PUBLIC_PIN_MISMATCH") from exc


def _metadata_inventory(
    metadata: dict[str, MetadataEnrichment],
    pins: dict[str, str],
) -> dict[str, str]:
    if (
        type(metadata) is not dict
        or type(pins) is not dict
        or set(metadata) != set(pins)
        or len(metadata) > 256
    ):
        _fail("COHORT_METADATA_PINS_MISMATCH")
    verified = {}
    for identifier, value in metadata.items():
        if type(identifier) is not str or value.content_id != identifier:
            _fail("COHORT_METADATA_PINS_MISMATCH")
        try:
            actual = metadata_snapshot_sha256(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("COHORT_METADATA_PINS_MISMATCH") from exc
        if type(pins[identifier]) is not str or actual != pins[identifier]:
            _fail("COHORT_METADATA_PINS_MISMATCH")
        verified[identifier] = actual
    return verified


def plan_private_metadata_cohort(
    *,
    previous: dict[str, MetadataEnrichment],
    current: dict[str, MetadataEnrichment],
    previous_metadata_pins: dict[str, str],
    current_metadata_pins: dict[str, str],
    previous_public_projection: dict[str, Any],
    current_public_projection: dict[str, Any],
    expected_previous_public_sha256: str,
    expected_current_public_sha256: str,
    expected_previous_generated_at: str,
    expected_current_generated_at: str,
    source_policies: dict[str, tuple[str, str]],
    private_opt_in: bool = False,
) -> PrivateMetadataCohort:
    """Classify private metadata changes without leaking titles/locators.

    Inventory union is explicit. A private record cannot establish it belongs
    to an approved source: public membership and legal permissions are
    separately pinned input contracts; `APPROVED` is not self-authenticating.
    """
    if private_opt_in is not True:
        _fail("COHORT_PRIVATE_OPT_IN_REQUIRED")
    before_public = _public(
        previous_public_projection,
        expected_previous_public_sha256,
        expected_previous_generated_at,
    )
    after_public = _public(
        current_public_projection,
        expected_current_public_sha256,
        expected_current_generated_at,
    )
    # Two individually pinned releases are not necessarily chronological.
    # Without a monotonically ordered owner-issued release timestamp, treating
    # an older snapshot as current would silently erase later review work.
    try:
        before_time = datetime.fromisoformat(
            before_public["generated_at"].replace("Z", "+00:00")
        )
        after_time = datetime.fromisoformat(
            after_public["generated_at"].replace("Z", "+00:00")
        )
        if before_time.tzinfo is None or after_time.tzinfo is None:
            _fail("COHORT_PUBLIC_RELEASE_TIME_INVALID")
        if after_time.astimezone(timezone.utc) < before_time.astimezone(timezone.utc):
            _fail("COHORT_PUBLIC_RELEASE_TIME_ROLLBACK")
        if (
            after_time.astimezone(timezone.utc) == before_time.astimezone(timezone.utc)
            and before_public["dataset_sha256"] != after_public["dataset_sha256"]
        ):
            _fail("COHORT_PUBLIC_GENERATION_CONFLICT")
    except (TypeError, AttributeError) as exc:
        raise ValueError("COHORT_PUBLIC_RELEASE_TIME_INVALID") from exc
    before_pins = _metadata_inventory(previous, previous_metadata_pins)
    after_pins = _metadata_inventory(current, current_metadata_pins)
    # A cohort cannot claim a clean release merely because a published
    # Content lacks *both* private metadata records. Include the COMPLETE
    # public-v2 scope from both validated, pinned releases, not just the
    # subset present in private inventories. Unknown policy stays held.
    scoped_ids = set(before_pins) | set(after_pins)
    identifiers = (
        scoped_ids
        | _public_content_ids(before_public)
        | _public_content_ids(after_public)
    )
    if len(identifiers) > 256:
        _fail("COHORT_PUBLIC_SCOPE_TOO_LARGE")
    if (
        type(source_policies) is not dict
        or set(source_policies) != scoped_ids
        or any(
            type(status) is not tuple
            or len(status) != 2
            or any(
                type(item) is not str or item not in POLICY_STATUSES for item in status
            )
            for status in source_policies.values()
        )
    ):
        _fail("COHORT_SOURCE_POLICY_MISMATCH")

    old_url = {
        identifier: _canonical_url(before_public, identifier)
        for identifier in before_pins
    }
    new_url = {
        identifier: _canonical_url(after_public, identifier)
        for identifier in after_pins
    }
    rows: list[PrivateCohortReviewItem] = []
    counts = dict(unchanged=0, changed=0, held=0, added=0, retired=0)

    for identifier in sorted(identifiers):
        use, review = source_policies.get(identifier, ("PENDING", "PENDING"))
        reasons: tuple[str, ...] = ()
        fields: tuple[str, ...] = ()
        if identifier not in scoped_ids:
            status = "UNSCOPED_PUBLIC_CONTENT_REVIEW"
            reasons = ("PUBLIC_CONTENT_METADATA_NOT_IN_REVIEW_SCOPE",)
        elif identifier not in before_pins:
            if _is_published_content(before_public, identifier):
                status = "NEW_METADATA_RECORD_REVIEW"
                reasons = ("NEW_PRIVATE_METADATA_NOT_SOURCE_APPROVAL",)
            else:
                status = "NEW_CONTENT_METADATA_REVIEW"
                counts["added"] += 1
                reasons = ("NEW_PUBLIC_CONTENT_NOT_SOURCE_APPROVAL",)
        elif identifier not in after_pins:
            if _is_published_content(after_public, identifier):
                status = "MISSING_CURRENT_METADATA_REVIEW"
                reasons = ("CURRENT_PRIVATE_METADATA_MISSING",)
            else:
                status = "RETIRED_CONTENT_REVIEW"
                counts["retired"] += 1
                reasons = ("RETIRED_PUBLIC_CONTENT_RECHECK",)
        elif old_url[identifier] != new_url[identifier]:
            status = "PUBLIC_SOURCE_LOCATOR_CHANGED_HOLD"
            reasons = ("PUBLIC_SOURCE_IDENTITY_DRIFT",)
        else:
            review_item: PrivateMetadataRecheck = plan_private_metadata_recheck(
                previous=previous[identifier],
                current=current[identifier],
                expected_previous_sha256=before_pins[identifier],
                expected_current_sha256=after_pins[identifier],
                public_projection=after_public,
                expected_public_projection_sha256=expected_current_public_sha256,
                expected_public_generated_at=expected_current_generated_at,
                content_id=identifier,
                source_use_status=use,
                source_review_status=review,
                allow_private_preview=True,
            )
            status, reasons, fields = (
                review_item.status,
                review_item.reason_codes,
                review_item.changed_fields,
            )

        if identifier in scoped_ids and (use != "APPROVED" or review != "APPROVED"):
            status = "WITHHELD_SOURCE_POLICY"
            reasons = tuple(sorted(set(reasons) | {"SOURCE_POLICY_NOT_APPROVED"}))
        if (
            status.startswith("WITHHELD")
            or status == "PUBLIC_SOURCE_LOCATOR_CHANGED_HOLD"
            or status == "UNSCOPED_PUBLIC_CONTENT_REVIEW"
        ):
            counts["held"] += 1
        if status == "UNCHANGED_REVIEW_PENDING":
            counts["unchanged"] += 1
        else:
            counts["changed"] += 1

        rows.append(
            PrivateCohortReviewItem(
                opaque_content_ref="sha256:"
                + hashlib.sha256(identifier.encode()).hexdigest(),
                status=status,
                changed_fields=fields,
                reason_codes=reasons,
                metadata_previous_sha256=before_pins.get(identifier),
                metadata_current_sha256=after_pins.get(identifier),
            )
        )
    rows.sort(
        key=lambda row: (
            row.status != "NEW_CONTENT_METADATA_REVIEW",
            row.opaque_content_ref,
        )
    )
    status = (
        "IDLE_PRIVATE_REVIEW_PENDING"
        if counts["changed"] == 0
        else "MANUAL_COHORT_RECHECK_REQUIRED"
    )
    material = {
        "version": VERSION,
        "status": status,
        "before": before_public["dataset_sha256"],
        "after": after_public["dataset_sha256"],
        "rows": [asdict(row) for row in rows],
        "counts": counts,
    }
    return PrivateMetadataCohort(
        version=VERSION,
        status=status,
        previous_public_sha256=before_public["dataset_sha256"],
        current_public_sha256=after_public["dataset_sha256"],
        cohort_count=len(identifiers),
        unchanged_count=counts["unchanged"],
        changed_count=counts["changed"],
        held_count=counts["held"],
        added_count=counts["added"],
        retired_count=counts["retired"],
        review_items=tuple(rows),
        snapshot_sha256=_material_sha(material),
    )
