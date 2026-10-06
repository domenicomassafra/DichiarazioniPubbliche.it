from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


WORDING_CONTRACT_VERSION = "wording-contract-v1"
SOURCE_OCCURRENCE_ROLE = "SOURCE_OCCURRENCE"
DERIVED_REPRESENTATION_ROLE = "DERIVED_REPRESENTATION"


class WordingType(StrEnum):
    VERBATIM_ORIGINAL = "VERBATIM_ORIGINAL"
    PARAPHRASE = "PARAPHRASE"
    SUMMARY = "SUMMARY"
    TRANSLATION = "TRANSLATION"
    REPORTED_QUOTE = "REPORTED_QUOTE"


SOURCE_WORDING_TYPES = frozenset(
    {WordingType.VERBATIM_ORIGINAL, WordingType.REPORTED_QUOTE}
)
DERIVED_WORDING_TYPES = frozenset(
    {WordingType.PARAPHRASE, WordingType.SUMMARY, WordingType.TRANSLATION}
)


class TranslationReviewState(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    REJECTED = "REJECTED"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?")
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
)
_CAPITALIZED_RE = re.compile(r"\b[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’.-]{2,}\b")

_NEGATIONS = {
    "it": re.compile(r"\b(?:non|mai|nessun[oa]?|senza)\b", re.I),
    "en": re.compile(r"\b(?:not|never|no|without|n't)\b", re.I),
    "fr": re.compile(r"\b(?:ne|pas|jamais|aucun|sans)\b", re.I),
    "es": re.compile(r"\b(?:no|nunca|ning[uú]n|sin)\b", re.I),
}
_MODALS = {
    "it": re.compile(r"\b(?:deve|devono|può|possono|potrebbe|potrebbero|dovrebbe|dovrebbero)\b", re.I),
    "en": re.compile(r"\b(?:must|may|might|can|could|should|would)\b", re.I),
    "fr": re.compile(r"\b(?:doit|doivent|peut|peuvent|pourrait|devrait)\b", re.I),
    "es": re.compile(r"\b(?:debe|deben|puede|pueden|podría|debería)\b", re.I),
}
_MODAL_CLASSES = {
    "it": {
        "OBLIGATION": re.compile(r"\b(?:deve|devono|dovrebbe|dovrebbero)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:può|possono|potrebbe|potrebbero)\b", re.I),
    },
    "en": {
        "OBLIGATION": re.compile(r"\b(?:must|should)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:may|might|can|could|would)\b", re.I),
    },
    "fr": {
        "OBLIGATION": re.compile(r"\b(?:doit|doivent|devrait)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:peut|peuvent|pourrait)\b", re.I),
    },
    "es": {
        "OBLIGATION": re.compile(r"\b(?:debe|deben|debería)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:puede|pueden|podría)\b", re.I),
    },
}
_LEGAL_CATEGORY_PATTERNS = {
    "INVESTIGATED": re.compile(
        r"\b(?:indagat[oa]|investigated|mis en examen|investigad[oa])\b", re.I
    ),
    "DEFENDANT": re.compile(
        r"\b(?:imputat[oa]|defendant|accused|prévenu|acusad[oa])\b", re.I
    ),
    "CONVICTED": re.compile(
        r"\b(?:condannat[oa]|convicted|condamné|condenad[oa])\b", re.I
    ),
    "ACQUITTED": re.compile(
        r"\b(?:assolt[oa]|acquitted|acquitté|absuelt[oa])\b", re.I
    ),
}


def _sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _validated_hash(value: str, field: str) -> str:
    clean = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"WORDING_{field.upper()}_INVALID")
    return clean


