"""DP416: one PostgreSQL snapshot for an authenticated private collection tree.

No Source body/URL, Passage text, normalised Statement/Claim, credentials or
review status is read. The parent is the exact INCLUDED Collection membership;
a bare Source/Content/Capture/Passage ID cannot enumerate a foreign resource.
This read model does not grant any rights, review, capture or publication action.
"""
from __future__ import annotations

import json
import re
from typing import Protocol


NAVIGATION_VERSION = "studio-collection-navigation-v1"
_REF = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_STATE = re.compile(r"[A-Z][A-Z_]{0,64}\Z")
_COLLECTION = {"ACTIVE", "PAUSED", "ARCHIVED"}
_CAPTURE = {"CAPTURED", "QUARANTINED", "PURGE_PENDING", "PURGED_BODY"}
_HOLD = {"NONE", "LEGAL_HOLD", "RIGHTS_HOLD", "PRIVACY_HOLD", "COPYRIGHT_HOLD", "DISPUTE_HOLD"}
_ARCHIVE = {"NOT_REQUESTED", "REQUESTED", "PENDING", "SUCCEEDED", "FAILED"}

# One PostgreSQL REPEATABLE READ read-only transaction and one SELECT for the
# *entire* parent/current-Capture/current-Passage/current-Candidate snapshot.
# No independent query can see a different revision midway through this view.
# The +1 member sentinel is validated to the same depth as displayed rows.
_NAV_SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object(
  'collection_id', collection.id,
  'state', collection.status,
  'cursor_valid', (:'after_id' = '' OR EXISTS (
    SELECT 1 FROM research_collection_content anchor
    WHERE anchor.collection_id=collection.id
      AND anchor.content_id=:'after_id' AND anchor.status='INCLUDED'
  )),
  'members', (
    SELECT coalesce(json_agg(row_to_json(item) ORDER BY item.content_id), '[]'::json)
    FROM (
      SELECT content.id AS content_id, content.source_id,
        (source.id IS NOT NULL) AS source_exists,
        content.rights_status, content.processing_status,
        (SELECT count(*) FROM content_capture capture
         WHERE capture.content_id=content.id) AS capture_count,
        (
          SELECT row_to_json(current_capture)
          FROM (
            SELECT capture.id, capture.content_sha256,
              capture.status, capture.hold_status, capture.rights_status,
              capture.archive_status,
              (SELECT count(*) FROM passage p
               WHERE p.capture_id=capture.id AND p.content_id=content.id
                 AND p.selector_type IN ('TEXT_POSITION','PAGE_RANGE')) AS passage_count,
              (
                SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.id), '[]'::json)
                FROM (
                  SELECT p.id, p.text_sha256, p.selector_type,
                    p.start_char, p.end_char, p.page_start, p.page_end,
                    (SELECT count(*) FROM statement_candidate_passage link
                     JOIN statement_candidate candidate
                       ON candidate.id=link.statement_candidate_id
                      AND candidate.content_id=link.content_id
                     WHERE link.passage_id=p.id AND link.content_id=content.id) AS candidate_count,
                    (SELECT min(candidate.id) FROM statement_candidate_passage link
                     JOIN statement_candidate candidate
                       ON candidate.id=link.statement_candidate_id
                      AND candidate.content_id=link.content_id
                     WHERE link.passage_id=p.id AND link.content_id=content.id) AS first_candidate_id
                  FROM passage p
                  WHERE p.content_id=content.id AND p.capture_id=capture.id
                    AND p.selector_type IN ('TEXT_POSITION','PAGE_RANGE')
                  ORDER BY p.id LIMIT 3
                ) selected
              ) AS passages
            FROM content_capture capture
            WHERE capture.content_id=content.id
            ORDER BY capture.observed_at DESC, capture.id DESC
            LIMIT 1
          ) current_capture
        ) AS latest_capture
      FROM research_collection_content member
      JOIN content_item content ON content.id=member.content_id
      LEFT JOIN source source ON source.id=content.source_id
      WHERE member.collection_id=collection.id
        AND member.status='INCLUDED' AND content.id>:'after_id'
      ORDER BY content.id LIMIT :'row_limit'::integer
    ) item
  )
)::text
FROM research_collection collection
WHERE collection.id=:'collection_id';
COMMIT;
""".strip()


class _Reader(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value) or ".." in value:
        raise ValueError("STUDIO_NAV_" + label + "_INVALID")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("STUDIO_NAV_SHA_INVALID")
    return value


def _state(value: object) -> str:
    if not isinstance(value, str) or not _STATE.fullmatch(value):
        raise ValueError("STUDIO_NAV_STATE_INVALID")
    return value


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**40:
        raise ValueError("STUDIO_NAV_COUNT_INVALID")
    return value


def _position(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 2**40:
        raise ValueError("STUDIO_NAV_POSITION_INVALID")
    return value


def _exact(row: object, keys: set[str]) -> dict:
    if not isinstance(row, dict) or set(row) != keys:
        raise ValueError("STUDIO_NAV_ROW_INVALID")
    return row


def _passages(value: object, count: int) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) > 3 or len(value) > count:
        raise ValueError("STUDIO_NAV_PASSAGE_PAGE_INVALID")
    result: list[dict[str, object]] = []
    previous = ""
    for raw in value:
        p = _exact(raw, {"id", "text_sha256", "selector_type", "start_char", "end_char",
                         "page_start", "page_end", "candidate_count", "first_candidate_id"})
        pid = _id(p["id"], "PASSAGE")
        if pid <= previous:
            raise ValueError("STUDIO_NAV_PASSAGE_ORDER_INVALID")
        previous = pid
        _sha(p["text_sha256"])
        kind = p["selector_type"]
        a, b, c, d = (_position(p[key]) for key in
                      ("start_char", "end_char", "page_start", "page_end"))
        if not ((kind == "TEXT_POSITION" and a is not None and b is not None
                 and b > a and c is None and d is None)
                or (kind == "PAGE_RANGE" and a is None and b is None
                    and c is not None and c >= 1 and d is not None and d >= c)):
            raise ValueError("STUDIO_NAV_PASSAGE_SELECTOR_INVALID")
        n = _count(p["candidate_count"])
        first = p["first_candidate_id"]
        if (first is None) != (n == 0):
            raise ValueError("STUDIO_NAV_CANDIDATE_BINDING_INVALID")
        if first is not None:
            _id(first, "FIRST_CANDIDATE")
        result.append(dict(p))
    return result


def read_collection_navigation(
    reader: _Reader, *, collection_id: str,
    limit: int = 10, after_content_id: str | None = None,
) -> dict[str, object]:
    """Bounded collection→Source→Capture→Passage→Candidate entrypoint.

    Cursor belongs to this Collection's currently INCLUDED membership; a
    foreign, removed, nonexistent cursor refuses rather than fabricating an
    empty page. Returns no text and grants no preview/mutation authority.
    """
    collection_id = _id(collection_id, "COLLECTION")
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("STUDIO_NAV_LIMIT_INVALID")
    cursor = _id(after_content_id, "CURSOR") if after_content_id is not None else ""
    try:
        data = json.loads(reader.run(_NAV_SQL, collection_id=collection_id,
                                     after_id=cursor, row_limit=limit + 1))
    except (ValueError, TypeError) as exc:
        raise ValueError("STUDIO_NAV_RESULT_INVALID") from None
    except Exception:
        raise RuntimeError("STUDIO_NAV_STORE_UNAVAILABLE") from None
    root = _exact(data, {"collection_id", "state", "cursor_valid", "members"})
    if (root["collection_id"] != collection_id or root["state"] not in _COLLECTION
            or type(root["cursor_valid"]) is not bool
            or (cursor and root["cursor_valid"] is not True)
            or not isinstance(root["members"], list)
            or len(root["members"]) > limit + 1):
        raise ValueError("STUDIO_NAV_COLLECTION_SCOPE_INVALID")
    emitted = []
    previous = cursor
    for raw in root["members"]:
        item = _exact(raw, {"content_id", "source_id", "source_exists",
                            "rights_status", "processing_status", "capture_count",
                            "latest_capture"})
        content_id = _id(item["content_id"], "CONTENT")
        if content_id <= previous:
            raise ValueError("STUDIO_NAV_CONTENT_ORDER_INVALID")
        previous = content_id
        source_id = item["source_id"]
        if source_id is not None:
            _id(source_id, "SOURCE")
        if type(item["source_exists"]) is not bool or bool(source_id) != item["source_exists"]:
            raise ValueError("STUDIO_NAV_SOURCE_BINDING_INVALID")
        rights, processing = _state(item["rights_status"]), _state(item["processing_status"])
        captures = _count(item["capture_count"])
        raw_capture = item["latest_capture"]
        current = None
        if raw_capture is not None:
            capture = _exact(raw_capture, {"id", "content_sha256", "status",
                                          "hold_status", "rights_status", "archive_status",
                                          "passage_count", "passages"})
            _id(capture["id"], "CAPTURE")
            _sha(capture["content_sha256"])
            if (_state(capture["status"]) not in _CAPTURE
                    or _state(capture["hold_status"]) not in _HOLD
                    or _state(capture["archive_status"]) not in _ARCHIVE):
                raise ValueError("STUDIO_NAV_CAPTURE_STATE_INVALID")
            cap_rights = _state(capture["rights_status"])
            passage_count = _count(capture["passage_count"])
            passages = _passages(capture["passages"], passage_count)
            current = dict(capture)
            current["passages"] = passages
            current["passages_truncated"] = passage_count > len(passages)
        if bool(current) != bool(captures):
            raise ValueError("STUDIO_NAV_CAPTURE_COUNT_INVALID")
        blockers = ["REVIEW_AUTHORITY_NOT_EVALUATED"]
        if not item["source_exists"]:
            blockers.append("SOURCE_MISSING")
        if rights != "APPROVED":
            blockers.append("CONTENT_RIGHTS_NOT_APPROVED")
        if processing != "READY":
            blockers.append("CONTENT_NOT_READY")
        if current is None:
            blockers.append("CAPTURE_NOT_PRESENT")
        elif (current["status"] != "CAPTURED" or current["hold_status"] != "NONE"
              or cap_rights != "APPROVED"):
            blockers.append("CAPTURE_NOT_READY_FOR_REVIEW")
        if len(emitted) < limit:
            emitted.append({
                "content_id": content_id, "source_id": source_id,
                "source_exists": item["source_exists"], "rights_status": rights,
                "processing_status": processing, "capture_count": captures,
                "latest_capture": current, "blockers": blockers,
                "source_preview_authorized": False, "review_authority": False,
            })
    more = len(root["members"]) > limit
    return {
        "contract_version": NAVIGATION_VERSION, "private_only": True,
        "read_only": True, "publication_authority": False,
        "rights_clearance": False, "review_authority": False,
        "collection_id": collection_id, "collection_state": root["state"],
        "members": emitted, "has_more": more,
        "next_after_content_id": emitted[-1]["content_id"] if more else None,
        "navigation": {
            "next_exact_passage_endpoint": "/v1/collections/passage-lineage",
            "requires_current_membership": True, "max_passages_per_capture": 3,
        },
    }


__all__ = ["NAVIGATION_VERSION", "read_collection_navigation"]
