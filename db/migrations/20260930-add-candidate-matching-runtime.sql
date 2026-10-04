BEGIN;

CREATE TABLE IF NOT EXISTS candidate_match_run (
    id                  text PRIMARY KEY,
    claim_candidate_id  text NOT NULL REFERENCES claim_candidate(id) ON DELETE CASCADE,
    matching_version    text NOT NULL DEFAULT 'candidate-matching-v1',
    input_fingerprint   text NOT NULL,
    status              text NOT NULL DEFAULT 'COMPLETED',
    result_count        integer NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (matching_version = 'candidate-matching-v1'),
    CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('COMPLETED', 'BLOCKED')),
    CHECK (result_count >= 0),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (claim_candidate_id, matching_version, input_fingerprint)
);

CREATE TABLE IF NOT EXISTS candidate_match_result (
    id                          text PRIMARY KEY,
    run_id                      text NOT NULL REFERENCES candidate_match_run(id) ON DELETE CASCADE,
    target_type                 text NOT NULL,
    target_claim_candidate_id   text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    target_atomic_claim_id      text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    rank                        integer NOT NULL,
    match_class                 text NOT NULL,
    method                      text NOT NULL,
    lexical_score               numeric(8,6) NOT NULL,
    supporting_features         jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features      jsonb NOT NULL DEFAULT '[]'::jsonb,
    disposition                 text NOT NULL,
    proposition_cluster_id      text REFERENCES proposition_cluster(id) ON DELETE SET NULL,
    matching_version            text NOT NULL DEFAULT 'candidate-matching-v1',
    status                      text NOT NULL DEFAULT 'CANDIDATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    metadata                    jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (target_type IN ('CLAIM_CANDIDATE', 'ATOMIC_CLAIM')),
    CHECK ((target_claim_candidate_id IS NOT NULL)::integer + (target_atomic_claim_id IS NOT NULL)::integer = 1),
    CHECK ((target_type = 'CLAIM_CANDIDATE' AND target_claim_candidate_id IS NOT NULL) OR (target_type = 'ATOMIC_CLAIM' AND target_atomic_claim_id IS NOT NULL)),
    CHECK (rank >= 1),
    CHECK (match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION', 'RELATED', 'DIFFERENT', 'UNCERTAIN')),
    CHECK (method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (lexical_score >= 0 AND lexical_score <= 1),
    CHECK (disposition IN ('PROPOSE_CLUSTER', 'HOLD', 'NO_CLUSTER')),
    CHECK ((disposition = 'PROPOSE_CLUSTER') = (proposition_cluster_id IS NOT NULL)),
    CHECK (matching_version = 'candidate-matching-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS candidate_match_run_candidate_idx
    ON candidate_match_run(claim_candidate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS candidate_match_result_run_idx
    ON candidate_match_result(run_id, rank);
CREATE UNIQUE INDEX IF NOT EXISTS candidate_match_result_candidate_unique
    ON candidate_match_result(run_id, target_claim_candidate_id)
    WHERE target_claim_candidate_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS candidate_match_result_atomic_unique
    ON candidate_match_result(run_id, target_atomic_claim_id)
    WHERE target_atomic_claim_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS candidate_match_result_atomic_idx
    ON candidate_match_result(target_atomic_claim_id, match_class)
    WHERE target_atomic_claim_id IS NOT NULL;

ALTER TABLE review_event DROP CONSTRAINT IF EXISTS review_event_entity_type_check;
ALTER TABLE review_event ADD CONSTRAINT review_event_entity_type_check CHECK (
    entity_type IN (
        'CLAIM_EVIDENCE_CANDIDATE','EVIDENCE_OBSERVATION','RELATION_CANDIDATE',
        'INFERENCE_CANDIDATE','CLAIM_TEXT_PROVENANCE','STATEMENT_CANDIDATE',
        'CLAIM_CANDIDATE','ENTITY_RESOLUTION_CANDIDATE','ENTITY_MENTION_CANDIDATE',
        'PROPOSITION_CLUSTER',
        'PROPOSITION_CLUSTER_MEMBER','CONTENT_DERIVATION_FAMILY',
        'CONTENT_DERIVATION_CANDIDATE','CANDIDATE_MATCH_RESULT','FINDING',
        'SPEAKER_IDENTITY_CANDIDATE','PERSON_ROLE_INTERVAL','RIGHT_OF_REPLY','CORRECTION'
    )
);

COMMIT;
