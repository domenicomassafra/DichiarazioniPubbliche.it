"""Read-only private Studio candidate-match inspection, not review authority.

Reads persisted DP-212 match results without re-running models, promoting a
candidate or claiming that the match run is current or reviewed.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.candidate_matching import (
    MATCHING_VERSION,
    deterministic_match_result_id,
    deterministic_match_run_id,
)

STUDIO_CANDIDATE_REVIEW_VERSION = "studio-candidate-review-readonly-v1"
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DISPOSITION = {
    "DUPLICATE_EXTRACTION": "PROPOSE_CLUSTER",
    "SAME_PROPOSITION": "PROPOSE_CLUSTER",
    "RELATED": "NO_CLUSTER",
    "DIFFERENT": "NO_CLUSTER",
    "UNCERTAIN": "HOLD",
}
_METHODS_BY_CLASS = {
    "DUPLICATE_EXTRACTION": {"SOURCE_SELECTOR_OVERLAP"},
    "SAME_PROPOSITION": {"EXACT_NORMALIZED", "LEXICAL_TRIGRAM"},
    "RELATED": {"LEXICAL_TRIGRAM"},
    "DIFFERENT": {"LEXICAL_TRIGRAM"},
    "UNCERTAIN": {"LEXICAL_TRIGRAM"},
}
_SUPPORTING_CODES = {
    "SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT", "HIGH_LEXICAL_OVERLAP",
    "SHARED_ENTITIES", "SHARED_TOPICS", "RELATED_LEXICAL_OR_ENTITY_CONTEXT",
    "AMBIGUOUS_LEXICAL_OVERLAP", "SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE",
}
_CONTRADICTING_CODES = {
    "LOW_LEXICAL_NO_SHARED_CONTEXT", "CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS",
}
_SCOPE_CONFLICT_CODES = {"CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS"}
_SCOPE_SUPPORT_CODES = {"SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE"}


def _validate_feature_semantics(
    match_class: str, method: str,
    supporting: tuple[str, ...], contradicting: tuple[str, ...],
) -> None:
    """Read the actual classifier's feature contract, not a class label alone."""
    support, contrary = set(supporting), set(contradicting)
    if (
        len(support) != len(supporting) or len(contrary) != len(contradicting)
        or ("SAME_CLAIM_TYPE" in support and "CLAIM_TYPE_MISMATCH" in contrary)
        or ("SAME_TEMPORAL_SCOPE" in support and "TEMPORAL_SCOPE_DIFFERS" in contrary)
    ):
        raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
    primary_support = support - _SCOPE_SUPPORT_CODES
    primary_contrary = contrary - _SCOPE_CONFLICT_CODES
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


class CandidateMatchReader(Protocol):
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]: ...


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_CANDIDATE_REFERENCE_INVALID")
    return value


def _features(value: object, allowed_codes: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 24:
        raise ValueError("STUDIO_CANDIDATE_FEATURES_INVALID")
    codes: list[str] = []
    for entry in value:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("code"), str):
            raise ValueError("STUDIO_CANDIDATE_FEATURE_INVALID")
        code = entry["code"]
        if not _CODE.fullmatch(code) or code not in allowed_codes:
            raise ValueError("STUDIO_CANDIDATE_FEATURE_CODE_INVALID")
        codes.append(code)
    return tuple(codes)


