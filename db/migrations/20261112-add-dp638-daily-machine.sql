-- DP-638: private persistence for the daily machine foundation.
--
-- Discovery, capture, statement candidates and verdicts remain private
-- operational records. Nothing in these tables grants publication authority.
-- This migration is additive and repeatable; it does not rewrite existing jobs.

CREATE TABLE IF NOT EXISTS daily_capture (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    content_capture_id  text NOT NULL UNIQUE REFERENCES content_capture(id) ON DELETE CASCADE,
    source_id           text NOT NULL REFERENCES source(id) ON DELETE RESTRICT,
    capture_kind        text NOT NULL,
    url                 text NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    char_count          integer NOT NULL,
    content_sha256      text NOT NULL,
    text_sha256         text NOT NULL,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (char_count >= 0),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (id, content_id, source_id, url)
);

CREATE OR REPLACE FUNCTION dp638_validate_daily_capture_source()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    item_source_id text;
    source_kind text;
    capture_content_id text;
    capture_url text;
    capture_rights_status text;
    capture_retention_class text;
    capture_hold_status text;
    capture_status text;
    capture_body_ref text;
    capture_body_purged_at timestamptz;
    capture_content_sha256 text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'DP638_DAILY_CAPTURE_IMMUTABLE';
    END IF;
    SELECT item.source_id, lower(source.source_type), existing_capture.content_id,
           existing_capture.final_url, existing_capture.rights_status,
           existing_capture.retention_class, existing_capture.hold_status,
           existing_capture.status, existing_capture.body_ref,
           existing_capture.body_purged_at, existing_capture.content_sha256
    INTO item_source_id, source_kind, capture_content_id, capture_url,
         capture_rights_status, capture_retention_class, capture_hold_status,
         capture_status, capture_body_ref, capture_body_purged_at,
         capture_content_sha256
    FROM content_item item
    JOIN source ON source.id = item.source_id
    JOIN content_capture existing_capture
      ON existing_capture.id = NEW.content_capture_id
    WHERE item.id = NEW.content_id;
    IF NOT FOUND
       OR item_source_id IS DISTINCT FROM NEW.source_id
       OR capture_content_id IS DISTINCT FROM NEW.content_id
       OR capture_url IS DISTINCT FROM NEW.url
       OR capture_content_sha256 IS DISTINCT FROM NEW.content_sha256 THEN
        RAISE EXCEPTION 'DP638_CAPTURE_SOURCE_MISMATCH';
    END IF;
    IF source_kind IN ('public_rss', 'rss') THEN
        RAISE EXCEPTION 'DP638_RIGHTS_HOLD_PUBLIC_RSS';
    END IF;
    IF capture_rights_status IS DISTINCT FROM 'CLEARED'
       OR capture_hold_status IS DISTINCT FROM 'NONE'
       OR capture_retention_class IS NULL
       OR capture_retention_class NOT IN ('DURABLE_PRIVATE', 'DURABLE_PROVENANCE')
       OR capture_status IS DISTINCT FROM 'CAPTURED'
       OR capture_body_ref IS NULL
       OR capture_body_purged_at IS NOT NULL THEN
        RAISE EXCEPTION 'DP638_CAPTURE_RIGHTS_OR_RETENTION_BLOCKED';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS daily_capture_source_matches_content ON daily_capture;
CREATE TRIGGER daily_capture_source_matches_content
BEFORE INSERT OR UPDATE ON daily_capture
FOR EACH ROW EXECUTE FUNCTION dp638_validate_daily_capture_source();

CREATE INDEX IF NOT EXISTS daily_capture_content_idx
    ON daily_capture (content_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS daily_statement (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    capture_id          text NOT NULL,
    source_id           text NOT NULL REFERENCES source(id) ON DELETE RESTRICT,
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
    claim_nature        text NOT NULL,
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
    CONSTRAINT daily_statement_id_nature_unique UNIQUE (id, claim_nature),
    FOREIGN KEY (capture_id, content_id, source_id, source_url)
        REFERENCES daily_capture (id, content_id, source_id, url) ON DELETE CASCADE
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
