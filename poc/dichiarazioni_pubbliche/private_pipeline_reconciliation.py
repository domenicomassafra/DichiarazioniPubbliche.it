"""Read-only reconciliation of real private discovery/capture/candidate lineage.

Only IDs, status codes and counts leave PostgreSQL; private text, URLs, provider
output, identities and evidence never leave the database. Not an extraction,
speaker-review, match-approval or publication entrypoint.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

VERSION = "private-pipeline-reconciliation-v1"
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_ITEMS = 25
MAX_CANDIDATES_PER_MEMBER = 24

# Join by persisted foreign keys, not by text resemblance or inferred source.
# Latest Capture is only a freshness comparison; older Capture links remain
# historical and must NOT be silently reused after a new observed version.
_CHAIN_SQL = """
BEGIN READ ONLY;
WITH members AS (
  SELECT member.content_id, member.status AS member_status,
         member.metadata->'capture_authorized' = 'true'::jsonb AS capture_authorized,
         collection.status AS collection_status,
         content.source_id, content.rights_status AS content_rights,
         source.id IS NOT NULL AS source_exists,
         (SELECT capture.id FROM content_capture capture
          WHERE capture.content_id=content.id
          ORDER BY capture.observed_at DESC, capture.id DESC LIMIT 1) AS latest_capture_id,
         (SELECT count(*) FROM content_capture capture
          WHERE capture.content_id=content.id) AS capture_count,
         (SELECT count(*) FROM passage passage
          WHERE passage.content_id=content.id) AS passage_count,
         (SELECT count(*) FROM research_discovery_hit hit
          WHERE hit.content_id=content.id
            AND hit.canonical_url=content.canonical_url
            AND hit.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
            AND hit.source_id=content.source_id
         ) AS discovery_count,
         (SELECT count(*) FROM claim_candidate candidate
          WHERE candidate.content_id=content.id) AS candidate_count,
         EXISTS (
           SELECT 1 FROM private_source_rights_record rights
           WHERE rights.content_id=content.id
             AND rights.locator_kind='URL'
             AND rights.locator_value=content.canonical_url
             AND rights.rights_status='CLEARED'
             AND rights.record_visibility='PRIVATE'
             AND rights.reviewed_at IS NOT NULL
             AND rights.reviewer_ref IS NOT NULL
             AND rights.rights_receipt_ref IS NOT NULL
             AND (rights.expires_at IS NULL OR rights.expires_at > statement_timestamp())
             AND rights.evidence_id IS NULL AND rights.passage_id IS NULL
             AND rights.transcript_segment_id IS NULL
             AND rights.canonical_segment_id IS NULL
             AND rights.permitted_uses @> ARRAY[
               'RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE'
             ]::text[]
             AND EXISTS (
               SELECT 1 FROM research_discovery_hit hit
               WHERE hit.content_id=content.id
                 AND hit.canonical_url=content.canonical_url
                 AND hit.source_family=rights.source_family
                 AND hit.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
                 AND hit.source_id=content.source_id
             )
             AND NOT EXISTS (
               SELECT 1 FROM private_source_rights_record successor
               WHERE successor.supersedes_id=rights.id
             )
         ) AS rights_current
  FROM research_collection_content member
  JOIN research_collection collection ON collection.id=member.collection_id
  JOIN content_item content ON content.id=member.content_id
  LEFT JOIN source source ON source.id=content.source_id
  WHERE member.collection_id=:'collection_id'
    AND member.content_id > :'after_id'
  ORDER BY member.content_id ASC
  LIMIT :'limit'::integer
)
SELECT json_build_object(
  'content_id', member.content_id, 'source_id', member.source_id,
  'source_exists', member.source_exists,
  'collection_status', member.collection_status,
  'member_status', member.member_status,
  'capture_authorized', COALESCE(member.capture_authorized,false),
  'content_rights', member.content_rights,
  'rights_current', member.rights_current,
  'latest_capture_id', member.latest_capture_id,
  'capture_count', member.capture_count,
  'passage_count', member.passage_count,
  'discovery_count', member.discovery_count,
  'candidate_count', member.candidate_count,
  'candidate_id', candidate.id,
  'candidate_status', candidate.status,
  'candidate_promoted', candidate.promoted_claim_id IS NOT NULL,
  'statement_id', statement.id,
  'statement_status', statement.status,
  'speaker_present', statement.speaker_person_id IS NOT NULL,
  'statement_hash', statement.statement_text_hash,
  'passage_link_count', COALESCE(link.link_count,0),
  'parent_passage_id', candidate.metadata->>'parent_passage_id',
  'passage_id', passage.id,
  'passage_hash', passage.text_sha256,
  'selector_type', passage.selector_type,
  'capture_id', capture.id,
  'capture_status', capture.status,
  'capture_rights', capture.rights_status,
  'capture_hold', capture.hold_status,
  'capture_retention', capture.retention_class,
  'body_available', capture.body_ref IS NOT NULL,
  'match_run_id', match_run.id,
  'match_status', match_run.status,
  'match_result_id', match_result.id,
  'match_class', match_result.match_class,
  'match_disposition', match_result.disposition,
  'match_result_status', match_result.status,
  'target_content_id', target_content.id,
  'target_source_id', target_content.source_id
)::text
FROM members member
LEFT JOIN LATERAL (
  SELECT candidate.*
  FROM claim_candidate candidate
  WHERE candidate.content_id=member.content_id
  ORDER BY candidate.id
  LIMIT :'candidate_limit'::integer
) candidate ON true
LEFT JOIN statement_candidate statement
  ON statement.id=candidate.statement_candidate_id
  AND statement.content_id=member.content_id