@dataclass(frozen=True)
class WordingReference:
    wording_type: WordingType
    text_sha256: str
    occurrence_id: str
    language: str | None
    derivation_method: str
    derivation_version: str
    source_wording_type: WordingType | None = None
    source_language: str | None = None
    review_state: str | None = None
    author_ref: str | None = None
    reviewer_ref: str | None = None
    signal_codes: tuple[str, ...] = ()
    version: str = WORDING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validated_hash(self.text_sha256, "text_sha256")
        if not str(self.occurrence_id or "").strip():
            raise ValueError("WORDING_OCCURRENCE_ID_REQUIRED")
        if not str(self.derivation_method or "").strip():
            raise ValueError("WORDING_DERIVATION_METHOD_REQUIRED")
        if not str(self.derivation_version or "").strip():
            raise ValueError("WORDING_DERIVATION_VERSION_REQUIRED")
        if (
            self.wording_type == WordingType.VERBATIM_ORIGINAL
            and self.source_wording_type is not None
        ):
            raise ValueError("WORDING_ORIGINAL_CANNOT_DERIVE_FROM_ANOTHER_WORDING_TYPE")
        if self.wording_type in DERIVED_WORDING_TYPES:
            if self.source_wording_type not in SOURCE_WORDING_TYPES:
                raise ValueError("WORDING_DERIVED_SOURCE_TYPE_REQUIRED")
        if self.wording_type == WordingType.REPORTED_QUOTE:
            if self.source_wording_type is not None:
                raise ValueError("WORDING_REPORTED_SOURCE_CANNOT_DERIVE_FROM_ANOTHER_TYPE")
        if self.wording_type == WordingType.TRANSLATION:
            if not str(self.source_language or "").strip():
                raise ValueError("WORDING_TRANSLATION_SOURCE_LANGUAGE_REQUIRED")
            if not str(self.language or "").strip():
                raise ValueError("WORDING_TRANSLATION_TARGET_LANGUAGE_REQUIRED")
            if self.review_state not in {state.value for state in TranslationReviewState}:
                raise ValueError("WORDING_TRANSLATION_REVIEW_STATE_REQUIRED")

    @property
    def direct_quote_eligible(self) -> bool:
        return self.wording_type == WordingType.VERBATIM_ORIGINAL

    @property
    def representation_role(self) -> str:
        if self.wording_type in SOURCE_WORDING_TYPES:
            return SOURCE_OCCURRENCE_ROLE
        return DERIVED_REPRESENTATION_ROLE

    def public_metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data["wording_type"] = self.wording_type.value
        if self.source_wording_type is not None:
            data["source_wording_type"] = self.source_wording_type.value
        data["direct_quote_eligible"] = self.direct_quote_eligible
        data["representation_role"] = self.representation_role
        return data


def make_source_occurrence_wording(
    *,
    occurrence_id: str,
    text_sha256: str,
    language: str | None = None,
    derivation_version: str,
    wording_type: WordingType = WordingType.VERBATIM_ORIGINAL,
) -> WordingReference:
    if wording_type not in SOURCE_WORDING_TYPES:
        raise ValueError("WORDING_SOURCE_TYPE_INVALID")
    return WordingReference(
        wording_type=wording_type,
        text_sha256=_validated_hash(text_sha256, "text_sha256"),
        occurrence_id=occurrence_id,
        language=str(language or "").strip() or None,
        derivation_method=(
            "EXACT_SOURCE_SPAN"
            if wording_type == WordingType.VERBATIM_ORIGINAL
            else "EXACT_REPORTED_SOURCE_SPAN"
        ),
        derivation_version=derivation_version,
    )


def make_derived_wording(
    *,
    wording_type: WordingType,
    occurrence_id: str,
    text: str,
    source_wording_type: WordingType,
    language: str | None,
    derivation_method: str,
    derivation_version: str,
    source_language: str | None = None,
    review_state: str | None = None,
    author_ref: str | None = None,
    reviewer_ref: str | None = None,
    signal_codes: Sequence[str] = (),
) -> WordingReference:
    if wording_type not in DERIVED_WORDING_TYPES:
        raise ValueError("WORDING_DERIVED_TYPE_INVALID")
    if source_wording_type not in SOURCE_WORDING_TYPES:
        raise ValueError("WORDING_DERIVED_SOURCE_TYPE_REQUIRED")
    value = str(text or "").strip()
    if not value:
        raise ValueError("WORDING_DERIVED_TEXT_REQUIRED")
    method = str(derivation_method or "").strip()
    if not method:
        raise ValueError("WORDING_DERIVATION_METHOD_REQUIRED")
    return WordingReference(
        wording_type=wording_type,
        text_sha256=_sha256(value),
        occurrence_id=occurrence_id,
        language=str(language or "").strip() or None,
        derivation_method=method,
        derivation_version=derivation_version,
        source_wording_type=source_wording_type,
        source_language=str(source_language or "").strip() or None,
        review_state=str(review_state or "").strip() or None,
        author_ref=str(author_ref or "").strip() or None,
        reviewer_ref=str(reviewer_ref or "").strip() or None,
        signal_codes=tuple(str(code).strip() for code in signal_codes if str(code).strip()),
    )


