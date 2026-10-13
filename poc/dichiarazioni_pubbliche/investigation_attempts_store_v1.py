"""DP-319 opt-in private SQLite investigation ledger; never dispatches work.

Source snapshots are *independently supplied* local registry facts, not proof
of rights or reviewer authority. Reservation precedes any hypothetical billed
operation. A missing completion receipt permanently fences duplicate work on
the same attempt ID; recovery requires an externally verified receipt, never a
blind retry. This adapter is not the canonical PostgreSQL runtime ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import asdict, dataclass, fields, replace
from decimal import Decimal
from pathlib import Path

from dichiarazioni_pubbliche.investigation_attempts_v1 import (
    InvestigationDecision,
    InvestigationObservation,
    InvestigationSpec,
    propose_investigation,
)
from dichiarazioni_pubbliche.research_plan import ResearchAssignment


STORE_VERSION = "dp319-private-investigation-sqlite-v1"
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_CODES = {"ALLOWED", "BLOCKED"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS dp319_source_epochs (
    need_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    record_json TEXT NOT NULL,
    checksum TEXT NOT NULL,
    PRIMARY KEY (need_id, revision)
);
CREATE TABLE IF NOT EXISTS dp319_scopes (
    plan_fingerprint TEXT PRIMARY KEY,
    scope_json TEXT NOT NULL,
    source_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)
);
CREATE TABLE IF NOT EXISTS dp319_events (
    plan_fingerprint TEXT NOT NULL REFERENCES dp319_scopes(plan_fingerprint),
    event_no INTEGER NOT NULL,
    attempt_id TEXT NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('RESERVED', 'COMPLETED')),
    event_json TEXT NOT NULL,
    checksum TEXT NOT NULL,
    PRIMARY KEY (plan_fingerprint, event_no),
    UNIQUE (plan_fingerprint, attempt_id, kind)
);
CREATE TRIGGER IF NOT EXISTS dp319_epoch_immutable_update
 BEFORE UPDATE ON dp319_source_epochs BEGIN SELECT RAISE(ABORT,'SOURCE_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS dp319_epoch_immutable_delete
 BEFORE DELETE ON dp319_source_epochs BEGIN SELECT RAISE(ABORT,'SOURCE_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS dp319_event_immutable_update
 BEFORE UPDATE ON dp319_events BEGIN SELECT RAISE(ABORT,'ATTEMPT_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS dp319_event_immutable_delete
 BEFORE DELETE ON dp319_events BEGIN SELECT RAISE(ABORT,'ATTEMPT_APPEND_ONLY'); END;
"""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for k, value in pairs:
        if k in result:
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
        result[k] = value
    return result


def _parse(raw: str, keys: set[str]) -> dict[str, object]:
    try:
        result = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, TypeError) as exc:
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
    if not isinstance(result, dict) or set(result) != keys or _json(result) != raw:
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
    return result


@dataclass(frozen=True)
class InvestigationSourceRecord:
    """A pinned external local registry observation, never self-approval."""

    need_id: str
    source_id: str
    candidate_id: str
    material_fingerprint: str
    source_version: str
    source_sha256: str
    rights_status: str
    policy_status: str
    revision: int

    def __post_init__(self) -> None:
        for value in (
            self.need_id,
            self.source_id,
            self.candidate_id,
            self.material_fingerprint,
            self.source_version,
        ):
            if not isinstance(value, str) or not _REF.fullmatch(value):
                raise ValueError("INVESTIGATION_SOURCE_REFERENCE_INVALID")
        if not isinstance(self.source_sha256, str) or not _SHA.fullmatch(
            self.source_sha256
        ):
            raise ValueError("INVESTIGATION_SOURCE_HASH_INVALID")
        if self.rights_status not in {
            "CLEARED",
            "UNKNOWN",
            "REVOKED",
            "EXPIRED",
            "DENIED",
        }:
            raise ValueError("INVESTIGATION_SOURCE_RIGHTS_INVALID")
        if (
            self.policy_status not in _CODES
            or type(self.revision) is not int
            or self.revision < 1
        ):
            raise ValueError("INVESTIGATION_SOURCE_POLICY_INVALID")


