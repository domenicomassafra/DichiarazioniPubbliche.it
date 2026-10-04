from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date

from dichiarazioni_pubbliche.domain_vocabulary import (
    RELATION_VERSION,
    RelationCandidateType,
)


@dataclass(frozen=True)
class StructuredClaimRelationInput:
    claim_id: str
    statement_date: str
    proposition_key: str | None = None
    topic_key: str | None = None
    stance: str | None = None
    scope_start: str | None = None
    scope_end: str | None = None
    asserts_past_continuity: bool = False


@dataclass(frozen=True)
class RelationCandidateResult:
    subject_claim_id: str
    object_claim_id: str
    relation_type: RelationCandidateType
    rationale_codes: tuple[str, ...]
    confidence: float | None
    relation_version: str = RELATION_VERSION


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _scopes_overlap(
    left: StructuredClaimRelationInput,
    right: StructuredClaimRelationInput,
) -> bool:
    left_start = _date_or_none(left.scope_start)
    left_end = _date_or_none(left.scope_end)
    right_start = _date_or_none(right.scope_start)
    right_end = _date_or_none(right.scope_end)
    if None in {left_start, left_end, right_start, right_end}:
        return False
    assert left_start and left_end and right_start and right_end
    return max(left_start, right_start) <= min(left_end, right_end)


def classify_relation(
    prior: StructuredClaimRelationInput,
    later: StructuredClaimRelationInput,
) -> RelationCandidateResult:
    if prior.claim_id == later.claim_id:
        raise ValueError("RELATION_SELF_REFUSED")
    if date.fromisoformat(prior.statement_date) > date.fromisoformat(
        later.statement_date
    ):
        prior, later = later, prior
    if not prior.proposition_key or not later.proposition_key:
        if prior.topic_key and prior.topic_key == later.topic_key:
            return RelationCandidateResult(
                prior.claim_id,
                later.claim_id,
                RelationCandidateType.RELATED_TOPIC,
                ("PROPOSITION_KEY_MISSING", "TOPIC_MATCH_ONLY"),
                None,
            )
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.NO_RELATION,
            ("NO_SHARED_PROPOSITION",),
            None,
        )
    if prior.proposition_key != later.proposition_key:
        if prior.topic_key and prior.topic_key == later.topic_key:
            return RelationCandidateResult(
                prior.claim_id,
                later.claim_id,
                RelationCandidateType.RELATED_TOPIC,
                ("DIFFERENT_PROPOSITION_SAME_TOPIC",),
                1.0,
            )
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.NO_RELATION,
            ("DIFFERENT_PROPOSITION",),
            1.0,
        )
    if not prior.stance or not later.stance:
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.SAME_PROPOSITION,
            ("SAME_PROPOSITION_STANCE_INCOMPLETE",),
            1.0,
        )
    if prior.stance == later.stance:
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.SAME_PROPOSITION,
            ("SAME_PROPOSITION_SAME_STANCE",),
            1.0,
        )
    if _scopes_overlap(prior, later) or later.asserts_past_continuity:
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.CONTRADICTION_CANDIDATE,
            (
                "SAME_PROPOSITION_OPPOSITE_STANCE",
                (
                    "OVERLAPPING_TEMPORAL_SCOPE"
                    if _scopes_overlap(prior, later)
                    else "RETROSPECTIVE_CONTINUITY_ASSERTION"
                ),
            ),
            1.0,
        )
    return RelationCandidateResult(
        prior.claim_id,
        later.claim_id,
        RelationCandidateType.POSITION_CHANGE_CANDIDATE,
        ("SAME_PROPOSITION_OPPOSITE_STANCE", "NON_OVERLAPPING_TIME"),
        1.0,
    )


def deterministic_relation_candidate_id(
    result: RelationCandidateResult,
) -> str:
    payload = json.dumps(
        asdict(result),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "relation-candidate:" + hashlib.sha256(payload).hexdigest()
