"""DP-320 opt-in OFFLINE reference for revocation-fenced served surface claims.

Seven *simulated* public artifacts are bound to one immutable SQLite release
ticket, one whole-set manifest SHA and each material's exact bytes digest.
No HTML, response body, private source, complaint, or rights authority is
stored, returned, logged, or automatically published by this module.

Neither a caller-computed hash nor a ticket minted by a fixture is an actual
editorial/rights authorization. The release owner must authenticate both the
current ticket and the independently approved manifest elsewhere. The SQLite
BEGIN IMMEDIATE check only serializes reference verification with local
revocation commits; it does NOT fence bytes delivered *after* this call,
distributed caches, network/CDN, production PostgreSQL, or MiniPC.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from .revocation_epoch_fence import (
    IsolatedPublicationEpochStore,
    PublicationEpochTicket,
    RevocationFenceHeld,
    _fingerprint,
    _id,
    _sha,
)

VERSION = "dp320-served-surfaces-reference-v1"
ALL_SURFACES = (
    "HTML",
    "API",
    "SEARCH",
    "FEED",
    "SITEMAP",
    "LINKED_CARD",
    "JSON_LD",
)
MAX_ARTIFACT_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class SurfaceArtifact:
    """One bounded fixture body; content never crosses the fence's return."""

    surface: str
    release_id: str
    source_id: str
    source_epoch: int
    ticket_fingerprint: str
    material_sha256: str
    content: bytes


def _held(code: str) -> None:
    # Refusals intentionally contain stable codes only, never caller data.
    raise RevocationFenceHeld("SURFACE_" + code)


def _validated_metadata(
    ticket: PublicationEpochTicket,
    item: SurfaceArtifact,
) -> tuple[str, str, str, int, str, str]:
    if type(item) is not SurfaceArtifact:
        _held("METADATA_INVALID")
    if item.surface not in ALL_SURFACES:
        _held("SURFACE_INVALID")
    if item.release_id != ticket.release_id:
        _held("RELEASE_MISMATCH")
    if item.ticket_fingerprint != ticket.fingerprint:
        _held("TICKET_MISMATCH")
    if type(item.source_epoch) is not int or item.source_epoch < 0:
        _held("EPOCH_INVALID")
    try:
        _id(item.source_id)
    except RevocationFenceHeld:
        _held("SOURCE_INVALID")
    dependencies = {
        dependency.dependency_id: dependency.epoch for dependency in ticket.dependencies
    }
    if item.source_id not in dependencies:
        _held("SOURCE_MISMATCH")
    if item.source_epoch != dependencies[item.source_id]:
        _held("EPOCH_MISMATCH")
    try:
        _sha(item.material_sha256)
    except RevocationFenceHeld:
        _held("MATERIAL_INVALID")
    if (
        type(item.content) is not bytes
        or not 0 < len(item.content) <= MAX_ARTIFACT_BYTES
    ):
        _held("MATERIAL_INVALID")
    if hashlib.sha256(item.content).hexdigest() != item.material_sha256:
        _held("MATERIAL_MISMATCH")
    return (
        item.surface,
        item.release_id,
        item.source_id,
        item.source_epoch,
        item.ticket_fingerprint,
        item.material_sha256,
    )


def _complete_metadata(
    ticket: PublicationEpochTicket,
    artifacts: tuple[SurfaceArtifact, ...],
) -> tuple[tuple[str, str, str, int, str, str], ...]:
    if not isinstance(ticket, PublicationEpochTicket) or (
        not isinstance(ticket.dependencies, tuple) or not ticket.dependencies
    ):
        _held("TICKET_INVALID")
    if type(artifacts) is not tuple or len(artifacts) != len(ALL_SURFACES):
        _held("SCOPE_INVALID")
    metadata = tuple(_validated_metadata(ticket, value) for value in artifacts)
    if tuple(row[0] for row in metadata) != ALL_SURFACES:
        _held("SURFACE_ORDER_OR_DUPLICATE")
    return metadata


def _manifest_hash(
    ticket: PublicationEpochTicket,
    metadata: tuple[tuple[str, str, str, int, str, str], ...],
) -> str:
    """Only public IDs/digests, never artifact bytes or private revocation data."""
    return _fingerprint(
        {
            "version": VERSION,
            "release_id": ticket.release_id,
            "ticket_sha256": ticket.fingerprint,
            "artifacts": [
                {
                    "surface": row[0],
                    "release_id": row[1],
                    "source_id": row[2],
                    "source_epoch": row[3],
                    "ticket_sha256": row[4],
                    "material_sha256": row[5],
                }
                for row in metadata
            ],
        }
    )


def surface_manifest_sha256(
    ticket: PublicationEpochTicket,
    artifacts: tuple[SurfaceArtifact, ...],
) -> str:
    """Compute fixture digest; NEVER treat self-hashing as owner authorization."""
    return _manifest_hash(ticket, _complete_metadata(ticket, artifacts))


