from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence


COVERAGE_NEED_VERSION = "coverage-need-v1"
DEFAULT_MAX_ATTEMPTS = 3

NEED_TYPES = frozenset(
    {
        "PRIMARY_SOURCE",
        "ORIGINAL_MEDIA",
        "OFFICIAL_RECORD",
        "EARLIER_VERSION",
        "INDEPENDENT_SOURCE",
        "TEMPORAL_GAP",
        "ATTRIBUTION_GAP",
        "OTHER",
    }
)


@dataclass(frozen=True)
class CoverageNeedSpec:
    id: str
    collection_id: str | None
    atomic_claim_id: str | None
    claim_candidate_id: str | None
    source_intelligence_assessment_id: str | None
    need_type: str
    requirement_kind: str
    requirement_fingerprint: str
    question: str
    required_roles: tuple[str, ...] = ()
    authority_scope: dict[str, Any] = field(default_factory=dict)
    temporal_constraints: dict[str, Any] = field(default_factory=dict)
    independence_requirement: int | None = None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    created_by: str = "SOURCE_INTELLIGENCE"
    metadata: dict[str, Any] = field(default_factory=dict)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode()).hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    return prefix + ":" + hashlib.sha256(
        "\x1f".join(str(part) for part in parts).encode()
    ).hexdigest()


def _need_type(candidate: Mapping[str, Any]) -> str:
    kind = str(candidate.get("requirement_kind") or "OTHER")
    roles = {str(item) for item in candidate.get("required_roles") or []}
    reason = str(candidate.get("reason") or "").upper()
    scope = candidate.get("authority_scope") or {}
    if kind == "MIN_INDEPENDENT_LINEAGES":
        return "INDEPENDENT_SOURCE"
    if kind == "TEMPORAL_CUTOFF":
        return "TEMPORAL_GAP"
    if kind == "FIELD_MATCH" and isinstance(scope, Mapping) and scope.get("reference_period"):
        return "TEMPORAL_GAP"
    if kind == "AUTHORITY_SCOPE" or roles & {
        "AUTHENTIC_LEGAL_TEXT",
        "OFFICIAL_PROCEDURAL_RECORD",
        "OFFICIAL_STATISTICS",
    }:
        return "OFFICIAL_RECORD"
    if roles & {"FIRST_PARTY_STATEMENT"} or "ATTRIBUT" in reason or "ORIGINAL" in reason:
        return "ATTRIBUTION_GAP" if "ATTRIBUT" in reason else "PRIMARY_SOURCE"
    if roles & {"PRIMARY_RECORD"}:
        return "PRIMARY_SOURCE"
    return "OTHER"


def _question(need_type: str, candidate: Mapping[str, Any]) -> str:
    roles = tuple(sorted(str(item) for item in candidate.get("required_roles") or []))
    reason = str(candidate.get("reason") or "MISSING_EVIDENCE_REQUIREMENT")
    if need_type == "INDEPENDENT_SOURCE":
        minimum = candidate.get("independence_requirement") or 1
        return f"Find at least {minimum} qualifying independent evidence lineage(s): {reason}."
    if need_type == "TEMPORAL_GAP":
        return f"Find evidence matching the required temporal scope/cutoff: {reason}."
    if need_type == "OFFICIAL_RECORD":
        role_text = ", ".join(roles) if roles else "the required official/authority scope"
        return f"Find the applicable official record for {role_text}: {reason}."
    if need_type in {"PRIMARY_SOURCE", "ATTRIBUTION_GAP", "ORIGINAL_MEDIA"}:
        role_text = ", ".join(roles) if roles else "the original/primary source"
        return f"Find {role_text}: {reason}."
    return f"Resolve the missing evidence requirement: {reason}."


