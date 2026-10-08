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


__all__ = ["STUDIO_QUEUES_VERSION", "StudioOperatorQueues"]
