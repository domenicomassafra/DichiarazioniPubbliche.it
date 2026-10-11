"""DP-516 local durable append-only batch checkpoint CAS.

No acquisition, LLM, quota reservation or pilot/publication authority.
The supplied capture verifier is an external caller obligation: a mocked
verifier is only synthetic functional evidence, never a signed receipt.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from dichiarazioni_pubbliche.historical_batch_gate_v1 import (
    BatchCheckpoint, CompletedCapture, create_checkpoint,
)


class SQLiteHistoricalCheckpointStore:
    """Single-batch CAS with immutable version history across process restart."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError("DP516_JOURNAL_SYMLINK_REFUSED")
        if not self.path.exists():
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        info = self.path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("DP516_JOURNAL_FILE_UNSAFE")
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS historical_checkpoint_version(
                    batch_id TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision>=1),
                    document TEXT NOT NULL,
                    PRIMARY KEY (batch_id,revision)
                );
                CREATE TRIGGER IF NOT EXISTS historical_checkpoint_no_update
                BEFORE UPDATE ON historical_checkpoint_version BEGIN
                    SELECT RAISE(ABORT, 'immutable batch checkpoint');
                END;
                CREATE TRIGGER IF NOT EXISTS historical_checkpoint_no_delete
                BEFORE DELETE ON historical_checkpoint_version BEGIN
                    SELECT RAISE(ABORT, 'immutable batch checkpoint');
                END;
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=3)
        connection.execute("PRAGMA busy_timeout=3000")
        return connection

    @staticmethod
    def _decode(raw: str) -> BatchCheckpoint:
        data = json.loads(raw)
        completed = tuple(CompletedCapture(**item) for item in data["completed"])
        observed = BatchCheckpoint(
            data["batch_id"], data["manifest_fingerprint"], completed,
            data["revision"], data["failed"], data["integrity_sha256"],
            data["version"],
        )
        expected = create_checkpoint(
            observed.batch_id, observed.manifest_fingerprint, observed.completed,
            revision=observed.revision, failed=observed.failed,
        )
        if observed != expected:
            raise ValueError("DP516_CHECKPOINT_STORED_TAMPERED")
        return observed

    @staticmethod
    def _latest(connection: sqlite3.Connection, batch_id: str) -> BatchCheckpoint | None:
        row = connection.execute(
            "SELECT document FROM historical_checkpoint_version "
            "WHERE batch_id=? ORDER BY revision DESC LIMIT 1", (batch_id,),
        ).fetchone()
        return SQLiteHistoricalCheckpointStore._decode(row[0]) if row else None

    def read(self, batch_id: str) -> BatchCheckpoint | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                result = self._latest(connection, batch_id)
                connection.execute("COMMIT")
                return result
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def commit_capture(
        self, *, batch_id: str, manifest_fingerprint: str, expected_revision: int,
        capture: CompletedCapture,
        verify_persisted_capture: Callable[[CompletedCapture], bool] | None,
    ) -> BatchCheckpoint:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("DP516_CHECKPOINT_REVISION_INVALID")
        # Validate source-bound shapes before any operation touching journal.
        create_checkpoint(batch_id, manifest_fingerprint, (capture,), revision=1)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                latest = self._latest(connection, batch_id)
                revision = latest.revision if latest else 0
                if revision != expected_revision:
                    raise ValueError("DP516_CHECKPOINT_REVISION_CONFLICT")
                if latest and latest.manifest_fingerprint != manifest_fingerprint:
                    raise ValueError("DP516_CHECKPOINT_MANIFEST_MISMATCH")
                if latest and latest.failed:
                    raise ValueError("DP516_CHECKPOINT_FAILED_HELD")
                prior = {r.item_key: r for r in latest.completed} if latest else {}
                if capture.item_key in prior:
                    if prior[capture.item_key] != capture:
                        raise ValueError("DP516_CHECKPOINT_CAPTURE_CONFLICT")
                    connection.execute("COMMIT")
                    return latest
                if not callable(verify_persisted_capture):
                    raise ValueError("DP516_CAPTURE_NOT_ATTESTED")
                try:
                    verified = verify_persisted_capture(capture) is True
                except Exception:
                    verified = False
                if not verified:
                    raise ValueError("DP516_CAPTURE_NOT_ATTESTED")
                completed = tuple(sorted((*prior.values(), capture),
                                         key=lambda row: row.item_key))
                result = create_checkpoint(batch_id, manifest_fingerprint,
                                           completed, revision=revision + 1)
                payload = json.dumps(asdict(result), sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True)
                connection.execute(
                    "INSERT INTO historical_checkpoint_version(batch_id,revision,document) "
                    "VALUES (?,?,?)", (batch_id, result.revision, payload),
                )
                connection.execute("COMMIT")
                return result
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def revision_count(self, batch_id: str) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM historical_checkpoint_version WHERE batch_id=?",
                (batch_id,),
            ).fetchone()[0])


__all__ = ["SQLiteHistoricalCheckpointStore"]
