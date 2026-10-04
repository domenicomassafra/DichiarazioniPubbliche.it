"""DP-302 — right-of-reply public intake: machine-checkable validation policy.

This module is the *edge* half of the DP-302 threat model. It answers one
question deterministically: given an untrusted intake submission, is it a
well-formed candidate for the private review queue, and if not, which bounded
rejection reason applies?

What this module deliberately does NOT do
-----------------------------------------
* It performs no network, DNS, HTTP, redirect, or render operation. A submitted
  URL is a *candidate reference* only (C-302-04, P-302-04).
* It does not accept, score, moderate, or publish anything. Acceptance here means
  "well-formed enough to enter the private queue", never "public" (C-302-01).
* It does not implement a rate limiter. A token bucket is stateful; this module
  is pure. The rate/quota decision is a separate, stateful adapter that calls
  ``rate_limit_decision()`` with a caller-supplied current count. The launch
  profile values themselves are an owner/security decision (P-302-07) and stay
  unset, which is why ``LAUNCH_PROFILE_CONFIGURED`` is False below.

Threat -> control mapping is in ``docs/policy/dp-302-intake-threat-model.md``;
every control here is traceable to a row there.

Pure, zero-I/O, deterministic. No database import.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.policy.intent_policy import (
    IntentTextRisk,
    classify_text_intent_risk,
)

INTAKE_POLICY_VERSION = "reply-intake-policy-v1"

# Reused verbatim from the existing private runtime so the public edge and the
# private path cannot disagree about what a valid body/identity/URL is.
MAX_REPLY_BODY_CHARS = 20_000
MAX_REPLY_IDENTITY_CHARS = 300
MAX_EVIDENCE_URLS = 32
MAX_EVIDENCE_URL_CHARS = 2_048

# Edge-specific bounds. These are *request-shape* limits, not policy positions
# on quotation, fairness, or data retention; those remain qualified questions.
MAX_FINDING_ID_CHARS = 200
MAX_REQUEST_FIELDS = 8

# P-302-07: the launch profile (rate/quota/retention values, owner, review date)
# has not been accepted. Until it is, the public intake stays disabled.
LAUNCH_PROFILE_CONFIGURED = False
INTAKE_ENABLED = False

# Bounded anti-abuse request shape. A submission larger than this is a resource
# exhaustion attempt regardless of content.
MAX_SUBMISSION_CHARS = (
    MAX_REPLY_BODY_CHARS
    + (2 * MAX_REPLY_IDENTITY_CHARS)
    + (MAX_EVIDENCE_URLS * MAX_EVIDENCE_URL_CHARS)
)

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class IntakeRejectionReason(StrEnum):
    """Bounded, non-reflective rejection reasons.

    The value is what a caller may log or return. It never contains the
    offending input (C-302-02: reject without echoing).
    """

    OK = "OK"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    WRONG_FIELD_NAME_TYPE = "WRONG_FIELD_NAME_TYPE"
    MISSING_FIELD = "MISSING_FIELD"
    WRONG_TYPE = "WRONG_TYPE"
    BODY_EMPTY = "BODY_EMPTY"
    BODY_TOO_LONG = "BODY_TOO_LONG"
    BODY_CONTROL_CHARACTERS = "BODY_CONTROL_CHARACTERS"
    FINDING_ID_EMPTY = "FINDING_ID_EMPTY"
    FINDING_ID_TOO_LONG = "FINDING_ID_TOO_LONG"
    IDENTITY_TOO_LONG = "IDENTITY_TOO_LONG"
    TOO_MANY_EVIDENCE_URLS = "TOO_MANY_EVIDENCE_URLS"
    UNSAFE_EVIDENCE_URL = "UNSAFE_EVIDENCE_URL"
    DUPLICATE_EVIDENCE_URL = "DUPLICATE_EVIDENCE_URL"
    INTENT_LANGUAGE_IN_BODY = "INTENT_LANGUAGE_IN_BODY"
    DISCLOSED_PRIVATE_CONTACT = "DISCLOSED_PRIVATE_CONTACT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    FINGERPRINT_MISSING = "FINGERPRINT_MISSING"
    INTAKE_DISABLED = "INTAKE_DISABLED"
    LAUNCH_PROFILE_MISSING = "LAUNCH_PROFILE_MISSING"


class IntakeDisposition(StrEnum):
    """Outcome of edge validation. Only ACCEPTED_PRIVATE reaches the queue."""

    ACCEPTED_PRIVATE = "ACCEPTED_PRIVATE"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    DEFERRED_RATE_LIMITED = "DEFERRED_RATE_LIMITED"


class RateScope(StrEnum):
    GLOBAL = "GLOBAL"
    PER_FINDING = "PER_FINDING"
    PER_NETWORK = "PER_NETWORK"


# Exactly the fields in E-302-01. Anything else is UNKNOWN_FIELD: an intake
# request can never smuggle a policy override or a status column.
ALLOWED_INTAKE_FIELDS: frozenset[str] = frozenset(
    {
        "finding_id",
        "body",
        "submitter_name",
        "submitter_role",
        "evidence_urls",
        "policy_version",
        "request_fingerprint",
    }
)

REQUIRED_INTAKE_FIELDS: frozenset[str] = frozenset(
    {"finding_id", "body", "evidence_urls", "request_fingerprint"}
)

# Fields that must never be settable from the public edge, even if a caller
# passes them. Defense in depth behind ALLOWED_INTAKE_FIELDS.
RESERVED_OPERATOR_FIELDS: frozenset[str] = frozenset(
    {
        "status",
        "publication_status",
        "public_visibility",
        "review_event",
        "review_actor",
        "assessment",
        "verification_result",
        "evidence_approved",
        "approved_by",
        "moderation_decision",
        "operator_note",
        "rights_status",
        "policy_override",
    }
)

# Heuristic detectors for the personal-data-flooding and abuse rows of the
# threat model. These are *quarantine* signals, never accusations, and they
# never become a person score (P-302-06).
_EMAIL_LIKE = re.compile(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", re.IGNORECASE)
_PHONE_LIKE = re.compile(r"(?<!\w)(?:\+?\d[\d .\-()]{7,}\d)(?!\w)")
_LONG_DIGIT_RUN = re.compile(r"(?<!\d)\d{9,}(?!\d)")


@dataclass(frozen=True)
class IntakeRequest:
    """Untrusted intake submission. ``evidence_urls`` is never fetched."""

    finding_id: object = None
    body: object = None
    submitter_name: object = None
    submitter_role: object = None
    evidence_urls: object = None
    policy_version: object = None
    request_fingerprint: object = None

    def as_mapping(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "body": self.body,
            "submitter_name": self.submitter_name,
            "submitter_role": self.submitter_role,
            "evidence_urls": self.evidence_urls,
            "policy_version": self.policy_version,
            "request_fingerprint": self.request_fingerprint,
        }


@dataclass(frozen=True)
class IntakeValidationResult:
    disposition: IntakeDisposition
    reason: IntakeRejectionReason
    reasons: tuple[IntakeRejectionReason, ...] = ()
    reply_id: str | None = None
    source_hash: str | None = None
    normalized_evidence_urls: tuple[str, ...] = field(default=())
    quarantine_signals: tuple[str, ...] = field(default=())

    @property
    def accepted(self) -> bool:
        return self.disposition is IntakeDisposition.ACCEPTED_PRIVATE

    @property
    def public_ack(self) -> dict[str, str]:
        """P-302-05: bounded receipt only. No body echo, no acceptance claim."""
        if not self.accepted or self.reply_id is None:
            return {"state": self.disposition.value}
        return {
            "receipt_id": self.reply_id,
            "policy_version": INTAKE_POLICY_VERSION,
            "state": "RECEIVED_PRIVATE",
        }


@dataclass(frozen=True)
class RateLimitProfile:
    """Launch-profile shape. Values are owner/security decisions (P-302-07)."""

    scope: RateScope
    limit: int
    window_seconds: int
    cooldown_seconds: int = 0
    configured: bool = False


@dataclass(frozen=True)
class RateLimitState:
    """Caller-supplied, pre-existing counters. This module never mutates them."""

    submissions_in_window: int = 0
    cooldown_remaining_seconds: int = 0


# --------------------------------------------------------------------------
# URL safety: validation only, never retrieval
# --------------------------------------------------------------------------


def validate_evidence_url(value: object) -> str:
    """Validate and normalize one candidate URL. Performs NO resolution/fetch.

    C-302-04 / P-302-04: this function must stay pure and offline. It is
    intentionally not allowed to call socket, requests, or urllib.request.
    """
    if not isinstance(value, str):
        raise ValueError(f"UNSAFE_EVIDENCE_URL:{IntakeRejectionReason.WRONG_TYPE.value}")
    raw = value.strip()
    if not raw or len(raw) > MAX_EVIDENCE_URL_CHARS:
        raise ValueError(f"UNSAFE_EVIDENCE_URL:{IntakeRejectionReason.BODY_TOO_LONG.value}")
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            f"UNSAFE_EVIDENCE_URL:{IntakeRejectionReason.UNSAFE_EVIDENCE_URL.value}"
        )
    return parsed.geturl()


def normalize_evidence_urls(values: object) -> tuple[str, ...]:
    """Bound, validate, and de-duplicate candidate references, order-preserving."""
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ValueError(f"WRONG_TYPE:{IntakeRejectionReason.WRONG_TYPE.value}")
    if len(values) > MAX_EVIDENCE_URLS:
        raise ValueError(
            f"TOO_MANY_EVIDENCE_URLS:{IntakeRejectionReason.TOO_MANY_EVIDENCE_URLS.value}"
        )
    normalized = [validate_evidence_url(value) for value in values]
    if len(set(normalized)) != len(normalized):
        raise ValueError(
            f"DUPLICATE_EVIDENCE_URL:{IntakeRejectionReason.DUPLICATE_EVIDENCE_URL.value}"
        )
    return tuple(normalized)


# --------------------------------------------------------------------------
# Quarantine signals (advisory, bounded, non-accusatory)
# --------------------------------------------------------------------------


def _quarantine_signals(body: str, submitter_name: str | None) -> tuple[str, ...]:
    signals: list[str] = []
    if _EMAIL_LIKE.search(body) or (submitter_name and _EMAIL_LIKE.search(submitter_name)):
        signals.append("contact_disclosure_candidate")
    if _PHONE_LIKE.search(body) or _LONG_DIGIT_RUN.search(body):
        signals.append("numeric_identifier_candidate")
    if re.search(r"[\w.+-]+@[\w.-]+\.\w+", str(submitter_name or "")):
        signals.append("submitter_contact_candidate")
    return tuple(sorted(set(signals)))


# --------------------------------------------------------------------------
# Deterministic identity / idempotency
# --------------------------------------------------------------------------


def compute_request_fingerprint(
    *,
    finding_id: str,
    body: str,
    submitter_name: str | None,
    submitter_role: str | None,
    evidence_urls: tuple[str, ...],
) -> str:
    """Stable fingerprint over normalized content only.

    Deliberately excludes network identifiers. Collecting an IP/device
    fingerprint is a qualified privacy question (Q-302-04, Q-306-05) and is
    BLOCKED; the launch profile must decide it explicitly, not by default here.
    """
    material = {
        "finding_id": finding_id,
        "body": body.strip(),
        "submitter_name": (submitter_name or "").strip(),
        "submitter_role": (submitter_role or "").strip(),
        "evidence_urls": list(evidence_urls),
        "policy_version": INTAKE_POLICY_VERSION,
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def deterministic_reply_id(fingerprint: str) -> str:
    """E-302-03: same normalized content always yields the same reply ID."""
    return "reply:" + hashlib.sha256(fingerprint.encode()).hexdigest()


# --------------------------------------------------------------------------
# Edge validation
# --------------------------------------------------------------------------


def _reject(
    reason: IntakeRejectionReason,
    *,
    disposition: IntakeDisposition = IntakeDisposition.REJECTED,
    reasons: tuple[IntakeRejectionReason, ...] = (),
    signals: tuple[str, ...] = (),
) -> IntakeValidationResult:
    return IntakeValidationResult(
        disposition=disposition,
        reason=reason,
        reasons=reasons or (reason,),
        quarantine_signals=signals,
    )


def validate_intake_request(
    request: IntakeRequest,
    *,
    intake_enabled: bool = INTAKE_ENABLED,
    launch_profile_configured: bool = LAUNCH_PROFILE_CONFIGURED,
) -> IntakeValidationResult:
    """Validate one untrusted intake submission at the public edge.

    Fails closed. Order of checks is fixed so the returned primary reason is
    deterministic for a given input.
    """
    # B-302-01: without a configured launch profile the public edge stays off.
    if not launch_profile_configured:
        return _reject(IntakeRejectionReason.LAUNCH_PROFILE_MISSING)
    if not intake_enabled:
        return _reject(IntakeRejectionReason.INTAKE_DISABLED)

    mapping = request.as_mapping()
    if len(mapping) > MAX_REQUEST_FIELDS:
        return _reject(IntakeRejectionReason.REQUEST_TOO_LARGE)

    for supplied, value in mapping.items():
        if value is None:
            continue
        lowered = supplied.casefold()
        if lowered in RESERVED_OPERATOR_FIELDS:
            return _reject(IntakeRejectionReason.UNKNOWN_FIELD)
        if supplied not in ALLOWED_INTAKE_FIELDS:
            return _reject(IntakeRejectionReason.UNKNOWN_FIELD)

    missing = [
        field_name
        for field_name in sorted(REQUIRED_INTAKE_FIELDS)
        if mapping.get(field_name) is None
    ]
    if missing:
        return _reject(IntakeRejectionReason.MISSING_FIELD)

    if not str(request.request_fingerprint or "").strip():
        return _reject(IntakeRejectionReason.FINGERPRINT_MISSING)

    finding_id = request.finding_id
    if not isinstance(finding_id, str):
        return _reject(IntakeRejectionReason.WRONG_TYPE)
    finding = finding_id.strip()
    if not finding:
        return _reject(IntakeRejectionReason.FINDING_ID_EMPTY)
    if len(finding) > MAX_FINDING_ID_CHARS:
        return _reject(IntakeRejectionReason.FINDING_ID_TOO_LONG)

    body = request.body
    if not isinstance(body, str):
        return _reject(IntakeRejectionReason.WRONG_TYPE)
    text = body.strip()
    if not text:
        return _reject(IntakeRejectionReason.BODY_EMPTY)
    if len(text) > MAX_REPLY_BODY_CHARS:
        return _reject(IntakeRejectionReason.BODY_TOO_LONG)
    if _CONTROL_CHARACTERS.search(text):
        return _reject(IntakeRejectionReason.BODY_CONTROL_CHARACTERS)

    submitter_name: str | None = None
    submitter_role: str | None = None
    for field_name in ("submitter_name", "submitter_role"):
        value = mapping[field_name]
        if value is None:
            continue
        if not isinstance(value, str):
            return _reject(IntakeRejectionReason.WRONG_TYPE)
        if len(value.strip()) > MAX_REPLY_IDENTITY_CHARS:
            return _reject(IntakeRejectionReason.IDENTITY_TOO_LONG)
        stripped = value.strip()
        if field_name == "submitter_name":
            submitter_name = stripped or None
        else:
            submitter_role = stripped or None

    try:
        evidence_urls = normalize_evidence_urls(request.evidence_urls)
    except ValueError as exc:
        code = str(exc).split(":", 1)[-1]
        try:
            reason = IntakeRejectionReason(code)
        except ValueError:
            reason = IntakeRejectionReason.UNSAFE_EVIDENCE_URL
        return _reject(reason)

    # Personal-data flooding / doxxing: quarantine, never auto-publish, never
    # an accusation (threat row "Impersonation or doxxing").
    signals = _quarantine_signals(text, submitter_name)

    # A submitter cannot assert intent in a public surface (DP-301 hard rule).
    # Body text stays private, so an intent-bearing body is a *hold* for a human
    # reviewer, not a published accusation and not a rejection of the fact.
    text_risk = classify_text_intent_risk(text)

    fingerprint = compute_request_fingerprint(
        finding_id=finding,
        body=text,
        submitter_name=submitter_name,
        submitter_role=submitter_role,
        evidence_urls=evidence_urls,
    )
    reply_id = deterministic_reply_id(fingerprint)

    if text_risk.disposition is IntentTextRisk.PROHIBITED_LABEL:
        return _reject(
            IntakeRejectionReason.INTENT_LANGUAGE_IN_BODY,
            disposition=IntakeDisposition.QUARANTINED,
            reasons=tuple(IntakeRejectionReason.INTENT_LANGUAGE_IN_BODY for _ in text_risk.reasons),
            signals=signals,
        )

    disposition = IntakeDisposition.QUARANTINED if signals else IntakeDisposition.ACCEPTED_PRIVATE
    reason = (
        IntakeRejectionReason.DISCLOSED_PRIVATE_CONTACT
        if signals
        else IntakeRejectionReason.OK
    )
    return IntakeValidationResult(
        disposition=disposition,
        reason=reason,
        reasons=(reason,),
        reply_id=reply_id,
        source_hash=fingerprint,
        normalized_evidence_urls=evidence_urls,
        quarantine_signals=signals,
    )


def validate_intake_payload(
    payload: object,
    *,
    intake_enabled: bool = INTAKE_ENABLED,
    launch_profile_configured: bool = LAUNCH_PROFILE_CONFIGURED,
) -> IntakeValidationResult:
    """Validate a RAW untrusted mapping, the way an HTTP body arrives.

    ``validate_intake_request`` takes a typed request, which has already
    discarded unknown keys. A public endpoint does not get that luxury: the
    submitter controls the field names. This entry point inspects the key set
    first, so an injected ``status`` or ``policy_override`` field is refused
    before any value is read. It never echoes the payload.
    """
    if not isinstance(payload, dict):
        return _reject(IntakeRejectionReason.WRONG_TYPE)
    if len(payload) > MAX_REQUEST_FIELDS:
        return _reject(IntakeRejectionReason.REQUEST_TOO_LARGE)
    for key in payload:
        if not isinstance(key, str):
            return _reject(IntakeRejectionReason.WRONG_FIELD_NAME_TYPE)
        if key not in ALLOWED_INTAKE_FIELDS:
            return _reject(IntakeRejectionReason.UNKNOWN_FIELD)
    return validate_intake_request(
        IntakeRequest(**payload),
        intake_enabled=intake_enabled,
        launch_profile_configured=launch_profile_configured,
    )


# --------------------------------------------------------------------------
# Abuse controls: rate / quota / cooldown (pure decision over caller state)
# --------------------------------------------------------------------------


def rate_limit_decision(
    profile: RateLimitProfile,
    state: RateLimitState,
) -> tuple[IntakeDisposition, IntakeRejectionReason]:
    """Decide rate/quota/cooldown from caller-supplied counters. No mutation.

    An unconfigured profile fails closed (P-302-07): the request is deferred,
    not admitted.
    """
    if not profile.configured or profile.limit <= 0 or profile.window_seconds <= 0:
        return IntakeDisposition.REJECTED, IntakeRejectionReason.LAUNCH_PROFILE_MISSING
    if state.cooldown_remaining_seconds > 0:
        return IntakeDisposition.DEFERRED_RATE_LIMITED, IntakeRejectionReason.COOLDOWN_ACTIVE
    if state.submissions_in_window >= profile.limit:
        if profile.scope is RateScope.GLOBAL:
            return IntakeDisposition.REJECTED, IntakeRejectionReason.QUOTA_EXCEEDED
        return IntakeDisposition.DEFERRED_RATE_LIMITED, IntakeRejectionReason.RATE_LIMIT_EXCEEDED
    return IntakeDisposition.ACCEPTED_PRIVATE, IntakeRejectionReason.OK


def acknowledgement_is_bounded(result: IntakeValidationResult) -> bool:
    """P-302-05 assertion used by tests and by any future HTTP adapter.

    An acknowledgement must contain only bounded receipt metadata, and must
    never claim acceptance of the *content*.
    """
    ack = result.public_ack
    if set(ack) - {"receipt_id", "policy_version", "state"}:
        return False
    if ack.get("state") not in {"RECEIVED_PRIVATE", IntakeDisposition.REJECTED.value,
                               IntakeDisposition.QUARANTINED.value,
                               IntakeDisposition.DEFERRED_RATE_LIMITED.value}:
        return False
    return not any(
        marker in " ".join(ack.values()).casefold()
        for marker in ("accepted", "verified", "approved", "published", "true")
    )


__all__ = [
    "ALLOWED_INTAKE_FIELDS",
    "INTAKE_ENABLED",
    "INTAKE_POLICY_VERSION",
    "IntakeDisposition",
    "IntakeRejectionReason",
    "IntakeRequest",
    "IntakeValidationResult",
    "LAUNCH_PROFILE_CONFIGURED",
    "MAX_EVIDENCE_URLS",
    "MAX_EVIDENCE_URL_CHARS",
    "MAX_FINDING_ID_CHARS",
    "MAX_REPLY_BODY_CHARS",
    "MAX_REPLY_IDENTITY_CHARS",
    "MAX_REQUEST_FIELDS",
    "REQUIRED_INTAKE_FIELDS",
    "RESERVED_OPERATOR_FIELDS",
    "RateLimitProfile",
    "RateLimitState",
    "RateScope",
    "acknowledgement_is_bounded",
    "compute_request_fingerprint",
    "deterministic_reply_id",
    "normalize_evidence_urls",
    "rate_limit_decision",
    "validate_evidence_url",
    "validate_intake_request",
]
