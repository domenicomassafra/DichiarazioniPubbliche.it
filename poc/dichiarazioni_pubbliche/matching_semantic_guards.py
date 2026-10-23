"""Deterministic conflict checks shared by lexical ranking and model hints."""
from __future__ import annotations

import re

from dichiarazioni_pubbliche.proposition_clustering import PropositionInput, normalize_proposition


_NUMBERS = re.compile(r"\b\d+(?:[,.]\d+)?\b")
_ITALIAN_NUMBER_WORDS = frozenset({
    "zero", "uno", "una", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove",
    "dieci", "undici", "dodici", "tredici", "quattordici", "quindici", "sedici",
    "diciassette", "diciotto", "diciannove", "venti", "trenta", "quaranta", "cinquanta",
    "sessanta", "settanta", "ottanta", "novanta", "cento", "mille", "mila",
    "milione", "milioni", "miliardo", "miliardi",
})
_NEGATION = frozenset({"non", "no", "mai", "nessuno", "nessuna", "nessun", "senza", "ne", "né"})
_QUOTES = ('"', "«", "»", "“", "”")


def conflicting_proposition_features(left: PropositionInput, right: PropositionInput) -> tuple[dict[str, str], ...]:
    """Return independent reasons why lexical similarity cannot establish equivalence."""
    conflicts: list[dict[str, str]] = []
    if (left.entity_keys or right.entity_keys) and set(left.entity_keys) != set(right.entity_keys):
        conflicts.append({"code": "SEMANTIC_IDENTITY_CONFLICT"})
    if not left.entity_keys and not right.entity_keys and normalize_proposition(
            left.normalized_text) != normalize_proposition(right.normalized_text):
        conflicts.append({"code": "SEMANTIC_IDENTITY_UNVERIFIED"})
    left_tokens = normalize_proposition(left.normalized_text).split()
    right_tokens = normalize_proposition(right.normalized_text).split()
    if (_NUMBERS.findall(left.normalized_text) != _NUMBERS.findall(right.normalized_text)
            or [w for w in left_tokens if w in _ITALIAN_NUMBER_WORDS]
            != [w for w in right_tokens if w in _ITALIAN_NUMBER_WORDS]):
        conflicts.append({"code": "SEMANTIC_NUMERIC_CONFLICT"})
    if ([word for word in left_tokens if word in _NEGATION]
            != [word for word in right_tokens if word in _NEGATION]):
        conflicts.append({"code": "SEMANTIC_NEGATION_CONFLICT"})
    if (any(char in left.normalized_text for char in _QUOTES)
            != any(char in right.normalized_text for char in _QUOTES)):
        conflicts.append({"code": "SEMANTIC_QUOTATION_CONFLICT"})
    return tuple(conflicts)
