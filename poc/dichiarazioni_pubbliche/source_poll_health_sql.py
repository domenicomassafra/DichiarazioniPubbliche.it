"""Private source-health SQL: a policy denial is not a provider failure.

Both paths stamp checked_at for source_due cooldown. A denial preserves
last_success_at: it does not prove a successful fetch or corpus freshness.
"""

TECHNICAL_FAILURE_HEALTH_SQL = """
INSERT INTO source_health (
    source_id, status, consecutive_failures, last_error, checked_at
) VALUES (
    :'source_id', 'DEGRADED', 1, :'error', now()
)
ON CONFLICT (source_id) DO UPDATE SET
    consecutive_failures = source_health.consecutive_failures + 1,
    status = CASE
        WHEN source_health.consecutive_failures + 1 >= 3 THEN 'FAILED'
        ELSE 'DEGRADED'
    END,
    last_error = EXCLUDED.last_error,
    checked_at = now();
"""

POLICY_BLOCK_HEALTH_SQL = """
INSERT INTO source_health (
    source_id, status, consecutive_failures, last_error, checked_at
) VALUES (
    :'source_id', 'POLICY_BLOCKED', 0, :'error', now()
)
ON CONFLICT (source_id) DO UPDATE SET
    status = 'POLICY_BLOCKED',
    consecutive_failures = 0,
    last_error = EXCLUDED.last_error,
    checked_at = now();
"""
