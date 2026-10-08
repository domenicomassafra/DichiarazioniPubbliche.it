#!/usr/bin/env python3
"""DP-417: PostgreSQL pg_temp-only Discovery inspection canary, no live mutations."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore  # noqa: E402
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402
from dichiarazioni_pubbliche.studio_discovery_detail import present_discovery_detail  # noqa: E402
from dichiarazioni_pubbliche.studio_operator_queues import _DISCOVERY_DETAIL_SQL  # noqa: E402


def synthetic_inspection_sql() -> str:
    """One eligible fixture and one revoked-attempt state inside a rollback."""
    return """
BEGIN;
SET LOCAL search_path TO pg_temp, public;
CREATE TEMP TABLE content_item (id text, canonical_url text, rights_status text);
CREATE TEMP TABLE research_collection (id text, status text);
CREATE TEMP TABLE research_collection_content (
    collection_id text, content_id text, status text, metadata jsonb);
CREATE TEMP TABLE research_discovery_manifest (
    id text, collection_id text, manifest_sha256 text, source_families jsonb, status text);
CREATE TEMP TABLE research_discovery_run (
    id text, manifest_id text, manifest_sha256 text, status text);
CREATE TEMP TABLE research_discovery_query (
    id text, manifest_id text, source_families jsonb, adapter_ids jsonb);
CREATE TEMP TABLE research_discovery_attempt (
    id text, run_id text, query_id text, status text, adapter_id text);
CREATE TEMP TABLE research_discovery_hit (
    id text, run_id text, attempt_id text, query_id text, content_id text,
    canonical_url text, disposition text, source_family text, reason_code text);
INSERT INTO content_item VALUES ('content:fixture','https://example.test/only-test','CLEARED');
INSERT INTO research_collection VALUES ('research:fixture','ACTIVE');
INSERT INTO research_collection_content VALUES
    ('research:fixture','content:fixture','INCLUDED','{"capture_authorized":true}');
INSERT INTO research_discovery_manifest VALUES
    ('manifest:fixture','research:fixture',repeat('a',64),'["REPORTING"]','ACTIVE');
INSERT INTO research_discovery_run VALUES
    ('run:fixture','manifest:fixture',repeat('a',64),'COMPLETED');
INSERT INTO research_discovery_query VALUES
    ('query:fixture','manifest:fixture','["REPORTING"]','["fixture-adapter"]');
INSERT INTO research_discovery_attempt VALUES
    ('attempt:fixture','run:fixture','query:fixture','HEALTHY','fixture-adapter');
INSERT INTO research_discovery_hit VALUES
    ('hit:fixture','run:fixture','attempt:fixture','query:fixture','content:fixture',
     'https://example.test/only-test','NEW_CONTENT','REPORTING',NULL);
""" + _DISCOVERY_DETAIL_SQL + """
UPDATE research_discovery_attempt SET status='FAILED';
""" + _DISCOVERY_DETAIL_SQL + """
ROLLBACK;
"""


def evaluate_synthetic_rows(raw: str) -> dict[str, object]:
    results = [present_discovery_detail(json.loads(line)) for line in raw.splitlines()
               if line.strip()]
    if len(results) != 2:
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_COUNT_INVALID")
    if results[0]["lineage_blockers"] or not results[0]["lineage_checks_passed"]:
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_POSITIVE_REJECTED")
    if "DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE" not in results[0]["blockers"]:
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_FALSE_REVIEW_APPROVAL")
    if "DISCOVERY_ATTEMPT_NOT_HEALTHY" not in results[1]["blockers"]:
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_REVOCATION_NOT_DETECTED")
    if any(item["publication_authority"] or item["triage_action_authorized"]
           for item in results):
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_UNSAFE_AUTHORITY")
    return {
        "status": "PASS_ROLLBACK_ONLY",
        "positive_synthetic_inspection": 1,
        "failed_attempt_blocker_detected": True,
        "private_only": True,
        "publication_authorized": False,
    }


def main() -> int:
    database = os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    counts = CapturePipelineStore(database_url=database)
    before = counts.read_private_capture_safety_counts()
    raw = PsqlRuntime(database_url=database).run(
        synthetic_inspection_sql(), hit_id="hit:fixture", collection_id="research:fixture"
    )
    result = evaluate_synthetic_rows(raw)
    if before != counts.read_private_capture_safety_counts():
        raise RuntimeError("STUDIO_DISCOVERY_CANARY_PRODUCTION_COUNTS_CHANGED")
    print(json.dumps({**result, "protected_counts_unchanged": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
