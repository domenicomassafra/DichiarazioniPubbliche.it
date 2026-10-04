BEGIN;

CREATE TABLE IF NOT EXISTS claim_text_provenance (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    person_id           text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    selector_type       text NOT NULL,
    quote_sha256        text NOT NULL,
    source_sha256       text,
    start_char          integer,
    end_char            integer,
    attribution_method  text NOT NULL,
    attribution_version text NOT NULL DEFAULT 'text-source-provenance-v1',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (selector_type IN ('TEXT_QUOTE_HASH', 'TEXT_POSITION_HASH')),
    CHECK (quote_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK ((start_char IS NULL AND end_char IS NULL) OR (start_char >= 0 AND end_char > start_char)),
    CHECK (selector_type <> 'TEXT_POSITION_HASH' OR start_char IS NOT NULL),
    CHECK (attribution_method IN ('SOURCE_BYLINE', 'SOURCE_QUOTE', 'ACCOUNT_OWNER', 'OFFICIAL_RECORD', 'MANUAL_REVIEW')),
    CHECK (attribution_version = 'text-source-provenance-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE INDEX IF NOT EXISTS claim_text_provenance_claim_idx
    ON claim_text_provenance(claim_id, status, created_at DESC);

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
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
