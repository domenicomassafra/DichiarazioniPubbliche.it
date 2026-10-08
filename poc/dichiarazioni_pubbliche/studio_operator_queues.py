"""Metadata-only, bounded private collection and discovery inbox readers.

No source URL, title, query text, raw passage, secret, evidence body, or
review/moderation mutation enters the receipt. The results are persisted
database rows, not reconstructed counters or fixture display values.
"""

from __future__ import annotations

import json
import re
from typing import Any

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

STUDIO_QUEUES_VERSION = "studio-operator-queues-v1"
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_COLLECTION_STATES = frozenset({"ACTIVE", "PAUSED", "ARCHIVED"})
_HIT_DISPOSITIONS = frozenset({
    "NEW_CONTENT", "EXISTING_CONTENT", "DUPLICATE_WITHIN_RUN", "HOST_LIMIT",
    "RESULT_LIMIT", "OUTSIDE_DATE_WINDOW", "REJECTED_POLICY",
    "AMBIGUOUS_CONTENT_IDENTITY",
})

_COLLECTIONS_SQL = """
SELECT json_build_object(
    'id', collection.id, 'status', collection.status,
    'included_content_count', (
        SELECT count(*) FROM research_collection_content member
        WHERE member.collection_id=collection.id AND member.status='INCLUDED'
    )
)::text
FROM research_collection collection
WHERE collection.id > :'after_id'
ORDER BY collection.id ASC
LIMIT :'limit'::integer;
""".strip()

_DISCOVERY_SQL = """
SELECT json_build_object(
    'id', hit.id, 'run_id', hit.run_id,
    'disposition', hit.disposition, 'content_id', hit.content_id,
    'reason_code', hit.reason_code
)::text
FROM research_discovery_hit hit
WHERE hit.id > :'after_id'
ORDER BY hit.id ASC
LIMIT :'limit'::integer;
""".strip()

# The membership is the *authority boundary*: do not browse a Content merely
# because the caller knows its ID. Neither query selects URLs, labels, bodies,
# raw claims, provider receipts, private metadata or review decisions.
_MEMBERS_SQL = """
SELECT json_build_object(
    'collection_id', collection.id, 'state', collection.status,
    'members', (
        SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.content_id), '[]'::json)
        FROM (
            SELECT member.content_id, content.source_id, content.rights_status,
                   content.processing_status
            FROM research_collection_content member
            JOIN content_item content ON content.id=member.content_id
            WHERE member.collection_id=collection.id
              AND member.status='INCLUDED'
              AND member.content_id > :'after_id'
            ORDER BY member.content_id
            LIMIT :'limit'::integer
        ) selected
    )
)::text
FROM research_collection collection
WHERE collection.id=:'collection_id';
""".strip()

_MEMBER_DETAIL_SQL = """
SELECT json_build_object(
    'collection_id', member.collection_id,
    'content_id', content.id, 'source_id', content.source_id,
    'source_exists', (source.id IS NOT NULL),
    'collection_state', collection.status,
    'rights_status', content.rights_status,
    'processing_status', content.processing_status,
    'capture_count', (SELECT count(*) FROM content_capture capture WHERE capture.content_id=content.id),
    'passage_count', (SELECT count(*) FROM passage p WHERE p.content_id=content.id),
    'statement_candidate_count', (
        SELECT count(*) FROM statement_candidate candidate WHERE candidate.content_id=content.id
    ),
    'claim_candidate_count', (
        SELECT count(*) FROM claim_candidate candidate WHERE candidate.content_id=content.id
    ),
    'atomic_claim_count', (SELECT count(*) FROM atomic_claim claim WHERE claim.content_id=content.id),
    'claims', (
        SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.id), '[]'::json)
        FROM (
            SELECT claim.id, claim.speaker_person_id, claim.claim_type
            FROM atomic_claim claim
            WHERE claim.content_id=content.id AND claim.id > :'after_claim_id'
            ORDER BY claim.id
            LIMIT :'limit'::integer
        ) selected
    )
)::text
FROM research_collection_content member
JOIN research_collection collection ON collection.id=member.collection_id
JOIN content_item content ON content.id=member.content_id
LEFT JOIN source source ON source.id=content.source_id
WHERE member.collection_id=:'collection_id'
  AND member.content_id=:'content_id'
  AND member.status='INCLUDED';
""".strip()


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"STUDIO_QUEUE_{label}_INVALID")
    return value


def _pagination(limit: int, after_id: str | None) -> tuple[int, str]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 30:
        raise ValueError("STUDIO_QUEUE_LIMIT_INVALID")
    return limit, _id(after_id, "CURSOR") if after_id is not None else ""


def _parse(raw: str, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(raw, str) or len(raw) > 30_000:
        raise ValueError("STUDIO_QUEUE_RESULT_SIZE_INVALID")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) > limit or any(not isinstance(row, dict) for row in rows):
        raise ValueError("STUDIO_QUEUE_RESULT_COUNT_INVALID")
    return rows


