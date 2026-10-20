from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


CONTEXT_INTEGRITY_VERSION = "context-integrity-v1"
CLEAR_STATES = frozenset({"CLEAR_AUTOMATIC", "APPROVED_CURATED"})

_NEGATION_RE = re.compile(r"\b(?:non|mai|nessun[oa]?|senza)\b", re.I)
_CONDITIONAL_RE = re.compile(
    r"\b(?:se|qualora|ipoteticamente|supponendo|supponiamo|nel caso|a condizione che)\b",
    re.I,
)
_QUALIFICATION_RE = re.compile(
    r"^[\s,;:—–-]*(?:ma|però|tuttavia|anche se|salvo|tranne|eccetto|"
    r"in realtà|preciso che|correggo)\b",
    re.I,
)
_DEPENDENT_PRONOUN_RE = re.compile(
    r"^(?:lui|lei|loro|esso|essa|essi|esse|questo|questa|quello|quella|"
    r"ciò|lo|la|li|le)\b",
    re.I,
)
_SHORT_ANSWER_RE = re.compile(
    r"^(?:sì|si|no|certo|esatto|assolutamente|mai)\b",
    re.I,
)
_SENTENCE_BOUNDARY = frozenset(".!?;:\n")


@dataclass(frozen=True)
class ContextIntegrityAssessment:
    state: str
    source_sha256: str
    quote_sha256: str
    quote_start: int
    quote_end: int
    context_start: int
    context_end: int
    context_sha256: str
    signal_codes: tuple[str, ...]
    version: str = CONTEXT_INTEGRITY_VERSION

    @property
    def clear(self) -> bool:
        return self.state in CLEAR_STATES

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredContextSpan:
    start_char: int
    end_char: int
    text_sha256: str
    speaker_ref: str | None = None
    source_part_ref: str | None = None


@dataclass(frozen=True)
class StructuredContextIntegrityAssessment:
    state: str
    source_sha256: str
    binding_sha256: str
    spans: tuple[StructuredContextSpan, ...]
    omission_count: int
    signal_codes: tuple[str, ...]
    version: str = CONTEXT_INTEGRITY_VERSION

    @property
    def clear(self) -> bool:
        return self.state in CLEAR_STATES

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_value(value: object, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"CONTEXT_{field}_INVALID")
    return text


def structured_context_binding_sha256(
    *,
    source_sha256: str,
    spans: Sequence[StructuredContextSpan],
    omission_count: int,
    signal_codes: Sequence[str],
    version: str = CONTEXT_INTEGRITY_VERSION,
) -> str:
    """Compute the canonical v1 binding for one structured context receipt."""

    source_hash = _sha256_value(source_sha256, "SOURCE_SHA256")
    if version != CONTEXT_INTEGRITY_VERSION:
        raise ValueError("CONTEXT_STRUCTURED_VERSION_INVALID")
    if len(spans) < 2:
        raise ValueError("CONTEXT_STRUCTURED_MULTIPLE_SPANS_REQUIRED")
    if omission_count != len(spans) - 1:
        raise ValueError("CONTEXT_STRUCTURED_OMISSION_COUNT_INVALID")
    material = {
        "source_sha256": source_hash,
        "spans": [asdict(row) for row in spans],
        "omission_count": omission_count,
        "signal_codes": list(signal_codes),
        "version": version,
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def verify_structured_context_integrity_metadata(
    metadata: Mapping[str, object],
) -> StructuredContextIntegrityAssessment:
    """Validate and rebind a persisted structured context-integrity v1 receipt."""

    if not isinstance(metadata, Mapping):
        raise ValueError("CONTEXT_STRUCTURED_METADATA_INVALID")
    version = str(metadata.get("version") or "")
    if version != CONTEXT_INTEGRITY_VERSION:
        raise ValueError("CONTEXT_STRUCTURED_VERSION_INVALID")
    source_hash = _sha256_value(metadata.get("source_sha256"), "SOURCE_SHA256")
    binding_hash = _sha256_value(metadata.get("binding_sha256"), "BINDING_SHA256")
    raw_spans = metadata.get("spans")
    if not isinstance(raw_spans, (list, tuple)) or len(raw_spans) < 2:
        raise ValueError("CONTEXT_STRUCTURED_MULTIPLE_SPANS_REQUIRED")

    rows: list[StructuredContextSpan] = []
    previous_end: int | None = None
    for raw_span in raw_spans:
        if not isinstance(raw_span, Mapping):
            raise ValueError("CONTEXT_STRUCTURED_SPAN_INVALID")
        start = raw_span.get("start_char")
        end = raw_span.get("end_char")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
        ):
            raise ValueError("CONTEXT_STRUCTURED_SPAN_INVALID")
        if previous_end is not None and start <= previous_end:
            raise ValueError("CONTEXT_STRUCTURED_SPAN_ORDER_INVALID")
        speaker_ref = raw_span.get("speaker_ref")
        source_part_ref = raw_span.get("source_part_ref")
        if speaker_ref is not None and not isinstance(speaker_ref, str):
            raise ValueError("CONTEXT_STRUCTURED_SPEAKER_REF_INVALID")
        if source_part_ref is not None and not isinstance(source_part_ref, str):
            raise ValueError("CONTEXT_STRUCTURED_SOURCE_PART_REF_INVALID")
        rows.append(
            StructuredContextSpan(
                start_char=start,
                end_char=end,
                text_sha256=_sha256_value(raw_span.get("text_sha256"), "SPAN_SHA256"),
                speaker_ref=speaker_ref.strip() or None if speaker_ref is not None else None,
                source_part_ref=(
                    source_part_ref.strip() or None if source_part_ref is not None else None
                ),
            )
        )
        previous_end = end

    omission_count = metadata.get("omission_count")
    if (
        not isinstance(omission_count, int)
        or isinstance(omission_count, bool)
        or omission_count != len(rows) - 1
    ):
        raise ValueError("CONTEXT_STRUCTURED_OMISSION_COUNT_INVALID")
    raw_signal_codes = metadata.get("signal_codes")
    if not isinstance(raw_signal_codes, (list, tuple)) or any(
        not isinstance(code, str) or not code for code in raw_signal_codes
    ):
        raise ValueError("CONTEXT_STRUCTURED_SIGNAL_CODES_INVALID")
    signal_codes = tuple(raw_signal_codes)
    expected_binding = structured_context_binding_sha256(
        source_sha256=source_hash,
        spans=rows,
        omission_count=omission_count,
        signal_codes=signal_codes,
        version=version,
    )
    if binding_hash != expected_binding:
        raise ValueError("CONTEXT_STRUCTURED_BINDING_MISMATCH")
    return StructuredContextIntegrityAssessment(
        state=str(metadata.get("state") or ""),
        source_sha256=source_hash,
        binding_sha256=binding_hash,
        spans=tuple(rows),
        omission_count=omission_count,
        signal_codes=signal_codes,
        version=version,
    )


