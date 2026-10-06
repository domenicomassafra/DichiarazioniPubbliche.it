BEGIN;

-- DP-305 AC-305.1: private, versioned source/content/evidence/segment rights registry.
--
-- This table records an operator/counsel-supplied rights state; it never grants rights,
-- never stores a rights-receipt body, and never authorizes a public excerpt. UNKNOWN is
-- the database default. Public excerpt decisions remain the separate DP-305 policy gate.
CREATE TABLE IF NOT EXISTS private_source_rights_record (
    id                          text PRIMARY KEY,
    subject_fingerprint         text NOT NULL,
    source_family               text NOT NULL,
    locator_kind                text NOT NULL,
    locator_value               text NOT NULL,
    content_id                  text REFERENCES content_item(id) ON DELETE RESTRICT,
    evidence_id                 text REFERENCES evidence(id) ON DELETE RESTRICT,
    transcript_segment_id       text REFERENCES transcript_segment(id) ON DELETE RESTRICT,
    canonical_segment_id        text REFERENCES canonical_transcript_segment(id) ON DELETE RESTRICT,
    passage_id                  text REFERENCES passage(id) ON DELETE RESTRICT,
    rights_status               text NOT NULL DEFAULT 'UNKNOWN',
    rights_receipt_ref          text,
    permitted_uses              text[] NOT NULL DEFAULT ARRAY[]::text[],
    attribution_requirements    text[] NOT NULL DEFAULT ARRAY[]::text[],
    reviewed_at                 timestamptz,
    expires_at                  timestamptz,
    reviewer_ref                text,
    policy_version              text NOT NULL,
    record_visibility           text NOT NULL DEFAULT 'PRIVATE',
    supersedes_id               text REFERENCES private_source_rights_record(id) ON DELETE RESTRICT,
    record_version              text NOT NULL DEFAULT 'private-rights-record-v1',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (subject_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (length(btrim(source_family)) BETWEEN 1 AND 128),
    CHECK (length(btrim(locator_kind)) BETWEEN 1 AND 64),
    CHECK (length(btrim(locator_value)) BETWEEN 1 AND 2048),
    CHECK (rights_status IN (
        'UNKNOWN', 'UNRESOLVED', 'EXPIRED', 'CONFLICTING', 'REVOKED',
        'BLOCKED', 'FORBIDDEN', 'LEGAL_HOLD', 'RIGHTS_HOLD',
        'TAKEDOWN_HOLD', 'REMOVED', 'CLEARED'
    )),
    CHECK (
        rights_receipt_ref IS NULL
        OR length(btrim(rights_receipt_ref)) BETWEEN 1 AND 512
    ),
    CHECK (cardinality(permitted_uses) <= 32),
    CHECK (cardinality(attribution_requirements) <= 32),
    CHECK ((reviewed_at IS NULL) = (reviewer_ref IS NULL)),
    CHECK (expires_at IS NULL OR reviewed_at IS NULL OR expires_at >= reviewed_at),
    CHECK (
        rights_status IN ('UNKNOWN', 'UNRESOLVED')
        OR rights_receipt_ref IS NOT NULL
    ),
    CHECK (
        rights_status <> 'CLEARED'
        OR (
            rights_receipt_ref IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND reviewer_ref IS NOT NULL
        )
    ),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (record_version = 'private-rights-record-v1'),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CHECK (num_nonnulls(transcript_segment_id, canonical_segment_id, passage_id) <= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS private_source_rights_record_root_unique
    ON private_source_rights_record(subject_fingerprint)
    WHERE supersedes_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS private_source_rights_record_one_successor
    ON private_source_rights_record(supersedes_id)
    WHERE supersedes_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS private_source_rights_record_subject_idx
    ON private_source_rights_record(subject_fingerprint, created_at DESC, id);

CREATE INDEX IF NOT EXISTS private_source_rights_record_content_idx
    ON private_source_rights_record(content_id, created_at DESC)
    WHERE content_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS private_source_rights_record_evidence_idx
    ON private_source_rights_record(evidence_id, created_at DESC)
    WHERE evidence_id IS NOT NULL;

CREATE OR REPLACE FUNCTION validate_private_source_rights_record_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_subject text;
BEGIN
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT subject_fingerprint INTO parent_subject
        FROM private_source_rights_record
        WHERE id = NEW.supersedes_id;

        IF parent_subject IS NULL THEN
            RAISE EXCEPTION 'private_source_rights_record supersedes target missing';
        END IF;
        IF parent_subject <> NEW.subject_fingerprint THEN
            RAISE EXCEPTION 'private_source_rights_record supersedes subject mismatch';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS private_source_rights_record_validate_insert
    ON private_source_rights_record;
CREATE TRIGGER private_source_rights_record_validate_insert
BEFORE INSERT ON private_source_rights_record
FOR EACH ROW EXECUTE FUNCTION validate_private_source_rights_record_insert();

CREATE OR REPLACE FUNCTION reject_private_source_rights_record_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'private_source_rights_record is append-only';
END;
$$;

DROP TRIGGER IF EXISTS private_source_rights_record_append_only
    ON private_source_rights_record;
CREATE TRIGGER private_source_rights_record_append_only
BEFORE UPDATE OR DELETE ON private_source_rights_record
FOR EACH ROW EXECUTE FUNCTION reject_private_source_rights_record_mutation();

DROP TRIGGER IF EXISTS private_source_rights_record_no_truncate
    ON private_source_rights_record;
CREATE TRIGGER private_source_rights_record_no_truncate
BEFORE TRUNCATE ON private_source_rights_record
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_source_rights_record_mutation();

COMMIT;
