-- DP-304: private, append-only rights-case and private-access audit ledgers.
--
-- These tables encode product/runtime safety only. They do not select a lawful
-- basis, decide a legal right, or define a retention period. Rights cases remain
-- private; published history can only be held/reviewed by separate publication
-- workflows. Private access audit rows intentionally contain identifiers/counts,
-- never requested field names or private body content.

CREATE TABLE IF NOT EXISTS privacy_rights_case (
    case_id                     text PRIMARY KEY,
    contract_version            text NOT NULL DEFAULT 'privacy-rights-case-v1',
    subject_ref                 text NOT NULL,
    target_record_ref           text NOT NULL,
    request_kind                text NOT NULL,
    affects_published_version   boolean NOT NULL DEFAULT false,
    requester_ref_sha256        text,
    privacy_policy_version      text NOT NULL,
    opened_at_text              text NOT NULL,
    case_integrity_sha256       text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'privacy-rights-case-v1'),
    CHECK (case_id = 'privacy-rights-case:' || case_integrity_sha256),
    CHECK (length(subject_ref) BETWEEN 1 AND 256),
    CHECK (length(target_record_ref) BETWEEN 1 AND 256),
    CHECK (request_kind IN ('ACCESS', 'CORRECTION', 'RESTRICTION', 'OBJECTION', 'DELETION')),
    CHECK (requester_ref_sha256 IS NULL OR requester_ref_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (length(privacy_policy_version) BETWEEN 1 AND 128),
    CHECK (length(opened_at_text) BETWEEN 1 AND 64),
    CHECK (case_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE')
);

CREATE TABLE IF NOT EXISTS privacy_rights_case_event (
    event_id                    text PRIMARY KEY,
    contract_version            text NOT NULL DEFAULT 'privacy-rights-case-event-v1',
    case_id                     text NOT NULL REFERENCES privacy_rights_case(case_id)
                                ON DELETE RESTRICT,
    event_sequence              integer NOT NULL CHECK (event_sequence > 0),
    event_type                  text NOT NULL,
    actor_ref                   text NOT NULL,
    purpose_ref                 text NOT NULL,
    occurred_at_text            text NOT NULL,
    previous_event_id           text REFERENCES privacy_rights_case_event(event_id)
                                ON DELETE RESTRICT,
    event_integrity_sha256      text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'privacy-rights-case-event-v1'),
    CHECK (event_id = 'privacy-rights-event:' || event_integrity_sha256),
    CHECK (event_type IN ('OPEN_PRIVATE', 'REVIEW_PENDING', 'PUBLIC_HISTORY_HOLD_REQUIRED')),
    CHECK (length(actor_ref) BETWEEN 1 AND 128),
    CHECK (length(purpose_ref) BETWEEN 1 AND 128),
    CHECK (length(occurred_at_text) BETWEEN 1 AND 64),
    CHECK (event_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (previous_event_id IS NULL OR previous_event_id <> event_id),
    UNIQUE (case_id, event_sequence)
);

CREATE UNIQUE INDEX IF NOT EXISTS privacy_rights_case_event_one_successor_idx
    ON privacy_rights_case_event(previous_event_id)
    WHERE previous_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS privacy_rights_case_event_case_idx
    ON privacy_rights_case_event(case_id, event_sequence DESC, event_id);

CREATE OR REPLACE FUNCTION validate_privacy_rights_case_event_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent privacy_rights_case_event%ROWTYPE;
BEGIN
    IF NEW.previous_event_id IS NULL THEN
        IF NEW.event_sequence <> 1 OR NEW.event_type <> 'OPEN_PRIVATE' THEN
            RAISE EXCEPTION 'privacy_rights_case_event root must be OPEN_PRIVATE sequence 1';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM privacy_rights_case_event
    WHERE event_id = NEW.previous_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'privacy_rights_case_event previous event missing';
    END IF;
    IF parent.case_id <> NEW.case_id THEN
        RAISE EXCEPTION 'privacy_rights_case_event case binding mismatch';
    END IF;
    IF NEW.event_sequence <> parent.event_sequence + 1 THEN
        RAISE EXCEPTION 'privacy_rights_case_event sequence mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS privacy_rights_case_event_validate_insert
    ON privacy_rights_case_event;
CREATE TRIGGER privacy_rights_case_event_validate_insert
BEFORE INSERT ON privacy_rights_case_event
FOR EACH ROW EXECUTE FUNCTION validate_privacy_rights_case_event_insert();

CREATE OR REPLACE FUNCTION reject_privacy_rights_case_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'privacy rights case ledger is append-only';
END;
$$;

DROP TRIGGER IF EXISTS privacy_rights_case_append_only ON privacy_rights_case;
CREATE TRIGGER privacy_rights_case_append_only
BEFORE UPDATE OR DELETE ON privacy_rights_case
FOR EACH ROW EXECUTE FUNCTION reject_privacy_rights_case_mutation();
DROP TRIGGER IF EXISTS privacy_rights_case_no_truncate ON privacy_rights_case;
CREATE TRIGGER privacy_rights_case_no_truncate
BEFORE TRUNCATE ON privacy_rights_case
FOR EACH STATEMENT EXECUTE FUNCTION reject_privacy_rights_case_mutation();
DROP TRIGGER IF EXISTS privacy_rights_case_event_append_only ON privacy_rights_case_event;
CREATE TRIGGER privacy_rights_case_event_append_only
BEFORE UPDATE OR DELETE ON privacy_rights_case_event
FOR EACH ROW EXECUTE FUNCTION reject_privacy_rights_case_mutation();
DROP TRIGGER IF EXISTS privacy_rights_case_event_no_truncate ON privacy_rights_case_event;
CREATE TRIGGER privacy_rights_case_event_no_truncate
BEFORE TRUNCATE ON privacy_rights_case_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_privacy_rights_case_mutation();

CREATE TABLE IF NOT EXISTS private_access_audit_event (
    event_id                    text PRIMARY KEY,
    contract_version            text NOT NULL DEFAULT 'private-access-audit-v1',
    privacy_policy_version      text NOT NULL,
    actor_ref                   text NOT NULL,
    record_ref                  text NOT NULL,
    purpose_ref                 text NOT NULL,
    outcome                     text NOT NULL,
    occurred_at_text            text NOT NULL,
    requested_field_count       integer NOT NULL,
    legal_hold_active           boolean NOT NULL DEFAULT false,
    event_integrity_sha256      text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'private-access-audit-v1'),
    CHECK (event_id = 'private-access-audit:' || event_integrity_sha256),
    CHECK (length(privacy_policy_version) BETWEEN 1 AND 128),
    CHECK (length(actor_ref) BETWEEN 1 AND 128),
    CHECK (length(record_ref) BETWEEN 1 AND 128),
    CHECK (length(purpose_ref) BETWEEN 1 AND 128),
    CHECK (outcome IN ('ALLOW_READ_ONLY', 'DENY')),
    CHECK (length(occurred_at_text) BETWEEN 1 AND 64),
    CHECK (requested_field_count BETWEEN 0 AND 64),
    CHECK (event_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE')
);

CREATE INDEX IF NOT EXISTS private_access_audit_record_idx
    ON private_access_audit_event(record_ref, persisted_at, event_id);

CREATE OR REPLACE FUNCTION reject_private_access_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'private_access_audit_event is append-only';
END;
$$;

DROP TRIGGER IF EXISTS private_access_audit_append_only ON private_access_audit_event;
CREATE TRIGGER private_access_audit_append_only
BEFORE UPDATE OR DELETE ON private_access_audit_event
FOR EACH ROW EXECUTE FUNCTION reject_private_access_audit_mutation();
DROP TRIGGER IF EXISTS private_access_audit_no_truncate ON private_access_audit_event;
CREATE TRIGGER private_access_audit_no_truncate
BEFORE TRUNCATE ON private_access_audit_event
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_access_audit_mutation();
