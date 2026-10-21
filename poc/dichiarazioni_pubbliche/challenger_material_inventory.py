"""DP-229: canonical *untrusted* challenger-material inventory from private SQL.

This deliberately does not issue a challenger review or mark research complete.
The SQL reads the entire current claim-evidence candidate set, including rejected
and pending rows, so newly discovered material invalidates previous fingerprints.
An approval in the generic review ledger is not an independently attested
challenger review, and metadata is never promoted to accepted rationale.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol


INVENTORY_VERSION = "challenger-material-inventory-v3"


class QueryRuntime(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


@dataclass(frozen=True)
class ChallengerMaterialInventory:
    claim_id: str
    material_sha256: str
    candidates: int
    pending_or_unverified: int
    counterevidence_candidates: int
    blockers: tuple[str, ...]
    version: str = INVENTORY_VERSION

    @property
    def publication_authority(self) -> bool:
        return False


def _validate_row(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("CHALLENGER_MATERIAL_ROW_INVALID")
    required = {
        "evidence_id", "retrieval_version", "retrieval_method", "relation_candidate", "status",
        "content_sha256", "rights_status", "record_status",
        "independence_group", "review_events", "statement_cutoff",
        "publication_date", "valid_from", "valid_until", "reference_period", "rights_records",
        "canonical_url",
    }
    if set(value) != required:
        raise ValueError("CHALLENGER_MATERIAL_ROW_SCHEMA_INVALID")
    for key in ("evidence_id", "retrieval_version", "retrieval_method", "relation_candidate", "status"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError("CHALLENGER_MATERIAL_IDENTITY_INVALID")
    for key in ("statement_cutoff", "publication_date", "valid_from", "valid_until", "reference_period"):
        if value[key] is not None and not isinstance(value[key], str):
            raise ValueError("CHALLENGER_MATERIAL_TEMPORAL_SCOPE_INVALID")
    if value["canonical_url"] is not None and not isinstance(value["canonical_url"], str):
        raise ValueError("CHALLENGER_MATERIAL_SOURCE_URL_INVALID")
    if not isinstance(value["review_events"], list):
        raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
    if not isinstance(value["rights_records"], list):
        raise ValueError("CHALLENGER_SOURCE_RIGHTS_SNAPSHOT_INVALID")
    rights_keys = {
        "id", "subject_fingerprint", "source_family", "locator_kind", "locator_value",
        "rights_status", "rights_receipt_ref", "permitted_uses", "reviewed_at",
        "expires_at", "reviewer_ref", "policy_version", "supersedes_id",
        "expired", "review_in_future",
    }
    for rights in value["rights_records"]:
        if not isinstance(rights, dict) or set(rights) != rights_keys:
            raise ValueError("CHALLENGER_SOURCE_RIGHTS_SNAPSHOT_INVALID")
        if not all(isinstance(rights[k], str) and rights[k] for k in (
            "id", "subject_fingerprint", "source_family", "locator_kind", "locator_value",
            "rights_status", "policy_version",
        )) or not isinstance(rights["permitted_uses"], list):
            raise ValueError("CHALLENGER_SOURCE_RIGHTS_SNAPSHOT_INVALID")
        if not all(isinstance(code, str) for code in rights["permitted_uses"]):
            raise ValueError("CHALLENGER_SOURCE_RIGHTS_SNAPSHOT_INVALID")
        if any(rights[k] is not None and not isinstance(rights[k], str) for k in (
            "rights_receipt_ref", "reviewed_at", "expires_at", "reviewer_ref", "supersedes_id",
        )) or type(rights["expired"]) is not bool or type(rights["review_in_future"]) is not bool:
            raise ValueError("CHALLENGER_SOURCE_RIGHTS_SNAPSHOT_INVALID")
    for event in value["review_events"]:
        if not isinstance(event, dict) or set(event) != {
            "id", "action", "actor_ref", "reason", "metadata",
        }:
            raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
        if not all(
            isinstance(event[key], str) and event[key]
            for key in ("id", "action", "actor_ref")
        ) or (event["reason"] is not None and not isinstance(event["reason"], str)):
            raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
        if not isinstance(event["metadata"], dict):
            raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
    return value


def _review_matches_candidate(
    event: dict[str, object], claim_id: str, row: dict[str, object],
) -> bool:
    # The existing review writer concatenates three unconstrained text IDs
    # with '|'. Distinct (evidence, retrieval) pairs can therefore have the
    # same review_event.entity_id. Its stored structured metadata is needed
    # to check the actual review target rather than trusting that string.
    return event["metadata"] == {
        "claim_id": claim_id,
        "evidence_id": row["evidence_id"],
        "retrieval_version": row["retrieval_version"],
    }


def _current_source_rights(row: dict[str, object]) -> bool:
    """A scoped private-use receipt is required even for legacy CLEARED evidence.

    The rights registry is a source-use *record*, not an external authority.
    Caller-supplied license names and legacy evidence flags never make this a
    publication authorization. The exact current registry leaf is hashed.
    """
    records = row["rights_records"]
    assert isinstance(records, list)
    if len(records) != 1:
        return False
    rights = records[0]
    return (
        rights["rights_status"] == "CLEARED"
        and rights["locator_kind"] == "URL"
        and rights["locator_value"] == row["canonical_url"]
        and bool(rights["rights_receipt_ref"])
        and bool(rights["reviewer_ref"])
        and bool(rights["reviewed_at"])
        and not rights["expired"]
        and not rights["review_in_future"]
        and "CHALLENGER_PRIVATE_RESEARCH" in rights["permitted_uses"]
    )


def load_challenger_material_inventory(
    runtime: QueryRuntime, *, claim_id: str,
) -> ChallengerMaterialInventory:
    clean_claim = str(claim_id or "").strip()
    if not clean_claim or len(clean_claim) > 512:
        raise ValueError("CHALLENGER_MATERIAL_CLAIM_ID_INVALID")
    # A single SQL statement gives a transactionally consistent MVCC snapshot.
    # The append-only review ledger's entity id is the exact composite identity
    # used in ClaimEvidenceObservationStore.approve_claim_evidence_with_review.
    raw = runtime.run(
        """
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'evidence_id', link.evidence_id,
            'retrieval_version', link.retrieval_version,
            'retrieval_method', link.retrieval_method,
            'relation_candidate', link.relation_candidate,
            'status', link.status,
            'statement_cutoff', link.statement_cutoff,
            'content_sha256', evidence.content_sha256,
            'canonical_url', evidence.canonical_url,
            'publication_date', evidence.publication_date,
            'valid_from', evidence.valid_from,
            'valid_until', evidence.valid_until,
            'reference_period', evidence.reference_period,
            'rights_status', evidence.rights_status,
            'record_status', evidence.record_status,
            'independence_group', evidence.independence_group,
            'rights_records', COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'id', rights.id,
                    'subject_fingerprint', rights.subject_fingerprint,
                    'source_family', rights.source_family,
                    'locator_kind', rights.locator_kind,
                    'locator_value', rights.locator_value,
                    'rights_status', rights.rights_status,
                    'rights_receipt_ref', rights.rights_receipt_ref,
                    'permitted_uses', to_jsonb(rights.permitted_uses),
                    'reviewed_at', rights.reviewed_at,
                    'expires_at', rights.expires_at,
                    'reviewer_ref', rights.reviewer_ref,
                    'policy_version', rights.policy_version,
                    'supersedes_id', rights.supersedes_id,
                    'expired', rights.expires_at IS NOT NULL
                        AND rights.expires_at <= statement_timestamp(),
                    'review_in_future', rights.reviewed_at IS NOT NULL
                        AND rights.reviewed_at > statement_timestamp()
                ) ORDER BY rights.subject_fingerprint, rights.id)
                FROM private_source_rights_record rights
                WHERE rights.evidence_id = link.evidence_id
                  AND NOT EXISTS (
                      SELECT 1 FROM private_source_rights_record successor
                      WHERE successor.supersedes_id = rights.id
                  )
            ), '[]'::jsonb),
            'review_events', COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'id', event.id, 'action', event.action,
                    'actor_ref', event.actor_ref, 'reason', event.reason,
                    'metadata', event.metadata
                ) ORDER BY event.created_at, event.id)
                FROM review_event event
                WHERE event.entity_type = 'CLAIM_EVIDENCE_CANDIDATE'
                  AND event.entity_id = link.claim_id || '|' ||
                      link.evidence_id || '|' || link.retrieval_version
            ), '[]'::jsonb)
        ) ORDER BY link.evidence_id, link.retrieval_version)::text, '[]')
        FROM claim_evidence_candidate link
        JOIN evidence ON evidence.id = link.evidence_id
        WHERE link.claim_id = :'claim_id';
        """,
        claim_id=clean_claim,
    )
    try:
        rows = json.loads(raw or "[]")
    except (TypeError, ValueError) as exc:
        raise ValueError("CHALLENGER_MATERIAL_SNAPSHOT_INVALID") from exc
    if not isinstance(rows, list):
        raise ValueError("CHALLENGER_MATERIAL_SNAPSHOT_INVALID")
    canonical = [_validate_row(row) for row in rows]
    identities = [(row["evidence_id"], row["retrieval_version"]) for row in canonical]
    if len(identities) != len(set(identities)):
        raise ValueError("CHALLENGER_MATERIAL_DUPLICATE_IDENTITY")
    canonical.sort(key=lambda row: (str(row["evidence_id"]), str(row["retrieval_version"])))
    material = {"version": INVENTORY_VERSION, "claim_id": clean_claim, "rows": canonical}
    digest = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    # An APPROVED generic review is not a challenger approval. Additionally,
    # legacy/misbound generic reviews and evidence without a canonical digest
    # must never be summarized as verified material. The DB allows NULL hashes.
    missing_provenance = any(
        not isinstance(row["content_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]) is None
        for row in canonical
    )
    misbound_review = any(
        not _review_matches_candidate(event, clean_claim, row)
        for row in canonical for event in row["review_events"]
    )
    pending = sum(
        row["status"] != "APPROVED"
        # A historical approval cannot outweigh a later reject/quarantine.
        or not row["review_events"]
        or row["review_events"][-1]["action"] != "APPROVED"
        or row["record_status"] != "ACTIVE"
        or row["rights_status"] not in {"CLEARED", "PUBLIC_DOMAIN", "OPEN_LICENSE"}
        or not _current_source_rights(row)
        or not isinstance(row["content_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]) is None
        or any(
            not _review_matches_candidate(event, clean_claim, row)
            for event in row["review_events"]
        )
        for row in canonical
    )
    blockers = [
        "CHALLENGER_RESEARCH_COMPLETION_AUTHORITY_UNAVAILABLE",
        "CHALLENGER_INDEPENDENT_REVIEW_AUTHORITY_UNAVAILABLE",
        "CHALLENGER_RATIONALE_APPROVAL_UNAVAILABLE",
    ]
    if not canonical:
        blockers.append("CHALLENGER_MATERIAL_EMPTY")
    if pending:
        blockers.append("CHALLENGER_MATERIAL_PENDING_OR_UNVERIFIED")
    if any(not _current_source_rights(row) for row in canonical):
        blockers.append("CHALLENGER_SOURCE_RIGHTS_NOT_CURRENT")
    if missing_provenance:
        blockers.append("CHALLENGER_MATERIAL_PROVENANCE_INCOMPLETE")
    if misbound_review:
        blockers.append("CHALLENGER_REVIEW_BINDING_MISMATCH")
    return ChallengerMaterialInventory(
        claim_id=clean_claim,
        material_sha256=digest,
        candidates=len(canonical),
        pending_or_unverified=pending,
        counterevidence_candidates=sum(
            row["relation_candidate"] in {"CONTRADICT", "CONTEXT", "UPDATE"}
            for row in canonical
        ),
        blockers=tuple(blockers),
    )


__all__ = ["INVENTORY_VERSION", "ChallengerMaterialInventory", "load_challenger_material_inventory"]
