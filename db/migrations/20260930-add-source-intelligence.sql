BEGIN;

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

ALTER TABLE verification_run
    ADD COLUMN IF NOT EXISTS source_intelligence_assessment_id text
    REFERENCES evidence_set_assessment(id);

CREATE INDEX IF NOT EXISTS verification_run_source_intelligence_idx
    ON verification_run(source_intelligence_assessment_id)
    WHERE source_intelligence_assessment_id IS NOT NULL;

COMMIT;
