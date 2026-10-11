"""DP-417: scoped, bounded, read-only inspection of private triage annotations.

Annotations are not review authority and MUST NOT authorize downstream actions.
This reader returns no operator identity, free text, URL, query or source body.
"""

from __future__ import annotations

import json
import re
from typing import Any

from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    TRIAGE_DECISIONS,
    _validated_ref,
    _validated_revision,
)

TRIAGE_HISTORY_VERSION = "studio-discovery-triage-history-v1"

_TRIAGE_HISTORY_SQL = """
WITH scoped_hit AS (
    SELECT hit.id, COALESCE(
        attempt.run_id=run.id AND attempt.query_id=hit.query_id
        AND discovery_query.manifest_id=manifest.id, false
    ) AS lineage_ok
    FROM research_discovery_hit hit
    JOIN research_discovery_run run ON run.id=hit.run_id
    JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
    LEFT JOIN research_discovery_attempt attempt ON attempt.id=hit.attempt_id
    LEFT JOIN research_discovery_query discovery_query ON discovery_query.id=hit.query_id
    WHERE hit.id=:'hit_id' AND manifest.collection_id=:'collection_id'
),
selected AS (
    SELECT history.revision, history.expected_revision, history.decision
    FROM research_discovery_triage_decision history
    JOIN scoped_hit hit ON hit.id=history.hit_id AND hit.lineage_ok
    WHERE history.collection_id=:'collection_id'
      AND history.revision > :'after_revision'::bigint
    ORDER BY history.revision ASC
    LIMIT :'limit'::integer
)
SELECT json_build_object(
    'collection_id', :'collection_id',
    'hit_id', hit.id, 'lineage_ok', hit.lineage_ok,
    'head_revision', (
        SELECT coalesce(max(history.revision),0)
        FROM research_discovery_triage_decision history
        WHERE history.hit_id=hit.id AND history.collection_id=:'collection_id'
          AND hit.lineage_ok
    ),
    'ledger_count', (
        SELECT count(*)
        FROM research_discovery_triage_decision history
        WHERE history.hit_id=hit.id AND history.collection_id=:'collection_id'
          AND hit.lineage_ok
    ),
    'decisions', (
        SELECT coalesce(
            json_agg(json_build_object(
                'revision', selected.revision,
                'expected_revision', selected.expected_revision,
                'decision', selected.decision
            ) ORDER BY selected.revision ASC),
            '[]'::json
        )
        FROM selected
    )
)::text
FROM scoped_hit hit;
""".strip()


def _present(row: dict[str, Any], *, collection_id: str, hit_id: str,
             limit: int, after_revision: int) -> dict[str, object]:
    if row.get("collection_id") != collection_id or row.get("hit_id") != hit_id:
        raise ValueError("STUDIO_TRIAGE_HISTORY_SCOPE_MISMATCH")
    lineage_ok = row.get("lineage_ok")
    if type(lineage_ok) is not bool:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LINEAGE_INVALID")
    head_revision = _validated_revision(row.get("head_revision"))
    ledger_count = _validated_revision(row.get("ledger_count"))
    # Revisions start at one and each insertion must increment by one. MAX()
    # alone hides deleted or missing rows outside the requested page.
    if ledger_count != head_revision:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LEDGER_INCOMPLETE")
    decisions = row.get("decisions")
    # Failed Hit -> Attempt -> Query lineage must not disclose old annotations,
    # including their count/head, even if the ledger's Collection ID matches.
    if not lineage_ok and (head_revision != 0 or ledger_count != 0 or decisions != []):
        raise ValueError("STUDIO_TRIAGE_HISTORY_LINEAGE_DISCLOSURE")
    visible_count = min(limit, max(head_revision - after_revision, 0))
    if not isinstance(decisions, list) or len(decisions) != visible_count:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LIMIT_INVALID")
    output: list[dict[str, object]] = []
    last_revision = after_revision
    for record in decisions:
        if not isinstance(record, dict):
            raise ValueError("STUDIO_TRIAGE_HISTORY_RECORD_INVALID")
        revision = _validated_revision(record.get("revision"))
        expected = _validated_revision(record.get("expected_revision"), expected=True)
        decision = record.get("decision")
        if (
            revision != last_revision + 1 or revision > head_revision
            or revision != expected + 1
            or decision not in TRIAGE_DECISIONS
        ):
            raise ValueError("STUDIO_TRIAGE_HISTORY_RECORD_INVALID")
        output.append({"revision": revision, "decision": decision})
        last_revision = revision
    if head_revision < after_revision and output:
        raise ValueError("STUDIO_TRIAGE_HISTORY_HEAD_INVALID")
    return {
        "contract_version": TRIAGE_HISTORY_VERSION,
        "collection_id": collection_id, "hit_id": hit_id,
        "private_only": True, "read_only": True,
        "publication_authority": False, "triage_action_authorized": False,
        "reviewer_identity_attested": False, "rights_clearance": False,
        "lineage_ok": lineage_ok, "head_revision": head_revision,
        "results": output,
        "next_after_revision": last_revision if len(output) == limit else None,
        "blockers": (
            ([] if lineage_ok else ["DISCOVERY_LINEAGE_MISMATCH"])
            + ["TRIAGE_REVIEWER_AUTHORITY_NOT_REEVALUATED",
               "PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED"]
        ),
    }


