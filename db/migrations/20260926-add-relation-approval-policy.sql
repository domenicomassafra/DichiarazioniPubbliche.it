BEGIN;

-- DP-104: Relation approval and publication policy constraints.
-- Public visibility is derived from the append-only review_event ledger
-- (entity_type='RELATION_CANDIDATE', action='APPROVED').
-- Storable states remain strictly ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED').
-- A mutable 'PUBLISHED' status is explicitly prohibited on relation candidates to
-- preserve review provenance and prevent unauthorized public projection.
-- Contradictions never imply deliberate falsehood or intent.

ALTER TABLE claim_relation_candidate
    ADD COLUMN IF NOT EXISTS policy_version text NOT NULL
        DEFAULT 'relation-publication-v1';

ALTER TABLE claim_relation_candidate
    DROP CONSTRAINT IF EXISTS claim_relation_candidate_policy_version_check;

ALTER TABLE claim_relation_candidate
    ADD CONSTRAINT claim_relation_candidate_policy_version_check
    CHECK (policy_version = 'relation-publication-v1');

ALTER TABLE claim_relation_candidate
    DROP CONSTRAINT IF EXISTS claim_relation_candidate_relation_version_check;

ALTER TABLE claim_relation_candidate
    ADD CONSTRAINT claim_relation_candidate_relation_version_check
    CHECK (relation_version = 'claim-relation-v1');

ALTER TABLE claim_relation_candidate
    DROP CONSTRAINT IF EXISTS claim_relation_candidate_status_check;

ALTER TABLE claim_relation_candidate
    ADD CONSTRAINT claim_relation_candidate_status_check
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'));

ALTER TABLE claim_relation_candidate
    DROP CONSTRAINT IF EXISTS claim_relation_candidate_relation_type_check;

ALTER TABLE claim_relation_candidate
    ADD CONSTRAINT claim_relation_candidate_relation_type_check
    CHECK (
        relation_type IN (
            'NO_RELATION',
            'RELATED_TOPIC',
            'SAME_PROPOSITION',
            'POSITION_CHANGE_CANDIDATE',
            'CONTRADICTION_CANDIDATE'
        )
    );

ALTER TABLE claim_relation_candidate
    DROP CONSTRAINT IF EXISTS claim_relation_candidate_distinct_claims_check;

ALTER TABLE claim_relation_candidate
    ADD CONSTRAINT claim_relation_candidate_distinct_claims_check
    CHECK (subject_claim_id <> object_claim_id);

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
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

ALTER TABLE review_event
    DROP CONSTRAINT IF EXISTS review_event_action_check;

ALTER TABLE review_event
    ADD CONSTRAINT review_event_action_check
    CHECK (
        action IN ('APPROVED', 'REJECTED', 'QUARANTINED', 'SUPERSEDED')
    );

COMMIT;
