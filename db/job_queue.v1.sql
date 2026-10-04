DROP FUNCTION IF EXISTS enqueue_blocked_processing_job(
    text, text, text, text, jsonb
);

CREATE OR REPLACE FUNCTION enqueue_processing_job(
    p_id text,
    p_content_id text,
    p_job_type text,
    p_payload jsonb DEFAULT '{}'::jsonb
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO processing_job (
        id,
        content_id,
        job_type,
        state,
        payload
    )
    VALUES (
        p_id,
        p_content_id,
        p_job_type,
        'QUEUED',
        p_payload
    )
    ON CONFLICT (id) DO NOTHING;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION claim_processing_job(
    p_worker_id text,
    p_lease_seconds integer DEFAULT 300
) RETURNS SETOF processing_job
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH candidate AS (
        SELECT id
        FROM processing_job
        WHERE
            state = 'QUEUED'
            AND available_at <= now()
            AND (lease_until IS NULL OR lease_until < now())
        ORDER BY available_at, created_at, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE processing_job AS job
    SET
        state = 'RUNNING',
        started_at = COALESCE(job.started_at, now()),
        lease_owner = p_worker_id,
        lease_until = now() + make_interval(secs => GREATEST(p_lease_seconds, 1)),
        updated_at = now()
    FROM candidate
    WHERE job.id = candidate.id
    RETURNING job.*;
END;
$$;

CREATE OR REPLACE FUNCTION renew_processing_job_lease(
    p_job_id text,
    p_worker_id text,
    p_lease_seconds integer DEFAULT 300
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE processing_job
    SET
        lease_until = now() + make_interval(secs => GREATEST(p_lease_seconds, 1)),
        updated_at = now()
    WHERE
        id = p_job_id
        AND state = 'RUNNING'
        AND lease_owner = p_worker_id;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION complete_processing_job(
    p_job_id text,
    p_worker_id text
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE processing_job
    SET
        state = 'COMPLETED',
        completed_at = now(),
        lease_owner = NULL,
        lease_until = NULL,
        updated_at = now()
    WHERE
        id = p_job_id
        AND state = 'RUNNING'
        AND lease_owner = p_worker_id;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION retry_processing_job(
    p_job_id text,
    p_worker_id text,
    p_error text,
    p_delay_seconds integer DEFAULT 60,
    p_max_attempts integer DEFAULT 5
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    new_attempt integer;
    next_state text;
BEGIN
    SELECT attempt + 1
    INTO new_attempt
    FROM processing_job
    WHERE
        id = p_job_id
        AND state = 'RUNNING'
        AND lease_owner = p_worker_id
    FOR UPDATE;

    IF new_attempt IS NULL THEN
        RETURN 'NOT_OWNED';
    END IF;

    next_state := CASE
        WHEN new_attempt >= GREATEST(p_max_attempts, 1) THEN 'DEAD_LETTER'
        ELSE 'QUEUED'
    END;

    UPDATE processing_job
    SET
        state = next_state,
        attempt = new_attempt,
        available_at = CASE
            WHEN next_state = 'QUEUED'
                THEN now() + make_interval(secs => GREATEST(p_delay_seconds, 0))
            ELSE available_at
        END,
        lease_owner = NULL,
        lease_until = NULL,
        last_error = p_error,
        updated_at = now()
    WHERE id = p_job_id;

    RETURN next_state;
END;
$$;

CREATE OR REPLACE FUNCTION defer_processing_job(
    p_job_id text,
    p_worker_id text,
    p_reason text,
    p_delay_seconds integer DEFAULT 300
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE processing_job
    SET
        state = 'QUEUED',
        available_at = now() + make_interval(secs => GREATEST(p_delay_seconds, 0)),
        lease_owner = NULL,
        lease_until = NULL,
        last_error = p_reason,
        updated_at = now()
    WHERE
        id = p_job_id
        AND state = 'RUNNING'
        AND lease_owner = p_worker_id;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION block_processing_job(
    p_job_id text,
    p_worker_id text,
    p_reason text
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE processing_job
    SET
        state = 'BLOCKED',
        lease_owner = NULL,
        lease_until = NULL,
        last_error = p_reason,
        updated_at = now()
    WHERE
        id = p_job_id
        AND state = 'RUNNING'
        AND lease_owner = p_worker_id;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION unblock_processing_job(
    p_job_id text
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE processing_job
    SET
        state = 'QUEUED',
        available_at = now(),
        last_error = NULL,
        updated_at = now()
    WHERE id = p_job_id AND state = 'BLOCKED';

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION reap_expired_processing_jobs(
    p_max_attempts integer DEFAULT 5
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    changed integer;
BEGIN
    WITH expired AS (
        SELECT id, attempt + 1 AS next_attempt
        FROM processing_job
        WHERE
            state = 'RUNNING'
            AND lease_until IS NOT NULL
            AND lease_until < now()
        FOR UPDATE SKIP LOCKED
    )
    UPDATE processing_job AS job
    SET
        state = CASE
            WHEN expired.next_attempt >= GREATEST(p_max_attempts, 1)
                THEN 'DEAD_LETTER'
            ELSE 'QUEUED'
        END,
        attempt = expired.next_attempt,
        available_at = CASE
            WHEN expired.next_attempt >= GREATEST(p_max_attempts, 1)
                THEN job.available_at
            ELSE now()
        END,
        lease_owner = NULL,
        lease_until = NULL,
        last_error = 'LEASE_EXPIRED',
        updated_at = now()
    FROM expired
    WHERE job.id = expired.id;

    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed;
END;
$$;
