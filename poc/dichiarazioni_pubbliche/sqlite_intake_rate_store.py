"""Durable local-only SQLite quota store for validated public intake."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .public_intake_abuse import RateStoreRequest, RateStoreResult


class SQLiteIntakeRateStore:
    """Process-safe, restart-safe quotas for one explicitly configured private edge.

    The caller provisions a private directory on the same host as the intake service.
    SQLite's BEGIN IMMEDIATE serializes independent workers; this store has no public
    endpoint, request payload, network, provider or publication capability. It must
    never be shared between hosts as a distributed quota authority.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("INTAKE_PRIVATE_ABSOLUTE_PATH_REQUIRED")
        parent = self.path.parent
        parent_mode = parent.lstat()
        if (
            not stat.S_ISDIR(parent_mode.st_mode)
            or parent_mode.st_uid != os.getuid()
            or parent_mode.st_mode & 0o077
        ):
            raise ValueError("INTAKE_PRIVATE_DIRECTORY_REQUIRED")
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        self._check_private_file()
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS intake_window (
                    scope TEXT PRIMARY KEY, window_id INTEGER NOT NULL, used INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intake_fingerprint (
                    fingerprint TEXT PRIMARY KEY,
                    last_seen_epoch INTEGER NOT NULL,
                    replay_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intake_checkpoint (
                    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                    last_epoch INTEGER NOT NULL,
                    profile TEXT NOT NULL
                );
                """
            )

    def _check_private_file(self) -> None:
        parent_mode = self.path.parent.lstat()
        if (
            not stat.S_ISDIR(parent_mode.st_mode)
            or parent_mode.st_uid != os.getuid()
            or parent_mode.st_mode & 0o077
        ):
            raise ValueError("INTAKE_PRIVATE_DIRECTORY_REQUIRED")
        file_mode = self.path.lstat()
        if (
            not stat.S_ISREG(file_mode.st_mode)
            or file_mode.st_uid != os.getuid()
            or file_mode.st_mode & 0o077
            or file_mode.st_nlink != 1
        ):
            raise ValueError("INTAKE_PRIVATE_DATABASE_REQUIRED")

    @staticmethod
    def _validate_request(request: RateStoreRequest) -> None:
        from .public_intake_abuse import _validate_rate_store_request

        _validate_rate_store_request(request)

    def reserve(self, request: RateStoreRequest) -> RateStoreResult:
        from .public_intake_abuse import RateStoreResult, RateStoreStatus

        self._validate_request(request)
        self._check_private_file()
        window_id = request.now_epoch // request.window_seconds
        bucket_scope = (
            "bucket:" + hashlib.sha256(request.bucket_key.encode()).hexdigest()
        )
        profile = json.dumps(
            (
                request.window_seconds,
                request.bucket_limit,
                request.global_quota,
                request.duplicate_window_seconds,
                request.duplicate_limit,
                request.duplicate_capacity,
            ),
            separators=(",", ":"),
        )
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                checkpoint = db.execute(
                    "SELECT last_epoch,profile FROM intake_checkpoint WHERE singleton=1"
                ).fetchone()
                if checkpoint is None:
                    # An older populated store has no reliable clock/config history.
                    # An operator must provision a new empty store before enabling it.
                    if (
                        db.execute("SELECT 1 FROM intake_window LIMIT 1").fetchone()
                        or db.execute(
                            "SELECT 1 FROM intake_fingerprint LIMIT 1"
                        ).fetchone()
                    ):
                        raise ValueError("INTAKE_RATE_CHECKPOINT_MISSING")
                    db.execute(
                        "INSERT INTO intake_checkpoint VALUES(1,?,?)",
                        (request.now_epoch, profile),
                    )
                else:
                    last_epoch, stored_profile = checkpoint
                    if stored_profile != profile:
                        raise ValueError("INTAKE_RATE_PROFILE_CHANGED")
                    if request.now_epoch < last_epoch:
                        raise ValueError("INTAKE_CLOCK_ROLLBACK")
                    db.execute(
                        "UPDATE intake_checkpoint SET last_epoch=? WHERE singleton=1",
                        (request.now_epoch,),
                    )
                global_row = db.execute(
                    "SELECT window_id,used FROM intake_window WHERE scope='global'"
                ).fetchone()
                if global_row is not None and global_row[0] > window_id:
                    raise ValueError("INTAKE_CLOCK_ROLLBACK")
                if global_row is not None and global_row[0] < window_id:
                    db.execute("DELETE FROM intake_window")
                    global_row = None

                db.execute(
                    "DELETE FROM intake_fingerprint WHERE last_seen_epoch <= ?",
                    (request.now_epoch - request.duplicate_window_seconds,),
                )
                global_used = global_row[1] if global_row is not None else 0
                bucket_row = db.execute(
                    "SELECT used FROM intake_window WHERE scope=?", (bucket_scope,)
                ).fetchone()
                if global_used >= request.global_quota:
                    return RateStoreResult(RateStoreStatus.GLOBAL_QUOTA)
                if bucket_row is not None and bucket_row[0] >= request.bucket_limit:
                    return RateStoreResult(RateStoreStatus.BUCKET_LIMIT)

                for scope in ("global", bucket_scope):
                    db.execute(
                        "INSERT INTO intake_window(scope,window_id,used) VALUES(?,?,1) "
                        "ON CONFLICT(scope) DO UPDATE SET used=used+1",
                        (scope, window_id),
                    )
                existing = db.execute(
                    "SELECT replay_count FROM intake_fingerprint WHERE fingerprint=?",
                    (request.fingerprint,),
                ).fetchone()
                if existing is not None:
                    replay_count = existing[0] + 1
                    db.execute(
                        "UPDATE intake_fingerprint SET last_seen_epoch=?,replay_count=? "
                        "WHERE fingerprint=?",
                        (request.now_epoch, replay_count, request.fingerprint),
                    )
                    status = (
                        RateStoreStatus.DUPLICATE_BURST
                        if replay_count > request.duplicate_limit
                        else RateStoreStatus.REPLAY
                    )
                else:
                    db.execute(
                        "INSERT INTO intake_fingerprint VALUES(?,?,0)",
                        (request.fingerprint, request.now_epoch),
                    )
                    status = RateStoreStatus.RESERVED
                excess = db.execute(
                    "SELECT COUNT(*) FROM intake_fingerprint"
                ).fetchone()[0]
                if excess > request.duplicate_capacity:
                    db.execute(
                        "DELETE FROM intake_fingerprint WHERE fingerprint IN "
                        "(SELECT fingerprint FROM intake_fingerprint "
                        "ORDER BY last_seen_epoch,fingerprint LIMIT ?)",
                        (excess - request.duplicate_capacity,),
                    )
                return RateStoreResult(status)
