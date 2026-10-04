BEGIN;

ALTER TABLE verification_run
    ADD COLUMN IF NOT EXISTS observation_ids jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE verification_run
    DROP CONSTRAINT IF EXISTS verification_run_provenance_arrays_check;

ALTER TABLE verification_run
    ADD CONSTRAINT verification_run_provenance_arrays_check
    CHECK (
        jsonb_typeof(evidence_ids) = 'array'
        AND jsonb_typeof(observation_ids) = 'array'
        AND jsonb_typeof(blockers) = 'array'
        AND jsonb_typeof(rationale_codes) = 'array'
    );

COMMIT;
