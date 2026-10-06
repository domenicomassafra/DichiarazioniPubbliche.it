-- DP-310: durable private review-event replay with an external identity-authority receipt.
--
-- This ledger is deliberately not an authentication authority. The database stores the
-- exact event plus the opaque authority receipt/binding used when it was appended. Replay
-- must resolve that receipt through a caller-owned ReviewerIdentityAuthority. A database
-- administrator can always fabricate database rows, so the trigger/checks below are only
-- defense in depth; they never turn the database itself into proof of reviewer identity.

CREATE TABLE IF NOT EXISTS publication_review_event_durable (
    event_id                            text PRIMARY KEY,
    record_id                           text NOT NULL,
    record_version                      text NOT NULL,
    sequence                            integer NOT NULL CHECK (sequence > 0),
    previous_event_id                   text,
    previous_integrity_sha256           text,
    actor_ref                           text NOT NULL,
    credential_fingerprint              text NOT NULL,
    policy_version                      text NOT NULL,
    reviewed_at_text                    text NOT NULL,
    event_json                          jsonb NOT NULL,
    integrity_sha256                    text NOT NULL,
    identity_authority_receipt_id       text NOT NULL,
    identity_authority_binding_sha256   text NOT NULL,
    persisted_at                        timestamptz NOT NULL DEFAULT now(),
    CHECK (integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (credential_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (
        previous_integrity_sha256 IS NULL
        OR previous_integrity_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CHECK (identity_authority_binding_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (event_json->>'event_id' = event_id),
    CHECK (event_json->>'record_id' = record_id),
    CHECK (event_json->>'record_version' = record_version),
    CHECK ((event_json->>'sequence')::integer = sequence),
    CHECK (event_json->>'actor_ref' = actor_ref),
    CHECK (event_json->>'credential_fingerprint' = credential_fingerprint),
    CHECK (event_json->>'policy_version' = policy_version),
    CHECK (event_json->>'reviewed_at' = reviewed_at_text),
    CHECK (event_json->>'integrity_sha256' = integrity_sha256),
    UNIQUE (record_id, sequence)
);

CREATE UNIQUE INDEX IF NOT EXISTS publication_review_event_durable_previous_idx
    ON publication_review_event_durable(previous_event_id)
    WHERE previous_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS publication_review_event_durable_record_idx
    ON publication_review_event_durable(record_id, sequence);

CREATE OR REPLACE FUNCTION reject_publication_review_event_durable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'publication_review_event_durable is append-only';
END;
$$;

DROP TRIGGER IF EXISTS publication_review_event_durable_append_only
    ON publication_review_event_durable;
CREATE TRIGGER publication_review_event_durable_append_only
BEFORE UPDATE OR DELETE ON publication_review_event_durable
FOR EACH ROW EXECUTE FUNCTION reject_publication_review_event_durable_mutation();

DROP TRIGGER IF EXISTS publication_review_event_durable_no_truncate
    ON publication_review_event_durable;
CREATE TRIGGER publication_review_event_durable_no_truncate
BEFORE TRUNCATE ON publication_review_event_durable
FOR EACH STATEMENT EXECUTE FUNCTION reject_publication_review_event_durable_mutation();
