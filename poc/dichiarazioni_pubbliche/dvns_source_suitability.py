from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Mapping

from dichiarazioni_pubbliche.dvns_structured_evidence import DvnsStructuredEvidenceImport
from dichiarazioni_pubbliche.source_intelligence import (
    BLOCKING_RIGHTS,
    EVIDENCE_ROLES,
    AuthorityScope,
    SourceProfile,
)
from dichiarazioni_pubbliche.structured_evidence import StructuredEvidenceValue


DVNS_DP215_BRIDGE_VERSION = "dvns-dp215-source-suitability-v1"
READY_FOR_DP215_ASSESSMENT = "READY_FOR_DP215_ASSESSMENT"
HELD = "HELD"

_DOMINANT_SOURCE_STATES = frozenset({"BLOCKED", "FAILED", "DEGRADED"})
_AUTHORITY_FIELDS = ("jurisdiction", "organization", "record_type", "dataset_class")
_RECORD_FIELDS = frozenset({"metric", "unit", "reference_period"})
_TEMPORAL_FIELDS = frozenset({"reference_period", "effective_at"})
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:[.,][0-9]+)?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?"
)


class DvnsSourceSuitabilityError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "DVNS_DP215_BRIDGE_ERROR").strip().upper()[:180]
        super().__init__(self.code)


@dataclass(frozen=True)
class DvnsCandidateEstablishmentMetadata:
    target_id: str
    record_id: str
    source_record_id: str
    source_profile_id: str
    evidence_role: str
    authority_scope_id: str
    candidate_state: str
    reason_codes: tuple[str, ...]
    metric_match: bool | None
    scope_match: bool | None
    temporal_match: bool | None
    value_present: bool | None
    bounded_establishment: tuple[tuple[str, str], ...]
    candidate_only: bool = True
    bridge_version: str = DVNS_DP215_BRIDGE_VERSION


@dataclass(frozen=True)
class DvnsCandidateSuitabilityBatch:
    target_id: str
    source_profile_id: str
    evidence_role: str
    authority_scope_id: str
    candidate_state: str
    blocking_reasons: tuple[str, ...]
    records: tuple[DvnsCandidateEstablishmentMetadata, ...]
    input_fingerprint: str
    candidate_only: bool = True
    bridge_version: str = DVNS_DP215_BRIDGE_VERSION


def _text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DvnsSourceSuitabilityError(f"DVNS_DP215_{name}_REQUIRED")
    return text


def _normalized_state(value: Any) -> str:
    return str(value or "").strip().upper()


def _date(value: Any, name: str) -> date:
    raw = _text(value, name)
    error_code = f"DVNS_DP215_{name}_INVALID"
    # A source's authority/cutoff must never be inferred from an ISO-looking
    # prefix of a malformed timestamp (or from implicit string coercion).
    if not isinstance(value, str) or raw != value:
        raise DvnsSourceSuitabilityError(error_code)
    try:
        if _ISO_DATE.fullmatch(raw):
            return date.fromisoformat(raw)
        if _ISO_TIMESTAMP.fullmatch(raw):
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise DvnsSourceSuitabilityError(error_code) from exc
    raise DvnsSourceSuitabilityError(error_code)


def _optional_date(value: Any, name: str) -> date | None:
    if value is None or value == "":
        return None
    return _date(value, name)