def assess_context_integrity(
    *,
    source_text: str,
    source_sha256: str,
    quote_start: int,
    quote_end: int,
    speech_mode: str = "DIRECT_UTTERANCE",
    window_radius: int = 240,
) -> ContextIntegrityAssessment:
    text = str(source_text or "")
    expected_source_hash = str(source_sha256 or "").strip().lower()
    if len(expected_source_hash) != 64 or _sha256(text) != expected_source_hash:
        raise ValueError("CONTEXT_SOURCE_HASH_MISMATCH")
    start = int(quote_start)
    end = int(quote_end)
    if start < 0 or end <= start or end > len(text):
        raise ValueError("CONTEXT_QUOTE_RANGE_INVALID")
    if not 32 <= int(window_radius) <= 2000:
        raise ValueError("CONTEXT_WINDOW_RADIUS_INVALID")

    quote = text[start:end]
    left_start = max(0, start - int(window_radius))
    right_end = min(len(text), end + int(window_radius))
    left = text[left_start:start]
    right = text[end:right_end]
    window = text[left_start:right_end]
    signals: list[str] = []

    if str(speech_mode or "DIRECT_UTTERANCE") != "DIRECT_UTTERANCE":
        signals.append("NON_DIRECT_SPEECH_MODE")

    normalized_quote = quote.strip()
    if _CONDITIONAL_RE.search(normalized_quote):
        signals.append("CONDITIONAL_OR_HYPOTHETICAL")
    if "..." in normalized_quote or "…" in normalized_quote or "[...]" in normalized_quote:
        signals.append("ELLIPSIS_OR_OMISSION_MARKER")

    immediate_left = left[-40:]
    immediate_right = right[:100]
    if not _NEGATION_RE.search(normalized_quote):
        if _NEGATION_RE.search(immediate_left) or _NEGATION_RE.search(immediate_right[:40]):
            signals.append("NEGATION_NEAR_BOUNDARY_OMITTED")
    if immediate_right and _QUALIFICATION_RE.search(immediate_right):
        signals.append("IMMEDIATE_QUALIFICATION_OMITTED")

    if start > 0:
        prior = text[start - 1]
        if prior not in _SENTENCE_BOUNDARY and not prior.isspace():
            signals.append("INCOMPLETE_LEFT_BOUNDARY")
        elif left.rstrip() and left.rstrip()[-1] not in _SENTENCE_BOUNDARY:
            signals.append("INCOMPLETE_LEFT_CONTEXT")
    if end < len(text):
        following = text[end]
        if following not in _SENTENCE_BOUNDARY and not following.isspace():
            signals.append("INCOMPLETE_RIGHT_BOUNDARY")
        elif right.lstrip() and right.lstrip()[0] not in _SENTENCE_BOUNDARY:
            signals.append("INCOMPLETE_RIGHT_CONTEXT")

    if _DEPENDENT_PRONOUN_RE.search(normalized_quote) and left.strip():
        signals.append("ANTECEDENT_DEPENDENT_PRONOUN")
    if _SHORT_ANSWER_RE.search(normalized_quote):
        if "?" in left or len(normalized_quote.split()) <= 4:
            signals.append("ANSWER_REQUIRES_QUESTION_CONTEXT")

    ordered = tuple(dict.fromkeys(signals))
    return ContextIntegrityAssessment(
        state="CLEAR_AUTOMATIC" if not ordered else "NEEDS_CONTEXT_REVIEW",
        source_sha256=expected_source_hash,
        quote_sha256=_sha256(quote),
        quote_start=start,
        quote_end=end,
        context_start=left_start,
        context_end=right_end,
        context_sha256=_sha256(window),
        signal_codes=ordered,
    )


