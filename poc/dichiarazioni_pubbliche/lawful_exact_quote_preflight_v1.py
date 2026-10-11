"""DP-317 offline consistency preflight for an exact public quotation.

This module compares *claims* about a source-specific, capture-specific lawful
quotation scope. Neither a claim, its hashes, a locally supplied reviewer name,
nor this result authenticates a legal grant. All public consumers MUST hold until
independent DP-307 qualified review, DP-320 read-time revocation authority and
DP-443 accepted live pilot attestations are wired into the public release path.

Only metadata and hashes are handled. No source body or private legal evidence is
persisted, emitted, or licensed here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.quote_binding import (
    QUOTE_BINDING_VERSION,
    QuoteBindingResult,
)
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)


EXACT_QUOTE_PREFLIGHT_VERSION = "dp317-source-only-exact-quote-v1"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_TEXT_REPRESENTATIONS = frozenset(
    {
        "WRITTEN_ORIGINAL",
        "OFFICIAL_TRANSCRIPT",
        "ASR_TRANSCRIPT",
        "DOCUMENT_OCR",
        "EDITORIAL_TRANSLATION",
        "CREATIVE_TEXT",
    }
)
_NON_TEXT_REPRESENTATIONS = frozenset(
    {
        "FILM_CLIP",
        "AUDIO_CLIP",
        "SCREENSHOT",
        "EMBED",
    }
)
_PUBLIC_USES = frozenset(
    {
        "STATEMENT",
        "LIST",
        "COMPARISON",
        "SEARCH",
        "API",
        "HTML",
        "RDF",
        "JSON_LD",
    }
)
_PURPOSES = frozenset({"PUBLIC_QUOTATION", "EDUCATIONAL_EXCERPT", "COMMERCIAL_REUSE"})
_LAWFUL_BASES = frozenset(
    {
        "CASE_SPECIFIC_PERMISSION",
        "SOURCE_SPECIFIC_LICENCE",
        "QUALIFIED_CASE_SPECIFIC_EXCEPTION",
    }
)
_EXTERNAL_GATES = ("DP-307", "DP-320", "DP-443")


@dataclass(frozen=True)
class ExactQuoteRequest:
    """Identity of one *proposed* use, not an approved public statement."""

    subject: RightsSubject
    capture_id: str
    capture_version: str
    capture_sha256: str
    representation_sha256: str
    quotation_sha256: str
    context_sha256: str
    selector_start: int
    selector_end: int
    representation: str
    text_role: str
    source_language: str
    displayed_language: str
    public_use: str
    purpose: str
    jurisdiction: str
    attribution_ref: str | None
    translation_parent_sha256: str | None = None
    representation_derivation_ref: str | None = None


@dataclass(frozen=True)
class ScopedQuoteRightsClaim:
    """Unauthenticated, private operator-supplied scope metadata.

    scope_fingerprint fixes every ExactQuoteRequest field, including the exact
    source locator, capture, wording, representation, use and jurisdiction.
    Signed/effective legal decisions must be independently verified elsewhere.
    """

    documented_scope: ExactQuoteRequest
    scope_fingerprint: str
    decision_version: str
    status: str
    legal_basis: str
    source_terms_ref: str | None
    source_terms_version: str
    lawful_basis_receipt_ref: str | None
    qualified_reviewer_ref: str | None
    owner_decision_ref: str | None
    reviewed_at: str | None
    effective_at: str | None
    expires_at: str | None
    max_quotation_chars: int | None
    necessity_ref: str | None
    attribution_required: bool
    conditions_satisfied: bool
    version_state: str
    revocation_state: str
    revocation_epoch: int


@dataclass(frozen=True)
class ExactQuotePreflightResult:
    status: str
    reason_code: str
    source_only_consistent: bool
    public_quote_permitted: bool
    scope_fingerprint: str
    required_external_gates: tuple[str, ...] = _EXTERNAL_GATES
    contract_version: str = EXACT_QUOTE_PREFLIGHT_VERSION


def quote_scope_fingerprint(request: ExactQuoteRequest) -> str:
    """Domain-separated identifier, useful for comparison but not authority."""
    if not isinstance(request, ExactQuoteRequest):
        raise TypeError("QUOTE_REQUEST_CONTRACT_INVALID")
    material = {
        "contract": EXACT_QUOTE_PREFLIGHT_VERSION,
        "request": asdict(request),
    }
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _nonempty(value: object, *, max_len: int = 256) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= max_len
        and "\x00" not in value
    )


def _hash(value: object) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _held(
    reason: str, fingerprint: str = "", *, consistent: bool = False
) -> ExactQuotePreflightResult:
    return ExactQuotePreflightResult(
        status="HELD",
        reason_code=reason,
        source_only_consistent=consistent,
        public_quote_permitted=False,
        scope_fingerprint=fingerprint,
    )


def _request_problem(request: ExactQuoteRequest) -> str | None:
    if not isinstance(request.subject, RightsSubject):
        return "QUOTE_SOURCE_SUBJECT_INVALID"
    try:
        rights_subject_fingerprint(request.subject)
    except (TypeError, AttributeError, ValueError):
        return "QUOTE_SOURCE_SUBJECT_INVALID"
    if not request.subject.content_id or not _nonempty(
        request.subject.content_id, max_len=512
    ):
        return "QUOTE_SOURCE_CONTENT_REQUIRED"
    if not all((_nonempty(request.capture_id), _nonempty(request.capture_version))):
        return "QUOTE_CAPTURE_IDENTITY_INVALID"
    if not all(
        (
            _hash(request.capture_sha256),
            _hash(request.representation_sha256),
            _hash(request.quotation_sha256),
            _hash(request.context_sha256),
        )
    ):
        return "QUOTE_HASH_BINDING_INVALID"
    if request.capture_sha256 != request.representation_sha256 and not _nonempty(
        request.representation_derivation_ref, max_len=512
    ):
        return "QUOTE_REPRESENTATION_DERIVATION_MISSING"
    if (
        type(request.selector_start) is not int
        or type(request.selector_end) is not int
        or request.selector_start < 0
        or request.selector_end <= request.selector_start
    ):
        return "QUOTE_SELECTOR_INVALID"
    if request.representation in _NON_TEXT_REPRESENTATIONS:
        return "QUOTE_NON_TEXT_REPRESENTATION_HELD"
    if request.representation not in _TEXT_REPRESENTATIONS:
        return "QUOTE_REPRESENTATION_UNKNOWN"
    if request.representation in {
        "OFFICIAL_TRANSCRIPT",
        "ASR_TRANSCRIPT",
        "DOCUMENT_OCR",
        "EDITORIAL_TRANSLATION",
    } and not _nonempty(request.representation_derivation_ref, max_len=512):
        return "QUOTE_REPRESENTATION_DERIVATION_MISSING"
    if (
        not isinstance(request.source_language, str)
        or not _LANGUAGE.fullmatch(request.source_language)
        or not isinstance(request.displayed_language, str)
        or not _LANGUAGE.fullmatch(request.displayed_language)
    ):
        return "QUOTE_LANGUAGE_INVALID"
    if request.text_role == "SOURCE_ORIGINAL":
        if (
            request.representation == "EDITORIAL_TRANSLATION"
            or request.source_language != request.displayed_language
            or request.translation_parent_sha256 is not None
        ):
            return "QUOTE_ORIGINAL_LANGUAGE_MISMATCH"
    elif request.text_role == "IDENTIFIED_TRANSLATION":
        if (
            request.representation != "EDITORIAL_TRANSLATION"
            or request.source_language == request.displayed_language
            or not _hash(request.translation_parent_sha256)
            or request.translation_parent_sha256 == request.representation_sha256
        ):
            return "QUOTE_TRANSLATION_LINEAGE_INVALID"
    else:
        return "QUOTE_WORDING_ROLE_UNKNOWN"
    if request.public_use not in _PUBLIC_USES or request.purpose not in _PURPOSES:
        return "QUOTE_PUBLIC_USE_UNKNOWN"
    if not (
        isinstance(request.jurisdiction, str)
        and re.fullmatch(r"[A-Z]{2}", request.jurisdiction)
    ):
        return "QUOTE_JURISDICTION_INVALID"
    if not _nonempty(request.attribution_ref, max_len=512):
        return "QUOTE_ATTRIBUTION_MISSING"
    return None


def _binding_problem(
    request: ExactQuoteRequest, binding: QuoteBindingResult | None
) -> str | None:
    if not isinstance(binding, QuoteBindingResult):
        return "QUOTE_BINDING_MISSING"
    if (
        binding.status != "VERIFIED"
        or binding.reason_code != "EXACT_SOURCE_SPAN_VERIFIED"
        or binding.version != QUOTE_BINDING_VERSION
    ):
        return "QUOTE_BINDING_UNVERIFIED"
    if (
        binding.source_sha256 != request.representation_sha256
        or binding.statement_text_sha256 != request.quotation_sha256
        or binding.passage_text_sha256 != request.quotation_sha256
        or binding.recomputed_text_sha256 != request.quotation_sha256
        or binding.start_char != request.selector_start
        or binding.end_char != request.selector_end
    ):
        return "QUOTE_BINDING_SCOPE_MISMATCH"
    return None


def _claim_problem(
    request: ExactQuoteRequest,
    claim: ScopedQuoteRightsClaim | None,
    now: datetime,
    current_revocation_epoch: int | None,
    fingerprint: str,
) -> str | None:
    if not isinstance(claim, ScopedQuoteRightsClaim):
        return "QUOTE_RIGHTS_CLAIM_MISSING"
    if claim.documented_scope != request:
        return "QUOTE_RIGHTS_DOCUMENTED_SCOPE_MISMATCH"
    if claim.scope_fingerprint != fingerprint:
        return "QUOTE_RIGHTS_SCOPE_MISMATCH"
    if claim.decision_version != "dp317-v1":
        return "QUOTE_RIGHTS_VERSION_UNKNOWN"
    if claim.status != "CASE_REVIEWED" or claim.version_state != "CURRENT":
        return "QUOTE_RIGHTS_REVIEW_NOT_CURRENT"
    if claim.revocation_state != "CURRENT":
        return "QUOTE_RIGHTS_REVOKED_OR_UNKNOWN"
    if (
        type(claim.revocation_epoch) is not int
        or claim.revocation_epoch < 0
        or type(current_revocation_epoch) is not int
        or claim.revocation_epoch != current_revocation_epoch
    ):
        return "QUOTE_REVOCATION_EPOCH_MISMATCH"
    if claim.legal_basis not in _LAWFUL_BASES:
        return "QUOTE_RIGHTS_BASIS_UNRESOLVED"
    if not all(
        (
            _nonempty(claim.source_terms_ref, max_len=512),
            _nonempty(claim.source_terms_version),
            _nonempty(claim.lawful_basis_receipt_ref, max_len=512),
            _nonempty(claim.qualified_reviewer_ref, max_len=512),
            _nonempty(claim.owner_decision_ref, max_len=512),
            _nonempty(claim.necessity_ref, max_len=512),
        )
    ):
        return "QUOTE_RIGHTS_PROOF_REFERENCES_INCOMPLETE"
    reviewed = _timestamp(claim.reviewed_at)
    effective = _timestamp(claim.effective_at)
    expiry = _timestamp(claim.expires_at)
    if reviewed is None or effective is None or expiry is None:
        return "QUOTE_RIGHTS_INTERVAL_INVALID"
    if reviewed > now or effective > now or expiry <= now or expiry <= effective:
        return "QUOTE_RIGHTS_EXPIRED_OR_NOT_EFFECTIVE"
    if (
        type(claim.max_quotation_chars) is not int
        or claim.max_quotation_chars <= 0
        or request.selector_end - request.selector_start > claim.max_quotation_chars
    ):
        return "QUOTE_RIGHTS_BOUNDED_LENGTH_NOT_PROVEN"
    if claim.attribution_required is not True or claim.conditions_satisfied is not True:
        return "QUOTE_RIGHTS_CONDITIONS_UNRESOLVED"
    return None


def evaluate_exact_quote_preflight(
    *,
    request: ExactQuoteRequest,
    rights_claim: ScopedQuoteRightsClaim | None,
    private_rights_record: PrivateRightsRecord | None,
    binding: QuoteBindingResult | None,
    private_rights_record_id: str,
    private_rights_policy_version: str,
    current_revocation_epoch: int | None,
    now: datetime,
) -> ExactQuotePreflightResult:
    """Pure, fail-closed source-only guard. Never yields a public grant.

    The DP-236 private STORE_BODY clearance cannot be reused as EXCERPT_PUBLIC.
    Revocation epoch is a *provided snapshot*; a caller can claim any value and
    this check cannot establish the live DP-320 lock/cache state. Exact success
    therefore remains HELD, including for synthetic fully matching fixtures.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _held("QUOTE_CLOCK_INVALID")
    now = now.astimezone(timezone.utc)
    if not isinstance(request, ExactQuoteRequest):
        return _held("QUOTE_REQUEST_CONTRACT_INVALID")
    problem = _request_problem(request)
    if problem is not None:
        return _held(problem)
    try:
        fingerprint = quote_scope_fingerprint(request)
    except (TypeError, ValueError, AttributeError):
        return _held("QUOTE_SCOPE_SERIALIZATION_INVALID")
    problem = _binding_problem(request, binding)
    if problem is not None:
        return _held(problem, fingerprint)
    try:
        private_use = evaluate_source_use(
            private_rights_record,
            subject=request.subject,
            rights_record_id=private_rights_record_id,
            policy_version=private_rights_policy_version,
            use="STORE_BODY",
            now=now,
        )
    except (AttributeError, TypeError, ValueError):
        return _held("QUOTE_PRIVATE_RIGHTS_CONTRACT_INVALID", fingerprint)
    if not private_use.permitted:
        return _held(private_use.reason_code, fingerprint)
    problem = _claim_problem(
        request, rights_claim, now, current_revocation_epoch, fingerprint
    )
    if problem is not None:
        return _held(problem, fingerprint)
    return _held(
        "EXTERNAL_QUALIFIED_AND_LIVE_PROOF_REQUIRED",
        fingerprint,
        consistent=True,
    )


__all__ = [
    "EXACT_QUOTE_PREFLIGHT_VERSION",
    "ExactQuotePreflightResult",
    "ExactQuoteRequest",
    "ScopedQuoteRightsClaim",
    "evaluate_exact_quote_preflight",
    "quote_scope_fingerprint",
]
