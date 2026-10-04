BEGIN;

-- DP-105: record the public contract version in an append-only registry table.
-- Replay-safe, never updates or rewrites existing rows, touches no projection data.

CREATE TABLE IF NOT EXISTS public_schema_contract (
    id                      text PRIMARY KEY,
    schema_version          text NOT NULL,
    status                  text NOT NULL,
    claim_level_only        boolean NOT NULL DEFAULT true,
    aggregate_person_score  boolean NOT NULL DEFAULT false,
    effective_from          timestamptz NOT NULL DEFAULT now(),
    notes                   text,
    UNIQUE (schema_version),
    CHECK (claim_level_only = true),
    CHECK (aggregate_person_score = false),
    CHECK (status IN ('ACTIVE', 'DEPRECATED', 'SUPERSEDED'))
);

CREATE INDEX IF NOT EXISTS public_schema_contract_status_idx
    ON public_schema_contract(status, effective_from DESC);

INSERT INTO public_schema_contract (
    id,
    schema_version,
    status,
    claim_level_only,
    aggregate_person_score,
    effective_from,
    notes
)
VALUES (
    'contract:dichiarazioni-pubbliche-public-v2',
    'dichiarazioni-pubbliche-public-v2',
    'ACTIVE',
    true,
    false,
    '2026-09-26T00:00:00+00:00',
    'Public schema v2 fail-closed contract with pure validator and strict person aggregate prevention.'
)
ON CONFLICT (schema_version) DO NOTHING;

COMMIT;
