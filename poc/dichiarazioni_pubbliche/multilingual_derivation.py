"""DP-239 private, immutable original→machine-translation candidates.

Lexical checks flag possible mistakes; even a clean German/Italian synthetic pair
is not independently meaning-verified. Callers own provenance authentication,
PARSE/TRANSLATE use rights, review, retention, and persistence. No provider runs.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
    deterministic_corpus_id,
)
from dichiarazioni_pubbliche.original_source_resolver import (
    ExactSourceLocator,
    ObservedMediaSegment,
    resolve_exact_source_locator,
)
from dichiarazioni_pubbliche.wording_contract import (
    TranslationReviewState,
    WordingReference,
    WordingType,
    make_derived_wording,
)


MULTILINGUAL_DERIVATION_VERSION = "private-multilingual-derivation-v1"
GERMAN_ITALIAN_RISK_VERSION = "de-it-critical-lexemes-v1"
MAX_SPAN_CHARS = 8_192
MAX_ACTORS = 16
_BCP47 = re.compile(r"^(?:[A-Za-z]{2,3}|und)(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|[0-9]{3}))?(?:-[A-Za-z0-9]{5,8})*$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_DATE = re.compile(r"(?<!\w)(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})(?!\w)")
_NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*%?(?!\w)")
_MONTH_WORDS = re.compile(r"\b(?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember|gennaio|febbraio|marzo|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", re.I)
_NEGATIONS = {
    "de": re.compile(r"\b(?:nicht|nie|niemals|kein(?:e[rsnm]?)?|ohne|weder)\b", re.I),
    "it": re.compile(r"\b(?:non|mai|nessun(?:o|a)?|senza|né)\b", re.I),
}
_MODALS = {
    "de": {
        "OBLIGATION": re.compile(r"\b(?:muss|muß|müssen|musste|soll|sollen|sollte)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:kann|können|könnte|könnten)\b", re.I),
        "PERMISSION": re.compile(r"\b(?:darf|dürfen|durfte)\b", re.I),
    },
    "it": {
        "OBLIGATION": re.compile(r"\b(?:deve|devono|dovrebbe|dovrebbero|bisogna)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:può|possono|potrebbe|potrebbero)\b", re.I),
        "PERMISSION": re.compile(r"\b(?:è\s+consentito|è\s+permesso|ha\s+il\s+permesso)\b", re.I),
    },
}
_LEGAL = {
    "de": {
        "INVESTIGATED": re.compile(r"\b(?:ermittelt|verdächtig(?:t|te|ten)|beschuldigt)\b", re.I),
        "DEFENDANT": re.compile(r"\b(?:angeklagt|angeschuldigt)\b", re.I),
        "CONVICTED": re.compile(r"\b(?:verurteilt)\b", re.I),
        "ACQUITTED": re.compile(r"\b(?:freigesprochen)\b", re.I),
        "CASE_DISMISSED": re.compile(r"\b(?:eingestellt)\b", re.I),
    },
    "it": {
        "INVESTIGATED": re.compile(r"\b(?:indagat[oa]|sospettat[oa])\b", re.I),
        "DEFENDANT": re.compile(r"\b(?:imputat[oa])\b", re.I),
        "CONVICTED": re.compile(r"\b(?:condannat[oa])\b", re.I),
        "ACQUITTED": re.compile(r"\b(?:assolt[oa])\b", re.I),
        "CASE_DISMISSED": re.compile(r"\b(?:archiviat[oa])\b", re.I),
    },
}
_REPORTED = {
    "de": re.compile(r"\b(?:sagte|sagten|berichtete|laut|zufolge|zitierte|behauptete)\b", re.I),
    "it": re.compile(r"\b(?:secondo|ha\s+detto|disse|riportò|riferì|ha\s+citato|ha\s+sostenuto|sostiene|afferma)\b", re.I),
}
_QUOTES = re.compile(r'["„“«»]')


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required(value: str, field: str, limit: int = 180) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > limit:
        raise ValueError(f"DP239_{field}_INVALID")
    return value


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"DP239_{field}_INVALID")
    return value


def _language(value: str, field: str) -> str:
    if not isinstance(value, str) or not _BCP47.fullmatch(value):
        raise ValueError(f"DP239_{field}_BCP47_INVALID")
    parts = value.split("-")
    canonical = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            canonical.append(part.title())
        elif len(part) == 2 and part.isalpha():
            canonical.append(part.upper())
        else:
            canonical.append(part.lower())
    return "-".join(canonical)


def _base(value: str) -> str:
    return value.split("-", 1)[0]


def _tag_script(value: str) -> str | None:
    return next((part for part in value.split("-")[1:] if len(part) == 4 and part.isalpha()), None)


def _scripts(text: str) -> tuple[str, ...]:
    observed: set[str] = set()
    names = (
        ("LATIN", "Latn"), ("CYRILLIC", "Cyrl"), ("GREEK", "Grek"),
        ("ARABIC", "Arab"), ("HEBREW", "Hebr"), ("DEVANAGARI", "Deva"),
        ("HIRAGANA", "Hira"), ("KATAKANA", "Kana"), ("HANGUL", "Hang"),
        ("CJK UNIFIED", "Hani"),
    )
    for char in text:
        if unicodedata.category(char).startswith("L"):
            label = unicodedata.name(char, "")
            script = next((tag for name, tag in names if name in label), "Zzzz")
            observed.add(script)
    return tuple(sorted(observed))


@dataclass(frozen=True)
class CodeSwitchSpan:
    """Coordinates are relative to the bounded source quote, not the whole file."""

    start_char: int
    end_char: int
    language: str


@dataclass(frozen=True)
class ActorAnchor:
    """A pinned string in the original; not an identity or grammatical verdict."""

    actor_ref: str
    source_surface: str


@dataclass(frozen=True)
class ImmutableOriginalSpan:
    content_id: str
    capture_id: str | None
    passage_id: str
    selector_type: str
    locator_fingerprint: str
    source_version_sha256: str
    extraction_method: str
    extraction_version: str
    original_charset: str | None
    transcript_variant_id: str | None
    source_text: str
    quote_sha256: str
    quote_start: int
    quote_end: int
    source_wording_type: WordingType
    speaker_person_id: str | None
    speaker_binding_state: str  # UNVERIFIED; the resolver cannot approve identity
    language: str
    language_origin: str
    scripts: tuple[str, ...]
    code_switch_spans: tuple[CodeSwitchSpan, ...]


@dataclass(frozen=True)
class PrivateTranslationDerivation:
    id: str
    original: ImmutableOriginalSpan
    translated_text: str
    translated_text_sha256: str
    target_language: str
    target_scripts: tuple[str, ...]
    method: str
    provider_id: str
    model_id: str
    model_version: str
    prompt_sha256: str
    config_sha256: str
    derivation_version: str
    signal_codes: tuple[str, ...]
    actor_anchors: tuple[ActorAnchor, ...]
    wording: WordingReference
    review_state: TranslationReviewState = TranslationReviewState.NEEDS_REVIEW
    status: str = "HELD"
    rule_version: str = GERMAN_ITALIAN_RISK_VERSION
    version: str = MULTILINGUAL_DERIVATION_VERSION

    @property
    def public_quote_eligible(self) -> bool:
        return False


@dataclass(frozen=True)
class DerivationRecheck:
    status: str  # CURRENT, STALE, BLOCKED; never a promotion decision
    reason_codes: tuple[str, ...]


def _dates_and_numbers(text: str) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    parsed_dates: list[str] = []
    for match in _DATE.finditer(text):
        value = match.group()
        try:
            if value[4:5] == "-":
                year, month, day = [int(x) for x in value.split("-")]
            else:
                day, month, year = [int(x) for x in re.split(r"[./-]", value)]
            parsed_dates.append(date(year, month, day).isoformat())
        except ValueError:
            parsed_dates.append("INVALID_DATE:" + value)
    without_dates = _DATE.sub(" ", text)
    numbers = tuple("".join(x for x in token if x.isdecimal()) + ("%" if token.endswith("%") else "") for token in _NUMBER.findall(without_dates))
    ambiguity = bool(_MONTH_WORDS.search(text))
    return tuple(parsed_dates), numbers, ambiguity


def _lexemes(text: str, language: str, patterns: dict[str, dict[str, re.Pattern[str]]]) -> tuple[str, ...]:
    return tuple(sorted(category for category, pattern in patterns[language].items()
                        for _ in pattern.finditer(text)))


def _anchor_position(text: str, surface: str) -> int:
    # Unicode-aware word boundaries prevent Anna matching Annabella. Do not
    # translate/transliterate proper names without qualified review.
    matches = list(re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text, re.I))
    return matches[0].start() if len(matches) == 1 else -1


def _risk_de_it(original: str, translated: str, anchors: tuple[ActorAnchor, ...],
                source_wording_type: WordingType) -> tuple[str, ...]:
    codes: list[str] = []
    source_dates, source_numbers, source_ambiguous = _dates_and_numbers(original)
    target_dates, target_numbers, target_ambiguous = _dates_and_numbers(translated)
    if source_dates != target_dates:
        codes.append("DATE_MISMATCH")
    if source_ambiguous or target_ambiguous or any(x.startswith("INVALID_DATE:") for x in source_dates + target_dates):
        codes.append("DATE_UNPARSED_OR_AMBIGUOUS")
    if source_numbers != target_numbers:
        codes.append("NUMBER_MISMATCH")
    # Lexical cardinality checks cannot independently confirm polarity scope.
    source_neg = _NEGATIONS["de"].findall(original)
    target_neg = _NEGATIONS["it"].findall(translated)
    if len(source_neg) != len(target_neg):
        codes.append("NEGATION_MISMATCH")
    if source_neg or target_neg:
        codes.append("NEGATION_SCOPE_UNVERIFIED")
    if _lexemes(original, "de", _MODALS) != _lexemes(translated, "it", _MODALS):
        codes.append("MODALITY_MISMATCH")
    if _lexemes(original, "de", _LEGAL) != _lexemes(translated, "it", _LEGAL):
        codes.append("JUDICIAL_STATUS_MISMATCH")
    if bool(_REPORTED["de"].search(original)) != bool(_REPORTED["it"].search(translated)):
        codes.append("REPORTED_SPEECH_MISMATCH")
    if bool(_QUOTES.search(original)) != bool(_QUOTES.search(translated)):
        codes.append("QUOTE_MARKER_MISMATCH")
    if source_wording_type == WordingType.REPORTED_QUOTE:
        codes.append("QUOTED_SPEAKER_ENDORSEMENT_UNVERIFIED")
    if not anchors:
        codes.append("ACTOR_BINDING_UNVERIFIED")
    else:
        source_positions = [_anchor_position(original, row.source_surface) for row in anchors]
        target_positions = [_anchor_position(translated, row.source_surface) for row in anchors]
        if -1 in source_positions:
            raise ValueError("DP239_SOURCE_ACTOR_ANCHOR_MISSING_OR_AMBIGUOUS")
        if -1 in target_positions:
            codes.append("ACTOR_ANCHOR_CHANGED")
        elif sorted(range(len(anchors)), key=source_positions.__getitem__) != sorted(
                range(len(anchors)), key=target_positions.__getitem__):
            codes.append("ACTOR_ORDER_CHANGED")
        # Mention order is a warning, never grammatical subject assurance.
        codes.append("ACTOR_GRAMMATICAL_ROLE_UNVERIFIED")
    return tuple(codes)


def _switches(spans: tuple[CodeSwitchSpan, ...], source: str) -> tuple[CodeSwitchSpan, ...]:
    if len(spans) > 32 or any(not isinstance(row, CodeSwitchSpan) for row in spans):
        raise ValueError("DP239_CODE_SWITCH_INVALID")
    cursor = 0
    canonical: list[CodeSwitchSpan] = []
    for row in spans:
        if type(row.start_char) is not int or type(row.end_char) is not int or row.start_char != cursor or not row.start_char < row.end_char <= len(source):
            raise ValueError("DP239_CODE_SWITCH_DISCONTINUOUS")
        canonical.append(CodeSwitchSpan(row.start_char, row.end_char, _language(row.language, "SWITCH_LANGUAGE")))
        cursor = row.end_char
    if spans and cursor != len(source):
        raise ValueError("DP239_CODE_SWITCH_DISCONTINUOUS")
    return tuple(canonical)


def build_private_translation(
    *, locator: ExactSourceLocator, passage: PassageRecord, source_text: str,
    translated_text: str, source_language: str, target_language: str,
    language_origin: str, provider_id: str, model_id: str, model_version: str,
    prompt_sha256: str, config_sha256: str, derivation_version: str,
    source_wording_type: WordingType,
    capture: ContentCaptureRecord | None = None, source_body: bytes | None = None,
    canonical_text: str | None = None, page_text: str | None = None,
    media_segment: ObservedMediaSegment | None = None,
    current_source_sha256: str | None = None,
    code_switch_spans: tuple[CodeSwitchSpan, ...] = (),
    actor_anchors: tuple[ActorAnchor, ...] = (),
) -> PrivateTranslationDerivation:
    """Build a held, private machine draft from a DP-237 verified exact selector.

    Callers must independently authenticate parser and language provenance,
    speaker review, and derivative-use rights. These are NEVER synthesized here.
    """
    if (not isinstance(source_text, str) or not source_text.strip()
            or source_text != source_text.strip() or len(source_text) > MAX_SPAN_CHARS
            or not isinstance(translated_text, str) or not translated_text.strip()
            or translated_text != translated_text.strip() or len(translated_text) > MAX_SPAN_CHARS):
        raise ValueError("DP239_TEXT_INVALID_OR_OVERSIZE")
    for name, value in (("PROVIDER", provider_id), ("MODEL", model_id),
                        ("MODEL_VERSION", model_version), ("DERIVATION_VERSION", derivation_version)):
        _required(value, name)
    _digest(prompt_sha256, "PROMPT_SHA256")
    _digest(config_sha256, "CONFIG_SHA256")
    if not isinstance(source_wording_type, WordingType) or source_wording_type not in {
            WordingType.VERBATIM_ORIGINAL, WordingType.REPORTED_QUOTE}:
        raise ValueError("DP239_SOURCE_WORDING_TYPE_INVALID")
    source_lang, target_lang = _language(source_language, "SOURCE_LANGUAGE"), _language(target_language, "TARGET_LANGUAGE")
    if language_origin not in {"SOURCE_DECLARED", "INFERRED_UNREVIEWED", "UNKNOWN", "MIXED_DECLARED"}:
        raise ValueError("DP239_LANGUAGE_ORIGIN_INVALID")
    if passage.language and _language(passage.language, "PASSAGE_LANGUAGE") != source_lang:
        raise ValueError("DP239_PASSAGE_LANGUAGE_CONFLICT")
    switches = _switches(tuple(code_switch_spans), source_text)
    anchors = tuple(actor_anchors)
    if len(anchors) > MAX_ACTORS or any(not isinstance(a, ActorAnchor) for a in anchors):
        raise ValueError("DP239_ACTOR_ANCHORS_INVALID")
    if len({a.actor_ref for a in anchors}) != len(anchors):
        raise ValueError("DP239_ACTOR_ANCHOR_DUPLICATE")
    for a in anchors:
        _required(a.actor_ref, "ACTOR_REF")
        _required(a.source_surface, "ACTOR_SURFACE", 100)
        if _anchor_position(source_text, a.source_surface) < 0:
            raise ValueError("DP239_SOURCE_ACTOR_ANCHOR_MISSING_OR_AMBIGUOUS")

    result = resolve_exact_source_locator(
        locator, passage=passage, quote_text=source_text, capture=capture,
        source_body=source_body, canonical_text=canonical_text,
        page_text=page_text, media_segment=media_segment,
        current_source_sha256=current_source_sha256,
    )
    if result.status != "LOCATED" or not result.locator_fingerprint or not result.source_version_sha256:
        raise ValueError("DP239_ORIGINAL_LOCATOR_" + (result.blockers[0] if result.blockers else result.status))
    scripts, target_scripts = _scripts(source_text), _scripts(translated_text)
    codes: list[str] = ["INDEPENDENT_MEANING_ASSURANCE_REQUIRED", "DERIVATIVE_USE_RIGHTS_UNVERIFIED"]
    if language_origin == "SOURCE_DECLARED":
        codes.append("SOURCE_LANGUAGE_IDENTIFICATION_UNVERIFIED")
    if not passage.language:
        codes.append("SOURCE_LANGUAGE_UNBOUND_TO_PASSAGE")
    if language_origin != "SOURCE_DECLARED" or source_lang == "und" or target_lang == "und":
        codes.append("SOURCE_LANGUAGE_UNKNOWN_OR_UNVERIFIED")
    if switches or language_origin == "MIXED_DECLARED":
        codes.append("CODE_SWITCH_UNRESOLVED")
    if len(scripts) != 1 or len(target_scripts) != 1 or "Zzzz" in scripts + target_scripts:
        codes.append("SCRIPT_UNKNOWN_OR_MIXED")
    source_script_valid = _tag_script(source_lang) is None or scripts == (_tag_script(source_lang),)
    target_script_valid = _tag_script(target_lang) is None or target_scripts == (_tag_script(target_lang),)
    if not source_script_valid:
        codes.append("SOURCE_SCRIPT_MISMATCH")
    if not target_script_valid:
        codes.append("TARGET_SCRIPT_MISMATCH")
    if _base(source_lang) in {"de", "it"} and scripts != ("Latn",):
        codes.append("SOURCE_SCRIPT_MISMATCH")
    if _base(target_lang) == "it" and target_scripts != ("Latn",):
        codes.append("TARGET_SCRIPT_MISMATCH")
    if (_base(source_lang) == "de" and _base(target_lang) == "it" and not switches
            and language_origin == "SOURCE_DECLARED" and scripts == ("Latn",)
            and target_scripts == ("Latn",) and source_script_valid and target_script_valid):
        codes.extend(_risk_de_it(source_text, translated_text, anchors, source_wording_type))
    else:
        codes.append("LANGUAGE_PAIR_RISK_RULE_UNAVAILABLE")
    if locator.selector_type == "MEDIA_SEGMENT_REF":
        codes.append("SPEAKER_REVIEW_AUTHORITY_UNVERIFIED")
        if not locator.speaker_person_id:
            codes.append("SPEAKER_BINDING_MISSING")
    binding = ImmutableOriginalSpan(
        content_id=locator.content_id,
        capture_id=locator.capture_id,
        passage_id=locator.passage_id,
        selector_type=locator.selector_type,
        locator_fingerprint=result.locator_fingerprint,
        source_version_sha256=result.source_version_sha256,
        extraction_method=passage.extraction_method,
        extraction_version=passage.extraction_version,
        original_charset=(capture.metadata.get("response_charset")
                          if capture is not None and isinstance(capture.metadata.get("response_charset"), str)
                          else None),
        transcript_variant_id=locator.transcript_variant_id,
        source_text=source_text,
        quote_sha256=locator.quote_sha256,
        quote_start=locator.quote_start,
        quote_end=locator.quote_end,
        source_wording_type=source_wording_type,
        speaker_person_id=locator.speaker_person_id if locator.selector_type == "MEDIA_SEGMENT_REF" else None,
        speaker_binding_state="UNVERIFIED",
        language=source_lang,
        language_origin=language_origin,
        scripts=scripts,
        code_switch_spans=switches,
    )
    wording = make_derived_wording(
        wording_type=WordingType.TRANSLATION, occurrence_id=locator.passage_id,
        text=translated_text, source_wording_type=source_wording_type,
        language=target_lang, source_language=source_lang,
        derivation_method="TRANSLATION_MACHINE",
        derivation_version=derivation_version,
        review_state=TranslationReviewState.NEEDS_REVIEW.value,
        signal_codes=tuple(dict.fromkeys(codes)),
    )
    identity = json.dumps({
        "contract": MULTILINGUAL_DERIVATION_VERSION,
        "locator": result.locator_fingerprint,
        "source": result.source_version_sha256,
        "source_wording_type": source_wording_type.value,
        "extraction_method": passage.extraction_method,
        "extraction_version": passage.extraction_version,
        "original_charset": binding.original_charset,
        "source_lang": source_lang, "target_lang": target_lang,
        "language_origin": language_origin,
        "code_switch": [(s.start_char, s.end_char, s.language) for s in switches],
        "actors": [(a.actor_ref, a.source_surface) for a in anchors],
        "provider": provider_id, "model": model_id, "model_version": model_version,
        "prompt": prompt_sha256, "config": config_sha256,
        "derivation_version": derivation_version, "translated_sha256": _hash(translated_text),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return PrivateTranslationDerivation(
        id=deterministic_corpus_id("translation", identity),
        original=binding, translated_text=translated_text,
        translated_text_sha256=_hash(translated_text),
        target_language=target_lang, target_scripts=target_scripts,
        method="MACHINE", provider_id=provider_id, model_id=model_id,
        model_version=model_version, prompt_sha256=prompt_sha256,
        config_sha256=config_sha256, derivation_version=derivation_version,
        signal_codes=tuple(dict.fromkeys(codes)), actor_anchors=anchors,
        wording=wording,
    )


def recheck_private_translation(
    derived: PrivateTranslationDerivation, *,
    locator: ExactSourceLocator, passage: PassageRecord,
    capture: ContentCaptureRecord | None = None, source_body: bytes | None = None,
    canonical_text: str | None = None, page_text: str | None = None,
    media_segment: ObservedMediaSegment | None = None,
    current_source_sha256: str | None = None,
) -> DerivationRecheck:
    """Read-only drift check, never silently updates original/translation text."""
    original = derived.original
    resolution = resolve_exact_source_locator(
        locator, passage=passage, quote_text=original.source_text,
        capture=capture, source_body=source_body, canonical_text=canonical_text,
        page_text=page_text, media_segment=media_segment,
        current_source_sha256=current_source_sha256,
    )
    if resolution.status == "STALE":
        return DerivationRecheck("STALE", resolution.blockers)
    if (resolution.status != "LOCATED" or resolution.locator_fingerprint != original.locator_fingerprint
            or resolution.source_version_sha256 != original.source_version_sha256
            or passage.extraction_method != original.extraction_method
            or passage.extraction_version != original.extraction_version
            or (capture.metadata.get("response_charset") if capture is not None else None) != original.original_charset):
        return DerivationRecheck("BLOCKED", resolution.blockers or ("TRANSLATION_ORIGINAL_BINDING_CHANGED",))
    return DerivationRecheck("CURRENT", ())


__all__ = [
    "ActorAnchor", "CodeSwitchSpan", "DerivationRecheck", "GERMAN_ITALIAN_RISK_VERSION",
    "ImmutableOriginalSpan", "MULTILINGUAL_DERIVATION_VERSION",
    "PrivateTranslationDerivation", "build_private_translation", "recheck_private_translation",
]