def _exact(left: Any, right: Any) -> bool:
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _sha(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_binding(
    source_profile: SourceProfile,
    evidence_role: str,
    authority_scope: AuthorityScope,
) -> str:
    role = _text(evidence_role, "EVIDENCE_ROLE")
    if role not in EVIDENCE_ROLES:
        raise DvnsSourceSuitabilityError("DVNS_DP215_EVIDENCE_ROLE_INVALID")
    if role not in source_profile.roles:
        raise DvnsSourceSuitabilityError("DVNS_DP215_ROLE_NOT_GRANTED_BY_PROFILE")
    if authority_scope not in source_profile.authority_scopes:
        raise DvnsSourceSuitabilityError("DVNS_DP215_SCOPE_NOT_GRANTED_BY_PROFILE")
    if authority_scope.role != role:
        raise DvnsSourceSuitabilityError("DVNS_DP215_SCOPE_ROLE_MISMATCH")
    return role


def _blocking_reasons(
    imported: DvnsStructuredEvidenceImport,
    source_profile: SourceProfile,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    fetch_state = _normalized_state(imported.normalized_batch.fetch_state)
    if fetch_state in _DOMINANT_SOURCE_STATES:
        reasons.add(f"DVNS_FETCH_{fetch_state}")

    imported_rights = _normalized_state(imported.rights_status)
    if imported_rights in BLOCKING_RIGHTS or imported_rights in _DOMINANT_SOURCE_STATES:
        reasons.add(f"DVNS_RIGHTS_{imported_rights}")

    availability = _normalized_state(imported.availability_status)
    if availability in _DOMINANT_SOURCE_STATES:
        reasons.add(f"DVNS_AVAILABILITY_{availability}")

    profile_rights = _normalized_state(source_profile.rights_status)
    if profile_rights in BLOCKING_RIGHTS or profile_rights in _DOMINANT_SOURCE_STATES:
        reasons.add(f"DP215_PROFILE_RIGHTS_{profile_rights}")

    profile_access = _normalized_state(source_profile.access_status)
    if profile_access in _DOMINANT_SOURCE_STATES:
        reasons.add(f"DP215_PROFILE_ACCESS_{profile_access}")

    return tuple(sorted(reasons))


def _bounded_establishment(
    value: StructuredEvidenceValue,
    evidence_role: str,
    authority_scope: AuthorityScope,
) -> tuple[tuple[str, str], ...]:
    fields: dict[str, str] = {
        "evidence_role": evidence_role,
        "authority_scope_id": authority_scope.id,
        "metric": value.metric,
    }
    if value.unit:
        fields["unit"] = value.unit
    if value.reference_period:
        fields["reference_period"] = value.reference_period
    if value.effective_from:
        fields["effective_from"] = value.effective_from
    if value.effective_to:
        fields["effective_to"] = value.effective_to
    for key, item in value.dimensions:
        fields[f"dimension.{key}"] = item
    for field_name in _AUTHORITY_FIELDS:
        item = getattr(authority_scope, field_name)
        if item:
            fields[f"authority.{field_name}"] = str(item)
    if authority_scope.valid_from:
        fields["authority.valid_from"] = authority_scope.valid_from
    if authority_scope.valid_until:
        fields["authority.valid_until"] = authority_scope.valid_until
    return tuple(sorted(fields.items()))


def _metric_matches(value: StructuredEvidenceValue, requirements: Mapping[str, Any]) -> bool:
    return _exact(value.metric, requirements.get("metric"))


def _scope_matches(
    value: StructuredEvidenceValue,
    authority_scope: AuthorityScope,
    requirements: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if requirements.get("unit") is not None and not _exact(value.unit, requirements.get("unit")):
        reasons.append("UNIT_MISMATCH")

    for field_name in _AUTHORITY_FIELDS:
        wanted = requirements.get(field_name)
        if wanted is None or not str(wanted).strip():
            continue
        if not _exact(getattr(authority_scope, field_name), wanted):
            reasons.append(f"AUTHORITY_{field_name.upper()}_MISMATCH")

    dimensions = dict(value.dimensions)
    reserved = _RECORD_FIELDS | _TEMPORAL_FIELDS | frozenset(_AUTHORITY_FIELDS)
    for key, wanted in sorted(requirements.items(), key=lambda pair: str(pair[0])):
        name = str(key)
        if name in reserved or wanted is None or not str(wanted).strip():
            continue
        if not _exact(dimensions.get(name), wanted):
            reasons.append(f"DIMENSION_{name.upper()}_MISMATCH")
    return not reasons, tuple(reasons)


def _temporal_matches(
    value: StructuredEvidenceValue,
    authority_scope: AuthorityScope,
    requirements: Mapping[str, Any],
    statement_date: str,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    cutoff = _date(statement_date, "STATEMENT_DATE")
    published = _optional_date(value.publication_date, "PUBLICATION_DATE")
    if published is None:
        reasons.append("PUBLICATION_DATE_MISSING")
    elif published > cutoff:
        reasons.append("POST_STATEMENT_EVIDENCE")

    wanted_period = requirements.get("reference_period")
    if wanted_period is not None and str(wanted_period).strip():
        if not _exact(value.reference_period, wanted_period):
            reasons.append("REFERENCE_PERIOD_MISMATCH")

    effective_at_raw = requirements.get("effective_at")
    effective_at = (
        _date(effective_at_raw, "EFFECTIVE_AT")
        if effective_at_raw is not None and effective_at_raw != ""
        else None
    )
    if effective_at is not None:
        effective_from = _optional_date(value.effective_from, "EFFECTIVE_FROM")
        effective_to = _optional_date(value.effective_to, "EFFECTIVE_TO")
        if effective_from is None and effective_to is None:
            reasons.append("EFFECTIVE_INTERVAL_MISSING")
        else:
            if effective_from is not None and effective_at < effective_from:
                reasons.append("EFFECTIVE_INTERVAL_MISMATCH")
            if effective_to is not None and effective_at >= effective_to:
                reasons.append("EFFECTIVE_INTERVAL_MISMATCH")

    authority_at = effective_at or cutoff
    scope_from = _optional_date(authority_scope.valid_from, "AUTHORITY_VALID_FROM")
    scope_until = _optional_date(authority_scope.valid_until, "AUTHORITY_VALID_UNTIL")
    if scope_from is not None and authority_at < scope_from:
        reasons.append("AUTHORITY_TEMPORAL_MISMATCH")
    if scope_until is not None and authority_at >= scope_until:
        reasons.append("AUTHORITY_TEMPORAL_MISMATCH")
    return not reasons, tuple(sorted(set(reasons)))


def derive_dvns_candidate_suitability(
    imported: DvnsStructuredEvidenceImport,
    *,
    target_id: str,
    statement_date: str,
    claim_requirements: Mapping[str, Any],
    source_profile: SourceProfile,
    evidence_role: str,
    authority_scope: AuthorityScope,
) -> DvnsCandidateSuitabilityBatch:
    target = _text(target_id, "TARGET_ID")
    _date(statement_date, "STATEMENT_DATE")
    if not isinstance(claim_requirements, Mapping):
        raise DvnsSourceSuitabilityError("DVNS_DP215_CLAIM_REQUIREMENTS_INVALID")
    metric = str(claim_requirements.get("metric") or "").strip()
    if not metric:
        raise DvnsSourceSuitabilityError("DVNS_DP215_METRIC_REQUIRED")

    role = _validate_binding(source_profile, evidence_role, authority_scope)
    blocking_reasons = _blocking_reasons(imported, source_profile)
    record_results: list[DvnsCandidateEstablishmentMetadata] = []
    for value in sorted(imported.normalized_batch.values, key=lambda item: item.record_id):
        establishment = _bounded_establishment(value, role, authority_scope)
        if blocking_reasons:
            record_results.append(
                DvnsCandidateEstablishmentMetadata(
                    target_id=target,
                    record_id=value.record_id,
                    source_record_id=value.source_record_id,
                    source_profile_id=source_profile.id,
                    evidence_role=role,
                    authority_scope_id=authority_scope.id,
                    candidate_state=HELD,
                    reason_codes=blocking_reasons,
                    metric_match=None,
                    scope_match=None,
                    temporal_match=None,
                    value_present=None,
                    bounded_establishment=establishment,
                )
            )
            continue

        metric_match = _metric_matches(value, claim_requirements)
        scope_match, scope_reasons = _scope_matches(value, authority_scope, claim_requirements)
        temporal_match, temporal_reasons = _temporal_matches(
            value,
            authority_scope,
            claim_requirements,
            statement_date,
        )
        value_present = value.value_state == "PRESENT"
        reasons: list[str] = []
        if not metric_match:
            reasons.append("METRIC_MISMATCH")
        reasons.extend(scope_reasons)
        reasons.extend(temporal_reasons)
        if not value_present:
            reasons.append(f"VALUE_STATE_{value.value_state}")
        state = READY_FOR_DP215_ASSESSMENT if not reasons else HELD
        record_results.append(
            DvnsCandidateEstablishmentMetadata(
                target_id=target,
                record_id=value.record_id,
                source_record_id=value.source_record_id,
                source_profile_id=source_profile.id,
                evidence_role=role,
                authority_scope_id=authority_scope.id,
                candidate_state=state,
                reason_codes=tuple(sorted(set(reasons))),
                metric_match=metric_match,
                scope_match=scope_match,
                temporal_match=temporal_match,
                value_present=value_present,
                bounded_establishment=establishment,
            )
        )

    batch_state = (
        READY_FOR_DP215_ASSESSMENT
        if record_results
        and not blocking_reasons
        and all(row.candidate_state == READY_FOR_DP215_ASSESSMENT for row in record_results)
        else HELD
    )
    fingerprint_payload = {
        "target_id": target,
        "statement_date": statement_date,
        "claim_requirements": dict(claim_requirements),
        "dvns_replay_id": imported.replay_id,
        "source_profile": {
            "id": source_profile.id,
            "profile_version": source_profile.profile_version,
            "registry_fingerprint": source_profile.registry_fingerprint,
        },
        "evidence_role": role,
        "authority_scope": asdict(authority_scope),
        "blocking_reasons": blocking_reasons,
        "records": [asdict(item) for item in record_results],
        "bridge_version": DVNS_DP215_BRIDGE_VERSION,
    }
    return DvnsCandidateSuitabilityBatch(
        target_id=target,
        source_profile_id=source_profile.id,
        evidence_role=role,
        authority_scope_id=authority_scope.id,
        candidate_state=batch_state,
        blocking_reasons=blocking_reasons,
        records=tuple(record_results),
        input_fingerprint=_sha(fingerprint_payload),
    )


__all__ = [
    "DVNS_DP215_BRIDGE_VERSION",
    "HELD",
    "READY_FOR_DP215_ASSESSMENT",
    "DvnsCandidateEstablishmentMetadata",
    "DvnsCandidateSuitabilityBatch",
    "DvnsSourceSuitabilityError",
    "derive_dvns_candidate_suitability",
]
