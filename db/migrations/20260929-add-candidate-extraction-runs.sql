BEGIN;

-- DP-211: bounded Passage -> research candidate extraction receipts.
CREATE TABLE IF NOT EXISTS candidate_extraction_run (
    id                      text PRIMARY KEY,
    operation_key           text NOT NULL UNIQUE,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id              text NOT NULL,
    capture_id              text,
    canonical_segment_id    text,
    input_sha256            text NOT NULL,
    extractor_version       text NOT NULL DEFAULT 'candidate-extraction-v1',
    provider_id             text NOT NULL,
    model_id                text,
    provider_version        text NOT NULL,
    status                  text NOT NULL DEFAULT 'RUNNING',
    call_count              integer NOT NULL DEFAULT 0,
    cost_upper_bound_usd    numeric(12,6) NOT NULL DEFAULT 0,
    cost_usd                numeric(12,6) NOT NULL DEFAULT 0,
    statement_count         integer NOT NULL DEFAULT 0,
    claim_count             integer NOT NULL DEFAULT 0,
    entity_mention_count    integer NOT NULL DEFAULT 0,
    entity_resolution_count integer NOT NULL DEFAULT 0,
    provider_receipt_id     text REFERENCES provider_receipt(id),
    error_category          text,
    lease_owner             text,
    lease_until             timestamptz,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (extractor_version = 'candidate-extraction-v1'),
    CHECK (status IN ('RUNNING', 'COMPLETED', 'BLOCKED', 'FAILED')),
    CHECK ((status = 'RUNNING') = (lease_owner IS NOT NULL AND lease_until IS NOT NULL)),
    CONSTRAINT candidate_extraction_run_call_count_check CHECK (call_count IN (0, 1)),
    CHECK (cost_upper_bound_usd >= 0 AND cost_usd >= 0),
    CONSTRAINT candidate_extraction_run_pre_call_cost_check CHECK (call_count > 0 OR cost_usd = 0),
    CONSTRAINT candidate_extraction_run_completed_receipt_check
        CHECK (status <> 'COMPLETED' OR (call_count = 1 AND provider_receipt_id IS NOT NULL)),
    CHECK (statement_count >= 0 AND claim_count >= 0 AND entity_mention_count >= 0 AND entity_resolution_count >= 0),
    CHECK ((capture_id IS NOT NULL)::integer + (canonical_segment_id IS NOT NULL)::integer = 1),
    FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id) ON DELETE CASCADE
);

-- Upgrade-safe hardening for schemas that already saw an earlier DP-211 draft.
ALTER TABLE candidate_extraction_run
    DROP CONSTRAINT IF EXISTS candidate_extraction_run_call_count_check;
ALTER TABLE candidate_extraction_run
    ADD CONSTRAINT candidate_extraction_run_call_count_check
    CHECK (call_count IN (0, 1));

ALTER TABLE candidate_extraction_run
    DROP CONSTRAINT IF EXISTS candidate_extraction_run_pre_call_cost_check;
ALTER TABLE candidate_extraction_run
    ADD CONSTRAINT candidate_extraction_run_pre_call_cost_check
    CHECK (call_count > 0 OR cost_usd = 0);

ALTER TABLE candidate_extraction_run
    DROP CONSTRAINT IF EXISTS candidate_extraction_run_completed_receipt_check;
ALTER TABLE candidate_extraction_run
    ADD CONSTRAINT candidate_extraction_run_completed_receipt_check
    CHECK (status <> 'COMPLETED' OR (call_count = 1 AND provider_receipt_id IS NOT NULL));

CREATE INDEX IF NOT EXISTS candidate_extraction_run_content_idx
    ON candidate_extraction_run(content_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS candidate_extraction_run_passage_idx
    ON candidate_extraction_run(passage_id, started_at DESC);

CREATE TABLE IF NOT EXISTS entity_mention_candidate (
    id                      text PRIMARY KEY,
    extraction_run_id       text NOT NULL REFERENCES candidate_extraction_run(id) ON DELETE CASCADE,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id              text NOT NULL,
    start_char              integer NOT NULL,
    end_char                integer NOT NULL,
    mention_text            text NOT NULL,
    mention_text_sha256     text NOT NULL,
    proposed_entity_type    text,
    extraction_method       text NOT NULL,
    extraction_version      text NOT NULL DEFAULT 'candidate-extraction-v1',
    status                  text NOT NULL DEFAULT 'CANDIDATE',
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (start_char >= 0 AND end_char > start_char),
    CHECK (mention_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (proposed_entity_type IS NULL OR proposed_entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (extraction_method IN ('KNOWN_ALIAS', 'MODEL')),
    CHECK (extraction_version = 'candidate-extraction-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_mention_candidate_identity_idx
    ON entity_mention_candidate(
        extraction_run_id, passage_id, start_char, end_char, extraction_method, COALESCE(proposed_entity_type, '')
    );

CREATE INDEX IF NOT EXISTS entity_mention_candidate_passage_idx
    ON entity_mention_candidate(content_id, passage_id, status, start_char);

ALTER TABLE review_event
    DROP CONSTRAINT IF EXISTS review_event_entity_type_check;

ALTER TABLE review_event
    ADD CONSTRAINT review_event_entity_type_check
    CHECK (
        entity_type IN (
            'CLAIM_EVIDENCE_CANDIDATE',
            'EVIDENCE_OBSERVATION',
            'RELATION_CANDIDATE',
            'INFERENCE_CANDIDATE',
            'CLAIM_TEXT_PROVENANCE',
            'STATEMENT_CANDIDATE',
            'CLAIM_CANDIDATE',
            'ENTITY_RESOLUTION_CANDIDATE',
            'ENTITY_MENTION_CANDIDATE',
            'PROPOSITION_CLUSTER',
            'PROPOSITION_CLUSTER_MEMBER',
            'CONTENT_DERIVATION_FAMILY',
            'CONTENT_DERIVATION_CANDIDATE',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
