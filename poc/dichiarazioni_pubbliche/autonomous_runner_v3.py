"""DP-413B: durable, private execution of the existing publication policy.

The capture, challenge, two reviewers and public-surface adapters retain their
independent authority. This module owns only the restart-safe event journal
and input-bound scheduling. The DB does not grant rights or publication power.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations, RunReceipt
from dichiarazioni_pubbliche.autonomous_publication import candidate_fingerprint


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _secure_file(path: Path) -> None:
    """Create private storage without following a symlink."""
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_mode & 0o077):
            raise ValueError("DP413B_UNSAFE_RUNTIME_STORAGE")
    finally:
        os.close(fd)


class SQLiteRunJournal:
    """Immutable, hash-linked event history and one replaceable run checkpoint."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ValueError("DP413B_RUNTIME_PATH_INVALID")
        _secure_file(self.path)
        _secure_file(self.lock_path)
        with closing(self._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS autonomous_run_event (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    previous_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS autonomous_event_no_update
                    BEFORE UPDATE ON autonomous_run_event
                    BEGIN SELECT RAISE(ABORT, 'immutable autonomous event'); END;
                CREATE TRIGGER IF NOT EXISTS autonomous_event_no_delete
                    BEFORE DELETE ON autonomous_run_event
                    BEGIN SELECT RAISE(ABORT, 'immutable autonomous event'); END;
                CREATE TABLE IF NOT EXISTS autonomous_run_checkpoint (
                    record_id TEXT PRIMARY KEY NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomous_review_execution (
                    provider_request_id TEXT PRIMARY KEY NOT NULL,
                    evidence_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS autonomous_review_no_update
                    BEFORE UPDATE ON autonomous_review_execution
                    BEGIN SELECT RAISE(ABORT, 'immutable review execution'); END;
                CREATE TRIGGER IF NOT EXISTS autonomous_review_no_delete
                    BEFORE DELETE ON autonomous_review_execution
                    BEGIN SELECT RAISE(ABORT, 'immutable review execution'); END;
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, isolation_level=None, timeout=120)
        db.execute("PRAGMA busy_timeout=120000")
        return db

    @contextmanager
    def locked(self) -> Iterator[None]:
        fd = os.open(self.lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            st = os.fstat(fd)
            if st.st_uid != os.getuid() or st.st_mode & 0o077 or not stat.S_ISREG(st.st_mode):
                raise ValueError("DP413B_RUN_LOCK_UNSAFE")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @staticmethod
    def _serialize(event: RunReceipt) -> str:
        return _json({
            "record_id": event.record_id,
            "disposition": event.disposition,
            "evidence_sha256": event.evidence_sha256,
            "reason_codes": list(event.reason_codes),
            "at": event.at.isoformat(),
        })

    @staticmethod
    def _deserialize(payload: str) -> RunReceipt:
        value = json.loads(payload)
        return RunReceipt(
            value["record_id"], value["disposition"], value["evidence_sha256"],
            tuple(value["reason_codes"]), datetime.fromisoformat(value["at"]),
        )

    def append(self, event: RunReceipt) -> None:
        payload = self._serialize(event)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT event_sha256 FROM autonomous_run_event ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
                previous = row[0] if row else "0" * 64
                digest = hashlib.sha256((previous + payload).encode()).hexdigest()
                db.execute("""
                    INSERT INTO autonomous_run_event
                        (record_id, disposition, event_json, previous_sha256, event_sha256)
                    VALUES (?, ?, ?, ?, ?)
                """, (event.record_id, event.disposition, payload, previous, digest))
                db.commit()
            except Exception:
                db.rollback()
                raise

    def events(self, record_id: str) -> tuple[RunReceipt, ...]:
        with closing(self._connect()) as db:
            rows = db.execute("""
                SELECT record_id, event_json, previous_sha256, event_sha256
                FROM autonomous_run_event ORDER BY event_id
            """).fetchall()
        previous = "0" * 64
        result = []
        for stored_id, payload, prev, digest in rows:
            if prev != previous or hashlib.sha256((prev + payload).encode()).hexdigest() != digest:
                raise ValueError("DP413B_EVENT_LEDGER_INTEGRITY_FAILURE")
            previous = digest
            if stored_id == record_id:
                result.append(self._deserialize(payload))
        return tuple(result)

    def append_review(self, receipt: dict[str, object]) -> None:
        """Persist actual gateway identity before a model verdict can be used."""
        request_id = receipt.get("provider_request_id")
        evidence_sha = receipt.get("evidence_sha256")
        if (not isinstance(request_id, str) or not request_id.strip()
                or not isinstance(evidence_sha, str) or len(evidence_sha) != 64):
            raise ValueError("DP413B_REVIEW_RECEIPT_INVALID")
        payload = _json(receipt)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with closing(self._connect()) as db:
            try:
                db.execute("""
                    INSERT INTO autonomous_review_execution
                        (provider_request_id, evidence_sha256, receipt_json, receipt_sha256)
                    VALUES (?, ?, ?, ?)
                """, (request_id, evidence_sha, payload, digest))
            except sqlite3.IntegrityError as exc:
                raise ValueError("DP413B_DUPLICATE_PROVIDER_REQUEST_ID") from exc

    def review_executions(self, evidence_sha: str) -> tuple[dict[str, object], ...]:
        with closing(self._connect()) as db:
            rows = db.execute("""
                SELECT receipt_json, receipt_sha256 FROM autonomous_review_execution
                WHERE evidence_sha256=? ORDER BY rowid
            """, (evidence_sha,)).fetchall()
        result = []
        for payload, digest in rows:
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise ValueError("DP413B_REVIEW_LEDGER_INTEGRITY_FAILURE")
            result.append(json.loads(payload))
        return tuple(result)

    def checkpoint(self, record_id: str) -> tuple[str, RunReceipt] | None:
        with closing(self._connect()) as db:
            row = db.execute("""
                SELECT input_sha256, event_sha256, receipt_json
                FROM autonomous_run_checkpoint WHERE record_id=?
            """, (record_id,)).fetchone()
        if row is None:
            return None
        expected, event_sha, payload = row
        with closing(self._connect()) as db:
            present = db.execute(
                "SELECT 1 FROM autonomous_run_event WHERE event_sha256=? AND event_json=?",
                (event_sha, payload),
            ).fetchone()
        if not present:
            raise ValueError("DP413B_CHECKPOINT_ORPHAN")
        # Validate the entire append-only chain before accepting an old approval.
        self.events(record_id)
        return expected, self._deserialize(payload)

    def complete(self, key: str, event: RunReceipt) -> None:
        payload = self._serialize(event)
        with closing(self._connect()) as db:
            row = db.execute("""
                SELECT event_sha256 FROM autonomous_run_event
                WHERE record_id=? AND event_json=? ORDER BY event_id DESC LIMIT 1
            """, (event.record_id, payload)).fetchone()
            if row is None:
                raise ValueError("DP413B_UNJOURNALED_RESULT")
            db.execute("""
                INSERT INTO autonomous_run_checkpoint
                    (record_id, input_sha256, event_sha256, receipt_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    input_sha256=excluded.input_sha256,
                    event_sha256=excluded.event_sha256,
                    receipt_json=excluded.receipt_json
            """, (event.record_id, key, row[0], payload))


class PersistentRunner:
    """On each tick, retry only new evidence, changed challenge or lost visibility."""

    def __init__(self, operations: AutonomousOperations, journal: SQLiteRunJournal):
        if operations.journal is not journal:
            raise ValueError("DP413B_JOURNAL_AUTHORITY_MISMATCH")
        self.operations = operations
        self.journal = journal

    def _input(self, record_id: str, provider_revision: str) -> str:
        try:
            candidate = self.operations.capture.current(record_id)
            binding = candidate_fingerprint(candidate) if candidate is not None else None
        except (Exception,):
            binding = None
        try:
            challenge = self.operations.challenge.current(record_id)
            challenge_state = str(challenge) if type(challenge) is bool else "UNKNOWN"
        except Exception:
            challenge_state = "UNKNOWN"
        reviewers = []
        for reviewer in (self.operations.first, self.operations.second):
            reviewers.append((getattr(reviewer, "agent_id", None),
                              getattr(reviewer, "model_id", None)))
        return hashlib.sha256(_json({
            "record": record_id, "evidence": binding, "challenge": challenge_state,
            "reviewers": reviewers, "provider_revision": provider_revision,
        }).encode()).hexdigest()

    def run(self, record_id: str, *, now: datetime, provider_revision: str = "") -> RunReceipt:
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("AUTONOMOUS_RECORD_ID_REQUIRED")
        if not isinstance(provider_revision, str) or len(provider_revision) > 256:
            raise ValueError("DP413B_PROVIDER_REVISION_INVALID")
        with self.journal.locked():
            key = self._input(record_id, provider_revision)
            prior = self.journal.checkpoint(record_id)
            if prior is not None and prior[0] == key:
                receipt = prior[1]
                try:
                    visible = self.operations.surface.current_evidence_sha256(record_id)
                except Exception:
                    visible = object()
                if ((receipt.disposition == "HOLD" and visible is None)
                        or (receipt.disposition == "PUBLISH"
                            and receipt.evidence_sha256 is not None
                            and visible == receipt.evidence_sha256)):
                    return receipt
            receipt = self.operations.evaluate_and_apply(record_id, now=now)
            self.journal.complete(key, receipt)
            return receipt
