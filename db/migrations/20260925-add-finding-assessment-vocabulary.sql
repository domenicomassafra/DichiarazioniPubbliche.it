BEGIN;

-- DP-103: constrain the canonical verification assessment copied onto findings.
-- DP-103: version and constrain claim, assessment, and publication vocabularies.
-- Existing rows are not rewritten: databases with legacy values must be
-- inventoried and migrated through reviewed superseding findings before this
-- migration is applied. The public projection fails closed on unknown values.
ALTER TABLE atomic_claim
    ADD COLUMN IF NOT EXISTS claim_type_version text NOT NULL
        DEFAULT 'atomic-claim-v1';

ALTER TABLE atomic_claim
    DROP CONSTRAINT IF EXISTS atomic_claim_claim_type_check;

ALTER TABLE atomic_claim
    ADD CONSTRAINT atomic_claim_claim_type_check
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
        AND claim_type_version = 'atomic-claim-v1'
    );

ALTER TABLE finding
    ADD COLUMN IF NOT EXISTS assessment_version text NOT NULL
        DEFAULT 'deterministic-verification-v2';

ALTER TABLE finding
    ADD COLUMN IF NOT EXISTS publication_status_version text NOT NULL
        DEFAULT 'finding-publication-v1';

ALTER TABLE finding
    DROP CONSTRAINT IF EXISTS finding_assessment_check;

ALTER TABLE finding
    ADD CONSTRAINT finding_assessment_check
    CHECK (
        assessment IN (
            'SUPPORTED',
            'FACTUALLY_FALSE',
            'OUTDATED_DATA',
            'INSUFFICIENT_EVIDENCE',
            'UNRESOLVED'
        )
    );

ALTER TABLE finding
    DROP CONSTRAINT IF EXISTS finding_assessment_version_check;

ALTER TABLE finding
    ADD CONSTRAINT finding_assessment_version_check
    CHECK (assessment_version = 'deterministic-verification-v2');

ALTER TABLE finding
    DROP CONSTRAINT IF EXISTS finding_publication_status_version_check;

ALTER TABLE finding
    ADD CONSTRAINT finding_publication_status_version_check
    CHECK (publication_status_version = 'finding-publication-v1');

COMMIT;
