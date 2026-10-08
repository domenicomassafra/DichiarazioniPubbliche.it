"""Shared strict Discovery Hit lineage query for private Capture authority.

PostgreSQL foreign keys alone do not prove that hit/attempt/query/run rows
belong to the same manifest or that a succeeded attempt generated a hit.
All mandatory relationships and the source-family/adapter scope must agree.
Do not loosen this to a generic "accepted hit exists" count.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_SQL_EXPRESSION = re.compile(
    r"^(?:collection|member|content)\.(?:id|collection_id|content_id|canonical_url)$"
)


def valid_discovery_hit_groups_sql(
    *, collection_id_sql: str, content_id_sql: str, canonical_url_sql: str
) -> str:
    """SQL grouped by source family; accepts only fixed, validated SQL identifiers."""
    if any(not _SQL_EXPRESSION.fullmatch(value) for value in
           (collection_id_sql, content_id_sql, canonical_url_sql)):
        raise ValueError("DISCOVERY_PROVENANCE_SQL_EXPRESSION_INVALID")
    return f"""
        SELECT hit.source_family, count(*)::integer AS hit_count
        FROM research_discovery_hit hit
        JOIN research_discovery_run run ON run.id=hit.run_id
        JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
        JOIN research_discovery_attempt attempt
          ON attempt.id=hit.attempt_id
         AND attempt.run_id=run.id
         AND attempt.query_id=hit.query_id
         AND attempt.status='HEALTHY'
        JOIN research_discovery_query discovery_query
          ON discovery_query.id=hit.query_id
         AND discovery_query.id=attempt.query_id
         AND discovery_query.manifest_id=manifest.id
         AND discovery_query.source_families ? hit.source_family
         AND discovery_query.adapter_ids ? attempt.adapter_id
        WHERE hit.content_id={content_id_sql}
          AND hit.canonical_url={canonical_url_sql}
          AND hit.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
          AND run.status IN ('COMPLETED','PARTIAL')
          AND manifest.collection_id={collection_id_sql}
          AND manifest.status='ACTIVE'
          AND manifest.manifest_sha256=run.manifest_sha256
          AND manifest.source_families ? hit.source_family
        GROUP BY hit.source_family
    """.strip()


def accepted_discovery_family_counts(row: Mapping[str, Any]) -> dict[str, int]:
    """Validate the materialized DB group list; no hand-authored approval flags."""
    raw = row.get("accepted_discovery_groups")
    if not isinstance(raw, list) or len(raw) > 128:
        raise ValueError("DISCOVERY_PROVENANCE_GROUPS_INVALID")
    counts: dict[str, int] = {}
    for entry in raw:
        if not isinstance(entry, Mapping) or set(entry) != {"source_family", "hit_count"}:
            raise ValueError("DISCOVERY_PROVENANCE_GROUP_INVALID")
        family, count = entry["source_family"], entry["hit_count"]
        if (not isinstance(family, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", family)
                or family in counts or type(count) is not int or not 0 < count <= 100_000):
            raise ValueError("DISCOVERY_PROVENANCE_FAMILY_OR_COUNT_INVALID")
        counts[family] = count
    return counts
