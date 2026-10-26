-- DP-413E: append-only nightly audit manifest, sample result, and daily metrics.
-- The coordinator records only results from authenticated v3 publication adapters.
CREATE TABLE IF NOT EXISTS autonomous_nightly_audit_run (
    run_id text PRIMARY KEY,
    audit_day date NOT NULL UNIQUE,
    denominator integer NOT NULL CHECK (denominator >= 0),
    sampled_ids jsonb NOT NULL CHECK (jsonb_typeof(sampled_ids) = 'array'),
    started_at timestamptz NOT NULL,
    CHECK (run_id ~ '^nightly:[0-9a-f]{64}$'),
    CHECK (jsonb_array_length(sampled_ids) = (denominator + 9) / 10)
);

CREATE TABLE IF NOT EXISTS autonomous_nightly_audit_result (
    run_id text NOT NULL REFERENCES autonomous_nightly_audit_run(run_id),
    record_id text NOT NULL,
    disposition text NOT NULL CHECK (disposition IN ('AUDIT_PASS', 'AUDIT_HOLD')),
    evidence_sha256 text CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    reason_codes jsonb NOT NULL CHECK (jsonb_typeof(reason_codes) = 'array'),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    audited_at timestamptz NOT NULL,
    PRIMARY KEY (run_id, record_id)
);

CREATE TABLE IF NOT EXISTS autonomous_nightly_audit_complete (
    run_id text PRIMARY KEY REFERENCES autonomous_nightly_audit_run(run_id),
    completed_at timestamptz NOT NULL,
    metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics) = 'object')
);

CREATE OR REPLACE FUNCTION reject_autonomous_nightly_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'autonomous nightly audit ledger is append-only';
END;
$$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'autonomous_nightly_audit_run',
        'autonomous_nightly_audit_result',
        'autonomous_nightly_audit_complete'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS nightly_audit_immutable ON %I', table_name);
        EXECUTE format('CREATE TRIGGER nightly_audit_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_autonomous_nightly_audit_mutation()', table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS nightly_audit_no_truncate ON %I', table_name);
        EXECUTE format('CREATE TRIGGER nightly_audit_no_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION reject_autonomous_nightly_audit_mutation()', table_name);
    END LOOP;
END;
$$;
