"""DP-240 local durable SQLite ledger for *private* mixed-Person batch receipts.

Stores a validated immutable plan and at most one terminal observation per
isolated Passage, with a unique retry/idempotency key and transactional revision
CAS. Existing pure reconciler and receipt index remain authoritative for result
semantics. Persisted observations are caller claims, NOT proof that a provider,
human reviewer, source-rights authority or publication workflow approved them.
There is deliberately no dispatch, provider call or public projection here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from dichiarazioni_pubbliche.multi_person_batch_v1 import (
    IsolatedBatchItem,
    IsolatedBatchPlan,
    PrivateBatchItemReceipt,
    PrivateBatchReadback,
    PrivateBatchReceiptIndex,
    PrivateBatchResult,
    _validate_isolated_plan,
    build_private_batch_receipt_index,
    lookup_private_batch_item_receipt,
    reconcile_isolated_private_results,
)
from dichiarazioni_pubbliche.private_candidate_batch import MAX_ITEMS


STORE_VERSION = "dp240-private-batch-sqlite-v1"
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS dp240_plans (
    plan_sha256 TEXT PRIMARY KEY NOT NULL,
    schema_version TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)
);
CREATE TABLE IF NOT EXISTS dp240_attempts (
    plan_sha256 TEXT NOT NULL REFERENCES dp240_plans(plan_sha256),
    passage_id TEXT NOT NULL,
    attempt_key TEXT NOT NULL,
    item_json TEXT NOT NULL,
    observation_json TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    PRIMARY KEY (plan_sha256, passage_id),
    UNIQUE (plan_sha256, attempt_key)
);
"""


@dataclass(frozen=True)
class PrivateBatchAttemptReceipt:
    """Immutable item-bound input receipt; hash is an integrity check, not auth."""

    plan_sha256: str
    attempt_key: str
    item: IsolatedBatchItem
    observation: PrivateBatchResult
    receipt_sha256: str


@dataclass(frozen=True)
class PrivateBatchStoredSnapshot:
    """Restartable operator readback with no grant of public/editorial authority."""

    revision: int
    index: PrivateBatchReceiptIndex
    readback: PrivateBatchReadback
    attempts: tuple[PrivateBatchAttemptReceipt, ...]


