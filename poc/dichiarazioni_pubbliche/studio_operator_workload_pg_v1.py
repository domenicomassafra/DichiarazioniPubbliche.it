"""DP-519 private Studio operational read model over disposable canonical PostgreSQL.

Read-only snapshot only. Operator authentication MUST be performed by the
calling Studio HTTP boundary; a verifier callback is not independent proof.
No raw text, URLs, images, image approvals, provider work or publication grants.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
from typing import Callable
from urllib.parse import urlsplit

VERSION = "studio-operator-workload-pg-v1"
MAX_MEMBERS = 500
MAX_PAGE = 20
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9.:/_-]{0,199}\Z")

# One SQL statement supplies both the Collection row and all bounded members,
# under one REPEATABLE READ READ ONLY transaction. Every child aggregate is
# scoped by the exact INCLUDED Collection member and the most recent Capture.
# A versioned next-cursor is rejected if any scoped metadata changes later.
_QUERY = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT json_build_object(
 'collection_id', col.id,
 'collection_state', col.status,
 'rows', (
   SELECT coalesce(json_agg(row_to_json(work) ORDER BY work.content_id),'[]'::json)
   FROM (
     SELECT content.id AS content_id, member.status AS membership_state,
       content.rights_status AS content_rights,
       content.processing_status AS processing_state,
       (SELECT count(*) FROM content_capture ca WHERE ca.content_id=content.id)
          AS capture_count,
       ca.id AS capture_id, ca.status AS capture_state,
       ca.rights_status AS capture_rights, ca.hold_status AS capture_hold,
       ca.content_sha256 AS capture_sha256,
       coalesce((SELECT count(*) FROM passage p
                 WHERE p.content_id=content.id AND p.capture_id=ca.id),0)
          AS passage_count,
       (SELECT count(DISTINCT link.statement_candidate_id)
        FROM passage p
        JOIN statement_candidate_passage link
          ON link.passage_id=p.id AND link.content_id=content.id
        WHERE p.content_id=content.id AND p.capture_id=ca.id)
          AS statement_candidate_count,
       (SELECT count(DISTINCT cc.id)
        FROM passage p
        JOIN statement_candidate_passage link
          ON link.passage_id=p.id AND link.content_id=content.id
        JOIN claim_candidate cc
          ON cc.statement_candidate_id=link.statement_candidate_id
         AND cc.content_id=content.id
        WHERE p.content_id=content.id AND p.capture_id=ca.id)
          AS claim_candidate_count,
       (SELECT count(DISTINCT link.statement_candidate_id)
        FROM passage p
        JOIN statement_candidate_passage link
          ON link.passage_id=p.id AND link.content_id=content.id
        JOIN statement_candidate sc
          ON sc.id=link.statement_candidate_id AND sc.content_id=content.id
        WHERE p.content_id=content.id AND p.capture_id=ca.id
          AND sc.status='HELD') AS held_statement_count,
       (SELECT count(DISTINCT cc.id)
        FROM passage p
        JOIN statement_candidate_passage link
          ON link.passage_id=p.id AND link.content_id=content.id
        JOIN claim_candidate cc
          ON cc.statement_candidate_id=link.statement_candidate_id
         AND cc.content_id=content.id
        WHERE p.content_id=content.id AND p.capture_id=ca.id
          AND cc.status='HELD') AS held_claim_count,
       (SELECT count(*) FROM private_source_rights_record rr
          WHERE rr.content_id=content.id
          AND NOT EXISTS (SELECT 1 FROM private_source_rights_record next
                          WHERE next.supersedes_id=rr.id)) AS rights_leaf_count,
       (SELECT rr.rights_status FROM private_source_rights_record rr
          WHERE rr.content_id=content.id
          AND NOT EXISTS (SELECT 1 FROM private_source_rights_record next
                          WHERE next.supersedes_id=rr.id)
          ORDER BY rr.id LIMIT 1) AS rights_leaf_status,
       (SELECT coalesce(rr.rights_status='CLEARED'
                AND rr.rights_receipt_ref IS NOT NULL
                AND rr.reviewed_at IS NOT NULL
                AND rr.reviewer_ref IS NOT NULL
                AND (rr.expires_at IS NULL OR rr.expires_at>current_timestamp)
                AND rr.permitted_uses @> ARRAY['FETCH','PARSE_TEXT']::text[],false)
        FROM private_source_rights_record rr
        WHERE rr.content_id=content.id
          AND NOT EXISTS (SELECT 1 FROM private_source_rights_record next
                          WHERE next.supersedes_id=rr.id)
        ORDER BY rr.id LIMIT 1) AS rights_ready
     FROM research_collection_content member
     JOIN content_item content ON content.id=member.content_id
     LEFT JOIN LATERAL (
       SELECT id,status,rights_status,hold_status,content_sha256
       FROM content_capture ca
       WHERE ca.content_id=content.id
       ORDER BY ca.observed_at DESC,ca.id DESC LIMIT 1
     ) ca ON true
     WHERE member.collection_id=col.id AND member.status='INCLUDED'
     ORDER BY content.id LIMIT 501
   ) work
 )
)::text
FROM research_collection col WHERE col.id=:'collection_id';
COMMIT;
""".strip()


