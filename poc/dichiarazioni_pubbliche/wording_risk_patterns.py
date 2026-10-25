"""Bounded lexical risk signals for derived wording parity.

These expressions are screening cues, never translation or source approval.
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?")
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
)
_CAPITALIZED_RE = re.compile(r"\b[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’.-]{2,}\b")

_NEGATIONS = {
    "it": re.compile(r"\b(?:non|mai|nessun\w*|niente|nulla|senza)\b", re.I),
    "en": re.compile(r"\b(?:not|never|no|none|neither|nobody|nothing|without|n't)\b", re.I),
    "de": re.compile(r"\b(?:nicht|nichts|nie|niemals|mitnichten|nimmer|kein\w*|ohne|weder|niemand\w*)\b", re.I),
    "fr": re.compile(r"\b(?:ne|pas|jamais|aucun|sans)\b", re.I),
    "es": re.compile(r"\b(?:no|nunca|ning[uú]n|sin)\b", re.I),
}
_MODALS = {
    "it": re.compile(r"\b(?:deve|devono|può|possono|potrebbe|potrebbero|dovrebbe|dovrebbero)\b", re.I),
    "en": re.compile(r"\b(?:must|may|might|can|could|should|would)\b", re.I),
    "de": re.compile(r"\b(?:muss|müssen|soll|sollen|kann|können|könnte|könnten|darf|dürfen)\b", re.I),
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
    "de": {
        "OBLIGATION": re.compile(r"\b(?:muss|müssen|soll|sollen)\b", re.I),
        "POSSIBILITY": re.compile(r"\b(?:kann|können|könnte|könnten|darf|dürfen)\b", re.I),
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
