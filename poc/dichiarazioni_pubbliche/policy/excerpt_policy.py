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
import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from urllib.parse import urlsplit

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
    BLOCKED = "BLOCKED"
    FORBIDDEN = "FORBIDDEN"
    LEGAL_HOLD = "LEGAL_HOLD"
    RIGHTS_HOLD = "RIGHTS_HOLD"
    TAKEDOWN_HOLD = "TAKEDOWN_HOLD"
    REMOVED = "REMOVED"
    CLEARED = "CLEARED"


# The only status that can ever authorize a public excerpt (C-305-01).
PUBLICATION_AUTHORIZING_RIGHTS_STATUSES: frozenset[RightsStatus] = frozenset(
    {RightsStatus.CLEARED}
)

# What the cleared rights actually permit. A source can be cleared to *link*
# but not to *quote*. P-305-01.
EXCERPT_PUBLIC_USE_REQUIRED = "QUOTATION_EXCERPT_PUBLIC"
MEDIA_EMBED_PUBLIC_USE_REQUIRED = "MEDIA_EMBED_PUBLIC"


class ExcerptDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    RIGHTS_NOT_CLEARED = "RIGHTS_NOT_CLEARED"
    RIGHTS_EXPIRED = "RIGHTS_EXPIRED"
    RIGHTS_REVOKED = "RIGHTS_REVOKED"
    RIGHTS_CONFLICTING = "RIGHTS_CONFLICTING"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"
    RIGHTS_DATE_INVALID = "RIGHTS_DATE_INVALID"
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


class ExcerptBudgetCode(StrEnum):
    ALLOW = "ALLOW"
    PROFILE_NOT_APPROVED = "PROFILE_NOT_APPROVED"
    INVALID_LENGTH = "INVALID_LENGTH"
    EXCERPT_ITEM_TOO_LONG = "EXCERPT_ITEM_TOO_LONG"
    EXCERPT_COUNT_EXCEEDED = "EXCERPT_COUNT_EXCEEDED"
    TOTAL_CHAR_BUDGET_EXCEEDED = "TOTAL_CHAR_BUDGET_EXCEEDED"


class MediaUseKind(StrEnum):
    EMBED = "EMBED"
    MEDIA_COPY = "MEDIA_COPY"
    AUDIO_COPY = "AUDIO_COPY"
    VIDEO_COPY = "VIDEO_COPY"
    SOURCE_CAPTURE = "SOURCE_CAPTURE"


class MediaDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    RIGHTS_NOT_CLEARED = "RIGHTS_NOT_CLEARED"
    RIGHTS_EXPIRED = "RIGHTS_EXPIRED"
    RIGHTS_REVOKED = "RIGHTS_REVOKED"
    RIGHTS_CONFLICTING = "RIGHTS_CONFLICTING"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"
    PUBLIC_USE_NOT_PERMITTED = "PUBLIC_USE_NOT_PERMITTED"
    PROFILE_NOT_APPROVED = "PROFILE_NOT_APPROVED"
    SUBSTITUTIVE_MEDIA_COPY = "SUBSTITUTIVE_MEDIA_COPY"
    MEDIA_URL_INVALID = "MEDIA_URL_INVALID"
    MEDIA_POLICY_VERSION_MISSING = "MEDIA_POLICY_VERSION_MISSING"
    CONTENT_KIND_NOT_MEDIA = "CONTENT_KIND_NOT_MEDIA"
    MEDIA_USE_KIND_INVALID = "MEDIA_USE_KIND_INVALID"


class RightsPolicyDisposition(StrEnum):
    ALLOWED = "ALLOWED"
    PROHIBITED = "PROHIBITED"


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


@dataclass(frozen=True)
class ExcerptBudgetDecision:
    disposition: RightsPolicyDisposition
    codes: tuple[ExcerptBudgetCode, ...]
    excerpt_count: int
    total_excerpt_chars: int
    max_excerpts: int
    max_total_chars: int

    @property
    def allowed(self) -> bool:
        return self.disposition is RightsPolicyDisposition.ALLOWED


