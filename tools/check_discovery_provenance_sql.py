#!/usr/bin/env python3
"""DP-214/209 strict Discovery provenance canary, rollback-only PostgreSQL.

All invented fixture rows exist solely as pg_temp tables inside one
transaction rolled back at the end. No production row is written or promoted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore  # noqa: E402
from dichiarazioni_pubbliche.discovery_provenance import valid_discovery_hit_groups_sql  # noqa: E402
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402


def ephemeral_provenance_sql() -> str:
    """One session, pg_temp shadow tables only, always end in ROLLBACK."""
    groups = valid_discovery_hit_groups_sql(
        collection_id_sql="collection.id",
        content_id_sql="content.id",
        canonical_url_sql="content.canonical_url",
    )
    probe = f"""
    SELECT COALESCE(sum(grouped.hit_count), 0)::integer AS matches,
           COALESCE(string_agg(grouped.source_family, ',' ORDER BY grouped.source_family), '') AS families
    FROM ({groups}) grouped
    """
    def query(label: str) -> str:
        return f"""
        SELECT '{label}|' || provenance.matches::text || '|' || provenance.families
        FROM collection CROSS JOIN content
        CROSS JOIN LATERAL ({probe}) provenance;
        """

    return f"""
    BEGIN;
    SET LOCAL search_path TO pg_temp, public;
    CREATE TEMP TABLE collection (id text);
    CREATE TEMP TABLE content (id text, canonical_url text);
    CREATE TEMP TABLE research_discovery_manifest (
        id text, collection_id text, manifest_sha256 text,
        source_families jsonb, status text
    );
    CREATE TEMP TABLE research_discovery_run (
        id text, manifest_id text, manifest_sha256 text, status text
    );
    CREATE TEMP TABLE research_discovery_query (
        id text, manifest_id text, source_families jsonb, adapter_ids jsonb
    );
    CREATE TEMP TABLE research_discovery_attempt (
        id text, run_id text, query_id text, status text, adapter_id text
    );
    CREATE TEMP TABLE research_discovery_hit (
        id text, content_id text, canonical_url text,
        source_family text, disposition text, run_id text,
        query_id text, attempt_id text
    );
    INSERT INTO collection VALUES ('research:canary');
    INSERT INTO content VALUES ('content:canary', 'https://example.test/canary');
    INSERT INTO research_discovery_manifest VALUES
      ('manifest:good', 'research:canary', repeat('a', 64), '["REPORTING"]', 'ACTIVE'),
      ('manifest:other', 'research:canary', repeat('b', 64), '["REPORTING"]', 'ACTIVE');
    INSERT INTO research_discovery_run VALUES
      ('run:good', 'manifest:good', repeat('a', 64), 'COMPLETED'),
      ('run:other', 'manifest:other', repeat('b', 64), 'COMPLETED');
    INSERT INTO research_discovery_query VALUES
      ('query:good', 'manifest:good', '["REPORTING"]', '["approved", "alternate"]'),
      ('query:other', 'manifest:other', '["REPORTING"]', '["approved"]');
    INSERT INTO research_discovery_attempt VALUES
      ('attempt:good', 'run:good', 'query:good', 'HEALTHY', 'approved'),
      ('attempt:failed', 'run:good', 'query:good', 'FAILED', 'alternate'),
      ('attempt:wrong-query', 'run:good', 'query:other', 'HEALTHY', 'approved'),
      ('attempt:wrong-run', 'run:other', 'query:good', 'HEALTHY', 'approved'),
      ('attempt:wrong-adapter', 'run:good', 'query:good', 'HEALTHY', 'rogue');
    INSERT INTO research_discovery_hit VALUES
      ('hit:good', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'NEW_CONTENT', 'run:good', 'query:good', 'attempt:good'),
      ('hit:failed-attempt', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'NEW_CONTENT', 'run:good', 'query:good', 'attempt:failed'),
      ('hit:wrong-query', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'NEW_CONTENT', 'run:good', 'query:other', 'attempt:wrong-query'),
      ('hit:wrong-run', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'NEW_CONTENT', 'run:good', 'query:good', 'attempt:wrong-run'),
      ('hit:wrong-adapter', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'NEW_CONTENT', 'run:good', 'query:good', 'attempt:wrong-adapter'),
      ('hit:wrong-family', 'content:canary', 'https://example.test/canary',
        'VIDEO_PODCAST', 'NEW_CONTENT', 'run:good', 'query:good', 'attempt:good'),
      ('hit:rejected', 'content:canary', 'https://example.test/canary',
        'REPORTING', 'REJECTED_POLICY', 'run:good', 'query:good', 'attempt:good');
    {query('valid_only')}
    UPDATE research_discovery_attempt SET status='BLOCKED' WHERE id='attempt:good';
    {query('revoked_attempt')}
    UPDATE research_discovery_attempt SET status='HEALTHY' WHERE id='attempt:good';
    UPDATE research_discovery_manifest SET status='PAUSED' WHERE id='manifest:good';
    {query('paused_manifest')}
    UPDATE research_discovery_manifest SET status='ACTIVE' WHERE id='manifest:good';
    UPDATE research_discovery_run SET manifest_sha256=repeat('f', 64)
      WHERE id='run:good';
    {query('stale_run_digest')}
    UPDATE research_discovery_run SET manifest_sha256=repeat('a', 64),
      status='BLOCKED' WHERE id='run:good';
    {query('blocked_run')}
    ROLLBACK;
    """


_EXPECTED = {
    "valid_only": (1, "REPORTING"),
    "revoked_attempt": (0, ""),
    "paused_manifest": (0, ""),
    "stale_run_digest": (0, ""),
    "blocked_run": (0, ""),
}


def check_receipts(stdout: str) -> dict[str, object]:
    observed = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) != 3 or parts[0] not in _EXPECTED or parts[0] in observed:
            raise RuntimeError("DISCOVERY_SQL_CANARY_RECEIPT_INVALID")
        if not parts[1].isdigit():
            raise RuntimeError("DISCOVERY_SQL_CANARY_COUNT_INVALID")
        observed[parts[0]] = (int(parts[1]), parts[2])
    if observed != _EXPECTED:
        raise RuntimeError("DISCOVERY_SQL_CANARY_LINEAGE_BYPASS")
    return {
        "status": "PASS_ROLLBACK_ONLY",
        "checks": len(observed),
        "provenance_lineage_checked": True,
        "publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    args = parser.parse_args(argv)
    capture = CapturePipelineStore(database_url=args.database_url)
    before = capture.read_private_capture_safety_counts()
    result = check_receipts(PsqlRuntime(database_url=args.database_url).run(ephemeral_provenance_sql()))
    after = capture.read_private_capture_safety_counts()
    if before != after:
        raise RuntimeError("DISCOVERY_SQL_CANARY_PROTECTED_COUNTS_CHANGED")
    print(json.dumps({**result, "protected_counts_unchanged": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
