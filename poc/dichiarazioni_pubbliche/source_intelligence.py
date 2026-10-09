from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dichiarazioni_pubbliche.domain_vocabulary import ClaimType
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_INTELLIGENCE = ROOT / "config" / "source-intelligence.v1.json"
DEFAULT_REQUIREMENTS = ROOT / "config" / "evidence-requirements.v1.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "config" / "evidence-sources.v1.json"
DEFAULT_SOURCE_REGISTRY = ROOT / "config" / "source-registry.v1.json"

SOURCE_INTELLIGENCE_VERSION = "source-intelligence-v1"
EVIDENCE_REQUIREMENTS_VERSION = "evidence-requirements-v1"
ASSESSMENT_VERSION = "evidence-set-assessment-v1"

EVIDENCE_ROLES = (
    "PRIMARY_RECORD",
    "OFFICIAL_STATISTICS",
    "AUTHENTIC_LEGAL_TEXT",
    "OFFICIAL_PROCEDURAL_RECORD",
    "FIRST_PARTY_STATEMENT",
    "INDEPENDENT_REPORTING",
    "EXPERT_SYNTHESIS",
    "ARCHIVE_COPY",
    "SECONDARY_REFERENCE",
)

SOURCE_RELATION_TYPES = (
    "DERIVED_FROM",
    "REPRINTS",
    "SYNDICATED_FROM",
    "MIRRORS",
    "ARCHIVES_COPY_OF",
    "OFFICIAL_RELEASE_OF",
    "SUMMARIZES",
    "INDEPENDENT_OF",
    "UNKNOWN_RELATION",
)

DERIVATIVE_RELATIONS = frozenset(
    {
        "DERIVED_FROM",
        "REPRINTS",
        "SYNDICATED_FROM",
        "MIRRORS",
        "ARCHIVES_COPY_OF",
        "OFFICIAL_RELEASE_OF",
        "SUMMARIZES",
    }
)

ASSESSMENT_STATUSES = (
    "SUFFICIENT_FOR_RULE",
    "INSUFFICIENT_PRIMARY_SOURCE",
    "INSUFFICIENT_INDEPENDENCE",
    "TEMPORAL_MISMATCH",
    "SCOPE_MISMATCH",
    "CONFLICTING_EVIDENCE",
    "ACCESS_OR_RIGHTS_BLOCKED",
    "UNRESOLVED_SOURCE_IDENTITY",
    "UNRESOLVED_DERIVATION",
    "NEEDS_REVIEW",
)

BLOCKING_RIGHTS = frozenset(
    {
        "BLOCKED",
        "FORBIDDEN",
        "LEGAL_HOLD",
        "RIGHTS_HOLD",
        "TAKEDOWN_HOLD",
        "REMOVED",
    }
)


class SourceIntelligenceError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    encoded = value if isinstance(value, str) else _json(value)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\0".join(str(part) for part in parts)
    return f"{prefix}:" + hashlib.sha256(payload.encode()).hexdigest()


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value)
    try:
        # Keep the evaluator's calendar-day semantics for valid ISO timestamps,
        # but do not let arbitrary suffixes (or invalid clock times) disappear.
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return date.fromisoformat(raw)
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:Z|[+-]\d{2}:\d{2})?",
            raw,
        ):
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise SourceIntelligenceError(f"SOURCE_INTELLIGENCE_DATE_INVALID:{value}") from exc
    raise SourceIntelligenceError(f"SOURCE_INTELLIGENCE_DATE_INVALID:{value}")


@dataclass(frozen=True)
class AuthorityScope:
    id: str
    role: str
    jurisdiction: str | None = None
    organization: str | None = None
    record_type: str | None = None
    dataset_class: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    authenticity_basis: str | None = None
    canonical_locator: dict[str, Any] = field(default_factory=dict)
    supersession_policy: str | None = None
    limitations: str | None = None
    required_companion_role: str | None = None


@dataclass(frozen=True)
class SourceProfile:
    id: str
    registry_kind: str
    registry_source_id: str
    display_name: str
    profile_version: str
    registry_fingerprint: str
    access_status: str
    rights_status: str
    roles: tuple[str, ...] = ()
    authority_scopes: tuple[AuthorityScope, ...] = ()


@dataclass(frozen=True)
class RequirementRule:
    id: str
    ordinal: int
    kind: str
    required: bool
    parameters: dict[str, Any]
    coverage_need_enabled: bool
    rationale_code: str


@dataclass(frozen=True)
class RequirementProfile:
    id: str
    claim_type: str
    profile_version: str
    automatic_sufficiency_allowed: bool
    manual_review_required: bool
    config_fingerprint: str
    rules: tuple[RequirementRule, ...]


@dataclass(frozen=True)
class SourceRelation:
    from_profile_id: str
    to_profile_id: str
    relation_type: str
    status: str = "APPROVED"
    evidence_basis: dict[str, Any] = field(default_factory=dict)
    derivation_candidate_id: str | None = None


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    registry_source_id: str | None
    source_profile_id: str | None
    roles: tuple[str, ...]
    authority_scopes: tuple[AuthorityScope, ...]
    publication_date: str | None
    reference_period: str | None
    rights_status: str
    access_status: str
    independence_group: str
    valid_from: str | None = None
    valid_until: str | None = None
    record_status: str = "ACTIVE"
    metric: str | None = None
    unit: str | None = None
    dimensions: dict[str, Any] = field(default_factory=dict)
    value_numeric: float | None = None
    value_text: str | None = None
    status: str = "APPROVED"


@dataclass(frozen=True)
class CoverageNeedCandidate:
    requirement_kind: str
    reason: str
    required_roles: tuple[str, ...] = ()
    authority_scope: dict[str, Any] = field(default_factory=dict)
    temporal_constraints: dict[str, Any] = field(default_factory=dict)
    independence_requirement: int | None = None


