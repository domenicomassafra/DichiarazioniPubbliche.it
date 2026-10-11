BEGIN;

-- DP-232/512: the adapter may report an upper bound of zero while its actual
-- provider billing basis is unknown. This must remain UNKNOWN, not be recoded
-- as ZERO_COST or a fabricated nonzero estimate. The billing consumer and
-- paid-dispatch gate independently deny UNKNOWN; this receipt is an audit.
ALTER TABLE provider_receipt
    DROP CONSTRAINT IF EXISTS provider_receipt_unknown_cost_check;

COMMIT;