@dataclass(frozen=True)
class MediaUseRequest:
    """Resolved source-rights input for public media/embed authorization.

    A caller must supply an already-reviewed rights status and explicit permitted
    public uses.  This seam grants no rights and performs no network lookup.
    """

    kind: MediaUseKind | str
    rights_status: RightsStatus | str
    permitted_public_uses: tuple[str, ...] = ()
    media_url: str | None = None
    media_policy_version: str | None = None
    content_kind: str | None = None
    profile_approved: bool = False


@dataclass(frozen=True)
class MediaUseDecision:
    disposition: RightsPolicyDisposition
    codes: tuple[MediaDecisionCode, ...]

    @property
    def allowed(self) -> bool:
        return self.disposition is RightsPolicyDisposition.ALLOWED


@dataclass(frozen=True)
class RightsPolicyAuditReceipt:
    """Content-free audit receipt with bounded machine reason codes only."""

    policy_version: str
    subject_ref: str
    disposition: str
    reason_codes: tuple[str, ...]
    reason_count: int
    reasons_truncated: bool


def _normalized_text(text: str) -> str:
    """NFKC-normalize and collapse whitespace. Punctuation is preserved so the
    quoted wording is not altered (C-305-03)."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


_BLOCKED_RIGHTS_STATUSES = frozenset(
    {
        RightsStatus.BLOCKED,
        RightsStatus.FORBIDDEN,
        RightsStatus.LEGAL_HOLD,
        RightsStatus.RIGHTS_HOLD,
        RightsStatus.TAKEDOWN_HOLD,
        RightsStatus.REMOVED,
    }
)


def _rights_block_code(rights: RightsStatus) -> ExcerptDecisionCode | None:
    if rights is RightsStatus.REVOKED:
        return ExcerptDecisionCode.RIGHTS_REVOKED
    if rights is RightsStatus.EXPIRED:
        return ExcerptDecisionCode.RIGHTS_EXPIRED
    if rights is RightsStatus.CONFLICTING:
        return ExcerptDecisionCode.RIGHTS_CONFLICTING
    if rights in _BLOCKED_RIGHTS_STATUSES:
        return ExcerptDecisionCode.RIGHTS_BLOCKED
    if rights is not RightsStatus.CLEARED:
        return ExcerptDecisionCode.RIGHTS_NOT_CLEARED
    return None


def _media_rights_block_code(rights: RightsStatus) -> MediaDecisionCode | None:
    if rights is RightsStatus.REVOKED:
        return MediaDecisionCode.RIGHTS_REVOKED
    if rights is RightsStatus.EXPIRED:
        return MediaDecisionCode.RIGHTS_EXPIRED
    if rights is RightsStatus.CONFLICTING:
        return MediaDecisionCode.RIGHTS_CONFLICTING
    if rights in _BLOCKED_RIGHTS_STATUSES:
        return MediaDecisionCode.RIGHTS_BLOCKED
    if rights is not RightsStatus.CLEARED:
        return MediaDecisionCode.RIGHTS_NOT_CLEARED
    return None


def _safe_public_https_url(value: str | None) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return True
    return bool(addr.is_global)


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

    rights_code = _rights_block_code(rights)
    if rights_code is not None:
        codes.append(rights_code)

    if not codes and EXCERPT_PUBLIC_USE_REQUIRED not in tuple(
        request.permitted_public_uses or ()
    ):
        codes.append(ExcerptDecisionCode.PUBLIC_USE_NOT_PERMITTED)

    # Read-time expiry/review-date validation. This consumes caller-supplied ISO
    # dates; it invents neither a duration nor a source-specific legal rule.
    reviewed_on: date | None = None
    expires_on: date | None = None
    today: date | None = None
    try:
        if request.rights_reviewed_on:
            reviewed_on = date.fromisoformat(request.rights_reviewed_on)
        if request.rights_expires_on:
            expires_on = date.fromisoformat(request.rights_expires_on)
        if request.today:
            today = date.fromisoformat(request.today)
    except (TypeError, ValueError):
        codes.append(ExcerptDecisionCode.RIGHTS_DATE_INVALID)
    if expires_on is not None:
        if today is None:
            codes.append(ExcerptDecisionCode.RIGHTS_DATE_INVALID)
        elif today > expires_on:
            codes.append(ExcerptDecisionCode.RIGHTS_EXPIRED)
    if reviewed_on is not None and today is not None and reviewed_on > today:
        codes.append(ExcerptDecisionCode.RIGHTS_DATE_INVALID)

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


def decide_excerpt_budget(
    excerpt_lengths: list[int],
    *,
    profile_approved: bool = EXCERPT_PROFILE_APPROVED,
    max_excerpts: int = MAX_EXCERPTS_PER_DOSSIER,
    max_excerpt_chars: int = MAX_EXCERPT_CHARS,
) -> ExcerptBudgetDecision:
    """Structured excerpt-budget decision without inventing a legal limit.

    The caller-supplied/profile values are treated only as an already-approved
    technical profile.  The repository default remains unapproved and therefore
    prohibits publication.  The total budget is derived from those supplied values
    (count × per-excerpt cap), not from a new independent legal assumption.
    """

    if (
        not isinstance(max_excerpts, int)
        or isinstance(max_excerpts, bool)
        or max_excerpts < 0
        or not isinstance(max_excerpt_chars, int)
        or isinstance(max_excerpt_chars, bool)
        or max_excerpt_chars < 0
        or any(
            not isinstance(length, int) or isinstance(length, bool) or length < 0
            for length in excerpt_lengths
        )
    ):
        return ExcerptBudgetDecision(
            RightsPolicyDisposition.PROHIBITED,
            (ExcerptBudgetCode.INVALID_LENGTH,),
            len(excerpt_lengths),
            0,
            max(0, max_excerpts) if isinstance(max_excerpts, int) and not isinstance(max_excerpts, bool) else 0,
            0,
        )

    total_chars = sum(excerpt_lengths)
    max_total_chars = max_excerpts * max_excerpt_chars
    codes: list[ExcerptBudgetCode] = []
    if not profile_approved:
        codes.append(ExcerptBudgetCode.PROFILE_NOT_APPROVED)
    if any(length > max_excerpt_chars for length in excerpt_lengths):
        codes.append(ExcerptBudgetCode.EXCERPT_ITEM_TOO_LONG)
    if len(excerpt_lengths) > max_excerpts:
        codes.append(ExcerptBudgetCode.EXCERPT_COUNT_EXCEEDED)
    if total_chars > max_total_chars:
        codes.append(ExcerptBudgetCode.TOTAL_CHAR_BUDGET_EXCEEDED)
    if codes:
        return ExcerptBudgetDecision(
            RightsPolicyDisposition.PROHIBITED,
            tuple(codes),
            len(excerpt_lengths),
            total_chars,
            max_excerpts,
            max_total_chars,
        )
    return ExcerptBudgetDecision(
        RightsPolicyDisposition.ALLOWED,
        (ExcerptBudgetCode.ALLOW,),
        len(excerpt_lengths),
        total_chars,
        max_excerpts,
        max_total_chars,
    )


def decide_media_use(request: MediaUseRequest) -> MediaUseDecision:
    """Fail-closed authorization seam for public media embeds.

    Copy/republication modes remain prohibited in the baseline.  An embed can be
    allowed only from pre-existing CLEARED rights plus an explicit public-use grant
    and an approved source-specific media profile.  This is technical enforcement,
    not a legal clearance decision.
    """

    try:
        kind = MediaUseKind(str(request.kind))
    except ValueError:
        return MediaUseDecision(
            RightsPolicyDisposition.PROHIBITED,
            (MediaDecisionCode.MEDIA_USE_KIND_INVALID,),
        )
    if kind is not MediaUseKind.EMBED:
        return MediaUseDecision(
            RightsPolicyDisposition.PROHIBITED,
            (MediaDecisionCode.SUBSTITUTIVE_MEDIA_COPY,),
        )
    try:
        rights = RightsStatus(str(request.rights_status))
    except ValueError:
        return MediaUseDecision(
            RightsPolicyDisposition.PROHIBITED,
            (MediaDecisionCode.RIGHTS_NOT_CLEARED,),
        )

    codes: list[MediaDecisionCode] = []
    rights_code = _media_rights_block_code(rights)
    if rights_code is not None:
        codes.append(rights_code)
    if (
        rights_code is None
        and MEDIA_EMBED_PUBLIC_USE_REQUIRED
        not in tuple(request.permitted_public_uses or ())
    ):
        codes.append(MediaDecisionCode.PUBLIC_USE_NOT_PERMITTED)
    if str(request.content_kind or "").upper() not in {"VIDEO", "AUDIO"}:
        codes.append(MediaDecisionCode.CONTENT_KIND_NOT_MEDIA)
    if not _safe_public_https_url(request.media_url):
        codes.append(MediaDecisionCode.MEDIA_URL_INVALID)
    if not isinstance(request.media_policy_version, str) or not request.media_policy_version.strip():
        codes.append(MediaDecisionCode.MEDIA_POLICY_VERSION_MISSING)
    if not request.profile_approved:
        codes.append(MediaDecisionCode.PROFILE_NOT_APPROVED)

    if codes:
        return MediaUseDecision(
            RightsPolicyDisposition.PROHIBITED,
            tuple(dict.fromkeys(codes)),
        )
    return MediaUseDecision(
        RightsPolicyDisposition.ALLOWED,
        (MediaDecisionCode.ALLOW,),
    )


_AUDIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_AUDIT_REASON_CODES = 8


def build_rights_policy_audit(
    *,
    subject_ref: str,
    disposition: StrEnum | str,
    reason_codes: tuple[StrEnum | str, ...],
) -> RightsPolicyAuditReceipt:
    """Return a bounded, content-free policy receipt.

    Only enum-like machine codes are retained.  Free-form reasons, excerpt text,
    URLs, rights receipts, and source bodies are not accepted into this structure.
    """

    subject = str(subject_ref or "").strip()
    if not _AUDIT_REF.fullmatch(subject):
        subject = "REDACTED_IDENTIFIER"
    disposition_value = disposition.value if isinstance(disposition, StrEnum) else str(disposition)
    if disposition_value not in {item.value for item in RightsPolicyDisposition} | {
        item.value for item in ExcerptDisposition
    }:
        disposition_value = RightsPolicyDisposition.PROHIBITED.value

    allowed_codes = (
        {item.value for item in ExcerptDecisionCode}
        | {item.value for item in ExcerptBudgetCode}
        | {item.value for item in MediaDecisionCode}
    )
    normalized: list[str] = []
    for raw_code in reason_codes:
        value = raw_code.value if isinstance(raw_code, StrEnum) else str(raw_code)
        if value in allowed_codes and value not in normalized:
            normalized.append(value)
    truncated = len(normalized) > MAX_AUDIT_REASON_CODES
    bounded = tuple(normalized[:MAX_AUDIT_REASON_CODES])
    if not bounded:
        bounded = ("RIGHTS_NOT_CLEARED",)
    return RightsPolicyAuditReceipt(
        policy_version=EXCERPT_POLICY_VERSION,
        subject_ref=subject,
        disposition=disposition_value,
        reason_codes=bounded,
        reason_count=len(bounded),
        reasons_truncated=truncated,
    )


__all__ = [
    "ALLOWED_PUBLIC_METHOD_FIELDS",
    "ExcerptDecision",
    "ExcerptDecisionCode",
    "ExcerptDisposition",
    "ExcerptBudgetCode",
    "ExcerptBudgetDecision",
    "ExcerptRequest",
    "EXCERPT_POLICY_VERSION",
    "EXCERPT_PROFILE_APPROVED",
    "EXCERPT_PUBLIC_USE_REQUIRED",
    "MAX_EXCERPT_CHARS",
    "MAX_EXCERPT_RATIO",
    "MAX_EXCERPTS_PER_DOSSIER",
    "MAX_AUDIT_REASON_CODES",
    "MEDIA_EMBED_PUBLIC_USE_REQUIRED",
    "MediaDecisionCode",
    "MediaUseDecision",
    "MediaUseKind",
    "MediaUseRequest",
    "PUBLICATION_AUTHORIZING_RIGHTS_STATUSES",
    "REQUIRED_ATTRIBUTION_FIELDS",
    "RightsStatus",
    "RightsPolicyAuditReceipt",
    "RightsPolicyDisposition",
    "build_rights_policy_audit",
    "decide_excerpt",
    "decide_excerpt_budget",
    "decide_media_use",
    "dossier_excerpt_budget",
    "effective_excerpt_cap",
    "render_attributed_excerpt",
]
