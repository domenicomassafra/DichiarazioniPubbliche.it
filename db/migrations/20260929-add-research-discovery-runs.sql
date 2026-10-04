BEGIN;

-- DP-209: bounded, replayable research discovery manifests and receipts.
CREATE TABLE IF NOT EXISTS research_discovery_manifest (
    id                      text PRIMARY KEY,
    collection_id           text NOT NULL REFERENCES research_collection(id) ON DELETE CASCADE,
    manifest_version        text NOT NULL DEFAULT 'research-discovery-manifest-v1',
    manifest_sha256         text NOT NULL,
    date_from               timestamptz,
    date_to                 timestamptz,
    max_results             integer NOT NULL,
    max_results_per_host    integer NOT NULL,
    cost_cap_usd            numeric(12,6) NOT NULL,
    seeds                   jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_families         jsonb NOT NULL DEFAULT '[]'::jsonb,
    status                  text NOT NULL DEFAULT 'ACTIVE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (manifest_version = 'research-discovery-manifest-v1'),
    CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (date_to IS NULL OR date_from IS NULL OR date_to >= date_from),
    CHECK (max_results BETWEEN 1 AND 200),
    CHECK (max_results_per_host BETWEEN 1 AND 50),
    CHECK (cost_cap_usd >= 0 AND cost_cap_usd <= 25),
    CHECK (jsonb_typeof(seeds) = 'array'),
    CHECK (jsonb_typeof(source_families) = 'array'),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    UNIQUE (collection_id, manifest_sha256)
);

CREATE TABLE IF NOT EXISTS research_discovery_query (
    id                      text PRIMARY KEY,
    manifest_id             text NOT NULL REFERENCES research_discovery_manifest(id) ON DELETE CASCADE,
    ordinal                 integer NOT NULL,
    query_text              text NOT NULL,
    source_families         jsonb NOT NULL,
    adapter_ids             jsonb NOT NULL,
    seeds                   jsonb NOT NULL DEFAULT '[]'::jsonb,
    max_results             integer NOT NULL,
    query_version           text NOT NULL DEFAULT 'research-discovery-query-v1',
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ordinal >= 0),
    CHECK (query_version = 'research-discovery-query-v1'),
    CHECK (jsonb_typeof(source_families) = 'array'),
    CHECK (jsonb_typeof(adapter_ids) = 'array'),
    CHECK (jsonb_typeof(seeds) = 'array'),
    CHECK (max_results BETWEEN 1 AND 100),
    UNIQUE (manifest_id, ordinal)
);

CREATE TABLE IF NOT EXISTS research_discovery_run (
    id                      text PRIMARY KEY,
    manifest_id             text NOT NULL REFERENCES research_discovery_manifest(id),
    manifest_sha256         text NOT NULL,
    run_version             text NOT NULL DEFAULT 'research-discovery-run-v1',
    status                  text NOT NULL DEFAULT 'RUNNING',
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    attempt_count           integer NOT NULL DEFAULT 0,
    healthy_attempts        integer NOT NULL DEFAULT 0,
    blocked_attempts        integer NOT NULL DEFAULT 0,
    failed_attempts         integer NOT NULL DEFAULT 0,
    raw_hits                integer NOT NULL DEFAULT 0,
    accepted_hits           integer NOT NULL DEFAULT 0,
    new_content             integer NOT NULL DEFAULT 0,
    existing_content        integer NOT NULL DEFAULT 0,
    rejected_hits           integer NOT NULL DEFAULT 0,
    cost_usd                numeric(12,6) NOT NULL DEFAULT 0,
    error_category          text,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (run_version = 'research-discovery-run-v1'),
    CHECK (status IN ('RUNNING', 'COMPLETED', 'PARTIAL', 'BLOCKED', 'FAILED')),
    CHECK (attempt_count >= 0 AND healthy_attempts >= 0 AND blocked_attempts >= 0 AND failed_attempts >= 0),
    CHECK (raw_hits >= 0 AND accepted_hits >= 0 AND new_content >= 0 AND existing_content >= 0 AND rejected_hits >= 0),
    CHECK (cost_usd >= 0)
);

CREATE TABLE IF NOT EXISTS research_discovery_attempt (
    id                      text PRIMARY KEY,
    run_id                  text NOT NULL REFERENCES research_discovery_run(id) ON DELETE CASCADE,
    query_id                text NOT NULL REFERENCES research_discovery_query(id),
    adapter_id              text NOT NULL,
    adapter_version         text NOT NULL,
    status                  text NOT NULL DEFAULT 'RUNNING',
    cost_upper_bound_usd    numeric(12,6) NOT NULL DEFAULT 0,
    cost_usd                numeric(12,6) NOT NULL DEFAULT 0,
    raw_hits                integer NOT NULL DEFAULT 0,
    accepted_hits           integer NOT NULL DEFAULT 0,
    rejected_hits           integer NOT NULL DEFAULT 0,
    omitted_hits            integer NOT NULL DEFAULT 0,
    error_category          text,
    provider_receipt        jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('RUNNING', 'HEALTHY', 'BLOCKED', 'BUDGET_BLOCKED', 'FAILED')),
    CHECK (cost_upper_bound_usd >= 0 AND cost_usd >= 0),
    CHECK (raw_hits >= 0 AND accepted_hits >= 0 AND rejected_hits >= 0 AND omitted_hits >= 0),
    CHECK (jsonb_typeof(provider_receipt) = 'object'),
    UNIQUE (run_id, query_id, adapter_id)
);

CREATE TABLE IF NOT EXISTS research_discovery_hit (
    id                      text PRIMARY KEY,
    run_id                  text NOT NULL REFERENCES research_discovery_run(id) ON DELETE CASCADE,
    attempt_id              text NOT NULL REFERENCES research_discovery_attempt(id) ON DELETE CASCADE,
    query_id                text NOT NULL REFERENCES research_discovery_query(id),
    hit_key                 text NOT NULL,
    ordinal                 integer NOT NULL,
    canonical_url           text NOT NULL,
    source_host             text NOT NULL,
    title                   text,
    published_at            timestamptz,
    source_family           text NOT NULL,
    source_id               text REFERENCES source(id),
    external_id             text,
    disposition             text NOT NULL,
    content_id              text REFERENCES content_item(id),
    reason_code             text,
    observed_at             timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (hit_key ~ '^[0-9a-f]{64}$'),
    CHECK (ordinal >= 0),
    CHECK (disposition IN (
        'NEW_CONTENT', 'EXISTING_CONTENT', 'DUPLICATE_WITHIN_RUN',
        'HOST_LIMIT', 'RESULT_LIMIT', 'OUTSIDE_DATE_WINDOW',
        'REJECTED_POLICY', 'AMBIGUOUS_CONTENT_IDENTITY'
    )),
    UNIQUE (attempt_id, hit_key)
);

CREATE INDEX IF NOT EXISTS research_discovery_run_manifest_idx
    ON research_discovery_run(manifest_id, started_at DESC);
CREATE INDEX IF NOT EXISTS research_discovery_attempt_run_idx
    ON research_discovery_attempt(run_id, status, query_id);
CREATE INDEX IF NOT EXISTS research_discovery_hit_run_idx
    ON research_discovery_hit(run_id, disposition, source_host);
CREATE INDEX IF NOT EXISTS research_discovery_hit_content_idx
    ON research_discovery_hit(content_id) WHERE content_id IS NOT NULL;

COMMIT;
