"""DP-417: persisted, Collection-scoped private Statement Candidate inspection queue.

The read-only adapter never approves a Candidate or evaluates qualified source
rights. It exposes exact provenance identifiers and explainable blockers only.
"""
from __future__ import annotations

import json
import re
from typing import Any

from dichiarazioni_pubbliche.studio_discovery_triage_contract import _validated_ref

CONTRACT_VERSION = "studio-statement-candidate-queue-pg-v1"
_REF = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_ROW_FIELDS = frozenset({
    "candidate_id", "content_id", "candidate_status", "content_rights_status",
    "source_id", "source_present",
    "capture_id", "capture_status", "capture_rights_status", "capture_hold_status",
    "capture_archive_status",
    "passage_count", "passage_id", "passage_capture_id", "selector_type",
})

_SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH scope AS (
  SELECT id,status FROM research_collection WHERE id=:'collection_id'
),
candidate_rows AS (
  SELECT candidate.id AS candidate_id, candidate.content_id,
         candidate.status AS candidate_status,
         content.rights_status AS content_rights_status,
         content.source_id, source.id IS NOT NULL AS source_present,
         capture.id AS capture_id,
         capture.status AS capture_status,
         capture.rights_status AS capture_rights_status,
         capture.hold_status AS capture_hold_status,
         capture.archive_status AS capture_archive_status,
         links.passage_count, links.passage_id,
         passage.capture_id AS passage_capture_id,
         passage.selector_type
  FROM scope
  JOIN research_collection_content membership
    ON membership.collection_id=scope.id AND membership.status='INCLUDED'
  JOIN content_item content ON content.id=membership.content_id
  LEFT JOIN source ON source.id=content.source_id
  JOIN statement_candidate candidate ON candidate.content_id=content.id
    AND candidate.status IN ('CANDIDATE','HELD','APPROVED')
  LEFT JOIN LATERAL (
    SELECT observed.id, observed.status, observed.rights_status,
           observed.hold_status, observed.archive_status
    FROM content_capture observed WHERE observed.content_id=content.id
    ORDER BY observed.observed_at DESC, observed.id DESC LIMIT 1
  ) capture ON TRUE
  LEFT JOIN LATERAL (
    SELECT count(*)::integer AS passage_count, min(link.passage_id) AS passage_id
    FROM statement_candidate_passage link
    WHERE link.statement_candidate_id=candidate.id
      AND link.content_id=candidate.content_id
  ) links ON TRUE
  LEFT JOIN passage ON passage.id=links.passage_id
    AND passage.content_id=candidate.content_id
), fingerprint AS (
  SELECT encode(sha256(convert_to(jsonb_build_object(
      'collection_state', scope.status,
      'candidates', (
        SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.candidate_id), '[]'::jsonb)
        FROM candidate_rows c
      )
  )::text, 'UTF8')), 'hex') AS snapshot_sha256
  FROM scope
), selected AS (
  SELECT * FROM candidate_rows
  WHERE candidate_id>:'after_id'
  ORDER BY candidate_id
  LIMIT (:'limit'::integer + 1)
)
SELECT json_build_object(
  'collection_id', scope.id,
  'collection_status', scope.status,
  'snapshot_sha256', fingerprint.snapshot_sha256,
  'snapshot_valid', (
    :'expected_snapshot_sha256'='' OR
    :'expected_snapshot_sha256'=fingerprint.snapshot_sha256
  ),
  'cursor_valid', (
    :'after_id'='' OR EXISTS(
      SELECT 1 FROM candidate_rows existing WHERE existing.candidate_id=:'after_id'
    )
  ),
  'rows', (
    SELECT coalesce(json_agg(row_to_json(page) ORDER BY page.candidate_id),'[]'::json)
    FROM selected page
  )
)::text FROM scope CROSS JOIN fingerprint;
COMMIT;
""".strip()


def _safe_ref(value: object, *, nullable: bool = False) -> bool:
    return (nullable and value is None) or (
        isinstance(value, str) and bool(_REF.fullmatch(value))
    )


def _safe_code(value: object, *, nullable: bool = False) -> bool:
    return (nullable and value is None) or (
        isinstance(value, str) and bool(_CODE.fullmatch(value))
    )


def _validate_response(
    document: dict[str, Any], *, collection_id: str, after_id: str, limit: int,
) -> dict[str, object]:
    if document.get("snapshot_valid") is False:
        raise ValueError("STUDIO_CANDIDATE_QUEUE_SNAPSHOT_STALE")
    if (
        set(document) != {
            "collection_id", "collection_status", "snapshot_sha256",
            "snapshot_valid", "cursor_valid", "rows",
        }
        or document["collection_id"] != collection_id
        or document["collection_status"] not in {"ACTIVE", "PAUSED", "ARCHIVED"}
        or type(document["snapshot_valid"]) is not bool
        or type(document["cursor_valid"]) is not bool
        or not document["cursor_valid"]
        or not isinstance(document["snapshot_sha256"], str)
        or not _SHA.fullmatch(document["snapshot_sha256"])
    ):
        raise ValueError("STUDIO_CANDIDATE_QUEUE_SCOPE_INVALID")
    rows = document["rows"]
    if not isinstance(rows, list) or len(rows) > limit + 1:
        raise ValueError("STUDIO_CANDIDATE_QUEUE_PAGE_INVALID")
    result: list[dict[str, object]] = []
    previous = after_id
    for record in rows:
        if not isinstance(record, dict) or set(record) != _ROW_FIELDS:
            raise ValueError("STUDIO_CANDIDATE_QUEUE_ROW_INVALID")
        candidate_id = record["candidate_id"]
        if (
            not _safe_ref(candidate_id) or candidate_id <= previous
            or not _safe_ref(record["content_id"])
            or not _safe_ref(record["source_id"], nullable=True)
            or type(record["source_present"]) is not bool
            or record["source_present"] != (record["source_id"] is not None)
            or record["candidate_status"] not in {"CANDIDATE", "HELD", "APPROVED"}
            or not _safe_code(record["content_rights_status"])
            or not _safe_ref(record["capture_id"], nullable=True)
            or not _safe_code(record["capture_status"], nullable=True)
            or not _safe_code(record["capture_rights_status"], nullable=True)
            or not _safe_code(record["capture_hold_status"], nullable=True)
            or not _safe_code(record["capture_archive_status"], nullable=True)
            or (record["capture_id"] is None) != (record["capture_status"] is None)
            or (record["capture_id"] is None) != (record["capture_archive_status"] is None)
            or not _safe_ref(record["passage_id"], nullable=True)
            or not _safe_ref(record["passage_capture_id"], nullable=True)
            or not _safe_code(record["selector_type"], nullable=True)
            or type(record["passage_count"]) is not int
            or record["passage_count"] < 0
            or (record["passage_count"] == 0) != (record["passage_id"] is None)
            or (record["passage_count"] > 0) != (record["selector_type"] is not None)
        ):
            raise ValueError("STUDIO_CANDIDATE_QUEUE_ROW_INVALID")
        previous = candidate_id
        blockers: list[str] = []
        if not record["source_present"]:
            blockers.append("SOURCE_REFERENCE_MISSING")
        if document["collection_status"] != "ACTIVE":
            blockers.append("COLLECTION_NOT_ACTIVE")
        if record["content_rights_status"] in {"REVOKED", "EXPIRED", "DENIED", "FORBIDDEN", "BLOCKED"}:
            blockers.append("CONTENT_RIGHTS_" + record["content_rights_status"])
        if record["capture_id"] is None:
            blockers.append("CURRENT_CAPTURE_MISSING")
        else:
            if record["capture_status"] != "CAPTURED":
                blockers.append("CURRENT_CAPTURE_" + record["capture_status"])
            if record["capture_archive_status"] == "FAILED":
                blockers.append("CURRENT_CAPTURE_ARCHIVE_FAILED")
            if record["capture_rights_status"] in {"REVOKED", "EXPIRED", "DENIED", "FORBIDDEN", "BLOCKED"}:
                blockers.append("CAPTURE_RIGHTS_" + record["capture_rights_status"])
            if record["capture_hold_status"] != "NONE":
                blockers.append("CAPTURE_HOLD_ACTIVE")
        if record["passage_count"] == 0:
            blockers.append("PASSAGE_PROVENANCE_MISSING")
        elif record["passage_count"] > 1:
            blockers.append("MULTIPLE_PASSAGES_REQUIRE_INSPECTION")
        elif record["passage_capture_id"] is None:
            blockers.append("MEDIA_SOURCE_VERSION_UNPROVEN")
        elif record["passage_capture_id"] != record["capture_id"]:
            blockers.append("PASSAGE_CAPTURE_NOT_LATEST")
        if record["candidate_status"] == "HELD":
            blockers.append("CANDIDATE_HELD")
        else:
            blockers.append("CANDIDATE_NEEDS_REVIEW")
        blockers.extend((
            "PRIVATE_SOURCE_RIGHTS_NOT_ATTESTED",
            "QUALIFIED_REVIEW_AUTHORITY_NOT_ATTESTED",
        ))
        result.append({
            "collection_id": collection_id,
            "candidate_id": candidate_id,
            "content_id": record["content_id"],
            # Inspection must bind the Passage to its persisted old Capture
            # when a newer version exists; the latest Capture is only the
            # currentness fence, never a substitute source version.
            "capture_id": (
                record["passage_capture_id"]
                if record["passage_count"] == 1 and record["passage_capture_id"] is not None
                else record["capture_id"]
            ),
            "passage_id": record["passage_id"] if record["passage_count"] == 1 else None,
            "candidate_status": record["candidate_status"],
            "state": "BLOCKED" if len(blockers) > 3 or record["candidate_status"] == "HELD"
                     else "NEEDS_REVIEW",
            "blockers": blockers,
            "retry_condition": "AFTER_PRIVATE_PROVENANCE_AND_RIGHTS_REVIEW",
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "private_only": True,
        "read_only": True,
        "publication_authority": False,
        "triage_action_authorized": False,
        "collection_id": collection_id,
        "collection_status": document["collection_status"],
        "snapshot_sha256": document["snapshot_sha256"],
        "rows": result[:limit],
        "next_after_candidate_id": result[limit - 1]["candidate_id"] if len(result) > limit else None,
    }


def read_candidate_triage_queue(
    store: Any, *, collection_id: str, limit: int = 20,
    after_candidate_id: str | None = None,
    expected_snapshot_sha256: str | None = None,
) -> dict[str, object]:
    collection_id = _validated_ref(collection_id)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("STUDIO_CANDIDATE_QUEUE_LIMIT_INVALID")
    if after_candidate_id is not None:
        after_candidate_id = _validated_ref(after_candidate_id)
    if (after_candidate_id is None) != (expected_snapshot_sha256 is None):
        raise ValueError("STUDIO_CANDIDATE_QUEUE_SNAPSHOT_REQUIRED")
    if expected_snapshot_sha256 is not None and (
        not isinstance(expected_snapshot_sha256, str)
        or not _SHA.fullmatch(expected_snapshot_sha256)
    ):
        raise ValueError("STUDIO_CANDIDATE_QUEUE_SNAPSHOT_INVALID")
    try:
        raw = store.run(
            _SQL, collection_id=collection_id,
            after_id=after_candidate_id or "", limit=limit,
            expected_snapshot_sha256=expected_snapshot_sha256 or "",
        )
    except Exception:
        raise RuntimeError("STUDIO_CANDIDATE_QUEUE_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or not raw or len(raw) > 70_000 or "\n" in raw:
        raise ValueError("STUDIO_CANDIDATE_QUEUE_RESPONSE_INVALID")
    try:
        document = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("STUDIO_CANDIDATE_QUEUE_RESPONSE_INVALID") from None
    if not isinstance(document, dict):
        raise ValueError("STUDIO_CANDIDATE_QUEUE_RESPONSE_INVALID")
    return _validate_response(
        document, collection_id=collection_id,
        after_id=after_candidate_id or "", limit=limit,
    )


__all__ = ["CONTRACT_VERSION", "read_candidate_triage_queue"]
