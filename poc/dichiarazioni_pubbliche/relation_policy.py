from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dichiarazioni_pubbliche.relation_runtime import (
    ScopedStatementRelationDecision,
    StatementRelationKind,
)

from dichiarazioni_pubbliche.domain_vocabulary import (
    RELATION_VERSION,
    RelationCandidateType,
)

RELATION_PUBLICATION_POLICY_VERSION = "relation-publication-v1"


class RelationCandidateStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


ALLOWED_RELATION_CANDIDATE_STATUSES: tuple[str, ...] = tuple(
    item.value for item in RelationCandidateStatus
)

ALLOWED_RELATION_TYPES: tuple[str, ...] = tuple(
    item.value for item in RelationCandidateType
)


class RelationPublicationEligibility(StrEnum):
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"
    PUBLIC_ELIGIBLE = "PUBLIC_ELIGIBLE"


PROHIBITED_INTENT_TERMS: frozenset[str] = frozenset(
    {
        "intent",
        "intentionality",
        "lie",
        "lying",
        "deception",
        "deliberate_falsehood",
        "dishonesty",
        "bad_faith",
        "motive",
    }
)


@dataclass(frozen=True)
class RelationPublicationInput:
    relation_type: RelationCandidateType | str
    relation_status: RelationCandidateStatus | str
    both_claims_have_published_finding: bool
    has_approved_review_event: bool
    has_proposition_keys: bool
    correction_involved: bool = False
    statement_context_compatible: bool = True
    review_is_stale: bool = False
    correction_approved: bool = True

    def __post_init__(self) -> None:
        for term in PROHIBITED_INTENT_TERMS:
            if hasattr(self, term):
                raise ValueError(
                    f"INTENT_ENCODING_PROHIBITED: field '{term}' cannot be encoded in relation policy"
                )


def evaluate_relation_publication_eligibility(
    relation_type: RelationPublicationInput | RelationCandidateType | str | None = None,
    relation_status: RelationCandidateStatus | str | None = None,
    both_claims_have_published_finding: bool | None = None,
    has_approved_review_event: bool | None = None,
    has_proposition_keys: bool | None = None,
    correction_involved: bool = False,
    *,
    statement_context_compatible: bool = True,
    review_is_stale: bool = False,
    correction_approved: bool = True,
    **kwargs,
) -> RelationPublicationEligibility:
    """Evaluate relation publication eligibility from bounded inputs.

    Pure function deciding whether a relation candidate is CANDIDATE,
    REJECTED, or PUBLIC_ELIGIBLE based on review provenance, finding
    publication, statement-time/context compatibility, and staleness.

    Candidate states never publish.
    A relation referencing an unpublished finding is never public-eligible.
    A relation without proposition keys can never be a contradiction.
    Public eligibility requires explicit review provenance.
    Contradiction never implies deliberate falsehood or intent.
    Public projection omits stale relation reviews fail-closed.
    """
    for key in kwargs:
        key_lower = key.lower()
        if any(term in key_lower for term in PROHIBITED_INTENT_TERMS):
            raise ValueError(
                f"INTENT_ENCODING_PROHIBITED: field '{key}' cannot be encoded in relation policy"
            )
    if kwargs:
        raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")

    if isinstance(relation_type, RelationPublicationInput):
        inp = relation_type
        rel_type = inp.relation_type
        rel_status = inp.relation_status
        findings_published = inp.both_claims_have_published_finding
        has_review = inp.has_approved_review_event
        has_props = inp.has_proposition_keys
        corr_involved = inp.correction_involved
        ctx_compatible = inp.statement_context_compatible
        stale_review = inp.review_is_stale
        corr_approved = inp.correction_approved
    else:
        rel_type = relation_type
        rel_status = relation_status
        findings_published = both_claims_have_published_finding
        has_review = has_approved_review_event
        has_props = has_proposition_keys
        corr_involved = correction_involved
        ctx_compatible = statement_context_compatible
        stale_review = review_is_stale
        corr_approved = correction_approved

    if rel_type is None or rel_status is None:
        raise ValueError(
            "RELATION_INPUT_INCOMPLETE: relation_type and relation_status are required"
        )
    if findings_published is None:
        raise ValueError(
            "RELATION_INPUT_INCOMPLETE: both_claims_have_published_finding is required"
        )
    if has_review is None:
        raise ValueError(
            "RELATION_INPUT_INCOMPLETE: has_approved_review_event is required"
        )
    if has_props is None:
        raise ValueError(
            "RELATION_INPUT_INCOMPLETE: has_proposition_keys is required"
        )

    type_val = (
        rel_type.value
        if isinstance(rel_type, RelationCandidateType)
        else str(rel_type)
    )
    status_val = (
        rel_status.value
        if isinstance(rel_status, RelationCandidateStatus)
        else str(rel_status)
    )

    if status_val not in ALLOWED_RELATION_CANDIDATE_STATUSES:
        raise ValueError(f"INVALID_RELATION_STATUS: {status_val}")
    if type_val not in ALLOWED_RELATION_TYPES:
        raise ValueError(f"INVALID_RELATION_TYPE: {type_val}")

    # Rule: NO_RELATION is never public-eligible
    if type_val == RelationCandidateType.NO_RELATION.value:
        return RelationPublicationEligibility.REJECTED

    # Rule: Terminal non-publishable storable states
    if status_val in (
        RelationCandidateStatus.REJECTED.value,
        RelationCandidateStatus.SUPERSEDED.value,
    ):
        return RelationPublicationEligibility.REJECTED

    # Rule: A relation without proposition keys can never be a contradiction
    if (
        type_val == RelationCandidateType.CONTRADICTION_CANDIDATE.value
        and not has_props
    ):
        return RelationPublicationEligibility.REJECTED

    # Rule: Statement-time and context compatibility must be verified
    if not ctx_compatible:
        return RelationPublicationEligibility.REJECTED

    # Rule: Candidate states never publish
    if status_val == RelationCandidateStatus.CANDIDATE.value:
        return RelationPublicationEligibility.CANDIDATE

    # Rule: Public eligibility requires explicit review provenance
    if not has_review:
        return RelationPublicationEligibility.CANDIDATE

    # Rule: Public projection omits stale relation reviews fail-closed
    if stale_review:
        return RelationPublicationEligibility.CANDIDATE

    # Rule: A relation referencing a non-published finding is never public-eligible
    if not findings_published:
        return RelationPublicationEligibility.CANDIDATE

    # Rule: If a correction is involved on either claim, it must be approved
    if corr_involved and not corr_approved:
        return RelationPublicationEligibility.CANDIDATE

    # If all criteria are satisfied and status is APPROVED:
    return RelationPublicationEligibility.PUBLIC_ELIGIBLE


