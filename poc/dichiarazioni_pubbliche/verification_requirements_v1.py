"""DP-314 opt-in, private verification-requirement preflight.

Caller-supplied provenance is NOT a reviewed primary source or independent
truth. This produces a bounded research/verifier eligibility proposal, never
an adjudication, Finding, source-rights grant or publication authorization.
The existing deterministic verification_runtime remains the authority for
its supported numerical/text rules, subject to external review gates.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date


VERSION = "verification-requirement-preflight-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ROLES = {
    "PRIMARY_RECORD",
    "INDEPENDENT_RECORD",
    "PRIMARY_STATISTICS",
    "PRIMARY_LEGAL_RECORD",
    "PRIMARY_TEXT",
}
_CLASSES = {
    "EVENT_SEQUENCE": (("PRIMARY_RECORD", "INDEPENDENT_RECORD"), 2),
    "DOCUMENTARY_LEGAL_STATUS": (("PRIMARY_LEGAL_RECORD",), 1),
    "FACTUAL_DENIAL": (("PRIMARY_RECORD", "INDEPENDENT_RECORD"), 2),
    "NUMERIC": (("PRIMARY_STATISTICS",), 1),
    "FACTUAL_TEXT_COMPARISON": (("PRIMARY_TEXT",), 1),
}


def _ref(value: str, key: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError(f"REQUIREMENT_{key}_INVALID")
    return value


def _date(value: str, key: str) -> date:
    try:
        if (
            not isinstance(value, str)
            or len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"REQUIREMENT_{key}_INVALID") from exc


def _digest(material: object) -> str:
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class VerificationRequirementProfile:
    claim_kind: str
    required_roles: tuple[str, ...]
    independent_roots_required: int
    rule_version: str = VERSION


@dataclass(frozen=True)
class RequirementClaim:
    claim_id: str
    claim_kind: str
    statement_date: str
    jurisdiction_ref: str | None
    proposition_sha256: str
    policy_version: str
    review_cutoff_date: str
    run_state: str  # NOT_STARTED | COMPLETED


@dataclass(frozen=True)
class RequirementEvidence:
    evidence_id: str
    evidence_sha256: str
    primary_root_ref: str
    source_family_ref: str
    locator_ref: str
    evidence_role: str
    published_date: str
    jurisdiction_ref: str | None
    stance: str  # SUPPORT | REFUTE | UNKNOWN; untrusted operator input
    source_use_status: str  # APPROVED | HELD | REVOKED
    evidence_review_status: str  # APPROVED | PENDING | REVOKED


@dataclass(frozen=True)
class RequirementPreflight:
    version: str
    claim_id: str
    state: str
    reason_codes: tuple[str, ...]
    required_roles: tuple[str, ...]
    eligible_evidence_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...]
    observed_independent_roots: int
    snapshot_sha256: str
    verdict: None = None
    finding_authority: bool = False
    publication_authority: bool = False


def select_requirement_profile(
    claim_kind: str,
) -> VerificationRequirementProfile | None:
    if not isinstance(claim_kind, str):
        raise ValueError("REQUIREMENT_CLAIM_KIND_INVALID")
    profile = _CLASSES.get(claim_kind)
    return VerificationRequirementProfile(claim_kind, *profile) if profile else None


def preflight_verification_requirements(
    claim: RequirementClaim,
    observations: tuple[RequirementEvidence, ...],
) -> RequirementPreflight:
    """Fail closed on wrong source, time, policy or independence; no verdict.

    Eligible means *operator-declared* review/rights status is consistent with
    a source-bound candidate. Only persisted authority can substantiate it.
    """
    if (
        not isinstance(claim, RequirementClaim)
        or not isinstance(observations, tuple)
        or len(observations) > 128
    ):
        raise ValueError("REQUIREMENT_INPUT_INVALID")
    _ref(claim.claim_id, "CLAIM")
    _ref(claim.policy_version, "POLICY_VERSION")
    if claim.jurisdiction_ref is not None:
        _ref(claim.jurisdiction_ref, "JURISDICTION")
    if not isinstance(claim.proposition_sha256, str) or not _SHA.fullmatch(
        claim.proposition_sha256
    ):
        raise ValueError("REQUIREMENT_PROPOSITION_SHA_INVALID")
    statement_day = _date(claim.statement_date, "STATEMENT_DATE")
    cutoff = _date(claim.review_cutoff_date, "REVIEW_DATE")
    if cutoff < statement_day or claim.run_state not in {"NOT_STARTED", "COMPLETED"}:
        raise ValueError("REQUIREMENT_RUN_INPUT_INVALID")
    profile = select_requirement_profile(claim.claim_kind)
    eligible: list[RequirementEvidence] = []
    excluded: list[str] = []
    reason_codes: set[str] = set()
    seen: set[str] = set()
    for row in observations:
        if not isinstance(row, RequirementEvidence):
            raise ValueError("REQUIREMENT_EVIDENCE_INPUT_INVALID")
        for key in (
            "evidence_id",
            "primary_root_ref",
            "source_family_ref",
            "locator_ref",
        ):
            _ref(getattr(row, key), key.upper())
        if row.evidence_id in seen:
            raise ValueError("REQUIREMENT_EVIDENCE_ID_DUPLICATE")
        seen.add(row.evidence_id)
        if not isinstance(row.evidence_sha256, str) or not _SHA.fullmatch(
            row.evidence_sha256
        ):
            raise ValueError("REQUIREMENT_EVIDENCE_SHA_INVALID")
        if row.jurisdiction_ref is not None:
            _ref(row.jurisdiction_ref, "EVIDENCE_JURISDICTION")
        published = _date(row.published_date, "EVIDENCE_DATE")
        if row.evidence_role not in _ROLES or row.stance not in {
            "SUPPORT",
            "REFUTE",
            "UNKNOWN",
        }:
            raise ValueError("REQUIREMENT_EVIDENCE_CLASS_INVALID")
        if row.source_use_status not in {
            "APPROVED",
            "HELD",
            "REVOKED",
        } or row.evidence_review_status not in {"APPROVED", "PENDING", "REVOKED"}:
            raise ValueError("REQUIREMENT_EVIDENCE_APPROVAL_INVALID")
        codes: list[str] = []
        if (
            row.source_use_status != "APPROVED"
            or row.evidence_review_status != "APPROVED"
        ):
            codes.append("EVIDENCE_OR_RIGHTS_NOT_APPROVED")
        if published > statement_day:
            codes.append("POST_STATEMENT_EVIDENCE_ONLY")
        if published > cutoff:
            codes.append("AFTER_REVIEW_CUTOFF")
        if claim.jurisdiction_ref and row.jurisdiction_ref != claim.jurisdiction_ref:
            codes.append("JURISDICTION_MISMATCH")
        if profile and row.evidence_role not in profile.required_roles:
            codes.append("ROLE_NOT_REQUIRED")
        if codes:
            excluded.append(row.evidence_id)
            reason_codes.update(codes)
        else:
            eligible.append(row)

    # Mirrors/reprints and reused source bytes cannot be independently counted,
    # even if a caller gives them another source-family label.
    roots_by_sha: dict[str, set[str]] = {}
    for row in eligible:
        roots_by_sha.setdefault(row.evidence_sha256, set()).add(row.primary_root_ref)
    if any(len(roots) > 1 for roots in roots_by_sha.values()):
        reason_codes.add("CROSS_ROOT_IDENTICAL_BYTES")
    roots = {row.primary_root_ref for row in eligible}
    families = {row.source_family_ref for row in eligible}
    roles = {row.evidence_role for row in eligible}
    if profile and not set(profile.required_roles).issubset(roles):
        reason_codes.add("REQUIRED_EVIDENCE_ROLE_MISSING")
    if profile and len(roots) < profile.independent_roots_required:
        reason_codes.add("INDEPENDENT_ORIGINAL_ROOT_MISSING")
    if profile and len(families) < profile.independent_roots_required:
        reason_codes.add("INDEPENDENT_SOURCE_FAMILY_MISSING")
    if claim.run_state == "NOT_STARTED":
        state = "NOT_CHECKED"
    elif claim.claim_kind == "NON_FACTUAL":
        state = "NON_FACTUAL"
    elif profile is None:
        state = "NOT_CHECKABLE_PROFILE_UNAVAILABLE"
    elif any(code in reason_codes for code in ("CROSS_ROOT_IDENTICAL_BYTES",)):
        state = "CHECKED_INSUFFICIENT_EVIDENCE"
    elif (
        not set(profile.required_roles).issubset(roles)
        or len(roots) < profile.independent_roots_required
        or len(families) < profile.independent_roots_required
    ):
        state = "CHECKED_INSUFFICIENT_EVIDENCE"
    elif {row.stance for row in eligible} >= {"SUPPORT", "REFUTE"}:
        state = "UNRESOLVED_CONFLICT"
        reason_codes.add("CONTRADICTORY_REVIEWED_OBSERVATIONS")
    else:
        state = "CHECKABLE_PENDING"
        reason_codes.add("DETERMINISTIC_VERIFICATION_OR_INDEPENDENT_GOLD_REQUIRED")
    snapshot = _digest(
        {
            "version": VERSION,
            "claim": asdict(claim),
            "observations": [
                asdict(row) for row in sorted(observations, key=lambda x: x.evidence_id)
            ],
        }
    )
    return RequirementPreflight(
        VERSION,
        claim.claim_id,
        state,
        tuple(sorted(reason_codes)),
        profile.required_roles if profile else (),
        tuple(sorted(row.evidence_id for row in eligible)),
        tuple(sorted(excluded)),
        len(roots),
        snapshot,
    )
