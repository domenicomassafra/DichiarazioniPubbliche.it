-- DP-232: private persisted mirror lineage for existing ClaimReview/fact-check lookups.
--
-- These tables are private research state. They do not grant publication rights and are
-- intentionally absent from the public projection SQL. DP-305 remains the authority for
-- any bounded public excerpt.

CREATE TABLE IF NOT EXISTS existing_factcheck_lineage (
    id                  text PRIMARY KEY,
    upstream_record_id  text NOT NULL UNIQUE,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS existing_factcheck_version (
    id                      text PRIMARY KEY,
    lineage_id              text NOT NULL REFERENCES existing_factcheck_lineage(id),
    source_version          text NOT NULL,
    source_content_sha256   text NOT NULL,
    supersedes_version_id   text REFERENCES existing_factcheck_version(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    CHECK (source_content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (supersedes_version_id IS NULL OR supersedes_version_id <> id),
    UNIQUE (lineage_id, source_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS existing_factcheck_version_one_successor_idx
    ON existing_factcheck_version(supersedes_version_id)
    WHERE supersedes_version_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS existing_factcheck_version_lineage_idx
    ON existing_factcheck_version(lineage_id, created_at, id);

CREATE TABLE IF NOT EXISTS existing_factcheck_mirror (
    id                          text PRIMARY KEY,
    version_id                  text NOT NULL REFERENCES existing_factcheck_version(id),
    provider_id                 text NOT NULL,
    source_external_id          text NOT NULL,
    source_version              text NOT NULL,
    review_url                  text NOT NULL,
    rights_status               text NOT NULL DEFAULT 'UNKNOWN',
    research_assignment_id      text NOT NULL,
    discovery_attempt_id        text NOT NULL REFERENCES research_discovery_attempt(id),
    discovery_hit_id            text NOT NULL REFERENCES research_discovery_hit(id),
    provider_receipt_sha256     text NOT NULL,
    normalized_record_sha256    text NOT NULL,
    normalized_record           jsonb NOT NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CHECK (provider_receipt_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (normalized_record_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(normalized_record) = 'object'),
    UNIQUE (provider_id, source_external_id, source_version),
    UNIQUE (discovery_hit_id)
);

CREATE INDEX IF NOT EXISTS existing_factcheck_mirror_version_idx
    ON existing_factcheck_mirror(version_id, provider_id, source_external_id);

CREATE OR REPLACE FUNCTION reject_existing_factcheck_mirror_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'existing factcheck mirror lineage is append-only';
END;
$$;

DROP TRIGGER IF EXISTS existing_factcheck_lineage_append_only ON existing_factcheck_lineage;
CREATE TRIGGER existing_factcheck_lineage_append_only
BEFORE UPDATE OR DELETE ON existing_factcheck_lineage
FOR EACH ROW EXECUTE FUNCTION reject_existing_factcheck_mirror_mutation();

DROP TRIGGER IF EXISTS existing_factcheck_version_append_only ON existing_factcheck_version;
CREATE TRIGGER existing_factcheck_version_append_only
BEFORE UPDATE OR DELETE ON existing_factcheck_version
FOR EACH ROW EXECUTE FUNCTION reject_existing_factcheck_mirror_mutation();

DROP TRIGGER IF EXISTS existing_factcheck_mirror_append_only ON existing_factcheck_mirror;
CREATE TRIGGER existing_factcheck_mirror_append_only
BEFORE UPDATE OR DELETE ON existing_factcheck_mirror
FOR EACH ROW EXECUTE FUNCTION reject_existing_factcheck_mirror_mutation();
