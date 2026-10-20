"""DP-229: non-authoritative audit of separate AI challenger executions.

All inputs are *claimed* receipts until replayed from independently controlled
provider/identity/material authorities. This module cannot mint publication
readiness, authenticate source rights or execute a query on its own.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from dichiarazioni_pubbliche.challenger_material_inventory import ChallengerMaterialInventory
from dichiarazioni_pubbliche.challenger_research import (
    ChallengerResearchRequest,
    DEFAULT_MAX_CHALLENGER_ASSIGNMENTS,
    DEFAULT_MAX_CHALLENGER_COST_USD,
    DEFAULT_MAX_CHALLENGER_QUERIES,
    DEFAULT_MAX_CHALLENGER_RESULTS,
)
from dichiarazioni_pubbliche.countercase import CounterCasePacket


AI_CHALLENGER_AUDIT_VERSION = "challenger-ai-audit-v1"
_ROLES = frozenset({"COUNTEREVIDENCE", "LIMITATIONS"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 512


def _digest(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _unique_refs(values: object) -> bool:
    return (isinstance(values, tuple) and len(values) <= 1000
            and all(_present(v) for v in values)
            and len(values) == len(set(values)))


@dataclass(frozen=True)
class AiExecutionIdentity:
    """Recorded execution identity; self-declaration does not prove isolation."""

    actor_ref: str
    run_id: str
    session_id: str
    provider: str
    model_family: str
    model_id: str
    credential_fingerprint: str
    prompt_sha256: str
    conflict_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovedMaterialManifest:
    """Candidate manifest to reconcile with a separate canonical authority."""

    claim_id: str
    record_version: str
    current_material_sha256: str
    approved_evidence_ids: tuple[str, ...]
    primary_evidence_ids: tuple[str, ...]
    approval_receipt_id: str


@dataclass(frozen=True)
class AiResearchExecution:
    request_id: str
    receipt_id: str
    query_count: int
    result_count: int
    cost_usd: Decimal
    executed_assignment_ids: tuple[str, ...]
    examined_evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class AiChallengerReview:
    role: str
    identity: AiExecutionIdentity
    receipt_id: str
    claim_id: str
    record_version: str
    packet_id: str
    material_sha256: str
    research_receipt_id: str
    examined_evidence_ids: tuple[str, ...]
    counterexample_evidence_ids: tuple[str, ...]
    limitation_codes: tuple[str, ...]
    review_action: str  # EXAMINED or NEEDS_MORE; not truth or publication vote


@dataclass(frozen=True)
class ChallengerAiAudit:
    audit_sha256: str
    blockers: tuple[str, ...]
    status: str
    version: str = AI_CHALLENGER_AUDIT_VERSION

    @property
    def publication_authority(self) -> bool:
        return False


def audit_ai_challenger(
    *,
    generator: AiExecutionIdentity,
    manifest: ApprovedMaterialManifest,
    inventory: ChallengerMaterialInventory,
    packet: CounterCasePacket,
    research_request: ChallengerResearchRequest,
    execution: AiResearchExecution,
    reviews: tuple[AiChallengerReview, ...],
) -> ChallengerAiAudit:
    """Check claimed execution receipts against current input; never return READY.

    Complete-looking, in-memory receipts are *not* durable authority. A later
    writer must replay provider, source-rights and AI-identity attestations
    independently before binding them to the publication eligibility runtime.
    """

    blockers: list[str] = []

    def block(condition: bool, code: str) -> None:
        if condition:
            blockers.append(code)

    identities = (generator, *(review.identity for review in reviews))
    for identity in identities:
        block(not all(_present(getattr(identity, key)) for key in (
            "actor_ref", "run_id", "session_id", "provider", "model_family", "model_id",
        )) or not _digest(identity.credential_fingerprint)
              or not _digest(identity.prompt_sha256), "CHALLENGER_AI_IDENTITY_INCOMPLETE")
        block(not _unique_refs(identity.conflict_codes), "CHALLENGER_CONFLICT_DECLARATION_INVALID")
        block(bool(identity.conflict_codes), "CHALLENGER_REVIEW_CONFLICT_DECLARED")

    block(len(reviews) != len(_ROLES) or {r.role for r in reviews} != _ROLES,
          "CHALLENGER_AI_ROLE_COVERAGE_INCOMPLETE")
    for key in ("actor_ref", "run_id", "session_id", "credential_fingerprint", "model_family"):
        block(len({str(getattr(i, key)).strip().casefold() for i in identities}) != len(identities),
              "CHALLENGER_AI_EXECUTION_NOT_INDEPENDENT")
    block(len({i.prompt_sha256 for i in identities}) != len(identities),
          "CHALLENGER_AI_PROMPT_NOT_SEPARATE")

    block(not _present(manifest.claim_id) or not _present(manifest.record_version)
          or not _digest(manifest.current_material_sha256)
          or not _present(manifest.approval_receipt_id), "CHALLENGER_MANIFEST_INVALID")
    block(not _unique_refs(manifest.approved_evidence_ids)
          or not _unique_refs(manifest.primary_evidence_ids), "CHALLENGER_MANIFEST_EVIDENCE_INVALID")
    approved = set(manifest.approved_evidence_ids)
    primary = set(manifest.primary_evidence_ids)
    block(not primary or not primary <= approved,
          "CHALLENGER_PRIMARY_SOURCE_NOT_APPROVED")
    block(manifest.claim_id != packet.claim_id or manifest.claim_id != inventory.claim_id
          or manifest.claim_id != research_request.claim_id,
          "CHALLENGER_CLAIM_BINDING_MISMATCH")
    block(manifest.current_material_sha256 != inventory.material_sha256,
          "CHALLENGER_MATERIAL_STALE")
    block(inventory.pending_or_unverified > 0,
          "CHALLENGER_MATERIAL_PENDING_OR_UNVERIFIED")
    block(packet.status != "READY" or research_request.status != "READY",
          "CHALLENGER_RESEARCH_OR_PACKET_INCOMPLETE")
    block(
        type(research_request.max_queries) is not int
        or not 1 <= research_request.max_queries <= DEFAULT_MAX_CHALLENGER_QUERIES
        or type(research_request.max_results) is not int
        or not 1 <= research_request.max_results <= DEFAULT_MAX_CHALLENGER_RESULTS
        or len(research_request.assignment_ids) > DEFAULT_MAX_CHALLENGER_ASSIGNMENTS
        or not isinstance(research_request.cost_cap_usd, Decimal)
        or not research_request.cost_cap_usd.is_finite()
        or not 0 <= research_request.cost_cap_usd <= DEFAULT_MAX_CHALLENGER_COST_USD,
        "CHALLENGER_REQUEST_NATIVE_BUDGET_EXCEEDED",
    )
    block(not research_request.stop_conditions or not research_request.adapter_ids,
          "CHALLENGER_REQUEST_PERMISSIONS_INCOMPLETE")
    block(set(packet.evidence_ids) != approved,
          "CHALLENGER_PACKET_MATERIAL_MISMATCH")

    block(not _present(execution.request_id) or not _present(execution.receipt_id)
          or execution.request_id != research_request.request_id,
          "CHALLENGER_RESEARCH_RECEIPT_MISMATCH")
    block(not _unique_refs(execution.executed_assignment_ids)
          or set(execution.executed_assignment_ids) != set(research_request.assignment_ids),
          "CHALLENGER_ASSIGNMENT_EXECUTION_INCOMPLETE")
    block(not _unique_refs(execution.examined_evidence_ids)
          or not set(execution.examined_evidence_ids) <= approved,
          "CHALLENGER_RESEARCH_EVIDENCE_UNAPPROVED")
    block(type(execution.query_count) is not int or execution.query_count < 1
          or execution.query_count > research_request.max_queries,
          "CHALLENGER_EXECUTED_QUERY_BUDGET_INVALID")
    block(type(execution.result_count) is not int or execution.result_count < 0
          or execution.result_count > research_request.max_results,
          "CHALLENGER_EXECUTED_RESULT_BUDGET_INVALID")
    try:
        cost = Decimal(str(execution.cost_usd))
        valid_cost = cost.is_finite() and 0 <= cost <= research_request.cost_cap_usd
    except (InvalidOperation, ValueError):
        valid_cost = False
    block(not valid_cost, "CHALLENGER_EXECUTED_COST_BUDGET_INVALID")

    block(len({review.receipt_id for review in reviews}) != len(reviews)
          or execution.receipt_id in {review.receipt_id for review in reviews},
          "CHALLENGER_AI_REVIEW_RECEIPT_REUSED")
    for review in reviews:
        block(review.role not in _ROLES or review.review_action not in {"EXAMINED", "NEEDS_MORE"},
              "CHALLENGER_REVIEW_ACTION_INVALID")
        block(not _present(review.receipt_id) or review.claim_id != manifest.claim_id
              or review.record_version != manifest.record_version
              or review.packet_id != packet.packet_id
              or review.material_sha256 != inventory.material_sha256
              or review.research_receipt_id != execution.receipt_id,
              "CHALLENGER_AI_REVIEW_BINDING_MISMATCH")
        block(not _unique_refs(review.examined_evidence_ids)
              or not set(review.examined_evidence_ids) <= set(execution.examined_evidence_ids)
              or not primary.intersection(review.examined_evidence_ids),
              "CHALLENGER_AI_PRIMARY_SOURCE_NOT_EXAMINED")
        block(not set(packet.evidence_ids) <= set(review.examined_evidence_ids),
              "CHALLENGER_AI_MATERIAL_NOT_FULLY_EXAMINED")
        block(not _unique_refs(review.counterexample_evidence_ids)
              or not set(review.counterexample_evidence_ids) <= set(packet.contradicting_evidence_ids),
              "CHALLENGER_AI_COUNTEREXAMPLE_NOT_APPROVED")
        block(not _unique_refs(review.limitation_codes),
              "CHALLENGER_AI_LIMITATION_CODES_INVALID")
        block(review.review_action == "NEEDS_MORE", "CHALLENGER_AI_MORE_RESEARCH_REQUIRED")
        if packet.contradicting_evidence_ids:
            block(not set(packet.contradicting_evidence_ids) <= set(review.examined_evidence_ids),
                  "CHALLENGER_AI_COUNTEREVIDENCE_NOT_EXAMINED")
        block(not review.counterexample_evidence_ids and not review.limitation_codes,
              "CHALLENGER_AI_NO_COUNTEREXAMPLE_OR_LIMITATION")

    audit_material = {
        "version": AI_CHALLENGER_AUDIT_VERSION,
        "generator": asdict(generator),
        "manifest": asdict(manifest),
        "inventory": asdict(inventory),
        "packet": asdict(packet),
        "research_request": {**asdict(research_request), "cost_cap_usd": str(research_request.cost_cap_usd)},
        "execution": {**asdict(execution), "cost_usd": str(execution.cost_usd)},
        "reviews": [asdict(r) for r in sorted(reviews, key=lambda r: r.role)],
        "blockers": sorted(set(blockers)),
    }
    digest = hashlib.sha256(json.dumps(audit_material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ChallengerAiAudit(
        audit_sha256=digest,
        blockers=tuple(dict.fromkeys(blockers)),
        status="HOLD" if blockers else "NON_AUTHORITATIVE_REVIEW_CANDIDATE",
    )


__all__ = [
    "AI_CHALLENGER_AUDIT_VERSION", "AiExecutionIdentity", "ApprovedMaterialManifest",
    "AiResearchExecution", "AiChallengerReview", "ChallengerAiAudit", "audit_ai_challenger",
]
