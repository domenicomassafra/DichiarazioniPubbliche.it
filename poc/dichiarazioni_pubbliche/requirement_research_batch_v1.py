"""DP-314 private bounded source-research planning from requirement profiles.

No provider I/O, source-body ingestion, fact conclusion, recommendation about
people, rights grant, challenger impersonation, or publication pathway. Even
an operator-labelled APPROVED source is a *claim*, not an attested approval.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping

from .verification_requirements_v1 import (
    RequirementClaim, RequirementEvidence,
    preflight_verification_requirements, select_requirement_profile,
)


VERSION = "private-verification-research-batch-v1"
_MAX_CLAIMS = 32
_MAX_EVIDENCE = 512


@dataclass(frozen=True)
class ResearchGapItem:
    claim_id: str
    claim_kind: str
    state: str
    preflight_sha256: str
    reason_codes: tuple[str, ...]
    eligible_evidence_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...]
    next_steps: tuple[str, ...]
    verdict: None = None
    source_approval_authority: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


@dataclass(frozen=True)
class PrivateResearchBatch:
    version: str
    items: tuple[ResearchGapItem, ...]
    snapshot_sha256: str
    claim_count: int
    eligible_evidence_count: int
    excluded_evidence_count: int
    source_body_count: int = 0
    provider_calls: int = 0
    verdict: None = None
    private_only: bool = True
    authoritative_source_approval: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()).hexdigest()


def _actions(claim: RequirementClaim, evidence: tuple[RequirementEvidence, ...],
             state: str, reason_codes: tuple[str, ...],
             eligible_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Plan missing *review*, not semantic/factual inference or source scraping."""
    if claim.claim_kind == "NON_FACTUAL" or state == "NON_FACTUAL":
        return ("NO_FACTUAL_VERIFICATION",)
    if state == "NOT_CHECKABLE_PROFILE_UNAVAILABLE":
        return ("PROFILE_AUTHORITY_REQUIRED",)
    profile = select_requirement_profile(claim.claim_kind)
    actions: set[str] = set()
    # `NOT_CHECKED` is a run-state only. Existing held evidence must still
    # produce visible source-rights, role and independence remediation tasks,
    # never a misleading single "start" action.
    if state == "NOT_CHECKED":
        actions.add("START_RESEARCH_RUN")
    if state == "UNRESOLVED_CONFLICT":
        actions.add("REVIEW_CONFLICT_WITH_CHALLENGER")
    if state == "CHECKABLE_PENDING":
        actions.add("DETERMINISTIC_VERIFICATION_REQUIRED")
    eligible_rows = tuple(row for row in evidence if row.evidence_id in eligible_ids)
    eligible_roles = {row.evidence_role for row in eligible_rows}
    if profile is not None:
        actions.update(f"REVIEW_{role}" for role in profile.required_roles
                       if role not in eligible_roles)
    if any(row.source_use_status != "APPROVED" or row.evidence_review_status != "APPROVED"
           for row in evidence):
        actions.add("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD")
    if claim.claim_kind == "DOCUMENTARY_LEGAL_STATUS" and claim.jurisdiction_ref is None:
        actions.add("DEFINE_LEGAL_JURISDICTION")
    if any(code in reason_codes for code in (
        "CROSS_ROOT_IDENTICAL_BYTES", "INDEPENDENT_ORIGINAL_ROOT_MISSING",
        "INDEPENDENT_SOURCE_FAMILY_MISSING", "INDEPENDENT_ROLE_SOURCE_PAIR_MISSING",
    )):
        actions.add("ESTABLISH_INDEPENDENT_PROVENANCE")
    if any(code in reason_codes for code in (
        "POST_STATEMENT_EVIDENCE_ONLY", "AFTER_REVIEW_CUTOFF", "JURISDICTION_MISMATCH",
    )):
        actions.add("RESOLVE_DATE_OR_SCOPE_CONFLICT")
    # Always make an unsupported state actionable, without claiming it can
    # be resolved automatically or by reading private source bodies.
    if not actions:
        actions.add("INDEPENDENT_SOURCE_REVIEW_REQUIRED")
    return tuple(sorted(actions))


def build_research_batch(
    claims: tuple[RequirementClaim, ...],
    evidence_by_claim: Mapping[str, tuple[RequirementEvidence, ...]],
    *, max_claims: int = _MAX_CLAIMS,
    max_evidence: int = _MAX_EVIDENCE,
) -> PrivateResearchBatch:
    if (not isinstance(claims, tuple) or not isinstance(evidence_by_claim, Mapping)
            or not isinstance(max_claims, int) or isinstance(max_claims, bool)
            or not isinstance(max_evidence, int) or isinstance(max_evidence, bool)
            or max_claims < 1 or max_claims > _MAX_CLAIMS
            or max_evidence < 1 or max_evidence > _MAX_EVIDENCE
            or len(claims) > max_claims):
        raise ValueError("BATCH_TOO_LARGE")
    if any(not isinstance(claim, RequirementClaim) for claim in claims):
        raise ValueError("BATCH_INVALID_CLAIM")
    identifiers = [claim.claim_id for claim in claims]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("BATCH_DUPLICATE_CLAIM")
    if (not all(isinstance(key, str) for key in evidence_by_claim)
            or set(evidence_by_claim) != set(identifiers)):
        raise ValueError("BATCH_UNEXPECTED_CLAIM")
    if any(not isinstance(rows, tuple) or
           any(not isinstance(row, RequirementEvidence) for row in rows)
           for rows in evidence_by_claim.values()):
        raise ValueError("BATCH_INVALID_EVIDENCE")
    if sum(len(rows) for rows in evidence_by_claim.values()) > max_evidence:
        raise ValueError("BATCH_TOO_LARGE")

    items: list[ResearchGapItem] = []
    for claim in sorted(claims, key=lambda item: item.claim_id):
        evidence = evidence_by_claim[claim.claim_id]
        preflight = preflight_verification_requirements(claim, evidence)
        item = ResearchGapItem(
            claim_id=claim.claim_id,
            claim_kind=claim.claim_kind,
            state=preflight.state,
            preflight_sha256=preflight.snapshot_sha256,
            reason_codes=preflight.reason_codes,
            eligible_evidence_ids=preflight.eligible_evidence_ids,
            excluded_evidence_ids=preflight.excluded_evidence_ids,
            next_steps=_actions(claim, evidence, preflight.state, preflight.reason_codes,
                                preflight.eligible_evidence_ids),
        )
        items.append(item)

    snapshot = _digest({"version": VERSION, "items": [asdict(row) for row in items]})
    return PrivateResearchBatch(
        version=VERSION, items=tuple(items), snapshot_sha256=snapshot,
        claim_count=len(items),
        eligible_evidence_count=sum(len(row.eligible_evidence_ids) for row in items),
        excluded_evidence_count=sum(len(row.excluded_evidence_ids) for row in items),
    )
