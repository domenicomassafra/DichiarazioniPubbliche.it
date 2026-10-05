BEGIN;

CREATE TABLE IF NOT EXISTS source (
    id              text PRIMARY KEY,
    canonical_name  text NOT NULL,
    source_type     text NOT NULL,
    canonical_url   text,
    language        text,
    country_code    text,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS person (
    id               text PRIMARY KEY,
    canonical_name   text NOT NULL,
    public_role      text,
    country_code     text,
    is_public_figure boolean NOT NULL DEFAULT true,
    metadata         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (is_public_figure = true)
);

CREATE TABLE IF NOT EXISTS person_alias (
    person_id       text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    alias           text NOT NULL,
    alias_type      text NOT NULL DEFAULT 'NAME',
    source          text,
    PRIMARY KEY (person_id, alias)
);

-- DP-101: organizations/offices and dated person role intervals.
-- btree_gist powers the overlap exclusion on person_role_interval.
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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

-- DP-114: stable private knowledge entities and reviewable resolution.
CREATE TABLE IF NOT EXISTS topic (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    canonical_name      text NOT NULL,
    scope_text          text NOT NULL,
    entity_version      text NOT NULL DEFAULT 'knowledge-entity-v1',
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES topic(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_version = 'knowledge-entity-v1'),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id)
);

CREATE TABLE IF NOT EXISTS topic_alias (
    topic_id            text NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS event (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    canonical_name      text NOT NULL,
    scope_text          text NOT NULL,
    start_at            timestamptz,
    end_at              timestamptz,
    entity_version      text NOT NULL DEFAULT 'knowledge-entity-v1',
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES event(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_version = 'knowledge-entity-v1'),
    CHECK (end_at IS NULL OR start_at IS NULL OR end_at >= start_at),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id)
);

