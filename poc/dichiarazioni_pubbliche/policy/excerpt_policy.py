"""DP-305 — copyright / transcript-excerpt publication policy.

Machine-checkable half of DP-305. Decides, from bounded inputs, whether a
bounded source excerpt may appear in the public projection, and whether the
proposed excerpt satisfies attribution, provenance, and non-substitution rules.

The fail-closed spine
---------------------
C-305-01 rights unknown means private. ``rights_status`` that is not
    ``CLEARED`` cannot authorize any public excerpt. There is no "fetchable
    therefore allowed" path (E-305-01).
C-305-02 no substitute republication. Excerpts are bounded and non-substitutive;
    a request for a full transcript is rejected by design (E-305-03).
C-305-03 exact provenance. Every excerpt carries source/content/segment,
    timestamp range, transcript variant, and content hash.
C-305-04 no raw-body leakage. The renderer returns attribution + escaped text
    only; no canonical transcript, evidence body, or rights receipt.
C-305-05 fail closed at read time. Expiry and staleness are re-evaluated.
C-305-07 source-safe acquisition. Reachability is not permission.

Numeric bounds
--------------
``MAX_EXCERPT_CHARS`` and ``MAX_EXCERPTS_PER_DOSSIER`` are *policy-profile*
values, not legal conclusions. The ticket explicitly forbids inventing a
universal word/character limit (DP-305 Non-goals, P-305-05). They are therefore
declared here as a **launch-profile placeholder that is NOT approved**: any
excerpt evaluation requires ``EXCERPT_PROFILE_APPROVED`` to be True, which is
an owner/counsel decision (Q-305-01, Q-306-11). With the placeholder in place,
``decide_excerpt`` always returns PROHIBITED, which is the correct fail-closed
default until the profile is approved. Tests cover both the placeholder
behaviour and the fully-approved behaviour with explicit values supplied.

Pure, zero-I/O, deterministic, importable without a database.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from dichiarazioni_pubbliche.policy.intent_policy import scan_public_label

EXCERPT_POLICY_VERSION = "excerpt-rights-v1"

# --- Launch-profile placeholder (NOT an approved limit) --------------------
# Chosen only to keep the arithmetic in this module total and deterministic.
# These numbers are a placeholder and must be replaced by an owner/counsel
# approved profile. See docs/policy/dp-305-excerpt-policy.md.
PLACEHOLDER_MAX_EXCERPT_CHARS = 400
PLACEHOLDER_MAX_EXCERPTS_PER_DOSSIER = 3

# P-305-05 / B-305-01: the excerpt profile is not approved. No public excerpt
# may be produced while this is False.
EXCERPT_PROFILE_APPROVED = False

MAX_EXCERPT_CHARS = PLACEHOLDER_MAX_EXCERPT_CHARS
MAX_EXCERPTS_PER_DOSSIER = PLACEHOLDER_MAX_EXCERPTS_PER_DOSSIER

# A ratio-based cap so a placeholder profile cannot accidentally authorize a
# whole (short) page. The effective cap is the smaller of the two.
MAX_EXCERPT_RATIO = 0.10

# Machine-transcription disclosure: the only method fields allowed publicly.
ALLOWED_PUBLIC_METHOD_FIELDS: frozenset[str] = frozenset(
    {
        "machine_transcribed",
        "transcript_method",
        "transcript_method_version",
        "asr_provider_class",
        "asr_version",
        "manual_correction_applied",
    }
)

# E-305-04: attribution fields that must be present for any public excerpt.
REQUIRED_ATTRIBUTION_FIELDS: frozenset[str] = frozenset(
    {
        "source_url",
        "content_id",
        "segment_id",
        "transcript_variant_id",
        "timestamp_start_seconds",
        "timestamp_end_seconds",
        "source_content_sha256",
        "excerpt_policy_version",
    }
)

_SHA256_LIKE = re.compile(r"^[0-9a-f]{64}$")
_WHITESPACE = re.compile(r"\s+")


class RightsStatus(StrEnum):
    """Mirrors the operational default of UNKNOWN, extended with explicit states."""

    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"
    EXPIRED = "EXPIRED"
    CONFLICTING = "CONFLICTING"
    REVOKED = "REVOKED"
    CLEARED = "CLEARED"


# The only status that can ever authorize a public excerpt (C-305-01).
PUBLICATION_AUTHORIZING_RIGHTS_STATUSES: frozenset[RightsStatus] = frozenset(
    {RightsStatus.CLEARED}
)

# What the cleared rights actually permit. A source can be cleared to *link*
# but not to *quote*. P-305-01.
EXCERPT_PUBLIC_USE_REQUIRED = "QUOTATION_EXCERPT_PUBLIC"


class ExcerptDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    RIGHTS_NOT_CLEARED = "RIGHTS_NOT_CLEARED"
    RIGHTS_EXPIRED = "RIGHTS_EXPIRED"
    RIGHTS_REVOKED = "RIGHTS_REVOKED"
    RIGHTS_CONFLICTING = "RIGHTS_CONFLICTING"
    PUBLIC_USE_NOT_PERMITTED = "PUBLIC_USE_NOT_PERMITTED"
    ATTRIBUTION_INCOMPLETE = "ATTRIBUTION_INCOMPLETE"
    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    INVALID_TIMESTAMP_RANGE = "INVALID_TIMESTAMP_RANGE"
    TIMESTAMP_RANGE_NOT_BOUNDED = "TIMESTAMP_RANGE_NOT_BOUNDED"
    EXCERPT_TOO_LONG = "EXCERPT_TOO_LONG"
    EXCERPT_EMPTY = "EXCERPT_EMPTY"
    SUBSTITUTIVE_REQUEST = "SUBSTITUTIVE_REQUEST"
    FULL_TRANSCRIPT_REQUEST = "FULL_TRANSCRIPT_REQUEST"
    METHOD_FIELD_NOT_ALLOWED = "METHOD_FIELD_NOT_ALLOWED"
    PROFILE_NOT_APPROVED = "PROFILE_NOT_APPROVED"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    SEGMENT_STALE = "SEGMENT_STALE"
    REVIEW_MISSING = "REVIEW_MISSING"
    INTENT_LANGUAGE_IN_EXCERPT = "INTENT_LANGUAGE_IN_EXCERPT"


class ExcerptDisposition(StrEnum):
    ALLOWED = "ALLOWED"
    PROHIBITED = "PROHIBITED"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"


@dataclass(frozen=True)
class ExcerptRequest:
    """Bounded excerpt proposal. Everything is already-resolved; no I/O here."""

    excerpt_text: str
    rights_status: RightsStatus | str
    permitted_public_uses: tuple[str, ...] = ()
    rights_reviewed_on: str | None = None
    rights_expires_on: str | None = None
    today: str = ""  # caller-supplied ISO date; keeps the module clock-free
    # Attribution / provenance (E-305-03)
    source_url: str | None = None
    content_id: str | None = None
    segment_id: str | None = None
    transcript_variant_id: str | None = None
    timestamp_start_seconds: float | None = None
    timestamp_end_seconds: float | None = None
    source_content_sha256: str | None = None
    observed_source_sha256: str | None = None
    # Freshness / review
    segment_is_stale: bool = False
    excerpt_review_approved: bool = False
    # Request shape
    request_kind: str = "EXCERPT"  # "EXCERPT" | "FULL_TRANSCRIPT" | "MEDIA_COPY"
    method_fields: dict[str, object] | None = None
    # Profile
    profile_approved: bool = EXCERPT_PROFILE_APPROVED
    max_excerpt_chars: int = MAX_EXCERPT_CHARS
    total_source_chars: int | None = None


@dataclass(frozen=True)
class ExcerptDecision:
    disposition: ExcerptDisposition
    codes: tuple[ExcerptDecisionCode, ...]
    normalized_excerpt: str = ""
    max_allowed_chars: int = 0

    @property
    def allowed(self) -> bool:
        return self.disposition is ExcerptDisposition.ALLOWED

    @property
    def reason(self) -> str:
        return self.codes[0].value if self.codes else ExcerptDecisionCode.ALLOW.value


def _normalized_text(text: str) -> str:
    """NFKC-normalize and collapse whitespace. Punctuation is preserved so the
    quoted wording is not altered (C-305-03)."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def effective_excerpt_cap(request: ExcerptRequest) -> int:
    """Smaller of the absolute cap and the ratio cap against the source."""
    absolute = max(0, int(request.max_excerpt_chars))
    total = request.total_source_chars
    if isinstance(total, int) and total > 0:
        ratio_cap = int(total * MAX_EXCERPT_RATIO)
        return min(absolute, ratio_cap)
    return absolute


