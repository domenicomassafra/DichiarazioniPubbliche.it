-- DP-304 AC-304.2: private append-only public-interest relevance authority
-- for acquisition/ingestion. The authority exists before content persistence,
-- so it deliberately has no FK to content_item.

CREATE TABLE IF NOT EXISTS privacy_ingestion_relevance_authority (
    authority_id                 text PRIMARY KEY,
    contract_version             text NOT NULL,
    binding_version              text NOT NULL,
    content_ref                  text NOT NULL,
    content_binding_sha256       text NOT NULL,
    relevance_reason             text NOT NULL,
    privacy_policy_version       text NOT NULL,
    reviewer_ref                 text NOT NULL,
    audit_ref                    text NOT NULL,
    reviewed_at_text             text NOT NULL,
    review_sequence              integer NOT NULL,
    supersedes_authority_id      text REFERENCES privacy_ingestion_relevance_authority(authority_id),
    authority_integrity_sha256   text NOT NULL,
    record_visibility            text NOT NULL DEFAULT 'PRIVATE',
    created_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'privacy-ingestion-relevance-v1'),
    CHECK (binding_version = 'content-acquisition-binding-v1'),
    CHECK (length(content_ref) BETWEEN 1 AND 256),
    CHECK (content_binding_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (
        relevance_reason IN (
            'PUBLIC_ROLE',
            'PUBLIC_INTEREST_FUNCTION',
            'OFFICIAL_RECORD',
            'DOCUMENTED_PUBLIC_ACTIVITY'
        )
    ),
    CHECK (length(privacy_policy_version) BETWEEN 1 AND 128),
    CHECK (length(reviewer_ref) BETWEEN 1 AND 128),
    CHECK (length(audit_ref) BETWEEN 1 AND 128),
    CHECK (length(reviewed_at_text) BETWEEN 1 AND 64),
    CHECK (review_sequence >= 1),
    CHECK (supersedes_authority_id IS NULL OR supersedes_authority_id <> authority_id),
    CHECK (authority_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE')
);

CREATE UNIQUE INDEX IF NOT EXISTS privacy_ingestion_relevance_root_idx
    ON privacy_ingestion_relevance_authority(content_ref)
    WHERE supersedes_authority_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS privacy_ingestion_relevance_sequence_idx
    ON privacy_ingestion_relevance_authority(content_ref, review_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS privacy_ingestion_relevance_one_successor_idx
    ON privacy_ingestion_relevance_authority(supersedes_authority_id)
    WHERE supersedes_authority_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS privacy_ingestion_relevance_current_idx
    ON privacy_ingestion_relevance_authority(content_ref, review_sequence DESC);

CREATE TABLE IF NOT EXISTS privacy_ingestion_acquisition_permit (
    permit_id                    text PRIMARY KEY,
    contract_version             text NOT NULL,
    authority_id                 text NOT NULL REFERENCES privacy_ingestion_relevance_authority(authority_id),
    content_ref                  text NOT NULL,
    content_binding_sha256       text NOT NULL,
    operation_kind               text NOT NULL,
    operation_ref                text NOT NULL,
    permit_integrity_sha256      text NOT NULL,
    record_visibility            text NOT NULL DEFAULT 'PRIVATE',
    created_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'privacy-ingestion-acquisition-permit-v1'),
    CHECK (length(content_ref) BETWEEN 1 AND 256),
    CHECK (content_binding_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (
        operation_kind IN (
            'SCHEDULER_INGEST',
            'RESEARCH_DISCOVERY',
            'CURATED_WRITTEN',
            'CAPTURE_FETCH'
        )
    ),
    CHECK (length(operation_ref) BETWEEN 1 AND 256),
    CHECK (permit_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (record_visibility = 'PRIVATE'),
    UNIQUE (operation_kind, operation_ref)
);

CREATE INDEX IF NOT EXISTS privacy_ingestion_acquisition_permit_content_idx
    ON privacy_ingestion_acquisition_permit(content_ref, created_at DESC);

CREATE OR REPLACE FUNCTION validate_privacy_ingestion_relevance_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent privacy_ingestion_relevance_authority%ROWTYPE;
BEGIN
    IF NEW.supersedes_authority_id IS NULL THEN
        IF NEW.review_sequence <> 1 THEN
            RAISE EXCEPTION 'privacy_ingestion_relevance root sequence must be 1';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM privacy_ingestion_relevance_authority
    WHERE authority_id = NEW.supersedes_authority_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'privacy_ingestion_relevance supersedes target missing';
    END IF;
    IF parent.content_ref <> NEW.content_ref THEN
        RAISE EXCEPTION 'privacy_ingestion_relevance supersedes binding mismatch';
    END IF;
    IF NEW.review_sequence <> parent.review_sequence + 1 THEN
        RAISE EXCEPTION 'privacy_ingestion_relevance sequence mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS privacy_ingestion_relevance_validate_insert
    ON privacy_ingestion_relevance_authority;
CREATE TRIGGER privacy_ingestion_relevance_validate_insert
BEFORE INSERT ON privacy_ingestion_relevance_authority
FOR EACH ROW EXECUTE FUNCTION validate_privacy_ingestion_relevance_insert();

CREATE OR REPLACE FUNCTION reject_privacy_ingestion_relevance_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'privacy_ingestion_relevance_authority is append-only';
END;
$$;

DROP TRIGGER IF EXISTS privacy_ingestion_relevance_append_only
    ON privacy_ingestion_relevance_authority;
CREATE TRIGGER privacy_ingestion_relevance_append_only
BEFORE UPDATE OR DELETE ON privacy_ingestion_relevance_authority
FOR EACH ROW EXECUTE FUNCTION reject_privacy_ingestion_relevance_mutation();

DROP TRIGGER IF EXISTS privacy_ingestion_relevance_no_truncate
    ON privacy_ingestion_relevance_authority;
CREATE TRIGGER privacy_ingestion_relevance_no_truncate
BEFORE TRUNCATE ON privacy_ingestion_relevance_authority
FOR EACH STATEMENT EXECUTE FUNCTION reject_privacy_ingestion_relevance_mutation();

CREATE OR REPLACE FUNCTION reject_privacy_ingestion_acquisition_permit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'privacy_ingestion_acquisition_permit is append-only';
END;
$$;

DROP TRIGGER IF EXISTS privacy_ingestion_acquisition_permit_append_only
    ON privacy_ingestion_acquisition_permit;
CREATE TRIGGER privacy_ingestion_acquisition_permit_append_only
BEFORE UPDATE OR DELETE ON privacy_ingestion_acquisition_permit
FOR EACH ROW EXECUTE FUNCTION reject_privacy_ingestion_acquisition_permit_mutation();

DROP TRIGGER IF EXISTS privacy_ingestion_acquisition_permit_no_truncate
    ON privacy_ingestion_acquisition_permit;
CREATE TRIGGER privacy_ingestion_acquisition_permit_no_truncate
BEFORE TRUNCATE ON privacy_ingestion_acquisition_permit
FOR EACH STATEMENT EXECUTE FUNCTION reject_privacy_ingestion_acquisition_permit_mutation();