@dataclass(frozen=True)
class EvidenceSetAssessment:
    id: str
    target_type: str
    target_id: str
    requirement_profile_id: str
    requirement_profile_version: str
    input_fingerprint: str
    status: str
    qualifying_evidence_ids: tuple[str, ...]
    rejected_evidence: tuple[dict[str, Any], ...]
    satisfied_rules: tuple[str, ...]
    missing_rules: tuple[str, ...]
    conflict_groups: tuple[dict[str, Any], ...]
    coverage_need_candidates: tuple[CoverageNeedCandidate, ...]
    rationale_codes: tuple[str, ...]
    assessment_version: str = ASSESSMENT_VERSION


@dataclass(frozen=True)
class SourceIntelligenceContract:
    source_version: str
    requirement_version: str
    profiles: tuple[SourceProfile, ...]
    requirement_profiles: tuple[RequirementProfile, ...]

    @property
    def evidence_profiles_by_registry_id(self) -> dict[str, SourceProfile]:
        return {
            item.registry_source_id: item
            for item in self.profiles
            if item.registry_kind == "EVIDENCE_REGISTRY"
        }

    @property
    def requirements_by_claim_type(self) -> dict[str, RequirementProfile]:
        return {item.claim_type: item for item in self.requirement_profiles}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise SourceIntelligenceError(f"SOURCE_INTELLIGENCE_CONFIG_INVALID:{path.name}")
    return payload


def _source_profile_id(registry_kind: str, registry_source_id: str, version: str) -> str:
    return _stable_id("source-profile", registry_kind, registry_source_id, version)


def _authority_scope(
    profile_id: str,
    raw: Mapping[str, Any],
    *,
    ordinal: int,
) -> AuthorityScope:
    role = str(raw.get("role") or "").strip()
    if role not in EVIDENCE_ROLES:
        raise SourceIntelligenceError(f"SOURCE_ROLE_INVALID:{role}")
    companion = str(raw.get("required_companion_role") or "").strip() or None
    if companion is not None and companion not in EVIDENCE_ROLES:
        raise SourceIntelligenceError(f"SOURCE_COMPANION_ROLE_INVALID:{companion}")
    locator = raw.get("canonical_locator") or {}
    if not isinstance(locator, dict):
        raise SourceIntelligenceError("SOURCE_CANONICAL_LOCATOR_INVALID")
    scope_payload = {
        key: raw.get(key)
        for key in (
            "role",
            "jurisdiction",
            "organization",
            "record_type",
            "dataset_class",
            "valid_from",
            "valid_until",
            "authenticity_basis",
            "canonical_locator",
            "supersession_policy",
            "limitations",
            "required_companion_role",
        )
    }
    return AuthorityScope(
        id=_stable_id("source-authority-scope", profile_id, ordinal, _sha(scope_payload)),
        role=role,
        jurisdiction=str(raw.get("jurisdiction") or "").strip() or None,
        organization=str(raw.get("organization") or "").strip() or None,
        record_type=str(raw.get("record_type") or "").strip() or None,
        dataset_class=str(raw.get("dataset_class") or "").strip() or None,
        valid_from=str(raw.get("valid_from") or "").strip() or None,
        valid_until=str(raw.get("valid_until") or "").strip() or None,
        authenticity_basis=str(raw.get("authenticity_basis") or "").strip() or None,
        canonical_locator=dict(locator),
        supersession_policy=str(raw.get("supersession_policy") or "").strip() or None,
        limitations=str(raw.get("limitations") or "").strip() or None,
        required_companion_role=companion,
    )


