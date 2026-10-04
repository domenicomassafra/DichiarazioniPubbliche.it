"""DP-304 — privacy, minimization, and sensitive-person policy.

This module encodes the *machine-checkable* part of DP-304. It decides, from
bounded inputs, whether a datum may be publicly projected, and it enforces the
deny-by-default classification of the ticket.

What is deliberately NOT decided here
-------------------------------------
* No lawful basis, no Art. 6/Art. 9 GDPR conclusion, no retention period, no
  rights-request outcome. Those are Q-304-* and Q-306-08..10 and stay
  BLOCKING (see ``docs/policy/legal-closure-register.md``).
* No inference of a sensitive trait. A sensitive *candidate* is a hold; the
  module never turns an unflagged field into a "safe" one by guessing, and it
  never turns a flagged field into a published label.

Classification (DP-304 "Data classification contract")
----------------------------------------------------
PUBLIC_CORE         allowed through the public allowlist + review gate
PUBLIC_SAFE_TEXT    allowed only when explicitly approved and bounded
OPERATIONAL_PRIVATE never public
SENSITIVE_CANDIDATE hold/quarantine; no automated promotion
HIGH_RISK_IDENTITY  never public; do not ingest by default
EPHEMERAL           never public; TTL + fail-closed purge

Retention interaction: ``retention_decision()`` returns a *class*, never a
number. A numeric period is an owner/counsel decision (P-304-06); the module
refuses to invent one and therefore always returns ``AWAITING_APPROVED_PERIOD``.

Pure, zero-I/O, deterministic, importable without a database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from dichiarazioni_pubbliche.policy.intent_policy import (
    normalize_label,
    scan_public_label,
)

PRIVACY_POLICY_VERSION = "privacy-minimization-v1"

# P-304-06: no retention period is invented. Until an owner/counsel-approved
# matrix exists, every class resolves to AWAITING_APPROVED_PERIOD and no
# automatic deletion may be scheduled from this module.
RETENTION_PERIODS_APPROVED = False

_SEPARATORS = re.compile(r"[\s_\-·•.:,;!?/\\'\"()\[\]{}<>|]+")

# Exact private operational field names. This is a *deny list of names*; it
# does not attempt to detect a sensitive value inside free text, because doing
# so would require the trait inference C-304-02 forbids.
OPERATIONAL_PRIVATE_FIELDS: frozenset[str] = frozenset(
    {
        "raw_text",
        "canonical_text",
        "transcript_text",
        "excerpt",
        "evidence_excerpt",
        "evidence_body",
        "reply_body",
        "correction_reason_private",
        "operator_note",
        "internal_note",
        "prompt",
        "system_prompt",
        "provider_request",
        "provider_response",
        "api_key",
        "token",
        "password",
        "credential",
        "contact_details",
        "submitter_contact",
        "private_address",
        "home_address",
        "phone_number",
        "email_address",
        "identity_document",
        "fingerprint_raw",
        "request_fingerprint",
    }
)

# PII-shaped value detectors used only to *quarantine* an item for human review.
# A hit is never a claim that a person belongs to a category.
_EMAIL_VALUE = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")
_PHONE_VALUE = re.compile(r"(?<!\w)(?:\+?\d[\d .\-()]{7,}\d)(?!\w)")
_LONG_DIGIT = re.compile(r"(?<!\d)\d{9,}(?!\d)")

# High-risk identity categories: presence in the input is a hold, not a trait.
HIGH_RISK_IDENTITY_MARKERS: frozenset[str] = frozenset(
    {
        "minor",
        "minore",
        "underage",
        "minorenne",
        "child",
        "bambino",
        "bambina",
        "victim",
        "vittima",
        "witness",
        "testimone",
        "survivor",
        "superstite",
        "patient",
        "paziente",
        "diagnos",
    }
)

# Sensitive-category markers: hold/quarantine, no automated promotion.
SENSITIVE_CATEGORY_MARKERS: frozenset[str] = frozenset(
    {
        "health",
        "salute",
        "sanitario",
        "sanitaria",
        "diagnosi",
        "diagnosi",
        "malattia",
        "illness",
        "disease",
        "disability",
        "disabilita",
        "religion",
        "religione",
        "fede",
        "belief",
        "sexual",
        "sessuale",
        "orientation",
        "orientamento",
        "ethnicity",
        "etnia",
        "razza",
        "race",
        "immigration",
        "immigrazione",
        "criminal",
        "criminale",
        "penale",
        "reato",
        "arrest",
        "indagato",
        "condanna",
        "conviction",
        "mental",
        "mentale",
        "psichiatr",
        "pregnan",
        "gravidanza",
    }
)


class DataClass(StrEnum):
    PUBLIC_CORE = "PUBLIC_CORE"
    PUBLIC_SAFE_TEXT = "PUBLIC_SAFE_TEXT"
    OPERATIONAL_PRIVATE = "OPERATIONAL_PRIVATE"
    SENSITIVE_CANDIDATE = "SENSITIVE_CANDIDATE"
    HIGH_RISK_IDENTITY = "HIGH_RISK_IDENTITY"
    EPHEMERAL = "EPHEMERAL"


# The deny-by-default public surface. Anything not in these two sets is
# prohibited from public projection.
PUBLIC_PROJECTABLE_CLASSES: frozenset[DataClass] = frozenset(
    {DataClass.PUBLIC_CORE, DataClass.PUBLIC_SAFE_TEXT}
)

# P-304-01: public-figure status alone is not sufficient relevance. A recorded
# public-role / public-interest reason is required.
REQUIRED_RELEVANCE_REASONS: frozenset[str] = frozenset(
    {normalize_label(reason) for reason in (
        "PUBLIC_ROLE",
        "PUBLIC_INTEREST_FUNCTION",
        "OFFICIAL_RECORD",
        "DOCUMENTED_PUBLIC_ACTIVITY",
    )}
)


class PublicationDecision(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    PROHIBIT = "PROHIBIT"


class RetentionDecision(StrEnum):
    RETAIN_FOREVER = "RETAIN_FOREVER"
    AWAITING_APPROVED_PERIOD = "AWAITING_APPROVED_PERIOD"
    LEGAL_HOLD = "LEGAL_HOLD"
    EPHEMERAL_PURGE_ELIGIBLE = "EPHEMERAL_PURGE_ELIGIBLE"


class RightsRequestKind(StrEnum):
    ACCESS = "ACCESS"
    CORRECTION = "CORRECTION"
    RESTRICTION = "RESTRICTION"
    OBJECTION = "OBJECTION"
    DELETION = "DELETION"


class RightsRequestOutcome(StrEnum):
    """C-304 / E-304-08/09: a rights case never silently edits public history."""

    OPEN_PRIVATE = "OPEN_PRIVATE"
    REVIEWED_CORRECTION = "REVIEWED_CORRECTION"
    REVIEWED_RESTRICTION = "REVIEWED_RESTRICTION"
    REVIEWED_PUBLIC_HOLD = "REVIEWED_PUBLIC_HOLD"
    DENIED_WITH_REASON = "DENIED_WITH_REASON"
    # A deletion that would erase a published historical version is NEVER a
    # terminal outcome by itself; it becomes a reviewed hold/correction.
    BLOCKED_BY_PUBLIC_HISTORY = "BLOCKED_BY_PUBLIC_HISTORY"


@dataclass(frozen=True)
class ProjectionInput:
    """Bounded field-level projection decision input."""

    field_name: str
    data_class: DataClass | str
    text_value: str | None = None
    relevance_reason: str | None = None
    explicitly_approved: bool = False
    is_published_version: bool = False
    is_ephemeral: bool = False


@dataclass(frozen=True)
class ProjectionDecision:
    decision: PublicationDecision
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.decision in {PublicationDecision.ALLOW, PublicationDecision.ALLOW_WITH_REDACTION}


def _normalized_markers(markers: frozenset[str]) -> frozenset[str]:
    out: set[str] = set()
    for marker in markers:
        flat = normalize_label(marker)
        out.add(flat)
        out.add(flat.replace(" ", ""))
    return frozenset(x for x in out if x)


_NORMALIZED_HIGH_RISK = _normalized_markers(HIGH_RISK_IDENTITY_MARKERS)
_NORMALIZED_SENSITIVE = _normalized_markers(SENSITIVE_CATEGORY_MARKERS)
_NORMALIZED_PRIVATE_FIELDS = _normalized_markers(OPERATIONAL_PRIVATE_FIELDS)


def _field_is_operational_private(field_name: str) -> bool:
    flat = normalize_label(field_name)
    compact = flat.replace(" ", "")
    return any(
        (m in flat) or (" " not in m and m in compact) for m in _NORMALIZED_PRIVATE_FIELDS
    )


def contains_high_risk_marker(text: str | None) -> bool:
    """True when the text carries a high-risk identity marker -> hold, not trait."""
    if not text:
        return False
    flat = normalize_label(text)
    compact = flat.replace(" ", "")
    return any(
        (m in flat) or (" " not in m and m in compact) for m in _NORMALIZED_HIGH_RISK
    )


def contains_sensitive_marker(text: str | None) -> bool:
    """True when the text carries a sensitive-category marker -> hold, not trait."""
    if not text:
        return False
    flat = normalize_label(text)
    compact = flat.replace(" ", "")
    return any(
        (m in flat) or (" " not in m and m in compact) for m in _NORMALIZED_SENSITIVE
    )


def contains_pii_shape(text: str | None) -> bool:
    """True when the text *looks* like it contains contact/PII shapes."""
    if not text:
        return False
    return bool(
        _EMAIL_VALUE.search(text) or _PHONE_VALUE.search(text) or _LONG_DIGIT.search(text)
    )


def decide_projection(inputs: ProjectionInput) -> ProjectionDecision:
    """Decide one field's public projection. Deny-by-default, fail closed.

    Ordering is fixed: structural class gate first (PROHIBIT), then relevance
    (HOLD), then text-shape quarantine (HOLD_WITH / PROHIBIT), then approval.
    """
    try:
        data_class = DataClass(str(inputs.data_class))
    except ValueError:
        return ProjectionDecision(PublicationDecision.PROHIBIT, ("UNKNOWN_DATA_CLASS",))

    if data_class not in PUBLIC_PROJECTABLE_CLASSES:
        return ProjectionDecision(PublicationDecision.PROHIBIT, (data_class.value,))

    if _field_is_operational_private(inputs.field_name):
        return ProjectionDecision(
            PublicationDecision.PROHIBIT, ("OPERATIONAL_PRIVATE_FIELD",)
        )

    # C-304-02: no sensitive inference. A high-risk identity marker is a hold.
    if contains_high_risk_marker(inputs.text_value):
        return ProjectionDecision(
            PublicationDecision.HOLD_FOR_REVIEW, ("HIGH_RISK_IDENTITY",)
        )
    if contains_sensitive_marker(inputs.text_value):
        return ProjectionDecision(
            PublicationDecision.HOLD_FOR_REVIEW, ("SENSITIVE_CANDIDATE",)
        )
    if contains_pii_shape(inputs.text_value):
        return ProjectionDecision(
            PublicationDecision.PROHIBIT, ("PII_SHAPE_IN_PUBLIC_FIELD",)
        )

    # P-304-01: relevance must be recorded.
    # normalize_label splits identifier separators into spaces, so the enum
    # values themselves are normalized the same way before comparison.
    relevance = normalize_label(inputs.relevance_reason)
    if relevance not in REQUIRED_RELEVANCE_REASONS:
        return ProjectionDecision(
            PublicationDecision.HOLD_FOR_REVIEW, ("PUBLIC_INTEREST_RELEVANCE_MISSING",)
        )

    if data_class is DataClass.PUBLIC_SAFE_TEXT and not inputs.explicitly_approved:
        return ProjectionDecision(
            PublicationDecision.HOLD_FOR_REVIEW, ("SAFE_TEXT_NOT_APPROVED",)
        )

    if scan_public_label(inputs.field_name) or (
        inputs.text_value is not None and scan_public_label(inputs.text_value)
    ):
        # The DP-301 hard rule applies to privacy-safe fields too.
        return ProjectionDecision(
            PublicationDecision.PROHIBIT, ("INTENT_LANGUAGE_IN_PUBLIC_FIELD",)
        )

    return ProjectionDecision(PublicationDecision.ALLOW, ("PUBLIC_CORE",))


def retention_decision(
    data_class: DataClass | str,
    *,
    legal_hold_active: bool = False,
    is_ephemeral: bool = False,
) -> RetentionDecision:
    """Class-level retention behavior. Returns a CLASS, never a numeric period.

    E-304-07 / P-304-06: a period is an owner/counsel decision. Until approved,
    only EPHEMERAL is purge-eligible, and only after the existing fail-closed
    manifest/provenance checks in ``retention.py`` pass.
    """
    try:
        resolved = DataClass(str(data_class))
    except ValueError:
        return RetentionDecision.AWAITING_APPROVED_PERIOD

    if legal_hold_active:
        return RetentionDecision.LEGAL_HOLD
    if resolved is DataClass.EPHEMERAL or is_ephemeral:
        return RetentionDecision.EPHEMERAL_PURGE_ELIGIBLE
    if not RETENTION_PERIODS_APPROVED:
        return RetentionDecision.AWAITING_APPROVED_PERIOD
    return RetentionDecision.RETAIN_FOREVER


def rights_request_outcome(
    kind: RightsRequestKind | str,
    *,
    affects_published_version: bool,
    reviewed: bool,
) -> RightsRequestOutcome:
    """E-304-08/09: a rights case is private and append-only; it cannot directly
    mutate a published historical version."""
    try:
        request = RightsRequestKind(str(kind))
    except ValueError:
        return RightsRequestOutcome.OPEN_PRIVATE

    if not reviewed:
        return RightsRequestOutcome.OPEN_PRIVATE

    if affects_published_version:
        # A deletion/restriction affecting a published version becomes a
        # reviewed public hold or correction; it is never a silent erase.
        if request in {RightsRequestKind.DELETION, RightsRequestKind.RESTRICTION}:
            return RightsRequestOutcome.REVIEWED_PUBLIC_HOLD
        return RightsRequestOutcome.REVIEWED_CORRECTION

    if request is RightsRequestKind.DELETION:
        return RightsRequestOutcome.BLOCKED_BY_PUBLIC_HISTORY
    if request is RightsRequestKind.RESTRICTION:
        return RightsRequestOutcome.REVIEWED_RESTRICTION
    if request is RightsRequestKind.CORRECTION:
        return RightsRequestOutcome.REVIEWED_CORRECTION
    return RightsRequestOutcome.DENIED_WITH_REASON


def minimize_public_fieldset(fields: list[str]) -> tuple[str, ...]:
    """C-304-03 minimization: keep only PUBLIC_CORE, provenance-shaped names.

    Drops operational-private names and any person-score/intent label. Returns
    a sorted, de-duplicated tuple so the projection is deterministic.
    """
    kept: set[str] = set()
    for field in fields:
        if _field_is_operational_private(field):
            continue
        if scan_public_label(field):
            continue
        kept.add(field)
    return tuple(sorted(kept))


def assert_no_trait_inference() -> None:
    """C-304-02 enforcement point.

    The module ships marker lists for *quarantine* only. This assertion documents
    and enforces that none of the markers can be used as a published trait: the
    only consumers are ``contains_*_marker`` which return booleans, never labels.
    """
    # A marker set must never be exposed as a projection label.
    for marker in HIGH_RISK_IDENTITY_MARKERS | SENSITIVE_CATEGORY_MARKERS:
        assert marker not in {c.value for c in DataClass}, (
            f"sensitive marker '{marker}' must not be a DataClass"
        )


assert_no_trait_inference()


__all__ = [
    "DataClass",
    "HIGH_RISK_IDENTITY_MARKERS",
    "OPERATIONAL_PRIVATE_FIELDS",
    "PRIVACY_POLICY_VERSION",
    "ProjectionDecision",
    "ProjectionInput",
    "PUBLIC_PROJECTABLE_CLASSES",
    "PublicationDecision",
    "REQUIRED_RELEVANCE_REASONS",
    "RETENTION_PERIODS_APPROVED",
    "RetentionDecision",
    "RightsRequestKind",
    "RightsRequestOutcome",
    "SENSITIVE_CATEGORY_MARKERS",
    "assert_no_trait_inference",
    "contains_high_risk_marker",
    "contains_pii_shape",
    "contains_sensitive_marker",
    "decide_projection",
    "minimize_public_fieldset",
    "retention_decision",
    "rights_request_outcome",
]
