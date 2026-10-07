BEGIN;

ALTER TABLE evidence
    ADD COLUMN IF NOT EXISTS valid_from date;

ALTER TABLE evidence
    ADD COLUMN IF NOT EXISTS valid_until date;

ALTER TABLE evidence
    ADD COLUMN IF NOT EXISTS record_status text NOT NULL DEFAULT 'ACTIVE';

ALTER TABLE evidence
    ALTER COLUMN record_status SET DEFAULT 'ACTIVE';

ALTER TABLE evidence
    ALTER COLUMN record_status SET NOT NULL;

ALTER TABLE evidence
    DROP CONSTRAINT IF EXISTS evidence_effective_interval_check;

ALTER TABLE evidence
    ADD CONSTRAINT evidence_effective_interval_check
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from);

ALTER TABLE evidence
    DROP CONSTRAINT IF EXISTS evidence_record_status_check;

ALTER TABLE evidence
    ADD CONSTRAINT evidence_record_status_check
    CHECK (record_status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED', 'EXPIRED'));

COMMIT;