def assess_structured_context_integrity(
    *,
    source_text: str,
    source_sha256: str,
    spans: Sequence[tuple[int, int]],
    speaker_refs: Sequence[str | None] = (),
    source_part_refs: Sequence[str | None] = (),
) -> StructuredContextIntegrityAssessment:
    """Bind discontinuous context to every source span without storing source text.

    Discontinuous excerpts always require explicit review. Different speaker refs expose
    cross-talk/interruption boundaries, and different source-part refs expose montage or
    embedded-source boundaries. Both cases stay held instead of inheriting context from
    a neighboring span.
    """

    text = str(source_text or "")
    expected_source_hash = str(source_sha256 or "").strip().lower()
    if len(expected_source_hash) != 64 or _sha256(text) != expected_source_hash:
        raise ValueError("CONTEXT_SOURCE_HASH_MISMATCH")
    if len(spans) < 2:
        raise ValueError("CONTEXT_STRUCTURED_MULTIPLE_SPANS_REQUIRED")
    if speaker_refs and len(speaker_refs) != len(spans):
        raise ValueError("CONTEXT_STRUCTURED_SPEAKER_COUNT_MISMATCH")
    if source_part_refs and len(source_part_refs) != len(spans):
        raise ValueError("CONTEXT_STRUCTURED_SOURCE_PART_COUNT_MISMATCH")

    rows: list[StructuredContextSpan] = []
    previous_end: int | None = None
    signals: list[str] = ["DISCONTINUOUS_EXCERPT_REQUIRES_REVIEW"]
    for index, (raw_start, raw_end) in enumerate(spans):
        start = int(raw_start)
        end = int(raw_end)
        if start < 0 or end <= start or end > len(text):
            raise ValueError("CONTEXT_STRUCTURED_SPAN_INVALID")
        if previous_end is not None and start <= previous_end:
            raise ValueError("CONTEXT_STRUCTURED_SPAN_ORDER_INVALID")
        raw_speaker = speaker_refs[index] if speaker_refs else None
        raw_source_part = source_part_refs[index] if source_part_refs else None
        rows.append(
            StructuredContextSpan(
                start_char=start,
                end_char=end,
                text_sha256=_sha256(text[start:end]),
                speaker_ref=(
                    None
                    if raw_speaker is None
                    else str(raw_speaker).strip() or None
                ),
                source_part_ref=(
                    None
                    if raw_source_part is None
                    else str(raw_source_part).strip() or None
                ),
            )
        )
        previous_end = end

    speakers = {row.speaker_ref for row in rows if row.speaker_ref}
    source_parts = {row.source_part_ref for row in rows if row.source_part_ref}
    if len(speakers) > 1:
        signals.append("CROSS_TALK_OR_SPEAKER_BOUNDARY")
    if len(source_parts) > 1:
        signals.append("MONTAGE_OR_SOURCE_BOUNDARY")

    binding = structured_context_binding_sha256(
        source_sha256=expected_source_hash,
        spans=rows,
        omission_count=len(rows) - 1,
        signal_codes=signals,
    )
    return StructuredContextIntegrityAssessment(
        state="NEEDS_CONTEXT_REVIEW",
        source_sha256=expected_source_hash,
        binding_sha256=binding,
        spans=tuple(rows),
        omission_count=len(rows) - 1,
        signal_codes=tuple(signals),
    )


