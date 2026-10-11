"""DP-518: strict offline inventory/readback comparison for a proposed withdrawal.

This is *not* an HTTP reader, a privileged release manifest, a cache purge,
an attested MiniPC receipt, or the DP-320 production atomic fence. All inputs
are caller-supplied. Passing consistency never authorizes release or claims a
live host/edge has been inspected: a separately trusted operator must gather
and sign actual host, CDN and source records with transactional verification.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from dichiarazioni_pubbliche.revocation_epoch_fence import (
    MaterialEpoch,
    PublicationEpochTicket,
    VERSION as EPOCH_VERSION,
    _ticket_fingerprint,
)

VERSION = "distributed-withdrawal-audit-v1"
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")

# Includes every public consumer that might retain, expose, navigate or cache
# an affected record. ABSENT must be explicit; a missing consumer is not safe.
REQUIRED_PUBLIC_CONSUMERS = frozenset(
    {
        "STATEMENT",
        "LIST",
        "PERSON_TOPIC",
        "CONTENT",
        "TRACE",
        "SEARCH",
        "SITEMAP",
        "API_JSON",
        "HTML",
        "JSON_LD",
        "RDF",
        "CACHE_EDGE",
    }
)


@dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    entity_id: str
    surface: str
    state: str  # ABSENT or PRESENT in proposed bundle, never an authorization
    artifact_sha256: str | None
    dependency_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReleaseSnapshot:
    release_id: str
    host_ref: str
    code_sha256: str
    mirror_sha256: str
    migration_sha256: str
    policy_sha256: str
    generation_sha256: str
    fence: PublicationEpochTicket
    artifacts: tuple[ReleaseArtifact, ...]


@dataclass(frozen=True, slots=True)
class ReleaseReadback:
    """Independently gathered release metadata; caller supplied, never attested here."""

    release_id: str
    host_ref: str
    code_sha256: str
    mirror_sha256: str
    migration_sha256: str
    policy_sha256: str
    generation_sha256: str
    fence_fingerprint: str
    inventory_sha256: str


@dataclass(frozen=True, slots=True)
class PublicReadback:
    entity_id: str
    surface: str
    host_ref: str
    generation_ref: str
    status_code: int
    body_sha256: str | None


@dataclass(frozen=True, slots=True)
class WithdrawalReadbackAudit:
    status: str
    sanitized_reason_codes: tuple[str, ...]
    surface_count: int
    unsafe_surfaces: tuple[str, ...]
    contract_version: str = VERSION

    @property
    def release_authorized(self) -> bool:
        return False

    @property
    def publication_authority(self) -> bool:
        return False

    @property
    def withdrawal_verified_on_live_host(self) -> bool:
        return False

    @property
    def cache_purge_verified(self) -> bool:
        return False


def _ref(value: object) -> bool:
    return isinstance(value, str) and _REF.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def release_inventory_sha256(artifacts: tuple[ReleaseArtifact, ...]) -> str:
    """Canonical inventory checksum; it does not prove who measured the bytes."""
    rows = [
        (row.entity_id, row.surface, row.state, row.artifact_sha256, row.dependency_refs)
        for row in sorted(artifacts, key=lambda row: (row.entity_id, row.surface))
    ]
    return hashlib.sha256(
        json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _fence_ok(ticket: PublicationEpochTicket) -> bool:
    if (
        not isinstance(ticket, PublicationEpochTicket)
        or ticket.version != EPOCH_VERSION
        or not _ref(ticket.release_id)
        or not _sha(ticket.fingerprint)
        or not isinstance(ticket.dependencies, tuple)
        or not 1 <= len(ticket.dependencies) <= 128
    ):
        return False
    if any(
        not isinstance(row, MaterialEpoch)
        or not _ref(row.dependency_id)
        or not _sha(row.material_sha256)
        or type(row.epoch) is not int
        or row.epoch < 0
        for row in ticket.dependencies
    ):
        return False
    keys = tuple(item.dependency_id for item in ticket.dependencies)
    return (
        keys == tuple(sorted(set(keys)))
        and _ticket_fingerprint(ticket.release_id, ticket.dependencies)
        == ticket.fingerprint
    )


def _validate_manifest(
    manifest: ReleaseSnapshot,
) -> dict[tuple[str, str], ReleaseArtifact]:
    if not isinstance(manifest, ReleaseSnapshot):
        raise ValueError("DP518_RELEASE_MANIFEST_INVALID")
    if not (
        _ref(manifest.release_id)
        and _ref(manifest.host_ref)
        and all(
            _sha(value)
            for value in (
                manifest.code_sha256,
                manifest.mirror_sha256,
                manifest.migration_sha256,
                manifest.policy_sha256,
                manifest.generation_sha256,
            )
        )
        and _fence_ok(manifest.fence)
        and manifest.fence.release_id == manifest.release_id
    ):
        raise ValueError("DP518_RELEASE_BINDING_INVALID")
    if (
        not isinstance(manifest.artifacts, tuple)
        or not 1 <= len(manifest.artifacts) <= 240
    ):
        raise ValueError("DP518_ARTIFACT_COUNT_INVALID")
    dependencies = {item.dependency_id for item in manifest.fence.dependencies}
    result: dict[tuple[str, str], ReleaseArtifact] = {}
    for item in manifest.artifacts:
        if (
            not isinstance(item, ReleaseArtifact)
            or not _ref(item.entity_id)
            or item.surface not in REQUIRED_PUBLIC_CONSUMERS
            or item.state not in {"ABSENT", "PRESENT"}
            or (item.artifact_sha256 is None) != (item.state == "ABSENT")
            or (item.artifact_sha256 is not None and not _sha(item.artifact_sha256))
            or not isinstance(item.dependency_refs, tuple)
            or not item.dependency_refs
            or len(item.dependency_refs) > 128
            or any(
                not _ref(ref) or ref not in dependencies for ref in item.dependency_refs
            )
            or tuple(sorted(set(item.dependency_refs))) != item.dependency_refs
        ):
            raise ValueError("DP518_ARTIFACT_INVALID")
        key = (item.entity_id, item.surface)
        if key in result:
            raise ValueError("DP518_DUPLICATE_ARTIFACT")
        result[key] = item
    return result


def audit_withdrawal_readback(
    manifest: ReleaseSnapshot,
    readbacks: tuple[PublicReadback, ...],
    *,
    revoked_dependencies: tuple[str, ...],
    observed_release: ReleaseReadback,
    current_fence: PublicationEpochTicket | None = None,
) -> WithdrawalReadbackAudit:
    """Compare *supplied* sanitized metadata, with all real authority absent.

    No caller flag/HTTP 404 can prove cache invalidation, and no returned
    status can be used as a release permission. Operational code must perform
    independent authenticated live fetch and DP-320 current epoch read-fence.
    """
    inventory = _validate_manifest(manifest)
    if (
        not isinstance(revoked_dependencies, tuple)
        or not 1 <= len(revoked_dependencies) <= 128
        or any(not _ref(ref) for ref in revoked_dependencies)
        or tuple(sorted(set(revoked_dependencies))) != revoked_dependencies
    ):
        raise ValueError("DP518_REVOCATION_SCOPE_INVALID")
    revocations = set(revoked_dependencies)
    dependencies = {item.dependency_id for item in manifest.fence.dependencies}
    if not revocations.issubset(dependencies):
        raise ValueError("DP518_REVOCATION_FENCE_SCOPE_MISSING")
    if (
        not isinstance(observed_release, ReleaseReadback)
        or not _ref(observed_release.release_id)
        or not _ref(observed_release.host_ref)
        or not all(
            _sha(value)
            for value in (
                observed_release.code_sha256,
                observed_release.mirror_sha256,
                observed_release.migration_sha256,
                observed_release.policy_sha256,
                observed_release.generation_sha256,
                observed_release.fence_fingerprint,
                observed_release.inventory_sha256,
            )
        )
    ):
        raise ValueError("DP518_RELEASE_READBACK_INVALID")
    if observed_release != ReleaseReadback(
        manifest.release_id,
        manifest.host_ref,
        manifest.code_sha256,
        manifest.mirror_sha256,
        manifest.migration_sha256,
        manifest.policy_sha256,
        manifest.generation_sha256,
        manifest.fence.fingerprint,
        release_inventory_sha256(manifest.artifacts),
    ):
        return WithdrawalReadbackAudit(
            "READBACK_UNTRUSTED_OR_DRIFT",
            ("RELEASE_IDENTITY_READBACK_DRIFT",),
            len(inventory),
            (),
        )
    if current_fence is not None:
        if (
            not _fence_ok(current_fence)
            or current_fence.release_id != manifest.release_id
        ):
            raise ValueError("DP518_CURRENT_FENCE_INVALID")
        if current_fence != manifest.fence:
            return WithdrawalReadbackAudit(
                "STALE_REVOCATION_EPOCH",
                ("FENCE_CHANGED_RECHECK_REQUIRED",),
                len(inventory),
                (),
            )

    if not isinstance(readbacks, tuple) or len(readbacks) > 240:
        raise ValueError("DP518_READBACK_COUNT_INVALID")
    observed: dict[tuple[str, str], PublicReadback] = {}
    for item in readbacks:
        if (
            not isinstance(item, PublicReadback)
            or not _ref(item.entity_id)
            or item.surface not in REQUIRED_PUBLIC_CONSUMERS
            or not _ref(item.host_ref)
            or not _ref(item.generation_ref)
            or type(item.status_code) is not int
            or not 100 <= item.status_code <= 599
            or (item.body_sha256 is not None and not _sha(item.body_sha256))
        ):
            raise ValueError("DP518_READBACK_INVALID")
        key = (item.entity_id, item.surface)
        if key in observed:
            raise ValueError("DP518_DUPLICATE_READBACK")
        observed[key] = item
    if set(observed) - set(inventory):
        raise ValueError("DP518_READBACK_UNSCOPED")

    revoked_by_entity: dict[str, set[str]] = {}
    for (entity, _), artifact in inventory.items():
        overlap = revocations.intersection(artifact.dependency_refs)
        if overlap:
            revoked_by_entity.setdefault(entity, set()).update(overlap)
    affected = set(revoked_by_entity)
    if not affected:
        return WithdrawalReadbackAudit(
            "INCOMPLETE_PUBLIC_COVERAGE",
            ("REVOCATION_NOT_LINKED_TO_PUBLIC_ENTITY",),
            len(inventory),
            (),
        )

    needs = {
        (entity, surface)
        for entity in affected
        for surface in REQUIRED_PUBLIC_CONSUMERS
    }
    if not needs.issubset(inventory) or not needs.issubset(observed):
        return WithdrawalReadbackAudit(
            "INCOMPLETE_PUBLIC_COVERAGE",
            ("EXACT_CONSUMER_INVENTORY_OR_READBACK_MISSING",),
            len(inventory),
            (),
        )

    unsafe: set[str] = set()
    errors: set[str] = set()
    for key in sorted(needs):
        artifact, observed_row = inventory[key], observed[key]
        if not revoked_by_entity[artifact.entity_id].issubset(artifact.dependency_refs):
            errors.add("PUBLIC_CONSUMER_DEPENDENCY_INCOMPLETE")
        if artifact.state != "ABSENT":
            unsafe.add(artifact.surface)
        if observed_row.host_ref != manifest.host_ref or (
            observed_row.generation_ref != "generation:" + manifest.generation_sha256
        ):
            errors.add("PUBLIC_HOST_OR_GENERATION_DRIFT")
        if (
            observed_row.status_code in {200, 206}
            or observed_row.body_sha256 is not None
        ):
            unsafe.add(artifact.surface)
        elif observed_row.status_code not in {404, 410}:
            errors.add("PUBLIC_READBACK_UNAVAILABLE_OR_REDIRECT")
    if unsafe:
        return WithdrawalReadbackAudit(
            "UNSAFE_PUBLIC_VISIBILITY",
            ("REVOKED_ENTITY_STILL_PRESENT",),
            len(inventory),
            tuple(sorted(unsafe)),
        )
    if errors:
        return WithdrawalReadbackAudit(
            "READBACK_UNTRUSTED_OR_DRIFT", tuple(sorted(errors)), len(inventory), ()
        )
    return WithdrawalReadbackAudit("CONSISTENT_UNATTESTED", (), len(inventory), ())


__all__ = [
    "REQUIRED_PUBLIC_CONSUMERS",
    "ReleaseArtifact",
    "ReleaseReadback",
    "ReleaseSnapshot",
    "PublicReadback",
    "WithdrawalReadbackAudit",
    "audit_withdrawal_readback",
    "release_inventory_sha256",
]
