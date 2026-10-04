BEGIN;

-- DP-114: stable private knowledge entities and reviewable resolution.
CREATE TABLE IF NOT EXISTS topic (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    canonical_name      text NOT NULL,
    scope_text          text NOT NULL,
    entity_version      text NOT NULL DEFAULT 'knowledge-entity-v1',
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES topic(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_version = 'knowledge-entity-v1'),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id)
);

CREATE TABLE IF NOT EXISTS topic_alias (
    topic_id            text NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS event (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    canonical_name      text NOT NULL,
    scope_text          text NOT NULL,
    start_at            timestamptz,
    end_at              timestamptz,
    entity_version      text NOT NULL DEFAULT 'knowledge-entity-v1',
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES event(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_version = 'knowledge-entity-v1'),
    CHECK (end_at IS NULL OR start_at IS NULL OR end_at >= start_at),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id)
);

CREATE TABLE IF NOT EXISTS event_alias (
    event_id            text NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS organization_alias (
    organization_id     text NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS entity_identifier (
    id                  text PRIMARY KEY,
    entity_type         text NOT NULL,
    person_id           text REFERENCES person(id) ON DELETE CASCADE,
    organization_id     text REFERENCES organization(id) ON DELETE CASCADE,
    topic_id            text REFERENCES topic(id) ON DELETE CASCADE,
    event_id            text REFERENCES event(id) ON DELETE CASCADE,
    identifier_kind     text NOT NULL,
    identifier_value    text NOT NULL,
    authority           text NOT NULL,
    identifier_version  text NOT NULL DEFAULT 'entity-identifier-v1',
    source_ref          jsonb NOT NULL,
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES entity_identifier(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (identifier_version = 'entity-identifier-v1'),
    CHECK (jsonb_typeof(source_ref) = 'object'),
    CHECK (source_ref <> '{}'::jsonb),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CHECK (
        (person_id IS NOT NULL)::integer +
        (organization_id IS NOT NULL)::integer +
        (topic_id IS NOT NULL)::integer +
        (event_id IS NOT NULL)::integer = 1
    ),
    CHECK (
        (entity_type = 'PERSON' AND person_id IS NOT NULL) OR
        (entity_type = 'ORGANIZATION' AND organization_id IS NOT NULL) OR
        (entity_type = 'TOPIC' AND topic_id IS NOT NULL) OR
        (entity_type = 'EVENT' AND event_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_identifier_active_unique
    ON entity_identifier(entity_type, authority, identifier_kind, identifier_value)
    WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS entity_resolution_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id          text,
    mention_text        text NOT NULL,
    mention_text_sha256 text NOT NULL,
    entity_type         text NOT NULL,
    target_person_id    text REFERENCES person(id),
    target_organization_id text REFERENCES organization(id),
    target_topic_id     text REFERENCES topic(id),
    target_event_id     text REFERENCES event(id),
    resolution_method   text NOT NULL,
    resolution_version  text NOT NULL DEFAULT 'entity-resolution-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    retrieval_score     numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (mention_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (resolution_method IN ('EXACT_IDENTIFIER', 'KNOWN_ALIAS', 'CONTEXT_MATCH', 'MODEL_SUGGESTION', 'MANUAL_REVIEW')),
    CHECK (resolution_version = 'entity-resolution-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (retrieval_score IS NULL OR (retrieval_score >= 0 AND retrieval_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (
        (target_person_id IS NOT NULL)::integer +
        (target_organization_id IS NOT NULL)::integer +
        (target_topic_id IS NOT NULL)::integer +
        (target_event_id IS NOT NULL)::integer = 1
    ),
    CHECK (
        (entity_type = 'PERSON' AND target_person_id IS NOT NULL) OR
        (entity_type = 'ORGANIZATION' AND target_organization_id IS NOT NULL) OR
        (entity_type = 'TOPIC' AND target_topic_id IS NOT NULL) OR
        (entity_type = 'EVENT' AND target_event_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS entity_resolution_candidate_content_idx
    ON entity_resolution_candidate(content_id, status, entity_type, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_resolution_candidate_passage_idx
    ON entity_resolution_candidate(passage_id) WHERE passage_id IS NOT NULL;

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
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