def curated_context_approval(
    *,
    source_sha256: str,
    quote_sha256: str,
    quote_start: int,
    quote_end: int,
) -> dict[str, object]:
    for value, field in (
        (source_sha256, "source_sha256"),
        (quote_sha256, "quote_sha256"),
    ):
        clean = str(value or "").strip().lower()
        if len(clean) != 64 or any(char not in "0123456789abcdef" for char in clean):
            raise ValueError(f"CONTEXT_{field.upper()}_INVALID")
    start = int(quote_start)
    end = int(quote_end)
    if start < 0 or end <= start:
        raise ValueError("CONTEXT_CURATED_RANGE_INVALID")
    return {
        "state": "APPROVED_CURATED",
        "source_sha256": str(source_sha256).lower(),
        "quote_sha256": str(quote_sha256).lower(),
        "quote_start": start,
        "quote_end": end,
        "signal_codes": [],
        "review_method": "CURATED_SOURCE_REVIEW",
        "version": CONTEXT_INTEGRITY_VERSION,
    }


# A private semantic hypothesis, deliberately separate from v1's publication-facing
# CLEAR_AUTOMATIC / APPROVED_CURATED context-review states.
SPEECH_ACT_CONTEXT_VERSION = "speech-act-context-v1"
_SPEECH_ACT_LANGUAGES = frozenset({"it", "en", "de"})
_SPEECH_ACT_MAX_TURN_CHARS = 12000
# U+2018/U+2019 delimit quotes;
# contractions, decade elisions and plausible plural/name possessives are
# orthographic exceptions. An s-final possessive at the apparent boundary is
# inherently ambiguous: prefer HOLD to inferring a speaker's endorsement.
_OTHER_QUOTED_TEXT_RE = re.compile(
    r"""«[^«»]+»|»[^«»]+«|‹[^‹›]+›|›[^‹›]+‹|“[^“”„‟]+”|„[^„“”‟]+“|\u300c[^\u300c\u300d]+\u300d|\u300e[^\u300e\u300f]+\u300f|\u300a[^\u300a\u300b]+\u300b|\u3010[^\u3010\u3011]+\u3011|"[^"\n]+"|(?<!\w)'[^'\n]+'(?!\w)"""
)
_ORTHOGRAPHIC_WORD_RE = re.compile(r"\w+", re.UNICODE)
_NEXT_WORD_RE = re.compile(r"\s+\w", re.UNICODE)


def _curly_quote_spans(turn: str) -> tuple[list[tuple[int, int]], bool]:
    """Bounded single-pass orthographic pairing, with no semantic word blacklist.

    A plural/common-noun s-ending or s-final proper name followed by another
    word can introduce a possessive. Without a later closer, the resulting
    open quotation remains unresolved. This is deliberately conservative for
    ambiguous words such as workers/James, not a grammar or publication proof.
    """
    spans: list[tuple[int, int]] = []
    # Pre-tokenize once: checking a possible apostrophe never re-scans a prefix.
    words_by_end = {match.end(): match.group() for match in _ORTHOGRAPHIC_WORD_RE.finditer(turn)}
    opened: int | None = None
    unbalanced = False
    for pos, char in enumerate(turn):
        if char == "‚":
            # German low-single opens a quotation completed by U+2018.
            # A second low opener is nesting, not a safe original quote.
            if opened is not None:
                unbalanced = True
            else:
                opened = pos
            continue
        if char == "‘":
            if opened is not None and turn[opened] == "‚":
                spans.append((opened, pos + 1))
                opened = None
            elif opened is not None:
                unbalanced = True
            else:
                opened = pos
            continue
        if char in "‛❛❜❝❞〝〞〟":
            # Unsupported quotation punctuation is not ordinary speech:
            # never interpret its clipped contents as direct endorsement.
            unbalanced = True
            continue
        if char != "’":
            continue
        before = turn[pos - 1] if pos else ""
        after = turn[pos + 1] if pos + 1 < len(turn) else ""
        if before.isalnum() and after.isalnum():
            # Internal contraction, such as I'm / I’m or workers’rights.
            continue
        if not before.isalnum() and after.isdigit():
            # Leading numeric elision: the ’90s.
            continue
        if before.casefold() == "s" and after.isspace():
            word = words_by_end.get(pos)
            if word and _NEXT_WORD_RE.match(turn, pos + 1):
                # S-final names and likely plural/common nouns are plausible
                # possessives. The criterion uses case and ending shape, not a
                # finite whitelist of English/German function words.
                noun_like = (
                    (len(word) > 1 and word.istitle())
                    or (len(word) >= 4 and word[-2].casefold() in "bcdfghjklmnpqrstvwxz")
                    or (len(word) >= 5 and word.casefold().endswith("es"))
                )
                if noun_like:
                    continue
        if opened is None:
            unbalanced = True
        else:
            spans.append((opened, pos + 1))
            opened = None
    return spans, unbalanced or opened is not None


