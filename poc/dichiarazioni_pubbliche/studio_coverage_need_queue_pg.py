"""Read-only, Collection-scoped DP417 Coverage Need queue.

Uses persisted canonical Coverage Need / event rows rather than fabricated
progress counters. No claim about source rights or triage authority is made.
"""
from __future__ import annotations

import json
import re
from typing import Any

from dichiarazioni_pubbliche.studio_discovery_triage_contract import _validated_ref

CONTRACT_VERSION = "studio-coverage-need-queue-pg-v1"
_ID = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z", re.ASCII)
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_NEED_TYPES = frozenset({
    "PRIMARY_SOURCE", "ORIGINAL_MEDIA", "OFFICIAL_RECORD", "EARLIER_VERSION",
    "INDEPENDENT_SOURCE", "TEMPORAL_GAP", "ATTRIBUTION_GAP", "OTHER",
})
_REQUIREMENT_KINDS = frozenset({
    "ROLE_ANY", "FIELD_MATCH", "AUTHORITY_SCOPE", "TEMPORAL_CUTOFF",
    "MIN_INDEPENDENT_LINEAGES", "MANUAL_REVIEW", "OTHER",
})
_FIELDS = frozenset({
    "need_id", "need_type", "requirement_kind", "status", "attempt_count",
    "max_attempts", "blocker_code", "event_id", "event_count",
    "atomic_claim_id", "claim_candidate_id", "source_intelligence_assessment_id",
})

_SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH scope AS (
  SELECT id,status FROM research_collection WHERE id=:'collection_id'
), candidates AS (
  SELECT need.id AS need_id, need.need_type, need.requirement_kind,
         need.status, need.attempt_count, need.max_attempts, need.blocker_code,
         need.atomic_claim_id, need.claim_candidate_id,
         need.source_intelligence_assessment_id,
         (SELECT e.id FROM coverage_need_event e WHERE e.coverage_need_id=need.id
          ORDER BY e.created_at DESC,e.id DESC LIMIT 1) AS event_id,
         (SELECT count(*)::integer FROM coverage_need_event e
          WHERE e.coverage_need_id=need.id) AS event_count
  FROM scope JOIN coverage_need need ON need.collection_id=scope.id
  WHERE need.status IN ('OPEN','SEARCHING','BLOCKED')
), fingerprint AS (
  SELECT encode(sha256(convert_to(jsonb_build_object(
    'collection_status',scope.status,
    'rows', (SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.need_id),'[]'::jsonb)
             FROM candidates c)
  )::text,'UTF8')),'hex') AS snapshot_sha256
  FROM scope
), selected AS (
  SELECT * FROM candidates WHERE need_id>:'after_id'
  ORDER BY need_id LIMIT (:'limit'::integer + 1)
)
SELECT json_build_object(
  'collection_id',scope.id,'collection_status',scope.status,
  'snapshot_sha256',fingerprint.snapshot_sha256,
  'snapshot_valid', (:'expected_snapshot_sha256'='' OR
                     fingerprint.snapshot_sha256=:'expected_snapshot_sha256'),
  'cursor_valid', (:'after_id'='' OR EXISTS(
     SELECT 1 FROM candidates c WHERE c.need_id=:'after_id')),
  'rows',(SELECT coalesce(json_agg(row_to_json(s) ORDER BY s.need_id),'[]'::json)
          FROM selected s)
)::text FROM scope CROSS JOIN fingerprint;
COMMIT;
""".strip()


def _valid_id(value: object, *, optional: bool = False) -> bool:
    return (optional and value is None) or (
        isinstance(value, str) and bool(_ID.fullmatch(value))
    )


def _validated_packet(document: dict[str, Any], *,
                      collection_id: str, after_id: str, limit: int) -> dict[str, object]:
    if document.get("snapshot_valid") is False:
        raise ValueError("STUDIO_COVERAGE_NEED_SNAPSHOT_STALE")
    if (
        set(document) != {
            "collection_id", "collection_status", "snapshot_sha256",
            "snapshot_valid", "cursor_valid", "rows",
        }
        or document["collection_id"] != collection_id
        or document["collection_status"] not in {"ACTIVE", "PAUSED", "ARCHIVED"}
        or type(document["snapshot_valid"]) is not bool
        or document["cursor_valid"] is not True
        or not isinstance(document["snapshot_sha256"], str)
        or not _SHA.fullmatch(document["snapshot_sha256"])
    ):
        raise ValueError("STUDIO_COVERAGE_NEED_SCOPE_INVALID")
    raw_rows = document["rows"]
    if not isinstance(raw_rows, list) or len(raw_rows) > limit + 1:
        raise ValueError("STUDIO_COVERAGE_NEED_PAGE_INVALID")
    rows: list[dict[str, object]] = []
    last = after_id
    for raw in raw_rows:
        if not isinstance(raw, dict) or set(raw) != _FIELDS:
            raise ValueError("STUDIO_COVERAGE_NEED_ROW_INVALID")
        if (
            not _valid_id(raw["need_id"]) or raw["need_id"] <= last
            or raw["need_type"] not in _NEED_TYPES
            or raw["requirement_kind"] not in _REQUIREMENT_KINDS
            or raw["status"] not in {"OPEN", "SEARCHING", "BLOCKED"}
            or type(raw["attempt_count"]) is not int
            or type(raw["max_attempts"]) is not int
            or not 0 <= raw["attempt_count"] <= raw["max_attempts"] <= 10
            or raw["max_attempts"] < 1
            or not _valid_id(raw["event_id"], optional=True)
            or type(raw["event_count"]) is not int or raw["event_count"] < 0
            or (raw["event_count"] == 0) != (raw["event_id"] is None)
            or not _valid_id(raw["atomic_claim_id"], optional=True)
            or not _valid_id(raw["claim_candidate_id"], optional=True)
            or not _valid_id(raw["source_intelligence_assessment_id"], optional=True)
            or (raw["blocker_code"] is not None
                and (not isinstance(raw["blocker_code"], str)
                     or not _CODE.fullmatch(raw["blocker_code"])))
            or (raw["status"] == "BLOCKED" and raw["blocker_code"] is None)
        ):
            raise ValueError("STUDIO_COVERAGE_NEED_ROW_INVALID")
        last = raw["need_id"]
        blockers = []
        if document["collection_status"] != "ACTIVE":
            blockers.append("COLLECTION_NOT_ACTIVE")
        if raw["status"] == "BLOCKED":
            blockers.append("SOURCE_" + raw["blocker_code"])
        elif raw["status"] == "SEARCHING":
            blockers.append("SEARCH_IN_PROGRESS")
        else:
            blockers.append("NEED_OPEN")
        if raw["attempt_count"] >= raw["max_attempts"]:
            blockers.append("ATTEMPT_CAP_REACHED")
        blockers.extend((
            "SOURCE_RIGHTS_NOT_ATTESTED",
            "EVIDENCE_REVIEW_NOT_ATTESTED",
        ))
        rows.append({
            "need_id": raw["need_id"], "collection_id": collection_id,
            "need_type": raw["need_type"],
            "requirement_kind": raw["requirement_kind"],
            "status": raw["status"],
            "attempt_count": raw["attempt_count"],
            "max_attempts": raw["max_attempts"],
            "atomic_claim_id": raw["atomic_claim_id"],
            "claim_candidate_id": raw["claim_candidate_id"],
            "source_intelligence_assessment_id": raw["source_intelligence_assessment_id"],
            "event_id": raw["event_id"],
            "state": "BLOCKED" if raw["status"] == "BLOCKED"
                     or document["collection_status"] != "ACTIVE"
                     or raw["attempt_count"] >= raw["max_attempts"]
                     else "NEEDS_REVIEW",
            "blockers": blockers,
            "retry_condition": "AFTER_SOURCE_RIGHTS_AND_COVERAGE_REVIEW",
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "private_only": True,
        "read_only": True,
        "publication_authority": False,
        "triage_action_authorized": False,
        "rights_clearance": False,
        "collection_id": collection_id,
        "collection_status": document["collection_status"],
        "snapshot_sha256": document["snapshot_sha256"],
        "rows": rows[:limit],
        "next_after_need_id": rows[limit - 1]["need_id"] if len(rows) > limit else None,
    }


def read_coverage_need_queue(
    store: Any, *, collection_id: str, limit: int = 20,
    after_need_id: str | None = None,
    expected_snapshot_sha256: str | None = None,
) -> dict[str, object]:
    collection_id = _validated_ref(collection_id)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("STUDIO_COVERAGE_NEED_LIMIT_INVALID")
    if after_need_id is not None:
        after_need_id = _validated_ref(after_need_id)
    if (after_need_id is None) != (expected_snapshot_sha256 is None):
        raise ValueError("STUDIO_COVERAGE_NEED_SNAPSHOT_REQUIRED")
    if expected_snapshot_sha256 is not None and (
        not isinstance(expected_snapshot_sha256, str)
        or not _SHA.fullmatch(expected_snapshot_sha256)
    ):
        raise ValueError("STUDIO_COVERAGE_NEED_SNAPSHOT_INVALID")
    try:
        raw = store.run(
            _SQL, collection_id=collection_id, limit=limit,
            after_id=after_need_id or "",
            expected_snapshot_sha256=expected_snapshot_sha256 or "",
        )
    except Exception:
        raise RuntimeError("STUDIO_COVERAGE_NEED_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or not 1 <= len(raw) <= 90_000 or "\n" in raw:
        raise ValueError("STUDIO_COVERAGE_NEED_RESULT_INVALID")
    try:
        packet = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("STUDIO_COVERAGE_NEED_RESULT_INVALID") from None
    if not isinstance(packet, dict):
        raise ValueError("STUDIO_COVERAGE_NEED_RESULT_INVALID")
    return _validated_packet(packet, collection_id=collection_id,
                             after_id=after_need_id or "", limit=limit)


__all__ = ["CONTRACT_VERSION", "read_coverage_need_queue"]
