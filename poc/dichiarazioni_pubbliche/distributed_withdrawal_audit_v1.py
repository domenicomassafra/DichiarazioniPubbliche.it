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
import os
import re
from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path

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

# Legacy static routes can survive a rebuild under filenames absent from the
# proposed consumer inventory. Only known build asset formats in dedicated
# asset directories are outside this route-coverage check; an API/search JSON
# file in those directories is still a public-content route, not an asset.
_BUILD_ASSET_DIRECTORIES = frozenset({"_astro", "assets", "static", "images", "fonts"})
_BUILD_ASSET_SUFFIXES = frozenset({
    ".avif", ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".map",
    ".mjs", ".otf", ".png", ".svg", ".ttf", ".wasm", ".webp", ".woff",
    ".woff2",
})
_MAX_LOCAL_RELEASE_ENTRIES = 10000


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
class LocalConsumerPath:
    """One concrete public output relative to an isolated static release directory."""

    entity_id: str
    surface: str
    relative_path: str


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
    linked_revocations = {
        dependency
        for entity_dependencies in revoked_by_entity.values()
        for dependency in entity_dependencies
    }
    # A partial withdrawal graph must never look consistent merely because
    # another revoked dependency *is* linked to valid 404/410 readbacks.
    # Every explicitly requested revocation must map to at least one public
    # entity in this inventory before asserting even offline consistency.
    if linked_revocations != revocations:
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