def load_source_intelligence_contract(
    *,
    source_intelligence_path: Path = DEFAULT_SOURCE_INTELLIGENCE,
    requirements_path: Path = DEFAULT_REQUIREMENTS,
    evidence_registry_path: Path = DEFAULT_EVIDENCE_REGISTRY,
    source_registry_path: Path = DEFAULT_SOURCE_REGISTRY,
) -> SourceIntelligenceContract:
    source_config = _load(source_intelligence_path)
    requirements_config = _load(requirements_path)
    evidence_registry = _load(evidence_registry_path)
    discovery_registry = _load(source_registry_path)
    if source_config.get("contract_version") != SOURCE_INTELLIGENCE_VERSION:
        raise SourceIntelligenceError("SOURCE_INTELLIGENCE_VERSION_MISMATCH")
    if requirements_config.get("contract_version") != EVIDENCE_REQUIREMENTS_VERSION:
        raise SourceIntelligenceError("EVIDENCE_REQUIREMENTS_VERSION_MISMATCH")

    evidence_by_id = {
        str(row.get("id") or ""): row for row in evidence_registry.get("sources") or []
    }
    semantic_by_id = {
        str(row.get("registry_source_id") or ""): row
        for row in source_config.get("evidence_sources") or []
    }
    if not evidence_by_id or set(evidence_by_id) != set(semantic_by_id):
        missing = sorted(set(evidence_by_id) - set(semantic_by_id))
        extra = sorted(set(semantic_by_id) - set(evidence_by_id))
        raise SourceIntelligenceError(
            f"SOURCE_INTELLIGENCE_REGISTRY_COVERAGE_MISMATCH:missing={missing}:extra={extra}"
        )

    profiles: list[SourceProfile] = []
    for registry_source_id in sorted(evidence_by_id):
        registry_row = evidence_by_id[registry_source_id]
        semantic = semantic_by_id[registry_source_id]
        roles = tuple(dict.fromkeys(str(item) for item in semantic.get("roles") or []))
        if not roles or any(role not in EVIDENCE_ROLES for role in roles):
            raise SourceIntelligenceError(
                f"SOURCE_INTELLIGENCE_ROLE_SET_INVALID:{registry_source_id}"
            )
        profile_id = _source_profile_id(
            "EVIDENCE_REGISTRY", registry_source_id, SOURCE_INTELLIGENCE_VERSION
        )
        scopes = tuple(
            _authority_scope(profile_id, raw, ordinal=ordinal)
            for ordinal, raw in enumerate(semantic.get("authority_scopes") or [])
        )
        fingerprint = _sha(
            {
                "registry": registry_row,
                "semantic": semantic,
                "version": SOURCE_INTELLIGENCE_VERSION,
            }
        )
        profiles.append(
            SourceProfile(
                id=profile_id,
                registry_kind="EVIDENCE_REGISTRY",
                registry_source_id=registry_source_id,
                display_name=str(
                    registry_row.get("publisher") or registry_source_id
                ).strip(),
                profile_version=SOURCE_INTELLIGENCE_VERSION,
                registry_fingerprint=fingerprint,
                access_status="AVAILABLE",
                rights_status=str(registry_row.get("rights_status") or "UNKNOWN"),
                roles=roles,
                authority_scopes=scopes,
            )
        )

    for registry_row in sorted(
        discovery_registry.get("sources") or [], key=lambda item: str(item.get("id") or "")
    ):
        registry_source_id = str(registry_row.get("id") or "").strip()
        if not registry_source_id:
            raise SourceIntelligenceError("DISCOVERY_SOURCE_ID_REQUIRED")
        profile_id = _source_profile_id(
            "DISCOVERY_REGISTRY", registry_source_id, SOURCE_INTELLIGENCE_VERSION
        )
        profiles.append(
            SourceProfile(
                id=profile_id,
                registry_kind="DISCOVERY_REGISTRY",
                registry_source_id=registry_source_id,
                display_name=str(registry_row.get("name") or registry_source_id).strip(),
                profile_version=SOURCE_INTELLIGENCE_VERSION,
                registry_fingerprint=_sha(
                    {
                        "registry": registry_row,
                        "version": SOURCE_INTELLIGENCE_VERSION,
                    }
                ),
                access_status="DISCOVERY_ONLY",
                rights_status="UNKNOWN",
            )
        )

    requirement_profiles: list[RequirementProfile] = []
    seen_claim_types: set[str] = set()
    all_claim_types = {item.value for item in ClaimType}
    for group in requirements_config.get("profile_groups") or []:
        group_name = str(group.get("name") or "").strip()
        if not group_name:
            raise SourceIntelligenceError("EVIDENCE_REQUIREMENT_GROUP_NAME_REQUIRED")
        raw_rules = group.get("rules") or []
        if not isinstance(raw_rules, list) or not raw_rules:
            raise SourceIntelligenceError(
                f"EVIDENCE_REQUIREMENT_RULES_REQUIRED:{group_name}"
            )
        for claim_type in group.get("claim_types") or []:
            claim_type = str(claim_type)
            if claim_type not in all_claim_types:
                raise SourceIntelligenceError(
                    f"EVIDENCE_REQUIREMENT_CLAIM_TYPE_UNKNOWN:{claim_type}"
                )
            if claim_type in seen_claim_types:
                raise SourceIntelligenceError(
                    f"EVIDENCE_REQUIREMENT_CLAIM_TYPE_DUPLICATE:{claim_type}"
                )
            seen_claim_types.add(claim_type)
            profile_payload = {
                "claim_type": claim_type,
                "group": group_name,
                "automatic_sufficiency_allowed": bool(
                    group.get("automatic_sufficiency_allowed", False)
                ),
                "manual_review_required": bool(group.get("manual_review_required", True)),
                "rules": raw_rules,
                "version": EVIDENCE_REQUIREMENTS_VERSION,
            }
            fingerprint = _sha(profile_payload)
            profile_id = _stable_id(
                "evidence-requirement-profile",
                claim_type,
                EVIDENCE_REQUIREMENTS_VERSION,
                fingerprint,
            )
            rules: list[RequirementRule] = []
            for ordinal, raw in enumerate(raw_rules):
                kind = str(raw.get("kind") or "").strip()
                if kind not in {
                    "ROLE_ANY",
                    "FIELD_MATCH",
                    "AUTHORITY_SCOPE",
                    "TEMPORAL_CUTOFF",
                    "MIN_INDEPENDENT_LINEAGES",
                    "CONFLICT_CHECK",
                    "HUMAN_REVIEW",
                }:
                    raise SourceIntelligenceError(
                        f"EVIDENCE_REQUIREMENT_RULE_KIND_INVALID:{kind}"
                    )
                parameters = raw.get("parameters") or {}
                if not isinstance(parameters, dict):
                    raise SourceIntelligenceError(
                        f"EVIDENCE_REQUIREMENT_PARAMETERS_INVALID:{claim_type}:{kind}"
                    )
                rules.append(
                    RequirementRule(
                        id=_stable_id(
                            "evidence-requirement-rule",
                            profile_id,
                            ordinal,
                            _sha(raw),
                        ),
                        ordinal=ordinal,
                        kind=kind,
                        required=bool(raw.get("required", True)),
                        parameters=dict(parameters),
                        coverage_need_enabled=bool(
                            raw.get("coverage_need_enabled", False)
                        ),
                        rationale_code=str(
                            raw.get("rationale_code") or f"{kind}_REQUIRED"
                        ),
                    )
                )
            requirement_profiles.append(
                RequirementProfile(
                    id=profile_id,
                    claim_type=claim_type,
                    profile_version=EVIDENCE_REQUIREMENTS_VERSION,
                    automatic_sufficiency_allowed=bool(
                        group.get("automatic_sufficiency_allowed", False)
                    ),
                    manual_review_required=bool(
                        group.get("manual_review_required", True)
                    ),
                    config_fingerprint=fingerprint,
                    rules=tuple(rules),
                )
            )
    if seen_claim_types != all_claim_types:
        raise SourceIntelligenceError(
            "EVIDENCE_REQUIREMENT_COVERAGE_INCOMPLETE:"
            + ",".join(sorted(all_claim_types - seen_claim_types))
        )
    return SourceIntelligenceContract(
        source_version=SOURCE_INTELLIGENCE_VERSION,
        requirement_version=EVIDENCE_REQUIREMENTS_VERSION,
        profiles=tuple(profiles),
        requirement_profiles=tuple(sorted(requirement_profiles, key=lambda item: item.claim_type)),
    )