def _encoded(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _attempt_sha(
    plan_sha256: str,
    attempt_key: str,
    item: IsolatedBatchItem,
    observation: PrivateBatchResult,
) -> str:
    return hashlib.sha256(
        _encoded(
            {
                "schema": STORE_VERSION,
                "plan_sha256": plan_sha256,
                "attempt_key": attempt_key,
                "item": asdict(item),
                "observation": asdict(observation),
            }
        ).encode("utf-8")
    ).hexdigest()


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID")
        result[key] = value
    return result


def _decode_object(payload: str, expected: set[str]) -> dict[str, object]:
    try:
        decoded = json.loads(payload, object_pairs_hook=_unique_keys)
    except (TypeError, ValueError) as exc:
        raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID") from exc
    if not isinstance(decoded, dict) or set(decoded) != expected:
        raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID")
    return decoded


class PrivateBatchSQLiteStore:
    """One file per local private operator workspace; no remote credential path.

    All mutations are serialized with BEGIN IMMEDIATE and revisions checked in
    the same transaction. A matching idempotency replay never mutates a receipt.
    FAILED/HELD/private candidate outcomes are terminal within this plan.
    Unobserved items alone may be resumed; no automatic provider retry occurs.
    """

    def __init__(self, db_path: Path):
        path = Path(db_path)
        if not path.is_absolute() or not path.parent.is_dir() or path.is_symlink():
            raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
        self.path = path

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        # Create the SQLite file with private permissions; never follow a
        # pre-existing symlink or silently accept a world-readable ledger.
        if not self.path.exists() and not readonly:
            try:
                descriptor = os.open(
                    self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600
                )
                os.close(descriptor)
            except FileExistsError:
                pass  # Another local caller created it: validate below.
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
        verified = self.path.stat()
        if not stat.S_ISREG(verified.st_mode) or verified.st_mode & 0o077:
            raise ValueError("MULTIPERSON_STORE_PERMISSIONS_INVALID")
        if readonly:
            # A pathname returned by PRAGMA database_list is NOT the inode
            # SQLite actually opened. Pin a private regular-file descriptor
            # first and open the readonly SQLite handle through that FD.
            # A concurrent rename-only replacement of the original pathname
            # cannot redirect this handle into an unrelated private ledger.
            fd = None
            try:
                fd = os.open(
                    self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                )
                pinned = os.fstat(fd)
                original_identity = (verified.st_dev, verified.st_ino)
                if (not stat.S_ISREG(pinned.st_mode)
                    or pinned.st_mode & 0o077
                    or (pinned.st_dev, pinned.st_ino) != original_identity
                    or (self.path.stat().st_dev, self.path.stat().st_ino)
                    != original_identity):
                    raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
                connection = sqlite3.connect(
                    f"file:/dev/fd/{fd}?mode=ro", uri=True,
                    isolation_level=None, timeout=5.0,
                )
            except (OSError, sqlite3.DatabaseError) as exc:
                raise ValueError("MULTIPERSON_STORE_PATH_INVALID") from exc
            finally:
                if fd is not None:
                    os.close(fd)
        else:
            connection = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        # SQLite opens the database after our pathname/mode check. A local
        # rename/symlink swap in that gap can redirect even an initially 0600
        # private ledger into a different, possibly world-readable database;
        # restoring the original pathname does not restore SQLite's handle.
        # Check the *opened main database*, not just the visible pathname,
        # before executing schema writes or reading foreign private receipts.
        try:
            main_files = [
                filename
                for _, name, filename in connection.execute("PRAGMA database_list")
                if name == "main" and filename
            ]
            if len(main_files) != 1 or self.path.is_symlink():
                raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
            current = self.path.stat()
            original_identity = (verified.st_dev, verified.st_ino)
            if (original_identity != (current.st_dev, current.st_ino)):
                raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
            if not readonly:
                # For writers, SQLite's own moved-database detection still
                # prevents a transaction after replacement of the main inode.
                # The PRAGMA path alone is not proof of an opened FD identity.
                opened = Path(main_files[0]).stat()
                if (not stat.S_ISREG(opened.st_mode)
                    or original_identity != (opened.st_dev, opened.st_ino)):
                    raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
            else:
                opened = verified
            if opened.st_mode & 0o077 or current.st_mode & 0o077:
                raise ValueError("MULTIPERSON_STORE_PERMISSIONS_INVALID")
            if readonly:
                # FD URI is deliberately independent of a pathname swap.
                # Its journal sidecar path is not the canonical DB sidecar;
                # never serve a potentially stale WAL-mode ledger snapshot.
                mode = connection.execute("PRAGMA journal_mode").fetchone()
                if not mode or mode[0] != "delete":
                    raise ValueError("MULTIPERSON_STORE_PATH_INVALID")
        except (OSError, sqlite3.DatabaseError) as exc:
            connection.close()
            raise ValueError("MULTIPERSON_STORE_PATH_INVALID") from exc
        except ValueError:
            connection.close()
            raise
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if not readonly:
            connection.executescript(_SCHEMA)
        return connection

    @staticmethod
    def _assert_plan(plan: IsolatedBatchPlan) -> str:
        _validate_isolated_plan(plan)
        return _encoded(asdict(plan))

    @staticmethod
    def _plan_row(
        connection: sqlite3.Connection, plan: IsolatedBatchPlan, serialized: str
    ) -> int:
        row = connection.execute(
            "SELECT schema_version, plan_json, revision FROM dp240_plans WHERE plan_sha256=?",
            (plan.plan_sha256,),
        ).fetchone()
        if row is None:
            raise ValueError("MULTIPERSON_STORE_BATCH_NOT_REGISTERED")
        if row[0] != STORE_VERSION or row[1] != serialized:
            raise ValueError("MULTIPERSON_STORE_PLAN_MISMATCH")
        revision = row[2]
        if type(revision) is not int or revision < 0:
            raise ValueError("MULTIPERSON_STORE_REVISION_INVALID")
        return revision

    @staticmethod
    def _read_locked(
        connection: sqlite3.Connection, plan: IsolatedBatchPlan, serialized: str
    ) -> PrivateBatchStoredSnapshot:
        revision = PrivateBatchSQLiteStore._plan_row(connection, plan, serialized)
        attempts: list[PrivateBatchAttemptReceipt] = []
        items = {item.passage_id: item for item in plan.items}
        records = connection.execute(
            "SELECT passage_id, attempt_key, item_json, observation_json, receipt_sha256 "
            "FROM dp240_attempts WHERE plan_sha256=? ORDER BY passage_id",
            (plan.plan_sha256,),
        ).fetchall()
        if revision != len(records) or len(records) > len(plan.items):
            raise ValueError("MULTIPERSON_STORE_REVISION_INVALID")
        for (
            passage_id,
            attempt_key,
            item_json,
            observation_json,
            receipt_sha256,
        ) in records:
            item = items.get(passage_id)
            if (
                item is None
                or not isinstance(attempt_key, str)
                or not _KEY.fullmatch(attempt_key)
            ):
                raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID")
            expected_item_json = _encoded(asdict(item))
            if item_json != expected_item_json:
                raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID")
            content = _decode_object(
                observation_json, {field.name for field in fields(PrivateBatchResult)}
            )
            try:
                observed = PrivateBatchResult(**content)
            except TypeError as exc:
                raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID") from exc
            if (
                (
                    observed.passage_id,
                    observed.content_id,
                    observed.capture_id,
                    observed.passage_sha256,
                )
                != (
                    item.passage_id,
                    item.content_id,
                    item.capture_id,
                    item.passage_sha256,
                )
                or observation_json != _encoded(asdict(observed))
                or receipt_sha256
                != _attempt_sha(plan.plan_sha256, attempt_key, item, observed)
            ):
                raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID")
            attempts.append(
                PrivateBatchAttemptReceipt(
                    plan.plan_sha256, attempt_key, item, observed, receipt_sha256
                )
            )
        try:
            observations = tuple(attempt.observation for attempt in attempts)
            index = build_private_batch_receipt_index(plan, observations)
            readback = reconcile_isolated_private_results(plan, observations)
        except (TypeError, ValueError) as exc:
            raise ValueError("MULTIPERSON_STORE_ATTEMPT_INTEGRITY_INVALID") from exc
        return PrivateBatchStoredSnapshot(revision, index, readback, tuple(attempts))

    def register(self, plan: IsolatedBatchPlan) -> PrivateBatchStoredSnapshot:
        """Register one immutable plan; replay is an exact, no-op readback."""
        serialized = self._assert_plan(plan)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO dp240_plans "
                "(plan_sha256, schema_version, plan_json, revision) VALUES (?, ?, ?, 0)",
                (plan.plan_sha256, STORE_VERSION, serialized),
            )
            return self._read_locked(connection, plan, serialized)

    def load_plan(self, plan_sha256: str) -> IsolatedBatchPlan:
        """Recover a canonical immutable plan using its stored fingerprint.

        A SHA is consistency evidence, not authorization to use upstream
        material or an assertion that the source/rights review remains valid.
        """
        if not isinstance(plan_sha256, str) or not _SHA.fullmatch(plan_sha256):
            raise ValueError("MULTIPERSON_STORE_PLAN_REFERENCE_INVALID")
        with closing(self._connect(readonly=True)) as connection, connection:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT schema_version, plan_json FROM dp240_plans WHERE plan_sha256=?",
                (plan_sha256,),
            ).fetchone()
            if row is None:
                raise ValueError("MULTIPERSON_STORE_BATCH_NOT_REGISTERED")
            if (
                row[0] != STORE_VERSION
                or not isinstance(row[1], str)
                or len(row[1]) > 1_048_576
            ):
                raise ValueError("MULTIPERSON_STORE_PLAN_INTEGRITY_INVALID")
            try:
                payload = _decode_object(
                    row[1], {field.name for field in fields(IsolatedBatchPlan)}
                )
                raw_items = payload["items"]
                if (
                    not isinstance(raw_items, list)
                    or not 1 <= len(raw_items) <= MAX_ITEMS
                    or any(
                        not isinstance(raw, dict)
                        or set(raw)
                        != {field.name for field in fields(IsolatedBatchItem)}
                        for raw in raw_items
                    )
                ):
                    raise ValueError("MULTIPERSON_STORE_PLAN_INTEGRITY_INVALID")
                planned = IsolatedBatchPlan(
                    **{
                        **payload,
                        "items": tuple(IsolatedBatchItem(**raw) for raw in raw_items),
                    }
                )
                if planned.plan_sha256 != plan_sha256 or row[1] != self._assert_plan(
                    planned
                ):
                    raise ValueError("MULTIPERSON_STORE_PLAN_INTEGRITY_INVALID")
            except (TypeError, ValueError) as exc:
                raise ValueError("MULTIPERSON_STORE_PLAN_INTEGRITY_INVALID") from exc
            return planned

    def resume(self, plan_sha256: str) -> PrivateBatchStoredSnapshot:
        """Read an interrupted batch with only its durable plan fingerprint."""
        return self.read(self.load_plan(plan_sha256))

    def read(self, plan: IsolatedBatchPlan) -> PrivateBatchStoredSnapshot:
        """Read only the exact plan registered in this SQLite workspace."""
        serialized = self._assert_plan(plan)
        with closing(self._connect(readonly=True)) as connection, connection:
            connection.execute("BEGIN")
            return self._read_locked(connection, plan, serialized)

    def observe(
        self,
        plan: IsolatedBatchPlan,
        item: IsolatedBatchItem,
        observation: PrivateBatchResult,
        *,
        attempt_key: str,
        expected_revision: int,
    ) -> PrivateBatchStoredSnapshot:
        """Atomically persist a single source-exact observation once.

        An identical key/observation returns the current snapshot even if its
        caller holds a stale revision. Another key or different payload cannot
        overwrite a terminal observation; callers may resume other items only.
        """
        serialized = self._assert_plan(plan)
        if not isinstance(item, IsolatedBatchItem) or item not in plan.items:
            raise ValueError("MULTIPERSON_STORE_SOURCE_BINDING_MISMATCH")
        if not isinstance(attempt_key, str) or not _KEY.fullmatch(attempt_key):
            raise ValueError("MULTIPERSON_STORE_ATTEMPT_KEY_INVALID")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("MULTIPERSON_STORE_REVISION_INVALID")
        if not isinstance(observation, PrivateBatchResult):
            raise ValueError("MULTIPERSON_RESULT_SCHEMA_INVALID")
        # These metadata fields are machine codes. Do not persist free-form
        # model output, quoted source text or failure log bodies by accident.
        for code in (observation.failure_reason, observation.extraction_version):
            if code is not None and (
                not isinstance(code, str) or not _CODE.fullmatch(code)
            ):
                raise ValueError("MULTIPERSON_STORE_PRIVATE_FIELD_INVALID")
        if (
            observation.passage_id,
            observation.content_id,
            observation.capture_id,
            observation.passage_sha256,
        ) != (
            item.passage_id,
            item.content_id,
            item.capture_id,
            item.passage_sha256,
        ):
            raise ValueError("MULTIPERSON_STORE_SOURCE_BINDING_MISMATCH")
        # Perform original per-Content/Capture/Passage status checks before
        # locking, then redo under the lock against the full persisted index.
        build_private_batch_receipt_index(plan, (observation,))
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            before = self._read_locked(connection, plan, serialized)
            by_key = {attempt.attempt_key: attempt for attempt in before.attempts}
            earlier = by_key.get(attempt_key)
            if earlier is not None:
                if earlier.item != item:
                    raise ValueError("MULTIPERSON_STORE_ATTEMPT_KEY_COLLISION")
                if earlier.observation != observation:
                    raise ValueError("MULTIPERSON_STORE_ATTEMPT_REPLAY_CONFLICT")
                return before
            if before.revision != expected_revision:
                raise ValueError("MULTIPERSON_STORE_REVISION_CONFLICT")
            if any(
                attempt.item.passage_id == item.passage_id
                for attempt in before.attempts
            ):
                raise ValueError("MULTIPERSON_STORE_ITEM_ALREADY_OBSERVED")
            # Cross-check exact source/segment/Person provenance, not just a
            # Passage id or a shared homonym. The caller cannot borrow a
            # foreign item even if its observation reuses the original id.
            match = next(
                (row for row in plan.items if row.passage_id == item.passage_id), None
            )
            if match != item:
                raise ValueError("MULTIPERSON_STORE_SOURCE_BINDING_MISMATCH")
            build_private_batch_receipt_index(
                plan,
                (observation,),
                previous_index=before.index,
            )
            receipt_sha = _attempt_sha(plan.plan_sha256, attempt_key, item, observation)
            connection.execute(
                "INSERT INTO dp240_attempts "
                "(plan_sha256, passage_id, attempt_key, item_json, observation_json, receipt_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    plan.plan_sha256,
                    item.passage_id,
                    attempt_key,
                    _encoded(asdict(item)),
                    _encoded(asdict(observation)),
                    receipt_sha,
                ),
            )
            updated = connection.execute(
                "UPDATE dp240_plans SET revision=revision+1 "
                "WHERE plan_sha256=? AND revision=?",
                (plan.plan_sha256, expected_revision),
            )
            if updated.rowcount != 1:
                raise ValueError("MULTIPERSON_STORE_REVISION_CONFLICT")
            return self._read_locked(connection, plan, serialized)

    def lookup(
        self,
        plan: IsolatedBatchPlan,
        *,
        passage_id: str,
        content_id: str,
        capture_id: str,
        source_sha256: str,
        passage_sha256: str,
        selector_fingerprint: str,
        speaker_candidate_id: str | None,
    ) -> PrivateBatchItemReceipt:
        """Operator readback requires Content, Capture, segment and Person scope."""
        snapshot = self.read(plan)
        item = lookup_private_batch_item_receipt(
            plan,
            snapshot.index,
            passage_id=passage_id,
            content_id=content_id,
            capture_id=capture_id,
            source_sha256=source_sha256,
        )
        if (
            item.passage_sha256,
            item.selector_fingerprint,
            item.speaker_candidate_id,
        ) != (passage_sha256, selector_fingerprint, speaker_candidate_id):
            raise ValueError("MULTIPERSON_STORE_SOURCE_BINDING_MISMATCH")
        return item
