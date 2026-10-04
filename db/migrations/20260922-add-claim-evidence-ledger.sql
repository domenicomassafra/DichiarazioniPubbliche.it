BEGIN;

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

COMMIT;
