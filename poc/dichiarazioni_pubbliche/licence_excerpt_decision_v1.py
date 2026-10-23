"""DP-317 licence-granted excerpt decision for one exact public quotation.

Why this module exists
----------------------
``evaluate_exact_quote_preflight`` is deliberately source-only: it can prove a
wording/capture/locator binding and it can *never* mint a grant, because a
caller-supplied epoch is not a live revocation authority. Its documented gap is
the "rights" half: nothing evaluated the actual source licence that grants a
reuse. This module is that half, and only that half, for one bounded case.

It is machine-checkable, not a legal opinion
--------------------------------------------
A permit here requires a *hashed* terms document that is byte-identified by
SHA-256, the licence identifier it declares, and a marker set that must be
observed inside that same document. The grant facts (attribution required,
adaptations allowed, commercial use allowed) are transcribed from the official
licence texts into ``LICENCE_GRANTS`` below; they are not supplied by the
caller, so an operator cannot assert a grant the licence does not make.

What stays closed
-----------------
``publication_authorized`` is False and the web projection is not touched. A
PERMITTED decision yields a *private* attributed rendering and a replayable
receipt for an authorised operator release; publishing it on the site is a
separate editorial/owner step (DP-305 ``EXCERPT_PROFILE_APPROVED``). Rights
that are not licence-granted (e.g. a case-specific permission) are PROHIBITED
here rather than silently upgraded.

Fail-closed boundaries
----------------------
* exact built-in primitive types only: no ``str``/``tuple``/``int`` subclasses,
  no callable or mutable leaves (the repo has a history of spoofing bugs);
* live revocation is read from an authority object at decision time, never from
  a caller-supplied integer, and it is read *after* every other check;
* expiry, revocation state and terms binding are re-evaluated on every call.

Pure: no I/O, no clock of its own, no database, no network.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from dichiarazioni_pubbliche.lawful_exact_quote_preflight_v1 import (
    ExactQuoteRequest,
    ScopedQuoteRightsClaim,
    evaluate_exact_quote_preflight,
    quote_scope_fingerprint,
)
from dichiarazioni_pubbliche.quote_binding import QuoteBindingResult
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRecord


LICENCE_EXCERPT_DECISION_VERSION = "dp317-licence-excerpt-v1"

# Product bound, not a legal quantity: an excerpt must stay non-substitutive.
# It mirrors the placeholder bound of DP-305 and the 400-character ceiling the
# DP-317 pilot receipts used; it is never presented as a statutory limit.
MAX_LICENCE_EXCERPT_CHARS = 400

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HTTPS_URL = re.compile(r"^https://[a-z0-9.-]+(?:/[^\s]*)?$")
_MARKER = re.compile(r"^[^\x00-\x1f]{3,120}$")


@dataclass(frozen=True)
class LicenceGrant:
    """Grant facts transcribed from the official licence text (see policy doc)."""

    licence_id: str
    licence_url: str
    attribution_required: bool
    adaptations_allowed: bool
    commercial_allowed: bool
    required_markers: tuple[str, ...]


LICENCE_GRANTS: dict[str, LicenceGrant] = {
    "CC-BY-4.0": LicenceGrant(
        "CC-BY-4.0",
        "https://creativecommons.org/licenses/by/4.0/",
        True,
        True,
        True,
        (
            "Attribution 4.0 International",
            "CC BY 4.0",
        ),
    ),
    "CC-BY-3.0": LicenceGrant(
        "CC-BY-3.0",
        "https://creativecommons.org/licenses/by/3.0/",
        True,
        True,
        True,
        (
            "Attribution 3.0 Unported",
            "CC BY 3.0",
        ),
    ),
    "CC0-1.0": LicenceGrant(
        "CC0-1.0",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        False,
        True,
        True,
        (
            "CC0 1.0 Universal",
            "CC0 1.0",
        ),
    ),
}


@dataclass(frozen=True)
class SourceTermsEvidence:
    """Identity of one fetched terms document plus what was read inside it."""

    terms_url: str
    terms_document_sha256: str
    terms_version: str
    licence_id: str
    licence_url: str
    rightsholder: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class AttributionStatement:
    creator: str
    work_title: str
    source_url: str
    licence_id: str
    licence_url: str
    modified: bool


class LiveRevocationAuthority(ABC):
    """Read-time revocation source. An epoch snapshot is not an authority."""

    @abstractmethod
    def current_epoch(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    def authority_ref(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class LicenceExcerptDecision:
    status: str
    reason_code: str
    scope_fingerprint: str
    licence_id: str | None = None
    terms_document_sha256: str | None = None
    attribution_text: str | None = None
    private_rendered_text: str | None = None
    quote_chars: int = 0
    max_quote_chars: int = MAX_LICENCE_EXCERPT_CHARS
    revocation_epoch: int | None = None
    private_only: bool = True
    publication_authorized: bool = False
    web_projection_enabled: bool = False
    contract_version: str = LICENCE_EXCERPT_DECISION_VERSION

    @property
    def permitted(self) -> bool:
        return self.status == "PERMITTED"


def _held(reason: str, fingerprint: str = "") -> LicenceExcerptDecision:
    return LicenceExcerptDecision("HELD", reason, fingerprint)


def _prohibited(
    reason: str, fingerprint: str = "", licence_id: str | None = None
) -> LicenceExcerptDecision:
    return LicenceExcerptDecision("PROHIBITED", reason, fingerprint, licence_id)


def _text(value: object, *, maximum: int = 512) -> bool:
    return (
        type(value) is str
        and bool(value.strip())
        and len(value) <= maximum
        and "\x00" not in value
    )


def _https(value: object) -> bool:
    return _text(value, maximum=2048) and bool(_HTTPS_URL.match(value))


def _evidence_problem(evidence: object) -> str | None:
    if type(evidence) is not SourceTermsEvidence:
        return "LICENCE_TERMS_EVIDENCE_INVALID"
    if not _https(evidence.terms_url):
        return "LICENCE_TERMS_URL_INVALID"
    if type(evidence.terms_document_sha256) is not str or not _SHA256.fullmatch(
        evidence.terms_document_sha256
    ):
        return "LICENCE_TERMS_DIGEST_INVALID"
    if not _text(evidence.terms_version, maximum=128):
        return "LICENCE_TERMS_VERSION_INVALID"
    if not _text(evidence.rightsholder, maximum=256):
        return "LICENCE_RIGHTSHOLDER_MISSING"
    if type(evidence.licence_id) is not str or evidence.licence_id not in LICENCE_GRANTS:
        return "LICENCE_ID_NOT_VERIFIABLE"
    if type(evidence.licence_url) is not str or (
        evidence.licence_url != LICENCE_GRANTS[evidence.licence_id].licence_url
    ):
        return "LICENCE_URL_MISMATCH"
    if type(evidence.markers) is not tuple:
        return "LICENCE_MARKERS_INVALID"
    if not evidence.markers:
        return "LICENCE_MARKERS_MISSING"
    if any(
        type(value) is not str or not _MARKER.fullmatch(value) for value in evidence.markers
    ):
        return "LICENCE_MARKERS_INVALID"
    if len(set(evidence.markers)) != len(evidence.markers):
        return "LICENCE_MARKERS_DUPLICATED"
    return None


def _attribution_problem(
    statement: object, evidence: SourceTermsEvidence, request: ExactQuoteRequest
) -> str | None:
    if type(statement) is not AttributionStatement:
        return "ATTRIBUTION_STATEMENT_MISSING"
    if not all(
        (
            _text(statement.creator, maximum=256),
            _text(statement.work_title, maximum=256),
            _text(statement.source_url, maximum=2048),
            _text(statement.licence_url, maximum=2048),
        )
    ):
        return "ATTRIBUTION_FIELDS_INCOMPLETE"
    if type(statement.modified) is not bool:
        return "ATTRIBUTION_MODIFICATION_UNKNOWN"
    if statement.creator != evidence.rightsholder:
        return "ATTRIBUTION_RIGHTSHOLDER_MISMATCH"
    if statement.licence_id != evidence.licence_id or (
        statement.licence_url != evidence.licence_url
    ):
        return "ATTRIBUTION_LICENCE_MISMATCH"
    if statement.source_url != request.subject.locator_value:
        return "ATTRIBUTION_LOCATOR_MISMATCH"
    if statement.modified is not False:
        return "ATTRIBUTION_MODIFIED_TEXT_NOT_SUPPORTED"
    return None


def render_attribution(statement: AttributionStatement, *, as_html: bool) -> str:
    """Plain attribution line; HTML callers get the same text escaped once."""

    if type(statement) is not AttributionStatement:
        raise ValueError("ATTRIBUTION_STATEMENT_MISSING")
    text = " — ".join(
        (
            statement.creator,
            statement.work_title,
            statement.source_url,
            statement.licence_id,
            statement.licence_url,
            "testo non modificato",
        )
    )
    return html.escape(text, quote=True) if as_html else text


def _render_private(
    private_quote_text: str, statement: AttributionStatement
) -> str:
    """Attributed private rendering; the quote is escaped, never reflowed."""

    return (
        f"“{html.escape(private_quote_text, quote=True)}” — "
        f"{render_attribution(statement, as_html=True)}"
    )


def _terms_binding_problem(
    evidence: SourceTermsEvidence, claim: ScopedQuoteRightsClaim
) -> str | None:
    if type(claim.source_terms_ref) is not str or type(claim.source_terms_version) is not str:
        return "LICENCE_TERMS_BINDING_MISMATCH"
    if (
        claim.source_terms_ref != evidence.terms_url
        or claim.source_terms_version != evidence.terms_version
    ):
        return "LICENCE_TERMS_BINDING_MISMATCH"
    return None


def _expiry_problem(claim: ScopedQuoteRightsClaim, now: datetime) -> str | None:
    raw = claim.expires_at
    if type(raw) is not str or not raw.strip():
        return "LICENCE_DECISION_EXPIRY_MISSING"
    try:
        expiry = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "LICENCE_DECISION_EXPIRY_INVALID"
    if expiry.tzinfo is None or expiry.utcoffset() is None or expiry <= now:
        return "LICENCE_DECISION_EXPIRED"
    return None


def _receipt(
    decision: LicenceExcerptDecision, request: ExactQuoteRequest
) -> str:
    material = {
        "contract": LICENCE_EXCERPT_DECISION_VERSION,
        "decision": asdict(decision),
        "request": asdict(request),
    }
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def decide_licence_excerpt(
    *,
    request: ExactQuoteRequest,
    binding: QuoteBindingResult | None,
    rights_claim: ScopedQuoteRightsClaim | None,
    private_rights_record: PrivateRightsRecord | None,
    private_rights_record_id: str,
    private_rights_policy_version: str,
    terms_evidence: SourceTermsEvidence | None,
    attribution: AttributionStatement | None,
    live_revocation: LiveRevocationAuthority | None,
    private_quote_text: str | None,
    now: datetime,
) -> LicenceExcerptDecision:
    """Authorise one bounded excerpt only under a verified source licence.

    Every earlier refusal returns HELD/PROHIBITED with an empty rendering. The
    live revocation authority is consulted last, so a stale or fabricated
    epoch cannot shortcut the licence checks.
    """
    if (
        type(now) is not datetime
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        return _held("LICENCE_DECISION_CLOCK_INVALID")
    now = now.astimezone(timezone.utc)
    if type(request) is not ExactQuoteRequest or type(binding) is not QuoteBindingResult:
        return _held("LICENCE_DECISION_INPUT_INVALID")
    if type(rights_claim) is not ScopedQuoteRightsClaim:
        return _held("LICENCE_RIGHTS_CLAIM_MISSING")
    fingerprint = quote_scope_fingerprint(request)
    # Licence-specific claim facts are checked first: neither a case-specific
    # permission nor a revoked decision may be reported as a mere inconsistency.
    if type(rights_claim.legal_basis) is not str or (
        rights_claim.legal_basis != "SOURCE_SPECIFIC_LICENCE"
    ):
        return _prohibited("LICENCE_GRANT_NOT_ESTABLISHED", fingerprint)
    if type(rights_claim.revocation_state) is not str or (
        rights_claim.revocation_state != "CURRENT"
    ):
        return _prohibited("LICENCE_DECISION_REVOKED", fingerprint)

    # Reuse the DP-317 source-only contract instead of re-implementing it: a
    # request, capture, wording or binding defect is refuted there, and only a
    # fully consistent case reaches the licence evaluation below.
    preflight = evaluate_exact_quote_preflight(
        request=request,
        rights_claim=rights_claim,
        private_rights_record=private_rights_record,
        binding=binding,
        private_rights_record_id=private_rights_record_id,
        private_rights_policy_version=private_rights_policy_version,
        current_revocation_epoch=rights_claim.revocation_epoch,
        now=now,
    )
    if preflight.reason_code == "EXTERNAL_QUALIFIED_AND_LIVE_PROOF_REQUIRED":
        if preflight.source_only_consistent is not True:
            return _held("LICENCE_SOURCE_ONLY_CONTRACT_INCONSISTENT", fingerprint)
    else:
        return _held(preflight.reason_code, fingerprint)

    problem = _evidence_problem(terms_evidence)
    if problem is not None:
        return _prohibited(problem, fingerprint)
    assert isinstance(terms_evidence, SourceTermsEvidence)
    grant = LICENCE_GRANTS[terms_evidence.licence_id]
    missing = tuple(
        marker for marker in grant.required_markers if marker not in terms_evidence.markers
    )
    if missing:
        return _prohibited("LICENCE_MARKERS_NOT_OBSERVED", fingerprint, grant.licence_id)

    problem = _terms_binding_problem(terms_evidence, rights_claim)
    if problem is not None:
        return _held(problem, fingerprint)

    if request.text_role == "IDENTIFIED_TRANSLATION" and not grant.adaptations_allowed:
        return _prohibited(
            "LICENCE_ADAPTATION_NOT_GRANTED", fingerprint, grant.licence_id
        )

    problem = _attribution_problem(attribution, terms_evidence, request)
    if problem is not None:
        return _held(problem, fingerprint)
    assert isinstance(attribution, AttributionStatement)

    quote_chars = request.selector_end - request.selector_start
    if quote_chars <= 0 or quote_chars > MAX_LICENCE_EXCERPT_CHARS:
        return _held("LICENCE_EXCERPT_BOUNDARY_EXCEEDED", fingerprint)
    if type(private_quote_text) is not str or not private_quote_text:
        return _held("LICENCE_EXCERPT_TEXT_MISSING", fingerprint)

    problem = _expiry_problem(rights_claim, now)
    if problem is not None:
        return _held(problem, fingerprint)

    if not isinstance(live_revocation, LiveRevocationAuthority):
        return _held("LIVE_REVOCATION_AUTHORITY_REQUIRED", fingerprint)
    try:
        epoch = live_revocation.current_epoch()
        authority_ref = live_revocation.authority_ref()
    except Exception:
        return _held("LIVE_REVOCATION_UNAVAILABLE", fingerprint)
    if type(epoch) is not int or epoch < 0:
        return _held("LIVE_REVOCATION_EPOCH_INVALID", fingerprint)
    if type(authority_ref) is not str or not authority_ref.strip():
        return _held("LIVE_REVOCATION_AUTHORITY_REF_INVALID", fingerprint)
    if epoch != rights_claim.revocation_epoch:
        return _prohibited("LIVE_REVOCATION_DIVERGED_FROM_CLAIM", fingerprint)

    decision = LicenceExcerptDecision(
        "PERMITTED",
        "LICENCE_GRANT_VERIFIED_WITH_CONDITIONS",
        fingerprint,
        grant.licence_id,
        terms_evidence.terms_document_sha256,
        render_attribution(attribution, as_html=False),
        _render_private(private_quote_text, attribution),
        quote_chars,
        MAX_LICENCE_EXCERPT_CHARS,
        epoch,
    )
    return decision


def licence_decision_receipt(
    decision: LicenceExcerptDecision, request: ExactQuoteRequest
) -> str:
    return _receipt(decision, request)


__all__ = [
    "AttributionStatement",
    "LICENCE_EXCERPT_DECISION_VERSION",
    "LICENCE_GRANTS",
    "LicenceExcerptDecision",
    "LicenceGrant",
    "LiveRevocationAuthority",
    "MAX_LICENCE_EXCERPT_CHARS",
    "SourceTermsEvidence",
    "decide_licence_excerpt",
    "licence_decision_receipt",
    "render_attribution",
]
