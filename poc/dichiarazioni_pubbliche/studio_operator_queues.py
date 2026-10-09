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
from dichiarazioni_pubbliche.studio_discovery_detail import present_discovery_detail
from dichiarazioni_pubbliche.studio_discovery_triage_reader import read_triage_history

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

_DISCOVERY_DETAIL_SQL = """
SELECT json_build_object(
    'id', hit.id, 'run_id', run.id, 'attempt_id', attempt.id,
    'query_id', hit.query_id, 'manifest_id', manifest.id,
    'collection_id', manifest.collection_id, 'content_id', hit.content_id,
    'disposition', hit.disposition, 'reason_code', hit.reason_code,
    'source_family', hit.source_family,
    'collection_status', collection.status, 'manifest_status', manifest.status,
    'run_status', run.status, 'attempt_status', attempt.status,
    'lineage_ok', COALESCE(
        attempt.run_id=run.id AND attempt.query_id=hit.query_id
        AND discovery_query.manifest_id=manifest.id, false),
    'manifest_digest_ok', (run.manifest_sha256=manifest.manifest_sha256),
    'family_ok', COALESCE(
        manifest.source_families ? hit.source_family
        AND discovery_query.source_families ? hit.source_family, false),
    'adapter_ok', COALESCE(discovery_query.adapter_ids ? attempt.adapter_id, false),
    'url_ok', COALESCE(content.canonical_url=hit.canonical_url, false),
    'membership_status', member.status,
    'capture_authorized', COALESCE(
        member.metadata->'capture_authorized'='true'::jsonb, false),
    'content_rights_status', content.rights_status
)::text
FROM research_discovery_hit hit
JOIN research_discovery_run run ON run.id=hit.run_id
JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
JOIN research_collection collection ON collection.id=manifest.collection_id
LEFT JOIN research_discovery_attempt attempt ON attempt.id=hit.attempt_id
LEFT JOIN research_discovery_query discovery_query ON discovery_query.id=hit.query_id
LEFT JOIN content_item content ON content.id=hit.content_id
LEFT JOIN research_collection_content member
  ON member.collection_id=collection.id AND member.content_id=hit.content_id
WHERE hit.id=:'hit_id' AND manifest.collection_id=:'collection_id';
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

_CLAIM_PROVENANCE_SQL = """
SELECT json_build_object(
    'collection_id', member.collection_id,
    'collection_state', collection.status,
    'content_id', content.id, 'claim_id', claim.id,
    'speaker_person_id', claim.speaker_person_id,
    'rights_status', content.rights_status,
    'processing_status', content.processing_status,
    'capture_count', (SELECT count(*) FROM content_capture capture WHERE capture.content_id=content.id),
    'passage_count', (SELECT count(*) FROM passage p WHERE p.content_id=content.id),
    'provenance_count', (
        SELECT count(*) FROM claim_text_provenance provenance WHERE provenance.claim_id=claim.id
    ),
    'provenance', (
        SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.id), '[]'::json)
        FROM (
            SELECT provenance.id, provenance.claim_id, provenance.content_id,
                   provenance.person_id, provenance.status, provenance.selector_type,
                   provenance.quote_sha256, provenance.source_sha256,
                   provenance.start_char, provenance.end_char, provenance.attribution_method
            FROM claim_text_provenance provenance
            WHERE provenance.claim_id=claim.id AND provenance.id > :'after_id'
            ORDER BY provenance.id
            LIMIT :'limit'::integer
        ) selected
    )
)::text
FROM research_collection_content member
JOIN research_collection collection ON collection.id=member.collection_id
JOIN content_item content ON content.id=member.content_id
JOIN atomic_claim claim ON claim.content_id=content.id
WHERE member.collection_id=:'collection_id'
  AND member.content_id=:'content_id'
  AND member.status='INCLUDED'
  AND claim.id=:'claim_id';