def evidence_item_from_row(
    row: Mapping[str, Any],
    contract: SourceIntelligenceContract,
) -> EvidenceItem:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    registry_source_id = str(
        row.get("source_id") or metadata.get("evidence_source_id") or ""
    ).strip() or None
    profile = (
        contract.evidence_profiles_by_registry_id.get(registry_source_id)
        if registry_source_id
        else None
    )
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), Mapping) else {}
    independence_group = str(row.get("independence_group") or "").strip()
    if not independence_group:
        independence_group = (
            f"source:{registry_source_id}" if registry_source_id else f"evidence:{row.get('evidence_id')}"
        )
    return EvidenceItem(
        evidence_id=str(row.get("evidence_id") or row.get("id") or "").strip(),
        registry_source_id=registry_source_id,
        source_profile_id=profile.id if profile else None,
        roles=profile.roles if profile else (),
        authority_scopes=profile.authority_scopes if profile else (),
        publication_date=str(row.get("publication_date") or "").strip() or None,
        reference_period=str(row.get("reference_period") or "").strip() or None,
        rights_status=str(row.get("rights_status") or "UNKNOWN").strip() or "UNKNOWN",
        access_status=profile.access_status if profile else "UNKNOWN",
        independence_group=independence_group,
        valid_from=str(row.get("valid_from") or "").strip() or None,
        valid_until=str(row.get("valid_until") or "").strip() or None,
        record_status=str(row.get("record_status") or "ACTIVE").strip() or "ACTIVE",
        metric=str(row.get("metric") or "").strip() or None,
        unit=str(row.get("unit") or "").strip() or None,
        dimensions=dict(dimensions),
        value_numeric=(
            None if row.get("value_numeric") is None else float(row.get("value_numeric"))
        ),
        value_text=str(row.get("value_text") or "").strip() or None,
        status=str(row.get("status") or "APPROVED"),
    )


def _scope_matches(
    scope: AuthorityScope,
    expected: Mapping[str, Any],
    fields: Sequence[str],
) -> bool:
    for field_name in fields:
        wanted = str(expected.get(field_name) or "").strip()
        if not wanted:
            continue
        actual = str(getattr(scope, field_name, None) or "").strip()
        if not actual or actual.casefold() != wanted.casefold():
            return False
    return True


def _scope_temporally_applicable(scope: AuthorityScope, cutoff: date | None) -> bool:
    if not scope.valid_from and not scope.valid_until:
        return True
    if cutoff is None:
        return False
    valid_from = _iso_date(scope.valid_from)
    valid_until = _iso_date(scope.valid_until)
    # Effective intervals follow [valid_from, valid_until), matching DP-227.
    return ((valid_from is None or valid_from <= cutoff)
            and (valid_until is None or cutoff < valid_until))


def _field_value(item: EvidenceItem, name: str) -> str | None:
    if name in {"metric", "unit", "reference_period"}:
        value = getattr(item, name)
        return str(value) if value is not None else None
    value = item.dimensions.get(name)
    return str(value) if value is not None else None


def _lineage_groups(
    evidence: Sequence[EvidenceItem],
    relations: Sequence[SourceRelation],
) -> tuple[dict[str, str], bool]:
    parents: dict[str, str] = {}

    def find(value: str) -> str:
        parents.setdefault(value, value)
        if parents[value] != value:
            parents[value] = find(parents[value])
        return parents[value]

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parents[max(a, b)] = min(a, b)

    for item in evidence:
        find(item.independence_group)
    profile_to_groups: dict[str, set[str]] = {}
    for item in evidence:
        if item.source_profile_id:
            profile_to_groups.setdefault(item.source_profile_id, set()).add(
                item.independence_group
            )
    relevant_profiles = set(profile_to_groups)
    unresolved_relation = False
    for relation in relations:
        if (
            relation.from_profile_id not in relevant_profiles
            or relation.to_profile_id not in relevant_profiles
        ):
            continue
        if relation.status != "APPROVED":
            if relation.status == "CANDIDATE":
                unresolved_relation = True
            continue
        if relation.relation_type == "UNKNOWN_RELATION":
            unresolved_relation = True
            continue
        if relation.relation_type == "INDEPENDENT_OF":
            if not relation.evidence_basis:
                unresolved_relation = True
            continue
        if relation.relation_type not in DERIVATIVE_RELATIONS:
            continue
        for left in profile_to_groups.get(relation.from_profile_id, set()):
            for right in profile_to_groups.get(relation.to_profile_id, set()):
                union(left, right)
    return ({group: find(group) for group in parents}, unresolved_relation)


def _conflicts(items: Sequence[EvidenceItem]) -> tuple[dict[str, Any], ...]:
    buckets: dict[tuple[str, str, str], list[EvidenceItem]] = {}
    for item in items:
        if item.value_numeric is None and item.value_text is None:
            continue
        key = (
            item.metric or "",
            item.unit or "",
            item.reference_period or "",
        )
        buckets.setdefault(key, []).append(item)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(buckets.items()):
        values = {
            ("numeric", str(Decimal(str(row.value_numeric)).normalize()))
            if row.value_numeric is not None
            else ("text", str(row.value_text).strip().casefold())
            for row in rows
        }
        if len(values) > 1:
            output.append(
                {
                    "metric": key[0] or None,
                    "unit": key[1] or None,
                    "reference_period": key[2] or None,
                    "evidence_ids": sorted(row.evidence_id for row in rows),
                    "values": sorted([list(value) for value in values]),
                }
            )
    return tuple(output)


