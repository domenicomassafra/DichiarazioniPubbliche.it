from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass


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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


__all__ = [
    "CLEAR_STATES",
    "CONTEXT_INTEGRITY_VERSION",
    "ContextIntegrityAssessment",
    "assess_context_integrity",
    "curated_context_approval",
]
