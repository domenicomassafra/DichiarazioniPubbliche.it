BEGIN;

-- DP-303: private append-only challenge request/event ledger.
-- This is workflow evidence only. It does not establish legal authority, publication
-- authority, deletion authority, or a public takedown route.
CREATE TABLE IF NOT EXISTS private_challenge_request (
    request_id                  text PRIMARY KEY,
    request_version             text NOT NULL DEFAULT 'private-challenge-request-v1',
    challenge_kind              text NOT NULL,
    target_finding_id           text NOT NULL REFERENCES finding(id) ON DELETE RESTRICT,
    target_record_version       text NOT NULL,
    source_request_ref          text NOT NULL,
    prior_decision_ref          text,
    initiated_by_actor_ref      text NOT NULL,
    initiated_by_role           text NOT NULL,
    reason                      text NOT NULL,
    policy_version              text NOT NULL,
    request_integrity_sha256    text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (request_version = 'private-challenge-request-v1'),
    CHECK (challenge_kind IN ('CORRECTION','TAKEDOWN','APPEAL')),
    CHECK (length(target_finding_id) BETWEEN 1 AND 256),
    CHECK (length(target_record_version) BETWEEN 1 AND 256),
    CHECK (length(source_request_ref) BETWEEN 1 AND 256),
    CHECK (prior_decision_ref IS NULL OR length(prior_decision_ref) BETWEEN 1 AND 256),
    CHECK (length(initiated_by_actor_ref) BETWEEN 1 AND 256),
    CHECK (initiated_by_role IN ('PUBLIC_SUBMITTER','INTAKE_ADAPTER','OPERATOR')),
    CHECK (length(reason) BETWEEN 1 AND 8000),
    CHECK (policy_version = 'challenge-workflow-v1'),
    CHECK (request_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (request_id = 'challenge-request:' || request_integrity_sha256),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (
        (challenge_kind = 'APPEAL' AND prior_decision_ref IS NOT NULL)
        OR (challenge_kind <> 'APPEAL' AND prior_decision_ref IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS private_challenge_request_identity_idx
    ON private_challenge_request(
        challenge_kind, target_finding_id, target_record_version, source_request_ref
    );
CREATE INDEX IF NOT EXISTS private_challenge_request_target_idx
    ON private_challenge_request(target_finding_id, challenge_kind, created_at, request_id);

CREATE TABLE IF NOT EXISTS private_challenge_event (
    event_id                    text PRIMARY KEY,
    event_version               text NOT NULL DEFAULT 'private-challenge-event-v1',
    request_id                  text NOT NULL
                                REFERENCES private_challenge_request(request_id)
                                ON DELETE RESTRICT,
    challenge_kind              text NOT NULL,
    event_sequence              integer NOT NULL CHECK (event_sequence > 0),
    from_state                  text,
    to_state                    text NOT NULL,
    actor_ref                   text NOT NULL,
    actor_role                  text NOT NULL,
    reason                      text NOT NULL,
    policy_version              text NOT NULL,
    target_record_version       text NOT NULL,
    transition_context          jsonb NOT NULL DEFAULT '{}'::jsonb,
    previous_event_id           text REFERENCES private_challenge_event(event_id)
                                ON DELETE RESTRICT,
    previous_integrity_sha256   text,
    event_integrity_sha256      text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (event_version = 'private-challenge-event-v1'),
    CHECK (challenge_kind IN ('CORRECTION','TAKEDOWN','APPEAL')),
    CHECK (
        from_state IS NULL OR from_state IN (
            'PRIVATE_RECEIVED','REANALYSIS_PENDING','TRIAGE_PENDING',
            'REVIEW_REQUIRED','INDEPENDENT_REVIEW_PENDING','PUBLIC_VERSIONED',
            'PUBLIC_HOLD_APPROVED','UPHELD','OVERTURNED','NEEDS_INFO',
            'REJECTED','QUARANTINED','REFERRED'
        )
    ),
    CHECK (to_state IN (
        'PRIVATE_RECEIVED','REANALYSIS_PENDING','TRIAGE_PENDING',
        'REVIEW_REQUIRED','INDEPENDENT_REVIEW_PENDING','PUBLIC_VERSIONED',
        'PUBLIC_HOLD_APPROVED','UPHELD','OVERTURNED','NEEDS_INFO',
        'REJECTED','QUARANTINED','REFERRED'
    )),
    CHECK (length(actor_ref) BETWEEN 1 AND 256),
    CHECK (actor_role IN (
        'PUBLIC_SUBMITTER','INTAKE_ADAPTER','TRIAGE_REVIEWER',
        'DECISION_REVIEWER','APPEAL_REVIEWER','OPERATOR'
    )),
    CHECK (length(reason) BETWEEN 1 AND 8000),
    CHECK (policy_version = 'challenge-workflow-v1'),
    CHECK (length(target_record_version) BETWEEN 1 AND 256),
    CHECK (jsonb_typeof(transition_context) = 'object'),
    CHECK (octet_length(transition_context::text) <= 8192),
    CHECK (
        previous_integrity_sha256 IS NULL
        OR previous_integrity_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CHECK (event_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (event_id = 'challenge-event:' || event_integrity_sha256),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (
        (
            event_sequence = 1
            AND previous_event_id IS NULL
            AND previous_integrity_sha256 IS NULL
            AND from_state IS NULL
            AND to_state = 'PRIVATE_RECEIVED'
        )
        OR (
            event_sequence > 1
            AND previous_event_id IS NOT NULL
            AND previous_integrity_sha256 IS NOT NULL
            AND from_state IS NOT NULL
        )
    ),
    CHECK (
        to_state <> 'PUBLIC_HOLD_APPROVED'
        OR (
            challenge_kind = 'TAKEDOWN'
            AND from_state = 'TRIAGE_PENDING'
            AND transition_context @> '{"challenge_review_approved":true}'::jsonb
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS private_challenge_event_sequence_idx
    ON private_challenge_event(request_id, event_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS private_challenge_event_one_successor_idx
    ON private_challenge_event(previous_event_id)
    WHERE previous_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS private_challenge_event_request_idx
    ON private_challenge_event(request_id, event_sequence, event_id);

CREATE OR REPLACE FUNCTION validate_private_challenge_event_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    request_row private_challenge_request%ROWTYPE;
    parent private_challenge_event%ROWTYPE;
BEGIN
    SELECT * INTO request_row
    FROM private_challenge_request
    WHERE request_id = NEW.request_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'private_challenge_event request missing';
    END IF;
    IF request_row.challenge_kind <> NEW.challenge_kind
       OR request_row.target_record_version <> NEW.target_record_version THEN
        RAISE EXCEPTION 'private_challenge_event request binding mismatch';
    END IF;

    IF NEW.event_sequence = 1 THEN
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM private_challenge_event
    WHERE event_id = NEW.previous_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'private_challenge_event previous event missing';
    END IF;
    IF parent.request_id <> NEW.request_id
       OR parent.challenge_kind <> NEW.challenge_kind
       OR parent.target_record_version <> NEW.target_record_version THEN
        RAISE EXCEPTION 'private_challenge_event previous binding mismatch';
    END IF;
    IF NEW.event_sequence <> parent.event_sequence + 1 THEN
        RAISE EXCEPTION 'private_challenge_event sequence mismatch';
    END IF;
    IF NEW.from_state <> parent.to_state THEN
        RAISE EXCEPTION 'private_challenge_event state chain mismatch';
    END IF;
    IF NEW.previous_integrity_sha256 <> parent.event_integrity_sha256 THEN
        RAISE EXCEPTION 'private_challenge_event integrity chain mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS private_challenge_event_validate_insert
    ON private_challenge_event;
CREATE TRIGGER private_challenge_event_validate_insert
BEFORE INSERT ON private_challenge_event
FOR EACH ROW EXECUTE FUNCTION validate_private_challenge_event_insert();

CREATE OR REPLACE FUNCTION reject_private_challenge_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'private_challenge_request is append-only';
END;
$$;

DROP TRIGGER IF EXISTS private_challenge_request_append_only
    ON private_challenge_request;
CREATE TRIGGER private_challenge_request_append_only
BEFORE UPDATE OR DELETE ON private_challenge_request
FOR EACH ROW EXECUTE FUNCTION reject_private_challenge_request_mutation();
DROP TRIGGER IF EXISTS private_challenge_request_no_truncate
    ON private_challenge_request;
CREATE TRIGGER private_challenge_request_no_truncate
BEFORE TRUNCATE ON private_challenge_request
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_challenge_request_mutation();

CREATE OR REPLACE FUNCTION reject_private_challenge_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'private_challenge_event is append-only';
END;
$$;

DROP TRIGGER IF EXISTS private_challenge_event_append_only
    ON private_challenge_event;
CREATE TRIGGER private_challenge_event_append_only
BEFORE UPDATE OR DELETE ON private_challenge_event
FOR EACH ROW EXECUTE FUNCTION reject_private_challenge_event_mutation();
DROP TRIGGER IF EXISTS private_challenge_event_no_truncate
    ON private_challenge_event;
CREATE TRIGGER private_challenge_event_no_truncate
BEFORE TRUNCATE ON private_challenge_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_challenge_event_mutation();

COMMIT;
