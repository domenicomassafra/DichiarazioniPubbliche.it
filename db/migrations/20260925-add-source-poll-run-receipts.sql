BEGIN;

CREATE TABLE IF NOT EXISTS source_poll_run (
    id                      text PRIMARY KEY,
    mode                    text NOT NULL,
    run_date                date NOT NULL,
    effective_config_hash   text NOT NULL,
    status                  text NOT NULL,
    diagnostic              boolean NOT NULL DEFAULT false,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    source_count            integer NOT NULL DEFAULT 0,
    discovered              integer NOT NULL DEFAULT 0,
    content_upserts         integer NOT NULL DEFAULT 0,
    jobs_enqueued           integer NOT NULL DEFAULT 0,
    duplicate_jobs          integer NOT NULL DEFAULT 0,
    budget_blocked          integer NOT NULL DEFAULT 0,
    omitted_items           integer NOT NULL DEFAULT 0,
    error_category          text,
    UNIQUE (mode, run_date, effective_config_hash),
    CHECK (mode IN ('source-due', 'full-source')),
    CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED_ALREADY_COMPLETED')),
    CHECK (source_count >= 0),
    CHECK (discovered >= 0),
    CHECK (content_upserts >= 0),
    CHECK (jobs_enqueued >= 0),
    CHECK (duplicate_jobs >= 0),
    CHECK (budget_blocked >= 0),
    CHECK (omitted_items >= 0)
);

CREATE INDEX IF NOT EXISTS source_poll_run_date_idx
    ON source_poll_run(run_date DESC, mode, status);

CREATE TABLE IF NOT EXISTS source_poll_run_source (
    id                      text PRIMARY KEY,
    run_id                  text NOT NULL REFERENCES source_poll_run(id) ON DELETE CASCADE,
    source_id               text NOT NULL REFERENCES source(id) ON DELETE CASCADE,
    mode                    text NOT NULL,
    run_date                date NOT NULL,
    effective_config_hash   text NOT NULL,
    diagnostic              boolean NOT NULL DEFAULT false,
    status                  text NOT NULL,
    discovered              integer NOT NULL DEFAULT 0,
    content_upserts         integer NOT NULL DEFAULT 0,
    jobs_enqueued           integer NOT NULL DEFAULT 0,
    duplicate_jobs          integer NOT NULL DEFAULT 0,
    budget_blocked          integer NOT NULL DEFAULT 0,
    omitted_items           integer NOT NULL DEFAULT 0,
    error_category          text,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    UNIQUE (run_id, source_id),
    CHECK (mode IN ('source-due', 'full-source')),
    CHECK (status IN (
        'RUNNING', 'HEALTHY', 'BUDGET_BLOCKED', 'FAILED',
        'SKIPPED_NOT_DUE', 'SKIPPED_UNSUPPORTED',
        'SKIPPED_DAILY_LIMIT', 'SKIPPED_ALREADY_COMPLETED', 'BLOCKED'
    )),
    CHECK (discovered >= 0),
    CHECK (content_upserts >= 0),
    CHECK (jobs_enqueued >= 0),
    CHECK (duplicate_jobs >= 0),
    CHECK (budget_blocked >= 0),
    CHECK (omitted_items >= 0)
);

CREATE INDEX IF NOT EXISTS source_poll_run_source_idx
    ON source_poll_run_source(source_id, run_id);

COMMIT;
