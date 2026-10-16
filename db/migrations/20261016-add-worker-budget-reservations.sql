-- DP-512.5: durable cross-worker admission before a paid provider attempt.
-- Run through the ordered, guarded MiniPC migration path. Existing receipts
-- are immutable; an unknown outbound attempt is never released by a lease expiry.
CREATE TABLE IF NOT EXISTS worker_budget_reservation (
    job_id text NOT NULL REFERENCES processing_job(id),
    attempt integer NOT NULL CHECK (attempt >= 0),
    content_id text NOT NULL REFERENCES content_item(id),
    source_id text NOT NULL REFERENCES source(id),
    upper_bound_usd numeric(12,6) NOT NULL CHECK (upper_bound_usd > 0),
    state text NOT NULL DEFAULT 'RESERVED'
        CHECK (state IN ('RESERVED', 'RECEIPTED')),
    receipt_id text REFERENCES provider_receipt(id),
    reserved_at timestamptz NOT NULL DEFAULT now(),
    receipted_at timestamptz,
    PRIMARY KEY (job_id, attempt),
    CHECK ((state = 'RECEIPTED') = (receipt_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS worker_budget_reservation_day_idx
  ON worker_budget_reservation(reserved_at, source_id);

CREATE OR REPLACE FUNCTION reserve_worker_budget(
    p_job_id text, p_attempt integer, p_worker text, p_source text,
    p_upper numeric, p_job_cap numeric, p_global_cap numeric, p_source_cap numeric
) RETURNS text LANGUAGE plpgsql AS $reserve$
DECLARE
    current_job record;
    current_source text;
    global_spend numeric;
    source_spend numeric;
    global_held numeric;
    source_held numeric;
    today_start timestamptz := date_trunc('day', now());
BEGIN
    -- Advisory lock serializes different jobs across different worker processes.
    -- This function is one PostgreSQL transaction: no read-then-dispatch gap
    -- between the global cost read and durable reservation INSERT.
    PERFORM pg_advisory_xact_lock(hashtextextended('dp512:worker:global', 0));
    IF p_upper IS NULL OR p_upper <= 0 OR p_job_cap IS NULL
       OR p_global_cap IS NULL OR p_source_cap IS NULL
       OR p_job_cap < 0 OR p_global_cap < 0 OR p_source_cap < 0
       OR p_upper > p_job_cap THEN RETURN 'JOB_COST_CAP_REACHED'; END IF;
    IF p_upper > 999999 OR p_job_cap > 999999
       OR p_global_cap > 999999 OR p_source_cap > 999999 THEN
        RETURN 'BUDGET_LIMIT_INVALID';
    END IF;
    SELECT job.id, job.attempt, job.state, job.lease_owner, job.lease_until,
           job.content_id, content.source_id
    INTO current_job
    FROM processing_job job JOIN content_item content ON content.id=job.content_id
    WHERE job.id=p_job_id FOR UPDATE OF job;
    IF NOT FOUND OR current_job.attempt <> p_attempt
       OR current_job.state <> 'RUNNING'
       OR current_job.lease_owner IS DISTINCT FROM p_worker
       OR current_job.lease_until IS NULL
       OR current_job.lease_until <= now()
       OR current_job.source_id IS DISTINCT FROM p_source THEN
        RETURN 'BUDGET_JOB_LEASE_OR_SOURCE_INVALID';
    END IF;
    IF EXISTS (SELECT 1 FROM worker_budget_reservation
               WHERE job_id=p_job_id AND attempt=p_attempt) THEN
        -- Never re-dispatch an ambiguous already-reserved attempt.
        RETURN 'BUDGET_RESERVATION_REPLAY_HELD';
    END IF;
    -- UNKNOWN and unattested ZERO_COST across all history hold global dispatch.
    -- Prior-day reservations without sufficient receipts also survive midnight.
    IF EXISTS (
      SELECT 1 FROM provider_receipt r WHERE
        CASE WHEN r.billing_basis='MEASURED_PROVIDER_COST'
          THEN r.measured_cost_usd IS NULL OR r.measured_cost_usd <= 0
        WHEN r.billing_basis='ESTIMATED_ONLY'
          THEN r.estimated_cost_usd IS NULL OR r.estimated_cost_usd <= 0
        ELSE TRUE END
    ) OR EXISTS (
      SELECT 1 FROM worker_budget_reservation h
      WHERE h.state='RESERVED' AND h.reserved_at < today_start
    ) THEN RETURN 'UNKNOWN_BILLING_LIABILITY_HELD'; END IF;
    SELECT COALESCE(sum(CASE WHEN r.billing_basis='MEASURED_PROVIDER_COST'
              THEN r.measured_cost_usd ELSE r.estimated_cost_usd END),0)
    INTO global_spend FROM provider_receipt r
    WHERE COALESCE(r.started_at,r.completed_at,now()) >= today_start;
    SELECT COALESCE(sum(CASE WHEN r.billing_basis='MEASURED_PROVIDER_COST'
              THEN r.measured_cost_usd ELSE r.estimated_cost_usd END),0)
    INTO source_spend FROM provider_receipt r
    JOIN content_item c ON c.id=r.content_id
    WHERE c.source_id=p_source
      AND COALESCE(r.started_at,r.completed_at,now()) >= today_start;
    SELECT COALESCE(sum(h.upper_bound_usd),0),
           COALESCE(sum(h.upper_bound_usd) FILTER (WHERE h.source_id=p_source),0)
    INTO global_held, source_held FROM worker_budget_reservation h
    WHERE h.state='RESERVED' AND h.reserved_at >= today_start;
    IF global_spend + global_held + p_upper > p_global_cap THEN
        RETURN 'GLOBAL_DAILY_BUDGET_REACHED';
    END IF;
    IF source_spend + source_held + p_upper > p_source_cap THEN
        RETURN 'SOURCE_DAILY_BUDGET_REACHED';
    END IF;
    INSERT INTO worker_budget_reservation(
        job_id, attempt, content_id, source_id, upper_bound_usd
    ) VALUES (p_job_id, p_attempt, current_job.content_id, p_source, p_upper);
    RETURN 'RESERVED';
END $reserve$;
