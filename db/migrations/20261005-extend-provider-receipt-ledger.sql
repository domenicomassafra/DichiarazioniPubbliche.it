BEGIN;

ALTER TABLE provider_receipt
    ADD COLUMN IF NOT EXISTS operation_key text,
    ADD COLUMN IF NOT EXISTS attempt integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS measured_cost_usd numeric(12,6),
    ADD COLUMN IF NOT EXISTS billing_basis text NOT NULL DEFAULT 'ESTIMATED_ONLY',
    ADD COLUMN IF NOT EXISTS total_tokens bigint,
    ADD COLUMN IF NOT EXISTS request_count integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS ledger_scope jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_receipt
    DROP CONSTRAINT IF EXISTS provider_receipt_operation_key_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_attempt_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_measured_cost_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_total_tokens_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_request_count_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_billing_basis_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_measured_basis_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_unknown_cost_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_zero_cost_check,
    DROP CONSTRAINT IF EXISTS provider_receipt_ledger_scope_check;

ALTER TABLE provider_receipt
    ADD CONSTRAINT provider_receipt_operation_key_check
        CHECK (operation_key IS NULL OR length(btrim(operation_key)) > 0),
    ADD CONSTRAINT provider_receipt_attempt_check CHECK (attempt >= 1),
    ADD CONSTRAINT provider_receipt_measured_cost_check
        CHECK (measured_cost_usd IS NULL OR measured_cost_usd >= 0),
    ADD CONSTRAINT provider_receipt_total_tokens_check
        CHECK (total_tokens IS NULL OR total_tokens >= 0),
    ADD CONSTRAINT provider_receipt_request_count_check CHECK (request_count >= 0),
    ADD CONSTRAINT provider_receipt_billing_basis_check CHECK (
        billing_basis IN (
            'MEASURED_PROVIDER_COST', 'ESTIMATED_ONLY', 'EXTERNAL_PLAN',
            'ZERO_COST', 'UNKNOWN'
        )
    ),
    ADD CONSTRAINT provider_receipt_measured_basis_check CHECK (
        billing_basis <> 'MEASURED_PROVIDER_COST'
        OR measured_cost_usd IS NOT NULL
    ),
    ADD CONSTRAINT provider_receipt_unknown_cost_check CHECK (
        billing_basis <> 'UNKNOWN'
        OR COALESCE(estimated_cost_usd, 0) > 0
        OR measured_cost_usd IS NOT NULL
    ),
    ADD CONSTRAINT provider_receipt_zero_cost_check CHECK (
        billing_basis <> 'ZERO_COST'
        OR (
            COALESCE(estimated_cost_usd, 0) = 0
            AND COALESCE(measured_cost_usd, 0) = 0
        )
    ),
    ADD CONSTRAINT provider_receipt_ledger_scope_check
        CHECK (jsonb_typeof(ledger_scope) = 'object');

CREATE INDEX IF NOT EXISTS provider_receipt_operation_idx
    ON provider_receipt(operation_key, attempt)
    WHERE operation_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS provider_receipt_billing_idx
    ON provider_receipt(billing_basis, completed_at);

COMMIT;