def assess_evidence_set(
    *,
    target_type: str,
    target_id: str,
    claim_type: str,
    statement_date: str | None,
    claim_requirements: Mapping[str, Any],
    evidence: Iterable[EvidenceItem],
    contract: SourceIntelligenceContract,
    relations: Sequence[SourceRelation] = (),
) -> EvidenceSetAssessment:
    if target_type not in {"ATOMIC_CLAIM", "CLAIM_CANDIDATE"}:
        raise SourceIntelligenceError("EVIDENCE_ASSESSMENT_TARGET_TYPE_INVALID")
    profile = contract.requirements_by_claim_type.get(str(claim_type))
    if profile is None:
        raise SourceIntelligenceError(f"EVIDENCE_REQUIREMENT_PROFILE_MISSING:{claim_type}")
    rows = tuple(sorted(evidence, key=lambda item: item.evidence_id))
    approved = tuple(item for item in rows if item.status == "APPROVED")
    rejected: list[dict[str, Any]] = []
    qualified = list(approved)
    satisfied: list[str] = []
    missing: list[str] = []
    needs: list[CoverageNeedCandidate] = []
    rationale: list[str] = []
    status: str | None = None

    unresolved_identity = [item for item in qualified if item.source_profile_id is None]
    if unresolved_identity:
        for item in unresolved_identity:
            rejected.append(
                {"evidence_id": item.evidence_id, "reason": "UNRESOLVED_SOURCE_IDENTITY"}
            )
        qualified = [item for item in qualified if item.source_profile_id is not None]
        status = "UNRESOLVED_SOURCE_IDENTITY"
        rationale.append("UNRESOLVED_SOURCE_IDENTITY")

    blocked = [
        item
        for item in qualified
        if item.access_status == "BLOCKED" or item.rights_status.upper() in BLOCKING_RIGHTS
    ]
    if blocked:
        for item in blocked:
            rejected.append(
                {"evidence_id": item.evidence_id, "reason": "ACCESS_OR_RIGHTS_BLOCKED"}
            )
        qualified = [item for item in qualified if item not in blocked]
        if status is None:
            status = "ACCESS_OR_RIGHTS_BLOCKED"
            rationale.append("ACCESS_OR_RIGHTS_BLOCKED")

    lineage_map, unresolved_derivation = _lineage_groups(qualified, relations)
    if unresolved_derivation and status is None:
        status = "UNRESOLVED_DERIVATION"
        rationale.append("UNRESOLVED_DERIVATION")

    for rule in profile.rules:
        rule_ok = True
        if rule.kind == "ROLE_ANY":
            wanted = tuple(str(value) for value in rule.parameters.get("roles") or [])
            matching = [item for item in qualified if set(item.roles) & set(wanted)]
            rule_ok = bool(matching)
            if rule_ok:
                qualified = matching
            elif rule.coverage_need_enabled:
                needs.append(
                    CoverageNeedCandidate(
                        requirement_kind=rule.kind,
                        reason=rule.rationale_code,
                        required_roles=wanted,
                    )
                )
            if not rule_ok and status is None:
                status = "INSUFFICIENT_PRIMARY_SOURCE"
        elif rule.kind == "FIELD_MATCH":
            fields = tuple(str(value) for value in rule.parameters.get("fields") or [])
            expected_fields = {
                name: str(claim_requirements.get(name) or "").strip()
                for name in fields
                if str(claim_requirements.get(name) or "").strip()
            }
            if expected_fields:
                matching = [
                    item
                    for item in qualified
                    if all(
                        (_field_value(item, name) or "").casefold()
                        == expected.casefold()
                        for name, expected in expected_fields.items()
                    )
                ]
                rule_ok = bool(matching)
                if rule_ok:
                    qualified = matching
                else:
                    for item in qualified:
                        rejected.append(
                            {"evidence_id": item.evidence_id, "reason": "SCOPE_MISMATCH"}
                        )
                    if rule.coverage_need_enabled:
                        needs.append(
                            CoverageNeedCandidate(
                                requirement_kind=rule.kind,
                                reason=rule.rationale_code,
                                authority_scope=expected_fields,
                            )
                        )
                    if status is None:
                        non_temporal = {
                            name: expected
                            for name, expected in expected_fields.items()
                            if name != "reference_period"
                        }
                        scope_matches = [
                            item
                            for item in qualified
                            if all(
                                (_field_value(item, name) or "").casefold()
                                == expected.casefold()
                                for name, expected in non_temporal.items()
                            )
                        ]
                        if (
                            "reference_period" in expected_fields
                            and scope_matches
                            and all(
                                (_field_value(item, "reference_period") or "").casefold()
                                != expected_fields["reference_period"].casefold()
                                for item in scope_matches
                            )
                        ):
                            status = "TEMPORAL_MISMATCH"
                        else:
                            status = "SCOPE_MISMATCH"
        elif rule.kind == "AUTHORITY_SCOPE":
            fields = tuple(str(value) for value in rule.parameters.get("match") or [])
            required_fields_present = all(
                str(claim_requirements.get(name) or "").strip() for name in fields
            )
            # Bind the scope to its preceding role requirement, not to every
            # ROLE_ANY rule in the profile: two independent required role
            # groups need not share one impossible intersection role.
            preceding_required_roles: set[str] | None = None
            for earlier in profile.rules:
                if earlier is rule:
                    break
                if earlier.kind == "ROLE_ANY" and earlier.required:
                    preceding_required_roles = set(
                        str(role) for role in earlier.parameters.get("roles") or []
                    )
            cutoff = _iso_date(statement_date)
            scope_matched = [
                (item, scope)
                for item in qualified
                for scope in item.authority_scopes
                if (required_fields_present
                    and scope.role in item.roles
                    and (preceding_required_roles is None
                         or scope.role in preceding_required_roles)
                    and _scope_matches(scope, claim_requirements, fields))
            ]
            matching = [
                item
                for item in qualified
                if any(candidate is item and _scope_temporally_applicable(scope, cutoff)
                       for candidate, scope in scope_matched)
            ]
            rule_ok = bool(matching)
            if rule_ok:
                qualified = matching
            else:
                temporal_only = bool(scope_matched)
                if temporal_only:
                    rejected.extend(
                        {"evidence_id": item.evidence_id,
                         "reason": "AUTHORITY_SCOPE_TEMPORAL_MISMATCH"}
                        for item in qualified
                        if any(candidate is item for candidate, _ in scope_matched)
                    )
                if rule.coverage_need_enabled:
                    needs.append(
                        CoverageNeedCandidate(
                            requirement_kind=rule.kind,
                            reason=rule.rationale_code,
                            authority_scope={
                                name: claim_requirements.get(name)
                                for name in fields
                                if claim_requirements.get(name) is not None
                            },
                        )
                    )
                if status is None:
                    status = "TEMPORAL_MISMATCH" if temporal_only else "SCOPE_MISMATCH"
        elif rule.kind == "TEMPORAL_CUTOFF":
            cutoff = _iso_date(statement_date)
            if cutoff is None and not bool(rule.parameters.get("allow_post_statement")):
                rule_ok = False
                rejected.extend(
                    {"evidence_id": item.evidence_id, "reason": "STATEMENT_DATE_REQUIRED"}
                    for item in qualified
                )
                if rule.coverage_need_enabled:
                    needs.append(
                        CoverageNeedCandidate(
                            requirement_kind=rule.kind,
                            reason=rule.rationale_code,
                            temporal_constraints={"statement_date_required": True},
                        )
                    )
                if status is None:
                    status = "TEMPORAL_MISMATCH"
            elif cutoff is not None and not bool(rule.parameters.get("allow_post_statement")):
                before: list[EvidenceItem] = []
                temporal_rejections: list[tuple[EvidenceItem, str]] = []
                for item in qualified:
                    published = _iso_date(item.publication_date)
                    if published is None or published > cutoff:
                        temporal_rejections.append(
                            (item, "POST_STATEMENT_EVIDENCE")
                        )
                        continue
                    valid_from = _iso_date(item.valid_from)
                    valid_until = _iso_date(item.valid_until)
                    if valid_from is not None and cutoff < valid_from:
                        temporal_rejections.append(
                            (item, "VERSION_NOT_YET_EFFECTIVE")
                        )
                        continue
                    # DP-227 uses [valid_from, valid_until) semantics.
                    if valid_until is not None and cutoff >= valid_until:
                        temporal_rejections.append(
                            (item, "VERSION_NO_LONGER_EFFECTIVE")
                        )
                        continue
                    if (
                        item.record_status in {"SUPERSEDED", "RETIRED", "EXPIRED"}
                        and valid_until is None
                    ):
                        temporal_rejections.append(
                            (item, "SUPERSEDED_VERSION_WITHOUT_VALID_UNTIL")
                        )
                        continue
                    before.append(item)
                rule_ok = bool(before)
                if rule_ok:
                    qualified = before
                else:
                    for item, reason in temporal_rejections:
                        rejected.append(
                            {"evidence_id": item.evidence_id, "reason": reason}
                        )
                    if rule.coverage_need_enabled:
                        needs.append(
                            CoverageNeedCandidate(
                                requirement_kind=rule.kind,
                                reason=rule.rationale_code,
                                temporal_constraints={
                                    "not_after": cutoff.isoformat(),
                                    "effective_at": cutoff.isoformat(),
                                },
                            )
                        )
                    if status is None:
                        status = "TEMPORAL_MISMATCH"
        elif rule.kind == "MIN_INDEPENDENT_LINEAGES":
            minimum = int(rule.parameters.get("minimum") or 1)
            groups = {
                lineage_map.get(item.independence_group, item.independence_group)
                for item in qualified
            }
            rule_ok = len(groups) >= minimum
            if not rule_ok:
                if rule.coverage_need_enabled:
                    needs.append(
                        CoverageNeedCandidate(
                            requirement_kind=rule.kind,
                            reason=rule.rationale_code,
                            independence_requirement=minimum,
                        )
                    )
                if status is None:
                    status = "INSUFFICIENT_INDEPENDENCE"
        elif rule.kind == "CONFLICT_CHECK":
            conflicts = _conflicts(qualified)
            rule_ok = not conflicts
            if conflicts and status is None:
                status = "CONFLICTING_EVIDENCE"
        elif rule.kind == "HUMAN_REVIEW":
            rule_ok = False
            if status is None:
                status = "NEEDS_REVIEW"
        else:  # pragma: no cover - config validator keeps this unreachable.
            raise SourceIntelligenceError(f"EVIDENCE_REQUIREMENT_RULE_UNSUPPORTED:{rule.kind}")

        if rule_ok:
            satisfied.append(rule.id)
        elif rule.required:
            missing.append(rule.id)
            if rule.rationale_code not in rationale:
                rationale.append(rule.rationale_code)

    conflicts = _conflicts(qualified)
    if conflicts and status not in {
        "UNRESOLVED_SOURCE_IDENTITY",
        "ACCESS_OR_RIGHTS_BLOCKED",
        "UNRESOLVED_DERIVATION",
    }:
        status = "CONFLICTING_EVIDENCE"
        if "CONFLICTING_EVIDENCE" not in rationale:
            rationale.append("CONFLICTING_EVIDENCE")

    if status is None:
        if profile.manual_review_required or not profile.automatic_sufficiency_allowed:
            status = "NEEDS_REVIEW"
            rationale.append("MANUAL_REVIEW_REQUIRED")
        else:
            status = "SUFFICIENT_FOR_RULE"
            rationale.append("EVIDENCE_REQUIREMENTS_SATISFIED")

    input_payload = {
        "target_type": target_type,
        "target_id": target_id,
        "claim_type": claim_type,
        "statement_date": statement_date,
        "claim_requirements": dict(claim_requirements),
        "profile": profile.config_fingerprint,
        "evidence": [asdict(item) for item in rows],
        "relations": [asdict(item) for item in relations],
        "assessment_version": ASSESSMENT_VERSION,
    }
    fingerprint = _sha(input_payload)
    assessment_id = _stable_id(
        "evidence-set-assessment", target_type, target_id, profile.id, fingerprint
    )
    return EvidenceSetAssessment(
        id=assessment_id,
        target_type=target_type,
        target_id=target_id,
        requirement_profile_id=profile.id,
        requirement_profile_version=profile.profile_version,
        input_fingerprint=fingerprint,
        status=status,
        qualifying_evidence_ids=tuple(sorted(item.evidence_id for item in qualified)),
        rejected_evidence=tuple(
            sorted(rejected, key=lambda item: (str(item.get("evidence_id")), str(item.get("reason"))))
        ),
        satisfied_rules=tuple(satisfied),
        missing_rules=tuple(missing),
        conflict_groups=conflicts,
        coverage_need_candidates=tuple(needs),
        rationale_codes=tuple(dict.fromkeys(rationale)),
    )