_SPEECH_ACT_CUES = {
    "it": {
        "opinion": re.compile(r"\b(?:secondo\s+me|a\s+mio\s+parere)\b", re.I),
        "critique": re.compile(r"\b(?:critico|condanno|contesto|respingo|non\s+condivido)\b", re.I),
        "performance": re.compile(r"\b(?:recito|interpreto|imito|insceno)\b", re.I),
        "report": re.compile(r"\b(?:secondo|ha\s+detto|diceva|riporto|cito)\b", re.I),
        "denial": re.compile(r"\b(?:non\s+(?:ho\s+)?(?:mai\s+)?(?:detto|sostengo|affermo|condivido|ritengo)|nego\s+che)\b", re.I),
        "endorse": re.compile(r"\b(?:io\s+)?(?:sostengo|affermo|ritengo)\s+che\b", re.I),
        "support": re.compile(r"\b(?:io\s+)?(?:sostengo|appoggio|condivido)\b", re.I),
        "negation": re.compile(r"\b(?:non|mai|nessuno|nessuna|senza)\b", re.I),
        "qualification": re.compile(r"\b(?:ma|però|tuttavia|salvo|tranne|in\s+realtà)\b", re.I),
        "conditional": re.compile(r"\b(?:se|qualora|purché|a\s+condizione\s+che)\b", re.I),
    },
    "en": {
        "opinion": re.compile(r"\b(?:in\s+my\s+opinion|i\s+think\s+that)\b", re.I),
        "critique": re.compile(r"\b(?:criticize|criticise|condemn|reject|disavow)\b", re.I),
        "performance": re.compile(r"\b(?:recite|perform|impersonate|act\s+out)\b", re.I),
        "report": re.compile(r"\b(?:according\s+to|said|reported|quoting)\b", re.I),
        "denial": re.compile(r"\b(?:i\s+(?:do\s+not|don't|never)\s+(?:say|said|support|endorse|believe)|i\s+deny\s+that)\b", re.I),
        "endorse": re.compile(r"\b(?:i\s+(?:support|maintain|affirm|believe)\s+that|i\s+support)\b", re.I),
        "support": re.compile(r"\bi\s+(?:support|endorse)\b", re.I),
        "negation": re.compile(r"\b(?:not|never|no|none|neither|nobody|nothing|without|don't|didn't)\b", re.I),
        "qualification": re.compile(r"\b(?:but|however|except|unless|although)\b", re.I),
        "conditional": re.compile(r"\b(?:if|provided\s+that|only\s+when)\b", re.I),
    },
    "de": {
        "opinion": re.compile(r"\b(?:meiner\s+meinung\s+nach|ich\s+denke\s*,?\s+dass)\b", re.I),
        "critique": re.compile(r"\b(?:kritisiere|verurteile|lehne\s+ab|distanziere)\b", re.I),
        "performance": re.compile(r"\b(?:rezitiere|spiele\s+nach|imitiere|trage\s+vor)\b", re.I),
        "report": re.compile(r"\b(?:laut|zufolge|sagte|berichtete|zitiere)\b", re.I),
        "denial": re.compile(r"\b(?:ich\s+habe\s+(?:nie|nicht)\s+gesagt|ich\s+unterstütze\s+nicht)\b", re.I),
        "endorse": re.compile(r"\b(?:ich\s+(?:unterstütze|befürworte|behaupte)|ich\s+sage\s*,?\s+dass)\b", re.I),
        "support": re.compile(r"\bich\s+(?:unterstütze|befürworte)\b", re.I),
        "negation": re.compile(r"\b(?:nicht|nichts|nie|kein\w*|niemals|mitnichten|nimmer|ohne|weder|niemand\w*)\b", re.I),
        "qualification": re.compile(r"\b(?:aber|jedoch|außer|obwohl|es\s+sei\s+denn)\b", re.I),
        "conditional": re.compile(r"\b(?:wenn|falls|sofern|vorausgesetzt)\b", re.I),
    },
}


@dataclass(frozen=True)
class SpeechActContextDecision:
    """An inspectable private hypothesis; it never approves speaker or publication."""

    state: str
    speech_act: str
    stance: str
    polarity: str
    language: str
    utterer_id: str
    quoted_author_id: str | None
    source_part_ref: str
    turn_speaker_ids: tuple[str, ...]
    context_parts: tuple[tuple[int, int, str], ...]
    turn_complete: bool
    source_sha256: str
    quote_sha256: str
    context_sha256: str
    quote_start: int
    quote_end: int
    context_start: int
    context_end: int
    signal_codes: tuple[str, ...]
    binding_sha256: str
    version: str = SPEECH_ACT_CONTEXT_VERSION

    @property
    def publication_authority(self) -> bool:
        return False

    def to_metadata(self) -> dict[str, object]:
        # No raw text, source URL, reviewer identity or publicly consumable READY flag.
        return asdict(self)


