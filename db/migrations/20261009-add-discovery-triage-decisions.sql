BEGIN;

-- DP-417: private Discovery Hit triage history. A decision only records a
-- human/operator review state; it never captures, promotes, approves or publishes.
-- Both FKs are necessary, but not sufficient, to establish Collection/Hit scope:
-- Hit -> Run -> Manifest -> Collection is checked under row locks on INSERT.
-- The existing discovery_hit.disposition remains independent of this ledger.
CREATE TABLE IF NOT EXISTS research_discovery_triage_decision (
    collection_id       text NOT NULL REFERENCES research_collection(id) ON DELETE RESTRICT,
    hit_id              text NOT NULL REFERENCES research_discovery_hit(id) ON DELETE RESTRICT,
    revision            bigint NOT NULL,
    expected_revision   bigint NOT NULL,
    request_key         text NOT NULL,
    decision            text NOT NULL,
    payload_sha256      text NOT NULL,
    actor_ref           text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (hit_id, revision),
    UNIQUE (request_key),
    CHECK (revision > 0),
    CHECK (expected_revision BETWEEN 0 AND 9223372036854775806),
    CHECK (revision = expected_revision + 1),
    CHECK (request_key ~ '^[A-Za-z0-9_:/.-]{1,128}$'),
    CHECK (decision IN ('NEEDS_REVIEW', 'DEFERRED', 'REJECTED')),
    CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (actor_ref ~ '^[A-Za-z0-9_:/.-]{1,128}$')
);

CREATE INDEX IF NOT EXISTS research_discovery_triage_decision_collection_idx
    ON research_discovery_triage_decision(collection_id, created_at DESC);

CREATE OR REPLACE FUNCTION validate_research_discovery_triage_decision_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    linked integer;
    last_revision bigint;
BEGIN
    -- Serializes all writers for the same Hit, including direct SQL inserts.
    -- The joins also lock lineage parents through the end of this transaction.
    -- A Hit FK alone cannot establish that it belongs to NEW.collection_id.
    PERFORM pg_advisory_xact_lock(hashtextextended('dp417:hit:' || NEW.hit_id, 0));
    SELECT 1 INTO linked
    FROM research_discovery_hit AS hit
    JOIN research_discovery_run AS dr ON dr.id = hit.run_id
    JOIN research_discovery_manifest AS dm ON dm.id = dr.manifest_id
    JOIN research_discovery_attempt AS da
      ON da.id = hit.attempt_id AND da.run_id = dr.id
     AND da.query_id = hit.query_id
    JOIN research_discovery_query AS dq
      ON dq.id = hit.query_id AND dq.manifest_id = dm.id
    WHERE hit.id = NEW.hit_id AND dm.collection_id = NEW.collection_id
    FOR SHARE OF hit, dr, dm, da, dq;
    IF linked IS NULL THEN
        RAISE EXCEPTION 'research_discovery_triage_decision scope mismatch'
            USING ERRCODE = '23514';
    END IF;

    SELECT COALESCE(MAX(revision), 0) INTO last_revision
    FROM research_discovery_triage_decision
    WHERE hit_id = NEW.hit_id;

    IF NEW.expected_revision <> last_revision THEN
        RAISE EXCEPTION 'research_discovery_triage_decision revision conflict'
            USING ERRCODE = '40001';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_discovery_triage_decision_validate_insert
    ON research_discovery_triage_decision;
CREATE TRIGGER research_discovery_triage_decision_validate_insert
BEFORE INSERT ON research_discovery_triage_decision
FOR EACH ROW EXECUTE FUNCTION validate_research_discovery_triage_decision_insert();

CREATE OR REPLACE FUNCTION reject_research_discovery_triage_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'research_discovery_triage_decision is append-only';
END;
$$;

DROP TRIGGER IF EXISTS research_discovery_triage_decision_append_only
    ON research_discovery_triage_decision;
CREATE TRIGGER research_discovery_triage_decision_append_only
BEFORE UPDATE OR DELETE ON research_discovery_triage_decision
FOR EACH ROW EXECUTE FUNCTION reject_research_discovery_triage_decision_mutation();

DROP TRIGGER IF EXISTS research_discovery_triage_decision_no_truncate
    ON research_discovery_triage_decision;
CREATE TRIGGER research_discovery_triage_decision_no_truncate
BEFORE TRUNCATE ON research_discovery_triage_decision
FOR EACH STATEMENT EXECUTE FUNCTION reject_research_discovery_triage_decision_mutation();

-- Runtime still owns actor authentication, authorized transitions, verifying
-- request_key replay against the stored digest and context, and reading state
-- before any capture/promotion. A duplicate key must not silently change state.
COMMIT;
