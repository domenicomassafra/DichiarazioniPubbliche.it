"""DP-320 PRIVATE reference: compare two sealed-looking public surface cohorts.

This is a bounded OFFLINE planning contract, not a serving or revocation fence.
An independently authenticated release owner must supply both whole-cohort
manifest digests and real issued times; a caller-computed digest is not an
authorization. The caller must check current legal rights, SQLite epochs,
live HTTP/CDN and production reader delivery separately. No artifact bytes,
source IDs, URLs, provider calls or private material leave this planner.
"""

from __future__ import annotations

import hmac
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone

from .revocation_epoch_fence import (
    VERSION as EPOCH_VERSION,
    MaterialEpoch,
    PublicationEpochTicket,
    RevocationFenceHeld,
    _ticket_fingerprint,
)
from .revocation_served_surfaces_v1 import (
    EXTENDED_SURFACES,
    MAX_ARTIFACT_BYTES,
    SurfaceArtifact,
    surface_manifest_sha256,
)

VERSION = "dp320-private-release-transition-v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_VALID_STATUS = frozenset({"APPROVED", "PENDING", "REVOKED", "EXPIRED", "DENIED"})


@dataclass(frozen=True, slots=True)
class SurfaceTransition:
    surface: str
    change: str  # UNCHANGED | CHANGED | ADDED | REMOVED
    changed: bool
    previous_material_sha256: str | None
    current_material_sha256: str | None
    publication_authority: bool = False


@dataclass(frozen=True, slots=True)
class PrivateSurfaceReleaseTransition:
    version: str
    status: str
    previous_manifest_sha256: str
    current_manifest_sha256: str
    surfaces: tuple[SurfaceTransition, ...]
    reason_codes: tuple[str, ...]
    surface_count: int
    changed_surface_count: int
    added_surface_count: int
    removed_surface_count: int
    held_dependency_count: int
    dependencies_changed: bool
    private_only: bool = True
    rights_authority: bool = False
    source_approval_authority: bool = False
    publication_authority: bool = False
    source_body_count: int = 0
    provider_calls: int = 0


def _invalid(code: str) -> None:
    raise ValueError("TRANSITION_" + code)


def _release(
    ticket: PublicationEpochTicket,
    artifacts: tuple[SurfaceArtifact, ...],
    expected_manifest_sha256: str,
    include_rdf: bool,
) -> tuple[PublicationEpochTicket, tuple[SurfaceArtifact, ...], str]:
    """Snapshot a complete exact-typed release BEFORE digest and comparison."""
    if (
        type(include_rdf) is not bool
        or type(ticket) is not PublicationEpochTicket
        or type(ticket.release_id) is not str
        or type(ticket.fingerprint) is not str
        or type(ticket.dependencies) is not tuple
        or not 1 <= len(ticket.dependencies) <= 128
        or type(ticket.version) is not str
        or ticket.version != EPOCH_VERSION
        or any(
            type(dep) is not MaterialEpoch
            or type(dep.dependency_id) is not str
            or _ID.fullmatch(dep.dependency_id) is None
            or type(dep.material_sha256) is not str
            or _SHA.fullmatch(dep.material_sha256) is None
            or type(dep.epoch) is not int
            or dep.epoch < 0
            for dep in ticket.dependencies
        )
        or type(artifacts) is not tuple
        or len(artifacts) != (8 if include_rdf else 7)
        or any(
            type(item) is not SurfaceArtifact
            or type(item.surface) is not str
            or type(item.release_id) is not str
            or type(item.source_id) is not str
            or type(item.source_epoch) is not int
            or type(item.ticket_fingerprint) is not str
            or type(item.material_sha256) is not str
            or type(item.content) is not bytes
            or not 0 < len(item.content) <= MAX_ARTIFACT_BYTES
            for item in artifacts
        )
    ):
        _invalid("RELEASE_INVALID")
    identifiers = tuple(dep.dependency_id for dep in ticket.dependencies)
    if identifiers != tuple(sorted(set(identifiers))):
        _invalid("DEPENDENCY_SCOPE_INVALID")
    if (
        type(expected_manifest_sha256) is not str
        or _SHA.fullmatch(expected_manifest_sha256) is None
    ):
        _invalid("MANIFEST_PIN_INVALID")
    ticket, artifacts = deepcopy((ticket, artifacts))
    if (
        _ticket_fingerprint(ticket.release_id, ticket.dependencies)
        != ticket.fingerprint
    ):
        _invalid("TICKET_INVALID")
    try:
        actual = surface_manifest_sha256(ticket, artifacts, include_rdf=include_rdf)
    except (TypeError, AttributeError, KeyError, RevocationFenceHeld) as exc:
        raise ValueError("TRANSITION_RELEASE_INVALID") from exc
    if not hmac.compare_digest(actual, expected_manifest_sha256):
        _invalid("MANIFEST_PIN_MISMATCH")
    return ticket, artifacts, actual


def _issued(value: str) -> datetime:
    if type(value) is not str or len(value) > 40:
        _invalid("RELEASE_TIME_INVALID")
    try:
        point = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if point.tzinfo is None or point.utcoffset() is None:
            _invalid("RELEASE_TIME_INVALID")
        return point.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError, OverflowError) as exc:
        raise ValueError("TRANSITION_RELEASE_TIME_INVALID") from exc


