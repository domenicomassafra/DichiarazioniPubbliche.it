BEGIN;

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
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

ALTER TABLE right_of_reply
    DROP CONSTRAINT IF EXISTS right_of_reply_status_check;

ALTER TABLE right_of_reply
    ADD CONSTRAINT right_of_reply_status_check
    CHECK (
        status IN (
            'RECEIVED',
            'UNDER_REVIEW',
            'ACCEPTED',
            'PUBLISHED',
            'REJECTED',
            'WITHDRAWN'
        )
    );

COMMIT;