def _record(raw: str) -> dict[str, Any] | None:
    if not isinstance(raw, str) or len(raw) > 30_000:
        raise ValueError("STUDIO_QUEUE_RECORD_SIZE_INVALID")
    if not raw.strip():
        return None
    lines = raw.splitlines()
    if len(lines) != 1:
        raise ValueError("STUDIO_QUEUE_RECORD_COUNT_INVALID")
    parsed = json.loads(lines[0])
    if not isinstance(parsed, dict):
        raise ValueError("STUDIO_QUEUE_RECORD_INVALID")
    return parsed


def _safe_state(value: object, label: str) -> str:
    if not isinstance(value, str) or not _REASON.fullmatch(value):
        raise ValueError(f"STUDIO_QUEUE_{label}_INVALID")
    return value


def _count(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"STUDIO_QUEUE_{label}_INVALID")
    return value


def _optional_id(value: object, label: str) -> str | None:
    return _id(value, label) if value is not None else None


class StudioOperatorQueues(PsqlRuntime):
    def list_collections(self, *, limit: int = 20, after_id: str | None = None) -> dict[str, object]:
        limit, cursor = _pagination(limit, after_id)
        try:
            rows = _parse(self.run(_COLLECTIONS_SQL, limit=limit, after_id=cursor), limit=limit)
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_COLLECTION_ROWS_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_COLLECTION_STORE_UNAVAILABLE") from None
        output: list[dict[str, object]] = []
        last_id = cursor
        for row in rows:
            item_id = _id(row.get("id"), "COLLECTION_ID")
            state = row.get("status")
            count = row.get("included_content_count")
            if (
                item_id <= last_id
                or state not in _COLLECTION_STATES
                or not isinstance(count, int) or isinstance(count, bool)
                or count < 0
            ):
                raise ValueError("STUDIO_COLLECTION_ROW_INVALID")
            output.append({"id": item_id, "state": state, "included_content_count": count})
            last_id = item_id
        return {
            "contract_version": STUDIO_QUEUES_VERSION,
            "private_only": True, "publication_authority": False,
            "results": output, "next_after_id": last_id if len(output) == limit else None,
        }

    def list_discovery(self, *, limit: int = 20, after_id: str | None = None) -> dict[str, object]:
        limit, cursor = _pagination(limit, after_id)
        try:
            rows = _parse(self.run(_DISCOVERY_SQL, limit=limit, after_id=cursor), limit=limit)
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_DISCOVERY_ROWS_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_DISCOVERY_STORE_UNAVAILABLE") from None
        output: list[dict[str, str | None]] = []
        last_id = cursor
        for row in rows:
            item_id = _id(row.get("id"), "DISCOVERY_ID")
            disposition = row.get("disposition")
            reason = row.get("reason_code")
            if item_id <= last_id or disposition not in _HIT_DISPOSITIONS:
                raise ValueError("STUDIO_DISCOVERY_ROW_INVALID")
            if reason is not None and (
                not isinstance(reason, str) or not _REASON.fullmatch(reason)
            ):
                raise ValueError("STUDIO_DISCOVERY_REASON_INVALID")
            output.append({
                "id": item_id,
                "run_id": _id(row.get("run_id"), "RUN_ID"),
                "content_id": _id(row["content_id"], "CONTENT_ID") if row.get("content_id") else None,
                "disposition": disposition,
                "reason_code": reason,
            })
            last_id = item_id
        return {
            "contract_version": STUDIO_QUEUES_VERSION,
            "private_only": True, "publication_authority": False,
            "results": output, "next_after_id": last_id if len(output) == limit else None,
        }

    def list_collection_members(
        self, *, collection_id: str, limit: int = 20, after_id: str | None = None,
    ) -> dict[str, object]:
        collection_id = _id(collection_id, "COLLECTION_ID")
        limit, cursor = _pagination(limit, after_id)
        try:
            row = _record(self.run(
                _MEMBERS_SQL, collection_id=collection_id, limit=limit, after_id=cursor,
            ))
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_COLLECTION_MEMBERS_RESULT_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_COLLECTION_MEMBERS_STORE_UNAVAILABLE") from None
        if row is None:
            raise ValueError("STUDIO_COLLECTION_NOT_FOUND")
        if row.get("collection_id") != collection_id or row.get("state") not in _COLLECTION_STATES:
            raise ValueError("STUDIO_COLLECTION_MEMBERS_AUTHORITY_MISMATCH")
        members = row.get("members")
        if not isinstance(members, list) or len(members) > limit:
            raise ValueError("STUDIO_COLLECTION_MEMBERS_LIMIT_INVALID")
        output: list[dict[str, object]] = []
        last_id = cursor
        for member in members:
            if not isinstance(member, dict):
                raise ValueError("STUDIO_COLLECTION_MEMBER_INVALID")
            content_id = _id(member.get("content_id"), "CONTENT_ID")
            if content_id <= last_id:
                raise ValueError("STUDIO_COLLECTION_MEMBER_ORDER_INVALID")
            rights = _safe_state(member.get("rights_status"), "RIGHTS_STATUS")
            processing = _safe_state(member.get("processing_status"), "PROCESSING_STATUS")
            source_id = _optional_id(member.get("source_id"), "SOURCE_ID")
            output.append({
                "content_id": content_id, "source_id": source_id,
                "rights_status": rights, "processing_status": processing,
                "capture_authorized": False, "publication_authority": False,
            })
            last_id = content_id
        return {
            "contract_version": STUDIO_QUEUES_VERSION,
            "collection_id": collection_id, "state": row["state"],
            "private_only": True, "publication_authority": False,
            "results": output, "next_after_id": last_id if len(output) == limit else None,
        }

    def inspect_collection_member(
        self, *, collection_id: str, content_id: str,
        limit: int = 20, after_claim_id: str | None = None,
    ) -> dict[str, object]:
        collection_id = _id(collection_id, "COLLECTION_ID")
        content_id = _id(content_id, "CONTENT_ID")
        limit, cursor = _pagination(limit, after_claim_id)
        try:
            row = _record(self.run(
                _MEMBER_DETAIL_SQL, collection_id=collection_id,
                content_id=content_id, limit=limit, after_claim_id=cursor,
            ))
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_COLLECTION_MEMBER_DETAIL_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_COLLECTION_MEMBER_STORE_UNAVAILABLE") from None
        if row is None:
            raise ValueError("STUDIO_COLLECTION_MEMBER_NOT_FOUND")
        if (
            row.get("collection_id") != collection_id
            or row.get("content_id") != content_id
            or row.get("collection_state") not in _COLLECTION_STATES
            or not isinstance(row.get("source_exists"), bool)
        ):
            raise ValueError("STUDIO_COLLECTION_MEMBER_SCOPE_INVALID")
        source = _optional_id(row.get("source_id"), "SOURCE_ID")
        if bool(source) != row["source_exists"]:
            raise ValueError("STUDIO_COLLECTION_MEMBER_SOURCE_MISMATCH")
        rights = _safe_state(row.get("rights_status"), "RIGHTS_STATUS")
        processing = _safe_state(row.get("processing_status"), "PROCESSING_STATUS")
        counts = {
            key: _count(row.get(key), key.upper())
            for key in ("capture_count", "passage_count", "statement_candidate_count",
                        "claim_candidate_count", "atomic_claim_count")
        }
        claims = row.get("claims")
        if not isinstance(claims, list) or len(claims) > limit:
            raise ValueError("STUDIO_COLLECTION_MEMBER_CLAIMS_INVALID")
        output_claims = []
        last_id = cursor
        for claim in claims:
            if not isinstance(claim, dict):
                raise ValueError("STUDIO_COLLECTION_MEMBER_CLAIM_INVALID")
            claim_id = _id(claim.get("id"), "CLAIM_ID")
            if claim_id <= last_id:
                raise ValueError("STUDIO_COLLECTION_MEMBER_CLAIM_ORDER_INVALID")
            output_claims.append({
                "id": claim_id,
                "speaker_person_id": _optional_id(claim.get("speaker_person_id"), "PERSON_ID"),
                "claim_type": _safe_state(claim.get("claim_type"), "CLAIM_TYPE"),
                "publication_authority": False,
            })
            last_id = claim_id
        blockers = []
        if rights != "APPROVED":
            blockers.append("CONTENT_RIGHTS_NOT_APPROVED")
        if processing != "READY":
            blockers.append("CONTENT_NOT_READY")
        if counts["capture_count"] == 0:
            blockers.append("NO_PERSISTED_CAPTURE")
        if counts["passage_count"] == 0:
            blockers.append("NO_PERSISTED_PASSAGE")
        if counts["statement_candidate_count"] == 0:
            blockers.append("NO_STATEMENT_CANDIDATE")
        if counts["claim_candidate_count"] == 0:
            blockers.append("NO_CLAIM_CANDIDATE")
        # Publication permissions are *never* inferred from these counts.
        blockers.append("REVIEW_AUTHORITY_NOT_EVALUATED")
        return {
            "contract_version": STUDIO_QUEUES_VERSION,
            "collection_id": collection_id, "collection_state": row["collection_state"],
            "content_id": content_id, "source_id": source, "source_exists": row["source_exists"],
            "rights_status": rights, "processing_status": processing, "counts": counts,
            "claims": output_claims, "next_after_claim_id": last_id if len(output_claims) == limit else None,
            "blockers": blockers, "private_only": True,
            "capture_authorized": False, "publication_authority": False,
        }


__all__ = ["STUDIO_QUEUES_VERSION", "StudioOperatorQueues"]
