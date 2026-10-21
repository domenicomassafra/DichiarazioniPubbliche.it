"""Restricted fork of Loki factcheck/core/Decompose.py (MIT; #160).

Retains upstream's two phases (claim decomposition and source-span restoration)
but accepts only local JSON fixtures; no model client, eval, NLTK or retries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LokiSpan:
    claim: str
    source: str
    start: int
    end: int


def _json_object(payload: str, *, maximum: int = 16384) -> dict:
    if not isinstance(payload, str) or len(payload) > maximum:
        raise ValueError("LOKI_OUTPUT_SIZE_INVALID")
    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("LOKI_OUTPUT_DUPLICATE_KEY")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload, object_pairs_hook=unique_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, TypeError) as exc:
        if str(exc) == "LOKI_OUTPUT_DUPLICATE_KEY":
            raise
        raise ValueError("LOKI_OUTPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("LOKI_OUTPUT_OBJECT_REQUIRED")
    return value


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", text))


_NEGATION_CUES = {
    "it": re.compile(r"\b(?:non|mai|nessun\w*|niente|né|senza)\b", re.I),
    "en": re.compile(r"\b(?:not|never|no|none|neither|nobody|nothing|without|\w+n't)\b", re.I),
    "de": re.compile(r"\b(?:nicht|nichts|nie|kein\w*|niemals|ohne|weder|niemand\w*)\b", re.I),
    "fr": re.compile(r"\b(?:pas|jamais|aucun\w*|sans|ni)\b", re.I),
    "es": re.compile(r"\b(?:no|nunca|jamás|ningun\w*|sin|ni)\b", re.I),
}


def _negation_signature(text: str, language: str) -> tuple[str, ...]:
    """Conservative lexical cues only; semantic negation scope still needs review."""
    return tuple(match.group(0).casefold() for match in
                 _NEGATION_CUES[language].finditer(text))


def _sentence_context(doc: str, start: int, end: int) -> str:
    """Include qualifiers outside cropped source spans to avoid false positives."""
    separators = ".!?\n"
    before = max(doc.rfind(char, 0, start) for char in separators) + 1
    after = min((pos for char in separators
                 if (pos := doc.find(char, end)) >= 0), default=len(doc))
    return doc[before:after]


_REPORTING_CUES = {
    "it": re.compile(r"\b(?:ha\s+(?:detto|dichiarato|riferito|affermato)\s+che|secondo)\b", re.I),
    "en": re.compile(r"\b(?:said\s+that|reported\s+that|according\s+to)\b", re.I),
    "de": re.compile(r"\b(?:sagte\s*,?\s*dass|berichtete\s*,?\s*dass|laut|zufolge)\b", re.I),
    "fr": re.compile(r"\b(?:a\s+(?:dit|déclaré|rapporté)\s+que|selon)\b", re.I),
    "es": re.compile(r"\b(?:(?:dijo|declaró|informó)\s+que|según)\b", re.I),
}


def has_reported_speech_context(doc: str, start: int, end: int, language: str) -> bool:
    """Fail closed on obvious attributions even when fixture metadata omits them."""
    return bool(_REPORTING_CUES[language].search(_sentence_context(doc, start, end)))


class Decompose:
    """Port of Loki's getclaims/restore_claims, with stricter source binding."""

    def getclaims(self, doc: str, output: str, restoration: str, *, language: str) -> tuple[LokiSpan, ...]:
        if not isinstance(doc, str) or not 1 <= len(doc) <= 16000:
            raise ValueError("LOKI_DOCUMENT_INVALID")
        parsed = _json_object(output)
        if set(parsed) != {"claims"}:
            raise ValueError("LOKI_CLAIMS_SCHEMA_INVALID")
        claims = parsed["claims"]
        if (not isinstance(claims, list) or not 1 <= len(claims) <= 12
                or any(not isinstance(c, str) or not c.strip() or len(c) > 2000 for c in claims)
                or len(set(claims)) != len(claims)):
            raise ValueError("LOKI_CLAIMS_INVALID")
        mapping = _json_object(restoration)
        if set(mapping) != set(claims):
            raise ValueError("LOKI_RESTORATION_INCOMPLETE")
        spans: list[LokiSpan] = []
        for claim in claims:
            source = mapping[claim]
            if (not isinstance(source, str) or not source.strip() or len(source) > len(doc)
                    or doc.count(source) != 1):
                raise ValueError("LOKI_SOURCE_SPAN_AMBIGUOUS")
            if not set(_numbers(claim)).issubset(set(_numbers(source))):
                raise ValueError("LOKI_QUANTITY_NOT_IN_SOURCE")
            start = doc.index(source)
            end = start + len(source)
            if _negation_signature(claim, language) != _negation_signature(source, language):
                raise ValueError("LOKI_NEGATION_MISMATCH")
            if _negation_signature(_sentence_context(doc, start, end), language) != _negation_signature(source, language):
                raise ValueError("LOKI_NEGATION_OUTSIDE_SOURCE_SPAN")
            if any(start < earlier.end and end > earlier.start for earlier in spans):
                raise ValueError("LOKI_SOURCE_SPAN_OVERLAP")
            spans.append(LokiSpan(claim, source, start, end))
        return tuple(spans)
