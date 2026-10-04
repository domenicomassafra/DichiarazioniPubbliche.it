BEGIN;

-- DP-113: immutable observed versions of logical Content.
CREATE TABLE IF NOT EXISTS content_capture (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    observed_at         timestamptz NOT NULL,
    final_url           text NOT NULL,
    media_type          text,
    content_sha256      text NOT NULL,
    body_ref            text,
    retrieval_method    text NOT NULL,
    retrieval_version   text NOT NULL,
    parser_method       text,
    parser_version      text,
    rights_status       text NOT NULL DEFAULT 'UNKNOWN',
    retention_class     text NOT NULL DEFAULT 'POLICY_PENDING',
    status              text NOT NULL DEFAULT 'CAPTURED',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('CAPTURED', 'QUARANTINED', 'PURGED_BODY')),
    UNIQUE (content_id, content_sha256)
);

CREATE INDEX IF NOT EXISTS content_capture_content_idx
    ON content_capture(content_id, observed_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS content_capture_id_content_unique
    ON content_capture(id, content_id);

CREATE TABLE IF NOT EXISTS research_collection (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    name                text NOT NULL,
    scope_text          text NOT NULL,
    status              text NOT NULL DEFAULT 'ACTIVE',
    policy_version      text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('ACTIVE', 'PAUSED', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS research_collection_content (
    collection_id       text NOT NULL REFERENCES research_collection(id) ON DELETE CASCADE,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    inclusion_method    text NOT NULL,
    inclusion_version   text NOT NULL,
    status              text NOT NULL DEFAULT 'INCLUDED',
    rationale           text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (collection_id, content_id),
    CHECK (status IN ('INCLUDED', 'REJECTED', 'REMOVED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS canonical_segment_id_content_unique
    ON canonical_transcript_segment(id, content_id);

CREATE TABLE IF NOT EXISTS passage (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    capture_id          text,
    canonical_segment_id text,
    selector_type       text NOT NULL,
    start_char          integer,
    end_char            integer,
    page_start          integer,
    page_end            integer,
    text_sha256         text NOT NULL,
    private_text        text,
    language            text,
    extraction_method   text NOT NULL,
    extraction_version  text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id) ON DELETE CASCADE,
    CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK ((capture_id IS NOT NULL)::integer + (canonical_segment_id IS NOT NULL)::integer = 1),
    CHECK (selector_type IN ('TEXT_POSITION', 'PAGE_RANGE', 'MEDIA_SEGMENT_REF')),
    CHECK ((start_char IS NULL AND end_char IS NULL) OR (start_char >= 0 AND end_char > start_char)),
    CHECK ((page_start IS NULL AND page_end IS NULL) OR (page_start >= 1 AND page_end >= page_start)),
    CHECK (selector_type <> 'TEXT_POSITION' OR (capture_id IS NOT NULL AND start_char IS NOT NULL)),
    CHECK (selector_type <> 'PAGE_RANGE' OR (capture_id IS NOT NULL AND page_start IS NOT NULL)),
    CHECK (selector_type <> 'MEDIA_SEGMENT_REF' OR canonical_segment_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS passage_content_idx
    ON passage(content_id, created_at);
CREATE INDEX IF NOT EXISTS passage_capture_idx
    ON passage(capture_id) WHERE capture_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS statement_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    speaker_person_id   text REFERENCES person(id),
    statement_text_hash text NOT NULL,
    normalized_statement text NOT NULL,
    statement_at        timestamptz,
    attribution_method  text,
    extraction_model    text,
    extraction_version  text NOT NULL,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (statement_text_hash ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'HELD', 'SUPERSEDED')),
    UNIQUE (id, content_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS passage_id_content_unique
    ON passage(id, content_id);

CREATE TABLE IF NOT EXISTS statement_candidate_passage (
    statement_candidate_id text NOT NULL,
    passage_id              text NOT NULL,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    PRIMARY KEY (statement_candidate_id, passage_id),
    FOREIGN KEY (statement_candidate_id, content_id) REFERENCES statement_candidate(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS statement_candidate_content_idx
    ON statement_candidate(content_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS claim_candidate (
    id                  text PRIMARY KEY,
    statement_candidate_id text NOT NULL,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    normalized_claim    text NOT NULL,
    proposed_claim_type text NOT NULL,
    claim_type_version  text NOT NULL DEFAULT 'atomic-claim-v1',
    temporal_scope      jsonb NOT NULL DEFAULT '{}'::jsonb,
    check_worthy        boolean NOT NULL DEFAULT true,
    extraction_model    text,
    extraction_version  text NOT NULL,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    promoted_claim_id   text REFERENCES atomic_claim(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (statement_candidate_id, content_id) REFERENCES statement_candidate(id, content_id) ON DELETE CASCADE,
    CHECK (
        proposed_claim_type IN (
            'ARITHMETIC', 'CAUSAL_CLAIM', 'CURRENT_FOREIGN_POLICY',
            'CURRENT_POLICY', 'CURRENT_POLICY_POSITION',
            'DISTRIBUTIONAL_CLAIM', 'ELECTION_PREDICTION',
            'FISCAL_INFERENCE', 'GROUP_MOTIVE', 'HISTORICAL_ATTRIBUTION',
            'HISTORICAL_CLAIM', 'HISTORICAL_POLITICAL',
            'LEGAL_POLICY_STATUS', 'LEGAL_QUOTE', 'MOTIVE_ATTRIBUTION',
            'NUMERIC_STATISTIC', 'POLICY_DIFFERENCE', 'POLICY_SCOPE',
            'POLITICAL_ATTRIBUTION', 'PRICE_STATISTIC', 'QUOTE_ATTRIBUTION',
            'RHETORICAL_GENERALIZATION', 'SYSTEMIC_CLAIM',
            'SYSTEMIC_INFERENCE', 'TAX_RATE', 'VALUE_JUDGMENT'
        )
    ),
    CHECK (
        claim_type_version = 'atomic-claim-v1'
        AND (proposed_claim_type NOT IN ('RHETORICAL_GENERALIZATION', 'VALUE_JUDGMENT')
             OR check_worthy = false)
    ),
    CHECK (status IN ('CANDIDATE', 'DUPLICATE', 'PROMOTED', 'REJECTED', 'HELD')),
    CHECK ((status = 'PROMOTED') = (promoted_claim_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS claim_candidate_content_idx
    ON claim_candidate(content_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS claim_candidate_promoted_idx
    ON claim_candidate(promoted_claim_id) WHERE promoted_claim_id IS NOT NULL;

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
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
