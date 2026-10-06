-- DP-232 follow-up: materialize the private Claim binding at mirror persistence time.
--
-- Public projection must never read private Coverage Need / research-discovery planning
-- state. Legacy mirror rows are intentionally left NULL and therefore do not project.

ALTER TABLE existing_factcheck_mirror
    ADD COLUMN IF NOT EXISTS atomic_claim_id text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'existing_factcheck_mirror_atomic_claim_fk'
          AND conrelid = 'existing_factcheck_mirror'::regclass
    ) THEN
        ALTER TABLE existing_factcheck_mirror
            ADD CONSTRAINT existing_factcheck_mirror_atomic_claim_fk
            FOREIGN KEY (atomic_claim_id)
            REFERENCES atomic_claim(id)
            ON DELETE RESTRICT;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS existing_factcheck_mirror_atomic_claim_idx
    ON existing_factcheck_mirror(atomic_claim_id, version_id)
    WHERE atomic_claim_id IS NOT NULL;
