-- Issue #180. Before applying on an operational DB, export the affected parent
-- rows (including original status, counters and error_category) and pg_constraint
-- definition to a private preimage file; restore only from that verified preimage.
-- No child receipts are synthesized. A partial historical run is explicitly FAILED.
BEGIN;

DO $source_poll_constraint$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'source_poll_run_source'::regclass
          AND conname = 'source_poll_run_source_status_check'
          AND pg_get_constraintdef(oid) LIKE '%''BLOCKED''%'
    ) THEN
        ALTER TABLE source_poll_run_source
            DROP CONSTRAINT IF EXISTS source_poll_run_source_status_check;
        ALTER TABLE source_poll_run_source
            ADD CONSTRAINT source_poll_run_source_status_check CHECK (status IN (
                'RUNNING', 'HEALTHY', 'BUDGET_BLOCKED', 'FAILED',
                'SKIPPED_NOT_DUE', 'SKIPPED_UNSUPPORTED',
                'SKIPPED_DAILY_LIMIT', 'SKIPPED_ALREADY_COMPLETED', 'BLOCKED'
            ));
    END IF;
END;
$source_poll_constraint$;

-- Preserve existing counters and child rows: the failure is of receipt integrity,
-- not evidence that a missing source was successfully processed.
UPDATE source_poll_run AS run
SET status = 'FAILED', error_category = 'RECEIPT_COUNT_MISMATCH'
WHERE run.mode = 'full-source'
  AND run.status = 'COMPLETED'
  AND run.source_count <> (
      SELECT count(*) FROM source_poll_run_source AS child WHERE child.run_id = run.id
  );

DO $source_poll_verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'source_poll_run_source'::regclass
          AND conname = 'source_poll_run_source_status_check'
          AND convalidated
          AND pg_get_constraintdef(oid) LIKE '%''BLOCKED''%'
    ) THEN
        RAISE EXCEPTION 'SOURCE_POLL_BLOCKED_CONSTRAINT_NOT_VALID';
    END IF;
    IF EXISTS (
        SELECT 1 FROM source_poll_run AS run
        WHERE run.mode = 'full-source' AND run.status = 'COMPLETED'
          AND run.source_count <> (
              SELECT count(*) FROM source_poll_run_source AS child WHERE child.run_id = run.id
          )
    ) THEN
        RAISE EXCEPTION 'SOURCE_POLL_COMPLETED_WITH_MISSING_RECEIPTS';
    END IF;
END;
$source_poll_verify$;

COMMIT;