CREATE TABLE IF NOT EXISTS event_alias (
    event_id            text NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS organization_alias (
    organization_id     text NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'NAME',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, alias),
    CHECK (alias_type IN ('NAME', 'ACRONYM', 'HISTORICAL_NAME', 'SEARCH')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE TABLE IF NOT EXISTS entity_identifier (
    id                  text PRIMARY KEY,
    entity_type         text NOT NULL,
    person_id           text REFERENCES person(id) ON DELETE CASCADE,
    organization_id     text REFERENCES organization(id) ON DELETE CASCADE,
    topic_id            text REFERENCES topic(id) ON DELETE CASCADE,
    event_id            text REFERENCES event(id) ON DELETE CASCADE,
    identifier_kind     text NOT NULL,
    identifier_value    text NOT NULL,
    authority           text NOT NULL,
    identifier_version  text NOT NULL DEFAULT 'entity-identifier-v1',
    source_ref          jsonb NOT NULL,
    status              text NOT NULL DEFAULT 'ACTIVE',
    supersedes_id       text REFERENCES entity_identifier(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (identifier_version = 'entity-identifier-v1'),
    CHECK (jsonb_typeof(source_ref) = 'object'),
    CHECK (source_ref <> '{}'::jsonb),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CHECK (
        (person_id IS NOT NULL)::integer +
        (organization_id IS NOT NULL)::integer +
        (topic_id IS NOT NULL)::integer +
        (event_id IS NOT NULL)::integer = 1
    ),
    CHECK (
        (entity_type = 'PERSON' AND person_id IS NOT NULL) OR
        (entity_type = 'ORGANIZATION' AND organization_id IS NOT NULL) OR
        (entity_type = 'TOPIC' AND topic_id IS NOT NULL) OR
        (entity_type = 'EVENT' AND event_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_identifier_active_unique
    ON entity_identifier(entity_type, authority, identifier_kind, identifier_value)
    WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS content_item (
    id                  text PRIMARY KEY,
    source_id           text REFERENCES source(id),
    source_external_id  text,
    canonical_url       text NOT NULL,
    title               text,
    description         text,
    language            text,
    published_at        timestamptz,
    discovered_at       timestamptz NOT NULL DEFAULT now(),
    duration_ms         bigint,
    content_sha256      text,
    rights_status       text NOT NULL DEFAULT 'UNKNOWN',
    processing_status   text NOT NULL DEFAULT 'DISCOVERED',
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_id, source_external_id),
    CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE TABLE IF NOT EXISTS content_locator (
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    platform            text NOT NULL,
    external_id         text NOT NULL,
    canonical_url       text NOT NULL,
    discovered_at       timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (platform, external_id),
    UNIQUE (content_id, platform, external_id)
);

-- DP-113: immutable observed versions of logical Content.
CREATE TABLE IF NOT EXISTS content_capture (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    observed_at         timestamptz NOT NULL,
    final_url           text NOT NULL,
    media_type          text,
    content_sha256      text NOT NULL,
    body_ref            text,
    retrieval_method    text NOT NULL,
    retrieval_version   text NOT NULL,
    parser_method       text,
    parser_version      text,
    rights_status       text NOT NULL DEFAULT 'UNKNOWN',
    retention_class     text NOT NULL DEFAULT 'POLICY_PENDING',
    hold_status         text NOT NULL DEFAULT 'NONE',
    archive_status      text NOT NULL DEFAULT 'NOT_REQUESTED',
    archive_provider    text,
    archive_requested_at timestamptz,
    archive_completed_at timestamptz,
    archive_receipt     jsonb NOT NULL DEFAULT '{}'::jsonb,
    body_purged_at      timestamptz,
    purge_reason        text,
    purge_receipt       jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              text NOT NULL DEFAULT 'CAPTURED',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (retention_class IN ('POLICY_PENDING', 'EPHEMERAL', 'DURABLE_PRIVATE', 'DURABLE_PROVENANCE')),
    CHECK (hold_status IN ('NONE', 'LEGAL_HOLD', 'RIGHTS_HOLD', 'PRIVACY_HOLD', 'COPYRIGHT_HOLD', 'DISPUTE_HOLD')),
    CHECK (archive_status IN ('NOT_REQUESTED', 'REQUESTED', 'PENDING', 'SUCCEEDED', 'FAILED')),
    CHECK (status IN ('CAPTURED', 'QUARANTINED', 'PURGE_PENDING', 'PURGED_BODY')),
    CHECK (jsonb_typeof(archive_receipt) = 'object'),
    CHECK (jsonb_typeof(purge_receipt) = 'object'),
    CHECK (
        archive_status = 'NOT_REQUESTED'
        OR (archive_provider IS NOT NULL AND archive_requested_at IS NOT NULL)
    ),
    CHECK (
        archive_status NOT IN ('SUCCEEDED', 'FAILED')
        OR (archive_completed_at IS NOT NULL AND archive_receipt <> '{}'::jsonb)
    ),
    CHECK (
        status <> 'PURGED_BODY'
        OR (body_ref IS NULL AND body_purged_at IS NOT NULL AND purge_reason IS NOT NULL AND purge_receipt <> '{}'::jsonb)
    ),
    UNIQUE (content_id, content_sha256)
);

CREATE INDEX IF NOT EXISTS content_capture_content_idx
    ON content_capture(content_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS capture_lifecycle_event (
    id                  text PRIMARY KEY,
    capture_id          text NOT NULL REFERENCES content_capture(id) ON DELETE CASCADE,
    event_type          text NOT NULL,
    event_version       text NOT NULL DEFAULT 'capture-lifecycle-v1',
    actor_ref           text NOT NULL DEFAULT 'local-operator',
    previous_state      jsonb NOT NULL DEFAULT '{}'::jsonb,
    new_state           jsonb NOT NULL DEFAULT '{}'::jsonb,
    receipt             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (event_version = 'capture-lifecycle-v1'),
    CHECK (event_type IN (
        'ARCHIVE_REQUESTED', 'ARCHIVE_PENDING', 'ARCHIVE_SUCCEEDED', 'ARCHIVE_FAILED',
        'BODY_PURGE_REQUESTED', 'BODY_PURGED', 'BODY_PURGE_FAILED',
        'HOLD_SET', 'HOLD_RELEASED', 'RIGHTS_STATUS_CHANGED',
        'CAPTURE_REOBSERVED', 'PARSE_SUCCEEDED', 'PARSE_FAILED', 'BROWSER_FALLBACK_FAILED'
    )),
    CHECK (jsonb_typeof(previous_state) = 'object'),
    CHECK (jsonb_typeof(new_state) = 'object'),
    CHECK (jsonb_typeof(receipt) = 'object')
);

CREATE INDEX IF NOT EXISTS capture_lifecycle_event_capture_idx
    ON capture_lifecycle_event(capture_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS content_capture_id_content_unique
    ON content_capture(id, content_id);

CREATE TABLE IF NOT EXISTS research_collection (
    id                  text PRIMARY KEY,
    slug                text NOT NULL UNIQUE,
    name                text NOT NULL,
    scope_text          text NOT NULL,
    status              text NOT NULL DEFAULT 'ACTIVE',
    policy_version      text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('ACTIVE', 'PAUSED', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS research_collection_content (
    collection_id       text NOT NULL REFERENCES research_collection(id) ON DELETE CASCADE,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    inclusion_method    text NOT NULL,
    inclusion_version   text NOT NULL,
    status              text NOT NULL DEFAULT 'INCLUDED',
    rationale           text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (collection_id, content_id),
    CHECK (status IN ('INCLUDED', 'REJECTED', 'REMOVED'))
);

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
    coverage_need_ids       jsonb NOT NULL DEFAULT '[]'::jsonb,
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
    CHECK (jsonb_typeof(coverage_need_ids) = 'array'),
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

-- DP-115: private source-derivation families and reviewable edges.
CREATE TABLE IF NOT EXISTS content_derivation_family (
    id                  text PRIMARY KEY,
    root_content_id     text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    family_version      text NOT NULL DEFAULT 'content-derivation-v1',
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (family_version = 'content-derivation-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE TABLE IF NOT EXISTS content_derivation_candidate (
    id                  text PRIMARY KEY,
    family_id           text NOT NULL REFERENCES content_derivation_family(id) ON DELETE CASCADE,
    derived_content_id  text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    origin_content_id   text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    relation_type       text NOT NULL,
    derivation_method   text NOT NULL,
    derivation_version  text NOT NULL DEFAULT 'content-derivation-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    lexical_score       numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (derived_content_id <> origin_content_id),
    CHECK (relation_type IN ('REPUBLICATION', 'SYNDICATION', 'QUOTATION', 'PRESS_RELEASE_DERIVED', 'UNKNOWN_DERIVATION')),
    CHECK (derivation_method IN ('EXACT_BODY_HASH', 'EXPLICIT_SOURCE_CREDIT', 'LEXICAL_OVERLAP', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (derivation_version = 'content-derivation-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (lexical_score IS NULL OR (lexical_score >= 0 AND lexical_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    UNIQUE (family_id, derived_content_id, origin_content_id, derivation_version)
);

CREATE INDEX IF NOT EXISTS content_derivation_candidate_family_idx
    ON content_derivation_candidate(family_id, status, derived_content_id);
CREATE INDEX IF NOT EXISTS content_derivation_candidate_origin_idx
    ON content_derivation_candidate(origin_content_id, status);
CREATE INDEX IF NOT EXISTS content_derivation_candidate_derived_idx
    ON content_derivation_candidate(derived_content_id, status);

CREATE TABLE IF NOT EXISTS appearance (
    content_id      text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    person_id       text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    role            text NOT NULL,
    confidence      numeric(5,4),
    start_ms        bigint,
    end_ms          bigint,
    evidence        jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (content_id, person_id, role, start_ms),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (start_ms IS NULL OR start_ms >= 0),
    CHECK (end_ms IS NULL OR end_ms >= start_ms)
);

CREATE TABLE IF NOT EXISTS speaker_identity_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    person_id           text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    start_ms            bigint NOT NULL,
    end_ms              bigint NOT NULL,
    speaker_label       text,
    attribution_method  text NOT NULL,
    attribution_version text NOT NULL,
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence          numeric(5,4),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (
        attribution_method IN (
            'MANUAL_REVIEW',
            'SOURCE_METADATA',
            'TRANSCRIPT_LABEL',
            'PLATFORM_CREDIT',
            'OFFICIAL_RECORD'
        )
    ),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE INDEX IF NOT EXISTS speaker_identity_candidate_content_idx
    ON speaker_identity_candidate(content_id, status, start_ms, end_ms);

CREATE TABLE IF NOT EXISTS transcript_variant (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    provider_id         text NOT NULL,
    source_kind         text NOT NULL,
    language            text,
    model_name          text,
    request_id          text,
    raw_text_sha256     text NOT NULL,
    raw_text            text NOT NULL,
    is_platform_caption boolean NOT NULL DEFAULT false,
    is_manual_caption   boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS transcript_variant_content_idx
    ON transcript_variant(content_id);

CREATE TABLE IF NOT EXISTS transcript_segment (
    id              text PRIMARY KEY,
    variant_id      text NOT NULL REFERENCES transcript_variant(id) ON DELETE CASCADE,
    segment_index   integer NOT NULL,
    start_ms        bigint NOT NULL,
    end_ms          bigint NOT NULL,
    speaker_label   text,
    text            text NOT NULL,
    confidence      numeric(5,4),
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (variant_id, segment_index),
    CHECK (segment_index >= 0),
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS canonical_transcript_segment (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    segment_index       integer NOT NULL,
    start_ms            bigint NOT NULL,
    end_ms              bigint NOT NULL,
    speaker_person_id   text REFERENCES person(id),
    speaker_label       text,
    canonical_text      text NOT NULL,
    transcript_status   text NOT NULL,
    publication_blocked boolean NOT NULL DEFAULT false,
    sensitive_signature jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (content_id, segment_index),
    CHECK (segment_index >= 0),
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms),
    CHECK (
        transcript_status IN (
            'RESOLVED',
            'CANDIDATE_DISAGREEMENT',
            'TRANSCRIPT_UNCERTAIN'
        )
    ),
    CHECK (
        transcript_status <> 'TRANSCRIPT_UNCERTAIN'
        OR publication_blocked = true
    )
);

CREATE TABLE IF NOT EXISTS canonical_segment_candidate (
    canonical_segment_id text NOT NULL
        REFERENCES canonical_transcript_segment(id) ON DELETE CASCADE,
    transcript_segment_id text NOT NULL
        REFERENCES transcript_segment(id) ON DELETE CASCADE,
    PRIMARY KEY (canonical_segment_id, transcript_segment_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS canonical_segment_id_content_unique
    ON canonical_transcript_segment(id, content_id);

CREATE TABLE IF NOT EXISTS passage (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    capture_id          text,
    canonical_segment_id text,
    selector_type       text NOT NULL,
    start_char          integer,
    end_char            integer,
    page_start          integer,
    page_end            integer,
    text_sha256         text NOT NULL,
    private_text        text,
    language            text,
    extraction_method   text NOT NULL,
    extraction_version  text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id) ON DELETE CASCADE,
    CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK ((capture_id IS NOT NULL)::integer + (canonical_segment_id IS NOT NULL)::integer = 1),
    CHECK (selector_type IN ('TEXT_POSITION', 'PAGE_RANGE', 'MEDIA_SEGMENT_REF')),
    CHECK ((start_char IS NULL AND end_char IS NULL) OR (start_char >= 0 AND end_char > start_char)),
    CHECK ((page_start IS NULL AND page_end IS NULL) OR (page_start >= 1 AND page_end >= page_start)),
    CHECK (selector_type <> 'TEXT_POSITION' OR (capture_id IS NOT NULL AND start_char IS NOT NULL)),
    CHECK (selector_type <> 'PAGE_RANGE' OR (capture_id IS NOT NULL AND page_start IS NOT NULL)),
    CHECK (selector_type <> 'MEDIA_SEGMENT_REF' OR canonical_segment_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS passage_content_idx
    ON passage(content_id, created_at);
CREATE INDEX IF NOT EXISTS passage_capture_idx
    ON passage(capture_id) WHERE capture_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS statement_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    speaker_person_id   text REFERENCES person(id),
    statement_text_hash text NOT NULL,
    normalized_statement text NOT NULL,
    statement_at        timestamptz,
    attribution_method  text,
    extraction_model    text,
    extraction_version  text NOT NULL,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (statement_text_hash ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'HELD', 'SUPERSEDED')),
    UNIQUE (id, content_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS passage_id_content_unique
    ON passage(id, content_id);

CREATE TABLE IF NOT EXISTS statement_candidate_passage (
    statement_candidate_id text NOT NULL,
    passage_id              text NOT NULL,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    PRIMARY KEY (statement_candidate_id, passage_id),
    FOREIGN KEY (statement_candidate_id, content_id) REFERENCES statement_candidate(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS statement_candidate_content_idx
    ON statement_candidate(content_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS entity_resolution_candidate (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id          text,
    mention_text        text NOT NULL,
    mention_text_sha256 text NOT NULL,
    entity_type         text NOT NULL,
    target_person_id    text REFERENCES person(id),
    target_organization_id text REFERENCES organization(id),
    target_topic_id     text REFERENCES topic(id),
    target_event_id     text REFERENCES event(id),
    resolution_method   text NOT NULL,
    resolution_version  text NOT NULL DEFAULT 'entity-resolution-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    retrieval_score     numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (mention_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (resolution_method IN ('EXACT_IDENTIFIER', 'KNOWN_ALIAS', 'CONTEXT_MATCH', 'MODEL_SUGGESTION', 'MANUAL_REVIEW')),
    CHECK (resolution_version = 'entity-resolution-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (retrieval_score IS NULL OR (retrieval_score >= 0 AND retrieval_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (
        (target_person_id IS NOT NULL)::integer +
        (target_organization_id IS NOT NULL)::integer +
        (target_topic_id IS NOT NULL)::integer +
        (target_event_id IS NOT NULL)::integer = 1
    ),
    CHECK (
        (entity_type = 'PERSON' AND target_person_id IS NOT NULL) OR
        (entity_type = 'ORGANIZATION' AND target_organization_id IS NOT NULL) OR
        (entity_type = 'TOPIC' AND target_topic_id IS NOT NULL) OR
        (entity_type = 'EVENT' AND target_event_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS entity_resolution_candidate_content_idx
    ON entity_resolution_candidate(content_id, status, entity_type, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_resolution_candidate_passage_idx
    ON entity_resolution_candidate(passage_id) WHERE passage_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS atomic_claim (
    id                  text PRIMARY KEY,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    speaker_person_id   text REFERENCES person(id),
    normalized_claim    text NOT NULL,
    claim_type          text NOT NULL,
    claim_type_version  text NOT NULL DEFAULT 'atomic-claim-v1',
    temporal_scope      jsonb NOT NULL DEFAULT '{}'::jsonb,
    check_worthy        boolean NOT NULL DEFAULT true,
    extraction_model    text,
    extraction_version  text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        claim_type IN (
            'ARITHMETIC', 'CAUSAL_CLAIM', 'CURRENT_FOREIGN_POLICY',
            'CURRENT_POLICY', 'CURRENT_POLICY_POSITION',
            'DISTRIBUTIONAL_CLAIM', 'ELECTION_PREDICTION',
            'FISCAL_INFERENCE', 'GROUP_MOTIVE', 'HISTORICAL_ATTRIBUTION',
            'HISTORICAL_CLAIM', 'HISTORICAL_POLITICAL',
            'LEGAL_POLICY_STATUS', 'LEGAL_QUOTE', 'MOTIVE_ATTRIBUTION',
            'NUMERIC_STATISTIC', 'POLICY_DIFFERENCE', 'POLICY_SCOPE',
            'POLITICAL_ATTRIBUTION', 'PRICE_STATISTIC', 'QUOTE_ATTRIBUTION',
            'RHETORICAL_GENERALIZATION', 'SYSTEMIC_CLAIM',
            'SYSTEMIC_INFERENCE', 'TAX_RATE', 'VALUE_JUDGMENT'
        )
    ),
    CHECK (
        claim_type_version = 'atomic-claim-v1'
        AND (claim_type NOT IN ('RHETORICAL_GENERALIZATION', 'VALUE_JUDGMENT')
             OR check_worthy = false)
    )
);

-- DP-430: reviewed public-subject membership. Knowledge topics remain private
-- until both the Topic and this claim->Topic membership receive explicit
-- review_event APPROVED decisions.
CREATE TABLE IF NOT EXISTS claim_topic_membership (
    id                              text PRIMARY KEY,
    claim_id                        text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    topic_id                        text NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    source_resolution_candidate_id  text REFERENCES entity_resolution_candidate(id),
    membership_version              text NOT NULL DEFAULT 'claim-topic-v1',
    status                          text NOT NULL DEFAULT 'CANDIDATE',
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at                      timestamptz NOT NULL DEFAULT now(),
    CHECK (membership_version = 'claim-topic-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS claim_topic_membership_approved_unique
    ON claim_topic_membership(claim_id, topic_id)
    WHERE status = 'APPROVED';
CREATE INDEX IF NOT EXISTS claim_topic_membership_topic_idx
    ON claim_topic_membership(topic_id, status, created_at);

CREATE TABLE IF NOT EXISTS claim_segment (
    claim_id        text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    segment_id      text NOT NULL
        REFERENCES canonical_transcript_segment(id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, segment_id)
);

CREATE TABLE IF NOT EXISTS claim_text_provenance (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    person_id           text NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    selector_type       text NOT NULL,
    quote_sha256        text NOT NULL,
    source_sha256       text,
    start_char          integer,
    end_char            integer,
    attribution_method  text NOT NULL,
    attribution_version text NOT NULL DEFAULT 'text-source-provenance-v1',
    source_ref          jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (selector_type IN ('TEXT_QUOTE_HASH', 'TEXT_POSITION_HASH')),
    CHECK (quote_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK ((start_char IS NULL AND end_char IS NULL) OR (start_char >= 0 AND end_char > start_char)),
    CHECK (selector_type <> 'TEXT_POSITION_HASH' OR start_char IS NOT NULL),
    CHECK (attribution_method IN ('SOURCE_BYLINE', 'SOURCE_QUOTE', 'ACCOUNT_OWNER', 'OFFICIAL_RECORD', 'MANUAL_REVIEW')),
    CHECK (attribution_version = 'text-source-provenance-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(source_ref) = 'object')
);

CREATE INDEX IF NOT EXISTS claim_text_provenance_claim_idx
    ON claim_text_provenance(claim_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS claim_candidate (
    id                  text PRIMARY KEY,
    statement_candidate_id text NOT NULL,
    content_id          text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    normalized_claim    text NOT NULL,
    proposed_claim_type text NOT NULL,
    claim_type_version  text NOT NULL DEFAULT 'atomic-claim-v1',
    temporal_scope      jsonb NOT NULL DEFAULT '{}'::jsonb,
    check_worthy        boolean NOT NULL DEFAULT true,
    extraction_model    text,
    extraction_version  text NOT NULL,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    promoted_claim_id   text REFERENCES atomic_claim(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (statement_candidate_id, content_id) REFERENCES statement_candidate(id, content_id) ON DELETE CASCADE,
    CHECK (
        proposed_claim_type IN (
            'ARITHMETIC', 'CAUSAL_CLAIM', 'CURRENT_FOREIGN_POLICY',
            'CURRENT_POLICY', 'CURRENT_POLICY_POSITION',
            'DISTRIBUTIONAL_CLAIM', 'ELECTION_PREDICTION',
            'FISCAL_INFERENCE', 'GROUP_MOTIVE', 'HISTORICAL_ATTRIBUTION',
            'HISTORICAL_CLAIM', 'HISTORICAL_POLITICAL',
            'LEGAL_POLICY_STATUS', 'LEGAL_QUOTE', 'MOTIVE_ATTRIBUTION',
            'NUMERIC_STATISTIC', 'POLICY_DIFFERENCE', 'POLICY_SCOPE',
            'POLITICAL_ATTRIBUTION', 'PRICE_STATISTIC', 'QUOTE_ATTRIBUTION',
            'RHETORICAL_GENERALIZATION', 'SYSTEMIC_CLAIM',
            'SYSTEMIC_INFERENCE', 'TAX_RATE', 'VALUE_JUDGMENT'
        )
    ),
    CHECK (
        claim_type_version = 'atomic-claim-v1'
        AND (proposed_claim_type NOT IN ('RHETORICAL_GENERALIZATION', 'VALUE_JUDGMENT')
             OR check_worthy = false)
    ),
    CHECK (status IN ('CANDIDATE', 'DUPLICATE', 'PROMOTED', 'REJECTED', 'HELD')),
    CHECK ((status = 'PROMOTED') = (promoted_claim_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS claim_candidate_content_idx
    ON claim_candidate(content_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS claim_candidate_promoted_idx
    ON claim_candidate(promoted_claim_id) WHERE promoted_claim_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS proposition_cluster (
    id                  text PRIMARY KEY,
    representative_text text NOT NULL,
    cluster_method      text NOT NULL,
    cluster_version     text NOT NULL DEFAULT 'proposition-cluster-v1',
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (cluster_method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (cluster_version = 'proposition-cluster-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE TABLE IF NOT EXISTS proposition_cluster_member (
    id                  text PRIMARY KEY,
    cluster_id          text NOT NULL REFERENCES proposition_cluster(id) ON DELETE CASCADE,
    member_type         text NOT NULL,
    claim_candidate_id  text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    atomic_claim_id     text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    match_class         text NOT NULL,
    membership_method   text NOT NULL,
    membership_version  text NOT NULL DEFAULT 'proposition-cluster-v1',
    supporting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    lexical_score       numeric(8,6),
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (member_type IN ('CLAIM_CANDIDATE', 'ATOMIC_CLAIM')),
    CHECK ((claim_candidate_id IS NOT NULL)::integer + (atomic_claim_id IS NOT NULL)::integer = 1),
    CHECK ((member_type = 'CLAIM_CANDIDATE' AND claim_candidate_id IS NOT NULL) OR (member_type = 'ATOMIC_CLAIM' AND atomic_claim_id IS NOT NULL)),
    CHECK (match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION', 'RELATED', 'DIFFERENT', 'UNCERTAIN')),
    CHECK (membership_method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (membership_version = 'proposition-cluster-v1'),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (lexical_score IS NULL OR (lexical_score >= 0 AND lexical_score <= 1)),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS proposition_cluster_member_claim_candidate_unique
    ON proposition_cluster_member(cluster_id, claim_candidate_id)
    WHERE claim_candidate_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS proposition_cluster_member_atomic_claim_unique
    ON proposition_cluster_member(cluster_id, atomic_claim_id)
    WHERE atomic_claim_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS proposition_cluster_member_status_idx
    ON proposition_cluster_member(cluster_id, status, match_class);

-- DP-212: replayable pairwise matching ledger. This records what the matcher
-- compared; reviewed semantic clusters remain the separate DP-115 model.
CREATE TABLE IF NOT EXISTS candidate_match_run (
    id                  text PRIMARY KEY,
    claim_candidate_id  text NOT NULL REFERENCES claim_candidate(id) ON DELETE CASCADE,
    matching_version    text NOT NULL DEFAULT 'candidate-matching-v1',
    input_fingerprint   text NOT NULL,
    status              text NOT NULL DEFAULT 'COMPLETED',
    result_count        integer NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (matching_version = 'candidate-matching-v1'),
    CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('COMPLETED', 'BLOCKED')),
    CHECK (result_count >= 0),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (claim_candidate_id, matching_version, input_fingerprint)
);

CREATE TABLE IF NOT EXISTS candidate_match_result (
    id                          text PRIMARY KEY,
    run_id                      text NOT NULL REFERENCES candidate_match_run(id) ON DELETE CASCADE,
    target_type                 text NOT NULL,
    target_claim_candidate_id   text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    target_atomic_claim_id      text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    rank                        integer NOT NULL,
    match_class                 text NOT NULL,
    method                      text NOT NULL,
    lexical_score               numeric(8,6) NOT NULL,
    supporting_features         jsonb NOT NULL DEFAULT '[]'::jsonb,
    contradicting_features      jsonb NOT NULL DEFAULT '[]'::jsonb,
    disposition                 text NOT NULL,
    proposition_cluster_id      text REFERENCES proposition_cluster(id) ON DELETE SET NULL,
    matching_version            text NOT NULL DEFAULT 'candidate-matching-v1',
    status                      text NOT NULL DEFAULT 'CANDIDATE',
    created_at                  timestamptz NOT NULL DEFAULT now(),
    metadata                    jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (target_type IN ('CLAIM_CANDIDATE', 'ATOMIC_CLAIM')),
    CHECK (
        (target_claim_candidate_id IS NOT NULL)::integer +
        (target_atomic_claim_id IS NOT NULL)::integer = 1
    ),
    CHECK (
        (target_type = 'CLAIM_CANDIDATE' AND target_claim_candidate_id IS NOT NULL) OR
        (target_type = 'ATOMIC_CLAIM' AND target_atomic_claim_id IS NOT NULL)
    ),
    CHECK (rank >= 1),
    CHECK (match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION', 'RELATED', 'DIFFERENT', 'UNCERTAIN')),
    CHECK (method IN ('EXACT_NORMALIZED', 'SOURCE_SELECTOR_OVERLAP', 'LEXICAL_TRIGRAM', 'MANUAL_REVIEW', 'MODEL_SUGGESTION')),
    CHECK (lexical_score >= 0 AND lexical_score <= 1),
    CHECK (disposition IN ('PROPOSE_CLUSTER', 'HOLD', 'NO_CLUSTER')),
    CHECK ((disposition = 'PROPOSE_CLUSTER') = (proposition_cluster_id IS NOT NULL)),
    CHECK (matching_version = 'candidate-matching-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(supporting_features) = 'array'),
    CHECK (jsonb_typeof(contradicting_features) = 'array'),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS candidate_match_run_candidate_idx
    ON candidate_match_run(claim_candidate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS candidate_match_result_run_idx
    ON candidate_match_result(run_id, rank);
CREATE UNIQUE INDEX IF NOT EXISTS candidate_match_result_candidate_unique
    ON candidate_match_result(run_id, target_claim_candidate_id)
    WHERE target_claim_candidate_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS candidate_match_result_atomic_unique
    ON candidate_match_result(run_id, target_atomic_claim_id)
    WHERE target_atomic_claim_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS candidate_match_result_atomic_idx
    ON candidate_match_result(target_atomic_claim_id, match_class)
    WHERE target_atomic_claim_id IS NOT NULL;

-- DP-117: explicit reviewed Claim Candidate -> Atomic Claim promotion ledger.
CREATE TABLE IF NOT EXISTS claim_candidate_promotion (
    id                  text PRIMARY KEY,
    claim_candidate_id  text NOT NULL REFERENCES claim_candidate(id) ON DELETE CASCADE,
    target_claim_id     text NOT NULL REFERENCES atomic_claim(id),
    action              text NOT NULL,
    provenance_channel  text NOT NULL,
    promotion_version   text NOT NULL DEFAULT 'claim-candidate-promotion-v1',
    idempotency_key     text NOT NULL UNIQUE,
    provenance_refs     jsonb NOT NULL DEFAULT '[]'::jsonb,
    actor_ref           text NOT NULL,
    reason              text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (action IN ('CREATED', 'LINKED_EXISTING')),
    CHECK (provenance_channel IN ('WRITTEN', 'MEDIA')),
    CHECK (promotion_version = 'claim-candidate-promotion-v1'),
    CHECK (jsonb_typeof(provenance_refs) = 'array'),
    UNIQUE (claim_candidate_id, promotion_version)
);

CREATE INDEX IF NOT EXISTS claim_candidate_promotion_target_idx
    ON claim_candidate_promotion(target_claim_id, action, created_at DESC);

-- DP-215: source identity and contextual evidence suitability. These records
-- deliberately contain no publisher/person trust, reliability or political score.
CREATE TABLE IF NOT EXISTS source_profile (
    id                      text PRIMARY KEY,
    source_id               text REFERENCES source(id) ON DELETE SET NULL,
    registry_kind           text NOT NULL,
    registry_source_id      text NOT NULL,
    display_name            text NOT NULL,
    profile_version         text NOT NULL,
    access_status           text NOT NULL DEFAULT 'UNKNOWN',
    rights_status           text NOT NULL DEFAULT 'UNKNOWN',
    registry_fingerprint    text NOT NULL,
    status                  text NOT NULL DEFAULT 'ACTIVE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (registry_kind IN ('EVIDENCE_REGISTRY', 'DISCOVERY_REGISTRY', 'MANUAL')),
    CHECK (access_status IN ('AVAILABLE', 'LIMITED', 'BLOCKED', 'DISCOVERY_ONLY', 'UNKNOWN')),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')),
    CHECK (registry_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (registry_kind, registry_source_id, profile_version)
);

CREATE INDEX IF NOT EXISTS source_profile_source_idx
    ON source_profile(source_id, status) WHERE source_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS source_profile_registry_idx
    ON source_profile(registry_kind, registry_source_id, status);

CREATE TABLE IF NOT EXISTS source_evidence_role (
    id                      text PRIMARY KEY,
    source_profile_id       text NOT NULL REFERENCES source_profile(id) ON DELETE CASCADE,
    evidence_role           text NOT NULL,
    basis                   text NOT NULL,
    role_version            text NOT NULL,
    status                  text NOT NULL DEFAULT 'ACTIVE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (evidence_role IN (
        'PRIMARY_RECORD', 'OFFICIAL_STATISTICS', 'AUTHENTIC_LEGAL_TEXT',
        'OFFICIAL_PROCEDURAL_RECORD', 'FIRST_PARTY_STATEMENT',
        'INDEPENDENT_REPORTING', 'EXPERT_SYNTHESIS', 'ARCHIVE_COPY',
        'SECONDARY_REFERENCE'
    )),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (source_profile_id, evidence_role, role_version)
);

CREATE INDEX IF NOT EXISTS source_evidence_role_profile_idx
    ON source_evidence_role(source_profile_id, status, evidence_role);

CREATE TABLE IF NOT EXISTS source_authority_scope (
    id                      text PRIMARY KEY,
    source_profile_id       text NOT NULL REFERENCES source_profile(id) ON DELETE CASCADE,
    evidence_role           text NOT NULL,
    jurisdiction            text,
    organization_ref        text,
    record_type             text,
    dataset_class           text,
    valid_from              date,
    valid_until             date,
    authenticity_basis      text,
    canonical_locator       jsonb NOT NULL DEFAULT '{}'::jsonb,
    supersession_policy     text,
    limitations             text,
    required_companion_role text,
    scope_version           text NOT NULL,
    status                  text NOT NULL DEFAULT 'ACTIVE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (evidence_role IN (
        'PRIMARY_RECORD', 'OFFICIAL_STATISTICS', 'AUTHENTIC_LEGAL_TEXT',
        'OFFICIAL_PROCEDURAL_RECORD', 'FIRST_PARTY_STATEMENT',
        'INDEPENDENT_REPORTING', 'EXPERT_SYNTHESIS', 'ARCHIVE_COPY',
        'SECONDARY_REFERENCE'
    )),
    CHECK (required_companion_role IS NULL OR required_companion_role IN (
        'PRIMARY_RECORD', 'OFFICIAL_STATISTICS', 'AUTHENTIC_LEGAL_TEXT',
        'OFFICIAL_PROCEDURAL_RECORD', 'FIRST_PARTY_STATEMENT',
        'INDEPENDENT_REPORTING', 'EXPERT_SYNTHESIS', 'ARCHIVE_COPY',
        'SECONDARY_REFERENCE'
    )),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')),
    CHECK (jsonb_typeof(canonical_locator) = 'object'),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS source_authority_scope_profile_idx
    ON source_authority_scope(source_profile_id, evidence_role, status);
CREATE INDEX IF NOT EXISTS source_authority_scope_lookup_idx
    ON source_authority_scope(jurisdiction, record_type, dataset_class, status);

-- Profile-level lineage assertions complement, but do not replace, DP-115's
-- content-level derivation candidate. When a content derivation row is the
-- evidence for the relation it is linked explicitly here.
CREATE TABLE IF NOT EXISTS source_relation (
    id                      text PRIMARY KEY,
    from_source_profile_id  text NOT NULL REFERENCES source_profile(id) ON DELETE CASCADE,
    to_source_profile_id    text NOT NULL REFERENCES source_profile(id) ON DELETE CASCADE,
    relation_type           text NOT NULL,
    derivation_candidate_id text REFERENCES content_derivation_candidate(id) ON DELETE SET NULL,
    evidence_basis          jsonb NOT NULL DEFAULT '{}'::jsonb,
    relation_version        text NOT NULL DEFAULT 'source-relation-v1',
    status                  text NOT NULL DEFAULT 'CANDIDATE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (from_source_profile_id <> to_source_profile_id),
    CHECK (relation_type IN (
        'DERIVED_FROM', 'REPRINTS', 'SYNDICATED_FROM', 'MIRRORS',
        'ARCHIVES_COPY_OF', 'OFFICIAL_RELEASE_OF', 'SUMMARIZES',
        'INDEPENDENT_OF', 'UNKNOWN_RELATION'
    )),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (jsonb_typeof(evidence_basis) = 'object'),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT source_relation_independence_basis_check CHECK (
        relation_type <> 'INDEPENDENT_OF'
        OR status <> 'APPROVED'
        OR evidence_basis <> '{}'::jsonb
    ),
    UNIQUE (
        from_source_profile_id, to_source_profile_id, relation_type,
        relation_version
    )
);

CREATE INDEX IF NOT EXISTS source_relation_from_idx
    ON source_relation(from_source_profile_id, status, relation_type);
CREATE INDEX IF NOT EXISTS source_relation_to_idx
    ON source_relation(to_source_profile_id, status, relation_type);
CREATE INDEX IF NOT EXISTS source_relation_derivation_idx
    ON source_relation(derivation_candidate_id)
    WHERE derivation_candidate_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS evidence_requirement_profile (
    id                              text PRIMARY KEY,
    claim_type                      text NOT NULL,
    jurisdiction                    text,
    domain                          text,
    profile_version                 text NOT NULL,
    automatic_sufficiency_allowed   boolean NOT NULL DEFAULT false,
    manual_review_required          boolean NOT NULL DEFAULT true,
    config_fingerprint              text NOT NULL,
    status                          text NOT NULL DEFAULT 'ACTIVE',
    created_at                      timestamptz NOT NULL DEFAULT now(),
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (config_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS evidence_requirement_profile_identity_idx
    ON evidence_requirement_profile(
        claim_type,
        COALESCE(jurisdiction, ''),
        COALESCE(domain, ''),
        profile_version
    );
CREATE INDEX IF NOT EXISTS evidence_requirement_profile_claim_idx
    ON evidence_requirement_profile(claim_type, status);

CREATE TABLE IF NOT EXISTS evidence_requirement_rule (
    id                      text PRIMARY KEY,
    requirement_profile_id  text NOT NULL REFERENCES evidence_requirement_profile(id) ON DELETE CASCADE,
    ordinal                 integer NOT NULL,
    rule_kind               text NOT NULL,
    required                boolean NOT NULL DEFAULT true,
    parameters              jsonb NOT NULL DEFAULT '{}'::jsonb,
    coverage_need_enabled   boolean NOT NULL DEFAULT false,
    rationale_code          text NOT NULL,
    status                  text NOT NULL DEFAULT 'ACTIVE',
    created_at              timestamptz NOT NULL DEFAULT now(),
    CHECK (ordinal >= 0),
    CHECK (rule_kind IN (
        'ROLE_ANY', 'FIELD_MATCH', 'AUTHORITY_SCOPE', 'TEMPORAL_CUTOFF',
        'MIN_INDEPENDENT_LINEAGES', 'CONFLICT_CHECK', 'HUMAN_REVIEW'
    )),
    CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')),
    CHECK (jsonb_typeof(parameters) = 'object'),
    UNIQUE (requirement_profile_id, ordinal)
);

CREATE INDEX IF NOT EXISTS evidence_requirement_rule_profile_idx
    ON evidence_requirement_rule(requirement_profile_id, status, ordinal);

-- This is an input/gate to verification. It is never a Finding and contains
-- only evidence ids/rationale, not evidence bodies or provider prompts.
CREATE TABLE IF NOT EXISTS evidence_set_assessment (
    id                              text PRIMARY KEY,
    atomic_claim_id                 text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    claim_candidate_id              text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    requirement_profile_id          text NOT NULL REFERENCES evidence_requirement_profile(id),
    requirement_profile_version     text NOT NULL,
    input_fingerprint               text NOT NULL,
    assessment                      text NOT NULL,
    qualifying_evidence_ids         jsonb NOT NULL DEFAULT '[]'::jsonb,
    rejected_evidence               jsonb NOT NULL DEFAULT '[]'::jsonb,
    satisfied_rules                 jsonb NOT NULL DEFAULT '[]'::jsonb,
    missing_rules                   jsonb NOT NULL DEFAULT '[]'::jsonb,
    conflict_groups                 jsonb NOT NULL DEFAULT '[]'::jsonb,
    coverage_need_candidates        jsonb NOT NULL DEFAULT '[]'::jsonb,
    rationale_codes                 jsonb NOT NULL DEFAULT '[]'::jsonb,
    assessment_version              text NOT NULL DEFAULT 'evidence-set-assessment-v1',
    created_at                      timestamptz NOT NULL DEFAULT now(),
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK ((atomic_claim_id IS NOT NULL)::integer + (claim_candidate_id IS NOT NULL)::integer = 1),
    CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (assessment IN (
        'SUFFICIENT_FOR_RULE', 'INSUFFICIENT_PRIMARY_SOURCE',
        'INSUFFICIENT_INDEPENDENCE', 'TEMPORAL_MISMATCH', 'SCOPE_MISMATCH',
        'CONFLICTING_EVIDENCE', 'ACCESS_OR_RIGHTS_BLOCKED',
        'UNRESOLVED_SOURCE_IDENTITY', 'UNRESOLVED_DERIVATION', 'NEEDS_REVIEW'
    )),
    CHECK (assessment_version = 'evidence-set-assessment-v1'),
    CHECK (jsonb_typeof(qualifying_evidence_ids) = 'array'),
    CHECK (jsonb_typeof(rejected_evidence) = 'array'),
    CHECK (jsonb_typeof(satisfied_rules) = 'array'),
    CHECK (jsonb_typeof(missing_rules) = 'array'),
    CHECK (jsonb_typeof(conflict_groups) = 'array'),
    CHECK (jsonb_typeof(coverage_need_candidates) = 'array'),
    CHECK (jsonb_typeof(rationale_codes) = 'array'),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS evidence_set_assessment_atomic_identity_idx
    ON evidence_set_assessment(atomic_claim_id, requirement_profile_id, input_fingerprint)
    WHERE atomic_claim_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS evidence_set_assessment_candidate_identity_idx
    ON evidence_set_assessment(claim_candidate_id, requirement_profile_id, input_fingerprint)
    WHERE claim_candidate_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS evidence_set_assessment_status_idx
    ON evidence_set_assessment(assessment, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence (
    id                  text PRIMARY KEY,
    canonical_url       text NOT NULL,
    publisher           text,
    source_type         text NOT NULL,
    publication_date    date,
    fetched_at          timestamptz,
    observed_at         timestamptz NOT NULL DEFAULT now(),
    content_sha256      text,
    excerpt             text,
    reference_period    text,
    independence_group  text,
    rights_status       text NOT NULL DEFAULT 'UNKNOWN',
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS claim_evidence_candidate (
    claim_id             text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    evidence_id          text NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    retrieval_method     text NOT NULL,
    retrieval_version    text NOT NULL,
    relation_candidate   text NOT NULL DEFAULT 'UNKNOWN',
    status               text NOT NULL DEFAULT 'RETRIEVED',
    score                numeric,
    statement_cutoff     date,
    retrieved_at         timestamptz NOT NULL DEFAULT now(),
    metadata             jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (claim_id, evidence_id, retrieval_version),
    CHECK (
        relation_candidate IN (
            'SUPPORT',
            'CONTRADICT',
            'CONTEXT',
            'UPDATE',
            'UNKNOWN'
        )
    ),
    CHECK (
        status IN (
            'RETRIEVED',
            'APPROVED',
            'REJECTED',
            'QUARANTINED'
        )
    ),
    CHECK (score IS NULL OR (score >= 0 AND score <= 1))
);

CREATE INDEX IF NOT EXISTS claim_evidence_candidate_claim_idx
    ON claim_evidence_candidate(claim_id, status);
CREATE INDEX IF NOT EXISTS evidence_url_hash_idx
    ON evidence(canonical_url, content_sha256);

CREATE TABLE IF NOT EXISTS evidence_observation (
    id                  text PRIMARY KEY,
    evidence_id         text NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    observation_type    text NOT NULL,
    metric              text,
    value_numeric       numeric,
    value_text          text,
    unit                text,
    reference_period    text,
    dimensions          jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_method   text NOT NULL,
    extraction_version  text NOT NULL,
    source_pointer      jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (value_numeric IS NOT NULL OR value_text IS NOT NULL),
    CONSTRAINT evidence_observation_status_check
        CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'QUARANTINED'))
);

CREATE INDEX IF NOT EXISTS evidence_observation_metric_idx
    ON evidence_observation(metric, reference_period);

-- DP-213: private, replayable statement of what evidence/research coverage is
-- still missing. A need can be collection-scoped, claim-scoped, candidate-scoped,
-- or collection + claim/candidate scoped. It is never a verdict or publication state.
CREATE TABLE IF NOT EXISTS coverage_need (
    id                              text PRIMARY KEY,
    collection_id                   text REFERENCES research_collection(id) ON DELETE CASCADE,
    atomic_claim_id                 text REFERENCES atomic_claim(id) ON DELETE CASCADE,
    claim_candidate_id              text REFERENCES claim_candidate(id) ON DELETE CASCADE,
    source_intelligence_assessment_id text REFERENCES evidence_set_assessment(id) ON DELETE SET NULL,
    need_type                       text NOT NULL,
    requirement_kind                text NOT NULL,
    requirement_fingerprint         text NOT NULL,
    question                        text NOT NULL,
    required_roles                  jsonb NOT NULL DEFAULT '[]'::jsonb,
    authority_scope                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    temporal_constraints            jsonb NOT NULL DEFAULT '{}'::jsonb,
    independence_requirement        integer,
    status                          text NOT NULL DEFAULT 'OPEN',
    attempt_count                   integer NOT NULL DEFAULT 0,
    max_attempts                    integer NOT NULL DEFAULT 3,
    blocker_code                    text,
    satisfied_by_content_id         text REFERENCES content_item(id) ON DELETE SET NULL,
    satisfied_by_evidence_id        text REFERENCES evidence(id) ON DELETE SET NULL,
    satisfied_by_source_profile_id  text REFERENCES source_profile(id) ON DELETE SET NULL,
    created_by                      text NOT NULL DEFAULT 'SOURCE_INTELLIGENCE',
    opened_at                       timestamptz NOT NULL DEFAULT now(),
    updated_at                      timestamptz NOT NULL DEFAULT now(),
    resolved_at                     timestamptz,
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK ((atomic_claim_id IS NOT NULL)::integer + (claim_candidate_id IS NOT NULL)::integer <= 1),
    CHECK (collection_id IS NOT NULL OR atomic_claim_id IS NOT NULL OR claim_candidate_id IS NOT NULL),
    CHECK (need_type IN ('PRIMARY_SOURCE','ORIGINAL_MEDIA','OFFICIAL_RECORD','EARLIER_VERSION','INDEPENDENT_SOURCE','TEMPORAL_GAP','ATTRIBUTION_GAP','OTHER')),
    CHECK (requirement_kind IN ('ROLE_ANY','FIELD_MATCH','AUTHORITY_SCOPE','TEMPORAL_CUTOFF','MIN_INDEPENDENT_LINEAGES','MANUAL_REVIEW','OTHER')),
    CHECK (requirement_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(required_roles) = 'array'),
    CHECK (jsonb_typeof(authority_scope) = 'object'),
    CHECK (jsonb_typeof(temporal_constraints) = 'object'),
    CHECK (independence_requirement IS NULL OR independence_requirement >= 1),
    CHECK (status IN ('OPEN','SEARCHING','SATISFIED','BLOCKED','WAIVED')),
    CHECK (attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempt_count <= max_attempts),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (
        (status IN ('OPEN','SEARCHING') AND resolved_at IS NULL)
        OR (status IN ('SATISFIED','BLOCKED','WAIVED') AND resolved_at IS NOT NULL)
    ),
    CHECK (
        status <> 'SATISFIED'
        OR satisfied_by_content_id IS NOT NULL
        OR satisfied_by_evidence_id IS NOT NULL
        OR satisfied_by_source_profile_id IS NOT NULL
    ),
    CHECK (status <> 'BLOCKED' OR blocker_code IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS coverage_need_identity_idx
    ON coverage_need(
        COALESCE(collection_id,''),
        COALESCE(atomic_claim_id,''),
        COALESCE(claim_candidate_id,''),
        requirement_fingerprint
    );
CREATE INDEX IF NOT EXISTS coverage_need_open_idx
    ON coverage_need(status, updated_at, attempt_count)
    WHERE status IN ('OPEN','SEARCHING');
CREATE INDEX IF NOT EXISTS coverage_need_collection_idx
    ON coverage_need(collection_id, status) WHERE collection_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS coverage_need_claim_idx
    ON coverage_need(atomic_claim_id, status) WHERE atomic_claim_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS coverage_need_event (
    id                              text PRIMARY KEY,
    coverage_need_id                text NOT NULL REFERENCES coverage_need(id) ON DELETE CASCADE,
    event_type                      text NOT NULL,
    from_status                     text,
    to_status                       text NOT NULL,
    attempt_number                  integer,
    source_intelligence_assessment_id text REFERENCES evidence_set_assessment(id) ON DELETE SET NULL,
    content_id                      text REFERENCES content_item(id) ON DELETE SET NULL,
    evidence_id                     text REFERENCES evidence(id) ON DELETE SET NULL,
    source_profile_id               text REFERENCES source_profile(id) ON DELETE SET NULL,
    actor_ref                       text NOT NULL DEFAULT 'system',
    reason                          text,
    created_at                      timestamptz NOT NULL DEFAULT now(),
    metadata                        jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (event_type IN ('CREATED','OBSERVED_AGAIN','SEARCH_ATTEMPT','SATISFIED','BLOCKED','WAIVED')),
    CHECK (from_status IS NULL OR from_status IN ('OPEN','SEARCHING','SATISFIED','BLOCKED','WAIVED')),
    CHECK (to_status IN ('OPEN','SEARCHING','SATISFIED','BLOCKED','WAIVED')),
    CHECK (attempt_number IS NULL OR attempt_number >= 1),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS coverage_need_event_need_idx
    ON coverage_need_event(coverage_need_id, created_at, id);

CREATE TABLE IF NOT EXISTS verification_run (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    source_intelligence_assessment_id text REFERENCES evidence_set_assessment(id),
    verification_kind   text NOT NULL,
    verification_version text NOT NULL,
    verification_rule    jsonb NOT NULL DEFAULT '{}'::jsonb,
    input_fingerprint   text NOT NULL,
    statement_cutoff    date NOT NULL,
    assessment          text NOT NULL,
    evidence_ids        jsonb NOT NULL DEFAULT '[]'::jsonb,
    observation_ids     jsonb NOT NULL DEFAULT '[]'::jsonb,
    blockers            jsonb NOT NULL DEFAULT '[]'::jsonb,
    rationale_codes     jsonb NOT NULL DEFAULT '[]'::jsonb,
    result              jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (
        assessment IN (
            'SUPPORTED',
            'FACTUALLY_FALSE',
            'OUTDATED_DATA',
            'INSUFFICIENT_EVIDENCE',
            'UNRESOLVED'
        )
    ),
    CHECK (
        jsonb_typeof(evidence_ids) = 'array'
        AND jsonb_typeof(observation_ids) = 'array'
        AND jsonb_typeof(blockers) = 'array'
        AND jsonb_typeof(rationale_codes) = 'array'
    )
);

CREATE INDEX IF NOT EXISTS verification_run_claim_idx
    ON verification_run(claim_id, created_at DESC);
CREATE INDEX IF NOT EXISTS verification_run_source_intelligence_idx
    ON verification_run(source_intelligence_assessment_id)
    WHERE source_intelligence_assessment_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS inference_candidate (
    id                      text PRIMARY KEY,
    claim_id                text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    conclusion_text         text NOT NULL,
    inference_kind          text NOT NULL,
    support_level           text NOT NULL,
    premise_refs            jsonb NOT NULL,
    assumptions             jsonb NOT NULL DEFAULT '[]'::jsonb,
    alternative_hypotheses  jsonb NOT NULL DEFAULT '[]'::jsonb,
    countervailing_factors  jsonb NOT NULL DEFAULT '[]'::jsonb,
    disconfirmers           jsonb NOT NULL DEFAULT '[]'::jsonb,
    risk_class              text NOT NULL DEFAULT 'STANDARD',
    inference_version       text NOT NULL DEFAULT 'reasoned-inference-v1',
    status                  text NOT NULL DEFAULT 'CANDIDATE',
    publication_blocked     boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (inference_kind IN ('DEDUCTIVE', 'ABDUCTIVE_BEST_EXPLANATION', 'STATISTICAL', 'EXCLUSION', 'COMPOSITE')),
    CHECK (support_level IN ('DIRECT', 'VERY_STRONG', 'STRONG', 'MODERATE', 'WEAK', 'INDETERMINATE')),
    CHECK (risk_class IN ('STANDARD', 'SENSITIVE_PERSON', 'CRIMINAL_ALLEGATION', 'IDENTITY_ATTRIBUTION', 'INTENT_ATTRIBUTION')),
    CHECK (inference_version = 'reasoned-inference-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (publication_blocked = true),
    CHECK (jsonb_typeof(premise_refs) = 'array' AND jsonb_array_length(premise_refs) > 0),
    CHECK (jsonb_typeof(assumptions) = 'array'),
    CHECK (jsonb_typeof(alternative_hypotheses) = 'array'),
    CHECK (jsonb_typeof(countervailing_factors) = 'array'),
    CHECK (jsonb_typeof(disconfirmers) = 'array')
);

CREATE INDEX IF NOT EXISTS inference_candidate_claim_idx
    ON inference_candidate(claim_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS claim_relation_candidate (
    id                  text PRIMARY KEY,
    subject_claim_id    text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    object_claim_id     text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    relation_type       text NOT NULL,
    relation_version    text NOT NULL,
    status              text NOT NULL DEFAULT 'CANDIDATE',
    confidence          numeric(5,4),
    rationale_codes     jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (subject_claim_id <> object_claim_id),
    CHECK (
        relation_type IN (
            'NO_RELATION',
            'RELATED_TOPIC',
            'SAME_PROPOSITION',
            'POSITION_CHANGE_CANDIDATE',
            'CONTRADICTION_CANDIDATE'
        )
    ),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX IF NOT EXISTS claim_relation_candidate_claims_idx
    ON claim_relation_candidate(subject_claim_id, object_claim_id, status);

CREATE TABLE IF NOT EXISTS reanalysis_trigger (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    trigger_type        text NOT NULL,
    source_type         text NOT NULL,
    source_id           text NOT NULL,
    source_hash         text,
    status              text NOT NULL DEFAULT 'PENDING',
    enqueued_job_id     text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    processed_at        timestamptz,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        trigger_type IN (
            'EVIDENCE_APPROVED',
            'EVIDENCE_HASH_CHANGED',
            'RIGHT_OF_REPLY',
            'CORRECTION',
            'RELATION_APPROVED',
            'MANUAL_REVIEW'
        )
    ),
    CHECK (status IN ('PENDING', 'ENQUEUED', 'PROCESSED', 'SUPERSEDED'))
);

CREATE INDEX IF NOT EXISTS reanalysis_trigger_claim_idx
    ON reanalysis_trigger(claim_id, status, created_at);

CREATE TABLE IF NOT EXISTS review_event (
    id                  text PRIMARY KEY,
    entity_type         text NOT NULL,
    entity_id           text NOT NULL,
    action              text NOT NULL,
    actor_ref           text NOT NULL DEFAULT 'local-operator',
    reason              text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        entity_type IN (
            'CLAIM_EVIDENCE_CANDIDATE',
            'EVIDENCE_OBSERVATION',
            'RELATION_CANDIDATE',
            'INFERENCE_CANDIDATE',
            'CLAIM_TEXT_PROVENANCE',
            'STATEMENT_CANDIDATE',
            'CLAIM_CANDIDATE',
            'ENTITY_RESOLUTION_CANDIDATE',
            'ENTITY_MENTION_CANDIDATE',
            'PROPOSITION_CLUSTER',
            'PROPOSITION_CLUSTER_MEMBER',
            'CONTENT_DERIVATION_FAMILY',
            'CONTENT_DERIVATION_CANDIDATE',
            'CANDIDATE_MATCH_RESULT',
            'TOPIC',
            'CLAIM_TOPIC_MEMBERSHIP',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    ),
    CHECK (
        action IN (
            'APPROVED',
            'REJECTED',
            'QUARANTINED',
            'SUPERSEDED'
        )
    )
);

CREATE INDEX IF NOT EXISTS review_event_entity_idx
    ON review_event(entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS finding (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    assessment          text NOT NULL,
    assessment_version  text NOT NULL DEFAULT 'deterministic-verification-v2',
    rationale           text NOT NULL,
    publication_status  text NOT NULL,
    publication_status_version text NOT NULL DEFAULT 'finding-publication-v1',
    policy_version      text NOT NULL,
    model_bundle        jsonb NOT NULL DEFAULT '{}'::jsonb,
    verification_run_id text REFERENCES verification_run(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    supersedes_id       text REFERENCES finding(id),
    CHECK (
        assessment IN (
            'SUPPORTED',
            'FACTUALLY_FALSE',
            'OUTDATED_DATA',
            'INSUFFICIENT_EVIDENCE',
            'UNRESOLVED'
        )
    ),
    CHECK (assessment_version = 'deterministic-verification-v2'),
    CHECK (publication_status_version = 'finding-publication-v1'),
    CHECK (
        publication_status IN (
            'INTERNAL_CANDIDATE',
            'PUBLISH',
            'NO_FINDING',
            'NEEDS_MORE_EVIDENCE',
            'UNRESOLVED',
            'POLICY_HOLD',
            'DISPUTED',
            'CORRECTED',
            'RETRACTED'
        )
    )
);

CREATE INDEX IF NOT EXISTS finding_claim_idx ON finding(claim_id);
CREATE UNIQUE INDEX IF NOT EXISTS finding_verification_policy_idx
    ON finding(verification_run_id, policy_version)
    WHERE verification_run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id      text NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    evidence_id     text NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    relation        text NOT NULL,
    PRIMARY KEY (finding_id, evidence_id, relation)
);

-- DP-224: material public assertions must be explicitly bound to approved
-- evidence/observations/passages. These rows are private publication-gate data,
-- not a second Finding model and not public prose by themselves.
CREATE TABLE IF NOT EXISTS finding_assertion (
    id                  text PRIMARY KEY,
    finding_id          text NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    assertion_text      text NOT NULL,
    assertion_text_sha256 text NOT NULL,
    assertion_type      text NOT NULL DEFAULT 'RATIONALE_MATERIAL',
    material            boolean NOT NULL DEFAULT true,
    required_relation   text NOT NULL DEFAULT 'SUPPORT',
    assertion_version   text NOT NULL DEFAULT 'finding-assertion-v1',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (assertion_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (assertion_type IN ('RATIONALE_MATERIAL','STRUCTURED_MATERIAL','LIMITATION')),
    CHECK (required_relation IN ('SUPPORT','CONTRADICT','CONTEXT','LIMITATION','UPDATE')),
    CHECK (assertion_version = 'finding-assertion-v1'),
    CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (finding_id, assertion_text_sha256, assertion_version)
);

CREATE INDEX IF NOT EXISTS finding_assertion_finding_idx
    ON finding_assertion(finding_id, material, created_at);

CREATE TABLE IF NOT EXISTS finding_assertion_citation (
    id                  text PRIMARY KEY,
    assertion_id        text NOT NULL REFERENCES finding_assertion(id) ON DELETE CASCADE,
    evidence_id         text NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    observation_id      text REFERENCES evidence_observation(id) ON DELETE CASCADE,
    passage_id          text REFERENCES passage(id) ON DELETE SET NULL,
    relation            text NOT NULL,
    citation_version    text NOT NULL DEFAULT 'finding-citation-v1',
    created_at          timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (relation IN ('SUPPORT','CONTRADICT','CONTEXT','LIMITATION','UPDATE')),
    CHECK (citation_version = 'finding-citation-v1'),
    CHECK (observation_id IS NOT NULL OR passage_id IS NOT NULL),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS finding_assertion_citation_assertion_idx
    ON finding_assertion_citation(assertion_id, relation, evidence_id);
CREATE INDEX IF NOT EXISTS finding_assertion_citation_observation_idx
    ON finding_assertion_citation(observation_id)
    WHERE observation_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS finding_assertion_citation_identity_idx
    ON finding_assertion_citation(
        assertion_id,
        evidence_id,
        COALESCE(observation_id, ''),
        COALESCE(passage_id, ''),
        relation
    );

CREATE TABLE IF NOT EXISTS claim_relation (
    subject_claim_id    text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    object_claim_id     text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    relation_type       text NOT NULL,
    confidence          numeric(5,4),
    rationale           text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_claim_id, object_claim_id, relation_type),
    CHECK (subject_claim_id <> object_claim_id),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS right_of_reply (
    id                  text PRIMARY KEY,
    finding_id          text NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    submitter_name      text,
    submitter_role      text,
    submitted_at        timestamptz NOT NULL DEFAULT now(),
    body                text NOT NULL,
    evidence_urls       jsonb NOT NULL DEFAULT '[]'::jsonb,
    status              text NOT NULL DEFAULT 'RECEIVED',
    reanalysis_job_id   text,
    public_visibility   text NOT NULL DEFAULT 'PRIVATE',
    CHECK (public_visibility IN ('PRIVATE', 'PUBLIC')),
    CHECK (
        status IN (
            'RECEIVED',
            'UNDER_REVIEW',
            'ACCEPTED',
            'PUBLISHED',
            'REJECTED',
            'WITHDRAWN'
        )
    )
);

CREATE TABLE IF NOT EXISTS correction (
    id                  text PRIMARY KEY,
    finding_id          text NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    previous_finding_id text REFERENCES finding(id),
    reason              text NOT NULL,
    changed_fields      jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    public_visibility   text NOT NULL DEFAULT 'PRIVATE',
    CHECK (public_visibility IN ('PRIVATE', 'PUBLIC'))
);

CREATE TABLE IF NOT EXISTS provider_receipt (
    id                  text PRIMARY KEY,
    content_id          text REFERENCES content_item(id) ON DELETE CASCADE,
    provider_id         text NOT NULL,
    model_id            text,
    operation           text NOT NULL,
    request_id          text,
    started_at          timestamptz,
    completed_at        timestamptz,
    input_bytes         bigint,
    input_seconds       numeric,
    estimated_cost_usd  numeric(12,6),
    status              text NOT NULL,
    receipt             jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (input_bytes IS NULL OR input_bytes >= 0),
    CHECK (input_seconds IS NULL OR input_seconds >= 0),
    CHECK (estimated_cost_usd IS NULL OR estimated_cost_usd >= 0)
);

-- DP-211: bounded Passage -> research candidate extraction receipts.
CREATE TABLE IF NOT EXISTS candidate_extraction_run (
    id                      text PRIMARY KEY,
    operation_key           text NOT NULL UNIQUE,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id              text NOT NULL,
    capture_id              text,
    canonical_segment_id    text,
    input_sha256            text NOT NULL,
    extractor_version       text NOT NULL DEFAULT 'candidate-extraction-v1',
    provider_id             text NOT NULL,
    model_id                text,
    provider_version        text NOT NULL,
    status                  text NOT NULL DEFAULT 'RUNNING',
    call_count              integer NOT NULL DEFAULT 0,
    cost_upper_bound_usd    numeric(12,6) NOT NULL DEFAULT 0,
    cost_usd                numeric(12,6) NOT NULL DEFAULT 0,
    statement_count         integer NOT NULL DEFAULT 0,
    claim_count             integer NOT NULL DEFAULT 0,
    entity_mention_count    integer NOT NULL DEFAULT 0,
    entity_resolution_count integer NOT NULL DEFAULT 0,
    provider_receipt_id     text REFERENCES provider_receipt(id),
    error_category          text,
    lease_owner             text,
    lease_until             timestamptz,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (extractor_version = 'candidate-extraction-v1'),
    CHECK (status IN ('RUNNING', 'COMPLETED', 'BLOCKED', 'FAILED')),
    CHECK ((status = 'RUNNING') = (lease_owner IS NOT NULL AND lease_until IS NOT NULL)),
    CONSTRAINT candidate_extraction_run_call_count_check CHECK (call_count IN (0, 1)),
    CHECK (cost_upper_bound_usd >= 0 AND cost_usd >= 0),
    CONSTRAINT candidate_extraction_run_pre_call_cost_check CHECK (call_count > 0 OR cost_usd = 0),
    CONSTRAINT candidate_extraction_run_completed_receipt_check
        CHECK (status <> 'COMPLETED' OR (call_count = 1 AND provider_receipt_id IS NOT NULL)),
    CHECK (statement_count >= 0 AND claim_count >= 0 AND entity_mention_count >= 0 AND entity_resolution_count >= 0),
    CHECK ((capture_id IS NOT NULL)::integer + (canonical_segment_id IS NOT NULL)::integer = 1),
    FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id) ON DELETE CASCADE,
    FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS candidate_extraction_run_content_idx
    ON candidate_extraction_run(content_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS candidate_extraction_run_passage_idx
    ON candidate_extraction_run(passage_id, started_at DESC);

CREATE TABLE IF NOT EXISTS entity_mention_candidate (
    id                      text PRIMARY KEY,
    extraction_run_id       text NOT NULL REFERENCES candidate_extraction_run(id) ON DELETE CASCADE,
    content_id              text NOT NULL REFERENCES content_item(id) ON DELETE CASCADE,
    passage_id              text NOT NULL,
    start_char              integer NOT NULL,
    end_char                integer NOT NULL,
    mention_text            text NOT NULL,
    mention_text_sha256     text NOT NULL,
    proposed_entity_type    text,
    extraction_method       text NOT NULL,
    extraction_version      text NOT NULL DEFAULT 'candidate-extraction-v1',
    status                  text NOT NULL DEFAULT 'CANDIDATE',
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id) ON DELETE CASCADE,
    CHECK (start_char >= 0 AND end_char > start_char),
    CHECK (mention_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (proposed_entity_type IS NULL OR proposed_entity_type IN ('PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT')),
    CHECK (extraction_method IN ('KNOWN_ALIAS', 'MODEL')),
    CHECK (extraction_version = 'candidate-extraction-v1'),
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_mention_candidate_identity_idx
    ON entity_mention_candidate(
        extraction_run_id, passage_id, start_char, end_char, extraction_method, COALESCE(proposed_entity_type, '')
    );

CREATE INDEX IF NOT EXISTS entity_mention_candidate_passage_idx
    ON entity_mention_candidate(content_id, passage_id, status, start_char);

CREATE TABLE IF NOT EXISTS processing_job (
    id              text PRIMARY KEY,
    content_id      text REFERENCES content_item(id) ON DELETE CASCADE,
    job_type        text NOT NULL,
    state           text NOT NULL,
    attempt         integer NOT NULL DEFAULT 0,
    available_at    timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    completed_at    timestamptz,
    lease_owner     text,
    lease_until     timestamptz,
    last_error      text,
    cost_usd        numeric(12,6) NOT NULL DEFAULT 0,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (attempt >= 0),
    CHECK (cost_usd >= 0)
);

CREATE INDEX IF NOT EXISTS processing_job_queue_idx
    ON processing_job(state, available_at, lease_until);

CREATE TABLE IF NOT EXISTS source_health (
    source_id               text PRIMARY KEY REFERENCES source(id) ON DELETE CASCADE,
    status                  text NOT NULL,
    last_success_at         timestamptz,
    last_item_at            timestamptz,
    consecutive_failures    integer NOT NULL DEFAULT 0,
    last_error              text,
    checked_at              timestamptz NOT NULL DEFAULT now(),
    CHECK (consecutive_failures >= 0)
);

CREATE TABLE IF NOT EXISTS source_poll_run (
    id                      text PRIMARY KEY,
    mode                    text NOT NULL,
    run_date                date NOT NULL,
    effective_config_hash   text NOT NULL,
    status                  text NOT NULL,
    diagnostic              boolean NOT NULL DEFAULT false,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    source_count            integer NOT NULL DEFAULT 0,
    discovered              integer NOT NULL DEFAULT 0,
    content_upserts         integer NOT NULL DEFAULT 0,
    jobs_enqueued           integer NOT NULL DEFAULT 0,
    duplicate_jobs          integer NOT NULL DEFAULT 0,
    budget_blocked          integer NOT NULL DEFAULT 0,
    omitted_items           integer NOT NULL DEFAULT 0,
    error_category          text,
    UNIQUE (mode, run_date, effective_config_hash),
    CHECK (mode IN ('source-due', 'full-source')),
    CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED_ALREADY_COMPLETED')),
    CHECK (source_count >= 0),
    CHECK (discovered >= 0),
    CHECK (content_upserts >= 0),
    CHECK (jobs_enqueued >= 0),
    CHECK (duplicate_jobs >= 0),
    CHECK (budget_blocked >= 0),
    CHECK (omitted_items >= 0)
);

CREATE INDEX IF NOT EXISTS source_poll_run_date_idx
    ON source_poll_run(run_date DESC, mode, status);

CREATE TABLE IF NOT EXISTS source_poll_run_source (
    id                      text PRIMARY KEY,
    run_id                  text NOT NULL REFERENCES source_poll_run(id) ON DELETE CASCADE,
    source_id               text NOT NULL REFERENCES source(id) ON DELETE CASCADE,
    mode                    text NOT NULL,
    run_date                date NOT NULL,
    effective_config_hash   text NOT NULL,
    diagnostic              boolean NOT NULL DEFAULT false,
    status                  text NOT NULL,
    discovered              integer NOT NULL DEFAULT 0,
    content_upserts         integer NOT NULL DEFAULT 0,
    jobs_enqueued           integer NOT NULL DEFAULT 0,
    duplicate_jobs          integer NOT NULL DEFAULT 0,
    budget_blocked          integer NOT NULL DEFAULT 0,
    omitted_items           integer NOT NULL DEFAULT 0,
    error_category          text,
    started_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz,
    UNIQUE (run_id, source_id),
    CHECK (mode IN ('source-due', 'full-source')),
    CHECK (status IN (
        'RUNNING', 'HEALTHY', 'BUDGET_BLOCKED', 'FAILED',
        'SKIPPED_NOT_DUE', 'SKIPPED_UNSUPPORTED',
        'SKIPPED_DAILY_LIMIT', 'SKIPPED_ALREADY_COMPLETED', 'BLOCKED'
    )),
    CHECK (discovered >= 0),
    CHECK (content_upserts >= 0),
    CHECK (jobs_enqueued >= 0),
    CHECK (duplicate_jobs >= 0),
    CHECK (budget_blocked >= 0),
    CHECK (omitted_items >= 0)
);

CREATE INDEX IF NOT EXISTS source_poll_run_source_idx
    ON source_poll_run_source(source_id, run_id);


-- DP-116: PostgreSQL-first private corpus search baseline.
CREATE INDEX IF NOT EXISTS content_item_search_fts_idx
    ON content_item USING gin (
        to_tsvector('italian', coalesce(title, '') || ' ' || coalesce(description, ''))
    );
CREATE INDEX IF NOT EXISTS content_item_title_trgm_idx
    ON content_item USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS passage_search_fts_idx
    ON passage USING gin (to_tsvector('italian', coalesce(private_text, '')));
CREATE INDEX IF NOT EXISTS passage_text_trgm_idx
    ON passage USING gin (private_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS statement_candidate_search_fts_idx
    ON statement_candidate USING gin (to_tsvector('italian', normalized_statement));
CREATE INDEX IF NOT EXISTS statement_candidate_text_trgm_idx
    ON statement_candidate USING gin (normalized_statement gin_trgm_ops);

CREATE INDEX IF NOT EXISTS claim_candidate_search_fts_idx
    ON claim_candidate USING gin (to_tsvector('italian', normalized_claim));
CREATE INDEX IF NOT EXISTS claim_candidate_text_trgm_idx
    ON claim_candidate USING gin (normalized_claim gin_trgm_ops);

CREATE INDEX IF NOT EXISTS atomic_claim_search_fts_idx
    ON atomic_claim USING gin (to_tsvector('italian', normalized_claim));
CREATE INDEX IF NOT EXISTS atomic_claim_text_trgm_idx
    ON atomic_claim USING gin (normalized_claim gin_trgm_ops);

CREATE INDEX IF NOT EXISTS research_collection_search_fts_idx
    ON research_collection USING gin (
        to_tsvector('italian', name || ' ' || scope_text)
    );
CREATE INDEX IF NOT EXISTS research_collection_name_trgm_idx
    ON research_collection USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS person_alias_trgm_idx
    ON person_alias USING gin (alias gin_trgm_ops);
CREATE INDEX IF NOT EXISTS organization_alias_trgm_idx
    ON organization_alias USING gin (alias gin_trgm_ops);
CREATE INDEX IF NOT EXISTS topic_alias_trgm_idx
    ON topic_alias USING gin (alias gin_trgm_ops);
CREATE INDEX IF NOT EXISTS event_alias_trgm_idx
    ON event_alias USING gin (alias gin_trgm_ops);

CREATE INDEX IF NOT EXISTS person_name_trgm_idx
    ON person USING gin (canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS organization_name_trgm_idx
    ON organization USING gin (canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS topic_search_fts_idx
    ON topic USING gin (to_tsvector('italian', canonical_name || ' ' || scope_text));
CREATE INDEX IF NOT EXISTS topic_name_trgm_idx
    ON topic USING gin (canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS event_search_fts_idx
    ON event USING gin (to_tsvector('italian', canonical_name || ' ' || scope_text));
CREATE INDEX IF NOT EXISTS event_name_trgm_idx
    ON event USING gin (canonical_name gin_trgm_ops);

COMMIT;
