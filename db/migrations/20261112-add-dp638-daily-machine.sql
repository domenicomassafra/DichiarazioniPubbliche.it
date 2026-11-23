-- DP-638: private persistence for the daily machine foundation.
--
-- Discovery, capture, statement candidates and verdicts remain private
-- operational records. Nothing in these tables grants publication authority.
-- This migration is additive and repeatable; it does not rewrite existing jobs.

CREATE TABLE IF NOT EXISTS daily_capture (
    id              text PRIMARY KEY,
    content_id      text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    source_id       text NOT NULL,
    capture_kind    text NOT NULL,
    url             text NOT NULL,
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    char_count      integer NOT NULL,
    text_sha256     text NOT NULL,
    body            text NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (char_count >= 0),
    CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS daily_capture_content_idx
    ON daily_capture (content_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS daily_statement (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    capture_id          text NOT NULL REFERENCES daily_capture(id) ON DELETE CASCADE,
    source_id           text NOT NULL,
    source_url          text NOT NULL,
    source_title        text NOT NULL,
    source_publisher    text NOT NULL,
    source_published_at timestamptz,
    statement_date      date NOT NULL,
    quote               text NOT NULL,
    quote_offset        integer NOT NULL,
    moment_label        text NOT NULL DEFAULT '',
    speaker_name        text NOT NULL DEFAULT '',
    speaker_role        text NOT NULL DEFAULT '',
    speaker_key         text NOT NULL DEFAULT '',
    topic               text NOT NULL DEFAULT '',
    claim_nature        text NOT NULL DEFAULT 'FACTUAL',
    status              text NOT NULL DEFAULT 'CANDIDATE',
    status_reason       text NOT NULL DEFAULT '',
    extraction_model    text NOT NULL DEFAULT '',
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT daily_statement_status_check CHECK (
        status IN ('CANDIDATE', 'HELD_NO_SPEAKER', 'HELD_NO_VERDICT', 'HELD_DUPLICATE')
    ),
    CONSTRAINT daily_statement_nature_check CHECK (
        claim_nature IN ('FACTUAL', 'OPINION')
    ),
    CHECK (length(btrim(quote)) > 0),
    CHECK (quote_offset >= 0),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT daily_statement_id_nature_unique UNIQUE (id, claim_nature)
);

CREATE INDEX IF NOT EXISTS daily_statement_content_idx
    ON daily_statement (content_id, created_at DESC);
CREATE INDEX IF NOT EXISTS daily_statement_date_idx
    ON daily_statement (statement_date DESC, status);

CREATE TABLE IF NOT EXISTS daily_verdict (
    statement_id    text PRIMARY KEY,
    claim_nature    text NOT NULL DEFAULT 'FACTUAL',
    verdict         text NOT NULL,
    explanation     text NOT NULL,
    evidence        jsonb NOT NULL DEFAULT '[]'::jsonb,
    first_pass      jsonb NOT NULL,
    check_pass      jsonb NOT NULL,
    agreement       text NOT NULL,
    models          text NOT NULL,
    model_calls     integer NOT NULL,
    duration_seconds numeric NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT daily_verdict_factual_only CHECK (claim_nature = 'FACTUAL'),
    CONSTRAINT daily_verdict_statement_fk
        FOREIGN KEY (statement_id, claim_nature)
        REFERENCES daily_statement(id, claim_nature) ON DELETE CASCADE,
    CONSTRAINT daily_verdict_value_check CHECK (
        verdict IN (
            'TRUE',
            'MOSTLY_TRUE',
            'MISLEADING',
            'FALSE',
            'NOT_VERIFIABLE',
            'CONTRADICTORY_WITH_ITSELF'
        )
    ),
    CHECK (jsonb_typeof(evidence) = 'array'),
    CHECK (jsonb_typeof(first_pass) = 'object' AND first_pass <> '{}'::jsonb),
    CHECK (jsonb_typeof(check_pass) = 'object' AND check_pass <> '{}'::jsonb),
    CHECK (length(btrim(models)) > 0),
    CHECK (model_calls >= 2),
    CHECK (duration_seconds >= 0)
);

CREATE TABLE IF NOT EXISTS daily_run (
    run_date             date PRIMARY KEY,
    started_at           timestamptz NOT NULL,
    finished_at          timestamptz,
    status               text NOT NULL DEFAULT 'RUNNING',
    items                integer NOT NULL DEFAULT 0,
    captures             integer NOT NULL DEFAULT 0,
    statements           integer NOT NULL DEFAULT 0,
    verdicts             integer NOT NULL DEFAULT 0,
    held_statements      integer NOT NULL DEFAULT 0,
    report               jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    CHECK (
        (status = 'RUNNING' AND finished_at IS NULL)
        OR (status IN ('COMPLETED', 'FAILED') AND finished_at IS NOT NULL)
    ),
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    CHECK (items >= 0 AND captures >= 0 AND statements >= 0
           AND verdicts >= 0 AND held_statements >= 0),
    CHECK (jsonb_typeof(report) = 'object')
);
