BEGIN;

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

ALTER TABLE evidence_observation
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'CANDIDATE';

ALTER TABLE evidence_observation
    DROP CONSTRAINT IF EXISTS evidence_observation_status_check;

ALTER TABLE evidence_observation
    ADD CONSTRAINT evidence_observation_status_check
    CHECK (status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'QUARANTINED'));

CREATE INDEX IF NOT EXISTS evidence_observation_metric_idx
    ON evidence_observation(metric, reference_period);

CREATE TABLE IF NOT EXISTS verification_run (
    id                  text PRIMARY KEY,
    claim_id            text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    verification_kind   text NOT NULL,
    verification_version text NOT NULL,
    verification_rule   jsonb NOT NULL DEFAULT '{}'::jsonb,
    input_fingerprint   text NOT NULL,
    statement_cutoff    date NOT NULL,
    assessment          text NOT NULL,
    evidence_ids        jsonb NOT NULL DEFAULT '[]'::jsonb,
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
    )
);

ALTER TABLE verification_run
    ADD COLUMN IF NOT EXISTS verification_rule jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS verification_run_claim_idx
    ON verification_run(claim_id, created_at DESC);

ALTER TABLE finding
    ADD COLUMN IF NOT EXISTS verification_run_id text REFERENCES verification_run(id);

CREATE UNIQUE INDEX IF NOT EXISTS finding_verification_policy_idx
    ON finding(verification_run_id, policy_version)
    WHERE verification_run_id IS NOT NULL;

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
            'FINDING'
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

COMMIT;
