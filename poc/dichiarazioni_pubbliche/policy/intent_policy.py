"""DP-301 — intentionality policy: the machine-checkable boundary.

Product invariant (PRODUCT.md, "Political neutrality and human agency"):

    No inference that a contradiction proves deception or malicious intent.
    A position change is not automatically a lie.
    A false factual claim is not automatically a deliberate falsehood.

This module turns that prose into a *closed, enumerable* boundary:

1. ``AssessmentIntent`` — the allowed kinds of statements the product can make
   about a claim. Every one is claim-level. None is about a speaker's state of
   mind. There is deliberately no member expressing intent.
2. ``PUBLIC_INTENT_PROHIBITED_TERMS`` — the normalized English/Italian term
   families that must never appear in any public-facing label. This is the
   *shared* source of truth; ``relation_policy.PROHIBITED_INTENT_TERMS`` and
   the new policy modules all derive from or re-assert it.
3. ``scan_public_label()`` — deterministic, case/diacritic/underscore-insensitive
   detection of a prohibited term anywhere in a public label, key, or enum value.
4. ``classify_text_intent_risk()`` — classifies *untrusted* submitted text
   (extraction output, reviewer note, reply body) into a hold disposition. It
   never rewrites the text into an intent claim; it only decides whether the
   text may be promoted to a public label at all.
5. ``assess_publishability()`` — the fail-closed conjunction required before a
   claim-level assessment can reach the public projection.

The module is pure: no I/O, no clock, no randomness, no database.

Design note on the hard rule
-----------------------------
A `contradiction` relation NEVER implies lying, deliberate falsehood, bad faith,
or motive. The reason `RelationCandidateType.CONTRADICTION_CANDIDATE` is
*absent* from every allowed assessment mapping is deliberate: a relation is
descriptive context, never an assessment. ``relation_to_assessment()`` returns
``None`` for contradiction/position-change rather than inventing a mapping.
That ``None`` is the machine-checkable form of the product invariant.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from dichiarazioni_pubbliche.domain_vocabulary import (
    CLAIM_TYPE_VERSION,
    RELATION_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    FindingPublicationStatus,
    RelationCandidateType,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.relation_policy import PROHIBITED_INTENT_TERMS

INTENT_POLICY_VERSION = "intentionality-policy-v1"

# The only assessment values the v1 public surface may ever carry.
# Mirrors public_schema.PUBLISHABLE_ASSESSMENTS but is owned by policy so the
# policy can be unit-tested without importing the projection module.
PUBLIC_ASSESSMENTS: frozenset[VerificationAssessment] = frozenset(
    {
        VerificationAssessment.SUPPORTED,
        VerificationAssessment.FACTUALLY_FALSE,
        VerificationAssessment.OUTDATED_DATA,
    }
)

# Assessments that are legal to *hold* but never to publish as a verdict.
NON_PUBLISHABLE_ASSESSMENTS: frozenset[VerificationAssessment] = frozenset(
    set(VerificationAssessment) - PUBLIC_ASSESSMENTS
)

# Vocabulary versions this policy is pinned to. If domain_vocabulary bumps a
# version, the policy must be re-reviewed before it can be trusted again.
PINNED_VOCABULARY_VERSIONS: dict[str, str] = {
    "claim_type": CLAIM_TYPE_VERSION,
    "verification_assessment": VERIFICATION_ASSESSMENT_VERSION,
    "relation_candidate": RELATION_VERSION,
}


class AssessmentIntent(StrEnum):
    """The complete, closed set of things an assessment may be *about*.

    Every member is a claim-level proposition. No member describes a speaker's
    knowledge, intent, belief, or good/bad faith. Adding an intent-bearing
    member here is a product-invariant violation, which is why the enum is
    sealed by test and by ``assert_no_intent_member()``.
    """

    SUPPORTED_BY_EVIDENCE = "SUPPORTED_BY_EVIDENCE"
    CONTRADICTED_BY_EVIDENCE = "CONTRADICTED_BY_EVIDENCE"
    STALE_AT_STATEMENT_TIME = "STALE_AT_STATEMENT_TIME"
    UNRESOLVED_BY_AVAILABLE_EVIDENCE = "UNRESOLVED_BY_AVAILABLE_EVIDENCE"


class IntentTextRisk(StrEnum):
    """Disposition for *untrusted* text that may contain intent language."""

    ALLOWED = "ALLOWED"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    PROHIBITED_LABEL = "PROHIBITED_LABEL"


class PublishabilityBlocker(StrEnum):
    """Machine-readable reasons a claim-level assessment is not projectable."""

    OK = "OK"
    UNKNOWN_ASSESSMENT = "UNKNOWN_ASSESSMENT"
    NON_PUBLISHABLE_ASSESSMENT = "NON_PUBLISHABLE_ASSESSMENT"
    NO_APPROVED_REVIEW_EVENT = "NO_APPROVED_REVIEW_EVENT"
    NO_VERIFICATION_RULE_VERSION = "NO_VERIFICATION_RULE_VERSION"
    NO_STATEMENT_CUTOFF = "NO_STATEMENT_CUTOFF"
    NO_APPROVED_EVIDENCE = "NO_APPROVED_EVIDENCE"
    NO_APPROVED_OBSERVATIONS = "NO_APPROVED_OBSERVATIONS"
    STALE_REVIEW = "STALE_REVIEW"
    FUTURE_EVIDENCE_USED = "FUTURE_EVIDENCE_USED"
    INTENT_LANGUAGE_IN_LABEL = "INTENT_LANGUAGE_IN_LABEL"
    LIMITATIONS_MISSING = "LIMITATIONS_MISSING"


# --------------------------------------------------------------------------
# Prohibited intent vocabulary (English + Italian)
# --------------------------------------------------------------------------
# Sourced from PRODUCT.md / CONTEXT.md ("contradiction != proof of intent",
# "false claim != deliberate falsehood", "position change != lie") and from
# the existing relation_policy.PROHIBITED_INTENT_TERMS which this module
# re-exports rather than duplicating. Italian families are added here because
# the product is Italy-first and public copy is Italian-facing.
_PROHIBITED_BASE: frozenset[str] = frozenset(PROHIBITED_INTENT_TERMS)

# Families present in PRODUCT.md/CONTEXT.md prose but absent from
# relation_policy's narrower list. Extending (not replacing) keeps the existing
# vocabulary guard authoritative while making the public-label scan match the
# invariant's own wording.
_PROHIBITED_EXTENDED: frozenset[str] = frozenset(
    {
        "deliberate",
        "deliberately",
        "dishonest",
        "dishonestly",
        "deceived",
        "intent_to_deceive",
        "mens rea",
        "mens_rea",
        "knowledge_of_falsity",
        "wilful",
        "willingly",
        "knowingly",
        "scienter",
        "dolo_dolo",
    }
)

_PROHIBITED_ITALIAN: frozenset[str] = frozenset(
    {
        "bugiardo",
        "bugiarda",
        "menzogna",
        "menzogne",
        "menzognero",
        "dolo",
        "doloso",
        "dolosa",
        "dolosi",
        "mala fede",
        "mala_fede",
        "malafede",
        "disonesto",
        "disonesta",
        "inganno",
        "ingannato",
        "fraudolento",
        "intenzionale",
        "intenzionalita",
        "intenzionalmente",
        "consapevolmente",
        "dolorosamente",
        "bugiardone",
    }
)

# Separators that must not let a term hide inside a snake/kebab/camel label.
_SEPARATORS = re.compile(r"[\s_\-·•.:,;!?/\\'\"()\[\]{}<>|]+")

# Public key/value names that encode a person-level judgment, independently of
# the intent word list (a score field leaks the same invariant).
PROHIBITED_PERSON_SCORE_TERMS: frozenset[str] = frozenset(
    {
        "score",
        "rating",
        "rank",
        "ranking",
        "leaderboard",
        "reliability",
        "trustworthiness",
        "credibility",
        "competence",
        "fitness",
        "affidabilita",
        "attendibilita",
        "credibilita",
        "competenza",
    }
)

PUBLIC_INTENT_PROHIBITED_TERMS: frozenset[str] = (
    _PROHIBITED_BASE | _PROHIBITED_EXTENDED | _PROHIBITED_ITALIAN
)


def normalize_label(value: object) -> str:
    """Casefold/strip accents and invisible format controls before token scan.

    Zero-width and bidi formatting characters must not split a forbidden
    accusation or person-score token. This is only a defensive public-label
    normalization; it neither infers a person's intent nor rewrites evidence.
    """
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch) and unicodedata.category(ch) != "Cf"
    )
    return " ".join(_SEPARATORS.split(text.casefold())).strip()


def _normalized_forms(term: str) -> tuple[str, ...]:
    flat = normalize_label(term)
    compact = flat.replace(" ", "")
    forms = {flat, compact}
    # A camelCase label normalizes with no separator, so also register the
    # un-cased compact form for comparison.
    forms.add(unicodedata.normalize("NFKD", str(term)).casefold())
    return tuple(sorted(forms))


_NORMALIZED_INTENT_FORMS: tuple[str, ...] = tuple(
    sorted(
        {form for term in PUBLIC_INTENT_PROHIBITED_TERMS for form in _normalized_forms(term)}
    )
)

_NORMALIZED_SCORE_FORMS: tuple[str, ...] = tuple(
    sorted(
        {
            form
            for term in PROHIBITED_PERSON_SCORE_TERMS
            for form in _normalized_forms(term)
        }
    )
)


def find_prohibited_intent_term(value: object) -> str | None:
    """Return the offending intent term in ``value``, or ``None``.

    Deterministic: returns the first offending term in sorted order so the same
    input always yields the same diagnostic.
    """
    haystack = normalize_label(value)
    compact = haystack.replace(" ", "")
    for form in _NORMALIZED_INTENT_FORMS:
        if not form:
            continue
        if (form in haystack) or (form in compact and " " not in form):
            return form
    return None


def find_prohibited_person_score_term(value: object) -> str | None:
    """Return the offending person-score term in ``value``, or ``None``."""
    haystack = normalize_label(value)
    compact = haystack.replace(" ", "")
    for form in _NORMALIZED_SCORE_FORMS:
        if not form:
            continue
        if (form in haystack) or (form in compact and " " not in form):
            return form
    return None


def scan_public_label(value: object) -> str | None:
    """Single public-label guard used by every serializer and policy module.

    Returns a machine-readable reason on rejection, ``None`` when clean.
    """
    if find_prohibited_intent_term(value) is not None:
        return "INTENT_LANGUAGE_IN_LABEL"
    if find_prohibited_person_score_term(value) is not None:
        return "PERSON_SCORE_LANGUAGE_IN_LABEL"
    return None


def assert_no_intent_member() -> None:
    """Fail fast if the intent/assessment vocabularies ever acquire a bad member.

    Called at import time and directly by tests. This is the enforcement point
    for E-301-01/E-301-02: it is impossible to add an intent-bearing public
    label without breaking an import.
    """
    for vocabulary_name, vocabulary in (
        ("AssessmentIntent", AssessmentIntent),
        ("VerificationAssessment", VerificationAssessment),
        ("FindingPublicationStatus", FindingPublicationStatus),
    ):
        for member in vocabulary:
            reason = scan_public_label(member.value)
            if reason is not None:
                raise ValueError(
                    f"INTENT_ENCODING_PROHIBITED: {vocabulary_name}.{member.name} "
                    f"fails public-label scan ({reason})"
                )


assert_no_intent_member()


# --------------------------------------------------------------------------
# Intent-language disposition for untrusted text
# --------------------------------------------------------------------------

# Italian negation / distancing markers that, combined with a prohibited term,
# mean the speaker is *denying* rather than *asserting* intent. The disposition
# is still a hold: the product does not adjudicate the denial either.
_DENIAL_MARKERS: frozenset[str] = frozenset(
    {
        "non",
        "no",
        "ne",
        "mai",
        "niente",
        "nulla",
        "not",
        "never",
        "noto",
        "smentisco",
        "smentita",
        "dennego",
        "accusato",
        "accusa",
        "falso",
        "falsa",
        "calunnia",
        "diffamazione",
        "defamation",
        "slander",
        "allege",
        "alleged",
    }
)

_DENIAL_PHRASES: tuple[str, ...] = (
    "accuse him",
    "accused him",
    "accused of",
    "accusa di",
    "accusato di",
    "smentisce",
    "smentita",
    "dennego",
    "diffamazione",
    "defamation",
    "slander",
    "calunnia",
)


@dataclass(frozen=True)
class IntentTextAssessment:
    disposition: IntentTextRisk
    reasons: tuple[str, ...]
    normalized_text: str


def classify_text_intent_risk(text: object) -> IntentTextAssessment:
    """Classify untrusted text for intent language. Never rewrites the text.

    P-301-05: user- or reviewer-supplied intentionality language is treated as
    untrusted text. It is never promoted to a public label; at most it is held
    for a human. This function decides *whether the text may be a public label*,
    which is different from deciding what the text means.
    """
    normalized = normalize_label(text)
    if not normalized:
        return IntentTextAssessment(IntentTextRisk.ALLOWED, (), normalized)

    reasons: list[str] = []
    for form in _NORMALIZED_INTENT_FORMS:
        if form and form in normalized:
            reasons.append(f"intent_term:{form}")

    if not reasons:
        return IntentTextAssessment(IntentTextRisk.ALLOWED, (), normalized)

    # A term inside a denial/distancing construction is a *different* risk: the
    # text reports an accusation rather than making one. It still cannot be a
    # public label, but the disposition is HOLD, not PROHIBITED.
    tokens = set(normalized.split())
    phrase_hit = any(phrase in normalized for phrase in _DENIAL_PHRASES)
    if phrase_hit or (tokens & _DENIAL_MARKERS):
        return IntentTextAssessment(
            IntentTextRisk.HOLD_FOR_REVIEW,
            tuple(sorted(reasons)) + ("reported_accusation",),
            normalized,
        )
    return IntentTextAssessment(
        IntentTextRisk.PROHIBITED_LABEL,
        tuple(sorted(reasons)),
        normalized,
    )


# --------------------------------------------------------------------------
# Relation -> assessment mapping (descriptive context only)
# --------------------------------------------------------------------------

# A relation never *is* an assessment. This table exists to make the null
# result explicit for the two relations the invariant names: contradiction and
# position change.
_RELATION_DESCRIPTIVE_ONLY: frozenset[RelationCandidateType] = frozenset(
    {
        RelationCandidateType.CONTRADICTION_CANDIDATE,
        RelationCandidateType.POSITION_CHANGE_CANDIDATE,
        RelationCandidateType.RELATED_TOPIC,
        RelationCandidateType.SAME_PROPOSITION,
    }
)


def relation_to_assessment(
    relation_type: RelationCandidateType | str,
) -> AssessmentIntent | None:
    """Map a relation type to an assessment intent, or ``None``.

    ``None`` is the correct, invariant-preserving answer for every relation:
    a relation is descriptive context and never carries an intent conclusion.
    The function exists so that a future caller cannot smuggle an assessment in
    by reaching for a relation.
    """
    try:
        RelationCandidateType(str(relation_type))
    except ValueError:
        return None
    return None


def is_descriptive_only_relation(relation_type: RelationCandidateType | str) -> bool:
    """True for relations that carry no assessment of their own."""
    return relation_type in _RELATION_DESCRIPTIVE_ONLY


# --------------------------------------------------------------------------
# Publishability
# --------------------------------------------------------------------------

ASSESSMENT_TO_INTENT: dict[VerificationAssessment, AssessmentIntent] = {
    VerificationAssessment.SUPPORTED: AssessmentIntent.SUPPORTED_BY_EVIDENCE,
    VerificationAssessment.FACTUALLY_FALSE: AssessmentIntent.CONTRADICTED_BY_EVIDENCE,
    VerificationAssessment.OUTDATED_DATA: AssessmentIntent.STALE_AT_STATEMENT_TIME,
    VerificationAssessment.INSUFFICIENT_EVIDENCE: (
        AssessmentIntent.UNRESOLVED_BY_AVAILABLE_EVIDENCE
    ),
    VerificationAssessment.UNRESOLVED: (
        AssessmentIntent.UNRESOLVED_BY_AVAILABLE_EVIDENCE
    ),
}


@dataclass(frozen=True)
class PublishabilityInput:
    """Bounded, already-resolved booleans. No I/O is performed by this module."""

    assessment: VerificationAssessment | str
    has_approved_review_event: bool = False
    verification_rule_version: str | None = None
    statement_cutoff: str | None = None
    approved_evidence_ids: tuple[str, ...] = ()
    approved_observation_ids: tuple[str, ...] = ()
    review_is_stale: bool = False
    uses_future_evidence: bool = False
    evaluates_later_outcome: bool = False
    public_label: str | None = None
    limitations_present: bool = True


@dataclass(frozen=True)
class PublishabilityDecision:
    publishable: bool
    blockers: tuple[PublishabilityBlocker, ...]

    @property
    def reason(self) -> str:
        return self.blockers[0].value if self.blockers else PublishabilityBlocker.OK.value


def assess_publishability(
    inputs: PublishabilityInput,
) -> PublishabilityDecision:
    """Fail-closed conjunction required before a claim-level assessment is public.

    Ordering is fixed so a given input always yields the same first blocker,
    which makes the diagnostic stable for audits and tests.
    """
    blockers: list[PublishabilityBlocker] = []

    try:
        assessment = VerificationAssessment(str(inputs.assessment))
    except ValueError:
        return PublishabilityDecision(False, (PublishabilityBlocker.UNKNOWN_ASSESSMENT,))

    if assessment not in PUBLIC_ASSESSMENTS:
        blockers.append(PublishabilityBlocker.NON_PUBLISHABLE_ASSESSMENT)

    if inputs.public_label is not None and scan_public_label(inputs.public_label):
        blockers.append(PublishabilityBlocker.INTENT_LANGUAGE_IN_LABEL)

    if not inputs.has_approved_review_event:
        blockers.append(PublishabilityBlocker.NO_APPROVED_REVIEW_EVENT)

    if not str(inputs.verification_rule_version or "").strip():
        blockers.append(PublishabilityBlocker.NO_VERIFICATION_RULE_VERSION)

    if not str(inputs.statement_cutoff or "").strip():
        blockers.append(PublishabilityBlocker.NO_STATEMENT_CUTOFF)

    if not inputs.approved_evidence_ids:
        blockers.append(PublishabilityBlocker.NO_APPROVED_EVIDENCE)

    if not inputs.approved_observation_ids:
        blockers.append(PublishabilityBlocker.NO_APPROVED_OBSERVATIONS)

    if inputs.review_is_stale:
        blockers.append(PublishabilityBlocker.STALE_REVIEW)

    # C-301-05 / AC-301.4: future evidence is refused unless the finding
    # explicitly evaluates a later outcome.
    if inputs.uses_future_evidence and not inputs.evaluates_later_outcome:
        blockers.append(PublishabilityBlocker.FUTURE_EVIDENCE_USED)

    if not inputs.limitations_present:
        blockers.append(PublishabilityBlocker.LIMITATIONS_MISSING)

    if blockers:
        return PublishabilityDecision(False, tuple(blockers))
    return PublishabilityDecision(True, (PublishabilityBlocker.OK,))


def is_person_score_free(mapping: dict[str, object]) -> bool:
    """True when no key in ``mapping`` encodes a person-level judgment.

    Applies to a whole mapping, not just its values, so a serializer cannot add
    a ``reliability_score`` key next to a clean assessment.
    """
    for key in mapping:
        if find_prohibited_person_score_term(key) is not None:
            return False
        if find_prohibited_intent_term(key) is not None:
            return False
    return True


__all__ = [
    "ASSESSMENT_TO_INTENT",
    "AssessmentIntent",
    "INTENT_POLICY_VERSION",
    "IntentTextAssessment",
    "IntentTextRisk",
    "NON_PUBLISHABLE_ASSESSMENTS",
    "PINNED_VOCABULARY_VERSIONS",
    "PROHIBITED_PERSON_SCORE_TERMS",
    "PUBLIC_ASSESSMENTS",
    "PUBLIC_INTENT_PROHIBITED_TERMS",
    "PublishabilityBlocker",
    "PublishabilityDecision",
    "PublishabilityInput",
    "assert_no_intent_member",
    "assess_publishability",
    "classify_text_intent_risk",
    "find_prohibited_intent_term",
    "find_prohibited_person_score_term",
    "is_descriptive_only_relation",
    "is_person_score_free",
    "normalize_label",
    "relation_to_assessment",
    "scan_public_label",
]
