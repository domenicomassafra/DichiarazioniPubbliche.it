BEGIN;

-- DP-217 / DP-220: private append-only review ledgers bound to immutable source spans.
-- These rows are review provenance only. They do not publish anything and the context
-- ledger deliberately stores hashes/offsets rather than surrounding source text.

CREATE TABLE IF NOT EXISTS transcript_verbatim_review_event (
    id                          text PRIMARY KEY,
    content_id                  text NOT NULL REFERENCES content_item(id) ON DELETE RESTRICT,
    source_variant_id           text NOT NULL REFERENCES transcript_variant(id) ON DELETE RESTRICT,
    source_segment_id           text NOT NULL REFERENCES transcript_segment(id) ON DELETE RESTRICT,
    source_variant_sha256       text NOT NULL,
    source_segment_sha256       text NOT NULL,
    start_ms                    bigint NOT NULL,
    end_ms                      bigint NOT NULL,
    reviewed_text               text NOT NULL,
    reviewed_text_sha256        text NOT NULL,
    decision                    text NOT NULL,
    reviewer_ref                text NOT NULL,
    reason_codes                text[] NOT NULL DEFAULT ARRAY[]::text[],
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    review_version              text NOT NULL DEFAULT 'transcript-verbatim-review-v1',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (source_variant_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (source_segment_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (reviewed_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (start_ms >= 0 AND end_ms > start_ms),
    CHECK (length(reviewed_text) > 0),
    CHECK (decision IN ('APPROVED', 'REJECTED')),
    CHECK (cardinality(reason_codes) <= 32),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (review_version = 'transcript-verbatim-review-v1')
);

CREATE INDEX IF NOT EXISTS transcript_verbatim_review_source_idx
    ON transcript_verbatim_review_event(source_variant_id, source_segment_id, created_at, id);

CREATE TABLE IF NOT EXISTS context_integrity_review_event (
    id                          text PRIMARY KEY,
    record_id                   text NOT NULL,
    source_sha256               text NOT NULL,
    quote_sha256                text NOT NULL,
    context_sha256              text NOT NULL,
    quote_start                 integer NOT NULL,
    quote_end                   integer NOT NULL,
    context_start               integer NOT NULL,
    context_end                 integer NOT NULL,
    signal_codes                text[] NOT NULL DEFAULT ARRAY[]::text[],
    decision                    text NOT NULL,
    reviewer_ref                text NOT NULL,
    reason_codes                text[] NOT NULL DEFAULT ARRAY[]::text[],
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    review_version              text NOT NULL DEFAULT 'context-integrity-review-v1',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (quote_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (context_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (quote_start >= 0 AND quote_end > quote_start),
    CHECK (context_start >= 0 AND context_end >= quote_end),
    CHECK (context_start <= quote_start),
    CHECK (cardinality(signal_codes) <= 32),
    CHECK (cardinality(reason_codes) <= 32),
    CHECK (decision IN ('APPROVED', 'REJECTED')),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (review_version = 'context-integrity-review-v1')
);

CREATE INDEX IF NOT EXISTS context_integrity_review_record_idx
    ON context_integrity_review_event(record_id, created_at, id);

CREATE OR REPLACE FUNCTION reject_source_span_review_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'source-span review ledgers are append-only';
END;
$$;

DROP TRIGGER IF EXISTS transcript_verbatim_review_append_only
    ON transcript_verbatim_review_event;
CREATE TRIGGER transcript_verbatim_review_append_only
BEFORE UPDATE OR DELETE ON transcript_verbatim_review_event
FOR EACH ROW EXECUTE FUNCTION reject_source_span_review_mutation();

DROP TRIGGER IF EXISTS transcript_verbatim_review_no_truncate
    ON transcript_verbatim_review_event;
CREATE TRIGGER transcript_verbatim_review_no_truncate
BEFORE TRUNCATE ON transcript_verbatim_review_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_source_span_review_mutation();

DROP TRIGGER IF EXISTS context_integrity_review_append_only
    ON context_integrity_review_event;
CREATE TRIGGER context_integrity_review_append_only
BEFORE UPDATE OR DELETE ON context_integrity_review_event
FOR EACH ROW EXECUTE FUNCTION reject_source_span_review_mutation();

DROP TRIGGER IF EXISTS context_integrity_review_no_truncate
    ON context_integrity_review_event;
CREATE TRIGGER context_integrity_review_no_truncate
BEFORE TRUNCATE ON context_integrity_review_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_source_span_review_mutation();

COMMIT;
