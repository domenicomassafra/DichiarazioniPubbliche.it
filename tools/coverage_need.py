#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.coverage_needs import (  # noqa: E402
    coverage_need_event_id,
    discovery_hint_for_need,
)
from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and transition private Coverage Needs")
    parser.add_argument("--database-url")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--collection-id")
    list_parser.add_argument("--limit", type=int, default=50)

    attempt = sub.add_parser("attempt")
    attempt.add_argument("coverage_need_id")
    attempt.add_argument("--actor-ref", default="local-operator")
    attempt.add_argument("--reason", default="")

    satisfy = sub.add_parser("satisfy")
    satisfy.add_argument("coverage_need_id")
    satisfy.add_argument("--content-id")
    satisfy.add_argument("--evidence-id")
    satisfy.add_argument("--source-profile-id")
    satisfy.add_argument("--actor-ref", default="local-operator")
    satisfy.add_argument("--reason", default="")

    block = sub.add_parser("block")
    block.add_argument("coverage_need_id")
    block.add_argument("blocker_code")
    block.add_argument("--actor-ref", default="local-operator")
    block.add_argument("--reason", default="")

    args = parser.parse_args()
    store = ClaimEvidenceObservationStore(database_url=args.database_url)
    if args.command == "list":
        rows = store.searchable_coverage_needs(
            collection_id=args.collection_id,
            limit=args.limit,
        )
        print(json.dumps([discovery_hint_for_need(row) for row in rows], ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "attempt":
        event_id = coverage_need_event_id(
            args.coverage_need_id,
            "SEARCH_ATTEMPT",
            args.actor_ref,
            args.reason,
        )
        print(
            json.dumps(
                store.record_coverage_need_attempt(
                    coverage_need_id=args.coverage_need_id,
                    event_id=event_id,
                    actor_ref=args.actor_ref,
                    reason=args.reason,
                ),
                sort_keys=True,
            )
        )
        return 0
    if args.command == "satisfy":
        event_id = coverage_need_event_id(
            args.coverage_need_id,
            "SATISFIED",
            args.content_id or "",
            args.evidence_id or "",
            args.source_profile_id or "",
        )
        state = store.satisfy_coverage_need(
            coverage_need_id=args.coverage_need_id,
            event_id=event_id,
            content_id=args.content_id,
            evidence_id=args.evidence_id,
            source_profile_id=args.source_profile_id,
            actor_ref=args.actor_ref,
            reason=args.reason,
        )
        print(json.dumps({"coverage_need_id": args.coverage_need_id, "state": state}, sort_keys=True))
        return 0 if state in {"SATISFIED", "EXISTING"} else 2
    if args.command == "block":
        event_id = coverage_need_event_id(
            args.coverage_need_id,
            "BLOCKED",
            args.blocker_code,
        )
        state = store.block_coverage_need(
            coverage_need_id=args.coverage_need_id,
            event_id=event_id,
            blocker_code=args.blocker_code,
            actor_ref=args.actor_ref,
            reason=args.reason,
        )
        print(json.dumps({"coverage_need_id": args.coverage_need_id, "state": state}, sort_keys=True))
        return 0 if state in {"BLOCKED", "EXISTING"} else 2
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