@dataclass(frozen=True)
class InvestigationReservation:
    attempt_id: str
    assignment_id: str
    lane: str
    material_fingerprint: str
    plan_fingerprint: str
    source_id: str
    candidate_id: str
    source_version: str
    source_sha256: str
    source_revision: int
    key: str
    publication_authority: bool = False
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class InvestigationStoredState:
    revision: int
    decision: InvestigationDecision
    reservations: tuple[InvestigationReservation, ...]
    observations: tuple[InvestigationObservation, ...]
    publication_authority: bool = False
    dispatch_authorized: bool = False


def _spec_json(spec: InvestigationSpec) -> dict[str, object]:
    return {**asdict(spec), "cost_cap_usd": str(spec.cost_cap_usd)}


def _assignment_json(item: ResearchAssignment) -> dict[str, object]:
    return {**asdict(item), "cost_cap_usd": str(item.cost_cap_usd)}


def _observation_json(row: InvestigationObservation) -> dict[str, object]:
    return {**asdict(row), "spent_usd": str(row.spent_usd)}


def _source_json(row: InvestigationSourceRecord) -> str:
    return _json(asdict(row))


def _scope_json(
    spec: InvestigationSpec, assignments: tuple[ResearchAssignment, ...]
) -> str:
    return _json(
        {
            "schema": STORE_VERSION,
            "spec": _spec_json(spec),
            "assignments": [_assignment_json(row) for row in assignments],
        }
    )


def _assert_inputs(
    spec: InvestigationSpec,
    assignments: tuple[ResearchAssignment, ...],
    current: InvestigationSourceRecord,
) -> str:
    if not isinstance(spec, InvestigationSpec) or not isinstance(
        current, InvestigationSourceRecord
    ):
        raise ValueError("INVESTIGATION_STORE_INPUT_INVALID")
    if (
        not isinstance(assignments, tuple)
        or not assignments
        or len(assignments) > 16
        or any(not isinstance(item, ResearchAssignment) for item in assignments)
    ):
        raise ValueError("INVESTIGATION_STORE_ASSIGNMENTS_INVALID")
    if (
        spec.need_id != current.need_id
        or spec.material_fingerprint != current.material_fingerprint
    ):
        raise ValueError("INVESTIGATION_STORE_SOURCE_STALE")
    if spec.rights_status != current.rights_status:
        raise ValueError("INVESTIGATION_STORE_SPEC_RIGHTS_MISMATCH")
    proposed = propose_investigation(
        spec=spec,
        assignments=assignments,
        observations=(),
        budget_ready=False,
        capability_ready=False,
    )
    return proposed.plan_fingerprint