LEFT JOIN LATERAL (
  SELECT count(*) AS link_count, min(binding.passage_id) AS passage_id
  FROM statement_candidate_passage binding
  WHERE binding.statement_candidate_id=statement.id
    AND binding.content_id=member.content_id
) link ON true
LEFT JOIN passage passage ON passage.id=link.passage_id
  AND passage.content_id=member.content_id
LEFT JOIN content_capture capture ON capture.id=passage.capture_id
  AND capture.content_id=member.content_id
LEFT JOIN LATERAL (
  SELECT run.id, run.status
  FROM candidate_match_run run
  WHERE run.claim_candidate_id=candidate.id
  ORDER BY run.created_at DESC, run.id DESC LIMIT 1
) match_run ON true
LEFT JOIN LATERAL (
  SELECT result.id, result.match_class, result.disposition,
         result.status, result.target_claim_candidate_id,
         result.target_atomic_claim_id
  FROM candidate_match_result result
  WHERE result.run_id=match_run.id
  ORDER BY result.rank, result.id LIMIT 1
) match_result ON true
LEFT JOIN claim_candidate other_candidate ON
  other_candidate.id=match_result.target_claim_candidate_id
LEFT JOIN atomic_claim other_claim ON
  other_claim.id=match_result.target_atomic_claim_id
LEFT JOIN content_item target_content ON
  target_content.id=COALESCE(other_candidate.content_id, other_claim.content_id)
