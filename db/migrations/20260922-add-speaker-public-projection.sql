BEGIN;

CREATE TABLE IF NOT EXISTS speaker_identity_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    person_id           text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    start_ms            bigint NOT NULL,
    end_ms              bigint NOT NULL,
    speaker_label       text,
    attribution_method  text NOT NULL,
    attribution_version text NOT NULL,
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence          numeric(5,4),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (
        attribution_method IN (
            'MANUAL_REVIEW',
            'SOURCE_METADATA',
            'TRANSCRIPT_LABEL',
            'PLATFORM_CREDIT',
            'OFFICIAL_RECORD'
        )
    ),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE INDEX IF NOT EXISTS speaker_identity_candidate_content_idx
    ON speaker_identity_candidate(content_id, status, start_ms, end_ms);

ALTER TABLE right_of_reply
    ADD COLUMN IF NOT EXISTS public_visibility text NOT NULL DEFAULT 'PRIVATE';

ALTER TABLE right_of_reply
    DROP CONSTRAINT IF EXISTS right_of_reply_public_visibility_check;

ALTER TABLE right_of_reply
    ADD CONSTRAINT right_of_reply_public_visibility_check
    CHECK (public_visibility IN ('PRIVATE', 'PUBLIC'));

ALTER TABLE correction
    ADD COLUMN IF NOT EXISTS public_visibility text NOT NULL DEFAULT 'PRIVATE';

ALTER TABLE correction
    DROP CONSTRAINT IF EXISTS correction_public_visibility_check;

ALTER TABLE correction
    ADD CONSTRAINT correction_public_visibility_check
    CHECK (public_visibility IN ('PRIVATE', 'PUBLIC'));

ALTER TABLE review_event
    DROP CONSTRAINT IF EXISTS review_event_entity_type_check;

ALTER TABLE review_event
    ADD CONSTRAINT review_event_entity_type_check
    CHECK (
        entity_type IN (
            'CLAIM_EVIDENCE_CANDIDATE',
            'EVIDENCE_OBSERVATION',
            'RELATION_CANDIDATE',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE'
        )
    );

COMMIT;
