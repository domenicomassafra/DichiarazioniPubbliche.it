"""Restricted fork of Loki factcheck/core/CheckWorthy.py (MIT; #160)."""

from __future__ import annotations

from dichiarazioni_pubbliche.claim_contract import NON_FACTUAL_CLAIM_TYPES
from dichiarazioni_pubbliche.domain_vocabulary import ClaimType
from dichiarazioni_pubbliche.loki_decompose_poc import _json_object


class Checkworthy:
    """Preserves per-claim Yes/No selection; never defaults to all-worthy."""

    def identify_checkworthiness(
        self, claims: tuple[str, ...], claim_types: dict[str, str], output: str,
    ) -> tuple[bool, ...]:
        mapping = _json_object(output)
        if set(mapping) != set(claims) or set(claim_types) != set(claims):
            raise ValueError("LOKI_CHECKWORTHY_INCOMPLETE")
        result: list[bool] = []
        for claim in claims:
            answer = mapping[claim]
            if answer not in ("Yes", "No"):
                raise ValueError("LOKI_CHECKWORTHY_AMBIGUOUS")
            try:
                kind = ClaimType(claim_types[claim])
            except (TypeError, ValueError) as exc:
                raise ValueError("LOKI_CLAIM_TYPE_UNKNOWN") from exc
            if kind in NON_FACTUAL_CLAIM_TYPES and answer == "Yes":
                raise ValueError("LOKI_NON_FACTUAL_CHECKWORTHY")
            result.append(answer == "Yes")
        return tuple(result)
