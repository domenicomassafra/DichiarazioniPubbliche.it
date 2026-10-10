from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
import re

from dichiarazioni_pubbliche.context_integrity import (
    SPEECH_ACT_CONTEXT_VERSION,
    SpeechActContextDecision,
)

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
    person_id: str | None = None


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
    # Additive identity guard for v1 callers supplying authenticated person IDs.
    # Callers without those fields keep the historical v1 behavior (and therefore
    # must NOT claim the identity-safe DP-318 proof).
    if prior.person_id and later.person_id and prior.person_id != later.person_id:
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.SAME_PROPOSITION,
            ("CROSS_PERSON_NO_POSITION_CHANGE",),
            None,
        )
    if bool(prior.person_id) != bool(later.person_id):
        return RelationCandidateResult(
            prior.claim_id,
            later.claim_id,
            RelationCandidateType.SAME_PROPOSITION,
            ("PERSON_ID_INCOMPLETE_NO_POSITION_CHANGE",),
            None,
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


# DP-318: private, explicitly typed semantic relation path. This is NOT the
# existing database relation vocabulary or an approval/publication API.
SCOPED_STATEMENT_RELATION_VERSION = "scoped-statement-relation-v1"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_KINDS = frozenset({"FACTUAL", "OPINION"})
_VALID_POSITIONS = frozenset({"SUPPORT", "OPPOSE"})
_VALID_MODALITIES = frozenset({"ASSERTED"})
_UNVERIFIED_REFS = frozenset({"UNKNOWN", "UNSPECIFIED", "UNRESOLVED"})


class StatementRelationKind(StrEnum):
    HOLD = "HOLD"
    CROSS_PERSON_AGREEMENT = "CROSS_PERSON_AGREEMENT"
    CROSS_PERSON_DIVERGENCE = "CROSS_PERSON_DIVERGENCE"
    SAME_PERSON_REAFFIRMATION = "SAME_PERSON_REAFFIRMATION"
    SAME_PERSON_POSITION_CHANGE_CANDIDATE = "SAME_PERSON_POSITION_CHANGE_CANDIDATE"
    SAME_PERSON_CONTRADICTION_CANDIDATE = "SAME_PERSON_CONTRADICTION_CANDIDATE"


@dataclass(frozen=True)
class StatementRelationScope:
    jurisdiction_ref: str
    subject_ref: str
    period_start: str
    period_end: str
    modality: str
    condition_ref: str
    location_ref: str = ""
    qualifier_ref: str = "NONE"


@dataclass(frozen=True)
class ScopedStatementRelationInput:
    statement_id: str
    person_id: str
    statement_date: str
    proposition_key: str | None
    equivalence_review_ref: str | None
    statement_kind: str
    position: str
    scope: StatementRelationScope
    speech_act: SpeechActContextDecision
    denial_kind: str = "NONE"
    asserts_past_continuity: bool = False


@dataclass(frozen=True)
class ScopedStatementRelationDecision:
    subject_statement_id: str
    object_statement_id: str
    kind: StatementRelationKind
    state: str
    person_cardinality: int
    statement_kinds: tuple[str, str]
    finding_required: bool
    source_context_bindings: tuple[str, str]
    rationale_codes: tuple[str, ...]
    binding_sha256: str
    version: str = SCOPED_STATEMENT_RELATION_VERSION

    @property
    def review_authority(self) -> bool:
        return False

    @property
    def publication_authority(self) -> bool:
        return False

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


def _iso_date(value: str, *, field: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ValueError(f"RELATION_{field}_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"RELATION_{field}_DATE_INVALID") from exc


def _validated_scope(scope: StatementRelationScope) -> tuple[str, ...]:
    if not isinstance(scope, StatementRelationScope):
        raise ValueError("RELATION_SCOPE_INVALID")
    begin = _iso_date(scope.period_start, field="SCOPE")
    finish = _iso_date(scope.period_end, field="SCOPE")
    if begin > finish:
        raise ValueError("RELATION_SCOPE_INVALID")
    fields = (
        scope.jurisdiction_ref,
        scope.subject_ref,
        scope.period_start,
        scope.period_end,
        scope.modality,
        scope.condition_ref,
        scope.location_ref,
        scope.qualifier_ref,
    )
    if any(not isinstance(value, str) for value in fields):
        raise ValueError("RELATION_SCOPE_INVALID")
    return fields


def evaluate_scoped_statement_relation(
    first: ScopedStatementRelationInput,
    second: ScopedStatementRelationInput,
) -> ScopedStatementRelationDecision:
    """Deterministic private hypothesis; source speech-act is not an approval receipt.

    A shared proposition key/review ref is a *claimed* matching aid, never proof
    of equivalence or review authority. Downstream adapters must independently
    revalidate persons, versions, actual review events and publication rights.
    """
    if not isinstance(first, ScopedStatementRelationInput) or not isinstance(
        second, ScopedStatementRelationInput
    ):
        raise ValueError("RELATION_SCOPED_INPUT_INVALID")
    for row in (first, second):
        if not isinstance(row.statement_id, str) or not row.statement_id.strip():
            raise ValueError("RELATION_STATEMENT_ID_REQUIRED")
        _iso_date(row.statement_date, field="STATEMENT")
        _validated_scope(row.scope)
        if not isinstance(row.asserts_past_continuity, bool):
            raise ValueError("RELATION_RETROSPECTIVE_CONTINUITY_INVALID")
    if first.statement_id == second.statement_id:
        raise ValueError("RELATION_SELF_REFUSED")
    left, right = sorted(
        (first, second), key=lambda row: (row.statement_date, row.statement_id)
    )
    rationale: list[str] = []
    for row in (left, right):
        if not isinstance(row.person_id, str) or not row.person_id.strip():
            rationale.append("PERSON_ID_UNVERIFIED")
        if (
            not isinstance(row.speech_act, SpeechActContextDecision)
            or row.speech_act.version != SPEECH_ACT_CONTEXT_VERSION
            or not _HASH_RE.fullmatch(row.speech_act.binding_sha256)
        ):
            rationale.append("SPEECH_ACT_PROVENANCE_UNVERIFIED")
            continue
        semantic = row.speech_act
        semantic_material = asdict(semantic)
        semantic_binding = semantic_material.pop("binding_sha256")
        expected_semantic_binding = hashlib.sha256(
            json.dumps(
                semantic_material, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if semantic_binding != expected_semantic_binding:
            rationale.append("SPEECH_ACT_BINDING_TAMPERED")
        if row.person_id != semantic.utterer_id:
            rationale.append("PERSON_UTTERER_MISMATCH")
        if (
            semantic.state != "CANDIDATE_PRIVATE"
            or semantic.signal_codes
            or semantic.stance != "ENDORSE"
            or semantic.speech_act not in {"ASSERTION", "OPINION"}
            or semantic.quoted_author_id is not None
        ):
            rationale.append("NON_ENDORSED_OR_REPORTED_SPEECH")
        if row.statement_kind not in _VALID_KINDS or (
            row.statement_kind == "OPINION" and semantic.speech_act != "OPINION"
        ) or (
            row.statement_kind == "FACTUAL" and semantic.speech_act != "ASSERTION"
        ):
            rationale.append("STATEMENT_KIND_ACT_MISMATCH")
        if row.denial_kind != "NONE":
            rationale.append("DENIAL_ROLE_UNRESOLVED")
        if row.position not in _VALID_POSITIONS:
            rationale.append("POSITION_NOT_REVIEWED")
        if (
            not _HASH_RE.fullmatch(semantic.source_sha256)
            or not _HASH_RE.fullmatch(semantic.context_sha256)
            or not _HASH_RE.fullmatch(semantic.quote_sha256)
        ):
            rationale.append("SOURCE_CONTEXT_BINDING_INVALID")
    if (
        not isinstance(left.proposition_key, str)
        or not isinstance(right.proposition_key, str)
        or not left.proposition_key.strip()
        or not right.proposition_key.strip()
        or left.proposition_key.upper() in _UNVERIFIED_REFS
        or right.proposition_key.upper() in _UNVERIFIED_REFS
        or (
        left.proposition_key != right.proposition_key
        )
    ):
        rationale.append("PROPOSITION_EQUIVALENCE_UNVERIFIED")
    if (
        not isinstance(left.equivalence_review_ref, str)
        or not isinstance(right.equivalence_review_ref, str)
        or not left.equivalence_review_ref.strip()
        or left.equivalence_review_ref.upper() in _UNVERIFIED_REFS
        or left.equivalence_review_ref != right.equivalence_review_ref
    ):
        rationale.append("EQUIVALENCE_REVIEW_REF_UNVERIFIED")
    if left.scope != right.scope:
        rationale.append("PROPOSITION_SCOPE_MISMATCH")
    for row in (left, right):
        if (
            row.scope.modality not in _VALID_MODALITIES
            or row.scope.condition_ref != "NONE"
            or not row.scope.jurisdiction_ref.strip()
            or not row.scope.subject_ref.strip()
            or not row.scope.location_ref.strip()
            or not row.scope.qualifier_ref.strip()
            or any(value.upper() in _UNVERIFIED_REFS for value in (
                row.scope.jurisdiction_ref,
                row.scope.subject_ref,
                row.scope.location_ref,
                row.scope.qualifier_ref,
            ))
        ):
            rationale.append("CONDITIONAL_OR_UNKNOWN_SCOPE")
    if left.statement_kind != right.statement_kind:
        rationale.append("STATEMENT_KIND_MISMATCH")
    if (
        left.position != right.position
        and isinstance(left.speech_act, SpeechActContextDecision)
        and isinstance(right.speech_act, SpeechActContextDecision)
        and left.speech_act.quote_sha256 == right.speech_act.quote_sha256
    ):
        rationale.append("IDENTICAL_QUOTATION_OPPOSITE_POSITION_UNSUPPORTED")

    same_person = bool(left.person_id) and left.person_id == right.person_id
    person_cardinality = (
        1 if same_person else 2 if left.person_id and right.person_id else 0
    )
    if rationale:
        kind = StatementRelationKind.HOLD
    elif not same_person:
        kind = (
            StatementRelationKind.CROSS_PERSON_AGREEMENT
            if left.position == right.position
            else StatementRelationKind.CROSS_PERSON_DIVERGENCE
        )
    elif left.position == right.position:
        kind = StatementRelationKind.SAME_PERSON_REAFFIRMATION
    elif left.statement_date == right.statement_date or right.asserts_past_continuity:
        kind = StatementRelationKind.SAME_PERSON_CONTRADICTION_CANDIDATE
    else:
        kind = StatementRelationKind.SAME_PERSON_POSITION_CHANGE_CANDIDATE
    if kind == StatementRelationKind.SAME_PERSON_CONTRADICTION_CANDIDATE and (
        right.asserts_past_continuity
    ):
        rationale.append("RETROSPECTIVE_CONTINUITY_CANDIDATE")

    def _context_binding(row: ScopedStatementRelationInput) -> str:
        return (
            row.speech_act.binding_sha256
            if isinstance(row.speech_act, SpeechActContextDecision)
            else ""
        )

    material = {
        "left": asdict(left),
        "right": asdict(right),
        "kind": kind.value,
        "rationale": tuple(dict.fromkeys(rationale)),
        "version": SCOPED_STATEMENT_RELATION_VERSION,
    }
    binding = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return ScopedStatementRelationDecision(
        subject_statement_id=left.statement_id,
        object_statement_id=right.statement_id,
        kind=kind,
        state="HOLD" if kind == StatementRelationKind.HOLD else "CANDIDATE_PRIVATE",
        person_cardinality=person_cardinality,
        statement_kinds=(left.statement_kind, right.statement_kind),
        finding_required=left.statement_kind == "FACTUAL" or right.statement_kind == "FACTUAL",
        source_context_bindings=(_context_binding(left), _context_binding(right)),
        rationale_codes=tuple(dict.fromkeys(rationale)),
        binding_sha256=binding,
    )
