BEGIN;

-- DP-430: an ACTIVE knowledge Topic is not public by existence alone. Public
-- membership is a separate reviewed assertion linking one atomic claim to one
-- stable Topic identity.
CREATE TABLE IF NOT EXISTS claim_topic_membership (
    id                              text PRIMARY KEY,
    claim_id                        text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    topic_id                        text NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    source_resolution_candidate_id  text REFERENCES entity_resolution_candidate(id),
    membership_version              text NOT NULL DEFAULT 'claim-topic-v1',
    status                          text NOT NULL DEFAULT 'CANDIDATE',
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at                      timestamptz NOT NULL DEFAULT now(),
    CHECK (membership_version = 'claim-topic-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS claim_topic_membership_approved_unique
    ON claim_topic_membership(claim_id, topic_id)
    WHERE status = 'APPROVED';
CREATE INDEX IF NOT EXISTS claim_topic_membership_topic_idx
    ON claim_topic_membership(topic_id, status, created_at);

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
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