def inspect_candidate_match_run(
    store: CandidateMatchReader,
    *,
    run_id: str,
    claim_candidate_id: str,
) -> dict[str, object]:
    run_id = _safe_id(run_id)
    claim_candidate_id = _safe_id(claim_candidate_id)
    try:
        run = store.get_run(run_id)
        if not isinstance(run, Mapping):
            raise ValueError("STUDIO_CANDIDATE_RUN_MISSING")
        if run.get("id") != run_id or run.get("claim_candidate_id") != claim_candidate_id:
            raise ValueError("STUDIO_CANDIDATE_RUN_BINDING_MISMATCH")
        if run.get("matching_version") != MATCHING_VERSION:
            raise ValueError("STUDIO_CANDIDATE_RUN_VERSION_INVALID")
        fingerprint = run.get("input_fingerprint")
        if not isinstance(fingerprint, str) or not _HASH.fullmatch(fingerprint):
            raise ValueError("STUDIO_CANDIDATE_RUN_FINGERPRINT_INVALID")
        if run_id != deterministic_match_run_id(claim_candidate_id, fingerprint):
            raise ValueError("STUDIO_CANDIDATE_RUN_BINDING_MISMATCH")
        if run.get("status") != "COMPLETED":
            raise ValueError("STUDIO_CANDIDATE_RUN_INCOMPLETE")
        count = run.get("result_count")
        if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 30:
            raise ValueError("STUDIO_CANDIDATE_RUN_COUNT_INVALID")
        rows = store.load_results(run_id)
        if len(rows) != count:
            raise ValueError("STUDIO_CANDIDATE_RUN_RESULT_MISMATCH")
        results: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        seen_targets: set[tuple[str, str]] = set()
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise ValueError("STUDIO_CANDIDATE_RESULT_INVALID")
            if row.get("matching_version") != MATCHING_VERSION:
                raise ValueError("STUDIO_CANDIDATE_RESULT_VERSION_INVALID")
            if row.get("status") != "CANDIDATE":
                raise ValueError("STUDIO_CANDIDATE_RESULT_STATUS_INVALID")
            result_id = _safe_id(row.get("id"))
            rank = row.get("rank")
            if (result_id in seen_ids or type(rank) is not int or rank != index):
                raise ValueError("STUDIO_CANDIDATE_RESULT_ORDER_INVALID")
            seen_ids.add(result_id)
            match_class = row.get("match_class")
            target_type = row.get("target_type")
            if target_type not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}:
                raise ValueError("STUDIO_CANDIDATE_MATCH_CLASS_INVALID")
            target_id = _safe_id(row.get("target_id"))
            target = (target_type, target_id)
            if (target in seen_targets or
                    result_id != deterministic_match_result_id(run_id, target_type, target_id)):
                raise ValueError("STUDIO_CANDIDATE_RESULT_BINDING_MISMATCH")
            seen_targets.add(target)
            supporting_codes = _features(row.get("supporting_features"), _SUPPORTING_CODES)
            contradicting_codes = _features(row.get("contradicting_features"), _CONTRADICTING_CODES)
            disposition = (
                "HOLD" if _SCOPE_CONFLICT_CODES.intersection(contradicting_codes)
                else _DISPOSITION.get(match_class)
            )
            if (
                match_class not in _DISPOSITION
                or row.get("method") not in _METHODS_BY_CLASS[match_class]
                or row.get("disposition") != disposition
                or (row.get("proposition_cluster_id") is not None) !=
                   (disposition == "PROPOSE_CLUSTER")
            ):
                raise ValueError("STUDIO_CANDIDATE_MATCH_CLASS_INVALID")
            _validate_feature_semantics(
                match_class, row["method"], supporting_codes, contradicting_codes,
            )
            results.append({
                "result_id": result_id,
                "target_id": target_id,
                "target_type": target_type,
                "match_class": match_class,
                "matching_method": row["method"],
                "suggested_disposition": disposition,
                "supporting_feature_codes": supporting_codes,
                "contradicting_feature_codes": contradicting_codes,
                "promotion_enabled": False,
            })
    except (ValueError, TypeError):
        raise
    except Exception:
        raise RuntimeError("STUDIO_CANDIDATE_MATCH_STORE_UNAVAILABLE") from None

    return {
        "contract_version": STUDIO_CANDIDATE_REVIEW_VERSION,
        "matching_version": MATCHING_VERSION,
        "run_id": run_id,
        "claim_candidate_id": claim_candidate_id,
        "input_fingerprint": fingerprint,
        "currentness": "UNVERIFIED",
        "review_authority": False,
        "publication_authority": False,
        "private_only": True,
        "results": results,
    }


__all__ = ["STUDIO_CANDIDATE_REVIEW_VERSION", "inspect_candidate_match_run"]