# DP-318 is an independent Statement candidate preflight, not a v1 Finding
# publication-policy override. A caller-supplied "approved" flag/ref or an LLM
# result cannot create a public relation without the authoritative append-only
# store review, source/currentness, rights and correction revalidation.
STATEMENT_RELATION_PREFLIGHT_VERSION = "statement-relation-preflight-v1"


class StatementRelationPreflightState(StrEnum):
    HOLD = "HOLD"
    PRIVATE_HANDOFF = "PRIVATE_HANDOFF"


@dataclass(frozen=True)
class StatementRelationPreflight:
    relation: ScopedStatementRelationDecision
    endpoint_public_statement_versions: tuple[str, str]
    source_context_current: bool
    person_identity_current: bool
    corrections_current: bool
    rights_current: bool
    relation_review_event_ref: str | None = None


@dataclass(frozen=True)
class StatementRelationPreflightDecision:
    state: StatementRelationPreflightState
    finding_required: bool
    reason_codes: tuple[str, ...]
    version: str = STATEMENT_RELATION_PREFLIGHT_VERSION

    @property
    def publication_authority(self) -> bool:
        return False


def evaluate_statement_relation_preflight(
    value: StatementRelationPreflight,
) -> StatementRelationPreflightDecision:
    """Private, fail-closed handoff for opinion-capable Statement relations.

    Even PRIVATE_HANDOFF cannot authorize publication: all supplied references
    and freshness flags are untrusted until independently verified by an
    authoritative store/public projection adapter (not implemented here).
    """
    if not isinstance(value, StatementRelationPreflight):
        raise ValueError("STATEMENT_RELATION_PREFLIGHT_INPUT_INVALID")
    reasons: list[str] = []
    relation = value.relation
    if (
        not isinstance(relation, ScopedStatementRelationDecision)
        or relation.kind == StatementRelationKind.HOLD
        or relation.state != "CANDIDATE_PRIVATE"
        or any(
            code not in {"RETROSPECTIVE_CONTINUITY_CANDIDATE"}
            for code in relation.rationale_codes
        )
        or relation.review_authority
        or relation.publication_authority
    ):
        reasons.append("RELATION_SEMANTICS_NOT_READY")
    if (
        not isinstance(value.endpoint_public_statement_versions, tuple)
        or len(value.endpoint_public_statement_versions) != 2
        or any(
            not isinstance(ref, str) or not ref.strip()
            for ref in value.endpoint_public_statement_versions
        )
    ):
        reasons.append("PUBLISHED_STATEMENT_VERSIONS_UNVERIFIED")
    if not isinstance(value.relation_review_event_ref, str) or not (
        value.relation_review_event_ref.strip()
    ):
        reasons.append("RELATION_REVIEW_EVENT_UNVERIFIED")
    for field, code in (
        ("source_context_current", "SOURCE_CONTEXT_STALE_OR_UNKNOWN"),
        ("person_identity_current", "PERSON_IDENTITY_STALE_OR_UNKNOWN"),
        ("corrections_current", "CORRECTION_SUPERSESSION_STALE_OR_UNKNOWN"),
        ("rights_current", "SOURCE_RIGHTS_STALE_OR_UNKNOWN"),
    ):
        if getattr(value, field) is not True:
            reasons.append(code)
    return StatementRelationPreflightDecision(
        state=(
            StatementRelationPreflightState.HOLD
            if reasons
            else StatementRelationPreflightState.PRIVATE_HANDOFF
        ),
        finding_required=(
            relation.finding_required
            if isinstance(relation, ScopedStatementRelationDecision)
            else True
        ),
        reason_codes=tuple(reasons),
    )


__all__ = [
    "ALLOWED_RELATION_CANDIDATE_STATUSES",
    "ALLOWED_RELATION_TYPES",
    "PROHIBITED_INTENT_TERMS",
    "RELATION_PUBLICATION_POLICY_VERSION",
    "RELATION_VERSION",
    "STATEMENT_RELATION_PREFLIGHT_VERSION",
    "RelationCandidateStatus",
    "RelationPublicationEligibility",
    "RelationPublicationInput",
    "StatementRelationPreflight",
    "StatementRelationPreflightDecision",
    "StatementRelationPreflightState",
    "evaluate_relation_publication_eligibility",
    "evaluate_statement_relation_preflight",
]
