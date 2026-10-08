"""Read-only private Studio candidate-match inspection, not review authority.

Reads persisted DP-212 match results without re-running models, promoting a
candidate or claiming that the match run is current or reviewed.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Protocol

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


class CandidateMatchReader(Protocol):
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]: ...


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_CANDIDATE_REFERENCE_INVALID")
    return value


def _features(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 24:
        raise ValueError("STUDIO_CANDIDATE_FEATURES_INVALID")
    codes: list[str] = []
    for entry in value:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("code"), str):
            raise ValueError("STUDIO_CANDIDATE_FEATURE_INVALID")
        code = entry["code"]
        if not _CODE.fullmatch(code):
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
        fingerprint = run.get("input_fingerprint")
        if not isinstance(fingerprint, str) or not _HASH.fullmatch(fingerprint):
            raise ValueError("STUDIO_CANDIDATE_RUN_FINGERPRINT_INVALID")
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
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise ValueError("STUDIO_CANDIDATE_RESULT_INVALID")
            result_id = _safe_id(row.get("id"))
            if result_id in seen_ids or row.get("rank") != index:
                raise ValueError("STUDIO_CANDIDATE_RESULT_ORDER_INVALID")
            seen_ids.add(result_id)
            match_class = row.get("match_class")
            if (
                match_class not in _DISPOSITION
                or row.get("disposition") != _DISPOSITION[match_class]
                or row.get("target_type") not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}
            ):
                raise ValueError("STUDIO_CANDIDATE_MATCH_CLASS_INVALID")
            results.append({
                "result_id": result_id,
                "target_id": _safe_id(row.get("target_id")),
                "target_type": row["target_type"],
                "match_class": match_class,
                "suggested_disposition": row["disposition"],
                "supporting_feature_codes": _features(row.get("supporting_features")),
                "contradicting_feature_codes": _features(row.get("contradicting_features")),
                "promotion_enabled": False,
            })
    except (ValueError, TypeError):
        raise
    except Exception:
        raise RuntimeError("STUDIO_CANDIDATE_MATCH_STORE_UNAVAILABLE") from None

    return {
        "contract_version": STUDIO_CANDIDATE_REVIEW_VERSION,
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
