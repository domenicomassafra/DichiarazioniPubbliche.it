"""DP-515 PostgreSQL watch CAS and atomic held-review canonical queue adapter.

Opt-in and source-exact. Existing PostgreSQL rights and DP-514 monthly
policy are read inside the SQL admission/commit transactions. A changed
source creates a BLOCKED private-review job, never a paid-provider dispatch.
No HTTP, scheduler, live DB migration, or public action is performed here.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchDecision, WatchObservation, WatchPlan, WatchPolicy, WatchReadiness,
    WatchState, _gate_reason, _utc, _validate_state, plan_watch_poll,
    policy_fingerprint, reconcile_watch_observation,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.source_watch_store_v1 import _json, _sha, _unpack


class PostgresSourceWatchStore(PsqlRuntime):
    """One PostgreSQL source lease with a CAS-fenced, blocked review queue job."""

    def _read_source(
        self, source_id: str
    ) -> tuple[WatchPolicy, WatchState, WatchReadiness, int, str]:
        raw = self.run(
            """SELECT json_build_object(
                'policy',policy_json,'state',state_json,'gate',gate_json,
                'gate_revision',gate_revision,'state_sha',state_sha
                )::text FROM dp515_watch_source WHERE source_id=:'source_id'""",
            source_id=source_id,
        )
        if not raw:
            raise ValueError("WATCH_PG_SOURCE_NOT_REGISTERED")
        row = json.loads(raw)
        policy = _unpack(WatchPolicy, _json(row["policy"]))
        state = _unpack(WatchState, _json(row["state"]))
        gate = _unpack(WatchReadiness, _json(row["gate"]))
        fingerprint = policy_fingerprint(policy)
        _validate_state(policy, state, fingerprint)
        if (
            policy.source_id != source_id
            or state.source_id != source_id
            or gate.source_id != source_id
            or gate.corpus_id != policy.corpus_id
            or gate.policy_fingerprint != fingerprint
            or row["state_sha"] != _sha(_json(asdict(state)))
        ):
            raise ValueError("WATCH_PG_PERSISTED_BINDING_INVALID")
        return policy, state, gate, row["gate_revision"], row["state_sha"]

    def _read_attempt(self, source_id: str, attempt_id: str) -> dict:
        raw = self.run(
            """SELECT json_build_object(
                 'status',status,'planning_gate_revision',planning_gate_revision,
                 'prior_state',prior_state_json,'planning_gate',planning_gate_json,
                 'plan',plan_json,'lease',lease_expires_at,
                 'observation',observation_json,'decision',decision_json
                )::text FROM dp515_watch_attempt
                WHERE source_id=:'source_id' AND attempt_id=:'attempt_id'""",
            source_id=source_id, attempt_id=attempt_id,
        )
        if not raw:
            raise ValueError("WATCH_PG_ATTEMPT_NOT_STARTED")
        return json.loads(raw)

    def _authority(self, source_id: str) -> str:
        return self.run(
            """SELECT COALESCE(dp515_authority_reason(src),'READY')
               FROM dp515_watch_source src WHERE source_id=:'source_id'""",
            source_id=source_id,
        )

    @staticmethod
    def _run_or_value_error(call):
        try:
            return call()
        except RuntimeError as exc:
            message = str(exc)
            if "WATCH_PG_" in message:
                raise ValueError(message[message.index("WATCH_PG_"):]) from exc
            raise

    def register_source(
        self, policy: WatchPolicy, state: WatchState,
        gate: WatchReadiness, *, content_id: str,
    ) -> None:
        fingerprint = policy_fingerprint(policy)
        _validate_state(policy, state, fingerprint)
        if (
            gate.source_id != policy.source_id
            or gate.corpus_id != policy.corpus_id
            or gate.policy_fingerprint != fingerprint
        ):
            raise ValueError("WATCH_PG_GATE_SCOPE_MISMATCH")
        if not isinstance(content_id, str) or not content_id:
            raise ValueError("WATCH_PG_CONTENT_REQUIRED")
        state_raw = _json(asdict(state))
        raw = self.run(
            """WITH inserted AS (
                 INSERT INTO dp515_watch_source
                   (source_id,content_id,policy_json,policy_sha,
                    state_json,state_sha,gate_json)
                 SELECT :'source_id',c.id,:'policy'::jsonb,:'fingerprint',
                        :'state'::jsonb,:'sha',:'gate'::jsonb
                 FROM content_item c WHERE c.id=:'content_id'
                   AND c.source_id=:'source_id'
                 ON CONFLICT (source_id) DO NOTHING RETURNING source_id
               ) SELECT count(*)::text FROM inserted""",
            source_id=policy.source_id, content_id=content_id,
            policy=_json(asdict(policy)), fingerprint=fingerprint,
            state=state_raw, sha=_sha(state_raw), gate=_json(asdict(gate)),
        )
        if raw != "1":
            raise ValueError("WATCH_PG_SOURCE_NOT_REGISTERABLE")

    def read_state(self, source_id: str) -> WatchState:
        return self._read_source(source_id)[1]

    def update_readiness(
        self, gate: WatchReadiness, *, expected_gate_revision: int,
    ) -> int:
        if type(expected_gate_revision) is not int or expected_gate_revision < 0:
            raise ValueError("WATCH_PG_GATE_REVISION_INVALID")
        policy, _, _, _, _ = self._read_source(gate.source_id)
        if (
            gate.policy_fingerprint != policy_fingerprint(policy)
            or gate.corpus_id != policy.corpus_id
        ):
            raise ValueError("WATCH_PG_GATE_SCOPE_MISMATCH")
        raw = self.run(
            """WITH updated AS (
                 UPDATE dp515_watch_source
                 SET gate_json=:'gate'::jsonb,
                     gate_revision=gate_revision+1
                 WHERE source_id=:'source_id'
                   AND gate_revision=:'expected'::integer
                 RETURNING gate_revision
               ) SELECT gate_revision::text FROM updated""",
            gate=_json(asdict(gate)), source_id=gate.source_id,
            expected=expected_gate_revision,
        )
        if not raw:
            raise ValueError("WATCH_PG_GATE_REVISION_CONFLICT")
        return int(raw)

    def begin_poll(
        self, source_id: str, *, attempt_id: str,
        attempted_at: datetime, lease_seconds: int = 300,
    ) -> WatchPlan:
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 86400:
            raise ValueError("WATCH_PG_LEASE_DURATION_INVALID")
        admitted_at = _utc(attempted_at, "ATTEMPTED_AT")
        assert admitted_at is not None
        policy, state, gate, revision, state_sha = self._read_source(source_id)
        plan = plan_watch_poll(
            policy, state, gate, attempt_id=attempt_id, attempted_at=admitted_at,
        )
        if not plan.allowed:
            return plan
        # Only the PG source rights record and active DP-514 policy can admit.
        reason = self._authority(source_id)
        if reason != "READY":
            return replace(plan, allowed=False, reason=reason)
        outcome = self._run_or_value_error(lambda: self.run(
            """SELECT dp515_begin_watch(
                 :'source_id',:'attempt_id',:'sha',:'revision'::integer,
                 :'plan'::jsonb,:'expiry'::timestamptz)""",
            source_id=source_id, attempt_id=attempt_id, sha=state_sha,
            revision=revision, plan=_json(asdict(plan)),
            expiry=(admitted_at+timedelta(seconds=lease_seconds)).isoformat(),
        ))
        if outcome in {"STARTED", "REPLAY"}:
            return plan
        if outcome in {"RIGHTS_NOT_READY", "CAPABILITY_NOT_READY",
                       "BUDGET_NOT_READY", "CAP_EXHAUSTED",
                       "GATE_SCOPE_MISMATCH"}:
            return replace(plan, allowed=False, reason=outcome)
        raise ValueError("WATCH_PG_" + outcome)

    def commit_observation(
        self, source_id: str, *, attempt_id: str, observation: WatchObservation,
    ) -> WatchDecision:
        policy, state, gate, revision, state_sha = self._read_source(source_id)
        row = self._read_attempt(source_id, attempt_id)
        prior = _unpack(WatchState, _json(row["prior_state"]))
        first_gate = _unpack(WatchReadiness, _json(row["planning_gate"]))
        plan = _unpack(WatchPlan, _json(row["plan"]))
        if plan_watch_poll(
            policy, prior, first_gate,
            attempt_id=attempt_id, attempted_at=plan.attempted_at,
        ) != plan:
            raise ValueError("WATCH_PG_PLAN_BINDING_MISMATCH")
        if row["status"] == "COMMITTED":
            if row["observation"] != json.loads(_json(asdict(observation))):
                raise ValueError("WATCH_PG_REPLAY_CONFLICT")
            decision = _unpack(WatchDecision, _json(row["decision"]))
            if (
                state != decision.next_state
                or revision != row["planning_gate_revision"]
                or self._authority(source_id) != "READY"
            ):
                raise ValueError("WATCH_PG_STATE_REVISION_CONFLICT")
            return decision
        if row["status"] != "IN_FLIGHT":
            raise ValueError("WATCH_PG_LEASE_NOT_ACTIVE")
        expiry = _utc(datetime.fromisoformat(row["lease"]), "LEASE_EXPIRES")
        at = _utc(observation.observed_at, "OBSERVED_AT")
        if at is None or expiry is None or at >= expiry:
            raise ValueError("WATCH_PG_LEASE_EXPIRED")
        if state != prior or state.revision != plan.state_revision:
            raise ValueError("WATCH_PG_STATE_REVISION_CONFLICT")
        if (
            revision != row["planning_gate_revision"]
            and _gate_reason(policy, gate, policy_fingerprint(policy)) is None
        ):
            raise ValueError("WATCH_PG_GATE_CHANGED")
        decision = reconcile_watch_observation(
            policy, state, gate, plan, observation,
        )
        next_json = _json(asdict(decision.next_state))
        child = decision.children[0] if decision.children else None
        job_payload = (
            _json({
                "source_id": source_id,
                "attempt_id": attempt_id,
                "proposal": asdict(child),
                "private_review_required": True,
                "provider_dispatch_authorized": False,
            })
            if child is not None else "{}"
        )
        self._run_or_value_error(lambda: self.run(
            """SELECT dp515_commit_watch(
                 :'source_id',:'attempt_id',:'sha',:'revision'::integer,
                 :'next'::jsonb,:'next_sha',:'observation'::jsonb,
                 :'decision'::jsonb,NULLIF(:'job_id',''),:'payload'::jsonb)""",
            source_id=source_id, attempt_id=attempt_id, sha=state_sha,
            revision=revision, next=next_json, next_sha=_sha(next_json),
            observation=_json(asdict(observation)),
            decision=_json(asdict(decision)),
            job_id=child.work_key if child else "", payload=job_payload,
        ))
        return decision

    def expire_stale_attempt(
        self, source_id: str, *, attempt_id: str,
        as_of: datetime, expected_state_revision: int,
        expected_gate_revision: int,
    ) -> None:
        if (
            type(expected_state_revision) is not int
            or type(expected_gate_revision) is not int
            or min(expected_state_revision, expected_gate_revision) < 0
        ):
            raise ValueError("WATCH_PG_LEASE_REVISION_INVALID")
        clock = _utc(as_of, "LEASE_AS_OF")
        assert clock is not None
        raw = self.run(
            """WITH locked AS (
                 SELECT a.source_id,a.attempt_id
                 FROM dp515_watch_source s
                 JOIN dp515_watch_attempt a ON a.source_id=s.source_id
                 WHERE s.source_id=:'source_id' AND a.attempt_id=:'attempt_id'
                   AND (s.state_json->>'revision')::integer=:'state_revision'::integer
                   AND s.gate_revision=:'gate_revision'::integer
                   AND a.status='IN_FLIGHT'
                   AND a.lease_expires_at<=LEAST(
                       :'clock'::timestamptz,clock_timestamp())
                 FOR UPDATE OF s,a
               ), retired AS (
                 UPDATE dp515_watch_attempt a SET status='ABANDONED'
                 FROM locked l WHERE a.source_id=l.source_id
                   AND a.attempt_id=l.attempt_id AND a.status='IN_FLIGHT'
                 RETURNING a.attempt_id
               ) SELECT count(*)::text FROM retired""",
            source_id=source_id, attempt_id=attempt_id,
            state_revision=expected_state_revision,
            gate_revision=expected_gate_revision, clock=clock.isoformat(),
        )
        if raw != "1":
            raise ValueError("WATCH_PG_LEASE_CAS_CONFLICT")
