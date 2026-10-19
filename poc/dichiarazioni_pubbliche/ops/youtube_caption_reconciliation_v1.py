"""Private, read-only source-backed assessment of historical YouTube captions.

Canonical provider_receipt rows stay immutable. This versioned assessment is
only for the public yt-dlp caption path, never an LLM, Data API v3, invoice,
plan entitlement or permission to dispatch paid work.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from decimal import Decimal
from typing import Any

from dichiarazioni_pubbliche.operation_ledger import reconcile_operation_billing
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore


RULE_VERSION = "youtube-caption-yt-dlp-v1"
OPERATIONS = frozenset({"CAPTION_PROBE", "CAPTION_CAPTURE"})
SOURCE_CODE = "poc/dichiarazioni_pubbliche/platform_transcript.py:YouTubeResolver"
SOURCE_DOC = "https://github.com/yt-dlp/yt-dlp/wiki/Extractors"
API_DOC = "https://developers.google.com/youtube/v3/getting-started"


def read_youtube_caption_reconciliation(
    store: QueueExecutionCostStore, *, since: str, until: str
) -> dict[str, Any]:
    """Assess only verifiable zero-marginal-fee caption receipts; fail closed.

    No effective basis is written to PostgreSQL. Recorded legacy classifications
    remain available for audit, while the source-backed assessment explicitly
    distinguishes the actual public extraction from an unverified zero estimate.
    """
    rows = store.operation_ledger_receipts(
        provider_id="youtube", since=since, until=until
    )
    billing = reconcile_operation_billing(rows)
    if not billing.attempt_count:
        raise ValueError("YOUTUBE_CAPTION_RECEIPTS_MISSING")

    unique = {}
    for row in rows:
        if (
            row.provider_id != "youtube"
            or row.operation not in OPERATIONS
            or row.model_id is not None
            or row.billing_basis not in {"ESTIMATED_ONLY", "ZERO_COST"}
            or row.estimated_cost_usd != Decimal("0")
            or row.measured_cost_usd not in {None, Decimal("0")}
            or row.total_tokens not in (None, 0)
        ):
            raise ValueError("YOUTUBE_CAPTION_BILLING_EVIDENCE_CONFLICT")
        unique[(row.operation_key, row.attempt)] = row

    if len(unique) != billing.attempt_count:
        raise ValueError("YOUTUBE_CAPTION_ATTEMPT_PARITY_MISMATCH")
    operations = Counter(row.operation for row in unique.values())
    bases = Counter(row.billing_basis for row in unique.values())
    return {
        "schema_version": "youtube-caption-reconciliation-v1",
        "status": "SOURCE_BACKED_ZERO_PROVIDER_FEE",
        "evidence_rule": RULE_VERSION,
        "source_code": SOURCE_CODE,
        "source_documentation": SOURCE_DOC,
        "data_api_v3_documentation": API_DOC,
        "channel": "PUBLIC_YT_DLP_CAPTION_NOT_DATA_API_V3",
        "provider_marginal_cost_usd": "0.000000",
        "youtube_data_api_v3_quota_units": 0,
        "operation_count": billing.operation_count,
        "attempt_count": billing.attempt_count,
        "duplicate_receipt_replays": billing.duplicate_receipt_replays,
        "caption_probe_attempts": operations["CAPTION_PROBE"],
        "caption_capture_attempts": operations["CAPTION_CAPTURE"],
        "historical_estimated_only_attempts": bases["ESTIMATED_ONLY"],
        "canonical_zero_cost_attempts": bases["ZERO_COST"],
        "assessed_zero_provider_fee_attempts": len(unique),
        "unreconciled_youtube_caption_attempts": 0,
        "unmeasured_local_energy_attempts": billing.unknown_energy_attempts,
        "canonical_receipts_modified": False,
        "invoice_attested": False,
        "paid_dispatch_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Private YouTube caption reconciliation")
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    args = parser.parse_args()
    if not (os.environ.get("PGDATABASE") or os.environ.get("PGSERVICE")):
        parser.error("PGDATABASE_OR_PGSERVICE_REQUIRED")
    try:
        result = read_youtube_caption_reconciliation(
            QueueExecutionCostStore(), since=args.since, until=args.until
        )
    except (ValueError, RuntimeError):
        print(json.dumps({"status": "HELD", "reason": "YOUTUBE_CAPTION_RECONCILIATION_FAILED"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
