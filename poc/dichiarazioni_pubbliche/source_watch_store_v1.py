"""DP-515 opt-in durable *private fixture* watch attempt and proposal ledger.

SQLite is an isolated transactional rehearsal, not the canonical production
database, external rights authority, fetch client, worker scheduler or queue.
The caller supplies observations and independently sourced rights/cost gates.
No operation sends HTTP, materializes a child job or authorizes publication.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, fields
from datetime import datetime, timedelta, timezone

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchChildProposal,
    WatchDecision,
    WatchObservation,
    WatchPlan,
    WatchPolicy,
    WatchReadiness,
    WatchState,
    _gate_reason,
    _utc,
    _validate_state,
    plan_watch_poll,
    policy_fingerprint,
    reconcile_watch_observation,
)


_DEFAULT_LEASE_SECONDS = 300
_MAX_LEASE_SECONDS = 86400


def _json(value: object) -> str:
    def encode(value: object) -> str:
        if not isinstance(value, datetime):
            raise TypeError("unsupported watch material")
        return value.astimezone(timezone.utc).isoformat()

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=encode,
        allow_nan=False,
    )


def _sha(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _unpack(cls, body: str) -> object:
    data = json.loads(body)
    if not isinstance(data, dict) or set(data) != {field.name for field in fields(cls)}:
        raise ValueError("WATCH_STORE_PERSISTED_RECORD_INVALID")
    if cls in {WatchPlan, WatchObservation, WatchState}:
        for key in (
            "attempted_at",
            "observed_at",
            "last_attempted_at",
            "last_successful_observed_at",
            "retry_not_before",
        ):
            if key in data:
                data[key] = _datetime(data[key])
    if cls is WatchPlan:
        data["conditional_headers"] = tuple(
            tuple(item) for item in data["conditional_headers"]
        )
    if cls is WatchDecision:
        data["next_state"] = _unpack(WatchState, _json(data["next_state"]))
        data["children"] = tuple(WatchChildProposal(**row) for row in data["children"])
    return cls(**data)


class LocalSourceWatchStore:
    """SQLite serialized source watch state+attempts with no child-job authority."""

    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection):
            raise ValueError("WATCH_STORE_SQLITE_REQUIRED")
        self.connection = connection

    def init_isolated_fixture_schema(self) -> None:
        if self.connection.in_transaction:
            raise ValueError("WATCH_STORE_ACTIVE_TRANSACTION")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS dp515_watch_source (
                source_id TEXT PRIMARY KEY,
                policy_json TEXT NOT NULL, policy_sha256 TEXT NOT NULL,
                state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL,
                gate_json TEXT NOT NULL, gate_revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dp515_watch_attempt (
                source_id TEXT NOT NULL REFERENCES dp515_watch_source(source_id),
                attempt_id TEXT NOT NULL, status TEXT NOT NULL
                    CHECK(status IN ('IN_FLIGHT', 'COMMITTED', 'ABANDONED')),
                planning_gate_revision INTEGER NOT NULL,
                prior_state_json TEXT NOT NULL, planning_gate_json TEXT NOT NULL,
                plan_json TEXT NOT NULL, plan_sha256 TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                observation_json TEXT, reconciliation_gate_json TEXT,
                decision_json TEXT,
                PRIMARY KEY(source_id, attempt_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS dp515_single_active_source_attempt
                ON dp515_watch_attempt(source_id) WHERE status='IN_FLIGHT';
            CREATE TABLE IF NOT EXISTS dp515_watch_proposal (
                work_key TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL, proposal_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('HELD_PRIVATE_PROPOSAL', 'WITHDRAWN')),
                FOREIGN KEY(source_id, attempt_id)
                    REFERENCES dp515_watch_attempt(source_id, attempt_id)
            );
            """
        )
        self.connection.execute("PRAGMA foreign_keys=ON")
        # This is a disposable fixture schema. Do not silently reinterpret
        # pre-lease attempts as expirable after a code upgrade.
        columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(dp515_watch_attempt)")
        }
        if "lease_expires_at" not in columns:
            raise ValueError("WATCH_STORE_FIXTURE_SCHEMA_RECREATE_REQUIRED")

    def _begin(self) -> None:
        if self.connection.in_transaction:
            raise ValueError("WATCH_STORE_ACTIVE_TRANSACTION")
        self.connection.execute("BEGIN IMMEDIATE")

    def _source(
        self, source_id: str
    ) -> tuple[WatchPolicy, WatchState, WatchReadiness, int]:
        row = self.connection.execute(
            "SELECT policy_json, policy_sha256, state_json, state_sha256, "
            "gate_json, gate_revision FROM dp515_watch_source WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if row is None:
            raise ValueError("WATCH_STORE_SOURCE_NOT_REGISTERED")
        policy_json, policy_sha, state_json, state_sha, gate_json, gate_revision = row
        try:
            policy = _unpack(WatchPolicy, policy_json)
            state = _unpack(WatchState, state_json)
            gate = _unpack(WatchReadiness, gate_json)
            fingerprint = policy_fingerprint(policy)
            if (
                policy.source_id != source_id
                or fingerprint != policy_sha
                or _sha(state_json) != state_sha
                or state.source_id != source_id
            ):
                raise ValueError("WATCH_STORE_POLICY_FINGERPRINT_MISMATCH")
            _validate_state(policy, state, fingerprint)
            if (
                gate.source_id != source_id
                or gate.corpus_id != policy.corpus_id
                or gate.policy_fingerprint != fingerprint
                or type(gate_revision) is not int
                or gate_revision < 0
            ):
                raise ValueError("WATCH_STORE_GATE_SCOPE_MISMATCH")
        except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError("WATCH_STORE_PERSISTED_RECORD_INVALID") from exc
        return policy, state, gate, gate_revision

    def register_fixture_source(
        self, policy: WatchPolicy, state: WatchState, gate: WatchReadiness
    ) -> None:
        """Seed an opt-in source; READY strings are *fixture* inputs, not proofs."""
        fingerprint = policy_fingerprint(policy)
        _validate_state(policy, state, fingerprint)
        if (
            gate.source_id != policy.source_id
            or gate.corpus_id != policy.corpus_id
            or gate.policy_fingerprint != fingerprint
        ):
            raise ValueError("WATCH_STORE_GATE_SCOPE_MISMATCH")
        self._begin()
        try:
            if self.connection.execute(
                "SELECT 1 FROM dp515_watch_source WHERE source_id=?",
                (policy.source_id,),
            ).fetchone():
                existing, _, _, _ = self._source(policy.source_id)
                if existing != policy:
                    raise ValueError("WATCH_STORE_POLICY_SCOPE_MISMATCH")
                raise ValueError("WATCH_STORE_SOURCE_ALREADY_REGISTERED")
            saved_state = _json(asdict(state))
            self.connection.execute(
                "INSERT INTO dp515_watch_source "
                "(source_id, policy_json, policy_sha256, state_json, state_sha256, gate_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    policy.source_id,
                    _json(asdict(policy)),
                    fingerprint,
                    saved_state,
                    _sha(saved_state),
                    _json(asdict(gate)),
                ),
            )
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def read_state(self, source_id: str) -> WatchState:
        return self._source(source_id)[1]

    def update_fixture_readiness(
        self, gate: WatchReadiness, *, expected_gate_revision: int
    ) -> int:
        """CAS fixture gate. A rights/capability/budget hold retires proposals."""
        if type(expected_gate_revision) is not int or expected_gate_revision < 0:
            raise ValueError("WATCH_STORE_GATE_REVISION_INVALID")
        self._begin()
        try:
            policy, _, _, revision = self._source(gate.source_id)
            if (
                gate.source_id != policy.source_id
                or gate.policy_fingerprint != policy_fingerprint(policy)
                or gate.corpus_id != policy.corpus_id
            ):
                raise ValueError("WATCH_STORE_GATE_SCOPE_MISMATCH")
            if revision != expected_gate_revision:
                raise ValueError("WATCH_STORE_GATE_REVISION_CONFLICT")
            updated = self.connection.execute(
                "UPDATE dp515_watch_source SET gate_json=?, gate_revision=gate_revision+1 "
                "WHERE source_id=? AND gate_revision=?",
                (_json(asdict(gate)), gate.source_id, expected_gate_revision),
            )
            if updated.rowcount != 1:
                raise ValueError("WATCH_STORE_GATE_REVISION_CONFLICT")
            if _gate_reason(policy, gate, policy_fingerprint(policy)) is not None:
                self.connection.execute(
                    "UPDATE dp515_watch_proposal SET status='WITHDRAWN' "
                    "WHERE source_id=? AND status='HELD_PRIVATE_PROPOSAL'",
                    (gate.source_id,),
                )
            self.connection.commit()
            return revision + 1
        except BaseException:
            self.connection.rollback()
            raise

    def begin_poll(
        self,
        source_id: str,
        *,
        attempt_id: str,
        attempted_at: datetime,
        lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    ) -> WatchPlan:
        """Atomically pin one planned HTTP operation; performs no HTTP itself."""
        if (
            type(lease_seconds) is not int
            or not 1 <= lease_seconds <= _MAX_LEASE_SECONDS
        ):
            raise ValueError("WATCH_STORE_LEASE_DURATION_INVALID")
        admitted_at = _utc(attempted_at, "ATTEMPTED_AT")
        assert admitted_at is not None
        expiry = admitted_at + timedelta(seconds=lease_seconds)
        self._begin()
        try:
            policy, state, gate, gate_revision = self._source(source_id)
            existing = self.connection.execute(
                "SELECT plan_json, plan_sha256, planning_gate_json, "
                "prior_state_json, status, planning_gate_revision, lease_expires_at "
                "FROM dp515_watch_attempt WHERE source_id=? AND attempt_id=?",
                (source_id, attempt_id),
            ).fetchone()
            if existing is not None:
                (
                    raw,
                    digest,
                    raw_gate,
                    raw_state,
                    status,
                    initial_revision,
                    old_expiry,
                ) = existing
                plan = _unpack(WatchPlan, raw)
                previous = _unpack(WatchState, raw_state)
                initial_gate = _unpack(WatchReadiness, raw_gate)
                if (
                    _sha(raw) != digest
                    or plan.attempted_at != admitted_at
                    or _utc(_datetime(old_expiry), "LEASE_EXPIRY") != expiry
                    or plan_watch_poll(
                        policy,
                        previous,
                        initial_gate,
                        attempt_id=attempt_id,
                        attempted_at=plan.attempted_at,
                    )
                    != plan
                ):
                    raise ValueError("WATCH_STORE_REPLAY_CONFLICT")
                if status != "IN_FLIGHT" or state != previous:
                    raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
                if (
                    initial_revision != gate_revision
                    or _gate_reason(policy, gate, policy_fingerprint(policy))
                    is not None
                ):
                    raise ValueError("WATCH_STORE_GATE_CHANGED")
                self.connection.commit()
                return plan
            if self.connection.execute(
                "SELECT 1 FROM dp515_watch_attempt "
                "WHERE source_id=? AND status='IN_FLIGHT'",
                (source_id,),
            ).fetchone():
                raise ValueError("WATCH_STORE_ATTEMPT_IN_FLIGHT")
            plan = plan_watch_poll(
                policy,
                state,
                gate,
                attempt_id=attempt_id,
                attempted_at=attempted_at,
            )
            if plan.allowed:
                raw = _json(asdict(plan))
                self.connection.execute(
                    "INSERT INTO dp515_watch_attempt "
                    "(source_id, attempt_id, status, planning_gate_revision, "
                    "prior_state_json, planning_gate_json, plan_json, plan_sha256, "
                    "lease_expires_at) "
                    "VALUES (?, ?, 'IN_FLIGHT', ?, ?, ?, ?, ?, ?)",
                    (
                        source_id,
                        attempt_id,
                        gate_revision,
                        _json(asdict(state)),
                        _json(asdict(gate)),
                        raw,
                        _sha(raw),
                        expiry.isoformat(),
                    ),
                )
            self.connection.commit()
            return plan
        except BaseException:
            self.connection.rollback()
            raise

    def commit_observation(
        self, source_id: str, *, attempt_id: str, observation: WatchObservation
    ) -> WatchDecision:
        """Reconcile supplied observation under current rights and state CAS."""
        self._begin()
        try:
            policy, state, gate, gate_revision = self._source(source_id)
            row = self.connection.execute(
                "SELECT status, planning_gate_revision, prior_state_json, "
                "planning_gate_json, plan_json, "
                "plan_sha256, observation_json, reconciliation_gate_json, decision_json, "
                "lease_expires_at "
                "FROM dp515_watch_attempt "
                "WHERE source_id=? AND attempt_id=?",
                (source_id, attempt_id),
            ).fetchone()
            if row is None:
                raise ValueError("WATCH_STORE_ATTEMPT_NOT_STARTED")
            (
                status,
                initial_gate_revision,
                old_state_json,
                first_gate_json,
                plan_json,
                plan_hash,
                observed,
                prior_reconciliation_gate,
                saved,
                lease_expiry,
            ) = row
            prior = _unpack(WatchState, old_state_json)
            first_gate = _unpack(WatchReadiness, first_gate_json)
            plan = _unpack(WatchPlan, plan_json)
            if (
                _sha(plan_json) != plan_hash
                or plan_watch_poll(
                    policy,
                    prior,
                    first_gate,
                    attempt_id=attempt_id,
                    attempted_at=plan.attempted_at,
                )
                != plan
            ):
                raise ValueError("WATCH_STORE_PLAN_BINDING_MISMATCH")
            payload = _json(asdict(observation))
            if status == "COMMITTED":
                if payload != observed:
                    raise ValueError("WATCH_STORE_REPLAY_CONFLICT")
                if _gate_reason(policy, gate, policy_fingerprint(policy)) is not None:
                    raise ValueError("WATCH_STORE_RIGHTS_NOT_READY")
                result = _unpack(WatchDecision, saved)
                if state != result.next_state:
                    raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
                if initial_gate_revision != gate_revision:
                    raise ValueError("WATCH_STORE_GATE_CHANGED")
                replayed = reconcile_watch_observation(
                    policy,
                    prior,
                    _unpack(WatchReadiness, prior_reconciliation_gate),
                    plan,
                    observation,
                )
                if result != replayed:
                    raise ValueError("WATCH_STORE_REPLAY_BINDING_MISMATCH")
                self.connection.commit()
                return result
            observed_at = _utc(observation.observed_at, "OBSERVED_AT")
            if observed_at is None or observed_at >= _utc(
                _datetime(lease_expiry), "LEASE_EXPIRY"
            ):
                raise ValueError("WATCH_STORE_LEASE_EXPIRED")
            if (
                status != "IN_FLIGHT"
                or state != prior
                or plan.state_revision != state.revision
            ):
                raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
            if (
                gate_revision != initial_gate_revision
                and _gate_reason(policy, gate, policy_fingerprint(policy)) is None
            ):
                raise ValueError("WATCH_STORE_GATE_CHANGED")
            result = reconcile_watch_observation(
                policy,
                state,
                gate,
                plan,
                observation,
            )
            old_sha = _sha(_json(asdict(state)))
            next_json = _json(asdict(result.next_state))
            changed = self.connection.execute(
                "UPDATE dp515_watch_source SET state_json=?, state_sha256=? "
                "WHERE source_id=? AND state_sha256=?",
                (next_json, _sha(next_json), source_id, old_sha),
            )
            if changed.rowcount != 1:
                raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
            self.connection.execute(
                "UPDATE dp515_watch_attempt SET status='COMMITTED', observation_json=?, "
                "reconciliation_gate_json=?, decision_json=? "
                "WHERE source_id=? AND attempt_id=? AND status='IN_FLIGHT'",
                (
                    payload,
                    _json(asdict(gate)),
                    _json(asdict(result)),
                    source_id,
                    attempt_id,
                ),
            )
            for child in result.children:
                # A private, permanently non-dispatchable proposal, *not* a job.
                self.connection.execute(
                    "INSERT OR IGNORE INTO dp515_watch_proposal "
                    "(work_key, source_id, attempt_id, proposal_json, status) "
                    "VALUES (?, ?, ?, ?, 'HELD_PRIVATE_PROPOSAL')",
                    (child.work_key, source_id, attempt_id, _json(asdict(child))),
                )
            self.connection.commit()
            return result
        except BaseException:
            self.connection.rollback()
            raise

    def committed_attempt_count(self, source_id: str) -> int:
        return self.connection.execute(
            "SELECT COUNT(*) FROM dp515_watch_attempt "
            "WHERE source_id=? AND status='COMMITTED'",
            (source_id,),
        ).fetchone()[0]

    def expire_stale_attempt(
        self,
        source_id: str,
        *,
        attempt_id: str,
        as_of: datetime,
        expected_state_revision: int,
        expected_gate_revision: int,
    ) -> None:
        """CAS-retire a crashed fixture poll after its immutable lease deadline.

        The caller supplies an independently verified clock/readback. This only
        frees a local attempt slot; it never claims a fetch, observation, cost,
        downstream job, or successful freshness update.
        """
        if (
            type(expected_state_revision) is not int
            or expected_state_revision < 0
            or type(expected_gate_revision) is not int
            or expected_gate_revision < 0
        ):
            raise ValueError("WATCH_STORE_LEASE_REVISION_INVALID")
        now = _utc(as_of, "LEASE_AS_OF")
        assert now is not None
        self._begin()
        try:
            _, state, _, gate_revision = self._source(source_id)
            if state.revision != expected_state_revision:
                raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
            if gate_revision != expected_gate_revision:
                raise ValueError("WATCH_STORE_GATE_REVISION_CONFLICT")
            row = self.connection.execute(
                "SELECT status, lease_expires_at FROM dp515_watch_attempt "
                "WHERE source_id=? AND attempt_id=?",
                (source_id, attempt_id),
            ).fetchone()
            if row is None or row[0] != "IN_FLIGHT":
                raise ValueError("WATCH_STORE_LEASE_NOT_ACTIVE")
            if now < _utc(_datetime(row[1]), "LEASE_EXPIRY"):
                raise ValueError("WATCH_STORE_LEASE_NOT_EXPIRED")
            updated = self.connection.execute(
                "UPDATE dp515_watch_attempt SET status='ABANDONED' "
                "WHERE source_id=? AND attempt_id=? AND status='IN_FLIGHT' "
                "AND lease_expires_at=?",
                (source_id, attempt_id, row[1]),
            )
            if updated.rowcount != 1:
                raise ValueError("WATCH_STORE_LEASE_NOT_ACTIVE")
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def abandon_stale_attempt(
        self,
        source_id: str,
        *,
        attempt_id: str,
        expected_state_revision: int,
        expected_gate_revision: int,
    ) -> None:
        """Release an obsolete gate-epoch reservation, retaining attempt history.

        Only an attempt whose planning gate revision was superseded can be
        abandoned. Requires the current state and gate revisions; it does not
        assert observation, charge a cost, advance freshness or mint proposals.
        """
        if (
            type(expected_state_revision) is not int
            or expected_state_revision < 0
            or type(expected_gate_revision) is not int
            or expected_gate_revision < 0
        ):
            raise ValueError("WATCH_STORE_ABANDON_REVISION_INVALID")
        self._begin()
        try:
            _, state, _, gate_revision = self._source(source_id)
            if state.revision != expected_state_revision:
                raise ValueError("WATCH_STORE_STATE_REVISION_CONFLICT")
            if gate_revision != expected_gate_revision:
                raise ValueError("WATCH_STORE_GATE_REVISION_CONFLICT")
            row = self.connection.execute(
                "SELECT status, planning_gate_revision FROM dp515_watch_attempt "
                "WHERE source_id=? AND attempt_id=?",
                (source_id, attempt_id),
            ).fetchone()
            if row is None or row[0] != "IN_FLIGHT" or row[1] == gate_revision:
                raise ValueError("WATCH_STORE_ABANDON_NOT_STALE")
            updated = self.connection.execute(
                "UPDATE dp515_watch_attempt SET status='ABANDONED' "
                "WHERE source_id=? AND attempt_id=? AND status='IN_FLIGHT' "
                "AND planning_gate_revision!=?",
                (source_id, attempt_id, gate_revision),
            )
            if updated.rowcount != 1:
                raise ValueError("WATCH_STORE_ABANDON_NOT_STALE")
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def private_proposals(self, source_id: str) -> tuple[WatchChildProposal, ...]:
        """Read HELD private suggestions only if gates still READY; no dispatch."""
        policy, _, gate, _ = self._source(source_id)
        if _gate_reason(policy, gate, policy_fingerprint(policy)) is not None:
            return ()
        rows = self.connection.execute(
            "SELECT proposal_json FROM dp515_watch_proposal "
            "WHERE source_id=? AND status='HELD_PRIVATE_PROPOSAL' ORDER BY work_key",
            (source_id,),
        ).fetchall()
        return tuple(_unpack(WatchChildProposal, row[0]) for row in rows)


__all__ = ["LocalSourceWatchStore"]
