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
    try:
        value = json.loads(payload, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError) as exc:
        raise ValueError("LOKI_OUTPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("LOKI_OUTPUT_OBJECT_REQUIRED")
    return value


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", text))


class Decompose:
    """Port of Loki's getclaims/restore_claims, with stricter source binding."""

    def getclaims(self, doc: str, output: str, restoration: str) -> tuple[LokiSpan, ...]:
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
            if any(start < earlier.end and end > earlier.start for earlier in spans):
                raise ValueError("LOKI_SOURCE_SPAN_OVERLAP")
            spans.append(LokiSpan(claim, source, start, end))
        return tuple(spans)
