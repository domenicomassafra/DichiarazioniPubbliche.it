-- DP-468: durable, version-bound authorities for public Statement v3.
-- All evidence remains private. Public projection reads only current approved
-- events and fails closed when any chain, review, privacy or challenge is absent.

CREATE TABLE IF NOT EXISTS public_statement_authority_event (
    event_id text PRIMARY KEY,
    statement_id text NOT NULL CHECK (length(btrim(statement_id)) > 0),
    version_id text NOT NULL CHECK (length(btrim(version_id)) > 0),
    authority_kind text NOT NULL CHECK (authority_kind IN (
        'RIGHTS', 'PRIVACY', 'RETENTION', 'ATTRIBUTION',
        'CONTEXT', 'WORDING', 'PUBLICATION'
    )),
    event_sequence integer NOT NULL CHECK (event_sequence > 0),
    previous_event_id text,
    previous_integrity_sha256 character(64),
    decision_id text NOT NULL UNIQUE CHECK (length(btrim(decision_id)) > 0),
    review_event_id text NOT NULL UNIQUE CHECK (length(btrim(review_event_id)) > 0),
    status text NOT NULL CHECK (status IN ('APPROVED', 'HELD', 'REJECTED', 'REVOKED')),
    binding jsonb NOT NULL CHECK (jsonb_typeof(binding) = 'object'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    review_evidence jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(review_evidence) = 'object'),
    reviewer_ref text NOT NULL CHECK (length(btrim(reviewer_ref)) > 0),
    reviewed_at text NOT NULL CHECK (length(btrim(reviewed_at)) > 0),
    expires_at text,
    integrity_sha256 character(64) NOT NULL CHECK (integrity_sha256 ~ '^[a-f0-9]{64}$'),
    record_visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (record_visibility = 'PRIVATE'),
    persisted_at timestamptz NOT NULL DEFAULT now(),
    CHECK (event_id = 'public-statement-authority:' || integrity_sha256),
    CHECK (binding->>'statement_id' = statement_id),
    CHECK (binding->>'version_id' = version_id),
    CHECK (status <> 'APPROVED' OR expires_at IS NOT NULL),
    CHECK (expires_at IS NULL OR length(btrim(expires_at)) > 0),
    CHECK (
        (event_sequence = 1 AND previous_event_id IS NULL AND previous_integrity_sha256 IS NULL)
        OR
        (event_sequence > 1 AND previous_event_id IS NOT NULL
            AND previous_integrity_sha256 IS NOT NULL
            AND previous_integrity_sha256 ~ '^[a-f0-9]{64}$')
    ),
    UNIQUE (statement_id, version_id, authority_kind, event_sequence),
    UNIQUE (previous_event_id)
);

CREATE OR REPLACE FUNCTION dp468_guard_public_statement_authority_chain()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous public_statement_authority_event%ROWTYPE;
BEGIN
    IF NEW.event_sequence = 1 THEN
        IF NEW.previous_event_id IS NOT NULL OR NEW.previous_integrity_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'DP468_AUTHORITY_ROOT_HAS_PREDECESSOR';
        END IF;
        IF EXISTS (
            SELECT 1 FROM public_statement_authority_event
            WHERE statement_id = NEW.statement_id
              AND version_id = NEW.version_id
              AND authority_kind = NEW.authority_kind
        ) THEN
            RAISE EXCEPTION 'DP468_AUTHORITY_ROOT_ALREADY_EXISTS';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO previous
    FROM public_statement_authority_event
    WHERE event_id = NEW.previous_event_id
    FOR SHARE;
    IF NOT FOUND
       OR previous.statement_id <> NEW.statement_id
       OR previous.version_id <> NEW.version_id
       OR previous.authority_kind <> NEW.authority_kind
       OR previous.event_sequence + 1 <> NEW.event_sequence
       OR previous.integrity_sha256 <> NEW.previous_integrity_sha256 THEN
        RAISE EXCEPTION 'DP468_AUTHORITY_CHAIN_PREDECESSOR_INVALID';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS dp468_public_statement_authority_chain_guard
    ON public_statement_authority_event;
CREATE TRIGGER dp468_public_statement_authority_chain_guard
BEFORE INSERT ON public_statement_authority_event
FOR EACH ROW EXECUTE FUNCTION dp468_guard_public_statement_authority_chain();

CREATE TABLE IF NOT EXISTS public_statement_challenge_request (
    request_id text PRIMARY KEY,
    statement_id text NOT NULL CHECK (length(btrim(statement_id)) > 0),
    version_id text NOT NULL CHECK (length(btrim(version_id)) > 0),
    intake_ref text NOT NULL CHECK (length(btrim(intake_ref)) > 0),
    requester_ref_sha256 character(64) NOT NULL CHECK (requester_ref_sha256 ~ '^[a-f0-9]{64}$'),
    reason_sha256 character(64) NOT NULL CHECK (reason_sha256 ~ '^[a-f0-9]{64}$'),
    created_at text NOT NULL CHECK (length(btrim(created_at)) > 0),
    integrity_sha256 character(64) NOT NULL CHECK (integrity_sha256 ~ '^[a-f0-9]{64}$'),
    record_visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (record_visibility = 'PRIVATE'),
    persisted_at timestamptz NOT NULL DEFAULT now(),
    CHECK (request_id = 'public-statement-challenge-request:' || integrity_sha256)
);

