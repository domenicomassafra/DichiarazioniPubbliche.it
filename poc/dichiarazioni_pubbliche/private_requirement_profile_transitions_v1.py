"""Offline DP-314 requirement-profile transitions over typed private source metadata.

Inputs are untrusted operator declarations. Even APPROVED flags and canonical
hashes cannot attest original source rights, reviewer identity, factual truth,
or publication permission. This consumer schedules *manual* rechecks only.
No source bodies, network/provider calls, or persisted/public mutations.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import asdict, dataclass

from .requirement_research_batch_v1 import _digest
from .verification_requirements_v1 import (
    RequirementClaim,
    RequirementEvidence,
    RequirementPreflight,
    VerificationRequirementProfile,
    preflight_verification_requirements,
    select_requirement_profile,
)

SNAPSHOT_VERSION = "private-requirement-profile-snapshot-v1"
VERSION = "private-requirement-profile-transitions-v1"
_MAX_CLAIMS = 32
_MAX_EVIDENCE = 512
_SHA = re.compile(r"^[a-f0-9]{64}$")
_GATES = (
    "SOURCE_RIGHTS_EXTERNAL_ATTESTATION_REQUIRED",
    "EVIDENCE_REVIEW_EXTERNAL_ATTESTATION_REQUIRED",
    "FACT_AUTHORITY_EXTERNAL_ATTESTATION_REQUIRED",
    "PUBLICATION_EXTERNAL_APPROVAL_REQUIRED",
)


@dataclass(frozen=True)
class PrivateProfileRecord:
    claim: RequirementClaim
    evidence: tuple[RequirementEvidence, ...]
    profile: VerificationRequirementProfile | None
    preflight: RequirementPreflight
    snapshot_sha256: str


@dataclass(frozen=True)
class PrivateProfileSnapshot:
    version: str
    records: tuple[PrivateProfileRecord, ...]
    snapshot_sha256: str
    claim_count: int
    evidence_count: int
    source_body_count: int = 0
    provider_calls: int = 0
    verdict: None = None
    private_only: bool = True
    source_rights_attested: bool = False
    reviewer_attested: bool = False
    fact_authority: bool = False
    source_approval_authority: bool = False
    publication_authority: bool = False


@dataclass(frozen=True)
class ProfileTransitionStep:
    claim_id: str
    kind: str  # ADDED | REMOVED | CHANGED, never an approval
    before_state: str | None
    after_state: str | None
    before_required_roles: tuple[str, ...]
    after_required_roles: tuple[str, ...]
    lost_eligible_ids: tuple[str, ...]
    gained_eligible_ids: tuple[str, ...]
    added_evidence_ids: tuple[str, ...]
    removed_evidence_ids: tuple[str, ...]
    changed_evidence_ids: tuple[str, ...]
    rights_declared_changed_ids: tuple[str, ...]
    review_declared_changed_ids: tuple[str, ...]
    change_codes: tuple[str, ...]
    manual_actions: tuple[str, ...]
    gates: tuple[str, ...] = _GATES
    source_approval_authority: bool = False
    finding_authority: bool = False
    publication_authority: bool = False
    verdict: None = None


@dataclass(frozen=True)
class PrivateProfileTransitionPlan:
    version: str
    status: str
    previous_snapshot_sha256: str
    current_snapshot_sha256: str
    steps: tuple[ProfileTransitionStep, ...]
    added_claim_ids: tuple[str, ...]
    removed_claim_ids: tuple[str, ...]
    recheck_claim_ids: tuple[str, ...]
    snapshot_sha256: str
    gates: tuple[str, ...] = _GATES
    private_only: bool = True
    source_body_count: int = 0
    provider_calls: int = 0
    verdict: None = None
    source_rights_attested: bool = False
    reviewer_attested: bool = False
    fact_authority: bool = False
    source_approval_authority: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


def _record_material(
    claim: RequirementClaim,
    evidence: tuple[RequirementEvidence, ...],
    profile: VerificationRequirementProfile | None,
    preflight: RequirementPreflight,
) -> dict[str, object]:
    return {
        "claim": asdict(claim),
        "evidence": [asdict(row) for row in evidence],
        "profile": asdict(profile) if profile is not None else None,
        "preflight": asdict(preflight),
    }


def _snapshot_material(records: tuple[PrivateProfileRecord, ...]) -> dict[str, object]:
    return {
        "version": SNAPSHOT_VERSION,
        "records": [asdict(record) for record in records],
        "source_body_count": 0,
        "provider_calls": 0,
        "private_only": True,
        "authority": False,
    }


def _typed_claim(row: RequirementClaim) -> bool:
    return (
        type(row) is RequirementClaim
        and all(
            type(getattr(row, key)) is str
            for key in (
                "claim_id",
                "claim_kind",
                "statement_date",
                "proposition_sha256",
                "policy_version",
                "review_cutoff_date",
                "run_state",
            )
        )
        and (row.jurisdiction_ref is None or type(row.jurisdiction_ref) is str)
        and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", row.claim_kind) is not None
    )


def _typed_evidence(row: RequirementEvidence) -> bool:
    return (
        type(row) is RequirementEvidence
        and all(
            type(getattr(row, key)) is str
            for key in (
                "evidence_id",
                "evidence_sha256",
                "primary_root_ref",
                "source_family_ref",
                "locator_ref",
                "evidence_role",
                "published_date",
                "stance",
                "source_use_status",
                "evidence_review_status",
            )
        )
        and (row.jurisdiction_ref is None or type(row.jurisdiction_ref) is str)
    )


def build_profile_snapshot(
    claims: tuple[RequirementClaim, ...],
    evidence_by_claim: dict[str, tuple[RequirementEvidence, ...]],
) -> PrivateProfileSnapshot:
    """Capture exact typed values before computing any preflight or digest.

    Claim/evidence subclasses and custom mapping callbacks are excluded so a
    caller cannot replace metadata between validation, hashing and comparison.
    All processing below uses detached, immutable, sorted copies.
    """
    if (
        type(claims) is not tuple
        or type(evidence_by_claim) is not dict
        or len(claims) > _MAX_CLAIMS
        or any(not _typed_claim(claim) for claim in claims)
        or any(type(key) is not str for key in evidence_by_claim)
        or any(
            type(rows) is not tuple
            or len(rows) > 128
            or any(not _typed_evidence(row) for row in rows)
            for rows in evidence_by_claim.values()
        )
    ):
        raise ValueError("PROFILE_INPUT_INVALID")
    # Snapshot from the single original read; never consult the caller's map
    # or objects again after this boundary.
    claims = deepcopy(claims)
    evidence_by_claim = deepcopy(evidence_by_claim)
    identifiers = [claim.claim_id for claim in claims]
    if (
        any(type(identifier) is not str for identifier in identifiers)
        or len(set(identifiers)) != len(identifiers)
        or set(identifiers) != set(evidence_by_claim)
        or sum(len(rows) for rows in evidence_by_claim.values()) > _MAX_EVIDENCE
    ):
        raise ValueError("PROFILE_INPUT_INVALID")

    records: list[PrivateProfileRecord] = []
    for claim in sorted(claims, key=lambda item: item.claim_id):
        evidence = tuple(
            sorted(evidence_by_claim[claim.claim_id], key=lambda item: item.evidence_id)
        )
        preflight = preflight_verification_requirements(claim, evidence)
        profile = select_requirement_profile(claim.claim_kind)
        records.append(
            PrivateProfileRecord(
                claim=claim,
                evidence=evidence,
                profile=profile,
                preflight=preflight,
                snapshot_sha256=_digest(
                    _record_material(claim, evidence, profile, preflight)
                ),
            )
        )
    snapshot_records = tuple(records)
    return PrivateProfileSnapshot(
        version=SNAPSHOT_VERSION,
        records=snapshot_records,
        snapshot_sha256=_digest(_snapshot_material(snapshot_records)),
        claim_count=len(snapshot_records),
        evidence_count=sum(len(row.evidence) for row in snapshot_records),
    )


def _validate_snapshot(snapshot: PrivateProfileSnapshot) -> None:
    if (
        type(snapshot) is not PrivateProfileSnapshot
        or snapshot.version != SNAPSHOT_VERSION
        or type(snapshot.records) is not tuple
        or len(snapshot.records) > _MAX_CLAIMS
        or type(snapshot.claim_count) is not int
        or snapshot.claim_count != len(snapshot.records)
        or type(snapshot.evidence_count) is not int
        or snapshot.evidence_count > _MAX_EVIDENCE
        or type(snapshot.source_body_count) is not int
        or snapshot.source_body_count != 0
        or type(snapshot.provider_calls) is not int
        or snapshot.provider_calls != 0
        or snapshot.verdict is not None
        or snapshot.private_only is not True
        or snapshot.source_rights_attested is not False
        or snapshot.reviewer_attested is not False
        or snapshot.fact_authority is not False
        or snapshot.source_approval_authority is not False
        or snapshot.publication_authority is not False
        or type(snapshot.snapshot_sha256) is not str
        or not _SHA.fullmatch(snapshot.snapshot_sha256)
    ):
        raise ValueError("PROFILE_SNAPSHOT_INVALID")
    ids: list[str] = []
    evidence_count = 0
    for row in snapshot.records:
        if (
            type(row) is not PrivateProfileRecord
            or type(row.claim) is not RequirementClaim
            or type(row.evidence) is not tuple
            or len(row.evidence) > 128
            or not _typed_claim(row.claim)
            or any(not _typed_evidence(item) for item in row.evidence)
            or type(row.preflight) is not RequirementPreflight
            or (
                row.profile is not None
                and type(row.profile) is not VerificationRequirementProfile
            )
            or type(row.snapshot_sha256) is not str
            or not _SHA.fullmatch(row.snapshot_sha256)
        ):
            raise ValueError("PROFILE_SNAPSHOT_INVALID")
        # Compare against freshly recomputed canonical preflight; a forged
        # review/eligibility state cannot be legitimized by rehashing the DTO.
        try:
            expected_preflight = preflight_verification_requirements(
                row.claim, row.evidence
            )
            expected_profile = select_requirement_profile(row.claim.claim_kind)
        except (TypeError, ValueError) as exc:
            raise ValueError("PROFILE_SNAPSHOT_INVALID") from exc
        if (
            row.preflight != expected_preflight
            or row.profile != expected_profile
            or tuple(item.evidence_id for item in row.evidence)
            != tuple(sorted(item.evidence_id for item in row.evidence))
            or row.snapshot_sha256
            != _digest(
                _record_material(row.claim, row.evidence, row.profile, row.preflight)
            )
        ):
            raise ValueError("PROFILE_SNAPSHOT_INVALID")
        ids.append(row.claim.claim_id)
        evidence_count += len(row.evidence)
    if (
        ids != sorted(set(ids))
        or evidence_count != snapshot.evidence_count
        or snapshot.snapshot_sha256 != _digest(_snapshot_material(snapshot.records))
    ):
        raise ValueError("PROFILE_SNAPSHOT_INVALID")


def _step(
    identifier: str,
    old: PrivateProfileRecord | None,
    new: PrivateProfileRecord | None,
) -> ProfileTransitionStep:
    older = {item.evidence_id: item for item in old.evidence} if old else {}
    newer = {item.evidence_id: item for item in new.evidence} if new else {}
    before_eligible = set(old.preflight.eligible_evidence_ids) if old else set()
    after_eligible = set(new.preflight.eligible_evidence_ids) if new else set()
    before_ids = set(older)
    after_ids = set(newer)
    common = before_ids & after_ids
    changed = tuple(sorted(key for key in common if older[key] != newer[key]))
    rights = tuple(
        sorted(
            key
            for key in common
            if older[key].source_use_status != newer[key].source_use_status
        )
    )
    review = tuple(
        sorted(
            key
            for key in common
            if older[key].evidence_review_status != newer[key].evidence_review_status
        )
    )
    lost = tuple(sorted(before_eligible - after_eligible))
    gained = tuple(sorted(after_eligible - before_eligible))
    kind = "ADDED" if old is None else "REMOVED" if new is None else "CHANGED"
    codes: set[str] = set()
    actions: set[str] = set()
    if kind == "ADDED":
        codes.add("CLAIM_ADDED")
        actions.add("ADDED_CLAIM_MANUAL_REVIEW")
    elif kind == "REMOVED":
        codes.add("CLAIM_REMOVED")
        actions.add("REMOVED_CLAIM_NOT_RESOLVED")
    else:
        if old.profile != new.profile or old.claim.claim_kind != new.claim.claim_kind:
            codes.add("REQUIREMENT_PROFILE_CHANGED")
            actions.add("REVIEW_CHANGED_REQUIREMENT_PROFILE")
        if old.claim != new.claim:
            codes.add("CLAIM_INPUT_CHANGED")
            actions.add("REVIEW_CHANGED_CLAIM_INPUT")
        if old.preflight.state != new.preflight.state:
            codes.add("PREFLIGHT_STATE_CHANGED")
            actions.add("REVIEW_CHANGED_PREFLIGHT_STATE")
        if old.preflight.reason_codes != new.preflight.reason_codes:
            codes.add("PREFLIGHT_REASON_CHANGED")
            actions.add("REVIEW_CHANGED_PREFLIGHT_REASONS")
    if changed or before_ids != after_ids:
        codes.add("EVIDENCE_METADATA_CHANGED")
        actions.add("REVIEW_CHANGED_EVIDENCE_PROVENANCE")
    if rights:
        codes.add("RIGHTS_DECLARATION_CHANGED")
        actions.add("RECHECK_DECLARED_SOURCE_RIGHTS")
    if review:
        codes.add("REVIEW_DECLARATION_CHANGED")
        actions.add("RECHECK_DECLARED_EVIDENCE_REVIEW")
    if lost:
        codes.add("ELIGIBILITY_LOST")
        actions.add("REVIEW_ELIGIBILITY_LOSS")
    if gained:
        codes.add("ELIGIBILITY_GAINED")
        actions.add("REVIEW_NEW_ELIGIBILITY")
    # No source status, rule, or apparent evidence sufficiency can authorize
    # the external rights, reviewer, factual or publication authorities.
    actions.add("EXTERNAL_AUTHORITY_REVIEW_REQUIRED")
    return ProfileTransitionStep(
        claim_id=identifier,
        kind=kind,
        before_state=old.preflight.state if old else None,
        after_state=new.preflight.state if new else None,
        before_required_roles=old.profile.required_roles if old and old.profile else (),
        after_required_roles=new.profile.required_roles if new and new.profile else (),
        lost_eligible_ids=lost,
        gained_eligible_ids=gained,
        added_evidence_ids=tuple(sorted(after_ids - before_ids)),
        removed_evidence_ids=tuple(sorted(before_ids - after_ids)),
        changed_evidence_ids=changed,
        rights_declared_changed_ids=rights,
        review_declared_changed_ids=review,
        change_codes=tuple(sorted(codes)),
        manual_actions=tuple(sorted(actions)),
    )


def compare_profile_snapshots(
    previous: PrivateProfileSnapshot,
    current: PrivateProfileSnapshot,
    *,
    expected_previous_sha256: str,
    expected_current_sha256: str,
) -> PrivateProfileTransitionPlan:
    """Compare two separately owner-pinned private metadata snapshots.

    Pins must originate outside these untrusted objects. Caller-rehashed
    metadata, even when internally consistent, is not source attestation.
    """
    if (
        type(previous) is not PrivateProfileSnapshot
        or type(current) is not PrivateProfileSnapshot
    ):
        raise ValueError("PROFILE_SNAPSHOT_INVALID")
    # Detach before digest, canonical validation, and downstream step reads.
    previous, current = deepcopy(previous), deepcopy(current)
    _validate_snapshot(previous)
    _validate_snapshot(current)
    if (
        type(expected_previous_sha256) is not str
        or type(expected_current_sha256) is not str
        or not _SHA.fullmatch(expected_previous_sha256)
        or not _SHA.fullmatch(expected_current_sha256)
        or previous.snapshot_sha256 != expected_previous_sha256
        or current.snapshot_sha256 != expected_current_sha256
    ):
        raise ValueError("PROFILE_PIN_MISMATCH")

    before = {record.claim.claim_id: record for record in previous.records}
    after = {record.claim.claim_id: record for record in current.records}
    added = tuple(sorted(after.keys() - before.keys()))
    removed = tuple(sorted(before.keys() - after.keys()))
    steps = tuple(
        _step(identifier, before.get(identifier), after.get(identifier))
        for identifier in sorted(before.keys() | after.keys())
        if identifier not in before
        or identifier not in after
        or before[identifier] != after[identifier]
    )
    recheck = tuple(item.claim_id for item in steps)
    material = {
        "version": VERSION,
        "previous": previous.snapshot_sha256,
        "current": current.snapshot_sha256,
        "steps": [asdict(item) for item in steps],
        "added": added,
        "removed": removed,
        "recheck": recheck,
    }
    return PrivateProfileTransitionPlan(
        version=VERSION,
        status="MANUAL_RECHECK_REQUIRED" if steps else "UNCHANGED_NO_AUTHORITY",
        previous_snapshot_sha256=previous.snapshot_sha256,
        current_snapshot_sha256=current.snapshot_sha256,
        steps=steps,
        added_claim_ids=added,
        removed_claim_ids=removed,
        recheck_claim_ids=recheck,
        snapshot_sha256=_digest(material),
    )
