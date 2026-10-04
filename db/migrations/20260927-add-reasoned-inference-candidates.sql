BEGIN;

-- DP-110: explicit evidence-based inference candidates.
-- This layer is private/review-only in v1. It may represent deductions or bounded
-- hypotheses, but it is not evidence, verification, a finding, or publication.

CREATE TABLE IF NOT EXISTS inference_candidate (
    id                      text PRIMARY KEY,
    claim_id                text NOT NULL REFERENCES atomic_claim(id) ON DELETE CASCADE,
    conclusion_text         text NOT NULL,
    inference_kind          text NOT NULL,
    support_level           text NOT NULL,
    premise_refs            jsonb NOT NULL,
    assumptions             jsonb NOT NULL DEFAULT '[]'::jsonb,
    alternative_hypotheses  jsonb NOT NULL DEFAULT '[]'::jsonb,
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
    CHECK (jsonb_typeof(disconfirmers) = 'array')
);

CREATE INDEX IF NOT EXISTS inference_candidate_claim_idx
    ON inference_candidate(claim_id, status, created_at DESC);

ALTER TABLE review_event
    DROP CONSTRAINT IF EXISTS review_event_entity_type_check;

ALTER TABLE review_event
    ADD CONSTRAINT review_event_entity_type_check
    CHECK (
        entity_type IN (
            'CLAIM_EVIDENCE_CANDIDATE',
            'EVIDENCE_OBSERVATION',
            'RELATION_CANDIDATE',
            'INFERENCE_CANDIDATE',
            'FINDING',
            'SPEAKER_IDENTITY_CANDIDATE',
            'PERSON_ROLE_INTERVAL',
            'RIGHT_OF_REPLY',
            'CORRECTION'
        )
    );

COMMIT;