def decide_excerpt(request: ExcerptRequest) -> ExcerptDecision:
    """Fail-closed conjunction for a public excerpt (AC-305.2/305.3/305.4)."""
    codes: list[ExcerptDecisionCode] = []

    # Non-goals first: a full-transcript or substitutive media request is
    # rejected before anything else (E-305-03, AC-305.7).
    kind = str(request.request_kind or "EXCERPT").upper()
    if kind == "FULL_TRANSCRIPT":
        return ExcerptDecision(
            ExcerptDisposition.PROHIBITED,
            (ExcerptDecisionCode.FULL_TRANSCRIPT_REQUEST,),
        )
    if kind in {"MEDIA_COPY", "MEDIA", "AUDIO", "VIDEO", "SOURCE_CAPTURE"}:
        return ExcerptDecision(
            ExcerptDisposition.PROHIBITED,
            (ExcerptDecisionCode.SUBSTITUTIVE_REQUEST,),
        )

    # C-305-01: rights.
    try:
        rights = RightsStatus(str(request.rights_status))
    except ValueError:
        return ExcerptDecision(
            ExcerptDisposition.PROHIBITED, (ExcerptDecisionCode.RIGHTS_NOT_CLEARED,)
        )

    if rights is RightsStatus.REVOKED:
        codes.append(ExcerptDecisionCode.RIGHTS_REVOKED)
    elif rights in {RightsStatus.EXPIRED}:
        codes.append(ExcerptDecisionCode.RIGHTS_EXPIRED)
    elif rights in {RightsStatus.CONFLICTING}:
        codes.append(ExcerptDecisionCode.RIGHTS_CONFLICTING)
    elif rights is not RightsStatus.CLEARED:
        codes.append(ExcerptDecisionCode.RIGHTS_NOT_CLEARED)

    if not codes and EXCERPT_PUBLIC_USE_REQUIRED not in tuple(
        request.permitted_public_uses or ()
    ):
        codes.append(ExcerptDecisionCode.PUBLIC_USE_NOT_PERMITTED)

    # Attribution (E-305-03/04).
    provided = {
        "source_url": request.source_url,
        "content_id": request.content_id,
        "segment_id": request.segment_id,
        "transcript_variant_id": request.transcript_variant_id,
        "timestamp_start_seconds": request.timestamp_start_seconds,
        "timestamp_end_seconds": request.timestamp_end_seconds,
        "source_content_sha256": request.source_content_sha256,
    }
    # excerpt_policy_version is supplied by the renderer, not by the caller.
    attribution_missing = sorted(
        name
        for name in REQUIRED_ATTRIBUTION_FIELDS
        if name != "excerpt_policy_version"
        and not str(provided.get(name) or "").strip()
    )
    if attribution_missing:
        codes.append(ExcerptDecisionCode.ATTRIBUTION_INCOMPLETE)
    elif not _SHA256_LIKE.match(str(provided["source_content_sha256"])):
        codes.append(ExcerptDecisionCode.PROVENANCE_INCOMPLETE)

    # Source-change integrity (E-305-06).
    if (
        isinstance(request.observed_source_sha256, str)
        and isinstance(request.source_content_sha256, str)
        and request.observed_source_sha256
        and request.observed_source_sha256 != request.source_content_sha256
    ):
        codes.append(ExcerptDecisionCode.SOURCE_HASH_MISMATCH)

    # Timestamp bounding.
    start, end = request.timestamp_start_seconds, request.timestamp_end_seconds
    if start is None or end is None:
        codes.append(ExcerptDecisionCode.INVALID_TIMESTAMP_RANGE)
    elif not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        codes.append(ExcerptDecisionCode.INVALID_TIMESTAMP_RANGE)
    elif end <= start or start < 0:
        codes.append(ExcerptDecisionCode.INVALID_TIMESTAMP_RANGE)
    elif end - start > 300:
        # A bounded excerpt window; a longer window is a transcription request.
        codes.append(ExcerptDecisionCode.TIMESTAMP_RANGE_NOT_BOUNDED)

    # Length (AC-305.3) and emptiness.
    excerpt = _normalized_text(str(request.excerpt_text or ""))
    cap = effective_excerpt_cap(request)
    if not excerpt:
        codes.append(ExcerptDecisionCode.EXCERPT_EMPTY)
    elif cap <= 0 or len(excerpt) > cap:
        codes.append(ExcerptDecisionCode.EXCERPT_TOO_LONG)

    # Freshness and review (C-305-05, E-305-05).
    if request.segment_is_stale:
        codes.append(ExcerptDecisionCode.SEGMENT_STALE)
    if not request.excerpt_review_approved:
        codes.append(ExcerptDecisionCode.REVIEW_MISSING)

    # Machine-transcript disclosure allowlist (E-305-08).
    for key in (request.method_fields or {}):
        if key not in ALLOWED_PUBLIC_METHOD_FIELDS:
            codes.append(ExcerptDecisionCode.METHOD_FIELD_NOT_ALLOWED)

    # The DP-301 hard rule: a quoted excerpt is not the place to assert intent.
    if excerpt and scan_public_label(excerpt):
        codes.append(ExcerptDecisionCode.INTENT_LANGUAGE_IN_EXCERPT)

    # B-305-01: nothing is public until the launch profile is approved.
    if not request.profile_approved:
        codes.append(ExcerptDecisionCode.PROFILE_NOT_APPROVED)

    if codes:
        disposition = (
            ExcerptDisposition.HOLD_FOR_REVIEW
            if set(codes) <= {ExcerptDecisionCode.REVIEW_MISSING}
            else ExcerptDisposition.PROHIBITED
        )
        return ExcerptDecision(disposition, tuple(dict.fromkeys(codes)), excerpt, cap)

    return ExcerptDecision(ExcerptDisposition.ALLOWED, (ExcerptDecisionCode.ALLOW,), excerpt, cap)


