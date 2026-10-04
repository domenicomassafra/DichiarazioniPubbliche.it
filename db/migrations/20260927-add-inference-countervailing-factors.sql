BEGIN;

ALTER TABLE inference_candidate
    ADD COLUMN IF NOT EXISTS countervailing_factors jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE inference_candidate
    DROP CONSTRAINT IF EXISTS inference_candidate_countervailing_factors_check;

ALTER TABLE inference_candidate
    ADD CONSTRAINT inference_candidate_countervailing_factors_check
    CHECK (jsonb_typeof(countervailing_factors) = 'array');

COMMIT;
