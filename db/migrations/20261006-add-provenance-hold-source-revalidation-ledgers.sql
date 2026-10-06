-- DP-510/DP-511: durable private provenance-hold/dependency and source-revalidation history.
-- These ledgers are append-only operational authority for projection-time quarantine checks.

CREATE TABLE IF NOT EXISTS provenance_dependency_graph_snapshot (
    snapshot_id                 text PRIMARY KEY,
    snapshot_version            text NOT NULL DEFAULT 'provenance-dependency-graph-v1',
    snapshot_sequence           bigint NOT NULL CHECK (snapshot_sequence > 0),
    previous_snapshot_id        text REFERENCES provenance_dependency_graph_snapshot(snapshot_id),
    previous_integrity_sha256   text,
    graph_json                  jsonb NOT NULL,
    graph_sha256                text NOT NULL,
    integrity_sha256            text NOT NULL,
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (snapshot_version = 'provenance-dependency-graph-v1'),
    CHECK (jsonb_typeof(graph_json) = 'object'),
    CHECK (graph_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (
        previous_integrity_sha256 IS NULL
        OR previous_integrity_sha256 ~ '^[0-9a-f]{64}$'
    ),
    UNIQUE (snapshot_sequence)
);

CREATE UNIQUE INDEX IF NOT EXISTS provenance_dependency_graph_one_successor_idx
    ON provenance_dependency_graph_snapshot(previous_snapshot_id)
    WHERE previous_snapshot_id IS NOT NULL;

CREATE OR REPLACE FUNCTION validate_provenance_dependency_graph_snapshot_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent provenance_dependency_graph_snapshot%ROWTYPE;
BEGIN
    IF NEW.snapshot_sequence = 1 THEN
        IF NEW.previous_snapshot_id IS NOT NULL
           OR NEW.previous_integrity_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'provenance dependency root cannot have a parent';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.previous_snapshot_id IS NULL
       OR NEW.previous_integrity_sha256 IS NULL THEN
        RAISE EXCEPTION 'provenance dependency snapshot parent required';
    END IF;
    SELECT * INTO parent
    FROM provenance_dependency_graph_snapshot
    WHERE snapshot_id = NEW.previous_snapshot_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'provenance dependency snapshot parent missing';
    END IF;
    IF NEW.snapshot_sequence <> parent.snapshot_sequence + 1 THEN
        RAISE EXCEPTION 'provenance dependency snapshot sequence mismatch';
    END IF;
    IF NEW.previous_integrity_sha256 <> parent.integrity_sha256 THEN
        RAISE EXCEPTION 'provenance dependency snapshot integrity mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS provenance_dependency_graph_validate_insert
    ON provenance_dependency_graph_snapshot;
CREATE TRIGGER provenance_dependency_graph_validate_insert
BEFORE INSERT ON provenance_dependency_graph_snapshot
FOR EACH ROW EXECUTE FUNCTION validate_provenance_dependency_graph_snapshot_insert();

CREATE OR REPLACE FUNCTION reject_provenance_dependency_graph_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'provenance_dependency_graph_snapshot is append-only';
END;
$$;

DROP TRIGGER IF EXISTS provenance_dependency_graph_append_only
    ON provenance_dependency_graph_snapshot;
CREATE TRIGGER provenance_dependency_graph_append_only
BEFORE UPDATE OR DELETE ON provenance_dependency_graph_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_provenance_dependency_graph_snapshot_mutation();
DROP TRIGGER IF EXISTS provenance_dependency_graph_no_truncate
    ON provenance_dependency_graph_snapshot;
CREATE TRIGGER provenance_dependency_graph_no_truncate
BEFORE TRUNCATE ON provenance_dependency_graph_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION reject_provenance_dependency_graph_snapshot_mutation();

CREATE TABLE IF NOT EXISTS provenance_hold_event_durable (
    event_id                        text PRIMARY KEY,
    event_sequence                  integer NOT NULL CHECK (event_sequence > 0),
    request_id                      text NOT NULL UNIQUE,
    hold_id                         text NOT NULL,
    event_type                      text NOT NULL,
    actor_id                        text NOT NULL,
    reason_code                     text NOT NULL,
    incident_id                     text,
    scope_json                      jsonb NOT NULL,
    impact_binding_sha256           text NOT NULL,
    revalidation_binding_sha256     text,
    private_note_sha256             text,
    previous_event_hash             text NOT NULL,
    event_hash                      text NOT NULL,
    event_version                   text NOT NULL DEFAULT 'provenance-quarantine-v1',
    dependency_snapshot_id          text NOT NULL REFERENCES provenance_dependency_graph_snapshot(snapshot_id),
    persisted_at                    timestamptz NOT NULL DEFAULT now(),
    CHECK (event_type IN ('ACTIVATE', 'REVIEWED_UNHOLD', 'REVALIDATED')),
    CHECK (jsonb_typeof(scope_json) = 'object'),
    CHECK (impact_binding_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (
        revalidation_binding_sha256 IS NULL
        OR revalidation_binding_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CHECK (
        private_note_sha256 IS NULL
        OR private_note_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CHECK (previous_event_hash ~ '^[0-9a-f]{64}$'),
    CHECK (event_hash ~ '^[0-9a-f]{64}$'),
    CHECK (event_version = 'provenance-quarantine-v1'),
    CHECK (
        (event_type = 'REVALIDATED' AND revalidation_binding_sha256 IS NOT NULL)
        OR (event_type <> 'REVALIDATED' AND revalidation_binding_sha256 IS NULL)
    ),
    UNIQUE (event_sequence),
    UNIQUE (hold_id, event_type)
);

CREATE INDEX IF NOT EXISTS provenance_hold_event_hold_idx
    ON provenance_hold_event_durable(hold_id, event_sequence);

CREATE OR REPLACE FUNCTION validate_provenance_hold_event_durable_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent provenance_hold_event_durable%ROWTYPE;
BEGIN
    IF NEW.event_sequence = 1 THEN
        IF NEW.previous_event_hash <> repeat('0', 64) THEN
            RAISE EXCEPTION 'provenance hold root previous hash mismatch';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM provenance_hold_event_durable
    WHERE event_sequence = NEW.event_sequence - 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'provenance hold previous event missing';
    END IF;
    IF NEW.previous_event_hash <> parent.event_hash THEN
        RAISE EXCEPTION 'provenance hold event hash chain mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS provenance_hold_event_validate_insert
    ON provenance_hold_event_durable;
CREATE TRIGGER provenance_hold_event_validate_insert
BEFORE INSERT ON provenance_hold_event_durable
FOR EACH ROW EXECUTE FUNCTION validate_provenance_hold_event_durable_insert();

CREATE OR REPLACE FUNCTION reject_provenance_hold_event_durable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'provenance_hold_event_durable is append-only';
END;
$$;

DROP TRIGGER IF EXISTS provenance_hold_event_durable_append_only
    ON provenance_hold_event_durable;
CREATE TRIGGER provenance_hold_event_durable_append_only
BEFORE UPDATE OR DELETE ON provenance_hold_event_durable
FOR EACH ROW EXECUTE FUNCTION reject_provenance_hold_event_durable_mutation();
DROP TRIGGER IF EXISTS provenance_hold_event_durable_no_truncate
    ON provenance_hold_event_durable;
CREATE TRIGGER provenance_hold_event_durable_no_truncate
BEFORE TRUNCATE ON provenance_hold_event_durable
FOR EACH STATEMENT EXECUTE FUNCTION reject_provenance_hold_event_durable_mutation();

CREATE TABLE IF NOT EXISTS source_revalidation_snapshot_durable (
    snapshot_ref                text PRIMARY KEY,
    source_id                   text NOT NULL REFERENCES source(id),
    content_id                  text REFERENCES content_item(id),
    capture_id                  text REFERENCES content_capture(id),
    observed_at                 timestamptz NOT NULL,
    availability                text NOT NULL,
    content_sha256              text,
    source_version              text,
    etag                        text,
    canonical_url               text NOT NULL,
    supersedes_version          text,
    rights_status               text NOT NULL,
    rights_expires_on           date,
    authority_valid_until       date,
    snapshot_version            text NOT NULL DEFAULT 'source-revalidation-v1',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (snapshot_ref ~ '^[0-9a-f]{64}$'),
    CHECK (availability IN ('AVAILABLE', 'UNAVAILABLE')),
    CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (snapshot_version = 'source-revalidation-v1')
);

CREATE INDEX IF NOT EXISTS source_revalidation_snapshot_source_idx
    ON source_revalidation_snapshot_durable(source_id, observed_at, snapshot_ref);

CREATE TABLE IF NOT EXISTS source_revalidation_event_durable (
    event_key                   text PRIMARY KEY,
    source_id                   text NOT NULL REFERENCES source(id),
    previous_snapshot_ref       text NOT NULL REFERENCES source_revalidation_snapshot_durable(snapshot_ref),
    current_snapshot_ref        text NOT NULL REFERENCES source_revalidation_snapshot_durable(snapshot_ref),
    disposition                 text NOT NULL,
    material_change_codes       jsonb NOT NULL DEFAULT '[]'::jsonb,
    benign_change_codes         jsonb NOT NULL DEFAULT '[]'::jsonb,
    needs_reanalysis            boolean NOT NULL,
    needs_targeted_hold         boolean NOT NULL,
    event_version               text NOT NULL DEFAULT 'source-revalidation-v1',
    persisted_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (event_key ~ '^[0-9a-f]{64}$'),
    CHECK (disposition IN ('UNCHANGED', 'AVAILABILITY_RETRY', 'REVIEW_REQUIRED', 'HOLD_REQUIRED')),
    CHECK (jsonb_typeof(material_change_codes) = 'array'),
    CHECK (jsonb_typeof(benign_change_codes) = 'array'),
    CHECK (event_version = 'source-revalidation-v1'),
    CHECK (previous_snapshot_ref <> current_snapshot_ref)
);

CREATE INDEX IF NOT EXISTS source_revalidation_event_source_idx
    ON source_revalidation_event_durable(source_id, persisted_at, event_key);

CREATE OR REPLACE FUNCTION reject_source_revalidation_durable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'source revalidation history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS source_revalidation_snapshot_append_only
    ON source_revalidation_snapshot_durable;
CREATE TRIGGER source_revalidation_snapshot_append_only
BEFORE UPDATE OR DELETE ON source_revalidation_snapshot_durable
FOR EACH ROW EXECUTE FUNCTION reject_source_revalidation_durable_mutation();
DROP TRIGGER IF EXISTS source_revalidation_snapshot_no_truncate
    ON source_revalidation_snapshot_durable;
CREATE TRIGGER source_revalidation_snapshot_no_truncate
BEFORE TRUNCATE ON source_revalidation_snapshot_durable
FOR EACH STATEMENT EXECUTE FUNCTION reject_source_revalidation_durable_mutation();

DROP TRIGGER IF EXISTS source_revalidation_event_append_only
    ON source_revalidation_event_durable;
CREATE TRIGGER source_revalidation_event_append_only
BEFORE UPDATE OR DELETE ON source_revalidation_event_durable
FOR EACH ROW EXECUTE FUNCTION reject_source_revalidation_durable_mutation();
DROP TRIGGER IF EXISTS source_revalidation_event_no_truncate
    ON source_revalidation_event_durable;
CREATE TRIGGER source_revalidation_event_no_truncate
BEFORE TRUNCATE ON source_revalidation_event_durable
FOR EACH STATEMENT EXECUTE FUNCTION reject_source_revalidation_durable_mutation();
