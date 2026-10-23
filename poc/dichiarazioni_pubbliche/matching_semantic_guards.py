"""Deterministic conflict checks shared by lexical ranking and model hints."""
from __future__ import annotations

import re

from dichiarazioni_pubbliche.proposition_clustering import PropositionInput, normalize_proposition


_NUMBERS = re.compile(r"\b\d+(?:[,.]\d+)?\b")
_NEGATION = frozenset({"non", "no", "mai", "nessuno", "nessuna", "nessun", "senza", "ne", "né"})
_QUOTES = ('"', "«", "»", "“", "”")


def conflicting_proposition_features(left: PropositionInput, right: PropositionInput) -> tuple[dict[str, str], ...]:
    """Return independent reasons why lexical similarity cannot establish equivalence."""
    conflicts: list[dict[str, str]] = []
    if (left.entity_keys or right.entity_keys) and set(left.entity_keys) != set(right.entity_keys):
        conflicts.append({"code": "SEMANTIC_IDENTITY_CONFLICT"})
    if _NUMBERS.findall(left.normalized_text) != _NUMBERS.findall(right.normalized_text):
        conflicts.append({"code": "SEMANTIC_NUMERIC_CONFLICT"})
    left_tokens = normalize_proposition(left.normalized_text).split()
    right_tokens = normalize_proposition(right.normalized_text).split()
    if ([word for word in left_tokens if word in _NEGATION]
            != [word for word in right_tokens if word in _NEGATION]):
        conflicts.append({"code": "SEMANTIC_NEGATION_CONFLICT"})
    if (any(char in left.normalized_text for char in _QUOTES)
            != any(char in right.normalized_text for char in _QUOTES)):
        conflicts.append({"code": "SEMANTIC_QUOTATION_CONFLICT"})
    return tuple(conflicts)