class IsolatedServedSurfaceFence:
    """SQLite-only adapter over the canonical DP-320 reference transaction.

    Caller supplies an isolated connection with the base fixture schema. The
    extra surface table is opt-in, never globally installed. One transaction
    atomically compares material epochs, root publication and all seven
    individually digested, immutable surface references. Every simulated read
    rechecks the *whole* cohort, not just the chosen URL/surface.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        if type(conn) is not sqlite3.Connection:
            _held("CONNECTION_INVALID")
        self.conn = conn
        self.base = IsolatedPublicationEpochStore(conn)

    def init_fixture_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS dp320_surface_reference (
                release_id TEXT NOT NULL,
                surface TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_epoch INTEGER NOT NULL CHECK(source_epoch >= 0),
                ticket_fingerprint TEXT NOT NULL,
                material_sha256 TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                PRIMARY KEY (release_id, surface)
            );
        """)

    def _published_metadata(
        self,
        ticket: PublicationEpochTicket,
        pinned_manifest: str,
    ) -> tuple[tuple[str, str, str, int, str, str], ...]:
        root = self.conn.execute(
            "SELECT artifact_sha256,fence_sha256 FROM epoch_publication WHERE release_id=?",
            (ticket.release_id,),
        ).fetchone()
        if root != (pinned_manifest, ticket.fingerprint):
            _held("PUBLICATION_MISMATCH")
        rows = self.conn.execute(
            "SELECT surface,release_id,source_id,source_epoch,"
            "ticket_fingerprint,material_sha256,manifest_sha256 "
            "FROM dp320_surface_reference WHERE release_id=? ORDER BY surface",
            (ticket.release_id,),
        ).fetchall()
        if len(rows) != len(ALL_SURFACES):
            _held("SCOPE_MISSING")
        by_surface = {row[0]: row for row in rows}
        if len(by_surface) != len(ALL_SURFACES) or set(by_surface) != set(ALL_SURFACES):
            _held("SURFACE_MISMATCH")
        metadata = tuple(tuple(by_surface[surface][:6]) for surface in ALL_SURFACES)
        if any(row[6] != pinned_manifest for row in rows):
            _held("MANIFEST_MISMATCH")
        for row in metadata:
            if (
                row[1] != ticket.release_id
                or row[4] != ticket.fingerprint
                or type(row[3]) is not int
                or (row[2], row[3])
                not in {(dep.dependency_id, dep.epoch) for dep in ticket.dependencies}
            ):
                _held("TICKET_EPOCH_MISMATCH")
            try:
                _sha(row[5])
            except RevocationFenceHeld:
                _held("MATERIAL_MISMATCH")
        if _manifest_hash(ticket, metadata) != pinned_manifest:
            _held("MANIFEST_MISMATCH")
        return metadata

    def seal(
        self,
        ticket: PublicationEpochTicket,
        artifacts: tuple[SurfaceArtifact, ...],
        independently_pinned_manifest_sha256: str,
    ) -> bool:
        """Atomically seal all seven material refs under one current ticket.

        No replace, delete, upsert, silent correction or auto restore is
        supported. A replacement needs a separately governed new release.
        """
        metadata = _complete_metadata(ticket, artifacts)
        try:
            pinned = _sha(independently_pinned_manifest_sha256)
        except RevocationFenceHeld:
            _held("TICKET_PIN_INVALID")
        if _manifest_hash(ticket, metadata) != pinned:
            _held("TICKET_PIN_MISMATCH")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.base._check(ticket)
            existing = self.conn.execute(
                "SELECT artifact_sha256,fence_sha256 FROM epoch_publication WHERE release_id=?",
                (ticket.release_id,),
            ).fetchone()
            if existing is not None:
                if existing != (pinned, ticket.fingerprint):
                    _held("RELEASE_CONFLICT")
                if self._published_metadata(ticket, pinned) != metadata:
                    _held("RELEASE_CONFLICT")
            else:
                orphan = self.conn.execute(
                    "SELECT 1 FROM dp320_surface_reference WHERE release_id=? LIMIT 1",
                    (ticket.release_id,),
                ).fetchone()
                if orphan:
                    _held("RELEASE_CONFLICT")
                self.conn.execute(
                    "INSERT INTO epoch_publication VALUES (?,?,?)",
                    (ticket.release_id, pinned, ticket.fingerprint),
                )
                self.conn.executemany(
                    "INSERT INTO dp320_surface_reference "
                    "(surface,release_id,source_id,source_epoch,ticket_fingerprint,"
                    "material_sha256,manifest_sha256) VALUES (?,?,?,?,?,?,?)",
                    (row + (pinned,) for row in metadata),
                )
            self.conn.commit()
            return True
        except BaseException:
            self.conn.rollback()
            raise

    def _read(
        self,
        ticket: PublicationEpochTicket,
        pinned: str,
        observed: tuple[tuple[str, str, str, int, str, str], ...],
        *,
        one: bool,
    ) -> bool:
        try:
            _sha(pinned)
        except RevocationFenceHeld:
            _held("TICKET_PIN_INVALID")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.base._check(ticket)
            stored = self._published_metadata(ticket, pinned)
            if one:
                if observed[0] != stored[ALL_SURFACES.index(observed[0][0])]:
                    _held("MATERIAL_MISMATCH")
            elif stored != observed:
                _held("MATERIAL_MISMATCH")
            self.conn.commit()
            return True
        except BaseException:
            self.conn.rollback()
            raise

    def check_one(
        self,
        ticket: PublicationEpochTicket,
        observation: SurfaceArtifact,
        independently_pinned_manifest_sha256: str,
    ) -> bool:
        """Reference-only admission for one bounded body, with whole-set check."""
        if not isinstance(ticket, PublicationEpochTicket):
            _held("TICKET_INVALID")
        item = _validated_metadata(ticket, observation)
        return self._read(
            ticket, independently_pinned_manifest_sha256, (item,), one=True
        )

    def check_all(
        self,
        ticket: PublicationEpochTicket,
        observations: tuple[SurfaceArtifact, ...],
        independently_pinned_manifest_sha256: str,
    ) -> bool:
        """Check all material bodies against the SAME immutable current cohort."""
        metadata = _complete_metadata(ticket, observations)
        return self._read(
            ticket, independently_pinned_manifest_sha256, metadata, one=False
        )
