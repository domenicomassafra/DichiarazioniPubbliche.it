"""DP-320: opt-in, isolated transactional revocation and public-read fence.

This is a SQLite reference contract for adversarial local tests, **not** a
production PostgreSQL adapter or CDN purge. No current public reader calls it.
An external release owner must bind every material dependency to the same
durable fence and validate it at every public read (including cached edges).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


VERSION = "publication-revocation-epoch-v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_REASONS = frozenset({
    "RIGHTS_WITHDRAWN", "RIGHTS_EXPIRED", "PRIVACY_HOLD", "CHALLENGE_PENDING",
    "SOURCE_SUPERSEDED", "CORRECTION", "REVIEW_REVOKED", "SOURCE_UNAVAILABLE",
})


class RevocationFenceHeld(ValueError):
    """Stable, private-data-free failure to issue, publish, or serve."""


def _id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise RevocationFenceHeld("FENCE_ID_INVALID")
    return value


def _sha(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise RevocationFenceHeld("FENCE_HASH_INVALID")
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()).hexdigest()


@dataclass(frozen=True)
class MaterialEpoch:
    dependency_id: str
    epoch: int
    material_sha256: str


@dataclass(frozen=True)
class PublicationEpochTicket:
    release_id: str
    dependencies: tuple[MaterialEpoch, ...]
    fingerprint: str
    version: str = VERSION


def _ticket_fingerprint(release_id: str, dependencies: tuple[MaterialEpoch, ...]) -> str:
    return _fingerprint({
        "version": VERSION,
        "release": release_id,
        "dependencies": [dict(
            dependency_id=item.dependency_id,
            epoch=item.epoch,
            material_sha256=item.material_sha256,
        ) for item in dependencies],
    })


class IsolatedPublicationEpochStore:
    """Explicit transaction prototype; caller owns its *isolated* SQLite DB.

    No schema is created automatically and no external connections are made.
    A future PostgreSQL owner must implement equivalent atomic semantics,
    never directly point this fixture at a production database.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def init_fixture_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS epoch_source (
                source_id TEXT PRIMARY KEY, epoch INTEGER NOT NULL DEFAULT 0,
                material_sha256 TEXT NOT NULL, status TEXT NOT NULL
                CHECK(status IN ('ACTIVE','HELD'))
            );
            CREATE TABLE IF NOT EXISTS epoch_revocation (
                event_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                epoch INTEGER NOT NULL, reason TEXT NOT NULL,
                material_sha256 TEXT NOT NULL, occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS epoch_outbox (
                event_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                epoch INTEGER NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS epoch_publication (
                release_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL,
                fence_sha256 TEXT NOT NULL
            );
        """)

    def register_fixture_source(self, source_id: str, material_sha256: str) -> None:
        """Only initial seed; does not restore an existing held source."""
        self.conn.execute(
            "INSERT OR IGNORE INTO epoch_source(source_id,epoch,material_sha256,status) "
            "VALUES (?,0,?,'ACTIVE')", (_id(source_id), _sha(material_sha256)),
        )
        self.conn.commit()

    def _check(self, ticket: PublicationEpochTicket) -> None:
        if (
            not isinstance(ticket, PublicationEpochTicket) or ticket.version != VERSION or
            not ticket.dependencies or not isinstance(ticket.dependencies, tuple) or
            tuple(sorted(ticket.dependencies, key=lambda item: item.dependency_id)) != ticket.dependencies
        ):
            raise RevocationFenceHeld("FENCE_TICKET_INVALID")
        _id(ticket.release_id)
        if len({item.dependency_id for item in ticket.dependencies}) != len(ticket.dependencies):
            raise RevocationFenceHeld("FENCE_DUPLICATE_DEPENDENCY")
        for item in ticket.dependencies:
            _id(item.dependency_id)
            _sha(item.material_sha256)
            if type(item.epoch) is not int or item.epoch < 0:
                raise RevocationFenceHeld("FENCE_EPOCH_INVALID")
        if _ticket_fingerprint(ticket.release_id, ticket.dependencies) != ticket.fingerprint:
            raise RevocationFenceHeld("FENCE_TICKET_TAMPERED")
        for item in ticket.dependencies:
            row = self.conn.execute(
                "SELECT epoch,material_sha256,status FROM epoch_source WHERE source_id=?",
                (item.dependency_id,),
            ).fetchone()
            if row != (item.epoch, item.material_sha256, "ACTIVE"):
                raise RevocationFenceHeld("FENCE_STALE_OR_HELD")

    def mint(self, *, release_id: str, dependency_ids: tuple[str, ...]) -> PublicationEpochTicket:
        _id(release_id)
        if not isinstance(dependency_ids, tuple) or not dependency_ids or len(dependency_ids) > 128:
            raise RevocationFenceHeld("FENCE_DEPENDENCY_SCOPE_INVALID")
        ids = tuple(sorted(_id(item) for item in dependency_ids))
        if len(set(ids)) != len(ids):
            raise RevocationFenceHeld("FENCE_DUPLICATE_DEPENDENCY")
        dependencies = []
        for source_id in ids:
            row = self.conn.execute(
                "SELECT epoch,material_sha256,status FROM epoch_source WHERE source_id=?", (source_id,),
            ).fetchone()
            if row is None or row[2] != "ACTIVE":
                raise RevocationFenceHeld("FENCE_STALE_OR_HELD")
            dependencies.append(MaterialEpoch(source_id, row[0], row[1]))
        items = tuple(dependencies)
        return PublicationEpochTicket(release_id, items, _ticket_fingerprint(release_id, items))

    def publish_reference(self, *, ticket: PublicationEpochTicket, artifact_sha256: str) -> None:
        """Commit an artifact reference, not public bytes, under an atomic fence."""
        _sha(artifact_sha256)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._check(ticket)
            old = self.conn.execute(
                "SELECT artifact_sha256,fence_sha256 FROM epoch_publication WHERE release_id=?",
                (ticket.release_id,),
            ).fetchone()
            if old and old != (artifact_sha256, ticket.fingerprint):
                raise RevocationFenceHeld("FENCE_RELEASE_ID_CONFLICT")
            self.conn.execute(
                "INSERT OR IGNORE INTO epoch_publication VALUES (?,?,?)",
                (ticket.release_id, artifact_sha256, ticket.fingerprint),
            )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def check_served(self, ticket: PublicationEpochTicket, artifact_sha256: str) -> bool:
        """Refuse a stale edge response even if the old artifact still exists."""
        self._check(ticket)
        row = self.conn.execute(
            "SELECT artifact_sha256,fence_sha256 FROM epoch_publication WHERE release_id=?",
            (ticket.release_id,),
        ).fetchone()
        if row != (_sha(artifact_sha256), ticket.fingerprint):
            raise RevocationFenceHeld("FENCE_PUBLIC_ARTIFACT_UNMATCHED")
        return True

    def revoke(self, *, source_id: str, event_id: str, reason: str, now: datetime) -> int:
        _id(source_id)
        _id(event_id)
        if reason not in _REASONS:
            raise RevocationFenceHeld("FENCE_REASON_INVALID")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RevocationFenceHeld("FENCE_TIMESTAMP_INVALID")
        stamp = now.astimezone(timezone.utc).isoformat()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            previous = self.conn.execute(
                "SELECT source_id,epoch,reason FROM epoch_revocation WHERE event_id=?", (event_id,),
            ).fetchone()
            if previous:
                if previous[0] != source_id or previous[2] != reason:
                    raise RevocationFenceHeld("FENCE_REPLAY_CONFLICT")
                self.conn.commit()
                return previous[1]
            row = self.conn.execute(
                "SELECT epoch,material_sha256 FROM epoch_source WHERE source_id=?", (source_id,),
            ).fetchone()
            if row is None:
                raise RevocationFenceHeld("FENCE_UNKNOWN_SOURCE")
            epoch = row[0] + 1
            self.conn.execute(
                "UPDATE epoch_source SET epoch=?, status='HELD' WHERE source_id=?",
                (epoch, source_id),
            )
            self.conn.execute(
                "INSERT INTO epoch_revocation VALUES (?,?,?,?,?,?)",
                (event_id, source_id, epoch, reason, row[1], stamp),
            )
            self.conn.execute(
                "INSERT INTO epoch_outbox(event_id,source_id,epoch,acknowledged) VALUES (?,?,?,0)",
                (event_id, source_id, epoch),
            )
            self.conn.commit()
            return epoch
        except BaseException:
            self.conn.rollback()
            raise

    def pending_invalidations(self) -> tuple[tuple[str, str, int], ...]:
        return tuple(self.conn.execute(
            "SELECT event_id,source_id,epoch FROM epoch_outbox "
            "WHERE acknowledged=0 ORDER BY source_id,epoch,event_id"
        ).fetchall())

    def acknowledge(self, *, event_id: str, epoch: int) -> None:
        # Acknowledging a side effect never re-opens or restores rights.
        cursor = self.conn.execute(
            "UPDATE epoch_outbox SET acknowledged=1 WHERE event_id=? AND epoch=?",
            (_id(event_id), epoch),
        )
        self.conn.commit()
        if cursor.rowcount != 1:
            raise RevocationFenceHeld("FENCE_OUTBOX_ACK_STALE")