def _id(value: object) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value) or ".." in value:
        raise ValueError("DP519_WORKLOAD_ID_INVALID")
    return value


def _cursor_read(value: str, collection_id: str) -> dict:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("DP519_WORKLOAD_CURSOR_INVALID")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or set(data) != {"v", "collection", "after", "fingerprint"}
            or data["v"] != VERSION
            or data["collection"] != collection_id
            or not re.fullmatch(r"[a-f0-9]{64}", data["fingerprint"])
        ):
            raise ValueError
        _id(data["after"])
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error):
        raise ValueError("DP519_WORKLOAD_CURSOR_INVALID") from None
    return data


def _cursor_write(collection_id: str, after: str, fingerprint: str) -> str:
    material = {
        "v": VERSION,
        "collection": collection_id,
        "after": after,
        "fingerprint": fingerprint,
    }
    return (
        base64.urlsafe_b64encode(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**40:
        raise ValueError("DP519_WORKLOAD_COUNT_INVALID")
    return value


_RIGHTS_STATES = {
    "UNKNOWN",
    "UNRESOLVED",
    "EXPIRED",
    "CONFLICTING",
    "REVOKED",
    "BLOCKED",
    "FORBIDDEN",
    "LEGAL_HOLD",
    "RIGHTS_HOLD",
    "TAKEDOWN_HOLD",
    "REMOVED",
    "CLEARED",
}
_CAPTURE_STATES = {"CAPTURED", "QUARANTINED", "PURGE_PENDING", "PURGED_BODY"}
_CAPTURE_HOLDS = {
    "NONE",
    "LEGAL_HOLD",
    "RIGHTS_HOLD",
    "PRIVACY_HOLD",
    "COPYRIGHT_HOLD",
    "DISPUTE_HOLD",
}


def _allow_state(value: object, allowed: set[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "UNKNOWN"


def _status(row: dict, collection_state: str) -> tuple[str, str]:
    if collection_state != "ACTIVE":
        return "BLOCKED", "COLLECTION_NOT_ACTIVE"
    if row["content_rights"] != "CLEARED":
        return "BLOCKED", "CONTENT_RIGHTS_NOT_CLEARED"
    if row["rights_leaf_count"] != 1:
        return "BLOCKED", "RIGHTS_MISSING_OR_AMBIGUOUS"
    if not row["rights_ready"]:
        return "BLOCKED", "CURRENT_RIGHTS_NOT_READY"
    if row["capture_id"] is None:
        return "BLOCKED", "CAPTURE_MISSING"
    if row["capture_state"] != "CAPTURED" or row["capture_hold"] != "NONE":
        return "BLOCKED", "CAPTURE_HELD"
    if row["capture_rights"] != "CLEARED":
        return "BLOCKED", "CAPTURE_RIGHTS_NOT_CLEARED"
    if row["passage_count"] == 0:
        return "BLOCKED", "PASSAGE_MISSING"
    if row["held_statement_count"] or row["held_claim_count"]:
        return "BLOCKED", "CANDIDATE_HELD"
    if row["statement_candidate_count"] == 0:
        return "REVIEW_ONLY", "STATEMENT_CANDIDATE_MISSING"
    if row["claim_candidate_count"] == 0:
        return "REVIEW_ONLY", "CLAIM_CANDIDATE_MISSING"
    return "REVIEW_ONLY", "PRIVATE_TRIAGE_REQUIRED"


_ACTIONS = {
    "COLLECTION_NOT_ACTIVE": "INSPECT_COLLECTION_POLICY",
    "CONTENT_RIGHTS_NOT_CLEARED": "INSPECT_CONTENT_RIGHTS",
    "RIGHTS_MISSING_OR_AMBIGUOUS": "RESOLVE_SOURCE_RIGHTS",
    "CURRENT_RIGHTS_NOT_READY": "INSPECT_SOURCE_RIGHTS",
    "CAPTURE_MISSING": "REVIEW_CAPTURE_AVAILABILITY",
    "CAPTURE_HELD": "INSPECT_CAPTURE_HOLD",
    "CAPTURE_RIGHTS_NOT_CLEARED": "INSPECT_CAPTURE_RIGHTS",
    "PASSAGE_MISSING": "REVIEW_EXTRACTION_STATUS",
    "CANDIDATE_HELD": "INSPECT_CANDIDATE_HOLD",
}


class IsolatedStudioOperatorWorkloadPg:
    """Authenticated-caller-gated read adapter; only disposable local PG.

    A production HTTP handler must replace this DSN guard and independently
    authenticate the actor, audit access and enforce a real Studio session.
    """

    def __init__(self, dsn: str, *, allow_disposable_postgres: bool = False):
        parsed = urlsplit(dsn)
        if (
            allow_disposable_postgres is not True
            or parsed.scheme not in {"postgresql", "postgres"}
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.port is None
            or parsed.path != "/dp519_disposable"
            or parsed.username != "postgres"
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not shutil.which("psql")
        ):
            raise ValueError("DP519_WORKLOAD_DISPOSABLE_ONLY")
        self.dsn = dsn

    def _snapshot(self, collection_id: str) -> dict:
        result = subprocess.run(
            [
                "psql",
                "-X",
                "-qAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-v",
                "collection_id=" + collection_id,
                "-d",
                self.dsn,
            ],
            input=_QUERY,
            text=True,
            capture_output=True,
            timeout=12,
            check=False,
        )
        if result.returncode:
            raise ValueError("DP519_WORKLOAD_SNAPSHOT_FAILED")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise ValueError("DP519_WORKLOAD_COLLECTION_MISSING")
        try:
            value = json.loads(lines[0])
        except json.JSONDecodeError:
            raise ValueError("DP519_WORKLOAD_SNAPSHOT_INVALID") from None
        if (
            not isinstance(value, dict)
            or set(value) != {"collection_id", "collection_state", "rows"}
            or value["collection_id"] != collection_id
        ):
            raise ValueError("DP519_WORKLOAD_SNAPSHOT_INVALID")
        return value

    def read(
        self,
        *,
        collection_id: str,
        limit: int = 10,
        after: str | None = None,
        verify_authenticated_operator: Callable[[str], bool] | None = None,
    ) -> dict:
        collection_id = _id(collection_id)
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
            raise ValueError("DP519_WORKLOAD_PAGE_INVALID")
        if not callable(verify_authenticated_operator):
            raise ValueError("DP519_WORKLOAD_OPERATOR_AUTH_REQUIRED")
        try:
            allowed = verify_authenticated_operator(collection_id) is True
        except Exception:
            allowed = False
        if not allowed:
            raise ValueError("DP519_WORKLOAD_OPERATOR_AUTH_REQUIRED")
        previous = _cursor_read(after, collection_id) if after is not None else None
        raw = self._snapshot(collection_id)
        state = raw["collection_state"]
        if state not in {"ACTIVE", "PAUSED", "ARCHIVED"}:
            raise ValueError("DP519_WORKLOAD_COLLECTION_STATE_INVALID")
        values = raw["rows"]
        if not isinstance(values, list) or len(values) > MAX_MEMBERS:
            raise ValueError("DP519_WORKLOAD_SCOPE_TOO_LARGE")
        rows = []
        last = ""
        for row in values:
            expected = {
                "content_id",
                "membership_state",
                "content_rights",
                "processing_state",
                "capture_count",
                "capture_id",
                "capture_state",
                "capture_rights",
                "capture_hold",
                "capture_sha256",
                "passage_count",
                "statement_candidate_count",
                "claim_candidate_count",
                "held_statement_count",
                "held_claim_count",
                "rights_leaf_count",
                "rights_leaf_status",
                "rights_ready",
            }
            if not isinstance(row, dict) or set(row) != expected:
                raise ValueError("DP519_WORKLOAD_ROW_INVALID")
            content_id = _id(row["content_id"])
            if content_id <= last or row["membership_state"] != "INCLUDED":
                raise ValueError("DP519_WORKLOAD_MEMBERSHIP_INVALID")
            last = content_id
            for key in (
                "capture_count",
                "passage_count",
                "statement_candidate_count",
                "claim_candidate_count",
                "held_statement_count",
                "held_claim_count",
                "rights_leaf_count",
            ):
                _count(row[key])
            if row["capture_id"] is not None:
                _id(row["capture_id"])
            status, reason = _status(row, state)
            rows.append(
                {
                    "content_id": content_id,
                    "capture_id": row["capture_id"],
                    "content_rights_state": _allow_state(
                        row["content_rights"], _RIGHTS_STATES
                    ),
                    "current_rights_state": (
                        "MISSING"
                        if row["rights_leaf_count"] == 0
                        else "AMBIGUOUS"
                        if row["rights_leaf_count"] != 1
                        else _allow_state(row["rights_leaf_status"], _RIGHTS_STATES)
                    ),
                    "capture_state": _allow_state(
                        row["capture_state"], _CAPTURE_STATES
                    ),
                    "capture_hold_state": _allow_state(
                        row["capture_hold"], _CAPTURE_HOLDS
                    ),
                    "capture_count": row["capture_count"],
                    "passage_count": row["passage_count"],
                    "statement_candidates": row["statement_candidate_count"],
                    "claim_candidates": row["claim_candidate_count"],
                    "state": status,
                    "reason": reason,
                }
            )
        fingerprint = hashlib.sha256(
            json.dumps([state, values], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if previous is not None:
            if fingerprint != previous["fingerprint"]:
                raise ValueError("DP519_WORKLOAD_SNAPSHOT_CHANGED")
            if previous["after"] not in {row["content_id"] for row in rows}:
                raise ValueError("DP519_WORKLOAD_CURSOR_INVALID")
        page = [
            row
            for row in rows
            if previous is None or row["content_id"] > previous["after"]
        ]
        visible = page[:limit]
        more = len(page) > limit
        return {
            "version": VERSION,
            "collection_id": collection_id,
            "collection_state": state,
            "total_members": len(rows),
            "blocked_members": sum(row["state"] == "BLOCKED" for row in rows),
            "review_only_members": sum(row["state"] == "REVIEW_ONLY" for row in rows),
            "capture_count": sum(row["capture_count"] for row in rows),
            "passage_count": sum(row["passage_count"] for row in rows),
            "statement_candidate_count": sum(
                row["statement_candidates"] for row in rows
            ),
            "claim_candidate_count": sum(row["claim_candidates"] for row in rows),
            "rows": visible,
            "blocked_queue": [
                {
                    "content_id": row["content_id"],
                    "reason": row["reason"],
                    "next_action": _ACTIONS[row["reason"]],
                }
                for row in visible
                if row["state"] == "BLOCKED"
            ],
            "next_cursor": _cursor_write(
                collection_id, visible[-1]["content_id"], fingerprint
            )
            if visible and more
            else None,
            "dispatch_authorized": False,
            "publication_authority": False,
            "image_approval_authority": False,
            "text_review_authority": False,
            "source_rights_attested": False,
        }


__all__ = ["IsolatedStudioOperatorWorkloadPg", "VERSION"]
