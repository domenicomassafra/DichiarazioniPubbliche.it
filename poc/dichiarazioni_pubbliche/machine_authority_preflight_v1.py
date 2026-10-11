"""DP-316: source-only immutable machine-authority *preflight*, never a signoff.

The source checkout has no independent off-DB machine principal, qualified
policy authority, trusted public-key register, signed receipt ledger, blind
gold adjudicator, or live DP-320 transaction/read fence. A hash, a local
preflight result, a model status, and the existing DP-311 *human* reviewer
identity authority cannot substitute for any of these.

Even a completely consistent snapshot therefore requires external decisions.
No function in this module issues a machine approval, clears human-only gates,
creates a release, or changes the legacy human publication path. In particular,
any caller-supplied claimed approval is treated as an adverse input.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from dichiarazioni_pubbliche.high_risk_assertion import (
    HIGH_RISK_ASSERTION_VERSION,
    HighRiskDecision,
    HighRiskSignals,
    RiskClass,
)
from dichiarazioni_pubbliche.publication_review_control import high_risk_binding_sha256
from dichiarazioni_pubbliche.publication_safety import (
    PUBLICATION_SAFETY_VERSION,
    PublicationSafetyResult,
)
from dichiarazioni_pubbliche.revocation_epoch_fence import (
    VERSION as FENCE_VERSION,
    MaterialEpoch,
    PublicationEpochTicket,
)
from dichiarazioni_pubbliche.verification_requirements_v1 import (
    VERSION as REQUIREMENT_VERSION,
    RequirementPreflight,
    select_requirement_profile,
)

MACHINE_AUTHORITY_PREFLIGHT_VERSION = "machine-authority-preflight-v1"
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RISK_CLASSES = frozenset({"STANDARD", "HIGH", "LEGAL"})

# A caller-supplied profile cannot delete baseline load-bearing references.
# Roles are deliberately coarse: the off-DB authority must verify each real
# referenced object and source lineage, not accept these labels at face value.
MACHINE_MATERIAL_ROLES = tuple(
    sorted(
        {
            "SOURCE_CAPTURE",
            "SOURCE_USE",
            "SOURCE_RIGHTS",
            "RIGHTS_DECISION",
            "PERSON",
            "ATTRIBUTION",
            "QUOTE",
            "CONTEXT",
            "PRIVACY",
            "OBSERVATION_SET",
            "EVIDENCE_SET",
            "VERIFIER_RESULT",
            "REQUIREMENT_RESULT",
            "SAFETY_RESULT",
            "HIGH_RISK_INPUT",
            "HIGH_RISK_RESULT",
            "RULE",
            "MODEL",
            "PROMPT",
            "CHALLENGER_PACKET",
            "GOLD_GATE",
            "QUALIFIED_POLICY",
            "PUBLICATION_POLICY",
            "MACHINE_PROFILE",
            "RELEASE_SCOPE",
            "CORRECTION_HEAD",
        }
    )
)


@dataclass(frozen=True)
class MachineAuthorityProfile:
    profile_ref: str
    profile_version: str
    claim_kind: str
    risk_class: str
    jurisdiction_ref: str
    policy_version: str
    requirement_rule_version: str


@dataclass(frozen=True)
class MachineDecisionReference:
    record_id: str
    record_version: str
    release_ref: str
    claim_kind: str
    risk_class: str
    jurisdiction_ref: str
    policy_version: str
    generator_run_ref: str
    generator_identity_ref: str
    generator_source_root_ref: str
    challenger_run_ref: str
    challenger_identity_ref: str
    challenger_source_root_ref: str
    rights_state: str
    correction_state: str
    challenger_state: str
    claimed_machine_approval: bool = False


@dataclass(frozen=True)
class MaterialBinding:
    role: str
    ref: str
    sha256: str
    epoch: int


@dataclass(frozen=True)
class MachineAuthoritySnapshot:
    profile: MachineAuthorityProfile
    decision: MachineDecisionReference
    materials: tuple[MaterialBinding, ...]
    fence: PublicationEpochTicket


@dataclass(frozen=True)
class MachineAuthorityPreflight:
    disposition: str
    reason_codes: tuple[str, ...]
    snapshot_sha256: str | None
    contract_version: str = MACHINE_AUTHORITY_PREFLIGHT_VERSION

    @property
    def machine_signoff(self) -> bool:
        """Always false: an immutable *consistency* result is not a signature."""
        return False

    @property
    def publication_authority(self) -> bool:
        return False

    @property
    def dispatch_authorized(self) -> bool:
        return False


def _ref(value: object) -> bool:
    return isinstance(value, str) and _REF.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _profile_ok(profile: object) -> bool:
    if not isinstance(profile, MachineAuthorityProfile):
        return False
    identifiers = (
        profile.profile_ref,
        profile.profile_version,
        profile.claim_kind,
        profile.jurisdiction_ref,
        profile.policy_version,
        profile.requirement_rule_version,
    )
    return (
        all(_ref(value) for value in identifiers)
        and profile.risk_class in _RISK_CLASSES
        and profile.requirement_rule_version == REQUIREMENT_VERSION
        and select_requirement_profile(profile.claim_kind) is not None
    )


def _decision_ok(decision: object) -> bool:
    if not isinstance(decision, MachineDecisionReference):
        return False
    values = (
        decision.record_id,
        decision.record_version,
        decision.release_ref,
        decision.claim_kind,
        decision.jurisdiction_ref,
        decision.policy_version,
        decision.generator_run_ref,
        decision.generator_identity_ref,
        decision.generator_source_root_ref,
        decision.challenger_run_ref,
        decision.challenger_identity_ref,
        decision.challenger_source_root_ref,
    )
    return (
        all(_ref(value) for value in values)
        and decision.risk_class in _RISK_CLASSES
        and decision.rights_state
        in {"CURRENT", "REVOKED", "EXPIRED", "HELD", "UNKNOWN"}
        and decision.correction_state in {"CLEAR", "PENDING", "SUPERSEDED", "REVOKED"}
        and decision.challenger_state in {"COMPLETED", "PENDING", "REVOKED"}
        and type(decision.claimed_machine_approval) is bool
    )


def _material_errors(materials: object) -> set[str]:
    if not isinstance(materials, tuple) or not 1 <= len(materials) <= 128:
        return {"MATERIAL_SET_INVALID"}
    if any(
        not isinstance(item, MaterialBinding)
        or not isinstance(item.role, str)
        or not _ref(item.ref)
        or not _sha(item.sha256)
        or type(item.epoch) is not int
        or item.epoch < 0
        for item in materials
    ):
        return {"MATERIAL_SET_INVALID"}
    roles = tuple(item.role for item in materials)
    errors: set[str] = set()
    if len(set(roles)) != len(roles):
        errors.add("MATERIAL_ROLE_DUPLICATE")
    if not set(MACHINE_MATERIAL_ROLES).issubset(roles):
        errors.add("REQUIRED_MATERIAL_ROLE_MISSING")
    if not set(roles).issubset(MACHINE_MATERIAL_ROLES):
        errors.add("MATERIAL_ROLE_UNKNOWN")
    if len({item.ref for item in materials}) != len(materials):
        errors.add("MATERIAL_DEPENDENCY_REF_DUPLICATE")
    if roles != tuple(sorted(roles)):
        errors.add("MATERIAL_ROLES_NOT_CANONICAL")
    return errors


def _fence_errors(snapshot: MachineAuthoritySnapshot) -> set[str]:
    """Check DP-320 ticket structure, NOT the real authority's current DB epoch.

    The ticket uses the existing DP-320 v1 canonical fingerprint. This digest
    can be recomputed by anyone and is expressly not a cryptographic signature.
    """
    fence = snapshot.fence
    if not isinstance(fence, PublicationEpochTicket) or fence.version != FENCE_VERSION:
        return {"FENCE_INTEGRITY_INVALID"}
    if not _ref(fence.release_id) or not _sha(fence.fingerprint):
        return {"FENCE_INTEGRITY_INVALID"}
    if not isinstance(fence.dependencies, tuple) or not fence.dependencies:
        return {"FENCE_INTEGRITY_INVALID"}
    if len(fence.dependencies) > 128:
        return {"FENCE_INTEGRITY_INVALID"}
    if any(
        not isinstance(item, MaterialEpoch)
        or not _ref(item.dependency_id)
        or not _sha(item.material_sha256)
        or type(item.epoch) is not int
        or item.epoch < 0
        for item in fence.dependencies
    ):
        return {"FENCE_INTEGRITY_INVALID"}
    if (
        tuple(sorted(fence.dependencies, key=lambda x: x.dependency_id))
        != fence.dependencies
    ):
        return {"FENCE_INTEGRITY_INVALID"}
    dependencies = [
        {
            "dependency_id": item.dependency_id,
            "epoch": item.epoch,
            "material_sha256": item.material_sha256,
        }
        for item in fence.dependencies
    ]
    if len({item["dependency_id"] for item in dependencies}) != len(dependencies):
        return {"FENCE_INTEGRITY_INVALID"}
    expected = _digest(
        {
            "version": FENCE_VERSION,
            "release": fence.release_id,
            "dependencies": dependencies,
        }
    )
    if (
        expected != fence.fingerprint
        or fence.release_id != snapshot.decision.release_ref
    ):
        return {"FENCE_INTEGRITY_INVALID"}
    return set()


def _fence_covers_materials(snapshot: MachineAuthoritySnapshot) -> bool:
    expected = {item.ref: (item.epoch, item.sha256) for item in snapshot.materials}
    seen = {
        item.dependency_id: (item.epoch, item.material_sha256)
        for item in snapshot.fence.dependencies
    }
    return expected == seen


def _high_risk_errors(
    risk_class: str, decision: HighRiskDecision
) -> tuple[set[str], set[str]]:
    """Distinguish legacy human review hold from substantive safety holds."""
    holds: set[str] = set()
    external: set[str] = set()
    if (
        not isinstance(decision, HighRiskDecision)
        or decision.version != HIGH_RISK_ASSERTION_VERSION
        or not isinstance(decision.signals, HighRiskSignals)
        or decision.signals.version != HIGH_RISK_ASSERTION_VERSION
        or not isinstance(decision.signals.risk_classes, tuple)
        or not isinstance(decision.signals.procedural_statuses, tuple)
        or type(decision.signals.allegation_framing) is not bool
        or not isinstance(decision.reason_codes, tuple)
        or not all(isinstance(code, str) for code in decision.reason_codes)
    ):
        return {"HIGH_RISK_RESULT_INVALID"}, external
    if risk_class == "STANDARD":
        if (
            decision.disposition != "STANDARD_REVIEW"
            or decision.signals.requires_escalation
        ):
            holds.add("HIGH_RISK_PROFILE_MISMATCH")
    else:
        if not decision.signals.requires_escalation:
            holds.add("HIGH_RISK_PROFILE_MISMATCH")
        if (
            risk_class == "LEGAL"
            and RiskClass.LEGAL_STATUS not in decision.signals.risk_classes
        ):
            holds.add("HIGH_RISK_PROFILE_MISMATCH")
        if (
            risk_class == "HIGH"
            and RiskClass.LEGAL_STATUS in decision.signals.risk_classes
        ):
            holds.add("HIGH_RISK_PROFILE_MISMATCH")
        human_only = {
            "HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",
            "HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED",
        }
        if decision.disposition == "HOLD_HIGH_RISK" and (
            decision.reason_codes and set(decision.reason_codes).issubset(human_only)
        ):
            external.add("LEGACY_HUMAN_REVIEW_NOT_MACHINE_SIGNOFF")
        elif decision.disposition == "ELIGIBLE_HIGH_RISK":
            # The old caller-supplied human approval flags remain untrusted for
            # machine signoff, even if they made the old decision ELIGIBLE.
            external.add("LEGACY_HUMAN_REVIEW_NOT_MACHINE_SIGNOFF")
        else:
            holds.add("HIGH_RISK_UPSTREAM_HOLD")
    return holds, external


def preflight_machine_authority(
    sealed: MachineAuthoritySnapshot,
    current: MachineAuthoritySnapshot,
    *,
    requirement: RequirementPreflight,
    publication_safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
) -> MachineAuthorityPreflight:
    """Deterministic local consistency gate; NEVER returns ELIGIBLE or a signoff.

    `sealed` and `current` are *caller-provided*. They are compared to expose
    obvious drift, but cannot prove a currently authorized owner, independent
    source, signed gold, challenger or live MiniPC epoch. A future integrator
    must resolve these through separately trusted external authorities and
    transactionally recheck at publication write AND final public read.
    """
    holds: set[str] = set()
    rechecks: set[str] = set()
    external: set[str] = set()
    if not isinstance(sealed, MachineAuthoritySnapshot) or not isinstance(
        current, MachineAuthoritySnapshot
    ):
        return MachineAuthorityPreflight("HOLD", ("MACHINE_SNAPSHOT_INVALID",), None)
    for snapshot in (sealed, current):
        if not _profile_ok(snapshot.profile) or not _decision_ok(snapshot.decision):
            holds.add("PROFILE_OR_CASE_INVALID")
            continue
        holds.update(_material_errors(snapshot.materials))
        holds.update(_fence_errors(snapshot))
        if snapshot.profile.claim_kind != snapshot.decision.claim_kind or (
            snapshot.profile.risk_class != snapshot.decision.risk_class
            or snapshot.profile.jurisdiction_ref != snapshot.decision.jurisdiction_ref
            or snapshot.profile.policy_version != snapshot.decision.policy_version
        ):
            holds.add("PROFILE_CASE_MISMATCH")
        if snapshot.decision.claimed_machine_approval is not False:
            holds.add("CALLER_SIGNOFF_CLAIM_UNTRUSTED")
        if snapshot.decision.rights_state != "CURRENT":
            holds.add("RIGHTS_NOT_CURRENT")
        if snapshot.decision.correction_state != "CLEAR":
            holds.add("CORRECTION_OR_CHALLENGE_PENDING")
        if snapshot.decision.challenger_state != "COMPLETED":
            holds.add("CHALLENGER_INCOMPLETE")
        if (
            snapshot.decision.generator_run_ref == snapshot.decision.challenger_run_ref
            or snapshot.decision.generator_identity_ref
            == snapshot.decision.challenger_identity_ref
            or snapshot.decision.generator_source_root_ref
            == snapshot.decision.challenger_source_root_ref
        ):
            holds.add("CHALLENGER_NOT_INDEPENDENT")

    if holds & {
        "PROFILE_OR_CASE_INVALID",
        "MATERIAL_SET_INVALID",
        "MATERIAL_ROLE_DUPLICATE",
        "MATERIAL_ROLE_UNKNOWN",
        "MATERIAL_DEPENDENCY_REF_DUPLICATE",
        "REQUIRED_MATERIAL_ROLE_MISSING",
        "MATERIAL_ROLES_NOT_CANONICAL",
        "MACHINE_SNAPSHOT_INVALID",
        "FENCE_INTEGRITY_INVALID",
    }:
        return MachineAuthorityPreflight("HOLD", tuple(sorted(holds)), None)

    if sealed.profile != current.profile or any(
        getattr(sealed.decision, field) != getattr(current.decision, field)
        for field in ("claim_kind", "risk_class", "jurisdiction_ref", "policy_version")
    ):
        rechecks.add("CURRENT_PROFILE_OR_POLICY_CHANGED")
    if sealed.decision != current.decision:
        rechecks.add("DECISION_CURRENTNESS_CHANGED")
    if sealed.materials != current.materials:
        rechecks.add("MATERIAL_CURRENTNESS_CHANGED")
    if sealed.fence != current.fence:
        rechecks.add("FENCE_CURRENTNESS_CHANGED")
    if not _fence_covers_materials(sealed):
        holds.add("FENCE_MATERIAL_BINDING_MISMATCH")
    if not _fence_covers_materials(current):
        rechecks.add("CURRENT_FENCE_OUT_OF_SYNC")

    by_role = {item.role: item for item in sealed.materials}
    if by_role["MACHINE_PROFILE"].sha256 != _digest(asdict(sealed.profile)):
        holds.add("MACHINE_PROFILE_BINDING_MISMATCH")
    if (
        sealed.profile.risk_class in {"HIGH", "LEGAL"}
        and isinstance(high_risk, HighRiskDecision)
        and by_role["QUALIFIED_POLICY"].ref != high_risk.policy_decision_ref
    ):
        holds.add("QUALIFIED_POLICY_REF_MISMATCH")
    if not isinstance(requirement, RequirementPreflight) or (
        requirement.version != REQUIREMENT_VERSION
        or requirement.claim_id != sealed.decision.record_id
        or requirement.state != "CHECKABLE_PENDING"
    ):
        holds.add("UPSTREAM_VERIFICATION_NOT_CHECKABLE")
    elif (
        requirement.snapshot_sha256 != by_role["REQUIREMENT_RESULT"].sha256
        or requirement.publication_authority is not False
        or requirement.finding_authority is not False
        or requirement.verdict is not None
    ):
        holds.add("REQUIREMENT_BINDING_OR_AUTHORITY_INVALID")

    if not isinstance(publication_safety, PublicationSafetyResult) or (
        publication_safety.profile_version != PUBLICATION_SAFETY_VERSION
        or publication_safety.disposition != "ELIGIBLE"
    ):
        holds.add("PUBLICATION_SAFETY_HELD")
    elif publication_safety.binding_sha256 != by_role["SAFETY_RESULT"].sha256:
        holds.add("PUBLICATION_SAFETY_BINDING_MISMATCH")

    risk_holds, risk_external = _high_risk_errors(sealed.profile.risk_class, high_risk)
    holds.update(risk_holds)
    external.update(risk_external)
    if not risk_holds:
        try:
            risk_sha = high_risk_binding_sha256(
                high_risk,
                input_binding_sha256=by_role["HIGH_RISK_INPUT"].sha256,
            )
        except (TypeError, ValueError, AttributeError):
            holds.add("HIGH_RISK_BINDING_INVALID")
        else:
            if by_role["HIGH_RISK_RESULT"].sha256 != risk_sha:
                holds.add("HIGH_RISK_BINDING_MISMATCH")

    # Structural hash for replay/inspection only; no MAC, signature, consent,
    # externally qualified decision or authentically fresh reads are implied.
    snapshot_hash = _digest(asdict(sealed))
    if holds:
        return MachineAuthorityPreflight(
            "HOLD", tuple(sorted(holds | rechecks)), snapshot_hash
        )
    if rechecks:
        return MachineAuthorityPreflight(
            "RECHECK", tuple(sorted(rechecks)), snapshot_hash
        )

    external.update(
        {
            "OFF_DB_MACHINE_AUTHORITY_UNAVAILABLE",
            "CRYPTOGRAPHIC_ATTESTATION_UNVERIFIED",
            "QUALIFIED_POLICY_NOT_ATTESTED",
            "INDEPENDENT_CHALLENGER_NOT_ATTESTED",
            "INDEPENDENT_GOLD_UNATTESTED",
            "LIVE_TRANSACTIONAL_FENCE_UNVERIFIED",
            "OWNER_RELEASE_SCOPE_NOT_ATTESTED",
            "INDEPENDENT_VERIFIER_OUTCOME_UNATTESTED",
        }
    )
    return MachineAuthorityPreflight(
        "NEEDS_EXTERNAL_DECISION", tuple(sorted(external)), snapshot_hash
    )


__all__ = [
    "MACHINE_AUTHORITY_PREFLIGHT_VERSION",
    "MACHINE_MATERIAL_ROLES",
    "MachineAuthorityPreflight",
    "MachineAuthorityProfile",
    "MachineAuthoritySnapshot",
    "MachineDecisionReference",
    "MaterialBinding",
    "preflight_machine_authority",
]