def plan_private_surface_release_transition(
    *,
    previous_ticket: PublicationEpochTicket,
    previous_artifacts: tuple[SurfaceArtifact, ...],
    expected_previous_manifest_sha256: str,
    current_ticket: PublicationEpochTicket,
    current_artifacts: tuple[SurfaceArtifact, ...],
    expected_current_manifest_sha256: str,
    previous_created_at: str,
    current_created_at: str,
    as_of: datetime,
    current_source_policies: dict[str, tuple[str, str]],
    previous_include_rdf: bool = False,
    current_include_rdf: bool = False,
    private_opt_in: bool = False,
) -> PrivateSurfaceReleaseTransition:
    """Return private review tasks, never a publication or CDN-clearance decision.

    Both release manifests, UTC release-issued timestamps, and source policy
    declarations are independent caller-supplied receipts and must be verified
    by their actual owner. Even APPROVED declarations produce no legal rights
    or source approval. No SQLite or external state is read or mutated here.
    """
    if private_opt_in is not True:
        _invalid("PRIVATE_OPT_IN_REQUIRED")
    if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
        _invalid("AS_OF_INVALID")
    # Snapshot the exact plain policy dict before any release hash/validation
    # or potentially expensive read. Never re-read a caller-owned container.
    if type(current_source_policies) is not dict or any(
        type(key) is not str
        or type(value) is not tuple
        or len(value) != 2
        or any(type(part) is not str or part not in _VALID_STATUS for part in value)
        for key, value in current_source_policies.items()
    ):
        _invalid("SOURCE_POLICY_INVALID")
    policies = dict(current_source_policies)
    older, before, old_digest = _release(
        previous_ticket,
        previous_artifacts,
        expected_previous_manifest_sha256,
        previous_include_rdf,
    )
    newer, after, new_digest = _release(
        current_ticket,
        current_artifacts,
        expected_current_manifest_sha256,
        current_include_rdf,
    )
    current_ids = {row.dependency_id for row in newer.dependencies}
    if set(policies) != current_ids:
        _invalid("SOURCE_POLICY_SCOPE_INVALID")
    before_time, after_time = _issued(previous_created_at), _issued(current_created_at)
    if before_time > after_time:
        _invalid("RELEASE_TIME_ROLLBACK")
    if after_time > as_of.astimezone(timezone.utc):
        _invalid("RELEASE_IN_FUTURE")
    if before_time == after_time and (
        older.release_id != newer.release_id or old_digest != new_digest
    ):
        _invalid("RELEASE_TIME_CONFLICT")
    if older.release_id == newer.release_id and (
        older.fingerprint != newer.fingerprint or old_digest != new_digest
    ):
        _invalid("RELEASE_ID_CONFLICT")

    old_dependencies = {
        item.dependency_id: (item.epoch, item.material_sha256)
        for item in older.dependencies
    }
    new_dependencies = {
        item.dependency_id: (item.epoch, item.material_sha256)
        for item in newer.dependencies
    }
    dependencies_changed = old_dependencies != new_dependencies
    held = sum(
        1
        for use, review in policies.values()
        if (use, review) != ("APPROVED", "APPROVED")
    )
    old_material = {item.surface: item.material_sha256 for item in before}
    new_material = {item.surface: item.material_sha256 for item in after}
    rows: list[SurfaceTransition] = []
    for name in EXTENDED_SURFACES:
        if name not in old_material and name not in new_material:
            continue
        old_sha, new_sha = old_material.get(name), new_material.get(name)
        change = (
            "ADDED"
            if old_sha is None
            else "REMOVED"
            if new_sha is None
            else "CHANGED"
            if old_sha != new_sha
            else "UNCHANGED"
        )
        rows.append(
            SurfaceTransition(
                surface=name,
                change=change,
                changed=change != "UNCHANGED",
                previous_material_sha256=old_sha,
                current_material_sha256=new_sha,
            )
        )
    changed_count = sum(row.change == "CHANGED" for row in rows)
    added_count = sum(row.change == "ADDED" for row in rows)
    removed_count = sum(row.change == "REMOVED" for row in rows)
    reasons: set[str] = set()
    if changed_count:
        reasons.add("SURFACE_MATERIAL_CHANGED")
    if added_count or removed_count:
        reasons.add("SURFACE_SCOPE_CHANGED")
    if dependencies_changed:
        reasons.add("SOURCE_DEPENDENCY_DRIFT")
    if held:
        reasons.add("SOURCE_POLICY_NOT_APPROVED")
    return PrivateSurfaceReleaseTransition(
        version=VERSION,
        status=(
            "WITHHELD_SOURCE_POLICY"
            if held
            else "MANUAL_RECHECK_REQUIRED"
            if reasons
            else "UNCHANGED_REVIEW_PENDING"
        ),
        previous_manifest_sha256=old_digest,
        current_manifest_sha256=new_digest,
        surfaces=tuple(rows),
        reason_codes=tuple(sorted(reasons)),
        surface_count=len(new_material),
        changed_surface_count=changed_count,
        added_surface_count=added_count,
        removed_surface_count=removed_count,
        held_dependency_count=held,
        dependencies_changed=dependencies_changed,
    )


__all__ = [
    "PrivateSurfaceReleaseTransition",
    "SurfaceTransition",
    "plan_private_surface_release_transition",
]
