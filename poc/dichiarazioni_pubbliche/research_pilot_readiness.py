"""DP-214/215 private pilot bottleneck report, strictly read-only.

Reports DB-observed stage counts and missing prerequisites; a reported rights
row is NOT equivalent to reviewed source authority, and a Content row is NOT
an accepted pilot item. Never emits source bodies, titles, URLs or PII.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.garlasco_tracer import REQUIRED_SOURCE_FAMILIES
from dichiarazioni_pubbliche.discovery_provenance import valid_discovery_hit_groups_sql

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

PILOT_TARGET = 100
VERSION = "research-pilot-readiness-v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_BOUNDED_MEMBERS = 2000

# A single SELECT for each collection: all counts come from the same SQL
# statement snapshot. No text/URLs are returned, even in private reports.
_VALID_DISCOVERY_GROUPS_SQL = valid_discovery_hit_groups_sql(
    collection_id_sql="member.collection_id",
    content_id_sql="content.id",
    canonical_url_sql="content.canonical_url",
)

_MEMBER_READ_SQL = f"""
SELECT json_build_object(
    'content_id', member.content_id,
    'membership_status', member.status,
    'capture_authorized', member.metadata->'capture_authorized',
    'content_rights_status', content.rights_status,
    'accepted_discovery_hits', provenance.hit_count,
    'observed_accepted_source_families', provenance.source_families,
    'current_rights_records', (
        SELECT count(*) FROM private_source_rights_record rights
        WHERE rights.content_id=content.id
          AND rights.locator_kind='URL'
          AND rights.locator_value=content.canonical_url
          AND NOT EXISTS (
              SELECT 1 FROM private_source_rights_record child
              WHERE child.supersedes_id=rights.id
          )
    ),
    'current_relevance_records', (
        SELECT count(*) FROM privacy_ingestion_relevance_authority relevance
        WHERE relevance.content_ref=content.id
          AND NOT EXISTS (
              SELECT 1 FROM privacy_ingestion_relevance_authority child
              WHERE child.supersedes_authority_id=relevance.authority_id
          )
    ),
    'captures', (SELECT count(*) FROM content_capture capture WHERE capture.content_id=content.id),
    'captured_with_body', (
        SELECT count(*) FROM content_capture capture
        WHERE capture.content_id=content.id
          AND capture.status='CAPTURED'
          AND capture.body_ref IS NOT NULL
          AND capture.rights_status='CLEARED'
          AND capture.hold_status='NONE'
    ),
    'passages', (SELECT count(*) FROM passage p WHERE p.content_id=content.id),
    'statement_candidates', (SELECT count(*) FROM statement_candidate s WHERE s.content_id=content.id),
    'claim_candidates', (SELECT count(*) FROM claim_candidate c WHERE c.content_id=content.id)
)::text
FROM research_collection_content member
JOIN content_item content ON content.id=member.content_id
CROSS JOIN LATERAL (
    SELECT COALESCE(sum(grouped.hit_count), 0)::integer AS hit_count,
        COALESCE(json_agg(grouped.source_family ORDER BY grouped.source_family), '[]'::json)
            AS source_families
    FROM ({_VALID_DISCOVERY_GROUPS_SQL}) grouped
) provenance
WHERE member.collection_id=:'collection_id'
ORDER BY member.content_id
LIMIT 2001;
""".strip()

_SUMMARY_READ_SQL = r"""
SELECT json_build_object(
    'collection_id', collection.id,
    'collection_status', collection.status,
    'members_total', (SELECT count(*) FROM research_collection_content WHERE collection_id=collection.id),
    'persisted_unlinked_discovery_hits', (
        SELECT count(*) FROM research_discovery_hit hit
        JOIN research_discovery_run run ON run.id=hit.run_id
        JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
        WHERE manifest.collection_id=collection.id
          AND hit.content_id IS NULL
          AND run.status IN ('COMPLETED','PARTIAL')
    ),
    'discovery_runs', (
        SELECT count(*) FROM research_discovery_run run
        JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
        WHERE manifest.collection_id=collection.id
    ),
    'baseline_garlasco_claims', (
        SELECT count(*) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%'
    )
)::text
FROM research_collection collection WHERE collection.id=:'collection_id';
""".strip()


class ReadinessReportError(ValueError):
    pass


class ResearchPilotReadinessStore(PsqlRuntime):
    def read_collection(self, collection_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not isinstance(collection_id, str) or not _ID.fullmatch(collection_id):
            raise ReadinessReportError("PILOT_COLLECTION_ID_INVALID")
        raw = self.run(_SUMMARY_READ_SQL, collection_id=collection_id)
        if not raw:
            raise ReadinessReportError("PILOT_COLLECTION_NOT_FOUND")
        summary = json.loads(raw)
        raw_members = self.run(_MEMBER_READ_SQL, collection_id=collection_id)
        members = [json.loads(line) for line in raw_members.splitlines() if line.strip()]
        if len(members) > _BOUNDED_MEMBERS or len(members) != int(summary["members_total"]):
            raise ReadinessReportError("PILOT_SNAPSHOT_MEMBERSHIP_DRIFT_OR_TOO_LARGE")
        return summary, members


def _require_count(row: Mapping[str, Any], key: str) -> int:
    value = row.get(key)
    if type(value) is not int or value < 0:
        raise ReadinessReportError(f"PILOT_{key.upper()}_COUNT_INVALID")
    return value


def summarize_readiness(
    summary: Mapping[str, Any],
    members: Sequence[Mapping[str, Any]],
    *,
    include_ids: bool = False,
) -> dict[str, Any]:
    """Deterministic, bounded, honest inventory. Never grants eligibility."""
    collection_id = summary.get("collection_id")
    if not isinstance(collection_id, str) or not _ID.fullmatch(collection_id):
        raise ReadinessReportError("PILOT_COLLECTION_ID_INVALID")
    collection_status = summary.get("collection_status")
    if collection_status not in {"ACTIVE", "PAUSED", "ARCHIVED"}:
        raise ReadinessReportError("PILOT_COLLECTION_STATUS_INVALID")
    if len(members) > _BOUNDED_MEMBERS or _require_count(summary, "members_total") != len(members):
        raise ReadinessReportError("PILOT_MEMBERS_INCOMPLETE")
    lead_count = _require_count(summary, "persisted_unlinked_discovery_hits")
    runs_count = _require_count(summary, "discovery_runs")
    claim_count = _require_count(summary, "baseline_garlasco_claims")
    blockers = Counter()
    stages = Counter()
    observed_families: set[str] = set()
    rows = []
    ids = set()
    for member in members:
        content_id = member.get("content_id")
        if not isinstance(content_id, str) or not _ID.fullmatch(content_id) or content_id in ids:
            raise ReadinessReportError("PILOT_CONTENT_ID_INVALID_OR_DUPLICATE")
        ids.add(content_id)
        membership_status = member.get("membership_status")
        if membership_status not in {"INCLUDED", "REJECTED", "REMOVED"}:
            raise ReadinessReportError("PILOT_MEMBERSHIP_STATUS_INVALID")
        rights_status = member.get("content_rights_status")
        if not isinstance(rights_status, str) or not rights_status:
            raise ReadinessReportError("PILOT_CONTENT_RIGHTS_INVALID")
        checked = tuple(
            _require_count(member, name) for name in (
                "accepted_discovery_hits", "current_rights_records",
                "current_relevance_records", "captures", "captured_with_body",
                "passages", "statement_candidates", "claim_candidates",
            )
        )
        discovery, rights_records, relevance, captures, ready_captures, passages, statements, claims = checked
        source_families = member.get("observed_accepted_source_families")
        if (not isinstance(source_families, list)
                or any(not isinstance(family, str) or not family or len(family) > 128
                       for family in source_families)
                or (discovery == 0 and source_families)):
            raise ReadinessReportError("PILOT_SOURCE_FAMILY_PROVENANCE_INVALID")
        codes = []
        if membership_status != "INCLUDED":
            codes.append("MEMBERSHIP_NOT_INCLUDED")
        else:
            stages["included"] += 1
            observed_families.update(source_families)
            if collection_status != "ACTIVE":
                codes.append("COLLECTION_NOT_ACTIVE")
            if member.get("capture_authorized") is not True:
                codes.append("CAPTURE_NOT_AUTHORIZED")
            if discovery == 0:
                codes.append("ACCEPTED_DISCOVERY_MISSING")
            if rights_status != "CLEARED":
                codes.append("CONTENT_RIGHTS_NOT_CLEARED")
            if rights_records == 0:
                codes.append("SOURCE_RIGHTS_RECORD_MISSING")
            if relevance == 0:
                codes.append("PRIVACY_RELEVANCE_RECORD_MISSING")
            if captures == 0:
                codes.append("CAPTURE_MISSING")
            elif ready_captures == 0:
                codes.append("CAPTURE_NOT_READY_OR_HELD")
            if passages == 0:
                codes.append("PASSAGE_MISSING")
            if statements == 0:
                codes.append("STATEMENT_CANDIDATES_MISSING")
            if claims == 0:
                codes.append("CLAIM_CANDIDATES_MISSING")
            for name, count in zip(
                ("discovered", "rights_recorded", "relevance_recorded",
                 "captured", "capture_body_ready", "passaged",
                 "statement_candidate", "claim_candidate"),
                checked,
            ):
                if count > 0:
                    stages[name] += 1
        for code in codes:
            blockers[code] += 1
        if include_ids:
            rows.append({
                "content_id": content_id,
                "membership_status": membership_status,
                "blockers": codes,
                # Presence is not current qualified authorization.
                "pipeline_counts": {
                    "accepted_discovery_hits": discovery,
                    "captures": captures,
                    "passages": passages,
                    "statement_candidates": statements,
                    "claim_candidates": claims,
                },
            })
    included = stages["included"]
    digest_material = {
        "summary": dict(summary),
        "members": sorted((dict(row) for row in members), key=lambda row: row["content_id"]),
    }
    sha256 = hashlib.sha256(
        json.dumps(digest_material, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "version": VERSION,
        "collection_id": collection_id,
        "status": "NO_GO_READ_ONLY",
        "collection_status": collection_status,
        "target_items": PILOT_TARGET,
        "included_items": included,
        "remaining_to_target": max(0, PILOT_TARGET - included),
        "target_proven": False,  # counts do not prove corpus acceptance
        "persisted_unlinked_discovery_hits": lead_count,
        "discovery_runs": runs_count,
        "baseline_garlasco_claims": claim_count,
        "baseline_claim_target": 30,
        "baseline_claim_count_matches": claim_count == 30,
        "observed_persisted_source_families": sorted(observed_families),
        "missing_required_source_families": sorted(REQUIRED_SOURCE_FAMILIES - observed_families),
        "stage_presence_counts": dict(sorted(stages.items())),
        "missing_prerequisite_counts": dict(sorted(blockers.items())),
        "qualified_rights_verified": False,
        "model_provider_verified": False,
        "publication_authorized": False,
        "snapshot_sha256": sha256,
        **({"members": rows} if include_ids else {}),
    }


def load_unreviewed_public_leads(path: Path) -> dict[str, Any]:
    """Count candidate-only file hints separately; never treat as persisted Discovery."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessReportError("PILOT_LEADS_FILE_UNREADABLE") from exc
    if not isinstance(raw, dict) or raw.get("version") != "garlasco-public-discovery-leads-v1" or raw.get("state") != "UNREVIEWED_CANDIDATES_ONLY":
        raise ReadinessReportError("PILOT_LEADS_CONTRACT_INVALID")
    candidates = raw.get("candidates")
    locators = raw.get("source_locator_only")
    if not isinstance(candidates, list) or not isinstance(locators, list) or len(candidates) > 200 or len(locators) > 50:
        raise ReadinessReportError("PILOT_LEADS_BOUNDS_INVALID")
    seen_ids: set[str] = set()
    for source, items in (("candidate", candidates), ("locator", locators)):
        for item in items:
            if not isinstance(item, dict):
                raise ReadinessReportError("PILOT_LEADS_ITEM_INVALID")
            lead_id = item.get("id")
            if not isinstance(lead_id, str) or not _ID.fullmatch(lead_id) or lead_id in seen_ids:
                raise ReadinessReportError("PILOT_LEADS_ID_INVALID")
            seen_ids.add(lead_id)
            try:
                url = item.get("url")
                if canonical_content_url(url) != url:
                    raise ValueError
            except ValueError as exc:
                raise ReadinessReportError("PILOT_LEADS_URL_INVALID") from exc
            if source == "candidate" and (
                item.get("candidate_only") is not True
                or item.get("capture_authorized") is not False
                or item.get("rights_status") != "UNKNOWN"
                or item.get("provenance_status") != "UNVERIFIED_IN_DATABASE"
            ):
                raise ReadinessReportError("PILOT_LEADS_NOT_UNREVIEWED")
            if source == "locator" and item.get("count_as_logical_item") is not False:
                raise ReadinessReportError("PILOT_LEADS_LOCATOR_NOT_EXCLUDED")
    return {
        "unreviewed_file_candidates": len(candidates),
        "source_locator_only": len(locators),
        "file_leads_counted_in_pilot": 0,
        "file_candidates_verified_in_postgres": False,
        "file_candidates_capture_authorized": False,
    }