def assess_speech_act_context(
    *,
    source_text: str,
    source_sha256: str,
    quote_start: int,
    quote_end: int,
    turn_start: int,
    turn_end: int,
    utterer_id: str,
    language: str,
    turn_speaker_ids: Sequence[str] = (),
    source_part_ref: str = "",
    turn_complete: bool = False,
    quoted_author_id: str | None = None,
    context_parts: Sequence[tuple[int, int, str]] = (),
) -> SpeechActContextDecision:
    """Conservative lexical cues for a *private* speech-act candidate.

    Completeness, speaker and source-part inputs are supplied provenance assertions,
    not independent attestations. Only the existing review/publication authorities
    can approve an attribution. Unsupported language and ambiguous phrasing hold.
    """
    if not isinstance(source_text, str) or _sha256(source_text) != _sha256_value(
        source_sha256, "SOURCE_SHA256"
    ):
        raise ValueError("CONTEXT_SOURCE_HASH_MISMATCH")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (quote_start, quote_end, turn_start, turn_end)
    ) or not (0 <= turn_start <= quote_start < quote_end <= turn_end <= len(source_text)):
        raise ValueError("SPEECH_ACT_RANGE_INVALID")
    if not isinstance(turn_complete, bool):
        raise ValueError("SPEECH_ACT_TURN_COMPLETENESS_INVALID")
    if not isinstance(language, str):
        raise ValueError("SPEECH_ACT_LANGUAGE_INVALID")
    if not isinstance(utterer_id, str) or not isinstance(source_part_ref, str):
        raise ValueError("SPEECH_ACT_PROVENANCE_REF_INVALID")
    if quoted_author_id is not None and not isinstance(quoted_author_id, str):
        raise ValueError("SPEECH_ACT_QUOTED_AUTHOR_REF_INVALID")
    if not isinstance(turn_speaker_ids, (tuple, list)) or any(
        not isinstance(ref, str) or not ref.strip() for ref in turn_speaker_ids
    ):
        raise ValueError("SPEECH_ACT_SPEAKER_REFS_INVALID")
    if not isinstance(context_parts, (tuple, list)) or len(context_parts) > 16:
        raise ValueError("SPEECH_ACT_CONTEXT_PARTS_INVALID")

    parts: list[tuple[int, int, str]] = []
    previous_end = turn_start
    for raw in context_parts:
        if (
            not isinstance(raw, (tuple, list)) or len(raw) != 3
            or any(not isinstance(x, int) or isinstance(x, bool) for x in raw[:2])
            or not isinstance(raw[2], str) or not raw[2].strip()
            or raw[0] != previous_end or not raw[0] < raw[1] <= turn_end
        ):
            raise ValueError("SPEECH_ACT_CONTEXT_PARTS_INVALID")
        parts.append((raw[0], raw[1], raw[2].strip()))
        previous_end = raw[1]
    if parts and previous_end != turn_end:
        raise ValueError("SPEECH_ACT_CONTEXT_PARTS_INVALID")

    lang = language.strip().casefold()
    speaker = utterer_id.strip()
    author = quoted_author_id.strip() or None if quoted_author_id is not None else None
    part = source_part_ref.strip()
    speakers = tuple(ref.strip() for ref in turn_speaker_ids)
    turn = source_text[turn_start:turn_end]
    quote = source_text[quote_start:quote_end]
    signals: list[str] = []
    if lang not in _SPEECH_ACT_LANGUAGES:
        signals.append("LANGUAGE_SEMANTICS_UNSUPPORTED")
    if not speaker or not part or not speakers:
        signals.append("UTTERER_PROVENANCE_REQUIRED")
    if speakers and (len(speakers) != 1 or speakers[0] != speaker):
        signals.append("SPEAKER_TURN_CONFLICT")
    if not turn_complete:
        signals.append("TURN_COMPLETENESS_UNVERIFIED")
    if len(turn) > _SPEECH_ACT_MAX_TURN_CHARS:
        signals.append("TURN_LENGTH_UNSUPPORTED")
    if (turn_start and source_text[:turn_start].rstrip()
            and source_text[:turn_start].rstrip()[-1] not in ".!?\n") or (
        turn_end < len(source_text) and turn.rstrip()
        and turn.rstrip()[-1] not in ".!?\n"
    ):
        signals.append("TURN_BOUNDARY_UNVERIFIED")
    if len({row[2] for row in parts}) > 1:
        signals.append("MONTAGE_OR_SOURCE_BOUNDARY")
    if parts and parts[0][2] != part:
        signals.append("SOURCE_PART_BINDING_MISMATCH")
    if not parts and not part:
        signals.append("SOURCE_PART_REQUIRED")

    # Keep quotation parsing and endorsement detection consistent.
    curly_spans, curly_unbalanced = _curly_quote_spans(turn)
    other_spans = [(m.start(), m.end()) for m in _OTHER_QUOTED_TEXT_RE.finditer(turn)]
    quote_spans = sorted((*curly_spans, *other_spans))
    if curly_unbalanced:
        signals.append("UNBALANCED_QUOTATION")
    # Nested or reversed angle delimiters can share the same total counts:
    # validate complete adjacent pairs in either supported orientation.
    for opener, closer in (("«", "»"), ("‹", "›")):
        angle_marks = "".join(char for char in turn if char in (opener, closer))
        if len(angle_marks) % 2 or any(
            angle_marks[i:i + 2] not in (opener + closer, closer + opener)
            for i in range(0, len(angle_marks), 2)
        ):
            signals.append("UNBALANCED_QUOTATION")
    # Corner/book/title quotation marks can enclose otherwise English text;
    # the source language tag does not convert reported speech to endorsement.
    for opener, closer in (("\u300c", "\u300d"), ("\u300e", "\u300f"), ("\u300a", "\u300b"), ("\u3010", "\u3011")):
        cjk_marks = "".join(char for char in turn if char in (opener, closer))
        if len(cjk_marks) % 2 or any(
            cjk_marks[i:i + 2] != opener + closer
            for i in range(0, len(cjk_marks), 2)
        ):
            signals.append("UNBALANCED_QUOTATION")
    # U+201E + U+201C are the conventional German low/high double pair;
    # U+201C + U+201D are the usual high-double pair. No inverted, nested,
    # dangling or unsupported U+201F token can imply direct endorsement.
    smart_double = "".join(char for char in turn if char in "“”„‟")
    if len(smart_double) % 2 or any(
        smart_double[i:i + 2] not in ("“”", "„“")
        for i in range(0, len(smart_double), 2)
    ):
        signals.append("UNBALANCED_QUOTATION")
    if turn.count('"') % 2:
        signals.append("UNBALANCED_QUOTATION")
    # ASCII apostrophe U+0027 can be an in-word contraction or leading
    # numeric elision; other unpaired marks must not silently endorse
    # a possibly clipped quoted turn. Ambiguous trailing possessives HOLD.
    straight_single = 0
    for pos, char in enumerate(turn):
        if char != "'":
            continue
        previous = turn[pos - 1] if pos else ""
        following = turn[pos + 1] if pos + 1 < len(turn) else ""
        if previous.isalnum() and following.isalnum():
            continue
        if not previous.isalnum() and following.isdigit():
            continue
        straight_single += 1
    if straight_single % 2:
        signals.append("UNBALANCED_QUOTATION")
    if len(re.findall(r"[.!?](?=\s|$)", turn)) > 1:
        signals.append("MULTI_SENTENCE_CONTEXT_REQUIRES_SPLIT")
    local_start = quote_start - turn_start
    local_end = quote_end - turn_start
    nested_target = any(
        local_start >= start + 1 and local_end <= end - 1
        for start, end in quote_spans
    )
    quoted_whole_turn = bool(
        len(quote_spans) == 1 and turn.strip() == turn[quote_spans[0][0]:quote_spans[0][1]]
    )
    # Blank matched quotation spans; leave unmatched text visible, but the
    # UNBALANCED_QUOTATION signal prevents such text from becoming ENDORSE.
    unquoted_chars = list(turn)
    for start, end in quote_spans:
        unquoted_chars[start:end] = " " * (end - start)
    unquoted = "".join(unquoted_chars)
    cues = _SPEECH_ACT_CUES.get(lang)
    act, stance = "UNKNOWN", "UNKNOWN"
    polarity = "UNKNOWN"
    if cues and "UNBALANCED_QUOTATION" not in signals:
        negative = bool(cues["negation"].search(turn))
        polarity = "NEGATED" if negative else "POSITIVE"
        if cues["critique"].search(unquoted):
            if negative:
                # A lexical criticism cue under negation does not establish
                # that the utterer distanced themselves from the target.
                # Scope must be resolved against the full source context.
                signals.append("CRITIQUE_NEGATION_SCOPE_UNRESOLVED")
            else:
                act, stance = "CRITIQUE", "DISTANCE"
        elif cues["performance"].search(unquoted):
            act, stance = "PERFORMANCE", "NON_COMMITTAL"
        elif cues["opinion"].search(unquoted):
            if negative:
                signals.append("OPINION_NEGATION_SCOPE_UNRESOLVED")
            else:
                act, stance = "OPINION", "ENDORSE"
        elif cues["report"].search(unquoted):
            act, stance = "REPORT", "NON_COMMITTAL"
        elif cues["denial"].search(unquoted):
            act, stance = "DENIAL", "REFUTE"
        elif "?" in unquoted:
            act, stance = "QUESTION", "NON_COMMITTAL"
        elif nested_target or quoted_whole_turn:
            act, stance = "QUOTE", "NON_COMMITTAL"
        else:
            explicit_support = cues["endorse"].search(unquoted) or cues["support"].search(unquoted)
            if explicit_support and not negative:
                act, stance = "ASSERTION", "ENDORSE"
            elif explicit_support and negative:
                # "Sostengo che non X" endorses a *negative proposition*;
                # "non sostengo che X" denies endorsement. Other scope/order
                # ambiguities need a contextual verifier, not a guessed stance.
                if lang == "it" and re.search(
                    r"\b(?:sostengo|affermo|ritengo)\s+che\s+non\b", unquoted, re.I
                ):
                    act, stance = "ASSERTION", "ENDORSE"
                else:
                    signals.append("NEGATION_SCOPE_UNRESOLVED")
        if cues["qualification"].search(unquoted):
            signals.append("QUALIFICATION_REQUIRES_INTERPRETATION")
        if cues["conditional"].search(unquoted):
            signals.append("CONDITIONAL_CONTEXT_REQUIRES_INTERPRETATION")
    if author is not None and not quote_spans and act not in {"REPORT", "QUOTE"}:
        signals.append("QUOTED_AUTHOR_WITHOUT_QUOTE")
    if act == "UNKNOWN":
        signals.append("SPEECH_ACT_NOT_DETERMINED")
    if nested_target and author is None:
        signals.append("QUOTED_AUTHOR_UNVERIFIED")
    if (
        quote_start != turn_start or quote_end != turn_end
    ) and not nested_target:
        signals.append("FRAGMENTARY_SOURCE_QUOTE")
        if cues and cues["negation"].search(turn) and not cues["negation"].search(quote):
            signals.append("NEGATION_OUTSIDE_QUOTE")

    if signals:
        if stance == "ENDORSE":
            stance = "UNKNOWN"
        state = "HOLD_FOR_CONTEXT"
    else:
        state = "CANDIDATE_PRIVATE"
    material = {
        "state": state, "speech_act": act, "stance": stance, "polarity": polarity,
        "language": lang, "utterer_id": speaker, "quoted_author_id": author,
        "source_part_ref": part, "turn_speaker_ids": speakers,
        "context_parts": tuple(parts), "turn_complete": turn_complete,
        "source_sha256": _sha256(source_text), "quote_sha256": _sha256(quote),
        "context_sha256": _sha256(turn), "quote_start": quote_start,
        "quote_end": quote_end, "context_start": turn_start,
        "context_end": turn_end, "signal_codes": tuple(dict.fromkeys(signals)),
        "version": SPEECH_ACT_CONTEXT_VERSION,
    }
    binding = hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return SpeechActContextDecision(binding_sha256=binding, **material)


