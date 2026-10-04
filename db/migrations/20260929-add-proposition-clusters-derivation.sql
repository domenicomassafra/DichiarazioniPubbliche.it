BEGIN;

-- DP-115: private source-derivation families and reviewable edges.
CREATE TABLE IF NOT EXISTS content_derivation_family (
    id                  text PRIMARY KEY,
    root_content_id     text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    family_version      text NOT NULL DEFAULT 'content-derivation-v1',
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (family_version = 'content-derivation-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE TABLE IF NOT EXISTS content_derivation_candidate (
    id                  text PRIMARY KEY,
    family_id           text NOT NULL REFERENCES content_derivation_family(id) ON DELETE CASCADE,
    derived_content_id  text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    origin_content_id   text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    relation_type       text NOT NULL,
    derivation_method   text NOT NULL,
    derivation_version  text NOT NULL DEFAULT 'content-derivation-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    lexical_score       numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (derived_content_id <> origin_content_id),
    CHECK (relation_type IN ('REPUBLICATION', 'SYNDICATION', 'QUOTATION', 'PRESS_RELEASE_DERIVED', 'UNKNOWN_DERIVATION')),
    CHECK (derivation_method IN ('EXACT_BODY_HASH', 'EXPLICIT_SOURCE_CREDIT', 'LEXICAL_OVERLAP', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (derivation_version = 'content-derivation-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (lexical_score IS NULL OR (lexical_score >= 0 AND lexical_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    UNIQUE (family_id, derived_content_id, origin_content_id, derivation_version)
);

CREATE INDEX IF NOT EXISTS content_derivation_candidate_family_idx
    ON content_derivation_candidate(family_id, status, derived_content_id);
CREATE INDEX IF NOT EXISTS content_derivation_candidate_origin_idx
    ON content_derivation_candidate(origin_content_id, status);
CREATE INDEX IF NOT EXISTS content_derivation_candidate_derived_idx
    ON content_derivation_candidate(derived_content_id, status);

CREATE TABLE IF NOT EXISTS proposition_cluster (
    id                  text PRIMARY KEY,
    representative_text text NOT NULL,
    cluster_method      text NOT NULL,
    cluster_version     text NOT NULL DEFAULT 'proposition-cluster-v1',
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (cluster_method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (cluster_version = 'proposition-cluster-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE TABLE IF NOT EXISTS proposition_cluster_member (
    id                  text PRIMARY KEY,
    cluster_id          text NOT NULL REFERENCES proposition_cluster(id) ON DELETE CASCADE,
    member_type         text NOT NULL,
    claim_candidate_id  text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    atomic_claim_id     text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    match_class         text NOT NULL,
    membership_method   text NOT NULL,
    membership_version  text NOT NULL DEFAULT 'proposition-cluster-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    lexical_score       numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (member_type IN ('CLAIM_CANDIDATE', 'ATOMIC_CLAIM')),
    CHECK ((claim_candidate_id IS NOT NULL)::integer + (atomic_claim_id IS NOT NULL)::integer = 1),
    CHECK ((member_type = 'CLAIM_CANDIDATE' AND claim_candidate_id IS NOT NULL) OR (member_type = 'ATOMIC_CLAIM' AND atomic_claim_id IS NOT NULL)),
    CHECK (match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION', 'RELATED', 'DIFFERENT', 'UNCERTAIN')),
    CHECK (membership_method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (membership_version = 'proposition-cluster-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (lexical_score IS NULL OR (lexical_score >= 0 AND lexical_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS proposition_cluster_member_claim_candidate_unique
    ON proposition_cluster_member(cluster_id, claim_candidate_id)
    WHERE claim_candidate_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS proposition_cluster_member_atomic_claim_unique
    ON proposition_cluster_member(cluster_id, atomic_claim_id)
    WHERE atomic_claim_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS proposition_cluster_member_status_idx
    ON proposition_cluster_member(cluster_id, status, match_class);

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
