"""Bounded, private DP-512 ledger/health/scheduler window parity readback.

Reuses the canonical QueueExecutionCostStore and operation-ledger reconciliation.
Both scheduler and canonical ledger now select started_at before completed_at.
Permanently undated rows are held rather than treated as verified-free. This
read-only checker detects remaining drift without granting paid dispatch.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from dichiarazioni_pubbliche.operation_ledger import (
    BILLING_BASES,
    reconcile_operation_billing,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

MAX_PARITY_RECEIPTS = 1000

_SCHEDULER_WINDOW_IDS_SQL = """
SELECT COALESCE(json_agg(id ORDER BY id)::text, '[]')
FROM (
    SELECT id
    FROM provider_receipt
    WHERE COALESCE(started_at, completed_at, now()) >= :'since'::timestamptz
      AND COALESCE(started_at, completed_at, now()) < :'until'::timestamptz
    ORDER BY id
    LIMIT 1001
) x;
"""

_LEDGER_WINDOW_COUNT_SQL = """
SELECT count(*)::text FROM provider_receipt
WHERE COALESCE(started_at, completed_at) >= :'since'::timestamptz
  AND COALESCE(started_at, completed_at) < :'until'::timestamptz;
"""

_UNDATED_COUNT_SQL = """
SELECT count(*)::text FROM provider_receipt
WHERE started_at IS NULL AND completed_at IS NULL;
"""


def _bound(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("DP512_WINDOW_INVALID")
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError("DP512_WINDOW_INVALID") from None


def read_private_billing_health(
    store: QueueExecutionCostStore, *, since: str, until: str
) -> dict[str, Any]:
    """Compare two actual PG consumers, exposing only sanitized aggregates.

    Independent psql invocations do not share a repeatable-read snapshot.
    A positive match is a bounded observation, never a concurrent CAS proof.
    """
    start, end = _bound(since), _bound(until)
    if start >= end:
        raise ValueError("DP512_WINDOW_INVALID")
    from_utc, to_utc = start.isoformat(), end.isoformat()
    scheduler_ids = json.loads(
        store.run(_SCHEDULER_WINDOW_IDS_SQL, since=from_utc, until=to_utc) or "[]"
    )
    if (
        not isinstance(scheduler_ids, list)
        or len(scheduler_ids) > MAX_PARITY_RECEIPTS
        or any(not isinstance(item, str) or not item for item in scheduler_ids)
        or len(set(scheduler_ids)) != len(scheduler_ids)
    ):
        raise ValueError("DP512_PARITY_RECEIPT_BOUND_OR_ID_INVALID")

    # Canonical worker/queue reader, not a second receipt adapter or cost table.
    ledger_count = int(
        store.run(_LEDGER_WINDOW_COUNT_SQL, since=from_utc, until=to_utc)
    )
    undated_count = int(store.run(_UNDATED_COUNT_SQL))
    if ledger_count < 0 or undated_count < 0:
        raise ValueError("DP512_PARITY_COUNT_INVALID")
    if ledger_count > MAX_PARITY_RECEIPTS:
        raise ValueError("DP512_PARITY_RECEIPT_BOUND_OR_ID_INVALID")
    rows = store.operation_ledger_receipts(since=from_utc, until=to_utc)
    if len(rows) > MAX_PARITY_RECEIPTS:
        raise ValueError("DP512_PARITY_RECEIPT_BOUND_OR_ID_INVALID")
    billing = reconcile_operation_billing(rows)
    counts = {basis: 0 for basis in sorted(BILLING_BASES)}
    for group in billing.groups:
        for attempt in group.attempts:
            counts[attempt.billing_basis] += 1
    ledger_ids = [row.receipt_id for row in rows]
    if any(row is None for row in ledger_ids):
        raise ValueError("DP512_PARITY_RECEIPT_ID_REQUIRED")

    # This is a warning that the receipt windows disagree; never auto-correct
    # the canonical row, infer a real invoice or lower the admission policy.
    same_receipts = set(scheduler_ids) == set(ledger_ids) and ledger_count == len(
        ledger_ids
    )
    parity = (
        "MISMATCH_HELD"
        if not same_receipts
        else "UNALLOCATED_HELD"
        if undated_count
        else "RECEIPT_IDS_MATCH_NONATOMIC"
    )
    return {
        "schema_version": "dp512-private-billing-health-v1",
        "window_start_utc": from_utc,
        "window_end_utc": to_utc,
        "scheduler_health_parity": parity,
        "scheduler_window_attempt_count": len(scheduler_ids),
        "undated_unallocated_attempt_count": undated_count,
        "operation_count": billing.operation_count,
        "attempt_count": billing.attempt_count,
        "classification_counts": counts,
        "legacy_attempt_count": sum(
            row.operation_key.startswith("legacy:") for row in rows
        ),
        "recorded_measured_unverified_usd": format(
            billing.recorded_measured_usd, ".6f"
        ),
        "provisional_estimated_usd": format(billing.provisional_estimated_usd, ".6f"),
        "unknown_cash_attempt_count": billing.unknown_cash_attempts,
        "unknown_local_energy_attempt_count": billing.unknown_energy_attempts,
        "verified_invoice_usd": None,
        "invoice_attested": False,
        "snapshot_atomic": False,
        "dispatch_authorized": False,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Private DP512 PG consumer parity readback"
    )
    parser.add_argument(
        "--since", required=True, help="Inclusive timezone-aware ISO datetime"
    )
    parser.add_argument(
        "--until", required=True, help="Exclusive timezone-aware ISO datetime"
    )
    args = parser.parse_args()
    # Use libpq's environment/service configuration. A URL containing account
    # credentials must not appear in a child psql process's command line.
    if not (os.environ.get("PGDATABASE") or os.environ.get("PGSERVICE")):
        parser.error("DP512_PGDATABASE_OR_PGSERVICE_REQUIRED")
    try:
        report = read_private_billing_health(
            QueueExecutionCostStore(), since=args.since, until=args.until
        )
    except (ValueError, RuntimeError):
        # Do not echo libpq errors, DSN, receipt/provider identifiers or SQL.
        print(json.dumps({"status": "HELD", "reason": "DP512_PARITY_READBACK_FAILED"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
