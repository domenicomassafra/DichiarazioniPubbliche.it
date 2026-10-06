-- DP-304: private, append-only privacy/public-interest publication-decision ledger.
--
-- record_version is an opaque binding supplied by the caller. This table does not
-- establish record-version authority, reviewer identity authority, lawful basis,
-- retention periods, or public eligibility by itself. Runtime replay must bind the
-- stored review to the caller's current record version and re-run the canonical
-- privacy_policy decision over the exact current input digest.

CREATE TABLE IF NOT EXISTS privacy_publication_decision (
    decision_id                 text PRIMARY KEY,
    contract_version            text NOT NULL,
    subject_ref                 text NOT NULL,
    record_ref                  text NOT NULL,
    record_version              text NOT NULL,
    field_name                  text NOT NULL,
    data_class                  text NOT NULL,
    relevance_reason            text,
    explicitly_approved         boolean NOT NULL DEFAULT false,
    is_published_version        boolean NOT NULL DEFAULT false,
    is_ephemeral                boolean NOT NULL DEFAULT false,
    text_value_sha256           text,
    input_sha256                text NOT NULL,
    privacy_policy_version      text NOT NULL,
    decision_action             text NOT NULL,
    decision_reasons            jsonb NOT NULL,
    reviewer_ref                text NOT NULL,
    audit_ref                   text NOT NULL,
    reviewed_at_text            text NOT NULL,
    review_sequence             integer NOT NULL CHECK (review_sequence > 0),
    supersedes_decision_id      text REFERENCES privacy_publication_decision(decision_id)
                                ON DELETE RESTRICT,
    decision_integrity_sha256   text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'privacy-publication-decision-v1'),
    CHECK (decision_id = 'privacy-decision:' || decision_integrity_sha256),
    CHECK (length(subject_ref) BETWEEN 1 AND 256),
    CHECK (length(record_ref) BETWEEN 1 AND 256),
    CHECK (length(record_version) BETWEEN 1 AND 256),
    CHECK (length(field_name) BETWEEN 1 AND 128),
    CHECK (length(data_class) BETWEEN 1 AND 64),
    CHECK (relevance_reason IS NULL OR length(relevance_reason) <= 128),
    CHECK (text_value_sha256 IS NULL OR text_value_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (length(privacy_policy_version) BETWEEN 1 AND 128),
    CHECK (decision_action IN ('ALLOW', 'ALLOW_WITH_REDACTION', 'HOLD_FOR_REVIEW', 'PROHIBIT')),
    CHECK (jsonb_typeof(decision_reasons) = 'array'),
    CHECK (jsonb_array_length(decision_reasons) BETWEEN 1 AND 32),
    CHECK (length(reviewer_ref) BETWEEN 1 AND 128),
    CHECK (length(audit_ref) BETWEEN 1 AND 128),
    CHECK (length(reviewed_at_text) BETWEEN 1 AND 64),
    CHECK (decision_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (supersedes_decision_id IS NULL OR supersedes_decision_id <> decision_id),
    UNIQUE (subject_ref, record_ref, field_name, review_sequence)
);

CREATE UNIQUE INDEX IF NOT EXISTS privacy_publication_decision_root_idx
    ON privacy_publication_decision(subject_ref, record_ref, field_name)
    WHERE supersedes_decision_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS privacy_publication_decision_one_successor_idx
    ON privacy_publication_decision(supersedes_decision_id)
    WHERE supersedes_decision_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS privacy_publication_decision_record_idx
    ON privacy_publication_decision(subject_ref, record_ref, field_name, review_sequence DESC);

CREATE OR REPLACE FUNCTION validate_privacy_publication_decision_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent privacy_publication_decision%ROWTYPE;
BEGIN
    IF NEW.supersedes_decision_id IS NULL THEN
        IF NEW.review_sequence <> 1 THEN
            RAISE EXCEPTION 'privacy_publication_decision root sequence must be 1';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM privacy_publication_decision
    WHERE decision_id = NEW.supersedes_decision_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'privacy_publication_decision supersedes target missing';
    END IF;
    IF parent.subject_ref <> NEW.subject_ref
       OR parent.record_ref <> NEW.record_ref
       OR parent.field_name <> NEW.field_name THEN
        RAISE EXCEPTION 'privacy_publication_decision supersedes binding mismatch';
    END IF;
    IF NEW.review_sequence <> parent.review_sequence + 1 THEN
        RAISE EXCEPTION 'privacy_publication_decision sequence mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS privacy_publication_decision_validate_insert
    ON privacy_publication_decision;
CREATE TRIGGER privacy_publication_decision_validate_insert
BEFORE INSERT ON privacy_publication_decision
FOR EACH ROW EXECUTE FUNCTION validate_privacy_publication_decision_insert();

CREATE OR REPLACE FUNCTION reject_privacy_publication_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'privacy_publication_decision is append-only';
END;
$$;

DROP TRIGGER IF EXISTS privacy_publication_decision_append_only
    ON privacy_publication_decision;
CREATE TRIGGER privacy_publication_decision_append_only
BEFORE UPDATE OR DELETE ON privacy_publication_decision
FOR EACH ROW EXECUTE FUNCTION reject_privacy_publication_decision_mutation();

DROP TRIGGER IF EXISTS privacy_publication_decision_no_truncate
    ON privacy_publication_decision;
CREATE TRIGGER privacy_publication_decision_no_truncate
BEFORE TRUNCATE ON privacy_publication_decision
FOR EACH STATEMENT EXECUTE FUNCTION reject_privacy_publication_decision_mutation();
