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
from dataclasses import dataclass
from typing import Protocol


INVENTORY_VERSION = "challenger-material-inventory-v1"


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
        "evidence_id", "retrieval_version", "relation_candidate", "status",
        "content_sha256", "rights_status", "record_status",
        "independence_group", "review_events",
    }
    if set(value) != required:
        raise ValueError("CHALLENGER_MATERIAL_ROW_SCHEMA_INVALID")
    for key in ("evidence_id", "retrieval_version", "relation_candidate", "status"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError("CHALLENGER_MATERIAL_IDENTITY_INVALID")
    if not isinstance(value["review_events"], list):
        raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
    for event in value["review_events"]:
        if not isinstance(event, dict) or set(event) != {"id", "action"}:
            raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
        if not all(isinstance(event[key], str) and event[key] for key in ("id", "action")):
            raise ValueError("CHALLENGER_MATERIAL_EVENTS_INVALID")
    return value


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
            'relation_candidate', link.relation_candidate,
            'status', link.status,
            'content_sha256', evidence.content_sha256,
            'rights_status', evidence.rights_status,
            'record_status', evidence.record_status,
            'independence_group', evidence.independence_group,
            'review_events', COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'id', event.id, 'action', event.action
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
    # Even a genuine generic APPROVED event does not grant permission to reclassify
    # a relation as LIMITATION, approve a rationale or complete challenger research.
    pending = sum(
        row["status"] != "APPROVED"
        # A historical approval cannot outweigh a later reject/quarantine.
        or not row["review_events"]
        or row["review_events"][-1]["action"] != "APPROVED"
        or row["record_status"] != "ACTIVE"
        or row["rights_status"] not in {"CLEARED", "PUBLIC_DOMAIN", "OPEN_LICENSE"}
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
