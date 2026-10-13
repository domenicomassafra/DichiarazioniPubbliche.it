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


@dataclass(frozen=True)
class SequenceEventObservation:
    """Source-hash-bound *assertion* about an event date, not proven truth.

    A separately approved evidence observation would need persisted lineage,
    rights and reviewing authority; a caller constructing this class supplies
    none of those attestations.
    """

    evidence_id: str
    evidence_sha256: str
    event_ref: str
    occurred_on: str


@dataclass(frozen=True)
class PrivateEventSequenceComparison:
    """A deterministic private observation comparison, never a fact Finding."""

    version: str
    claim_id: str
    state: str
    comparison_status: str
    observed_order: str | None
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    snapshot_sha256: str
    verdict: None = None
    private_only: bool = True
    source_proof_attested: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


def select_requirement_profile(
    claim_kind: str,
) -> VerificationRequirementProfile | None:
    if not isinstance(claim_kind, str):
        raise ValueError("REQUIREMENT_CLAIM_KIND_INVALID")
    profile = _CLASSES.get(claim_kind)
    return VerificationRequirementProfile(claim_kind, *profile) if profile else None


def _has_independent_role_sources(
    rows: tuple[RequirementEvidence, ...] | list[RequirementEvidence],
    required_roles: tuple[str, ...],
) -> bool:
    """Bind each required role to a different original root AND source family.

    Separate set counts can be satisfied with overlapping rows even when no
    pair of required roles has independent provenance on both dimensions.
    """
    candidates = tuple(
        tuple(row for row in rows if row.evidence_role == role)
        for role in required_roles
    )

    def cover(index: int, roots: frozenset[str], families: frozenset[str]) -> bool:
        if index == len(candidates):
            return True
        return any(
            cover(
                index + 1,
                roots | {row.primary_root_ref},
                families | {row.source_family_ref},
            )
            for row in candidates[index]
            if row.primary_root_ref not in roots
            and row.source_family_ref not in families
        )

    return cover(0, frozenset(), frozenset())


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
    # Legal status has no meaningful authority scope without a jurisdiction.
    # An arbitrary legal record must not make an unscoped law claim checkable.
    if claim.claim_kind == "DOCUMENTARY_LEGAL_STATUS" and claim.jurisdiction_ref is None:
        reason_codes.add("LEGAL_JURISDICTION_UNSPECIFIED")
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
        if "LEGAL_JURISDICTION_UNSPECIFIED" in reason_codes:
            codes.append("LEGAL_JURISDICTION_UNSPECIFIED")
        if profile is None:
            codes.append(
                "NON_FACTUAL_EVIDENCE_NOT_APPLICABLE"
                if claim.claim_kind == "NON_FACTUAL"
                else "PROFILE_UNAVAILABLE"
            )
        elif row.evidence_role not in profile.required_roles:
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
    role_sources_independent = profile is None or _has_independent_role_sources(
        eligible, profile.required_roles
    )
    if (
        profile
        and not role_sources_independent
        and set(profile.required_roles).issubset(roles)
        and len(roots) >= profile.independent_roots_required
        and len(families) >= profile.independent_roots_required
    ):
        reason_codes.add("INDEPENDENT_ROLE_SOURCE_PAIR_MISSING")
    if profile is None and claim.claim_kind != "NON_FACTUAL":
        state = "NOT_CHECKABLE_PROFILE_UNAVAILABLE"
    elif claim.run_state == "NOT_STARTED":
        state = "NOT_CHECKED"
    elif claim.claim_kind == "NON_FACTUAL":
        state = "NON_FACTUAL"
    elif any(code in reason_codes for code in ("CROSS_ROOT_IDENTICAL_BYTES",)):
        state = "CHECKED_INSUFFICIENT_EVIDENCE"
    elif (
        "LEGAL_JURISDICTION_UNSPECIFIED" in reason_codes
        or not set(profile.required_roles).issubset(roles)
        or len(roots) < profile.independent_roots_required
        or len(families) < profile.independent_roots_required
        or not role_sources_independent
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


def compare_private_event_sequence(
    claim: RequirementClaim,
    evidence: tuple[RequirementEvidence, ...],
    observations: tuple[SequenceEventObservation, ...],
    *,
    left_event_ref: str,
    right_event_ref: str,
    claimed_order: str,
) -> PrivateEventSequenceComparison:
    """Compare two event dates derived from independently labeled source rows.

    Only input dates, approved *declarations* and evidence SHA references are
    compared. A declaration of APPROVED is not itself an independent review
    attestation. A matching observation pair is not a factual verdict and has
    no publication/machine-signoff authority. No remote fetch or model call.
    """
    _ref(left_event_ref, "LEFT_EVENT")
    _ref(right_event_ref, "RIGHT_EVENT")
    if left_event_ref == right_event_ref or claimed_order not in {"BEFORE", "AFTER"}:
        raise ValueError("SEQUENCE_QUESTION_INVALID")
    if not isinstance(observations, tuple) or len(observations) > 128:
        raise ValueError("SEQUENCE_OBSERVATIONS_INVALID")

    preliminary = preflight_verification_requirements(claim, evidence)
    by_id = {row.evidence_id: row for row in evidence}
    observed: dict[str, list[tuple[RequirementEvidence, str]]] = {
        left_event_ref: [], right_event_ref: [],
    }
    observed_pairs: set[tuple[str, str]] = set()
    reasons = set(preliminary.reason_codes)
    cutoff = _date(claim.statement_date, "STATEMENT_DATE")
    allowed = set(preliminary.eligible_evidence_ids)

    for row in observations:
        if not isinstance(row, SequenceEventObservation):
            raise ValueError("SEQUENCE_OBSERVATION_INPUT_INVALID")
        _ref(row.evidence_id, "SEQUENCE_EVIDENCE_ID")
        _ref(row.event_ref, "SEQUENCE_EVENT_REF")
        if row.event_ref not in observed:
            raise ValueError("SEQUENCE_OBSERVATION_EVENT_UNBOUND")
        unique = (row.evidence_id, row.event_ref)
        if unique in observed_pairs:
            raise ValueError("SEQUENCE_OBSERVATION_DUPLICATE")
        observed_pairs.add(unique)
        bound = by_id.get(row.evidence_id)
        if bound is None:
            raise ValueError("SEQUENCE_OBSERVATION_EVIDENCE_UNBOUND")
        if row.evidence_sha256 != bound.evidence_sha256:
            raise ValueError("SEQUENCE_OBSERVATION_EVIDENCE_SHA_MISMATCH")
        occurred = _date(row.occurred_on, "SEQUENCE_EVENT_DATE")
        published = _date(bound.published_date, "EVIDENCE_DATE")
        if occurred > cutoff:
            reasons.add("EVENT_AFTER_STATEMENT_CUTOFF")
            continue
        if occurred > published:
            reasons.add("EVENT_NOT_YET_OCCURRED_AT_SOURCE_PUBLICATION")
            continue
        if row.evidence_id in allowed:
            observed[row.event_ref].append((bound, row.occurred_on))

    comparison_status = "NOT_COMPUTABLE"
    observed_order: str | None = None
    state = preliminary.state
    used: set[str] = set()
    if claim.claim_kind != "EVENT_SEQUENCE":
        state = "NOT_CHECKABLE_PROFILE_UNAVAILABLE"
        reasons.add("EVENT_SEQUENCE_PROFILE_REQUIRED")
    elif state == "NOT_CHECKED":
        pass
    elif state == "UNRESOLVED_CONFLICT":
        reasons.add("CONFLICTING_REVIEWED_STANCES")
    else:
        event_dates: dict[str, str] = {}
        insufficient = False
        conflicting = False
        for event_ref in (left_event_ref, right_event_ref):
            group = observed[event_ref]
            roles = {row.evidence_role for row, _ in group}
            roots = {row.primary_root_ref for row, _ in group}
            families = {row.source_family_ref for row, _ in group}
            if (not {"PRIMARY_RECORD", "INDEPENDENT_RECORD"}.issubset(roles)
                    or len(roots) < 2 or len(families) < 2
                    or not _has_independent_role_sources(
                        [row for row, _ in group],
                        ("PRIMARY_RECORD", "INDEPENDENT_RECORD"),
                    )):
                insufficient = True
                reasons.add("EVENT_INDEPENDENCE_MISSING")
                continue
            dates = {date_value for _, date_value in group}
            if len(dates) != 1:
                conflicting = True
                reasons.add("CONFLICTING_EVENT_DATES")
                continue
            used.update(row.evidence_id for row, _ in group)
            event_dates[event_ref] = next(iter(dates))
        if state == "CHECKABLE_PENDING" and not insufficient and conflicting:
            state = "UNRESOLVED_CONFLICT"
        elif insufficient or state == "CHECKED_INSUFFICIENT_EVIDENCE":
            state = "CHECKED_INSUFFICIENT_EVIDENCE"
        elif conflicting:
            state = "UNRESOLVED_CONFLICT"
        elif len(event_dates) == 2:
            left, right = event_dates[left_event_ref], event_dates[right_event_ref]
            if left == right:
                # Dates only have day precision; both events may have occurred
                # in either order within that day. Do not infer a refutation.
                state = "CHECKED_INSUFFICIENT_EVIDENCE"
                reasons.add("SAME_DAY_EVENT_ORDER_UNRESOLVED")
            else:
                observed_order = "BEFORE" if left < right else "AFTER"
                comparison_status = (
                    "OBSERVATIONS_AGREE" if observed_order == claimed_order
                    else "OBSERVATIONS_DISAGREE"
                )
                reasons.add("INDEPENDENT_SOURCE_TRUTH_UNATTESTED")

    fingerprint = _digest({
        "version": VERSION,
        "comparison": "event-sequence-v1",
        "requirement_snapshot_sha256": preliminary.snapshot_sha256,
        "left_event_ref": left_event_ref,
        "right_event_ref": right_event_ref,
        "claimed_order": claimed_order,
        "observations": [asdict(row) for row in sorted(
            observations, key=lambda value: (value.evidence_id, value.event_ref)
        )],
    })
    return PrivateEventSequenceComparison(
        version="private-event-sequence-comparison-v1",
        claim_id=claim.claim_id,
        state=state,
        comparison_status=comparison_status,
        observed_order=observed_order,
        reason_codes=tuple(sorted(reasons)),
        evidence_ids=tuple(sorted(used)),
        snapshot_sha256=fingerprint,
    )
