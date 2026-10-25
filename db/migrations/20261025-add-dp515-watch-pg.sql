-- DP-515 / #370: private watcher lease and canonical held-review queue boundary.
-- Apply only after schema.v1.sql, job_queue.v1.sql and DP-514 monthly migration.
CREATE TABLE IF NOT EXISTS dp515_watch_source (
    source_id text PRIMARY KEY REFERENCES source(id),
    content_id text NOT NULL REFERENCES content_item(id),
    policy_json jsonb NOT NULL,
    policy_sha text NOT NULL CHECK (policy_sha ~ '^[0-9a-f]{64}$'),
    state_json jsonb NOT NULL,
    state_sha text NOT NULL CHECK (state_sha ~ '^[0-9a-f]{64}$'),
    gate_json jsonb NOT NULL,
    gate_revision integer NOT NULL DEFAULT 0 CHECK (gate_revision >= 0)
);
CREATE TABLE IF NOT EXISTS dp515_watch_attempt (
    source_id text NOT NULL REFERENCES dp515_watch_source(source_id),
    attempt_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('IN_FLIGHT','COMMITTED','ABANDONED')),
    planning_gate_revision integer NOT NULL,
    prior_state_json jsonb NOT NULL,
    planning_gate_json jsonb NOT NULL,
    plan_json jsonb NOT NULL,
    lease_expires_at timestamptz NOT NULL,
    observation_json jsonb,
    reconciliation_gate_json jsonb,
    decision_json jsonb,
    PRIMARY KEY (source_id, attempt_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS dp515_one_active_poll
    ON dp515_watch_attempt(source_id) WHERE status='IN_FLIGHT';

CREATE OR REPLACE FUNCTION dp515_authority_reason(p_source dp515_watch_source)
RETURNS text LANGUAGE plpgsql VOLATILE AS $$
BEGIN
    IF p_source.policy_json->>'enabled' <> 'true'
       OR p_source.gate_json->>'source_id' IS DISTINCT FROM p_source.source_id
       OR p_source.gate_json->>'corpus_id' IS DISTINCT FROM p_source.policy_json->>'corpus_id'
       OR p_source.gate_json->>'policy_fingerprint' IS DISTINCT FROM p_source.policy_sha
    THEN RETURN 'GATE_SCOPE_MISMATCH';
    END IF;
    IF p_source.gate_json->>'rights_status' IS DISTINCT FROM 'READY'
       OR NOT EXISTS (
           SELECT 1
           FROM private_source_rights_record r
           JOIN content_item c ON c.id=p_source.content_id
           WHERE r.id=p_source.gate_json->>'rights_receipt'
             AND r.content_id=p_source.content_id
             AND c.source_id=p_source.source_id
             AND r.source_family=p_source.policy_json->>'source_family'
             AND r.locator_kind='URL'
             AND r.locator_value=c.canonical_url
             AND r.locator_value=p_source.policy_json->>'locator_id'
             AND r.rights_status='CLEARED'
             AND r.reviewed_at IS NOT NULL
             AND r.reviewed_at<=now()
             AND (r.expires_at IS NULL OR r.expires_at>now())
             AND r.permitted_uses @> ARRAY['FETCH']::text[]
             AND NOT EXISTS (
                 SELECT 1 FROM private_source_rights_record successor
                 WHERE successor.supersedes_id=r.id
             )
       )
    THEN RETURN 'RIGHTS_NOT_READY';
    END IF;
    IF p_source.gate_json->>'capability_status' IS DISTINCT FROM 'READY'
       OR COALESCE(p_source.gate_json->>'capability_receipt','')=''
    THEN RETURN 'CAPABILITY_NOT_READY';
    END IF;
    IF p_source.gate_json->>'budget_status' IS DISTINCT FROM 'READY'
       OR NOT EXISTS (
           SELECT 1 FROM dp514_monthly_dispatch_policy b
           WHERE b.approval_ref=p_source.gate_json->>'budget_receipt'
             AND b.active=true AND b.cap_eur>0
             AND b.quota_remaining_attempts>0
             AND b.quota_valid_until>now()
             AND b.fx_asof>=current_date
             AND b.period=to_char(now() AT TIME ZONE b.accounting_tz,'YYYY-MM')
             AND COALESCE((
                 SELECT sum(m.upper_bound_eur)
                 FROM dp514_monthly_dispatch_reservation m
                 WHERE m.period=b.period
             ),0) < b.cap_eur
             AND (
                 SELECT count(*)
                 FROM dp514_monthly_dispatch_reservation m
                 WHERE m.period=b.period
             ) < b.quota_remaining_attempts
       )
    THEN RETURN 'BUDGET_NOT_READY';
    END IF;
    -- DP-514's unknown-billing fence: a monthly policy cannot grant
    -- source-watch admission when provider liabilities are unaccounted for.
    IF EXISTS (
        SELECT 1 FROM provider_receipt r
        WHERE NOT EXISTS (
            SELECT 1 FROM worker_budget_reservation h
            JOIN dp514_monthly_dispatch_reservation m
              ON (m.job_id,m.attempt)=(h.job_id,h.attempt)
            WHERE h.receipt_id=r.id
        )
    ) OR EXISTS (
        SELECT 1 FROM provider_receipt r
        JOIN worker_budget_reservation h ON h.receipt_id=r.id
        JOIN dp514_monthly_dispatch_reservation m
          ON (m.job_id,m.attempt)=(h.job_id,h.attempt)
        WHERE r.billing_basis NOT IN
            ('MEASURED_PROVIDER_COST','ESTIMATED_ONLY')
          OR COALESCE(
                CASE WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                     THEN r.measured_cost_usd
                     ELSE r.estimated_cost_usd END, -1
             )>h.upper_bound_usd
    ) THEN RETURN 'BUDGET_NOT_READY';
    END IF;
    IF COALESCE((p_source.gate_json->>'remaining_children')::integer,0)
       < COALESCE((p_source.policy_json->>'max_children')::integer,1)
    THEN RETURN 'CAP_EXHAUSTED';
    END IF;
    RETURN NULL;
END;
$$;

-- Rights records are append-only. Appending a new current/revoked version
-- fences in-flight plans by changing the watched source gate epoch while
-- holding the same source lock used by begin/commit.
CREATE OR REPLACE FUNCTION dp515_rights_append_epoch()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE dp515_watch_source
    SET gate_revision=gate_revision+1
    WHERE content_id=NEW.content_id
      AND policy_json->>'source_family'=NEW.source_family;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS dp515_rights_append_epoch_trg
    ON private_source_rights_record;
CREATE TRIGGER dp515_rights_append_epoch_trg
AFTER INSERT ON private_source_rights_record
FOR EACH ROW EXECUTE FUNCTION dp515_rights_append_epoch();

CREATE OR REPLACE FUNCTION dp515_begin_watch(
    p_source_id text, p_attempt_id text, p_state_sha text,
    p_gate_revision integer, p_plan jsonb, p_lease_until timestamptz
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE src dp515_watch_source%ROWTYPE;
        old dp515_watch_attempt%ROWTYPE;
        reason text;
BEGIN
    IF p_lease_until <= clock_timestamp()
       OR p_lease_until > clock_timestamp()+interval '86400 seconds'
    THEN RETURN 'LEASE_DURATION_INVALID'; END IF;
    SELECT * INTO src FROM dp515_watch_source
      WHERE source_id=p_source_id FOR UPDATE;
    IF NOT FOUND THEN RETURN 'SOURCE_NOT_REGISTERED'; END IF;
    IF src.state_sha<>p_state_sha OR src.gate_revision<>p_gate_revision
       OR (src.state_json->>'revision')::integer <>
          (p_plan->>'state_revision')::integer
    THEN RETURN 'CAS_LOST'; END IF;
    reason := dp515_authority_reason(src);
    IF reason IS NOT NULL THEN RETURN reason; END IF;
    SELECT * INTO old FROM dp515_watch_attempt
      WHERE source_id=p_source_id AND attempt_id=p_attempt_id FOR UPDATE;
    IF FOUND THEN
        IF old.status='IN_FLIGHT' AND old.plan_json=p_plan
           AND old.lease_expires_at=p_lease_until
           AND old.planning_gate_revision=p_gate_revision
        THEN RETURN 'REPLAY'; END IF;
        RETURN 'REPLAY_CONFLICT';
    END IF;
    IF EXISTS (
       SELECT 1 FROM dp515_watch_attempt
       WHERE source_id=p_source_id AND status='IN_FLIGHT'
    ) THEN RETURN 'ATTEMPT_IN_FLIGHT'; END IF;
    INSERT INTO dp515_watch_attempt (
        source_id,attempt_id,status,planning_gate_revision,
        prior_state_json,planning_gate_json,plan_json,lease_expires_at
    ) VALUES (
        p_source_id,p_attempt_id,'IN_FLIGHT',p_gate_revision,
        src.state_json,src.gate_json,p_plan,p_lease_until
    );
    RETURN 'STARTED';
END;
$$;

CREATE OR REPLACE FUNCTION dp515_commit_watch(
    p_source_id text, p_attempt_id text, p_state_sha text,
    p_gate_revision integer, p_next_state jsonb, p_next_sha text,
    p_observation jsonb, p_decision jsonb,
    p_job_id text, p_payload jsonb
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE src dp515_watch_source%ROWTYPE;
        attempt dp515_watch_attempt%ROWTYPE;
        reason text;
        canonical processing_job%ROWTYPE;
BEGIN
    SELECT * INTO src FROM dp515_watch_source
      WHERE source_id=p_source_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'WATCH_PG_SOURCE_NOT_REGISTERED'; END IF;
    SELECT * INTO attempt FROM dp515_watch_attempt
      WHERE source_id=p_source_id AND attempt_id=p_attempt_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'WATCH_PG_ATTEMPT_NOT_STARTED'; END IF;
    IF attempt.status='COMMITTED' THEN RETURN 'ALREADY_COMMITTED'; END IF;
    IF attempt.status<>'IN_FLIGHT' THEN
        RAISE EXCEPTION 'WATCH_PG_LEASE_NOT_ACTIVE';
    END IF;
    IF src.state_sha<>p_state_sha OR src.gate_revision<>p_gate_revision
       OR src.state_json<>attempt.prior_state_json
    THEN RAISE EXCEPTION 'WATCH_PG_CAS_LOST'; END IF;
    IF clock_timestamp()>=attempt.lease_expires_at THEN
        RAISE EXCEPTION 'WATCH_PG_LEASE_EXPIRED';
    END IF;
    IF (p_observation->>'observed_at')::timestamptz >= attempt.lease_expires_at
       OR (p_observation->>'observed_at')::timestamptz <
          (attempt.plan_json->>'attempted_at')::timestamptz
    THEN RAISE EXCEPTION 'WATCH_PG_LEASE_EXPIRED'; END IF;
    IF (p_next_state->>'revision')::integer <>
       (src.state_json->>'revision')::integer + 1
       OR p_next_state->>'source_id' IS DISTINCT FROM p_source_id
       OR p_decision->'next_state' IS DISTINCT FROM p_next_state
    THEN RAISE EXCEPTION 'WATCH_PG_DECISION_INVALID'; END IF;
    reason := dp515_authority_reason(src);
    IF p_job_id IS NOT NULL THEN
        IF reason IS NOT NULL THEN
            RAISE EXCEPTION 'WATCH_PG_%', reason;
        END IF;
        IF p_decision->>'disposition' <> 'CHANGED'
           OR jsonb_array_length(p_decision->'children')<>1
           OR p_decision->'children'->0->>'work_key' IS DISTINCT FROM p_job_id
           OR p_payload->>'source_id' IS DISTINCT FROM p_source_id
           OR p_payload->>'attempt_id' IS DISTINCT FROM p_attempt_id
        THEN RAISE EXCEPTION 'WATCH_PG_JOB_BINDING_INVALID'; END IF;
    ELSIF jsonb_array_length(p_decision->'children')<>0 THEN
        RAISE EXCEPTION 'WATCH_PG_MISSING_REVIEW_JOB';
    END IF;
    UPDATE dp515_watch_source SET state_json=p_next_state,state_sha=p_next_sha
      WHERE source_id=p_source_id AND state_sha=p_state_sha
        AND gate_revision=p_gate_revision;
    IF NOT FOUND THEN RAISE EXCEPTION 'WATCH_PG_CAS_LOST'; END IF;
    UPDATE dp515_watch_attempt SET status='COMMITTED',
      observation_json=p_observation, reconciliation_gate_json=src.gate_json,
      decision_json=p_decision
      WHERE source_id=p_source_id AND attempt_id=p_attempt_id AND status='IN_FLIGHT';
    IF p_job_id IS NOT NULL THEN
        -- The canonical job is deliberately held for private review.
        -- worker_daemon cannot claim BLOCKED jobs or dispatch a provider.
        INSERT INTO processing_job
          (id,content_id,job_type,state,last_error,payload)
        VALUES (p_job_id,src.content_id,'SOURCE_REVALIDATION_REVIEW',
                'BLOCKED','PRIVATE_SOURCE_REVIEW_REQUIRED',p_payload)
        ON CONFLICT(id) DO NOTHING;
        SELECT * INTO canonical FROM processing_job WHERE id=p_job_id;
        IF canonical.content_id IS DISTINCT FROM src.content_id
           OR canonical.job_type<>'SOURCE_REVALIDATION_REVIEW'
           OR canonical.payload IS DISTINCT FROM p_payload
           OR canonical.state<>'BLOCKED'
        THEN RAISE EXCEPTION 'WATCH_PG_CANONICAL_JOB_CONFLICT'; END IF;
    END IF;
    RETURN 'COMMITTED';
END;
$$;
