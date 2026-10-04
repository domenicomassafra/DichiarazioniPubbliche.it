BEGIN;

-- Early worker canaries materialized one BLOCKED job per deterministic claim
-- window while the claim-extraction runtime itself was unavailable. That is
-- unnecessary queue amplification: the windows are reproducible from the
-- canonical transcript and should only be materialized when an executor can
-- actually consume them.
WITH affected AS (
    SELECT DISTINCT content_id
    FROM processing_job
    WHERE
        job_type = 'CLAIM_EXTRACT_WINDOW'
        AND state = 'BLOCKED'
        AND last_error IN (
            'CLAIM_EXTRACTION_RUNTIME_DISABLED',
            'CLAIM_EXTRACTION_EXECUTOR_NOT_IMPLEMENTED'
        )
),
deleted AS (
    DELETE FROM processing_job
    WHERE
        job_type = 'CLAIM_EXTRACT_WINDOW'
        AND state = 'BLOCKED'
        AND last_error IN (
            'CLAIM_EXTRACTION_RUNTIME_DISABLED',
            'CLAIM_EXTRACTION_EXECUTOR_NOT_IMPLEMENTED'
        )
    RETURNING content_id
)
UPDATE processing_job AS parent
SET
    state = 'BLOCKED',
    completed_at = NULL,
    lease_owner = NULL,
    lease_until = NULL,
    last_error = 'CLAIM_EXTRACTION_CANARY_FAILED',
    updated_at = now()
WHERE
    parent.content_id IN (SELECT content_id FROM affected)
    AND parent.job_type IN ('CLAIM_PREPARE', 'CLAIM_EXTRACT')
    AND parent.state = 'COMPLETED';

UPDATE processing_job
SET
    last_error = 'CLAIM_EXTRACTION_CANARY_FAILED',
    updated_at = now()
WHERE
    job_type IN ('CLAIM_PREPARE', 'CLAIM_EXTRACT')
    AND state = 'BLOCKED'
    AND last_error = 'CLAIM_EXTRACTION_RUNTIME_DISABLED';

UPDATE content_item AS content
SET
    processing_status = 'CLAIM_EXTRACTION_BLOCKED',
    metadata = (
        content.metadata
        - 'claim_window_count'
        - 'claim_window_new_jobs'
        - 'claim_window_blocked_jobs'
        - 'claim_window_estimated_input_tokens'
    ) || jsonb_build_object(
        'runtime_blocker', 'CLAIM_EXTRACTION_CANARY_FAILED',
        'claim_window_materialized', false,
        'claim_window_compacted_at', now()
    )
WHERE content.id IN (
    SELECT DISTINCT content_id
    FROM processing_job
    WHERE
        job_type IN ('CLAIM_PREPARE', 'CLAIM_EXTRACT')
        AND state = 'BLOCKED'
        AND last_error = 'CLAIM_EXTRACTION_CANARY_FAILED'
);

COMMIT;