def make_normalized_claim_wording(
    *,
    occurrence_id: str,
    normalized_claim: str,
    language: str | None = None,
    derivation_version: str,
    source_wording_type: WordingType = WordingType.VERBATIM_ORIGINAL,
) -> WordingReference:
    text = str(normalized_claim or "").strip()
    if not text:
        raise ValueError("WORDING_NORMALIZED_CLAIM_REQUIRED")
    return make_derived_wording(
        wording_type=WordingType.PARAPHRASE,
        occurrence_id=occurrence_id,
        text=text,
        source_wording_type=source_wording_type,
        language=str(language or "").strip() or None,
        derivation_method="CLAIM_NORMALIZATION",
        derivation_version=derivation_version,
    )


def make_summary_wording(
    *,
    occurrence_id: str,
    summary: str,
    source_wording_type: WordingType,
    language: str | None,
    derivation_version: str,
    author_ref: str | None = None,
    reviewer_ref: str | None = None,
) -> WordingReference:
    return make_derived_wording(
        wording_type=WordingType.SUMMARY,
        occurrence_id=occurrence_id,
        text=summary,
        source_wording_type=source_wording_type,
        language=language,
        derivation_method="EDITORIAL_SUMMARY",
        derivation_version=derivation_version,
        author_ref=author_ref,
        reviewer_ref=reviewer_ref,
    )


