#!/usr/bin/env python3
"""Inspect the authoritative private research chain; no fetch, model or writes."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.private_pipeline_reconciliation import (  # noqa: E402
    PrivatePipelineReconciliationStore,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read persisted private source-to-review linkage")
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--after-content-id")
    parser.add_argument("--summary", action="store_true", help="Aggregate private blocker codes without emitting record IDs")
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    args = parser.parse_args(argv)
    try:
        result = PrivatePipelineReconciliationStore(database_url=args.database_url).read_collection(
            collection_id=args.collection_id, limit=args.limit,
            after_content_id=args.after_content_id,
        )
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({
            "status": "BLOCKED_READ_ONLY",
            "reason_code": str(exc),
            "private_only": True,
            "publication_authority": False,
        }, sort_keys=True))
        return 2
    if args.summary:
        result = {
            "contract_version": result["contract_version"],
            "status": "PRIVATE_PIPELINE_READ_ONLY_SUMMARY",
            "scanned_contents": result["contents"],
            "scanned_items": len(result["items"]),
            "review_ready_private": sum(bool(item["private_review_queue_eligible"]) for item in result["items"]),
            "next_private_steps": dict(sorted(Counter(
                str(item["next_private_step"]) for item in result["items"]
            ).items())),
            "blocker_counts": dict(sorted(Counter(
                str(reason) for item in result["items"] for reason in item["blockers"]
            ).items())),
            "candidate_pagination_required": result["candidate_pagination_required"],
            "private_only": True,
            "publication_authority": False,
            "review_authority": False,
            "promotion_authority": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