CREATE TABLE IF NOT EXISTS public_statement_challenge_event (
    event_id text PRIMARY KEY,
    request_id text NOT NULL REFERENCES public_statement_challenge_request(request_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    event_sequence integer NOT NULL CHECK (event_sequence > 0),
    previous_event_id text,
    previous_integrity_sha256 character(64),
    status text NOT NULL CHECK (status IN (
        'OPEN', 'TRIAGED', 'NEEDS_INFO', 'UPHELD', 'CORRECTED',
        'RETRACTED', 'REJECTED', 'WITHDRAWN', 'CLOSED_NO_CHANGE'
    )),
    reason_code text NOT NULL CHECK (length(btrim(reason_code)) > 0),
    actor_ref text NOT NULL CHECK (length(btrim(actor_ref)) > 0),
    occurred_at text NOT NULL CHECK (length(btrim(occurred_at)) > 0),
    integrity_sha256 character(64) NOT NULL CHECK (integrity_sha256 ~ '^[a-f0-9]{64}$'),
    record_visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (record_visibility = 'PRIVATE'),
    persisted_at timestamptz NOT NULL DEFAULT now(),
    CHECK (event_id = 'public-statement-challenge-event:' || integrity_sha256),
    CHECK (event_sequence <> 1 OR status = 'OPEN'),
    CHECK (event_sequence = 1 OR status <> 'OPEN'),
    CHECK (
        (event_sequence = 1 AND previous_event_id IS NULL AND previous_integrity_sha256 IS NULL)
        OR
        (event_sequence > 1 AND previous_event_id IS NOT NULL
            AND previous_integrity_sha256 IS NOT NULL
            AND previous_integrity_sha256 ~ '^[a-f0-9]{64}$')
    ),
    UNIQUE (request_id, event_sequence),
    UNIQUE (previous_event_id)
);

CREATE OR REPLACE FUNCTION dp468_guard_public_statement_challenge_chain()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous public_statement_challenge_event%ROWTYPE;
BEGIN
    IF NEW.event_sequence = 1 THEN
        IF NEW.previous_event_id IS NOT NULL OR NEW.previous_integrity_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'DP468_CHALLENGE_ROOT_HAS_PREDECESSOR';
        END IF;
        IF EXISTS (
            SELECT 1 FROM public_statement_challenge_event
            WHERE request_id = NEW.request_id
        ) THEN
            RAISE EXCEPTION 'DP468_CHALLENGE_ROOT_ALREADY_EXISTS';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO previous
    FROM public_statement_challenge_event
    WHERE event_id = NEW.previous_event_id
    FOR SHARE;
    IF NOT FOUND
       OR previous.request_id <> NEW.request_id
       OR previous.event_sequence + 1 <> NEW.event_sequence
       OR previous.integrity_sha256 <> NEW.previous_integrity_sha256 THEN
        RAISE EXCEPTION 'DP468_CHALLENGE_CHAIN_PREDECESSOR_INVALID';
    END IF;
    IF NOT (
        (previous.status = 'OPEN' AND NEW.status IN (
            'TRIAGED', 'NEEDS_INFO', 'UPHELD', 'REJECTED', 'WITHDRAWN',
            'CLOSED_NO_CHANGE'
        ))
        OR (previous.status IN ('TRIAGED', 'NEEDS_INFO') AND NEW.status IN (
            'TRIAGED', 'NEEDS_INFO', 'UPHELD', 'CORRECTED', 'RETRACTED',
            'REJECTED', 'WITHDRAWN', 'CLOSED_NO_CHANGE'
        ))
        OR (previous.status = 'UPHELD' AND NEW.status IN ('CORRECTED', 'RETRACTED'))
    ) THEN
        RAISE EXCEPTION 'DP468_CHALLENGE_TRANSITION_INVALID';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS dp468_public_statement_challenge_chain_guard
    ON public_statement_challenge_event;
CREATE TRIGGER dp468_public_statement_challenge_chain_guard
BEFORE INSERT ON public_statement_challenge_event
FOR EACH ROW EXECUTE FUNCTION dp468_guard_public_statement_challenge_chain();

CREATE OR REPLACE FUNCTION dp468_reject_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '55000';
END;
$$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'public_statement_authority_event',
        'public_statement_challenge_request',
        'public_statement_challenge_event'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I',
            table_name || '_no_update_delete', table_name);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION dp468_reject_append_only_mutation()',
            table_name || '_no_update_delete', table_name
        );
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I',
            table_name || '_no_truncate', table_name);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE TRUNCATE ON %I '
            'FOR EACH STATEMENT EXECUTE FUNCTION dp468_reject_append_only_mutation()',
            table_name || '_no_truncate', table_name
        );
    END LOOP;
END;
$$;

CREATE INDEX IF NOT EXISTS public_statement_authority_current_idx
    ON public_statement_authority_event (statement_id, version_id, authority_kind, event_sequence DESC);
CREATE INDEX IF NOT EXISTS public_statement_challenge_target_idx
    ON public_statement_challenge_request (statement_id, version_id, created_at DESC);
CREATE INDEX IF NOT EXISTS public_statement_challenge_event_current_idx
    ON public_statement_challenge_event (request_id, event_sequence DESC);