def _clean_source_provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("WORDING_SOURCE_PROVENANCE_INVALID")
    allowed = {
        "passage_id",
        "selector_type",
        "capture_id",
        "canonical_segment_id",
        "start_char",
        "end_char",
        "quote_local_start_char",
        "quote_local_end_char",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError("WORDING_SOURCE_PROVENANCE_FIELD_INVALID")
    cleaned: dict[str, Any] = {}
    for key, raw in value.items():
        if raw is None:
            continue
        if key.endswith("_char"):
            if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
                raise ValueError("WORDING_SOURCE_PROVENANCE_OFFSET_INVALID")
            cleaned[key] = raw
            continue
        text = str(raw).strip()
        if not text:
            raise ValueError("WORDING_SOURCE_PROVENANCE_VALUE_INVALID")
        cleaned[key] = text[:500]
    selector_type = cleaned.get("selector_type")
    if selector_type is not None and selector_type not in {
        "TEXT_POSITION",
        "PAGE_RANGE",
        "MEDIA_SEGMENT_REF",
    }:
        raise ValueError("WORDING_SOURCE_PROVENANCE_SELECTOR_INVALID")
    for start_key, end_key in (
        ("start_char", "end_char"),
        ("quote_local_start_char", "quote_local_end_char"),
    ):
        start_present = start_key in cleaned
        end_present = end_key in cleaned
        if start_present != end_present:
            raise ValueError("WORDING_SOURCE_PROVENANCE_OFFSET_PAIR_REQUIRED")
        if start_present and cleaned[end_key] <= cleaned[start_key]:
            raise ValueError("WORDING_SOURCE_PROVENANCE_OFFSET_RANGE_INVALID")
    if cleaned.get("capture_id") and cleaned.get("canonical_segment_id"):
        raise ValueError("WORDING_SOURCE_PROVENANCE_SOURCE_AMBIGUOUS")
    if selector_type == "TEXT_POSITION":
        if not cleaned.get("capture_id") or "start_char" not in cleaned:
            raise ValueError("WORDING_SOURCE_PROVENANCE_TEXT_POSITION_INVALID")
    if selector_type == "MEDIA_SEGMENT_REF" and not cleaned.get("canonical_segment_id"):
        raise ValueError("WORDING_SOURCE_PROVENANCE_MEDIA_SEGMENT_INVALID")
    return cleaned


def wording_contract_metadata(
    *,
    occurrence_id: str,
    source_text_sha256: str,
    normalized_claim: str,
    language: str | None,
    derivation_version: str,
    source_wording_type: WordingType = WordingType.VERBATIM_ORIGINAL,
    source_provenance: Mapping[str, Any] | None = None,
    representations: Sequence[WordingReference] = (),
) -> dict[str, Any]:
    source = make_source_occurrence_wording(
        occurrence_id=occurrence_id,
        text_sha256=source_text_sha256,
        language=language,
        derivation_version=derivation_version,
        wording_type=source_wording_type,
    )
    claim = make_normalized_claim_wording(
        occurrence_id=occurrence_id,
        normalized_claim=normalized_claim,
        language=language,
        derivation_version=derivation_version,
        source_wording_type=source_wording_type,
    )
    derived: list[dict[str, Any]] = []
    for representation in representations:
        if not isinstance(representation, WordingReference):
            raise ValueError("WORDING_REPRESENTATION_INVALID")
        if representation.wording_type not in DERIVED_WORDING_TYPES:
            raise ValueError("WORDING_REPRESENTATION_TYPE_INVALID")
        if representation.occurrence_id != occurrence_id:
            raise ValueError("WORDING_REPRESENTATION_OCCURRENCE_MISMATCH")
        if representation.source_wording_type != source_wording_type:
            raise ValueError("WORDING_REPRESENTATION_SOURCE_TYPE_MISMATCH")
        derived.append(representation.public_metadata())
    return {
        "version": WORDING_CONTRACT_VERSION,
        "source_occurrence": source.public_metadata(),
        "normalized_claim": claim.public_metadata(),
        "source_provenance": _clean_source_provenance(source_provenance),
        "representations": derived,
    }


def validate_wording_contract_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("WORDING_CONTRACT_REQUIRED")
    if str(value.get("version") or "") != WORDING_CONTRACT_VERSION:
        raise ValueError("WORDING_CONTRACT_VERSION_INVALID")
    source = value.get("source_occurrence")
    claim = value.get("normalized_claim")
    if not isinstance(source, Mapping) or not isinstance(claim, Mapping):
        raise ValueError("WORDING_CONTRACT_CHANNELS_REQUIRED")
    try:
        source_type = WordingType(str(source.get("wording_type") or ""))
    except ValueError as exc:
        raise ValueError("WORDING_SOURCE_TYPE_INVALID") from exc
    if source_type not in SOURCE_WORDING_TYPES:
        raise ValueError("WORDING_SOURCE_TYPE_INVALID")
    if str(claim.get("wording_type") or "") != WordingType.PARAPHRASE:
        raise ValueError("WORDING_NORMALIZED_CLAIM_MUST_BE_PARAPHRASE")
    expected_source_quote_authority = source_type == WordingType.VERBATIM_ORIGINAL
    if source.get("direct_quote_eligible") is not expected_source_quote_authority:
        raise ValueError("WORDING_SOURCE_DIRECT_QUOTE_AUTHORITY_INVALID")
    if str(source.get("representation_role") or "") != SOURCE_OCCURRENCE_ROLE:
        raise ValueError("WORDING_SOURCE_REPRESENTATION_ROLE_INVALID")
    if claim.get("direct_quote_eligible") is not False:
        raise ValueError("WORDING_PARAPHRASE_DIRECT_QUOTE_FORBIDDEN")
    if str(claim.get("representation_role") or "") != DERIVED_REPRESENTATION_ROLE:
        raise ValueError("WORDING_PARAPHRASE_REPRESENTATION_ROLE_INVALID")
    if str(claim.get("source_wording_type") or "") != source_type.value:
        raise ValueError("WORDING_NORMALIZED_CLAIM_SOURCE_TYPE_MISMATCH")
    source_occurrence = str(source.get("occurrence_id") or "").strip()
    claim_occurrence = str(claim.get("occurrence_id") or "").strip()
    if not source_occurrence or source_occurrence != claim_occurrence:
        raise ValueError("WORDING_OCCURRENCE_LINK_MISMATCH")
    source_hash = _validated_hash(
        str(source.get("text_sha256") or ""),
        "source_occurrence_text_sha256",
    )
    claim_hash = _validated_hash(
        str(claim.get("text_sha256") or ""),
        "normalized_claim_text_sha256",
    )
    source_method = str(source.get("derivation_method") or "").strip()
    source_version = str(source.get("derivation_version") or "").strip()
    claim_method = str(claim.get("derivation_method") or "").strip()
    claim_version = str(claim.get("derivation_version") or "").strip()
    if not source_method or not source_version or not claim_method or not claim_version:
        raise ValueError("WORDING_DERIVATION_PROVENANCE_REQUIRED")
    source_language = str(source.get("language") or "").strip() or None
    source_provenance = _clean_source_provenance(value.get("source_provenance"))
    raw_representations = value.get("representations") or []
    if not isinstance(raw_representations, list):
        raise ValueError("WORDING_REPRESENTATIONS_INVALID")
    representations: list[dict[str, Any]] = []
    for raw in raw_representations:
        if not isinstance(raw, Mapping):
            raise ValueError("WORDING_REPRESENTATION_INVALID")
        try:
            representation_type = WordingType(str(raw.get("wording_type") or ""))
        except ValueError as exc:
            raise ValueError("WORDING_REPRESENTATION_TYPE_INVALID") from exc
        if representation_type not in DERIVED_WORDING_TYPES:
            raise ValueError("WORDING_REPRESENTATION_TYPE_INVALID")
        if raw.get("direct_quote_eligible") is not False:
            raise ValueError("WORDING_DERIVED_DIRECT_QUOTE_FORBIDDEN")
        if str(raw.get("representation_role") or "") != DERIVED_REPRESENTATION_ROLE:
            raise ValueError("WORDING_DERIVED_REPRESENTATION_ROLE_INVALID")
        if str(raw.get("source_wording_type") or "") != source_type.value:
            raise ValueError("WORDING_REPRESENTATION_SOURCE_TYPE_MISMATCH")
        occurrence = str(raw.get("occurrence_id") or "").strip()
        if occurrence != source_occurrence:
            raise ValueError("WORDING_REPRESENTATION_OCCURRENCE_MISMATCH")
        method = str(raw.get("derivation_method") or "").strip()
        derivation_version = str(raw.get("derivation_version") or "").strip()
        if not method:
            raise ValueError("WORDING_DERIVATION_METHOD_REQUIRED")
        if not derivation_version:
            raise ValueError("WORDING_DERIVATION_VERSION_REQUIRED")
        representation_language = str(raw.get("language") or "").strip() or None
        representation_source_language = (
            str(raw.get("source_language") or "").strip() or None
        )
        review_state = str(raw.get("review_state") or "").strip() or None
        if representation_type == WordingType.TRANSLATION:
            if not source_language or representation_source_language != source_language:
                raise ValueError("WORDING_TRANSLATION_SOURCE_LANGUAGE_MISMATCH")
            if not representation_language:
                raise ValueError("WORDING_TRANSLATION_TARGET_LANGUAGE_REQUIRED")
            if review_state not in {state.value for state in TranslationReviewState}:
                raise ValueError("WORDING_TRANSLATION_REVIEW_STATE_REQUIRED")
        raw_signals = raw.get("signal_codes") or []
        if not isinstance(raw_signals, (list, tuple)):
            raise ValueError("WORDING_REPRESENTATION_SIGNALS_INVALID")
        representations.append(
            {
                "wording_type": representation_type.value,
                "text_sha256": _validated_hash(
                    str(raw.get("text_sha256") or ""),
                    "representation_text_sha256",
                ),
                "occurrence_id": occurrence,
                "language": representation_language,
                "derivation_method": method[:200],
                "derivation_version": derivation_version[:200],
                "source_wording_type": source_type.value,
                "source_language": representation_source_language,
                "review_state": review_state,
                "author_ref": str(raw.get("author_ref") or "").strip()[:200] or None,
                "reviewer_ref": str(raw.get("reviewer_ref") or "").strip()[:200]
                or None,
                "signal_codes": [
                    str(code).strip()[:200]
                    for code in raw_signals
                    if str(code).strip()
                ],
                "direct_quote_eligible": False,
                "representation_role": DERIVED_REPRESENTATION_ROLE,
            }
        )
    return {
        "version": WORDING_CONTRACT_VERSION,
        "source_occurrence": {
            "wording_type": source_type.value,
            "text_sha256": source_hash,
            "occurrence_id": source_occurrence,
            "language": source_language,
            "derivation_method": source_method[:200],
            "derivation_version": source_version[:200],
            "direct_quote_eligible": expected_source_quote_authority,
            "representation_role": SOURCE_OCCURRENCE_ROLE,
        },
        "normalized_claim": {
            "wording_type": WordingType.PARAPHRASE.value,
            "text_sha256": claim_hash,
            "occurrence_id": claim_occurrence,
            "language": str(claim.get("language") or "").strip() or None,
            "derivation_method": claim_method[:200],
            "derivation_version": claim_version[:200],
            "source_wording_type": source_type.value,
            "direct_quote_eligible": False,
            "representation_role": DERIVED_REPRESENTATION_ROLE,
        },
        "source_provenance": source_provenance,
        "representations": representations,
    }


def _pattern_count(patterns: dict[str, re.Pattern[str]], language: str, text: str) -> int:
    pattern = patterns.get(language.casefold())
    if pattern is None:
        # Unknown-language translations are never auto-cleared; returning zero here only
        # means this individual signal is unavailable.
        return 0
    return len(pattern.findall(text))


def _legal_categories(text: str) -> tuple[str, ...]:
    return tuple(
        category
        for category, pattern in _LEGAL_CATEGORY_PATTERNS.items()
        if pattern.search(text)
    )


def _modal_categories(language: str, text: str) -> tuple[str, ...]:
    patterns = _MODAL_CLASSES.get(language.casefold())
    if patterns is None:
        return ()
    return tuple(
        category
        for category, pattern in patterns.items()
        if pattern.search(text)
    )


def _names(text: str) -> tuple[str, ...]:
    # This is deliberately only a risk signal. It does not resolve identities.
    candidates = {
        token.casefold()
        for token in _CAPITALIZED_RE.findall(text)
        if token.casefold()
        not in {
            "il",
            "la",
            "lo",
            "un",
            "una",
            "non",
            "noi",
            "io",
            "the",
            "we",
            "i",
            "not",
            "this",
            "that",
            "if",
            "se",
        }
    }
    return tuple(sorted(candidates))


@dataclass(frozen=True)
class TranslationAssessment:
    state: TranslationReviewState
    method: str
    source_language: str
    target_language: str
    source_sha256: str
    translation_sha256: str
    signal_codes: tuple[str, ...]
    version: str = WORDING_CONTRACT_VERSION

    @property
    def public_quote_eligible(self) -> bool:
        return False


def assess_translation(
    *,
    source_text: str,
    translated_text: str,
    source_language: str,
    target_language: str,
    method: str,
    human_reviewed: bool = False,
) -> TranslationAssessment:
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()
    if not source or not translated:
        raise ValueError("WORDING_TRANSLATION_TEXT_REQUIRED")
    source_lang = str(source_language or "").strip().casefold()
    target_lang = str(target_language or "").strip().casefold()
    if not source_lang or not target_lang:
        raise ValueError("WORDING_TRANSLATION_LANGUAGE_REQUIRED")
    translation_method = str(method or "").strip().upper()
    if translation_method not in {"MACHINE", "HUMAN", "HUMAN_REVIEWED_MACHINE"}:
        raise ValueError("WORDING_TRANSLATION_METHOD_INVALID")

    signals: list[str] = []
    if tuple(_NUMBER_RE.findall(source)) != tuple(_NUMBER_RE.findall(translated)):
        signals.append("NUMBER_CHANGED")
    if tuple(_DATE_RE.findall(source)) != tuple(_DATE_RE.findall(translated)):
        signals.append("DATE_CHANGED")
    if _pattern_count(_NEGATIONS, source_lang, source) != _pattern_count(
        _NEGATIONS, target_lang, translated
    ):
        signals.append("NEGATION_CHANGED")
    if (
        _pattern_count(_MODALS, source_lang, source)
        != _pattern_count(_MODALS, target_lang, translated)
        or _modal_categories(source_lang, source)
        != _modal_categories(target_lang, translated)
    ):
        signals.append("MODALITY_CHANGED")
    if _legal_categories(source) != _legal_categories(translated):
        signals.append("LEGAL_STATUS_TERM_CHANGED")
    source_names = _names(source)
    translated_names = _names(translated)
    if source_names and source_names != translated_names:
        signals.append("PROPER_NAME_CHANGED")
    if source_lang not in _NEGATIONS or target_lang not in _NEGATIONS:
        signals.append("LANGUAGE_RISK_RULE_UNAVAILABLE")
    if translation_method == "MACHINE" and not human_reviewed:
        signals.append("MACHINE_TRANSLATION_REQUIRES_REVIEW")

    state = (
        TranslationReviewState.HUMAN_REVIEWED
        if human_reviewed and not signals
        else TranslationReviewState.NEEDS_REVIEW
    )
    return TranslationAssessment(
        state=state,
        method=translation_method,
        source_language=source_lang,
        target_language=target_lang,
        source_sha256=_sha256(source),
        translation_sha256=_sha256(translated),
        signal_codes=tuple(dict.fromkeys(signals)),
    )


def make_translation_wording(
    *,
    occurrence_id: str,
    source_text: str,
    translated_text: str,
    source_wording_type: WordingType,
    source_language: str,
    target_language: str,
    method: str,
    derivation_version: str,
    human_reviewed: bool = False,
    author_ref: str | None = None,
    reviewer_ref: str | None = None,
) -> WordingReference:
    assessment = assess_translation(
        source_text=source_text,
        translated_text=translated_text,
        source_language=source_language,
        target_language=target_language,
        method=method,
        human_reviewed=human_reviewed,
    )
    return make_derived_wording(
        wording_type=WordingType.TRANSLATION,
        occurrence_id=occurrence_id,
        text=translated_text,
        source_wording_type=source_wording_type,
        source_language=assessment.source_language,
        language=assessment.target_language,
        derivation_method=f"TRANSLATION_{assessment.method}",
        derivation_version=derivation_version,
        review_state=assessment.state.value,
        author_ref=author_ref,
        reviewer_ref=reviewer_ref,
        signal_codes=assessment.signal_codes,
    )


def assert_direct_quote_eligible(wording: WordingReference) -> None:
    if not wording.direct_quote_eligible:
        raise ValueError(
            f"WORDING_DIRECT_QUOTE_FORBIDDEN:{wording.wording_type.value}"
        )


__all__ = [
    "DERIVED_REPRESENTATION_ROLE",
    "DERIVED_WORDING_TYPES",
    "SOURCE_OCCURRENCE_ROLE",
    "SOURCE_WORDING_TYPES",
    "TranslationAssessment",
    "TranslationReviewState",
    "WORDING_CONTRACT_VERSION",
    "WordingReference",
    "WordingType",
    "assert_direct_quote_eligible",
    "assess_translation",
    "make_derived_wording",
    "make_normalized_claim_wording",
    "make_source_occurrence_wording",
    "make_summary_wording",
    "make_translation_wording",
    "wording_contract_metadata",
    "validate_wording_contract_metadata",
]
