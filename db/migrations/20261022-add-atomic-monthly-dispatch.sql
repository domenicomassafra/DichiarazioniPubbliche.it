-- DP-514: conservative EUR-month envelope in the existing PostgreSQL USD
-- admission transaction. Deployment creates no spending authority: a missing
-- owner-attested policy/quota/FX always holds paid dispatch.
-- Uses the existing global advisory transaction lock (PostgreSQL License).
CREATE TABLE IF NOT EXISTS dp514_monthly_dispatch_policy (
    period text PRIMARY KEY CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    policy_version text NOT NULL CHECK (length(trim(policy_version)) > 0),
    accounting_tz text NOT NULL CHECK (accounting_tz IN ('Europe/Rome', 'UTC')),
    cap_eur numeric(12,6) NOT NULL CHECK (cap_eur > 0),
    eur_per_usd numeric(14,8) NOT NULL CHECK (eur_per_usd > 0),
    fx_source text NOT NULL CHECK (length(trim(fx_source)) > 0),
    fx_asof date NOT NULL,
    provider_id text NOT NULL CHECK (length(trim(provider_id)) > 0),
    quota_remaining_attempts integer NOT NULL CHECK (quota_remaining_attempts > 0),
    quota_valid_until timestamptz NOT NULL,
    quota_evidence_ref text NOT NULL CHECK (length(trim(quota_evidence_ref)) > 0),
    approval_ref text NOT NULL CHECK (length(trim(approval_ref)) > 0),
    active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dp514_monthly_dispatch_reservation (
    job_id text NOT NULL,
    attempt integer NOT NULL,
    period text NOT NULL REFERENCES dp514_monthly_dispatch_policy(period),
    policy_version text NOT NULL,
    provider_id text NOT NULL,
    upper_bound_eur numeric(12,6) NOT NULL CHECK (upper_bound_eur > 0),
    pinned_eur_per_usd numeric(14,8) NOT NULL CHECK (pinned_eur_per_usd > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, attempt),
    FOREIGN KEY (job_id, attempt)
        REFERENCES worker_budget_reservation(job_id, attempt)
);
CREATE INDEX IF NOT EXISTS dp514_monthly_dispatch_period_idx
    ON dp514_monthly_dispatch_reservation(period, provider_id);

-- Neither the policy nor its consumed upper bounds can be rewritten to
-- manufacture headroom; a later owner-approved revision needs an audited
-- migration/change of policy period, not a silent UPDATE.
CREATE OR REPLACE FUNCTION dp514_reject_immutable_mutation()
RETURNS trigger LANGUAGE plpgsql AS $immut$
BEGIN
    RAISE EXCEPTION 'DP514_APPEND_ONLY';
END $immut$;
DROP TRIGGER IF EXISTS dp514_policy_immutable ON dp514_monthly_dispatch_policy;
CREATE TRIGGER dp514_policy_immutable
BEFORE UPDATE OR DELETE ON dp514_monthly_dispatch_policy
FOR EACH ROW EXECUTE FUNCTION dp514_reject_immutable_mutation();
DROP TRIGGER IF EXISTS dp514_reservation_immutable
    ON dp514_monthly_dispatch_reservation;
CREATE TRIGGER dp514_reservation_immutable
BEFORE UPDATE OR DELETE ON dp514_monthly_dispatch_reservation
FOR EACH ROW EXECUTE FUNCTION dp514_reject_immutable_mutation();

-- Preserve the already-tested USD global/day/source/job transaction as a
-- native primitive and make every existing caller take this stronger gate.
DO $rename$
BEGIN
    IF to_regprocedure('reserve_worker_budget_usd(text,integer,text,text,numeric,numeric,numeric,numeric)') IS NULL THEN
        ALTER FUNCTION reserve_worker_budget(
            text, integer, text, text, numeric, numeric, numeric, numeric
        ) RENAME TO reserve_worker_budget_usd;
    END IF;
END $rename$;

CREATE OR REPLACE FUNCTION reserve_worker_budget(
    p_job_id text, p_attempt integer, p_worker text, p_source text,
    p_upper numeric, p_job_cap numeric, p_global_cap numeric, p_source_cap numeric,
    p_provider text DEFAULT ''
) RETURNS text LANGUAGE plpgsql AS $monthly$
DECLARE
    p dp514_monthly_dispatch_policy%ROWTYPE;
    candidate_count integer;
    current_provider text;
    current_job_type text;
    held_eur numeric;
    proposed_eur numeric;
    used_quota integer;
    previous_result text;
BEGIN
    -- Same lock as USD admission and receipt settlement. Locks are held until
    -- the complete EUR + USD + quota reservation transaction commits.
    PERFORM pg_advisory_xact_lock(hashtextextended('dp512:worker:global', 0));
    IF EXISTS (SELECT 1 FROM worker_budget_reservation
               WHERE job_id=p_job_id AND attempt=p_attempt) THEN
        RETURN 'BUDGET_RESERVATION_REPLAY_HELD';
    END IF;
    SELECT count(*) INTO candidate_count
    FROM dp514_monthly_dispatch_policy x
    WHERE x.period=to_char(now() AT TIME ZONE x.accounting_tz, 'YYYY-MM');
    IF candidate_count <> 1 THEN RETURN 'MONTHLY_POLICY_UNAVAILABLE'; END IF;
    SELECT * INTO p FROM dp514_monthly_dispatch_policy x
    WHERE x.period=to_char(now() AT TIME ZONE x.accounting_tz, 'YYYY-MM');
    IF NOT p.active
       OR p.fx_asof > (now() AT TIME ZONE p.accounting_tz)::date
       OR p.fx_asof < (now() AT TIME ZONE p.accounting_tz)::date - 3
        THEN RETURN 'MONTHLY_POLICY_UNATTESTED'; END IF;
    IF p.quota_valid_until <= now()
        THEN RETURN 'PROVIDER_QUOTA_EVIDENCE_EXPIRED'; END IF;
    SELECT job.payload->>'provider_id', job.job_type
    INTO current_provider, current_job_type
    FROM processing_job job WHERE job.id=p_job_id;
    IF p_provider IS NULL OR trim(p_provider) = ''
       OR p_provider IS DISTINCT FROM p.provider_id
       OR (current_job_type='TRANSCRIPT_ACQUIRE_ASR'
           AND current_provider IS DISTINCT FROM p_provider)
        THEN RETURN 'PROVIDER_QUOTA_UNATTESTED'; END IF;
    IF p_upper IS NULL OR p_upper <= 0 OR p_upper > 999999
        THEN RETURN 'JOB_COST_CAP_REACHED'; END IF;

    -- Historical or out-of-band receipts lacking a corresponding monthly
    -- reservation make the EUR exposure unknowable. Even an over-bound
    -- measured receipt cannot release the old upper bound.
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
        WHERE (r.billing_basis NOT IN
                  ('MEASURED_PROVIDER_COST','ESTIMATED_ONLY')
               OR COALESCE(
                  CASE WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                    THEN r.measured_cost_usd ELSE r.estimated_cost_usd END,
                  -1
               ) > h.upper_bound_usd)
    ) THEN RETURN 'UNKNOWN_BILLING_LIABILITY_HELD'; END IF;

    SELECT COALESCE(sum(upper_bound_eur),0), count(*)::integer
    INTO held_eur, used_quota
    FROM dp514_monthly_dispatch_reservation WHERE period=p.period;
    IF used_quota >= p.quota_remaining_attempts
        THEN RETURN 'PROVIDER_QUOTA_REACHED'; END IF;
    proposed_eur := ceil(p_upper * p.eur_per_usd * 1000000) / 1000000;
    IF held_eur + proposed_eur > p.cap_eur
        THEN RETURN 'MONTHLY_EUR_BUDGET_REACHED'; END IF;

    SELECT reserve_worker_budget_usd(
        p_job_id,p_attempt,p_worker,p_source,p_upper,
        p_job_cap,p_global_cap,p_source_cap
    ) INTO previous_result;
    IF previous_result <> 'RESERVED' THEN RETURN previous_result; END IF;
    INSERT INTO dp514_monthly_dispatch_reservation(
        job_id,attempt,period,policy_version,provider_id,
        upper_bound_eur,pinned_eur_per_usd
    ) VALUES (
        p_job_id,p_attempt,p.period,p.policy_version,p.provider_id,
        proposed_eur,p.eur_per_usd
    );
    RETURN 'RESERVED';
END $monthly$;
