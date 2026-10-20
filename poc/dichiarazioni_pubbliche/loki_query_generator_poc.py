"""Restricted fork of Loki factcheck/core/QueryGenerator.py (MIT; #160)."""

from __future__ import annotations

from dichiarazioni_pubbliche.loki_decompose_poc import _json_object, _numbers


class QueryGenerator:
    """Only validates private suggested questions; performs no retrieval."""

    def __init__(self, max_query_per_claim: int = 3) -> None:
        if not 1 <= max_query_per_claim <= 5:
            raise ValueError("LOKI_QUERY_CAP_INVALID")
        self.max_query_per_claim = max_query_per_claim

    def generate_query(
        self, claims: tuple[str, ...], worthy: tuple[bool, ...], output: str,
    ) -> dict[str, tuple[str, ...]]:
        mapping = _json_object(output)
        if set(mapping) != set(claims) or len(worthy) != len(claims):
            raise ValueError("LOKI_QUERY_MAPPING_INVALID")
        queries: dict[str, tuple[str, ...]] = {}
        for claim, is_worthy in zip(claims, worthy):
            row = mapping[claim]
            if not isinstance(row, dict) or set(row) != {"Questions"}:
                raise ValueError("LOKI_QUERY_SCHEMA_INVALID")
            questions = row["Questions"]
            if (not isinstance(questions, list) or len(questions) > self.max_query_per_claim
                    or any(not isinstance(q, str) or not 8 <= len(q.strip()) <= 240
                           or "://" in q for q in questions)
                    or len(set(questions)) != len(questions)):
                raise ValueError("LOKI_QUERIES_INVALID")
            if any(not set(_numbers(q)).issubset(set(_numbers(claim))) for q in questions):
                raise ValueError("LOKI_QUERY_QUANTITY_NOT_IN_CLAIM")
            if (is_worthy and not questions) or (not is_worthy and questions):
                raise ValueError("LOKI_QUERY_POLICY_BLOCKED")
            queries[claim] = tuple(questions)
        return queries