def read_triage_history(store: Any, *, collection_id: str, hit_id: str,
                        limit: int = 20, after_revision: int = 0) -> dict[str, object]:
    collection_id = _validated_ref(collection_id)
    hit_id = _validated_ref(hit_id)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LIMIT_INVALID")
    after_revision = _validated_revision(after_revision)
    try:
        raw = store.run(
            _TRIAGE_HISTORY_SQL, collection_id=collection_id, hit_id=hit_id,
            limit=limit, after_revision=after_revision,
        )
    except Exception:
        raise RuntimeError("STUDIO_TRIAGE_HISTORY_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or len(raw) > 30_000:
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    if not raw.strip():
        raise ValueError("STUDIO_TRIAGE_HISTORY_NOT_FOUND")
    if len(raw.splitlines()) != 1:
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    try:
        row = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID") from None
    if not isinstance(row, dict):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    try:
        return _present(
            row, collection_id=collection_id, hit_id=hit_id,
            limit=limit, after_revision=after_revision,
        )
    except (ValueError, TypeError):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID") from None


# A separate, existing-schema queue family. Capture is not Discovery Hit:
# a logical Content may have multiple independently observed snapshots.
# This SQL never reads a body, URL, title, reviewer, candidate text or receipt.
# Its included Collection edge is the permission/scope fence; an external
# authenticated read-only Studio runtime must own the supplied store.
CAPTURE_QUEUE_VERSION = "studio-capture-triage-queue-v1"
_CAPTURE_QUEUE_SQL = """
BEGIN TRANSACTION READ ONLY;
WITH scope AS (
    SELECT id, status FROM research_collection
    WHERE id=:'collection_id'
),
capture_history AS (
    SELECT c.id, c.content_id, c.status AS capture_status,
           c.hold_status, c.rights_status, c.archive_status,
           lag(c.id) OVER (
               PARTITION BY c.content_id ORDER BY c.observed_at ASC, c.id ASC
           ) AS previous_capture_id,
           row_number() OVER (
               PARTITION BY c.content_id ORDER BY c.observed_at DESC, c.id DESC
           ) AS latest_rank
    FROM scope
    JOIN research_collection_content member
      ON member.collection_id=scope.id AND member.status='INCLUDED'
    JOIN content_capture c ON c.content_id=member.content_id
),
eligible AS (
    SELECT * FROM capture_history
    WHERE latest_rank=1 AND (
        previous_capture_id IS NOT NULL
        OR capture_status <> 'CAPTURED'
        OR hold_status <> 'NONE'
        OR rights_status IN ('REVOKED', 'EXPIRED', 'DENIED')
        OR archive_status='FAILED'
    )
),
selected AS (
    SELECT c.id, c.content_id, c.previous_capture_id,
           c.capture_status, c.hold_status, c.rights_status,
           c.archive_status, (c.previous_capture_id IS NOT NULL) AS source_changed,
           (
               SELECT event.id FROM capture_lifecycle_event event
               WHERE event.capture_id=c.id
               ORDER BY event.created_at DESC, event.id DESC
               LIMIT 1
           ) AS lifecycle_event_id
    FROM eligible c
    WHERE c.id > :'after_id'
    ORDER BY c.id ASC
    LIMIT (:'limit'::integer + 1)
)
SELECT json_build_object(
    'collection_id', scope.id, 'collection_status', scope.status,
    'cursor_valid', (
        :'after_id'='' OR EXISTS (
            SELECT 1 FROM eligible anchor WHERE anchor.id=:'after_id'
        )
    ),
    'rows', (
        SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.id ASC), '[]'::json)
        FROM selected
    )
)::text
FROM scope;
COMMIT;
""".strip()

_CAPTURE_STATUS = frozenset({"CAPTURED", "QUARANTINED", "PURGE_PENDING", "PURGED_BODY"})
_CAPTURE_HOLD = frozenset({
    "NONE", "LEGAL_HOLD", "RIGHTS_HOLD", "PRIVACY_HOLD",
    "COPYRIGHT_HOLD", "DISPUTE_HOLD",
})
_ARCHIVE_STATUS = frozenset({
    "NOT_REQUESTED", "REQUESTED", "PENDING", "SUCCEEDED", "FAILED",
})
_SAFE_CAPTURE_ID = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z", re.ASCII)
_SAFE_RIGHTS_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_CAPTURE_FIELDS = frozenset({
    "id", "content_id", "previous_capture_id", "capture_status",
    "hold_status", "rights_status", "archive_status", "source_changed",
    "lifecycle_event_id",
})


def _present_capture_queue(
    result: dict[str, Any], *, collection_id: str, after_id: str, limit: int,
) -> dict[str, object]:
    if (set(result) != {"collection_id", "collection_status", "cursor_valid", "rows"}
        or result["collection_id"] != collection_id
        or result["collection_status"] not in {"ACTIVE", "PAUSED", "ARCHIVED"}
        or type(result["cursor_valid"]) is not bool
        or not result["cursor_valid"]):
        raise ValueError("STUDIO_CAPTURE_QUEUE_SCOPE_INVALID")
    rows = result["rows"]
    if not isinstance(rows, list) or len(rows) > limit + 1:
        raise ValueError("STUDIO_CAPTURE_QUEUE_ROWS_INVALID")
    output = []
    last = after_id
    for item in rows:
        if not isinstance(item, dict) or set(item) != _CAPTURE_FIELDS:
            raise ValueError("STUDIO_CAPTURE_QUEUE_RECORD_INVALID")
        cid, content_id = item["id"], item["content_id"]
        prior, event_id = item["previous_capture_id"], item["lifecycle_event_id"]
        if (not all(isinstance(value, str) and _SAFE_CAPTURE_ID.fullmatch(value)
                    for value in (cid, content_id))
            or cid <= last
            or prior is not None and (not isinstance(prior, str)
                                     or not _SAFE_CAPTURE_ID.fullmatch(prior)
                                     or prior == cid)
            or event_id is not None and (
                not isinstance(event_id, str) or not _SAFE_CAPTURE_ID.fullmatch(event_id)
            )
            or item["capture_status"] not in _CAPTURE_STATUS
            or item["hold_status"] not in _CAPTURE_HOLD
            or item["archive_status"] not in _ARCHIVE_STATUS
            or not isinstance(item["rights_status"], str)
            or not _SAFE_RIGHTS_CODE.fullmatch(item["rights_status"])
            or type(item["source_changed"]) is not bool
            or item["source_changed"] != (prior is not None)):
            raise ValueError("STUDIO_CAPTURE_QUEUE_RECORD_INVALID")
        blocked = (
            result["collection_status"] != "ACTIVE" or
            item["capture_status"] != "CAPTURED" or
            item["hold_status"] != "NONE" or
            item["rights_status"] in {"REVOKED", "EXPIRED", "DENIED"} or
            item["archive_status"] == "FAILED"
        )
        if not blocked and prior is None:
            raise ValueError("STUDIO_CAPTURE_QUEUE_NOT_AN_EXCEPTION")
        if result["collection_status"] != "ACTIVE":
            reason, retry = "COLLECTION_NOT_ACTIVE", "AFTER_COLLECTION_SCOPE_REVIEW"
        elif item["capture_status"] == "QUARANTINED":
            reason, retry = "CAPTURE_QUARANTINED", "AFTER_QUARANTINE_REVIEW"
        elif item["capture_status"] == "PURGE_PENDING":
            reason, retry = "CAPTURE_PURGE_PENDING", "AFTER_PURGE_LIFECYCLE_RESOLUTION"
        elif item["capture_status"] == "PURGED_BODY":
            reason, retry = "CAPTURE_BODY_PURGED", "RECAPTURE_ONLY_AFTER_RIGHTS_REVIEW"
        elif item["hold_status"] != "NONE":
            reason, retry = "CAPTURE_HOLD_ACTIVE", "AFTER_HOLD_RELEASE_AND_RIGHTS_REVIEW"
        elif item["rights_status"] in {"REVOKED", "EXPIRED", "DENIED"}:
            reason, retry = (
                "CAPTURE_RIGHTS_" + item["rights_status"],
                "AFTER_NEW_SOURCE_RIGHTS_DECISION",
            )
        elif item["archive_status"] == "FAILED":
            reason, retry = "CAPTURE_ARCHIVE_FAILED", "AFTER_ARCHIVE_RETRY_REVIEW"
        else:
            reason, retry = "CAPTURE_CHANGE_REVIEW_REQUIRED", "AFTER_PRIVATE_CAPTURE_REVIEW"
        output.append({
            "queue_family": "BLOCKED_CAPTURE" if blocked else "CHANGED_CAPTURE",
            "collection_id": collection_id, "content_id": content_id, "capture_id": cid,
            "previous_capture_id": prior, "lifecycle_event_id": event_id,
            "source_changed": item["source_changed"],
            "state": "BLOCKED" if blocked else "NEEDS_REVIEW",
            "blockers": [
                reason, "PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED",
                "CAPTURE_REVIEW_AUTHORITY_NOT_EVALUATED",
            ],
            "retry_condition": retry,
        })
        last = cid
    return {
        "contract_version": CAPTURE_QUEUE_VERSION,
        "collection_id": collection_id, "collection_status": result["collection_status"],
        "private_only": True, "read_only": True,
        "publication_authority": False, "rights_clearance": False,
        "triage_action_authorized": False,
        "results": output[:limit],
        "next_after_capture_id": (
            output[limit - 1]["capture_id"] if len(output) > limit else None
        ),
    }


def read_capture_triage_queue(
    store: Any, *, collection_id: str,
    limit: int = 20, after_capture_id: str | None = None,
) -> dict[str, object]:
    """Read a persisted changed/restricted-Capture queue, without state changes.

    Only call through an already authenticated, private read-only Studio
    database context. This function itself cannot attest caller identity.
    No user input is interpolated into SQL; the cursor must belong to the
    currently eligible included-Collection queue, or the read fails closed.
    """
    collection_id = _validated_ref(collection_id)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("STUDIO_CAPTURE_QUEUE_LIMIT_INVALID")
    if after_capture_id is not None:
        after_capture_id = _validated_ref(after_capture_id)
    cursor = after_capture_id or ""
    try:
        raw = store.run(
            _CAPTURE_QUEUE_SQL, collection_id=collection_id,
            after_id=cursor, limit=limit,
        )
    except Exception:
        raise RuntimeError("STUDIO_CAPTURE_QUEUE_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or not raw or len(raw) > 45000 or "\n" in raw:
        raise ValueError("STUDIO_CAPTURE_QUEUE_RESULT_UNAVAILABLE")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("STUDIO_CAPTURE_QUEUE_RESULT_INVALID") from None
    if not isinstance(value, dict):
        raise ValueError("STUDIO_CAPTURE_QUEUE_RESULT_INVALID")
    return _present_capture_queue(
        value, collection_id=collection_id, after_id=cursor, limit=limit,
    )


__all__ = [
    "TRIAGE_HISTORY_VERSION", "read_triage_history",
    "CAPTURE_QUEUE_VERSION", "read_capture_triage_queue",
]
