"""Atomic provider receipt settlement SQL for PostgreSQL queue accounting."""

RECEIPT_INSERT_SQL = """
            -- The lock and receipt query need distinct READ COMMITTED
            -- snapshots: another writer may commit while this lock waits.
            BEGIN;
            SET LOCAL lock_timeout = '2500ms';
            DO $guard$
            BEGIN
                PERFORM pg_advisory_xact_lock(
                    hashtextextended('dp512:worker:global',0));
            END $guard$;
            WITH receipt_candidate AS (
                SELECT
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM provider_receipt legacy
                            WHERE legacy.id=:'receipt_id_base'
                              AND legacy.attempt=GREATEST(job.attempt,1)
                        ) THEN :'receipt_id_base'
                        ELSE :'receipt_id_base' || ':attempt:' ||
                            GREATEST(job.attempt,1)::text
                    END AS receipt_id,
                    GREATEST(job.attempt,1) AS attempt
                FROM processing_job job
                WHERE job.id=:'job_id'
                  AND job.content_id=:'content_id'
            ),
            prior_paid_receipt AS MATERIALIZED (
                -- One chargeable receipt per reserved job/attempt. A changed
                -- request_key must not produce a second debit for one hold.
                SELECT r.id
                FROM receipt_candidate candidate
                JOIN worker_budget_reservation h
                  ON h.job_id=:'job_id' AND GREATEST(h.attempt,1)=candidate.attempt
                JOIN provider_receipt r
                  ON r.ledger_scope->>'job_id'=:'job_id'
                 AND r.attempt=candidate.attempt
                WHERE COALESCE(CASE
                    WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                        THEN r.measured_cost_usd
                    ELSE r.estimated_cost_usd
                END, 0) > 0
                ORDER BY r.started_at NULLS LAST, r.id
                LIMIT 1
            ),
            inserted AS (
                INSERT INTO provider_receipt (
                    id, content_id, provider_id, model_id, operation, request_id,
                    operation_key, attempt,
                    started_at, completed_at, input_bytes, input_seconds,
                    estimated_cost_usd, measured_cost_usd, billing_basis,
                    total_tokens, request_count, ledger_scope, status, receipt
                )
                SELECT
                    candidate.receipt_id, :'content_id', :'provider_id',
                    NULLIF(:'model_id',''), :'operation', NULLIF(:'request_id',''),
                    :'operation_key', candidate.attempt,
                    now(), now(), NULLIF(:'input_bytes','')::bigint,
                    NULLIF(:'input_seconds','')::numeric,
                    :'estimated_cost_usd'::numeric,
                    NULLIF(:'measured_cost_usd','')::numeric,
                    :'billing_basis',
                    NULLIF(:'total_tokens','')::bigint,
                    :'request_count'::integer,
                    :'ledger_scope'::jsonb,
                    :'status', :'receipt'::jsonb
                FROM receipt_candidate candidate
                WHERE NOT EXISTS (SELECT 1 FROM prior_paid_receipt)
                ON CONFLICT (id) DO NOTHING
                RETURNING
                    id,
                    content_id,
                    attempt,
                    ledger_scope,
                    CASE
                        WHEN billing_basis='MEASURED_PROVIDER_COST'
                            THEN measured_cost_usd
                        ELSE estimated_cost_usd
                    END AS accounted_cost_usd
            ),
            updated_job AS (
            UPDATE processing_job
            SET cost_usd = cost_usd + COALESCE(
                (SELECT accounted_cost_usd FROM inserted), 0
            )
            WHERE id = :'job_id'
            RETURNING id
            )
            , settled_reservation AS (
                UPDATE worker_budget_reservation h
                SET state='RECEIPTED', receipt_id=r.id, receipted_at=now()
                FROM inserted r
                WHERE h.job_id=:'job_id'
                  AND h.attempt=(SELECT attempt FROM processing_job
                                 WHERE id=:'job_id')
                  AND h.state='RESERVED'
                  AND h.content_id=r.content_id
                  AND r.attempt=GREATEST(h.attempt,1)
                  AND r.ledger_scope->>'job_id'=:'job_id'
                  -- An underpriced receipt retains its hold.
                  AND r.accounted_cost_usd >= h.upper_bound_usd
                RETURNING h.job_id
            )
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM prior_paid_receipt r, receipt_candidate c
                    WHERE r.id <> c.receipt_id
                ) THEN 'RECEIPT_ATTEMPT_ALREADY_CHARGED'
                ELSE COALESCE(
                    (SELECT id FROM inserted),
                    (SELECT id FROM prior_paid_receipt),
                    (SELECT receipt_id FROM receipt_candidate)
                )
            END::text;
            COMMIT;
            """
