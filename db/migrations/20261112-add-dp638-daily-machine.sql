-- DP-638: the daily machine's own records.
--
-- One capture per content item, one row per statement, one row per verdict,
-- one row per run. These four tables replace the manual relevance authority,
-- the acquisition permit, the review chain and the proof ledgers that stood
-- between a captured source and a published statement. The accuracy facts they
-- must preserve are the ones the owner listed: the exact words, the person who
-- said them, the source link and date, and the evidence links of a verdict.

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
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb
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
    status              text NOT NULL,
    status_reason       text NOT NULL DEFAULT '',
    extraction_model    text NOT NULL DEFAULT '',
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT daily_statement_status_check CHECK (
        status IN ('PUBLISHED', 'HELD_NO_SPEAKER', 'HELD_NO_VERDICT', 'HELD_DUPLICATE')
    ),
    CONSTRAINT daily_statement_nature_check CHECK (
        claim_nature IN ('FACTUAL', 'OPINION')
    )
);

CREATE INDEX IF NOT EXISTS daily_statement_content_idx
    ON daily_statement (content_id, created_at DESC);
CREATE INDEX IF NOT EXISTS daily_statement_date_idx
    ON daily_statement (statement_date DESC, status);

CREATE TABLE IF NOT EXISTS daily_verdict (
    statement_id    text PRIMARY KEY REFERENCES daily_statement(id) ON DELETE CASCADE,
    verdict         text NOT NULL,
    explanation     text NOT NULL,
    evidence        jsonb NOT NULL,
    first_pass      jsonb NOT NULL,
    check_pass      jsonb NOT NULL,
    agreement       text NOT NULL,
    models          text NOT NULL,
    model_calls     integer NOT NULL,
    duration_seconds numeric NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT daily_verdict_value_check CHECK (
        verdict IN ('TRUE', 'FALSE', 'PARTLY_TRUE', 'NOT_VERIFIABLE', 'OPINION')
    )
);

CREATE TABLE IF NOT EXISTS daily_run (
    run_date    date PRIMARY KEY,
    started_at  timestamptz NOT NULL,
    finished_at timestamptz,
    items       integer NOT NULL DEFAULT 0,
    captures    integer NOT NULL DEFAULT 0,
    statements  integer NOT NULL DEFAULT 0,
    verdicts    integer NOT NULL DEFAULT 0,
    published   integer NOT NULL DEFAULT 0,
    report      jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- DP-638: close the corpses. 31 jobs blocked in September and October were
-- waiting for a path (manual relevance authority, claim canary, Groq key) that
-- the daily machine replaces; an all-time COUNT(*) made the health check
-- permanently red. They are historical rows, so they are marked terminal in
-- place and nothing is deleted.
UPDATE processing_job
SET state = 'CANCELLED_DP638_DAILY_MACHINE',
    last_error = COALESCE(last_error, '') || ' [DP-638: path replaced by the daily machine]'
WHERE state = 'BLOCKED'
  AND created_at < now() - interval '30 days';
