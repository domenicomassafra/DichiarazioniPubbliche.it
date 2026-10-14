"""Private DP-314 research-worklist diff and stale-input fence.

Pure metadata reconciliation of two *caller-supplied* worklist snapshots.
An SHA is a change detector, NOT an authenticated attestation, rights grant,
source verification, reviewer identity, finding or publication authority.
No source body, transcript, provider, database or network I/O exists here.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .requirement_research_batch_v1 import (
    PrivateResearchBatch, ResearchGapItem, VERSION as BATCH_VERSION, _digest,
)

VERSION = "private-verification-research-delta-v1"
_SHA = re.compile(r"^[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_CLAIMS = 32
_MAX_EVIDENCE = 512
_STATES = frozenset({"NON_FACTUAL", "NOT_CHECKED", "NOT_CHECKABLE_PROFILE_UNAVAILABLE",
                     "CHECKED_INSUFFICIENT_EVIDENCE", "UNRESOLVED_CONFLICT", "CHECKABLE_PENDING"})
_ACTIONS = frozenset({
    "NO_FACTUAL_VERIFICATION", "PROFILE_AUTHORITY_REQUIRED", "START_RESEARCH_RUN",
    "REVIEW_CONFLICT_WITH_CHALLENGER", "DETERMINISTIC_VERIFICATION_REQUIRED",
    "RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", "DEFINE_LEGAL_JURISDICTION",
    "ESTABLISH_INDEPENDENT_PROVENANCE", "RESOLVE_DATE_OR_SCOPE_CONFLICT",
    "INDEPENDENT_SOURCE_REVIEW_REQUIRED", "REVIEW_PRIMARY_RECORD",
    "REVIEW_INDEPENDENT_RECORD", "REVIEW_PRIMARY_STATISTICS",
    "REVIEW_PRIMARY_LEGAL_RECORD", "REVIEW_PRIMARY_TEXT",
})


@dataclass(frozen=True)
class ResearchClaimChange:
    claim_id: str
    before_state: str
    after_state: str
    before_preflight_sha256: str
    after_preflight_sha256: str
    lost_eligible_ids: tuple[str, ...]
    gained_eligible_ids: tuple[str, ...]
    current_next_steps: tuple[str, ...]
    actions: tuple[str, ...]
    verdict: None = None
    finding_authority: bool = False
    publication_authority: bool = False


@dataclass(frozen=True)
class PrivateResearchDelta:
    version: str
    status: str
    before_sha256: str
    after_sha256: str
    changed_claims: tuple[ResearchClaimChange, ...]
    added_claim_ids: tuple[str, ...]
    removed_claim_ids: tuple[str, ...]
    recheck_claim_ids: tuple[str, ...]
    snapshot_sha256: str
    verdict: None = None
    private_only: bool = True
    source_body_count: int = 0
    provider_calls: int = 0
    authoritative_source_approval: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


def _validate(batch: PrivateResearchBatch) -> None:
    if not isinstance(batch, PrivateResearchBatch):
        raise ValueError("DELTA_BATCH_INVALID")
    if (batch.version != BATCH_VERSION or not isinstance(batch.items, tuple)
            or len(batch.items) > _MAX_CLAIMS
            or not isinstance(batch.snapshot_sha256, str)
            or not _SHA.fullmatch(batch.snapshot_sha256)
            or type(batch.source_body_count) is not int or batch.source_body_count != 0
            or type(batch.provider_calls) is not int or batch.provider_calls != 0
            or batch.private_only is not True or batch.verdict is not None
            or batch.authoritative_source_approval is not False
            or batch.finding_authority is not False
            or batch.publication_authority is not False):
        raise ValueError("DELTA_BATCH_INVALID")
    if not all(isinstance(row, ResearchGapItem) for row in batch.items):
        raise ValueError("DELTA_BATCH_INVALID")
    ids = [row.claim_id for row in batch.items]
    if (ids != sorted(set(ids)) or
            any(not isinstance(identifier, str) or not _ID.fullmatch(identifier)
                for identifier in ids) or
            type(batch.claim_count) is not int or batch.claim_count != len(ids)):
        raise ValueError("DELTA_BATCH_INVALID")
    eligible = 0
    excluded = 0
    for row in batch.items:
        if (not isinstance(row.claim_kind, str) or not _ID.fullmatch(row.claim_kind)
                or not isinstance(row.state, str) or row.state not in _STATES
                or not isinstance(row.preflight_sha256, str)
                or not _SHA.fullmatch(row.preflight_sha256)
                or row.verdict is not None
                or row.source_approval_authority is not False
                or row.finding_authority is not False
                or row.publication_authority is not False):
            raise ValueError("DELTA_BATCH_INVALID")
        for values in (row.reason_codes, row.eligible_evidence_ids,
                       row.excluded_evidence_ids, row.next_steps):
            if (not isinstance(values, tuple) or len(values) > _MAX_EVIDENCE
                    or any(not isinstance(value, str) or not _ID.fullmatch(value)
                           for value in values) or values != tuple(sorted(set(values)))):
                raise ValueError("DELTA_BATCH_INVALID")
        if set(row.eligible_evidence_ids) & set(row.excluded_evidence_ids):
            raise ValueError("DELTA_BATCH_INVALID")
        if any(action not in _ACTIONS for action in row.next_steps):
            raise ValueError("DELTA_BATCH_INVALID")
        eligible += len(row.eligible_evidence_ids)
        excluded += len(row.excluded_evidence_ids)
    if (type(batch.eligible_evidence_count) is not int
            or type(batch.excluded_evidence_count) is not int
            or batch.eligible_evidence_count != eligible
            or batch.excluded_evidence_count != excluded
            or eligible + excluded > _MAX_EVIDENCE
            or batch.snapshot_sha256 != _digest({
                "version": BATCH_VERSION,
                "items": [asdict(row) for row in batch.items],
            })):
        raise ValueError("DELTA_BATCH_INVALID")


def compare_research_batches(
    previous: PrivateResearchBatch,
    current: PrivateResearchBatch,
    expected_previous_sha256: str,
    expected_current_sha256: str,
) -> PrivateResearchDelta:
    """Require two exact metadata fingerprints; report *review needs*, no actions.

    The caller must supply separately retained expected hashes. Supplying
    hashes copied from the same untrusted input cannot authenticate identity.
    A disappearing claim is a RECHECK, never implied withdrawal authorization.
    """
    _validate(previous)
    _validate(current)
    if (not isinstance(expected_previous_sha256, str)
            or not isinstance(expected_current_sha256, str)
            or not _SHA.fullmatch(expected_previous_sha256)
            or not _SHA.fullmatch(expected_current_sha256)
            or previous.snapshot_sha256 != expected_previous_sha256
            or current.snapshot_sha256 != expected_current_sha256):
        raise ValueError("DELTA_PIN_MISMATCH")

    older = {row.claim_id: row for row in previous.items}
    newer = {row.claim_id: row for row in current.items}
    added = tuple(sorted(newer.keys() - older.keys()))
    removed = tuple(sorted(older.keys() - newer.keys()))
    changes: list[ResearchClaimChange] = []
    for claim_id in sorted(older.keys() & newer.keys()):
        before, after = older[claim_id], newer[claim_id]
        if before == after:
            continue
        lost = tuple(sorted(set(before.eligible_evidence_ids)
                            - set(after.eligible_evidence_ids)))
        gained = tuple(sorted(set(after.eligible_evidence_ids)
                              - set(before.eligible_evidence_ids)))
        actions = {"REVALIDATE_CHANGED_INPUT"}
        if lost:
            # Loss might be revocation, changed approval, missing metadata,
            # time drift or a removed row; this does NOT assert provider revoke.
            actions.add("REVIEW_EVIDENCE_ELIGIBILITY_LOSS")
        if gained:
            actions.add("REVIEW_NEW_EVIDENCE_ELIGIBILITY")
        if before.claim_kind != after.claim_kind:
            actions.add("REVIEW_CHANGED_REQUIREMENT_PROFILE")
        if before.state != after.state:
            actions.add("REVIEW_CHANGED_PREFLIGHT_STATE")
        changes.append(ResearchClaimChange(
            claim_id=claim_id, before_state=before.state, after_state=after.state,
            before_preflight_sha256=before.preflight_sha256,
            after_preflight_sha256=after.preflight_sha256,
            lost_eligible_ids=lost, gained_eligible_ids=gained,
            current_next_steps=after.next_steps,
            actions=tuple(sorted(actions)),
        ))
    recheck = tuple(sorted(set(added) | set(removed) |
                           {item.claim_id for item in changes}))
    material = {
        "version": VERSION,
        "before_sha256": previous.snapshot_sha256,
        "after_sha256": current.snapshot_sha256,
        "changed_claims": [asdict(row) for row in changes],
        "added_claim_ids": added,
        "removed_claim_ids": removed,
        "recheck_claim_ids": recheck,
    }
    return PrivateResearchDelta(
        version=VERSION, status="RECHECK_REQUIRED" if recheck else "UNCHANGED",
        before_sha256=previous.snapshot_sha256,
        after_sha256=current.snapshot_sha256,
        changed_claims=tuple(changes), added_claim_ids=added,
        removed_claim_ids=removed, recheck_claim_ids=recheck,
        snapshot_sha256=_digest(material),
    )