def materialize_coverage_need_specs(
    *,
    target_type: str,
    target_id: str,
    source_intelligence_assessment_id: str,
    candidates: Iterable[Mapping[str, Any]],
    collection_ids: Sequence[str] = (),
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> tuple[CoverageNeedSpec, ...]:
    if target_type not in {"ATOMIC_CLAIM", "CLAIM_CANDIDATE"}:
        raise ValueError("COVERAGE_NEED_TARGET_TYPE_INVALID")
    if not 1 <= int(max_attempts) <= 10:
        raise ValueError("COVERAGE_NEED_MAX_ATTEMPTS_INVALID")
    scopes: tuple[str | None, ...] = tuple(dict.fromkeys(collection_ids)) or (None,)
    specs: list[CoverageNeedSpec] = []
    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        requirement_kind = str(candidate.get("requirement_kind") or "OTHER")
        need_type = _need_type(candidate)
        if need_type not in NEED_TYPES:
            raise ValueError("COVERAGE_NEED_TYPE_INVALID")
        normalized = {
            "need_type": need_type,
            "requirement_kind": requirement_kind,
            "reason": str(candidate.get("reason") or ""),
            "required_roles": sorted(str(item) for item in candidate.get("required_roles") or []),
            "authority_scope": dict(candidate.get("authority_scope") or {}),
            "temporal_constraints": dict(candidate.get("temporal_constraints") or {}),
            "independence_requirement": candidate.get("independence_requirement"),
            "version": COVERAGE_NEED_VERSION,
        }
        fingerprint = _sha(normalized)
        for collection_id in scopes:
            need_id = _stable_id(
                "coverage-need",
                COVERAGE_NEED_VERSION,
                collection_id or "",
                target_type,
                target_id,
                fingerprint,
            )
            specs.append(
                CoverageNeedSpec(
                    id=need_id,
                    collection_id=collection_id,
                    atomic_claim_id=target_id if target_type == "ATOMIC_CLAIM" else None,
                    claim_candidate_id=target_id if target_type == "CLAIM_CANDIDATE" else None,
                    source_intelligence_assessment_id=source_intelligence_assessment_id,
                    need_type=need_type,
                    requirement_kind=requirement_kind,
                    requirement_fingerprint=fingerprint,
                    question=_question(need_type, candidate),
                    required_roles=tuple(normalized["required_roles"]),
                    authority_scope=normalized["authority_scope"],
                    temporal_constraints=normalized["temporal_constraints"],
                    independence_requirement=(
                        None
                        if normalized["independence_requirement"] is None
                        else int(normalized["independence_requirement"])
                    ),
                    max_attempts=int(max_attempts),
                    metadata={"source_reason": normalized["reason"]},
                )
            )
    return tuple(specs)


def coverage_need_params(spec: CoverageNeedSpec) -> dict[str, str]:
    data = asdict(spec)
    output: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            output[key] = ""
        elif isinstance(value, (dict, list, tuple)):
            output[key] = _stable_json(value)
        else:
            output[key] = str(value)
    output["created_event_id"] = _stable_id("coverage-need-event", spec.id, "CREATED")
    output["observed_event_id"] = _stable_id(
        "coverage-need-event",
        spec.id,
        "OBSERVED_AGAIN",
        spec.source_intelligence_assessment_id or "",
    )
    return output


def coverage_need_event_id(
    need_id: str,
    event_type: str,
    *parts: object,
) -> str:
    return _stable_id("coverage-need-event", need_id, event_type, *parts)


def discovery_hint_for_need(row: Mapping[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    if status not in {"OPEN", "SEARCHING"}:
        raise ValueError("COVERAGE_NEED_NOT_SEARCHABLE")
    roles = list(row.get("required_roles") or [])
    scope = dict(row.get("authority_scope") or {})
    temporal = dict(row.get("temporal_constraints") or {})
    return {
        "coverage_need_id": str(row["id"]),
        "question": str(row.get("question") or ""),
        "need_type": str(row.get("need_type") or "OTHER"),
        "required_roles": roles,
        "authority_scope": scope,
        "temporal_constraints": temporal,
        "remaining_attempts": max(
            0, int(row.get("max_attempts") or 0) - int(row.get("attempt_count") or 0)
        ),
    }


__all__ = [
    "COVERAGE_NEED_VERSION",
    "CoverageNeedSpec",
    "DEFAULT_MAX_ATTEMPTS",
    "NEED_TYPES",
    "coverage_need_event_id",
    "coverage_need_params",
    "discovery_hint_for_need",
    "materialize_coverage_need_specs",
]