class SourceIntelligenceStore(PsqlRuntime):
    def _assert_fingerprint(self, table: str, row_id: str, column: str, value: str) -> None:
        raw = self.run(
            f"SELECT COALESCE({column}, '') FROM {table} WHERE id=:'row_id';",
            row_id=row_id,
        )
        if raw and raw != value:
            raise SourceIntelligenceError(
                f"SOURCE_INTELLIGENCE_VERSION_DRIFT:{table}:{row_id}"
            )

    def sync_contract(self, contract: SourceIntelligenceContract) -> dict[str, int]:
        counts = {"profiles": 0, "roles": 0, "scopes": 0, "requirements": 0, "rules": 0}
        for profile in contract.profiles:
            self._assert_fingerprint(
                "source_profile", profile.id, "registry_fingerprint", profile.registry_fingerprint
            )
            self.run(
                """
                INSERT INTO source_profile (
                    id, source_id, registry_kind, registry_source_id, display_name, profile_version,
                    access_status, rights_status, registry_fingerprint, status, metadata
                ) VALUES (
                    :'id', (SELECT id FROM source WHERE id=:'registry_source_id'),
                    :'registry_kind', :'registry_source_id', :'display_name', :'profile_version',
                    :'access_status', :'rights_status', :'registry_fingerprint', 'ACTIVE', '{}'::jsonb
                ) ON CONFLICT (id) DO NOTHING;
                """,
                id=profile.id,
                registry_kind=profile.registry_kind,
                registry_source_id=profile.registry_source_id,
                display_name=profile.display_name,
                profile_version=profile.profile_version,
                access_status=profile.access_status,
                rights_status=profile.rights_status,
                registry_fingerprint=profile.registry_fingerprint,
            )
            counts["profiles"] += 1
            for role in profile.roles:
                role_id = _stable_id("source-evidence-role", profile.id, role, profile.profile_version)
                self.run(
                    """
                    INSERT INTO source_evidence_role (
                        id, source_profile_id, evidence_role, basis, role_version, status, metadata
                    ) VALUES (
                        :'id', :'source_profile_id', :'evidence_role', 'CONFIG_VERSIONED',
                        :'role_version', 'ACTIVE', '{}'::jsonb
                    ) ON CONFLICT (id) DO NOTHING;
                    """,
                    id=role_id,
                    source_profile_id=profile.id,
                    evidence_role=role,
                    role_version=profile.profile_version,
                )
                counts["roles"] += 1
            for scope in profile.authority_scopes:
                self.run(
                    """
                    INSERT INTO source_authority_scope (
                        id, source_profile_id, evidence_role, jurisdiction, organization_ref,
                        record_type, dataset_class, valid_from, valid_until, authenticity_basis,
                        canonical_locator, supersession_policy, limitations, required_companion_role,
                        scope_version, status, metadata
                    ) VALUES (
                        :'id', :'source_profile_id', :'evidence_role', NULLIF(:'jurisdiction',''),
                        NULLIF(:'organization_ref',''), NULLIF(:'record_type',''),
                        NULLIF(:'dataset_class',''), NULLIF(:'valid_from','')::date,
                        NULLIF(:'valid_until','')::date, NULLIF(:'authenticity_basis',''),
                        :'canonical_locator'::jsonb, NULLIF(:'supersession_policy',''),
                        NULLIF(:'limitations',''), NULLIF(:'required_companion_role',''),
                        :'scope_version', 'ACTIVE', '{}'::jsonb
                    ) ON CONFLICT (id) DO NOTHING;
                    """,
                    id=scope.id,
                    source_profile_id=profile.id,
                    evidence_role=scope.role,
                    jurisdiction=scope.jurisdiction or "",
                    organization_ref=scope.organization or "",
                    record_type=scope.record_type or "",
                    dataset_class=scope.dataset_class or "",
                    valid_from=scope.valid_from or "",
                    valid_until=scope.valid_until or "",
                    authenticity_basis=scope.authenticity_basis or "",
                    canonical_locator=_json(scope.canonical_locator),
                    supersession_policy=scope.supersession_policy or "",
                    limitations=scope.limitations or "",
                    required_companion_role=scope.required_companion_role or "",
                    scope_version=profile.profile_version,
                )
                counts["scopes"] += 1
        for profile in contract.requirement_profiles:
            self._assert_fingerprint(
                "evidence_requirement_profile",
                profile.id,
                "config_fingerprint",
                profile.config_fingerprint,
            )
            self.run(
                """
                INSERT INTO evidence_requirement_profile (
                    id, claim_type, jurisdiction, domain, profile_version,
                    automatic_sufficiency_allowed, manual_review_required,
                    config_fingerprint, status, metadata
                ) VALUES (
                    :'id', :'claim_type', NULL, NULL, :'profile_version',
                    :'automatic_sufficiency_allowed'::boolean,
                    :'manual_review_required'::boolean,
                    :'config_fingerprint', 'ACTIVE', '{}'::jsonb
                ) ON CONFLICT (id) DO NOTHING;
                """,
                id=profile.id,
                claim_type=profile.claim_type,
                profile_version=profile.profile_version,
                automatic_sufficiency_allowed=str(profile.automatic_sufficiency_allowed).lower(),
                manual_review_required=str(profile.manual_review_required).lower(),
                config_fingerprint=profile.config_fingerprint,
            )
            counts["requirements"] += 1
            for rule in profile.rules:
                self.run(
                    """
                    INSERT INTO evidence_requirement_rule (
                        id, requirement_profile_id, ordinal, rule_kind, required,
                        parameters, coverage_need_enabled, rationale_code, status
                    ) VALUES (
                        :'id', :'requirement_profile_id', :'ordinal'::integer, :'rule_kind',
                        :'required'::boolean, :'parameters'::jsonb,
                        :'coverage_need_enabled'::boolean, :'rationale_code', 'ACTIVE'
                    ) ON CONFLICT (id) DO NOTHING;
                    """,
                    id=rule.id,
                    requirement_profile_id=profile.id,
                    ordinal=rule.ordinal,
                    rule_kind=rule.kind,
                    required=str(rule.required).lower(),
                    parameters=_json(rule.parameters),
                    coverage_need_enabled=str(rule.coverage_need_enabled).lower(),
                    rationale_code=rule.rationale_code,
                )
                counts["rules"] += 1
        return counts

    def source_relations(self) -> tuple[SourceRelation, ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'from_profile_id', from_source_profile_id,
                'to_profile_id', to_source_profile_id,
                'relation_type', relation_type,
                'status', status,
                'evidence_basis', evidence_basis,
                'derivation_candidate_id', derivation_candidate_id
            ) ORDER BY id)::text, '[]')
            FROM source_relation
            WHERE status IN ('CANDIDATE', 'APPROVED');
            """
        )
        rows = json.loads(raw or "[]")
        return tuple(SourceRelation(**row) for row in rows)

    def persist_assessment(self, assessment: EvidenceSetAssessment) -> bool:
        if assessment.status not in ASSESSMENT_STATUSES:
            raise SourceIntelligenceError("EVIDENCE_ASSESSMENT_STATUS_INVALID")
        atomic_claim_id = assessment.target_id if assessment.target_type == "ATOMIC_CLAIM" else ""
        claim_candidate_id = (
            assessment.target_id if assessment.target_type == "CLAIM_CANDIDATE" else ""
        )
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO evidence_set_assessment (
                    id, atomic_claim_id, claim_candidate_id, requirement_profile_id,
                    requirement_profile_version, input_fingerprint, assessment,
                    qualifying_evidence_ids, rejected_evidence, satisfied_rules,
                    missing_rules, conflict_groups, coverage_need_candidates,
                    rationale_codes, assessment_version, metadata
                ) VALUES (
                    :'id', NULLIF(:'atomic_claim_id',''), NULLIF(:'claim_candidate_id',''),
                    :'requirement_profile_id', :'requirement_profile_version', :'input_fingerprint',
                    :'assessment', :'qualifying_evidence_ids'::jsonb, :'rejected_evidence'::jsonb,
                    :'satisfied_rules'::jsonb, :'missing_rules'::jsonb, :'conflict_groups'::jsonb,
                    :'coverage_need_candidates'::jsonb, :'rationale_codes'::jsonb,
                    :'assessment_version', '{}'::jsonb
                ) ON CONFLICT (id) DO NOTHING
                RETURNING id
            ) SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            id=assessment.id,
            atomic_claim_id=atomic_claim_id,
            claim_candidate_id=claim_candidate_id,
            requirement_profile_id=assessment.requirement_profile_id,
            requirement_profile_version=assessment.requirement_profile_version,
            input_fingerprint=assessment.input_fingerprint,
            assessment=assessment.status,
            qualifying_evidence_ids=_json(list(assessment.qualifying_evidence_ids)),
            rejected_evidence=_json(list(assessment.rejected_evidence)),
            satisfied_rules=_json(list(assessment.satisfied_rules)),
            missing_rules=_json(list(assessment.missing_rules)),
            conflict_groups=_json(list(assessment.conflict_groups)),
            coverage_need_candidates=_json(
                [asdict(item) for item in assessment.coverage_need_candidates]
            ),
            rationale_codes=_json(list(assessment.rationale_codes)),
            assessment_version=assessment.assessment_version,
        )
        return raw.lower() in {"t", "true", "1"}


__all__ = [
    "ASSESSMENT_STATUSES",
    "ASSESSMENT_VERSION",
    "AuthorityScope",
    "CoverageNeedCandidate",
    "DERIVATIVE_RELATIONS",
    "EVIDENCE_REQUIREMENTS_VERSION",
    "EVIDENCE_ROLES",
    "EvidenceItem",
    "EvidenceSetAssessment",
    "RequirementProfile",
    "RequirementRule",
    "SOURCE_INTELLIGENCE_VERSION",
    "SOURCE_RELATION_TYPES",
    "SourceIntelligenceContract",
    "SourceIntelligenceError",
    "SourceIntelligenceStore",
    "SourceProfile",
    "SourceRelation",
    "assess_evidence_set",
    "evidence_item_from_row",
    "load_source_intelligence_contract",
]