def verify_speech_act_context_metadata(
    metadata: Mapping[str, object], *, source_text: str
) -> SpeechActContextDecision:
    """Replay the same private hypothesis against exact source bytes, never a signature."""
    if not isinstance(metadata, Mapping):
        raise ValueError("SPEECH_ACT_METADATA_INVALID")
    if metadata.get("version") != SPEECH_ACT_CONTEXT_VERSION:
        raise ValueError("SPEECH_ACT_VERSION_INVALID")
    try:
        result = assess_speech_act_context(
            source_text=source_text,
            source_sha256=metadata["source_sha256"],
            quote_start=metadata["quote_start"],
            quote_end=metadata["quote_end"],
            turn_start=metadata["context_start"],
            turn_end=metadata["context_end"],
            utterer_id=metadata["utterer_id"],
            quoted_author_id=metadata["quoted_author_id"],
            turn_speaker_ids=metadata["turn_speaker_ids"],
            source_part_ref=metadata["source_part_ref"],
            context_parts=metadata["context_parts"],
            turn_complete=metadata["turn_complete"],
            language=metadata["language"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("SPEECH_ACT_METADATA_INVALID") from exc
    if json.dumps(result.to_metadata(), sort_keys=True) != json.dumps(
        dict(metadata), sort_keys=True
    ):
        raise ValueError("SPEECH_ACT_BINDING_MISMATCH")
    return result


__all__ = [
    "CLEAR_STATES",
    "CONTEXT_INTEGRITY_VERSION",
    "ContextIntegrityAssessment",
    "SPEECH_ACT_CONTEXT_VERSION",
    "SpeechActContextDecision",
    "StructuredContextIntegrityAssessment",
    "StructuredContextSpan",
    "assess_context_integrity",
    "assess_speech_act_context",
    "assess_structured_context_integrity",
    "curated_context_approval",
    "structured_context_binding_sha256",
    "verify_structured_context_integrity_metadata",
    "verify_speech_act_context_metadata",
]
