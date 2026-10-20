"""DP-239 independent AI review attestations for a private machine translation.

This module never runs a provider or promotes a translation. A second model
must independently assess the same hash-bound original and derived version.
External receipts, source rights and actual model independence are supplied
and verified outside this contract; synthetic approvals cannot publish.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime

from dichiarazioni_pubbliche.multilingual_derivation import PrivateTranslationDerivation
from dichiarazioni_pubbliche.multilingual_gold import TRANSLATION_MEANING_RISKS
from dichiarazioni_pubbliche.wording_contract import TranslationReviewState


AI_TRANSLATION_REVIEW_VERSION = "dp239-ai-double-review-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED_PAIR = ("de", "it")
_LANGUAGE_HOLDS = frozenset({
    "CODE_SWITCH_UNRESOLVED", "SOURCE_LANGUAGE_UNKNOWN_OR_UNVERIFIED",
    "SCRIPT_UNKNOWN_OR_MIXED", "SOURCE_SCRIPT_MISMATCH",
    "TARGET_SCRIPT_MISMATCH", "LANGUAGE_PAIR_RISK_RULE_UNAVAILABLE",
})


@dataclass(frozen=True)
class AITranslationReview:
    reviewer_id: str
    provider_id: str
    model_id: str
    model_version: str
    prompt_sha256: str
    config_sha256: str
    response_sha256: str
    translation_id: str
    original_quote_sha256: str
    source_version_sha256: str
    translated_text_sha256: str
    source_language: str
    target_language: str
    rights_receipt_sha256: str
    license_ref: str
    observed_at: str
    retention_until: str
    verdict: str  # FAITHFUL / MISMATCH / UNRESOLVED
    meaning_risks: tuple[str, ...]
    contract_version: str = AI_TRANSLATION_REVIEW_VERSION


@dataclass(frozen=True)
class AITranslationReviewResult:
    status: str
    translation_id: str
    language_pair: str
    review_receipt_sha256: str | None = None
    meaning_risks: tuple[str, ...] = ()
    double_review_complete: bool = False
    release_eligible: bool = False
    publication_authority: bool = False


def _timestamp(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except ValueError:
        return None


def _has_sha(value: str) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _nonempty(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


def _externally_valid(check: Callable[[AITranslationReview], bool] | None,
                      review: AITranslationReview) -> bool:
    if check is None:
        return False
    try:
        return check(review) is True
    except Exception:
        return False


def evaluate_ai_translation_reviews(
    translation: PrivateTranslationDerivation,
    reviews: tuple[AITranslationReview, ...],
    *,
    now: datetime,
    independent_receipt_check: Callable[[AITranslationReview], bool] | None = None,
    rights_receipt_check: Callable[[AITranslationReview], bool] | None = None,
) -> AITranslationReviewResult:
    """Evaluate two independently attested model outputs, always privately HELD.

    Callback checks represent integration seams for durable signed provider
    receipts and current exact-source rights, not model assertions. Returning
    True in a local test establishes *only* this deterministic contract.
    """
    if not isinstance(translation, PrivateTranslationDerivation):
        raise ValueError("DP239_AI_TRANSLATION_INVALID")
    original = translation.original
    pair = f"{original.language}->{translation.target_language}"
    def blocked(code: str, risks: tuple[str, ...] = ()) -> AITranslationReviewResult:
        return AITranslationReviewResult(code, translation.id, pair, meaning_risks=risks)

    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("DP239_AI_REVIEW_CLOCK_INVALID")
    if (translation.method != "MACHINE" or translation.status != "HELD"
            or translation.review_state != TranslationReviewState.NEEDS_REVIEW
            or translation.public_quote_eligible):
        return blocked("BLOCKED_DERIVATIVE_NOT_HELD")
    if (not isinstance(original.language, str)
            or not isinstance(translation.target_language, str)
            or (original.language.split("-", 1)[0], translation.target_language.split("-", 1)[0])
            != _SUPPORTED_PAIR
            or original.language_origin != "SOURCE_DECLARED"
            or _LANGUAGE_HOLDS.intersection(translation.signal_codes)
            or original.code_switch_spans):
        return blocked("UNSUPPORTED_LANGUAGE_PAIR")
    if not isinstance(reviews, tuple) or len(reviews) != 2 or not all(
            isinstance(item, AITranslationReview) for item in reviews):
        return blocked("BLOCKED_TWO_AI_REVIEWS_REQUIRED")

    for row in reviews:
        if (row.contract_version != AI_TRANSLATION_REVIEW_VERSION
                or any(not _nonempty(value) for value in (
                    row.reviewer_id, row.provider_id, row.model_id,
                    row.model_version, row.translation_id, row.source_language,
                    row.target_language, row.license_ref,
                ))
                or any(not _has_sha(value) for value in (
                    row.prompt_sha256, row.config_sha256, row.response_sha256,
                    row.original_quote_sha256, row.source_version_sha256,
                    row.translated_text_sha256, row.rights_receipt_sha256,
                ))
                or row.verdict not in {"FAITHFUL", "MISMATCH", "UNRESOLVED"}
                or not isinstance(row.meaning_risks, tuple)
                or any(not isinstance(code, str) for code in row.meaning_risks)
                or len(set(row.meaning_risks)) != len(row.meaning_risks)
                or set(row.meaning_risks) - TRANSLATION_MEANING_RISKS):
            return blocked("BLOCKED_REVIEW_EVIDENCE_INVALID")
        if (row.translation_id != translation.id
                or row.original_quote_sha256 != original.quote_sha256
                or row.source_version_sha256 != original.source_version_sha256
                or row.translated_text_sha256 != translation.translated_text_sha256
                or row.source_language != original.language
                or row.target_language != translation.target_language):
            return blocked("BLOCKED_REVIEW_SOURCE_BINDING")

    primary, independent = reviews
    if (primary.reviewer_id == independent.reviewer_id
            or primary.provider_id == independent.provider_id
            or primary.model_id == independent.model_id
            or primary.response_sha256 == independent.response_sha256
            or primary.prompt_sha256 == independent.prompt_sha256
            or primary.provider_id == translation.provider_id
            or independent.provider_id == translation.provider_id
            or primary.model_id == translation.model_id
            or independent.model_id == translation.model_id):
        return blocked("BLOCKED_REVIEW_INDEPENDENCE")
    if (primary.rights_receipt_sha256 != independent.rights_receipt_sha256
            or primary.license_ref != independent.license_ref):
        return blocked("BLOCKED_SOURCE_RIGHTS_RECEIPT")
    for row in reviews:
        observed, expiration = _timestamp(row.observed_at), _timestamp(row.retention_until)
        if (observed is None or expiration is None or observed > now
                or expiration <= now or expiration <= observed):
            return blocked("BLOCKED_REVIEW_RETENTION")
    if not all(_externally_valid(rights_receipt_check, row) for row in reviews):
        return blocked("BLOCKED_SOURCE_RIGHTS_RECEIPT")
    if not all(_externally_valid(independent_receipt_check, row) for row in reviews):
        return blocked("BLOCKED_EXTERNAL_REVIEW_ATTESTATION")

    risks = tuple(sorted(set(primary.meaning_risks) | set(independent.meaning_risks)
                         | (set(translation.signal_codes) & TRANSLATION_MEANING_RISKS)))
    payload = {
        "contract": AI_TRANSLATION_REVIEW_VERSION,
        "translation_id": translation.id,
        "reviews": [asdict(row) for row in reviews],
    }
    receipt = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    if (primary.verdict != independent.verdict
            or primary.meaning_risks != independent.meaning_risks):
        status = "HELD_REVIEW_DISAGREEMENT"
    elif primary.verdict != "FAITHFUL" or risks:
        status = "HELD_MEANING_RISK"
    else:
        status = "CONTRACT_ONLY_PRIVATE_HOLD"
    return AITranslationReviewResult(
        status, translation.id, pair, review_receipt_sha256=receipt,
        meaning_risks=risks, double_review_complete=True,
    )


__all__ = [
    "AI_TRANSLATION_REVIEW_VERSION", "AITranslationReview",
    "AITranslationReviewResult", "evaluate_ai_translation_reviews",
]