""".strip()

_PROVENANCE_STATES = frozenset({"CANDIDATE", "APPROVED", "REJECTED", "SUPERSEDED"})
_SELECTOR_TYPES = frozenset({"TEXT_QUOTE_HASH", "TEXT_POSITION_HASH"})
_ATTRIBUTION_METHODS = frozenset({
    "SOURCE_BYLINE", "SOURCE_QUOTE", "ACCOUNT_OWNER",
    "OFFICIAL_RECORD", "MANUAL_REVIEW",
})
_HASH = re.compile(r"^[0-9a-f]{64}$")


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


def _hash(value: object, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"STUDIO_QUEUE_{label}_INVALID")
    return value


def _position(value: object, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"STUDIO_QUEUE_{label}_INVALID")
    return value


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

    def inspect_discovery(self, *, collection_id: str, hit_id: str) -> dict[str, object]:
        """Inspect persisted run/attempt/query/manifest provenance for one scoped Hit."""
        collection_id = _id(collection_id, "COLLECTION_ID")
        hit_id = _id(hit_id, "DISCOVERY_ID")
        try:
            row = _record(self.run(
                _DISCOVERY_DETAIL_SQL, collection_id=collection_id, hit_id=hit_id,
            ))
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_DISCOVERY_DETAIL_RESULT_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_DISCOVERY_DETAIL_STORE_UNAVAILABLE") from None
        if row is None:
            raise ValueError("STUDIO_DISCOVERY_DETAIL_NOT_FOUND")
        if row.get("id") != hit_id or row.get("collection_id") != collection_id:
            raise ValueError("STUDIO_DISCOVERY_DETAIL_SCOPE_MISMATCH")
        return present_discovery_detail(row)

    def inspect_discovery_triage(
        self, *, collection_id: str, hit_id: str,
        limit: int = 20, after_revision: int = 0,
    ) -> dict[str, object]:
        """Read scoped annotation history; no identity, approval or mutation."""
        return read_triage_history(
            self, collection_id=collection_id, hit_id=hit_id,
            limit=limit, after_revision=after_revision,
        )

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

    def inspect_claim_provenance(
        self, *, collection_id: str, content_id: str, claim_id: str,
        limit: int = 20, after_id: str | None = None,
    ) -> dict[str, object]:
        """Private attribution history scoped to an INCLUDED Content's exact claim."""
        collection_id = _id(collection_id, "COLLECTION_ID")
        content_id = _id(content_id, "CONTENT_ID")
        claim_id = _id(claim_id, "CLAIM_ID")
        limit, cursor = _pagination(limit, after_id)
        try:
            row = _record(self.run(
                _CLAIM_PROVENANCE_SQL, collection_id=collection_id,
                content_id=content_id, claim_id=claim_id, limit=limit, after_id=cursor,
            ))
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_PROVENANCE_ROWS_INVALID") from None
        except Exception:
            raise RuntimeError("STUDIO_PROVENANCE_STORE_UNAVAILABLE") from None
        if row is None:
            raise ValueError("STUDIO_PROVENANCE_CLAIM_NOT_IN_COLLECTION")
        if (
            row.get("collection_id") != collection_id
            or row.get("content_id") != content_id
            or row.get("claim_id") != claim_id
            or row.get("collection_state") not in _COLLECTION_STATES
        ):
            raise ValueError("STUDIO_PROVENANCE_CLAIM_BINDING_MISMATCH")
        speaker = _optional_id(row.get("speaker_person_id"), "SPEAKER_ID")
        rights = _safe_state(row.get("rights_status"), "RIGHTS_STATUS")
        processing = _safe_state(row.get("processing_status"), "PROCESSING_STATUS")
        captures = _count(row.get("capture_count"), "CAPTURE_COUNT")
        passages = _count(row.get("passage_count"), "PASSAGE_COUNT")
        count = _count(row.get("provenance_count"), "PROVENANCE_COUNT")
        values = row.get("provenance")
        if not isinstance(values, list) or len(values) > limit or len(values) > count:
            raise ValueError("STUDIO_PROVENANCE_PAGE_INVALID")
        last_id = cursor
        records: list[dict[str, object]] = []
        for value in values:
            if not isinstance(value, dict):
                raise ValueError("STUDIO_PROVENANCE_RECORD_INVALID")
            record_id = _id(value.get("id"), "RECORD_ID")
            if (
                record_id <= last_id
                or value.get("claim_id") != claim_id
                or value.get("content_id") != content_id
                or speaker is None or value.get("person_id") != speaker
                or value.get("status") not in _PROVENANCE_STATES
                or value.get("selector_type") not in _SELECTOR_TYPES
                or value.get("attribution_method") not in _ATTRIBUTION_METHODS
            ):
                raise ValueError("STUDIO_PROVENANCE_RECORD_BINDING_INVALID")
            quote_hash = _hash(value.get("quote_sha256"), "QUOTE_HASH")
            source_hash = _hash(value.get("source_sha256"), "SOURCE_HASH", optional=True)
            start = _position(value.get("start_char"), "START_CHAR")
            end = _position(value.get("end_char"), "END_CHAR")
            if (
                (start is None) != (end is None)
                or (start is not None and (end is None or end <= start))
                or (value["selector_type"] == "TEXT_POSITION_HASH" and start is None)
            ):
                raise ValueError("STUDIO_PROVENANCE_SELECTOR_INVALID")
            records.append({
                "id": record_id, "status": value["status"],
                "selector_type": value["selector_type"],
                "quote_sha256": quote_hash, "source_sha256": source_hash,
                "start_char": start, "end_char": end,
                "attribution_method": value["attribution_method"],
                "rights_clearance": False, "review_authority_evaluated": False,
            })
            last_id = record_id
        blockers = []
        if count == 0:
            blockers.append("CLAIM_TEXT_PROVENANCE_MISSING")
        if rights != "APPROVED":
            blockers.append("CONTENT_RIGHTS_NOT_APPROVED")
        if processing != "READY":
            blockers.append("CONTENT_NOT_READY")
        if captures == 0:
            blockers.append("NO_PERSISTED_CAPTURE")
        if passages == 0:
            blockers.append("NO_PERSISTED_PASSAGE")
        blockers.append("ATTRIBUTION_REVIEW_AUTHORITY_NOT_REEVALUATED")
        return {
            "contract_version": STUDIO_QUEUES_VERSION,
            "collection_id": collection_id, "content_id": content_id,
            "claim_id": claim_id, "speaker_person_id": speaker,
            "collection_state": row["collection_state"],
            "rights_status": rights, "processing_status": processing,
            "provenance_record_count": count,
            "records": records, "next_after_id": last_id if len(records) == limit else None,
            "blockers": blockers, "private_only": True,
            "rights_clearance": False, "review_authority_evaluated": False,
            "publication_authority": False,
        }


__all__ = ["STUDIO_QUEUES_VERSION", "StudioOperatorQueues"]
