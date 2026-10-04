BEGIN;

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
    CHECK ((status IN ('OPEN','SEARCHING') AND resolved_at IS NULL) OR (status IN ('SATISFIED','BLOCKED','WAIVED') AND resolved_at IS NOT NULL)),
    CHECK (status <> 'SATISFIED' OR satisfied_by_content_id IS NOT NULL OR satisfied_by_evidence_id IS NOT NULL OR satisfied_by_source_profile_id IS NOT NULL),
    CHECK (status <> 'BLOCKED' OR blocker_code IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS coverage_need_identity_idx
    ON coverage_need(COALESCE(collection_id,''),COALESCE(atomic_claim_id,''),COALESCE(claim_candidate_id,''),requirement_fingerprint);
CREATE INDEX IF NOT EXISTS coverage_need_open_idx
    ON coverage_need(status, updated_at, attempt_count) WHERE status IN ('OPEN','SEARCHING');
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

ALTER TABLE research_discovery_manifest
    ADD COLUMN IF NOT EXISTS coverage_need_ids jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE research_discovery_manifest
    DROP CONSTRAINT IF EXISTS research_discovery_manifest_coverage_need_ids_check;
ALTER TABLE research_discovery_manifest
    ADD CONSTRAINT research_discovery_manifest_coverage_need_ids_check
    CHECK (jsonb_typeof(coverage_need_ids) = 'array');

COMMIT;
