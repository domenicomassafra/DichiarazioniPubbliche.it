BEGIN;

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

COMMIT;
