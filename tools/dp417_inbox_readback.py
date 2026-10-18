#!/usr/bin/env python3
"""Private DP-417 readback: count *persisted* Discovery runs/Hits, never fixtures.

Read-only and metadata-only. An empty queue is explicitly a missing canary,
not proof that a discovery workflow succeeded or that a source is covered.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402


READBACK_SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object(
  'collections', (SELECT count(*) FROM research_collection),
  'manifests', (SELECT count(*) FROM research_discovery_manifest),
  'runs', (SELECT count(*) FROM research_discovery_run),
  'completed_runs', (SELECT count(*) FROM research_discovery_run
                     WHERE status = 'COMPLETED'),
  'blocked_runs', (SELECT count(*) FROM research_discovery_run
                   WHERE status IN ('BLOCKED', 'FAILED')),
  'incomplete_runs', (SELECT count(*) FROM research_discovery_run
                      WHERE status IN ('RUNNING', 'PARTIAL')),
  'hits', (SELECT count(*) FROM research_discovery_hit),
  'annotated_hits', (SELECT count(DISTINCT hit_id)
                     FROM research_discovery_triage_decision),
  'invalid_lineage_hits', (SELECT count(*)
    FROM research_discovery_hit hit
    LEFT JOIN research_discovery_run run ON run.id = hit.run_id
    LEFT JOIN research_discovery_manifest manifest ON manifest.id = run.manifest_id
    LEFT JOIN research_discovery_query query ON query.id = hit.query_id
    LEFT JOIN research_discovery_attempt attempt ON attempt.id = hit.attempt_id
    WHERE run.id IS NULL OR manifest.id IS NULL OR query.id IS NULL
       OR attempt.id IS NULL
       OR attempt.run_id IS DISTINCT FROM run.id
       OR attempt.query_id IS DISTINCT FROM hit.query_id
       OR query.manifest_id IS DISTINCT FROM manifest.id
       OR run.manifest_sha256 IS DISTINCT FROM manifest.manifest_sha256
       OR EXISTS (SELECT 1 FROM research_discovery_triage_decision decision
                  WHERE decision.hit_id = hit.id
                    AND decision.collection_id IS DISTINCT FROM manifest.collection_id))
)::text;
COMMIT;
"""

_COUNTS = (
    "collections", "manifests", "runs", "completed_runs", "blocked_runs",
    "incomplete_runs",
    "hits", "annotated_hits", "invalid_lineage_hits",
)


def validate_readback(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict) or set(raw) != set(_COUNTS):
        raise ValueError("DP417_READBACK_SCHEMA_INVALID")
    if any(type(raw[key]) is not int or raw[key] < 0 for key in _COUNTS):
        raise ValueError("DP417_READBACK_COUNT_INVALID")
    # The schema defines exactly these five Run statuses. Unknown/new states
    # must not be omitted from the operational blocker totals.
    if (raw["completed_runs"] + raw["blocked_runs"] + raw["incomplete_runs"] != raw["runs"]
            or raw["annotated_hits"] > raw["hits"]
            or raw["invalid_lineage_hits"] > raw["hits"]):
        raise ValueError("DP417_READBACK_CONTRADICTION")
    return raw


def summarize(counts: dict[str, int]) -> dict[str, object]:
    counts = validate_readback(counts)
    blockers = []
    if not counts["runs"]:
        blockers.append("NO_PERSISTED_DISCOVERY_RUN")
    if not counts["hits"]:
        blockers.append("NO_PERSISTED_DISCOVERY_HIT")
    if counts["blocked_runs"]:
        blockers.append("BLOCKED_OR_FAILED_DISCOVERY_RUN")
    if counts["incomplete_runs"]:
        blockers.append("INCOMPLETE_DISCOVERY_RUN")
    if counts["invalid_lineage_hits"]:
        blockers.append("INVALID_DISCOVERY_LINEAGE")
    return {
        "contract_version": "dp417-private-inbox-readback-v1",
        "private_only": True,
        "read_only": True,
        "runtime_acceptance_proven": False,
        "counts": counts,
        "blockers": blockers,
        "note": "Counts do not attest source rights, actionable review, or public publication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    args = parser.parse_args()
    runtime = PsqlRuntime(args.database_url)
    try:
        counts = validate_readback(json.loads(runtime.run(READBACK_SQL)))
    except (ValueError, RuntimeError, json.JSONDecodeError):
        print("DP417_READBACK_UNAVAILABLE", file=sys.stderr)
        return 2
    print(json.dumps(summarize(counts), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
