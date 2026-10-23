"""DP-519: durable, local PRIVATE visual-only worklist and *reported* time journal.

No HTTP role, editor, image licence or identity authority is created here.
An authenticated caller must own and authenticate any external source/actor
receipt before recording it. SQLite holds only opaque IDs, hashes, state and
reported minutes; rights refresh is an explicit compare-and-swap operation.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from dataclasses import asdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dichiarazioni_pubbliche.visual_operator_capacity_v1 import (
    VisualDecisionEvent, VisualException, VisualWorkItem, VisualCapacityReport,
    _check_work, _check_event, reconcile_visual_capacity,
)


def _serialize(value: object) -> str:
    return json.dumps(asdict(value), ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), default=lambda obj: (
                          obj.isoformat() if isinstance(obj, datetime) else obj
                      ))


def _unpack_work(value: str) -> VisualWorkItem:
    row = json.loads(value)
    for key in ("created_at", "expires_at"):
        row[key] = datetime.fromisoformat(row[key])
    row["automated_attempt_hashes"] = tuple(row["automated_attempt_hashes"])
    return VisualWorkItem(**row)


def _unpack_event(value: str) -> VisualDecisionEvent:
    row = json.loads(value)
    for key in ("started_at", "completed_at"):
        row[key] = datetime.fromisoformat(row[key])
    return VisualDecisionEvent(**row)


def _unpack_exception(value: str) -> VisualException:
    row = json.loads(value)
    row["prior_attempt_hashes"] = tuple(row["prior_attempt_hashes"])
    return VisualException(**row)


class SQLiteVisualWorklist:
    """Transactional append-only store for local, unverified operator metadata.

    It does not attest operator identity or source rights. No public reader,
    image bytes, URLs or free-text commentary is stored or served.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError("DP519_JOURNAL_SYMLINK_REFUSED")
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        info = self.path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise ValueError("DP519_JOURNAL_FILE_UNSAFE")
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS visual_work(
                    work_key TEXT PRIMARY KEY NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS visual_time_event(
                    event_id TEXT PRIMARY KEY NOT NULL,
                    work_key TEXT NOT NULL REFERENCES visual_work(work_key),
                    document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS visual_exception(
                    exception_id TEXT PRIMARY KEY NOT NULL,
                    work_key TEXT NOT NULL REFERENCES visual_work(work_key),
                    document TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS visual_exception_no_update
                BEFORE UPDATE ON visual_exception BEGIN
                    SELECT RAISE(ABORT, 'immutable visual exception');
                END;
                CREATE TRIGGER IF NOT EXISTS visual_exception_no_delete
                BEFORE DELETE ON visual_exception BEGIN
                    SELECT RAISE(ABORT, 'immutable visual exception');
                END;
                CREATE TRIGGER IF NOT EXISTS visual_event_no_update
                BEFORE UPDATE ON visual_time_event BEGIN
                    SELECT RAISE(ABORT, 'immutable visual event');
                END;
                CREATE TRIGGER IF NOT EXISTS visual_event_no_delete
                BEFORE DELETE ON visual_time_event BEGIN
                    SELECT RAISE(ABORT, 'immutable visual event');
                END;
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, isolation_level=None, timeout=3)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=3000")
        return db

    def upsert_item(self, item: VisualWorkItem, *, expected_revision: int) -> dict[str, object]:
        """Save new/current PRIVATE metadata only after explicit owner CAS.

        Source freshness, allowed images and identities are not inferred;
        the caller must supply the new independent source readback.
        """
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("DP519_WORK_REVISION_INVALID")
        _check_work(item, datetime.now(timezone.utc))
        document = _serialize(item)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT revision, document FROM visual_work WHERE work_key=?",
                                 (item.work_key,)).fetchone()
                revision = row[0] if row is not None else 0
                if revision != expected_revision:
                    raise ValueError("DP519_WORK_REVISION_CONFLICT")
                if row is not None and row[1] == document:
                    return {"work_key": item.work_key, "revision": revision,
                            "publication_authority": False}
                if row is not None:
                    previous = _unpack_work(row[1])
                    if (previous.content_id != item.content_id
                            or previous.person_id != item.person_id
                            or previous.reason_code != item.reason_code):
                        raise ValueError("DP519_WORK_IDENTITY_CONFLICT")
                    recorded = db.execute(
                        "SELECT document FROM visual_exception WHERE work_key=?",
                        (item.work_key,)
                    ).fetchall()
                    if any(
                        not set(_unpack_exception(entry[0]).prior_attempt_hashes)
                        .issubset(item.automated_attempt_hashes)
                        for entry in recorded
                    ):
                        raise ValueError("DP519_EXCEPTION_ATTEMPT_HISTORY_CONFLICT")
                revision += 1
                db.execute("INSERT INTO visual_work(work_key,revision,document) VALUES (?,?,?) "
                           "ON CONFLICT(work_key) DO UPDATE SET revision=excluded.revision,document=excluded.document",
                           (item.work_key, revision, document))
                db.execute("COMMIT")
                return {"work_key": item.work_key, "revision": revision,
                        "publication_authority": False}
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def append_reported_event(
        self, event: VisualDecisionEvent, *, expected_work_revision: int,
    ) -> dict[str, object]:
        """Durably count unverified visual time; no actor or review authority."""
        if type(expected_work_revision) is not int or expected_work_revision < 1:
            raise ValueError("DP519_WORK_REVISION_INVALID")
        document = _serialize(event)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT revision,document FROM visual_work WHERE work_key=?",
                                 (event.work_key,)).fetchone()
                if row is None:
                    raise ValueError("DP519_WORK_NOT_FOUND")
                if row[0] != expected_work_revision:
                    raise ValueError("DP519_WORK_REVISION_CONFLICT")
                item = _unpack_work(row[1])
                previous = db.execute("SELECT document FROM visual_time_event WHERE event_id=?",
                                      (event.event_id,)).fetchone()
                if previous is not None:
                    if previous[0] != document:
                        raise ValueError("DP519_EVENT_ID_CONFLICT")
                    db.execute("COMMIT")
                    return self._receipt(event)
                if event.source_version_sha256 != item.source_version_sha256:
                    raise ValueError("DP519_EVENT_SOURCE_STALE")
                now = datetime.now(timezone.utc)
                _check_event(event, item, now)
                existing = tuple(_unpack_event(x[0]) for x in db.execute(
                    "SELECT document FROM visual_time_event ORDER BY event_id").fetchall())
                work_items = tuple(_unpack_work(x[0]) for x in db.execute(
                    "SELECT document FROM visual_work ORDER BY work_key").fetchall())
                try:
                    reconcile_visual_capacity(work_items, existing + (event,), (), now=now)
                except ValueError as exc:
                    raise ValueError("DP519_EVENT_CHAIN_CONFLICT") from exc
                db.execute("INSERT INTO visual_time_event(event_id,work_key,document) VALUES (?,?,?)",
                           (event.event_id, event.work_key, document))
                db.execute("COMMIT")
                return self._receipt(event)
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def append_exception(
        self, exception: VisualException, *, expected_work_revision: int,
    ) -> dict[str, object]:
        """Persist unresolved exception estimates, never qualified approval.

        The caller must independently attest the underlying automated attempts.
        Current work revision and recorded attempts are checked atomically.
        """
        if type(expected_work_revision) is not int or expected_work_revision < 1:
            raise ValueError("DP519_WORK_REVISION_INVALID")
        if type(exception) is not VisualException:
            raise ValueError("DP519_EXCEPTION_INVALID")
        document = _serialize(exception)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT revision FROM visual_work WHERE work_key=?",
                    (exception.work_key,)
                ).fetchone()
                if row is None:
                    raise ValueError("DP519_WORK_NOT_FOUND")
                if row[0] != expected_work_revision:
                    raise ValueError("DP519_WORK_REVISION_CONFLICT")
                previous = db.execute(
                    "SELECT document FROM visual_exception WHERE exception_id=?",
                    (exception.exception_id,)
                ).fetchone()
                if previous is not None:
                    if previous[0] != document:
                        raise ValueError("DP519_EXCEPTION_ID_CONFLICT")
                    db.execute("COMMIT")
                    return self._exception_receipt(exception)
                items = tuple(_unpack_work(entry[0]) for entry in db.execute(
                    "SELECT document FROM visual_work ORDER BY work_key").fetchall())
                existing = tuple(_unpack_exception(entry[0]) for entry in db.execute(
                    "SELECT document FROM visual_exception ORDER BY exception_id").fetchall())
                reconcile_visual_capacity(
                    items, (), existing + (exception,),
                    now=datetime.now(timezone.utc),
                )
                db.execute(
                    "INSERT INTO visual_exception(exception_id,work_key,document) VALUES (?,?,?)",
                    (exception.exception_id, exception.work_key, document)
                )
                db.execute("COMMIT")
                return self._exception_receipt(exception)
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    @staticmethod
    def _exception_receipt(exception: VisualException) -> dict[str, object]:
        return {
            "exception_id": exception.exception_id,
            "work_key": exception.work_key,
            "state": "RECORDED_UNRESOLVED_EXCEPTION",
            "image_approval_authority": False,
            "text_review_authority": False,
            "publication_authority": False,
        }

    @staticmethod
    def _receipt(event: VisualDecisionEvent) -> dict[str, object]:
        return {"event_id": event.event_id, "work_key": event.work_key,
                "state": "RECORDED_UNVERIFIED_OPERATOR_TIME",
                "image_approval_authority": False, "text_review_authority": False,
                "publication_authority": False}

    def private_report(self, *, now: datetime, weekly_planning_minutes: int = 300) -> VisualCapacityReport:
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            try:
                items = tuple(_unpack_work(x[0]) for x in db.execute(
                    "SELECT document FROM visual_work ORDER BY work_key").fetchall())
                events = tuple(_unpack_event(x[0]) for x in db.execute(
                    "SELECT document FROM visual_time_event ORDER BY event_id").fetchall())
                exceptions = tuple(_unpack_exception(x[0]) for x in db.execute(
                    "SELECT document FROM visual_exception ORDER BY exception_id").fetchall())
                result = reconcile_visual_capacity(
                    items, events, exceptions, now=now,
                    weekly_planning_minutes=weekly_planning_minutes)
                db.execute("COMMIT")
                return result
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def event_count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM visual_time_event").fetchone()[0])

    def exception_count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM visual_exception").fetchone()[0])


__all__ = ["SQLiteVisualWorklist"]
