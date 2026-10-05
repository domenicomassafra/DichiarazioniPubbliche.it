BEGIN;

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

COMMIT;