def _resume_scope(raw: str) -> tuple[InvestigationSpec, tuple[ResearchAssignment, ...]]:
    payload = _parse(raw, {"schema", "spec", "assignments"})
    if payload["schema"] != STORE_VERSION:
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
    s = payload["spec"]
    assignments = payload["assignments"]
    if (
        not isinstance(s, dict)
        or set(s) != {f.name for f in fields(InvestigationSpec)}
        or not isinstance(assignments, list)
        or not 1 <= len(assignments) <= 16
        or any(
            not isinstance(a, dict)
            or set(a) != {f.name for f in fields(ResearchAssignment)}
            for a in assignments
        )
    ):
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
    try:
        spec = InvestigationSpec(**{**s, "cost_cap_usd": Decimal(s["cost_cap_usd"])})
        rows = tuple(
            ResearchAssignment(
                **{
                    **a,
                    "cost_cap_usd": Decimal(a["cost_cap_usd"]),
                    "adapter_ids": tuple(a["adapter_ids"]),
                    "stop_conditions": tuple(a["stop_conditions"]),
                    "blockers": tuple(a["blockers"]),
                }
            )
            for a in assignments
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
    if raw != _scope_json(spec, rows):
        raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
    return spec, rows


class InvestigationSQLiteStore:
    """Bounded private ledger. No model, source fetch, queue or real cost debit."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if (
            not self.path.is_absolute()
            or not self.path.parent.is_dir()
            or self.path.is_symlink()
        ):
            raise ValueError("INVESTIGATION_STORE_PATH_INVALID")

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        if not self.path.exists() and not readonly:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("INVESTIGATION_STORE_PATH_INVALID")
        if (
            not stat.S_ISREG(self.path.stat().st_mode)
            or self.path.stat().st_mode & 0o077
        ):
            raise ValueError("INVESTIGATION_STORE_PERMISSIONS_INVALID")
        conn = sqlite3.connect(
            self.path.as_uri() + "?mode=ro" if readonly else self.path,
            uri=readonly,
            isolation_level=None,
            timeout=5.0,
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        if not readonly:
            conn.executescript(_SCHEMA)
        return conn

    @staticmethod
    def _latest(conn: sqlite3.Connection, need_id: str) -> InvestigationSourceRecord:
        rows = conn.execute(
            "SELECT revision,record_json,checksum FROM dp319_source_epochs "
            "WHERE need_id=? ORDER BY revision",
            (need_id,),
        ).fetchall()
        if not rows:
            raise ValueError("INVESTIGATION_STORE_SOURCE_NOT_REGISTERED")
        latest = None
        for idx, (revision, raw, checksum) in enumerate(rows, start=1):
            if revision != idx or checksum != _hash(
                {"schema": STORE_VERSION, "source": raw}
            ):
                raise ValueError("INVESTIGATION_STORE_SOURCE_INTEGRITY_INVALID")
            data = _parse(raw, {f.name for f in fields(InvestigationSourceRecord)})
            try:
                latest = InvestigationSourceRecord(**data)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "INVESTIGATION_STORE_SOURCE_INTEGRITY_INVALID"
                ) from exc
            if (
                latest.need_id != need_id
                or latest.revision != revision
                or _source_json(latest) != raw
            ):
                raise ValueError("INVESTIGATION_STORE_SOURCE_INTEGRITY_INVALID")
        assert latest is not None
        return latest

    def record_source(
        self, record: InvestigationSourceRecord, *, expected_revision: int
    ) -> None:
        """Append a supplied independent local source/rights/policy observation.

        The caller must first have obtained this from an authorized persisted
        upstream registry. This method never decides source legality itself.
        """
        if (
            not isinstance(record, InvestigationSourceRecord)
            or type(expected_revision) is not int
        ):
            raise ValueError("INVESTIGATION_STORE_SOURCE_INVALID")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT count(*) FROM dp319_source_epochs WHERE need_id=?",
                (record.need_id,),
            ).fetchone()[0]
            if rows != expected_revision or record.revision != expected_revision + 1:
                raise ValueError("INVESTIGATION_STORE_SOURCE_REVISION_CONFLICT")
            if rows:
                earlier = self._latest(conn, record.need_id)
                if (record.source_id, record.candidate_id) != (
                    earlier.source_id,
                    earlier.candidate_id,
                ):
                    raise ValueError("INVESTIGATION_STORE_SOURCE_IDENTITY_CHANGE")
            raw = _source_json(record)
            conn.execute(
                "INSERT INTO dp319_source_epochs VALUES (?,?,?,?)",
                (
                    record.need_id,
                    record.revision,
                    raw,
                    _hash({"schema": STORE_VERSION, "source": raw}),
                ),
            )

    @staticmethod
    def _require_current(
        conn: sqlite3.Connection, current: InvestigationSourceRecord
    ) -> None:
        if (
            not isinstance(current, InvestigationSourceRecord)
            or InvestigationSQLiteStore._latest(conn, current.need_id) != current
        ):
            raise ValueError("INVESTIGATION_STORE_SOURCE_STALE")

    @staticmethod
    def _scope_row(
        conn: sqlite3.Connection, fingerprint: str, scope: str | None = None
    ) -> tuple[str, InvestigationSourceRecord, int]:
        row = conn.execute(
            "SELECT scope_json,source_json,revision FROM dp319_scopes "
            "WHERE plan_fingerprint=?",
            (fingerprint,),
        ).fetchone()
        if row is None:
            raise ValueError("INVESTIGATION_STORE_PLAN_NOT_REGISTERED")
        if scope is not None and row[0] != scope:
            raise ValueError("INVESTIGATION_STORE_PLAN_CONFLICT")
        data = _parse(row[1], {f.name for f in fields(InvestigationSourceRecord)})
        try:
            recorded = InvestigationSourceRecord(**data)
        except (TypeError, ValueError) as exc:
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
        if _source_json(recorded) != row[1] or type(row[2]) is not int or row[2] < 0:
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
        return row[0], recorded, row[2]

    @classmethod
    def _reject_cross_scope_cost_replay(
        cls, conn: sqlite3.Connection, current: InvestigationSourceRecord,
        fingerprint: str,
    ) -> None:
        """Fence prior cost reservations across scopes for one source version.

        Earlier planner versions omitted authority fields from their hash.
        Even two modern fingerprints with different time/jurisdiction scopes
        must never both reserve the same source material. No old scope is
        migrated or deleted, and this grants no permission to dispatch.
        """
        # JSON_EXTRACT filters are not sufficient: a valid SQLite JSON array
        # or a canonical object missing source_sha256 would silently fall
        # outside that predicate. Validate each persisted source record before
        # comparing the immutable source identity. Cursor iteration avoids
        # materializing the ledger and malformed older rows fail closed.
        prior_scopes = conn.execute(
            "SELECT plan_fingerprint FROM dp319_scopes ORDER BY plan_fingerprint"
        )
        source_key = (
            current.need_id, current.source_id, current.candidate_id,
            current.material_fingerprint, current.source_version,
            current.source_sha256,
        )
        for (earlier_fingerprint,) in prior_scopes:
            raw_scope, earlier_source, _ = cls._scope_row(conn, earlier_fingerprint)
            if earlier_fingerprint == fingerprint:
                continue
            prior_key = (
                earlier_source.need_id, earlier_source.source_id,
                earlier_source.candidate_id, earlier_source.material_fingerprint,
                earlier_source.source_version, earlier_source.source_sha256,
            )
            if prior_key != source_key:
                continue
            earlier_spec, earlier_assignments = _resume_scope(raw_scope)
            if _assert_inputs(
                earlier_spec, earlier_assignments, earlier_source,
            ) != earlier_fingerprint:
                # Covers both incomplete and completed legacy attempts, even
                # if the submitted new scope narrows a time/jurisdiction cap.
                raise ValueError("INVESTIGATION_STORE_LEGACY_FINGERPRINT_CONFLICT")
            # Reserved attempts remain cost-bearing even after COMPLETED;
            # scanning the append-only event ledger (rather than current
            # planner status) prevents an independent modern plan from
            # reissuing work under a different authority/time fingerprint.
            if conn.execute(
                "SELECT 1 FROM dp319_events "
                "WHERE plan_fingerprint=? AND kind='RESERVED' LIMIT 1",
                (earlier_fingerprint,),
            ).fetchone() is not None:
                raise ValueError("INVESTIGATION_STORE_SOURCE_SCOPE_ALREADY_RESERVED")

    def register(
        self,
        spec: InvestigationSpec,
        assignments: tuple[ResearchAssignment, ...],
        current: InvestigationSourceRecord,
    ) -> InvestigationStoredState:
        fingerprint = _assert_inputs(spec, assignments, current)
        if current.policy_status != "ALLOWED":
            raise ValueError("INVESTIGATION_STORE_POLICY_BLOCKED")
        scoped = _scope_json(spec, assignments)
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_current(conn, current)
            self._reject_cross_scope_cost_replay(conn, current, fingerprint)
            conn.execute(
                "INSERT OR IGNORE INTO dp319_scopes VALUES (?,?,?,0)",
                (
                    fingerprint,
                    scoped,
                    _source_json(current),
                ),
            )
            return self._state(conn, spec, assignments, current)

    def _state(
        self,
        conn: sqlite3.Connection,
        spec: InvestigationSpec,
        assignments: tuple[ResearchAssignment, ...],
        bound: InvestigationSourceRecord,
    ) -> InvestigationStoredState:
        fingerprint = _assert_inputs(spec, assignments, bound)
        _, pinned, revision = self._scope_row(
            conn, fingerprint, _scope_json(spec, assignments)
        )
        if pinned != bound:
            raise ValueError("INVESTIGATION_STORE_PLAN_CONFLICT")
        records = conn.execute(
            "SELECT event_no,attempt_id,key,kind,event_json,checksum "
            "FROM dp319_events WHERE plan_fingerprint=? ORDER BY event_no",
            (fingerprint,),
        ).fetchall()
        if len(records) != revision or len(records) > 32:
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
        reservations: dict[str, InvestigationReservation] = {}
        completed: dict[str, InvestigationObservation] = {}
        for index, (seq, attempt_id, key, kind, raw, checksum) in enumerate(
            records, start=1
        ):
            if (
                seq != index
                or not isinstance(key, str)
                or not _REF.fullmatch(key)
                or checksum
                != _hash(
                    {
                        "schema": STORE_VERSION,
                        "plan": fingerprint,
                        "seq": seq,
                        "kind": kind,
                        "payload": raw,
                    }
                )
            ):
                raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
            if kind == "RESERVED":
                data = _parse(raw, {f.name for f in fields(InvestigationReservation)})
                try:
                    reserve = InvestigationReservation(**data)
                except (ValueError, TypeError) as exc:
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
                if (
                    reserve.attempt_id != attempt_id
                    or reserve.key != key
                    or reserve.plan_fingerprint != fingerprint
                    or reserve.material_fingerprint != spec.material_fingerprint
                    or reserve.source_id != pinned.source_id
                    or reserve.candidate_id != pinned.candidate_id
                    or reserve.source_version != pinned.source_version
                    or reserve.source_sha256 != pinned.source_sha256
                    or reserve.source_revision != pinned.revision
                    or reserve.dispatch_authorized is not False
                    or reserve.publication_authority is not False
                    or reserve.assignment_id
                    not in {a.assignment_id for a in assignments}
                    or reserve.lane
                    != next(
                        a.lane
                        for a in assignments
                        if a.assignment_id == reserve.assignment_id
                    )
                    or attempt_id in reservations
                ):
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
                # Reconstruct the original pure planner *at the time of each
                # reservation*. Matching an assignment and a self-hashed JSON
                # row alone must never mint a plausible foreign attempt ID.
                if any(r.attempt_id not in completed for r in reservations.values()):
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
                expected = propose_investigation(
                    spec=spec,
                    assignments=assignments,
                    observations=tuple(completed.values()),
                    budget_ready=True,
                    capability_ready=True,
                )
                if (
                    expected.status != "READY_PRIVATE_PROPOSAL"
                    or expected.proposed_attempt_id != attempt_id
                    or expected.assignment_id != reserve.assignment_id
                ):
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
                reservations[attempt_id] = reserve
            elif kind == "COMPLETED":
                data = _parse(raw, {f.name for f in fields(InvestigationObservation)})
                try:
                    observation = InvestigationObservation(
                        **{
                            **data,
                            "spent_usd": Decimal(data["spent_usd"]),
                        }
                    )
                except (ValueError, TypeError) as exc:
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
                reserve = reservations.get(attempt_id)
                if (
                    reserve is None
                    or attempt_id in completed
                    or reserve.key != key
                    or not self._matches(reserve, observation)
                    or observation.result == "REVIEWED_SOURCE_CANDIDATE"
                    or observation.spent_usd
                    > next(
                        a.cost_cap_usd
                        for a in assignments
                        if a.assignment_id == reserve.assignment_id
                    )
                    or _json(_observation_json(observation)) != raw
                ):
                    raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
                completed[attempt_id] = observation
            else:
                raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
        records_observed = tuple(completed.values())
        try:
            result = propose_investigation(
                spec=spec,
                assignments=assignments,
                observations=records_observed,
                budget_ready=True,
                capability_ready=True,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID") from exc
        if (
            len(reservations) > spec.max_attempts
            or result.spent_usd > spec.cost_cap_usd
        ):
            raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
        # A reservation whose actual effects are unknown is always a hard
        # dedup fence; even a recreated process cannot spend a second time.
        if any(key not in completed for key in reservations):
            result = replace(
                result,
                status="WAIT_EXTERNAL",
                reason_code="INVESTIGATION_UNCONFIRMED_RESERVATION",
                proposed_attempt_id=None,
                assignment_id=None,
            )
        return InvestigationStoredState(
            revision, result, tuple(reservations.values()), records_observed
        )

    @staticmethod
    def _matches(
        reservation: InvestigationReservation, observation: InvestigationObservation
    ) -> bool:
        return (
            observation.attempt_id,
            observation.material_fingerprint,
            observation.assignment_id,
            observation.lane,
        ) == (
            reservation.attempt_id,
            reservation.material_fingerprint,
            reservation.assignment_id,
            reservation.lane,
        )

    @staticmethod
    def _append(
        conn: sqlite3.Connection,
        fingerprint: str,
        revision: int,
        attempt_id: str,
        key: str,
        kind: str,
        data: object,
    ) -> None:
        raw = _json(data)
        event_no = revision + 1
        conn.execute(
            "INSERT INTO dp319_events VALUES (?,?,?,?,?,?,?)",
            (
                fingerprint,
                event_no,
                attempt_id,
                key,
                kind,
                raw,
                _hash(
                    {
                        "schema": STORE_VERSION,
                        "plan": fingerprint,
                        "seq": event_no,
                        "kind": kind,
                        "payload": raw,
                    }
                ),
            ),
        )
        updated = conn.execute(
            "UPDATE dp319_scopes SET revision=revision+1 "
            "WHERE plan_fingerprint=? AND revision=?",
            (fingerprint, revision),
        )
        if updated.rowcount != 1:
            raise ValueError("INVESTIGATION_REVISION_CONFLICT")

    def read(
        self,
        spec: InvestigationSpec,
        assignments: tuple[ResearchAssignment, ...],
        current: InvestigationSourceRecord,
    ) -> InvestigationStoredState:
        _assert_inputs(spec, assignments, current)
        with closing(self._connect(readonly=True)) as conn, conn:
            conn.execute("BEGIN")
            self._require_current(conn, current)
            return self._state(conn, spec, assignments, current)

    def history(
        self, spec: InvestigationSpec, assignments: tuple[ResearchAssignment, ...]
    ) -> InvestigationStoredState:
        """Read prior receipts without treating a stale scope as current work."""
        if not isinstance(spec, InvestigationSpec):
            raise ValueError("INVESTIGATION_STORE_INPUT_INVALID")
        fingerprint = propose_investigation(
            spec=spec,
            assignments=assignments,
            observations=(),
            budget_ready=False,
            capability_ready=False,
        ).plan_fingerprint
        with closing(self._connect(readonly=True)) as conn, conn:
            conn.execute("BEGIN")
            _, pinned, _ = self._scope_row(
                conn, fingerprint, _scope_json(spec, assignments)
            )
            return self._state(conn, spec, assignments, pinned)

    def reserve(
        self,
        spec: InvestigationSpec,
        assignments: tuple[ResearchAssignment, ...],
        current: InvestigationSourceRecord,
        *,
        key: str,
        expected_revision: int,
    ) -> InvestigationStoredState:
        fingerprint = _assert_inputs(spec, assignments, current)
        self._inputs_mutation(key, expected_revision)
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_current(conn, current)
            state = self._state(conn, spec, assignments, current)
            earlier = next((r for r in state.reservations if r.key == key), None)
            if earlier is not None:
                return state
            # Another scope may have been registered before this one spent
            # money. Recheck under the same write lock immediately before
            # the first new reservation, not just at scope registration.
            self._reject_cross_scope_cost_replay(conn, current, fingerprint)
            if state.revision != expected_revision:
                raise ValueError("INVESTIGATION_REVISION_CONFLICT")
            if current.rights_status != "CLEARED":
                raise ValueError("INVESTIGATION_STORE_RIGHTS_BLOCKED")
            if current.policy_status != "ALLOWED":
                raise ValueError("INVESTIGATION_STORE_POLICY_BLOCKED")
            if any(
                r.attempt_id not in {o.attempt_id for o in state.observations}
                for r in state.reservations
            ):
                raise ValueError("INVESTIGATION_STORE_UNCONFIRMED_RESERVATION")
            proposal = state.decision
            if (
                proposal.status != "READY_PRIVATE_PROPOSAL"
                or proposal.proposed_attempt_id is None
            ):
                raise ValueError("INVESTIGATION_STORE_NO_READY_ATTEMPT")
            if any(
                r.attempt_id == proposal.proposed_attempt_id for r in state.reservations
            ):
                raise ValueError("INVESTIGATION_STORE_ATTEMPT_ALREADY_RESERVED")
            active = next(
                a for a in assignments if a.assignment_id == proposal.assignment_id
            )
            if proposal.spent_usd + active.cost_cap_usd > spec.cost_cap_usd:
                raise ValueError("INVESTIGATION_STORE_COST_CAP")
            receipt = InvestigationReservation(
                proposal.proposed_attempt_id,
                active.assignment_id,
                active.lane,
                spec.material_fingerprint,
                fingerprint,
                current.source_id,
                current.candidate_id,
                current.source_version,
                current.source_sha256,
                current.revision,
                key,
            )
            self._append(
                conn,
                fingerprint,
                state.revision,
                receipt.attempt_id,
                key,
                "RESERVED",
                asdict(receipt),
            )
            return self._state(conn, spec, assignments, current)

    @staticmethod
    def _inputs_mutation(key: str, expected_revision: int) -> None:
        if (
            not isinstance(key, str)
            or not _REF.fullmatch(key)
            or type(expected_revision) is not int
            or expected_revision < 0
        ):
            raise ValueError("INVESTIGATION_STORE_MUTATION_INPUT_INVALID")

    def complete(
        self,
        spec: InvestigationSpec,
        assignments: tuple[ResearchAssignment, ...],
        current: InvestigationSourceRecord,
        *,
        observation: InvestigationObservation,
        key: str,
        expected_revision: int,
    ) -> InvestigationStoredState:
        _assert_inputs(spec, assignments, current)
        self._inputs_mutation(key, expected_revision)
        if not isinstance(observation, InvestigationObservation):
            raise ValueError("INVESTIGATION_STORE_OBSERVATION_INVALID")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_current(conn, current)
            state = self._state(conn, spec, assignments, current)
            reservation = next((r for r in state.reservations if r.key == key), None)
            if reservation is None or not self._matches(reservation, observation):
                raise ValueError("INVESTIGATION_STORE_OBSERVATION_MISMATCH")
            existing = next(
                (
                    r
                    for r in state.observations
                    if r.attempt_id == reservation.attempt_id
                ),
                None,
            )
            if existing is not None:
                if existing != observation:
                    raise ValueError("INVESTIGATION_STORE_COMPLETION_REPLAY_CONFLICT")
                return state
            if state.revision != expected_revision:
                raise ValueError("INVESTIGATION_REVISION_CONFLICT")
            if current.rights_status != "CLEARED":
                raise ValueError("INVESTIGATION_STORE_RIGHTS_BLOCKED")
            if current.policy_status != "ALLOWED":
                raise ValueError("INVESTIGATION_STORE_POLICY_BLOCKED")
            if observation.result == "REVIEWED_SOURCE_CANDIDATE":
                # Self-declared model receipt is not an independently persisted
                # review/rights decision. This local store lacks that authority.
                raise ValueError("INVESTIGATION_STORE_UNVERIFIED_REVIEW")
            if any(
                (
                    observation.lineage_id,
                    observation.source_version,
                    observation.source_sha256,
                    observation.review_event_id,
                )
            ):
                raise ValueError("INVESTIGATION_STORE_UNVERIFIED_REVIEW")
            active = next(
                a for a in assignments if a.assignment_id == reservation.assignment_id
            )
            if (
                observation.spent_usd > active.cost_cap_usd
                or state.decision.spent_usd + observation.spent_usd > spec.cost_cap_usd
            ):
                raise ValueError("INVESTIGATION_STORE_COST_CAP")
            fingerprint = state.decision.plan_fingerprint
            self._append(
                conn,
                fingerprint,
                state.revision,
                reservation.attempt_id,
                key,
                "COMPLETED",
                _observation_json(observation),
            )
            return self._state(conn, spec, assignments, current)

    def resume(
        self, plan_fingerprint: str, *, source_revision: int
    ) -> InvestigationStoredState:
        """Load complete registered plan/source context after interpreter crash."""
        if not isinstance(plan_fingerprint, str) or not _SHA.fullmatch(
            plan_fingerprint
        ):
            raise ValueError("INVESTIGATION_STORE_PLAN_REFERENCE_INVALID")
        if type(source_revision) is not int or source_revision < 1:
            raise ValueError("INVESTIGATION_STORE_SOURCE_REVISION_CONFLICT")
        with closing(self._connect(readonly=True)) as conn, conn:
            conn.execute("BEGIN")
            raw_scope, bound, _ = self._scope_row(conn, plan_fingerprint)
            spec, assignments = _resume_scope(raw_scope)
            latest = self._latest(conn, bound.need_id)
            if latest != bound or latest.revision != source_revision:
                raise ValueError("INVESTIGATION_STORE_SOURCE_STALE")
            if _assert_inputs(spec, assignments, bound) != plan_fingerprint:
                raise ValueError("INVESTIGATION_STORE_INTEGRITY_INVALID")
            return self._state(conn, spec, assignments, bound)
