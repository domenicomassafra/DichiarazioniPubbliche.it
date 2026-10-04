BEGIN;

-- DP-101: additive organization + person role interval model.
-- Replay-idempotent: every statement is IF NOT EXISTS / CREATE OR REPLACE
-- so fresh schema.v0.sql installs and replayed incremental upgrades
-- converge on the same shape.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS organization (
    id                  text PRIMARY KEY,
    canonical_name      text NOT NULL,
    organization_type   text NOT NULL DEFAULT 'GENERAL',
    country_code        text,
    canonical_url       text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Person role interval: a dated relationship between a Person and an
-- organization, office, publication, program, or public role.
-- Semantics: a half-open interval [start_date, end_date); start_date is
-- required and end_date is exclusive for range/lookup purposes, while
-- end_date NULL still means the interval is open/current. Public role
-- claims require a provenance source_ref. Corrections are append-only:
-- insert a corrected row with supersedes_id pointing at the row it replaces
-- and mark that row SUPERSEDED. ACTIVE intervals must not overlap for the
-- same person + organization + role (adjacent intervals may share a
-- boundary date).
CREATE TABLE IF NOT EXISTS person_role_interval (
    id                  text PRIMARY KEY,
    person_id           text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    organization_id     text NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    role                text NOT NULL,
    start_date          date NOT NULL,
    end_date            date,
    is_public_role      boolean NOT NULL DEFAULT true,
    source_ref          jsonb,
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES person_role_interval(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (end_date IS NULL OR end_date >= start_date),
    CHECK (source_ref IS NULL OR jsonb_typeof(source_ref) = 'object'),
    CHECK (is_public_role = false OR source_ref IS NOT NULL),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CONSTRAINT person_role_interval_overlap_excl
        EXCLUDE USING gist (
            person_id WITH =,
            organization_id WITH =,
            role WITH =,
            daterange(start_date, end_date, '[)'::text) WITH &&
        ) WHERE (status = 'ACTIVE')
);

CREATE INDEX IF NOT EXISTS person_role_interval_person_idx
    ON person_role_interval(person_id, status, start_date, end_date);
CREATE INDEX IF NOT EXISTS person_role_interval_org_idx
    ON person_role_interval(organization_id, start_date);

-- Time-specific role lookup: active role intervals for a person on a given
-- date. Intervals are half-open [start_date, end_date), so at_date must be
-- before end_date; open intervals (end_date NULL) match any date at or
-- after start.
CREATE OR REPLACE FUNCTION person_role_interval_at(
    p_person_id text,
    at_date date
) RETURNS TABLE (
    id              text,
    organization_id text,
    role            text,
    start_date      date,
    end_date        date,
    is_public_role  boolean,
    source_ref      jsonb
)
LANGUAGE sql STABLE AS $$
    SELECT
        id,
        organization_id,
        role,
        start_date,
        end_date,
        is_public_role,
        source_ref
    FROM person_role_interval
    WHERE
        person_id = p_person_id
        AND status = 'ACTIVE'
        AND start_date <= at_date
        AND (end_date IS NULL OR at_date < end_date)
    ORDER BY start_date, role
$$;

-- person.public_role remains a legacy timeless convenience field (see
-- DP-101 compatibility path): dated public roles live in
-- person_role_interval with provenance, and existing public_role values may
-- be backfilled into role intervals.
COMMENT ON COLUMN person.public_role IS
    'Legacy timeless convenience role; dated public roles are modeled in person_role_interval with source_ref provenance.';

ALTER TABLE review_event
    DROP CONSTRAINT IF EXISTS review_event_entity_type_check;

ALTER TABLE review_event
    ADD CONSTRAINT review_event_entity_type_check
    CHECK (
        entity_type IN (
            'CLAIM_EVIDENCE_CANDIDATE',
            'EVIDENCE_OBSERVATION',
            'RELATION_CANDIDATE',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;