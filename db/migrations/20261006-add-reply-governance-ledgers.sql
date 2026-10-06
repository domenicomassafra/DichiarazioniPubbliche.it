BEGIN;

-- DP-302: durable private abuse-decision audit. This ledger stores only bounded
-- machine metadata; request bodies, identity fields, URLs and raw bucket keys are
-- deliberately absent.
CREATE TABLE IF NOT EXISTS private_intake_abuse_event (
    event_id                    text PRIMARY KEY,
    event_version               text NOT NULL DEFAULT 'private-intake-abuse-event-v1',
    subject_digest_sha256       text NOT NULL,
    actor_ref                   text NOT NULL,
    guard_version               text NOT NULL,
    policy_version              text NOT NULL,
    decision_state              text NOT NULL,
    reason_code                 text NOT NULL,
    decision_time               timestamptz NOT NULL,
    signal_count                integer NOT NULL DEFAULT 0,
    event_integrity_sha256      text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (event_version = 'private-intake-abuse-event-v1'),
    CHECK (subject_digest_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (length(btrim(actor_ref)) BETWEEN 1 AND 256),
    CHECK (length(btrim(guard_version)) BETWEEN 1 AND 128),
    CHECK (length(btrim(policy_version)) BETWEEN 1 AND 128),
    CHECK (decision_state IN ('ALLOWED_PRIVATE','RATE_LIMITED','QUARANTINED','REPLAY','BLOCKED')),
    CHECK (reason_code ~ '^[A-Z0-9_]{1,96}$'),
    CHECK (signal_count BETWEEN 0 AND 99),
    CHECK (event_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (event_id = 'intake-abuse-event:' || event_integrity_sha256),
    CHECK (record_visibility = 'PRIVATE')
);

CREATE INDEX IF NOT EXISTS private_intake_abuse_event_subject_idx
    ON private_intake_abuse_event(subject_digest_sha256, decision_time, event_id);

-- DP-302: parameterized retention/legal-hold lifecycle for unpublished replies.
-- No retention duration or legal conclusion is encoded. PURGE_APPROVED requires an
-- opaque caller-supplied policy decision reference and a later PURGE_EXECUTED event
-- records the deletion while the audit trail survives the reply row.
CREATE TABLE IF NOT EXISTS private_reply_retention_event (
    event_id                    text PRIMARY KEY,
    event_version               text NOT NULL DEFAULT 'private-reply-retention-event-v1',
    reply_id                    text NOT NULL,
    finding_id                  text NOT NULL REFERENCES finding(id) ON DELETE RESTRICT,
    event_sequence              integer NOT NULL CHECK (event_sequence > 0),
    action                      text NOT NULL,
    actor_ref                   text NOT NULL,
    policy_decision_ref         text,
    reason_code                 text NOT NULL,
    previous_event_id           text REFERENCES private_reply_retention_event(event_id)
                                ON DELETE RESTRICT,
    previous_integrity_sha256   text,
    event_integrity_sha256      text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (event_version = 'private-reply-retention-event-v1'),
    CHECK (length(btrim(reply_id)) BETWEEN 1 AND 512),
    CHECK (length(btrim(finding_id)) BETWEEN 1 AND 512),
    CHECK (action IN ('RETAIN','LEGAL_HOLD_SET','LEGAL_HOLD_RELEASE','PURGE_APPROVED','PURGE_EXECUTED')),
    CHECK (length(btrim(actor_ref)) BETWEEN 1 AND 256),
    CHECK (policy_decision_ref IS NULL OR length(btrim(policy_decision_ref)) BETWEEN 1 AND 512),
    CHECK (reason_code ~ '^[A-Z0-9_]{1,96}$'),
    CHECK (
        action NOT IN ('LEGAL_HOLD_RELEASE','PURGE_APPROVED')
        OR policy_decision_ref IS NOT NULL
    ),
    CHECK (
        (event_sequence = 1 AND previous_event_id IS NULL AND previous_integrity_sha256 IS NULL)
        OR
        (event_sequence > 1 AND previous_event_id IS NOT NULL AND previous_integrity_sha256 IS NOT NULL)
    ),
    CHECK (previous_integrity_sha256 IS NULL OR previous_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (event_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (event_id = 'reply-retention-event:' || event_integrity_sha256),
    CHECK (record_visibility = 'PRIVATE')
);

CREATE UNIQUE INDEX IF NOT EXISTS private_reply_retention_event_sequence_idx
    ON private_reply_retention_event(reply_id, event_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS private_reply_retention_event_one_successor_idx
    ON private_reply_retention_event(previous_event_id)
    WHERE previous_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS private_reply_retention_event_reply_idx
    ON private_reply_retention_event(reply_id, event_sequence, event_id);

CREATE OR REPLACE FUNCTION validate_private_reply_retention_event_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent private_reply_retention_event%ROWTYPE;
BEGIN
    IF NEW.event_sequence = 1 THEN
        RETURN NEW;
    END IF;
    SELECT * INTO parent
    FROM private_reply_retention_event
    WHERE event_id = NEW.previous_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'private_reply_retention_event previous event missing';
    END IF;
    IF parent.reply_id <> NEW.reply_id OR parent.finding_id <> NEW.finding_id THEN
        RAISE EXCEPTION 'private_reply_retention_event binding mismatch';
    END IF;
    IF NEW.event_sequence <> parent.event_sequence + 1 THEN
        RAISE EXCEPTION 'private_reply_retention_event sequence mismatch';
    END IF;
    IF NEW.previous_integrity_sha256 <> parent.event_integrity_sha256 THEN
        RAISE EXCEPTION 'private_reply_retention_event integrity mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS private_reply_retention_event_validate_insert
    ON private_reply_retention_event;
CREATE TRIGGER private_reply_retention_event_validate_insert
BEFORE INSERT ON private_reply_retention_event
FOR EACH ROW EXECUTE FUNCTION validate_private_reply_retention_event_insert();

CREATE OR REPLACE FUNCTION reject_private_intake_abuse_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'private_intake_abuse_event is append-only';
END;
$$;
DROP TRIGGER IF EXISTS private_intake_abuse_event_append_only ON private_intake_abuse_event;
CREATE TRIGGER private_intake_abuse_event_append_only
BEFORE UPDATE OR DELETE ON private_intake_abuse_event
FOR EACH ROW EXECUTE FUNCTION reject_private_intake_abuse_event_mutation();
DROP TRIGGER IF EXISTS private_intake_abuse_event_no_truncate ON private_intake_abuse_event;
CREATE TRIGGER private_intake_abuse_event_no_truncate
BEFORE TRUNCATE ON private_intake_abuse_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_intake_abuse_event_mutation();

CREATE OR REPLACE FUNCTION reject_private_reply_retention_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'private_reply_retention_event is append-only';
END;
$$;
DROP TRIGGER IF EXISTS private_reply_retention_event_append_only ON private_reply_retention_event;
CREATE TRIGGER private_reply_retention_event_append_only
BEFORE UPDATE OR DELETE ON private_reply_retention_event
FOR EACH ROW EXECUTE FUNCTION reject_private_reply_retention_event_mutation();
DROP TRIGGER IF EXISTS private_reply_retention_event_no_truncate ON private_reply_retention_event;
CREATE TRIGGER private_reply_retention_event_no_truncate
BEFORE TRUNCATE ON private_reply_retention_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_reply_retention_event_mutation();

COMMIT;
