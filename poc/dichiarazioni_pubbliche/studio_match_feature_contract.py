"""Allowlisted private Studio match-feature contract and semantic validation."""
from __future__ import annotations

SUPPORTING_CODES = {
    "SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT", "HIGH_LEXICAL_OVERLAP",
    "SHARED_ENTITIES", "SHARED_TOPICS", "RELATED_LEXICAL_OR_ENTITY_CONTEXT",
    "AMBIGUOUS_LEXICAL_OVERLAP", "SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE",
}
SEMANTIC_CONFLICT_CODES = {
    "SEMANTIC_IDENTITY_CONFLICT", "SEMANTIC_IDENTITY_UNVERIFIED",
    "SEMANTIC_NUMERIC_CONFLICT", "SEMANTIC_NEGATION_CONFLICT",
    "SEMANTIC_QUOTATION_CONFLICT",
}
SCOPE_CONFLICT_CODES = {"CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS"}
HOLD_CONFLICT_CODES = SCOPE_CONFLICT_CODES | SEMANTIC_CONFLICT_CODES
CONTRADICTING_CODES = {"LOW_LEXICAL_NO_SHARED_CONTEXT"} | HOLD_CONFLICT_CODES
SCOPE_SUPPORT_CODES = {"SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE"}


def validate_feature_semantics(
    match_class: str, method: str,
    supporting: tuple[str, ...], contradicting: tuple[str, ...],
) -> None:
    """Require the native classifier's features, with extra fail-closed conflicts."""
    support, contrary = set(supporting), set(contradicting)
    if (
        len(support) != len(supporting) or len(contrary) != len(contradicting)
        or ("SAME_CLAIM_TYPE" in support and "CLAIM_TYPE_MISMATCH" in contrary)
        or ("SAME_TEMPORAL_SCOPE" in support and "TEMPORAL_SCOPE_DIFFERS" in contrary)
    ):
        raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
    primary_support = support - SCOPE_SUPPORT_CODES
    primary_contrary = contrary - HOLD_CONFLICT_CODES
    expected = {
        ("DUPLICATE_EXTRACTION", "SOURCE_SELECTOR_OVERLAP"):
            ({"SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT"}, set()),
        ("SAME_PROPOSITION", "EXACT_NORMALIZED"):
            ({"EXACT_NORMALIZED_TEXT"}, set()),
        ("RELATED", "LEXICAL_TRIGRAM"):
            ({"RELATED_LEXICAL_OR_ENTITY_CONTEXT"}, set()),
        ("DIFFERENT", "LEXICAL_TRIGRAM"):
            (set(), {"LOW_LEXICAL_NO_SHARED_CONTEXT"}),
        ("UNCERTAIN", "LEXICAL_TRIGRAM"):
            ({"AMBIGUOUS_LEXICAL_OVERLAP"}, set()),
    }
    if (match_class, method) == ("SAME_PROPOSITION", "LEXICAL_TRIGRAM"):
        if (
            "HIGH_LEXICAL_OVERLAP" not in primary_support
            or not primary_support.intersection({"SHARED_ENTITIES", "SHARED_TOPICS"})
            or not primary_support <= {
                "HIGH_LEXICAL_OVERLAP", "SHARED_ENTITIES", "SHARED_TOPICS"
            }
            or primary_contrary
        ):
            raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
    elif (primary_support, primary_contrary) != expected.get(
        (match_class, method), (None, None)
    ):
        raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