def audit_local_static_withdrawal(
    root: Path,
    receipt_path: Path,
    manifest: ReleaseSnapshot,
    paths: tuple[LocalConsumerPath, ...],
    *,
    revoked_dependencies: tuple[str, ...],
    current_fence: PublicationEpochTicket,
) -> WithdrawalReadbackAudit:
    """Read real bytes in a *local fixture* tree, including a simulated edge cache.

    A separate private sidecar receipt (outside the public document root)
    binds release hashes, inventory digest and every material epoch.
    This function only reads paths: it cannot purge caches, deploy, authorize,
    or attest a live host. The complete path inventory must be explicit.
    """
    inventory = _validate_manifest(manifest)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("DP518_LOCAL_ROOT_INVALID")
    if not isinstance(paths, tuple) or len(paths) != len(inventory):
        raise ValueError("DP518_LOCAL_ROUTE_COVERAGE_INVALID")
    routes: dict[tuple[str, str], str] = {}
    seen_paths: set[str] = set()
    for route in paths:
        if (
            not isinstance(route, LocalConsumerPath)
            or (route.entity_id, route.surface) not in inventory
            or not isinstance(route.relative_path, str)
            or len(route.relative_path) > 400
            or not re.fullmatch(r"[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._:-]+)*", route.relative_path)
            or any(part in {".", ".."} for part in route.relative_path.split("/"))
        ):
            raise ValueError("DP518_LOCAL_PATH_UNSAFE")
        key = (route.entity_id, route.surface)
        if key in routes or route.relative_path in seen_paths:
            raise ValueError("DP518_LOCAL_ROUTE_COVERAGE_INVALID")
        routes[key] = route.relative_path
        seen_paths.add(route.relative_path)
    if set(routes) != set(inventory):
        raise ValueError("DP518_LOCAL_ROUTE_COVERAGE_INVALID")

    def checked_path(relative: str) -> Path:
        current = root
        for component in relative.split("/"):
            current = current / component
            if current.is_symlink():
                raise ValueError("DP518_LOCAL_PATH_UNSAFE")
        return current

    receipt = Path(receipt_path)
    if (
        receipt.is_symlink()
        or not receipt.is_file()
        or receipt.resolve().is_relative_to(root.resolve())
        or receipt.stat().st_size > 65536
    ):
        raise ValueError("DP518_LOCAL_RELEASE_RECEIPT_INVALID")
    try:
        document = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or set(document) != {"version", "release", "epochs"}
            or document["version"] != VERSION
            or not isinstance(document["release"], dict)
            or set(document["release"]) != set(ReleaseReadback.__dataclass_fields__)
            or not isinstance(document["epochs"], list)
        ):
            raise ValueError("DP518_LOCAL_RELEASE_RECEIPT_INVALID")
        observed = ReleaseReadback(**document["release"])
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise ValueError("DP518_LOCAL_RELEASE_RECEIPT_INVALID") from exc
    if (
        not _ref(observed.release_id)
        or not _ref(observed.host_ref)
        or not all(
            _sha(value) for value in (
                observed.code_sha256, observed.mirror_sha256,
                observed.migration_sha256, observed.policy_sha256,
                observed.generation_sha256, observed.fence_fingerprint,
                observed.inventory_sha256,
            )
        )
    ):
        raise ValueError("DP518_LOCAL_RELEASE_RECEIPT_INVALID")
    if document["epochs"] != [asdict(row) for row in manifest.fence.dependencies]:
        return WithdrawalReadbackAudit(
            "READBACK_UNTRUSTED_OR_DRIFT", ("LOCAL_EPOCH_READBACK_DRIFT",),
            len(inventory), (),
        )

    readbacks: list[PublicReadback] = []
    for (entity, surface), relative in sorted(routes.items()):
        file = checked_path(relative)
        if file.exists() and not file.is_file():
            raise ValueError("DP518_LOCAL_PATH_UNSAFE")
        digest = None
        if file.is_file():
            hasher = hashlib.sha256()
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(65536), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()
        readbacks.append(
            PublicReadback(
                entity, surface, observed.host_ref,
                "generation:" + observed.generation_sha256,
                200 if digest is not None else 404, digest,
            )
        )

    result = audit_withdrawal_readback(
        manifest, tuple(readbacks), revoked_dependencies=revoked_dependencies,
        observed_release=observed, current_fence=current_fence,
    )
    if result.status != "CONSISTENT_UNATTESTED":
        return result
    # Reading only declared routes cannot prove even offline absence of stale
    # legacy HTML/API/search files left behind by a previous static generation.
    # Enumerate the *selected local release root*, not arbitrary filesystem
    # trees. A missed directory or an unlisted symlink may itself be servable.
    # Stream and bound directory entries so a large or corrupt release cannot
    # hang the safety audit or be treated as successfully inspected.
    try:
        pending = [root]
        entries_seen = 0
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > _MAX_LOCAL_RELEASE_ENTRIES:
                        raise ValueError("DP518_LOCAL_SCAN_LIMIT_EXCEEDED")
                    if entry.is_symlink():
                        raise ValueError("DP518_LOCAL_PATH_UNSAFE")
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        raise ValueError("DP518_LOCAL_PATH_UNSAFE")
                    candidate = Path(entry.path)
                    relative = candidate.relative_to(root)
                    if relative.as_posix() in seen_paths:
                        continue
                    if (
                        relative.parts[0] in _BUILD_ASSET_DIRECTORIES
                        and candidate.suffix.lower() in _BUILD_ASSET_SUFFIXES
                    ):
                        continue
                    return WithdrawalReadbackAudit(
                        "READBACK_UNTRUSTED_OR_DRIFT",
                        ("LOCAL_UNINVENTORIED_PUBLIC_FILE",),
                        len(inventory), (),
                    )
    except OSError as exc:
        raise ValueError("DP518_LOCAL_PATH_UNSAFE") from exc
    # A withdrawn release may retain unaffected content. Those bytes must
    # still match the pinned local inventory or the rehearsal is incomplete.
    if any(
        (row.status_code == 200) != (inventory[(row.entity_id, row.surface)].state == "PRESENT")
        or (row.status_code == 200 and row.body_sha256 != inventory[(row.entity_id, row.surface)].artifact_sha256)
        for row in readbacks
    ):
        return WithdrawalReadbackAudit(
            "READBACK_UNTRUSTED_OR_DRIFT", ("LOCAL_UNAFFECTED_ARTIFACT_DRIFT",),
            len(inventory), (),
        )
    return result


__all__ = [
    "REQUIRED_PUBLIC_CONSUMERS",
    "LocalConsumerPath",
    "ReleaseArtifact",
    "ReleaseReadback",
    "ReleaseSnapshot",
    "PublicReadback",
    "WithdrawalReadbackAudit",
    "audit_withdrawal_readback",
    "audit_local_static_withdrawal",
    "release_inventory_sha256",
]
