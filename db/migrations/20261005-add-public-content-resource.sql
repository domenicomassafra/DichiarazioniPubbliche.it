BEGIN;

-- DP-434: discovery/capture is not publication. This reviewed candidate
-- snapshots only the bounded metadata that may enter the public Content
-- resource; operational transcript/capture/provider fields are intentionally
-- absent from the table.
CREATE TABLE IF NOT EXISTS content_publication_candidate (
    id                      text PRIMARY KEY,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    slug                    text NOT NULL,
    canonical_url           text NOT NULL,
    title                   text NOT NULL,
    published_at            timestamptz,
    content_kind            text NOT NULL DEFAULT 'OTHER',
    duration_ms             bigint,
    public_media_url        text,
    media_policy_version    text,
    publication_version     text NOT NULL DEFAULT 'public-content-v1',
    status                  text NOT NULL DEFAULT 'CANDIDATE',
    supersedes_id           text REFERENCES content_publication_candidate(id),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    CHECK (length(btrim(canonical_url)) > 0),
    CHECK (length(btrim(title)) > 0),
    CHECK (content_kind IN ('VIDEO', 'AUDIO', 'WRITTEN', 'OTHER')),
    CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CHECK (publication_version = 'public-content-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (
        public_media_url IS NULL OR (
            content_kind IN ('VIDEO', 'AUDIO')
            AND media_policy_version IS NOT NULL
            AND length(btrim(media_policy_version)) > 0
        )
    ),
    CHECK (
        content_kind IN ('VIDEO', 'AUDIO')
        OR (duration_ms IS NULL AND public_media_url IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS content_publication_candidate_approved_unique
    ON content_publication_candidate(content_id)
    WHERE status = 'APPROVED';
CREATE UNIQUE INDEX IF NOT EXISTS content_publication_candidate_slug_approved_unique
    ON content_publication_candidate(slug)
    WHERE status = 'APPROVED';
CREATE INDEX IF NOT EXISTS content_publication_candidate_content_idx
    ON content_publication_candidate(content_id, status, created_at DESC);

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
            'CANDIDATE_MATCH_RESULT',
            'TOPIC',
            'CLAIM_TOPIC_MEMBERSHIP',
            'CONTENT_PUBLICATION_CANDIDATE',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