ORDER BY member.content_id, candidate.id NULLS FIRST;
COMMIT;
""".strip()


def _id(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("PRIVATE_CHAIN_ID_INVALID")
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("PRIVATE_CHAIN_COUNT_INVALID")
    return value


def _status(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value):
        raise ValueError("PRIVATE_CHAIN_STATUS_INVALID")
    return value


def _analyze(row: Mapping[str, Any]) -> dict[str, object]:
    """Do not infer rights, source identity, attribution, match or publication."""
    content_id = _id(row.get("content_id"))
    source_id = _id(row.get("source_id"), optional=True)
    capture_id = _id(row.get("capture_id"), optional=True)
    latest_capture_id = _id(row.get("latest_capture_id"), optional=True)
    passage_id = _id(row.get("passage_id"), optional=True)
    candidate_id = _id(row.get("candidate_id"), optional=True)
    statement_id = _id(row.get("statement_id"), optional=True)
    match_run_id = _id(row.get("match_run_id"), optional=True)
    match_result_id = _id(row.get("match_result_id"), optional=True)
    target_content_id = _id(row.get("target_content_id"), optional=True)
    target_source_id = _id(row.get("target_source_id"), optional=True)
    blockers: list[str] = []
    for key in ("source_exists", "capture_authorized", "rights_current",
                "candidate_promoted", "speaker_present", "body_available"):
        if type(row.get(key)) is not bool:
            raise ValueError("PRIVATE_CHAIN_BOOLEAN_INVALID")
    for key in ("capture_count", "passage_count", "candidate_count", "passage_link_count",
                "discovery_count"):
        _count(row.get(key))
    if row.get("collection_status") != "ACTIVE" or row.get("member_status") != "INCLUDED":
        blockers.append("COLLECTION_OR_MEMBERSHIP_INACTIVE")
    if not source_id or row["source_exists"] is not True:
        blockers.append("SOURCE_IDENTITY_NOT_PERSISTED")
    if not row["capture_authorized"]:
        blockers.append("CAPTURE_MEMBERSHIP_NOT_AUTHORIZED")
    if _count(row["discovery_count"]) == 0:
        blockers.append("DISCOVERY_PROVENANCE_NOT_PERSISTED")
    if row.get("content_rights") != "CLEARED" or not row["rights_current"]:
        blockers.append("RIGHTS_HOLD_CURRENT_GRANT_MISSING")
    if latest_capture_id is None:
        blockers.append("NO_CAPTURE")
    if _count(row["passage_count"]) == 0:
        blockers.append("NO_PASSAGE")
    if candidate_id is None:
        blockers.append("NO_CLAIM_CANDIDATE")
    if _count(row["candidate_count"]) > MAX_CANDIDATES_PER_MEMBER:
        blockers.append("CANDIDATE_PAGE_TRUNCATED_REQUIRES_PAGINATION")
    if candidate_id is not None:
        if statement_id is None:
            blockers.append("STATEMENT_BINDING_MISSING")
        if _count(row["passage_link_count"]) != 1 or passage_id is None:
            blockers.append("PASSAGE_BINDING_NOT_ATOMIC")
        if row.get("parent_passage_id") not in (None, passage_id):
            blockers.append("CANDIDATE_PARENT_PASSAGE_MISMATCH")
        if capture_id is None:
            blockers.append("CAPTURE_BINDING_MISSING_OR_MEDIA")
        elif capture_id != latest_capture_id:
            blockers.append("CAPTURE_VERSION_STALE")
        if row.get("selector_type") != "TEXT_POSITION":
            blockers.append("WRITTEN_SELECTOR_UNVERIFIED")
        phrase_hash, passage_hash = row.get("statement_hash"), row.get("passage_hash")
        if not (isinstance(phrase_hash, str) and isinstance(passage_hash, str)
                and _HASH.fullmatch(phrase_hash) and phrase_hash == passage_hash):
            blockers.append("STATEMENT_PASSAGE_EXACT_HASH_UNVERIFIED")
        if (row.get("capture_status") != "CAPTURED"
                or row.get("capture_rights") != "CLEARED"
                or row.get("capture_hold") != "NONE"
                or row.get("capture_retention") not in
                {"EPHEMERAL", "DURABLE_PRIVATE", "DURABLE_PROVENANCE"}
                or not row["body_available"]):
            blockers.append("CAPTURE_PRIVATE_INTEGRITY_OR_RIGHTS_HOLD")
        if row.get("candidate_status") not in {"CANDIDATE", "DUPLICATE"}:
            blockers.append("CANDIDATE_NOT_PENDING_REVIEW")
        if row["candidate_promoted"]:
            blockers.append("CANDIDATE_ALREADY_PROMOTED")
    if match_result_id is not None and match_run_id is None:
        blockers.append("MATCH_RUN_BINDING_MISSING")
    if match_run_id is not None and row.get("match_status") != "COMPLETED":
        blockers.append("MATCH_RUN_NOT_COMPLETED")
    if match_result_id is not None and row.get("match_result_status") != "CANDIDATE":
        blockers.append("MATCH_RESULT_NOT_PENDING")
    match_class = row.get("match_class")
    if match_class is not None and match_class not in {
        "DUPLICATE_EXTRACTION", "SAME_PROPOSITION", "RELATED", "DIFFERENT", "UNCERTAIN",
    }:
        raise ValueError("PRIVATE_CHAIN_MATCH_CLASS_INVALID")
    if match_result_id is not None and match_class is None:
        blockers.append("MATCH_CLASS_MISSING")
    eligible = bool(candidate_id is not None and not blockers)
    flags = ["SPEAKER_ATTRIBUTION_NOT_REVIEWED", "PUBLICATION_NOT_AUTHORIZED"]
    if match_run_id is None:
        flags.append("MATCH_NOT_RUN")
    else:
        flags.append("MATCH_CURRENTNESS_AND_REVIEW_REQUIRED")
    if match_class == "UNCERTAIN":
        flags.append("UNCERTAIN_MATCH_REQUIRES_HUMAN_REVIEW")
    if row["speaker_present"]:
        flags.append("SPEAKER_ID_IS_NOT_ATTRIBUTION_PROOF")
    flags.append("CAPTURE_BYTES_AND_SELECTOR_REVALIDATION_REQUIRED")
    cross_source_match = bool(
        match_result_id and match_run_id and row.get("match_status") == "COMPLETED"
        and row.get("match_result_status") == "CANDIDATE"
        and match_class in {"DUPLICATE_EXTRACTION", "SAME_PROPOSITION", "RELATED", "UNCERTAIN"}
        and target_content_id and target_content_id != content_id
        and source_id and target_source_id and source_id != target_source_id
    )
    if "DISCOVERY_PROVENANCE_NOT_PERSISTED" in blockers or "SOURCE_IDENTITY_NOT_PERSISTED" in blockers:
        next_step = "REVIEW_DISCOVERY_SOURCE_BINDING"
    elif "RIGHTS_HOLD_CURRENT_GRANT_MISSING" in blockers:
        next_step = "REVIEW_CURRENT_PRIVATE_RIGHTS"
    elif "CAPTURE_MEMBERSHIP_NOT_AUTHORIZED" in blockers or "COLLECTION_OR_MEMBERSHIP_INACTIVE" in blockers:
        next_step = "REVIEW_COLLECTION_CAPTURE_SCOPE"
    elif "NO_CAPTURE" in blockers:
        next_step = "PRIVATE_CAPTURE_BATCH_REQUIRES_OPERATOR"
    elif "NO_PASSAGE" in blockers:
        next_step = "INSPECT_PARSER_AND_CAPTURE"
    elif "NO_CLAIM_CANDIDATE" in blockers:
        next_step = "PRIVATE_EXTRACTION_BATCH_REQUIRES_OPERATOR_AND_PROVIDER_GRANT"
    else:
        next_step = "PRIVATE_STUDIO_CANDIDATE_REVIEW" if eligible else "REPAIR_PRIVATE_CANDIDATE_LINEAGE"
    return {
        "content_id": content_id, "source_id": source_id,
        "discovery_count": row["discovery_count"],
        "capture_count": row["capture_count"],
        "passage_count": row["passage_count"],
        "candidate_count": row["candidate_count"],
        "latest_capture_id": latest_capture_id, "capture_id": capture_id,
        "passage_id": passage_id, "statement_id": statement_id,
        "candidate_id": candidate_id,
        "match_run_id": match_run_id, "match_result_id": match_result_id,
        "match_class": match_class, "target_content_id": target_content_id if match_result_id else None,
        "cross_source_persisted_match_unreviewed": cross_source_match,
        "private_review_queue_eligible": eligible,
        "state": ("REVIEW_READY_PRIVATE_NOT_APPROVED" if eligible else "HOLD_PRIVATE"),
        "next_private_step": next_step,
        "blockers": blockers, "review_warnings": flags,
        "publication_authority": False, "promotion_authority": False,
        "review_authority": False,
    }


def reconcile_rows(rows: list[Mapping[str, Any]], *, limit: int) -> dict[str, object]:
    if type(limit) is not int or not 1 <= limit <= MAX_ITEMS:
        raise ValueError("PRIVATE_CHAIN_LIMIT_INVALID")
    if len(rows) > limit * MAX_CANDIDATES_PER_MEMBER:
        raise ValueError("PRIVATE_CHAIN_ROW_BOUNDS_EXCEEDED")
    results: list[dict[str, object]] = []
    previous: tuple[str, str] | None = None
    distinct: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("PRIVATE_CHAIN_ROW_INVALID")
        item = _analyze(row)
        key = (str(item["content_id"]), str(item["candidate_id"] or ""))
        if previous is not None and key <= previous:
            raise ValueError("PRIVATE_CHAIN_ORDER_OR_DUPLICATE_INVALID")
        previous = key
        distinct.add(key[0])
        results.append(item)
    if len(distinct) > limit:
        raise ValueError("PRIVATE_CHAIN_MEMBER_BOUNDS_EXCEEDED")
    return {
        "contract_version": VERSION, "private_only": True,
        "publication_authority": False, "promotion_authority": False,
        "review_authority": False, "contents": len(distinct),
        "items": results,
        "candidate_pagination_required": any(
            item["candidate_count"] > MAX_CANDIDATES_PER_MEMBER for item in results
        ),
    }


class PrivatePipelineReconciliationStore(PsqlRuntime):
    def read_collection(self, *, collection_id: str, limit: int = 20,
                        after_content_id: str | None = None) -> dict[str, object]:
        _id(collection_id)
        if type(limit) is not int or not 1 <= limit <= MAX_ITEMS:
            raise ValueError("PRIVATE_CHAIN_LIMIT_INVALID")
        cursor = _id(after_content_id, optional=True) or ""
        try:
            raw = self.run(
                _CHAIN_SQL, collection_id=collection_id, after_id=cursor,
                limit=limit, candidate_limit=MAX_CANDIDATES_PER_MEMBER,
            )
        except Exception:
            raise RuntimeError("PRIVATE_CHAIN_READ_ONLY_STORE_UNAVAILABLE") from None
        try:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip().startswith("{")]
            receipt = reconcile_rows(rows, limit=limit)
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("PRIVATE_CHAIN_PERSISTED_ROWS_INVALID") from None
        receipt["collection_id"] = collection_id
        receipt["next_after_content_id"] = (
            receipt["items"][-1]["content_id"] if receipt["contents"] == limit
            and receipt["items"] else None
        )
        return receipt