def render_attributed_excerpt(request: ExcerptRequest, decision: ExcerptDecision) -> dict[str, object]:
    """E-305-04: escaped, attributed, bounded public excerpt.

    Returns only the approved public fields. Refuses to render unless the
    decision is ALLOWED, so a caller cannot bypass the gate by skipping
    ``decide_excerpt``.
    """
    if not decision.allowed:
        raise ValueError("EXCERPT_NOT_ALLOWED: public excerpt rendering refused")

    method_fields = {
        key: value
        for key, value in (request.method_fields or {}).items()
        if key in ALLOWED_PUBLIC_METHOD_FIELDS
    }

    return {
        "text": html.escape(decision.normalized_excerpt, quote=True),
        "source_url": str(request.source_url or ""),
        "content_id": str(request.content_id or ""),
        "segment_id": str(request.segment_id or ""),
        "transcript_variant_id": str(request.transcript_variant_id or ""),
        "timestamp_start_seconds": request.timestamp_start_seconds,
        "timestamp_end_seconds": request.timestamp_end_seconds,
        "excerpt_policy_version": EXCERPT_POLICY_VERSION,
        "excerpt_chars": len(decision.normalized_excerpt),
        **method_fields,
    }


def dossier_excerpt_budget(
    excerpt_lengths: list[int],
    *,
    max_excerpts: int = MAX_EXCERPTS_PER_DOSSIER,
) -> bool:
    """AC-305.3 / C-305-02: a dossier may carry only a bounded number of
    excerpts. Substitutive republication is refused by construction."""
    return len(excerpt_lengths) <= max_excerpts


__all__ = [
    "ALLOWED_PUBLIC_METHOD_FIELDS",
    "ExcerptDecision",
    "ExcerptDecisionCode",
    "ExcerptDisposition",
    "ExcerptRequest",
    "EXCERPT_POLICY_VERSION",
    "EXCERPT_PROFILE_APPROVED",
    "EXCERPT_PUBLIC_USE_REQUIRED",
    "MAX_EXCERPT_CHARS",
    "MAX_EXCERPT_RATIO",
    "MAX_EXCERPTS_PER_DOSSIER",
    "PUBLICATION_AUTHORIZING_RIGHTS_STATUSES",
    "REQUIRED_ATTRIBUTION_FIELDS",
    "RightsStatus",
    "decide_excerpt",
    "dossier_excerpt_budget",
    "effective_excerpt_cap",
    "render_attributed_excerpt",
]
