"""DP-303 — correction / takedown / appeal append-only workflow.

This module is the *pure state machine* half of DP-303. It does not fork
``correction_runtime``; it imports and re-uses that module's deterministic
identifiers and bounds so the private runtime and the policy can never disagree
about what a correction or a reply is. The functions below add only the
transition/authority layer that ``correction_runtime`` deliberately does not
have (that module is validation + identity; this one is transitions + gates).

Invariants encoded here
-----------------------
C-303-01 append-only history      : a material change is a NEW record. Nothing
                                    here mutates or deletes a prior record.
C-303-02 explicit authority       : every transition names a role, and records
                                    actor/reason/policy version.
C-303-03 no status-only authority : a state value NEVER authorizes publication.
                                    ``publication_authorized()`` is a separate
                                    conjunction and always false for a bare
                                    status string.
C-303-04 no intent inference      : a correction or appeal changes an assessment
                                    or a public version; it never establishes
                                    that a person lied. Enforced by
                                    ``NO_INTENT_DERIVATION`` and by the label scan.
C-303-05 private pending content  : intake/triage/hold states are private.
C-303-06 reversible omission      : a takedown HOLD removes current public
                                    output; it never destroys the record.
C-303-07 fair review separation   : the appeal reviewer must differ from the
                                    original reviewer, or an explicit recorded
                                    exception is required.
C-303-08 fail closed              : any missing prerequisite -> HOLD/OMIT.

Pure, zero-I/O, deterministic, importable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dichiarazioni_pubbliche.correction_runtime import (
    MAX_CORRECTION_REASON_CHARS,
    deterministic_correction_id,
    deterministic_right_of_reply_id,
)
from dichiarazioni_pubbliche.policy.intent_policy import scan_public_label

CHALLENGE_WORKFLOW_VERSION = "challenge-workflow-v1"

# C-303-04. Exported so callers and tests can assert against it directly.
NO_INTENT_DERIVATION = (
    "A correction, takedown, or appeal may change an assessment or a public "
    "version. It never establishes intent, deception, or bad faith."
)


class ChallengeKind(StrEnum):
    CORRECTION = "CORRECTION"
    TAKEDOWN = "TAKEDOWN"
    APPEAL = "APPEAL"


class ChallengeState(StrEnum):
    """Logical states. Names may map to database values, transitions may not be
    relaxed (DP-303 "State and transition contract")."""

    PRIVATE_RECEIVED = "PRIVATE_RECEIVED"
    REANALYSIS_PENDING = "REANALYSIS_PENDING"
    TRIAGE_PENDING = "TRIAGE_PENDING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INDEPENDENT_REVIEW_PENDING = "INDEPENDENT_REVIEW_PENDING"
    PUBLIC_VERSIONED = "PUBLIC_VERSIONED"
    PUBLIC_HOLD_APPROVED = "PUBLIC_HOLD_APPROVED"
    UPHELD = "UPHELD"
    OVERTURNED = "OVERTURNED"
    NEEDS_INFO = "NEEDS_INFO"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    REFERRED = "REFERRED"


class ChallengeRole(StrEnum):
    """Who may perform each action (C-303-02, E-303-11)."""

    PUBLIC_SUBMITTER = "PUBLIC_SUBMITTER"
    INTAKE_ADAPTER = "INTAKE_ADAPTER"
    TRIAGE_REVIEWER = "TRIAGE_REVIEWER"
    DECISION_REVIEWER = "DECISION_REVIEWER"
    APPEAL_REVIEWER = "APPEAL_REVIEWER"
    OPERATOR = "OPERATOR"


class TransitionBlocker(StrEnum):
    OK = "OK"
    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION"
    ROLE_NOT_AUTHORIZED = "ROLE_NOT_AUTHORIZED"
    TARGET_UNKNOWN = "TARGET_UNKNOWN"
    TARGET_KIND_MISMATCH = "TARGET_KIND_MISMATCH"
    CHAIN_MISSING = "CHAIN_MISSING"
    CHAIN_NOT_LEAF = "CHAIN_NOT_LEAF"
    TRIGGER_NOT_PROCESSED = "TRIGGER_NOT_PROCESSED"
    FINDING_REVIEW_MISSING = "FINDING_REVIEW_MISSING"
    CHALLENGE_REVIEW_MISSING = "CHALLENGE_REVIEW_MISSING"
    STALE_REVIEW = "STALE_REVIEW"
    REVIEWER_NOT_SEPARATE = "REVIEWER_NOT_SEPARATE"
    SEPARATION_EXCEPTION_MISSING = "SEPARATION_EXCEPTION_MISSING"
    SUPERSEDING_FINDING_MISSING = "SUPERSEDING_FINDING_MISSING"
    INTENT_LANGUAGE_IN_PUBLIC_COPY = "INTENT_LANGUAGE_IN_PUBLIC_COPY"
    REASON_TOO_LONG = "REASON_TOO_LONG"
    RETENTION_HOLD_ACTIVE = "RETENTION_HOLD_ACTIVE"


# The transition table from the DP-303 state contract. Anything not listed here
# is an ILLEGAL_TRANSITION -- including any transition that would make a private
# state public without the required gate.
ALLOWED_TRANSITIONS: dict[ChallengeKind, dict[ChallengeState, frozenset[ChallengeState]]] = {
    ChallengeKind.CORRECTION: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {ChallengeState.REANALYSIS_PENDING, ChallengeState.QUARANTINED, ChallengeState.REJECTED}
        ),
        ChallengeState.REANALYSIS_PENDING: frozenset(
            {ChallengeState.REVIEW_REQUIRED, ChallengeState.QUARANTINED}
        ),
        ChallengeState.REVIEW_REQUIRED: frozenset(
            {
                ChallengeState.PUBLIC_VERSIONED,
                ChallengeState.REJECTED,
                ChallengeState.QUARANTINED,
            }
        ),
        ChallengeState.PUBLIC_VERSIONED: frozenset(),
    },
    ChallengeKind.TAKEDOWN: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {
                ChallengeState.TRIAGE_PENDING,
                ChallengeState.REJECTED,
                ChallengeState.QUARANTINED,
            }
        ),
        ChallengeState.TRIAGE_PENDING: frozenset(
            {
                ChallengeState.PUBLIC_HOLD_APPROVED,
                ChallengeState.REJECTED,
                ChallengeState.REFERRED,
                ChallengeState.QUARANTINED,
            }
        ),
        ChallengeState.PUBLIC_HOLD_APPROVED: frozenset(
            {
                ChallengeState.REVIEW_REQUIRED,
                ChallengeState.REJECTED,
                ChallengeState.REFERRED,
            }
        ),
    },
    ChallengeKind.APPEAL: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {
                ChallengeState.INDEPENDENT_REVIEW_PENDING,
                ChallengeState.REJECTED,
                ChallengeState.QUARANTINED,
            }
        ),
        ChallengeState.INDEPENDENT_REVIEW_PENDING: frozenset(
            {
                ChallengeState.UPHELD,
                ChallengeState.OVERTURNED,
                ChallengeState.NEEDS_INFO,
                ChallengeState.REJECTED,
            }
        ),
    },
}

# Who may initiate / advance each challenge kind. Intake cannot reach a
# decision state (C-302-07, E-303-11, B-302-02).
ALLOWED_ACTOR_ROLES: dict[ChallengeKind, dict[ChallengeState, frozenset[ChallengeRole]]] = {
    ChallengeKind.CORRECTION: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {ChallengeRole.PUBLIC_SUBMITTER, ChallengeRole.INTAKE_ADAPTER, ChallengeRole.OPERATOR}
        ),
        ChallengeState.REANALYSIS_PENDING: frozenset(
            {ChallengeRole.OPERATOR, ChallengeRole.DECISION_REVIEWER}
        ),
        ChallengeState.REVIEW_REQUIRED: frozenset({ChallengeRole.DECISION_REVIEWER}),
        ChallengeState.PUBLIC_VERSIONED: frozenset({ChallengeRole.DECISION_REVIEWER}),
    },
    ChallengeKind.TAKEDOWN: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {ChallengeRole.PUBLIC_SUBMITTER, ChallengeRole.INTAKE_ADAPTER, ChallengeRole.OPERATOR}
        ),
        ChallengeState.TRIAGE_PENDING: frozenset(
            {ChallengeRole.TRIAGE_REVIEWER, ChallengeRole.OPERATOR}
        ),
        ChallengeState.PUBLIC_HOLD_APPROVED: frozenset({ChallengeRole.TRIAGE_REVIEWER}),
        ChallengeState.REVIEW_REQUIRED: frozenset({ChallengeRole.DECISION_REVIEWER}),
    },
    ChallengeKind.APPEAL: {
        ChallengeState.PRIVATE_RECEIVED: frozenset(
            {ChallengeRole.PUBLIC_SUBMITTER, ChallengeRole.INTAKE_ADAPTER, ChallengeRole.OPERATOR}
        ),
        ChallengeState.INDEPENDENT_REVIEW_PENDING: frozenset({ChallengeRole.APPEAL_REVIEWER}),
        ChallengeState.UPHELD: frozenset({ChallengeRole.APPEAL_REVIEWER}),
        ChallengeState.OVERTURNED: frozenset({ChallengeRole.APPEAL_REVIEWER}),
        ChallengeState.NEEDS_INFO: frozenset({ChallengeRole.APPEAL_REVIEWER}),
    },
}

# States whose public visibility is a *hold/omission*, never a deletion
# (C-303-06) and never an approval.
OMISSION_STATES: frozenset[ChallengeState] = frozenset(
    {ChallengeState.PUBLIC_HOLD_APPROVED}
)

PRIVATE_STATES: frozenset[ChallengeState] = frozenset(
    {
        ChallengeState.PRIVATE_RECEIVED,
        ChallengeState.REANALYSIS_PENDING,
        ChallengeState.TRIAGE_PENDING,
        ChallengeState.REVIEW_REQUIRED,
        ChallengeState.INDEPENDENT_REVIEW_PENDING,
    }
)


@dataclass(frozen=True)
class ChallengeContext:
    """Bounded, already-resolved facts. No I/O is performed by this module."""

    kind: ChallengeKind | str
    current_state: ChallengeState | str
    actor_role: ChallengeRole | str
    actor_id: str
    reason: str = ""
    # Target resolution
    target_record_exists: bool = True
    target_is_leaf: bool = True
    # Correction chain (E-303-03)
    superseding_finding_id: str | None = None
    supersedes_chain_valid: bool = False
    # Re-analysis (E-303-04)
    reanalysis_trigger_processed: bool = False
    # Reviews (E-303-05)
    target_finding_review_approved: bool = False
    challenge_review_approved: bool = False
    review_is_stale: bool = False
    # Appeal separation (E-303-08)
    original_reviewer_id: str | None = None
    separation_exception_recorded: bool = False
    # Public copy (E-303-09, DP-301 hard rule)
    public_notice_text: str | None = None
    # Retention (E-303-10)
    retention_hold_active: bool = False


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    next_state: ChallengeState
    blockers: tuple[TransitionBlocker, ...]

    @property
    def reason(self) -> str:
        return self.blockers[0].value if self.blockers else TransitionBlocker.OK.value


def _coerce(kind: ChallengeKind | str) -> ChallengeKind | None:
    try:
        return ChallengeKind(str(kind))
    except ValueError:
        return None


def _coerce_state(state: ChallengeState | str) -> ChallengeState | None:
    try:
        return ChallengeState(str(state))
    except ValueError:
        return None


def _coerce_role(role: ChallengeRole | str) -> ChallengeRole | None:
    try:
        return ChallengeRole(str(role))
    except ValueError:
        return None


def evaluate_transition(context: ChallengeContext) -> TransitionDecision:
    """Decide one transition. Fails closed: the current state is retained on
    any blocker, so the caller never has to guess what the record now is.

    Order is fixed for deterministic diagnostics: structural validity, then role
    authority, then the state table, then the kind-specific gates.
    """
    kind = _coerce(context.kind)
    state = _coerce_state(context.current_state)
    role = _coerce_role(context.actor_role)

    if kind is None:
        return TransitionDecision(
            False, ChallengeState.PRIVATE_RECEIVED, (TransitionBlocker.TARGET_KIND_MISMATCH,)
        )
    if state is None:
        return TransitionDecision(
            False, ChallengeState.PRIVATE_RECEIVED, (TransitionBlocker.ILLEGAL_TRANSITION,)
        )

    # A retention/legal hold freezes every challenge transition.
    if context.retention_hold_active:
        return TransitionDecision(False, state, (TransitionBlocker.RETENTION_HOLD_ACTIVE,))

    if not context.target_record_exists:
        return TransitionDecision(False, state, (TransitionBlocker.TARGET_UNKNOWN,))

    if len(str(context.reason or "")) > MAX_CORRECTION_REASON_CHARS:
        return TransitionDecision(False, state, (TransitionBlocker.REASON_TOO_LONG,))

    if context.public_notice_text is not None and scan_public_label(
        context.public_notice_text
    ):
        return TransitionDecision(
            False, state, (TransitionBlocker.INTENT_LANGUAGE_IN_PUBLIC_COPY,)
        )

    permitted_roles = ALLOWED_ACTOR_ROLES[kind].get(state)
    if role is None or permitted_roles is None or role not in permitted_roles:
        return TransitionDecision(False, state, (TransitionBlocker.ROLE_NOT_AUTHORIZED,))

    next_state = _resolve_next_state(kind, state, context, role)

    if next_state is None:
        return TransitionDecision(False, state, (TransitionBlocker.ILLEGAL_TRANSITION,))

    blockers = _gate_blockers(kind, next_state, context, role)
    if blockers:
        return TransitionDecision(False, state, blockers)
    return TransitionDecision(True, next_state, (TransitionBlocker.OK,))


def _resolve_next_state(
    kind: ChallengeKind,
    state: ChallengeState,
    context: ChallengeContext,
    role: ChallengeRole,
) -> ChallengeState | None:
    """Pick the destination implied by the guards. Returns None when the
    transition is structurally illegal."""
    allowed = ALLOWED_TRANSITIONS[kind].get(state, frozenset())

    if kind is ChallengeKind.CORRECTION:
        if state is ChallengeState.PRIVATE_RECEIVED:
            if not context.superseding_finding_id or not context.supersedes_chain_valid:
                # An incomplete chain is a reject, not a silent accept.
                return (
                    ChallengeState.REJECTED
                    if ChallengeState.REJECTED in allowed
                    else None
                )
            return ChallengeState.REANALYSIS_PENDING
        if state is ChallengeState.REANALYSIS_PENDING:
            if context.reanalysis_trigger_processed:
                return ChallengeState.REVIEW_REQUIRED
            return None
        if state is ChallengeState.REVIEW_REQUIRED:
            if (
                context.challenge_review_approved
                and context.target_finding_review_approved
                and not context.review_is_stale
            ):
                return ChallengeState.PUBLIC_VERSIONED
            return (
                ChallengeState.REJECTED
                if ChallengeState.REJECTED in allowed
                else None
            )
        return None

    if kind is ChallengeKind.TAKEDOWN:
        if state is ChallengeState.PRIVATE_RECEIVED:
            return ChallengeState.TRIAGE_PENDING
        if state is ChallengeState.TRIAGE_PENDING:
            if context.challenge_review_approved:
                return ChallengeState.PUBLIC_HOLD_APPROVED
            return ChallengeState.REFERRED
        if state is ChallengeState.PUBLIC_HOLD_APPROVED:
            if context.target_finding_review_approved:
                return ChallengeState.REVIEW_REQUIRED
            return None
        return None

    # APPEAL
    if state is ChallengeState.PRIVATE_RECEIVED:
        if (
            context.original_reviewer_id
            and context.actor_id == context.original_reviewer_id
            and not context.separation_exception_recorded
        ):
            # C-303-07: an appeal cannot be decided by the original reviewer
            # without an explicit recorded exception.
            return None
        return ChallengeState.INDEPENDENT_REVIEW_PENDING
    if state is ChallengeState.INDEPENDENT_REVIEW_PENDING:
        if not context.challenge_review_approved:
            return ChallengeState.NEEDS_INFO
        if (
            context.original_reviewer_id
            and context.actor_id == context.original_reviewer_id
            and not context.separation_exception_recorded
        ):
            return ChallengeState.NEEDS_INFO
        if context.reanalysis_trigger_processed and context.target_finding_review_approved:
            return ChallengeState.UPHELD
        return ChallengeState.OVERTURNED
    return None


def _gate_blockers(
    kind: ChallengeKind,
    next_state: ChallengeState,
    context: ChallengeContext,
    role: ChallengeRole,
) -> tuple[TransitionBlocker, ...]:
    blockers: list[TransitionBlocker] = []

    if context.review_is_stale:
        blockers.append(TransitionBlocker.STALE_REVIEW)

    if kind is ChallengeKind.CORRECTION and next_state in {
        ChallengeState.PUBLIC_VERSIONED,
        ChallengeState.REVIEW_REQUIRED,
    }:
        if not context.superseding_finding_id:
            blockers.append(TransitionBlocker.SUPERSEDING_FINDING_MISSING)
        if not context.supersedes_chain_valid:
            blockers.append(TransitionBlocker.CHAIN_MISSING)
        if not context.target_is_leaf:
            blockers.append(TransitionBlocker.CHAIN_NOT_LEAF)
        if not context.reanalysis_trigger_processed:
            blockers.append(TransitionBlocker.TRIGGER_NOT_PROCESSED)
        if not context.target_finding_review_approved:
            blockers.append(TransitionBlocker.FINDING_REVIEW_MISSING)
        if not context.challenge_review_approved:
            blockers.append(TransitionBlocker.CHALLENGE_REVIEW_MISSING)

    if kind is ChallengeKind.TAKEDOWN and next_state is ChallengeState.PUBLIC_HOLD_APPROVED:
        if not context.challenge_review_approved:
            blockers.append(TransitionBlocker.CHALLENGE_REVIEW_MISSING)

    if kind is ChallengeKind.APPEAL and next_state in {
        ChallengeState.UPHELD,
        ChallengeState.OVERTURNED,
    }:
        if not context.challenge_review_approved:
            blockers.append(TransitionBlocker.CHALLENGE_REVIEW_MISSING)
        if (
            context.original_reviewer_id
            and context.actor_id == context.original_reviewer_id
            and not context.separation_exception_recorded
        ):
            blockers.append(TransitionBlocker.REVIEWER_NOT_SEPARATE)

    return tuple(blockers)


def publication_authorized(
    context: ChallengeContext,
    decision: TransitionDecision,
) -> bool:
    """C-303-03: publication is never implicit and never status-only.

    Returns True only when a full, non-stale correction decision landed on
    PUBLIC_VERSIONED. A bare status value can never produce True.
    """
    if not decision.allowed:
        return False
    if context.kind != ChallengeKind.CORRECTION:
        return False
    if decision.next_state is not ChallengeState.PUBLIC_VERSIONED:
        return False
    return (
        context.challenge_review_approved
        and context.target_finding_review_approved
        and context.reanalysis_trigger_processed
        and context.supersedes_chain_valid
        and context.target_is_leaf
        and not context.review_is_stale
        and not context.retention_hold_active
    )


def public_omission_required(context: ChallengeContext) -> bool:
    """C-303-06: an approved takedown hold removes the current public projection
    while the durable record and audit trail are retained."""
    if context.kind != ChallengeKind.TAKEDOWN:
        return False
    return (
        context.current_state == ChallengeState.PUBLIC_HOLD_APPROVED
        and context.challenge_review_approved
    )


def is_private_state(state: ChallengeState | str) -> bool:
    """C-303-05: challenge content is private until its own review."""
    coerced = _coerce_state(state)
    return coerced is not None and coerced in PRIVATE_STATES


def build_correction_record_id(
    *,
    finding_id: str,
    previous_finding_id: str,
    reason: str,
    changed_fields: dict[str, object],
) -> str:
    """Re-export of the private runtime's deterministic correction ID.

    Present so a caller never has to choose between the policy module and
    ``correction_runtime``; the two cannot drift because this *is* that function.
    """
    return deterministic_correction_id(
        finding_id=finding_id,
        previous_finding_id=previous_finding_id,
        reason=reason,
        changed_fields=changed_fields,
    )


def build_reply_record_id(
    *,
    finding_id: str,
    body: str,
    submitter_name: str | None,
    submitter_role: str | None,
    evidence_urls: list[str],
) -> str:
    """Re-export of the private runtime's deterministic reply ID (E-303-01)."""
    return deterministic_right_of_reply_id(
        finding_id=finding_id,
        body=body,
        submitter_name=submitter_name,
        submitter_role=submitter_role,
        evidence_urls=evidence_urls,
    )


__all__ = [
    "ALLOWED_ACTOR_ROLES",
    "ALLOWED_TRANSITIONS",
    "CHALLENGE_WORKFLOW_VERSION",
    "ChallengeContext",
    "ChallengeKind",
    "ChallengeRole",
    "ChallengeState",
    "MAX_CORRECTION_REASON_CHARS",
    "NO_INTENT_DERIVATION",
    "OMISSION_STATES",
    "PRIVATE_STATES",
    "TransitionBlocker",
    "TransitionDecision",
    "build_correction_record_id",
    "build_reply_record_id",
    "evaluate_transition",
    "is_private_state",
    "public_omission_required",
    "publication_authorized",
]
