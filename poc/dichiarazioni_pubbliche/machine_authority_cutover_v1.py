from __future__ import annotations

import re
from dataclasses import dataclass

from dichiarazioni_pubbliche.machine_authority_signed_v1 import SignedAuthorityVerdict
from dichiarazioni_pubbliche.publication_eligibility import (
    PUBLICATION_ELIGIBILITY_VERSION,
    PublicationEligibilityResult,
)

VERSION = "dp316-cutover-v1"
CUTOVER_MODES = frozenset({"LEGACY_ONLY", "DUAL_READ", "MACHINE_V1"})
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


@dataclass(frozen=True)
class MachineAuthorityCutoverDecision:
    version: str
    mode: str
    disposition: str
    selected_path: str
    reason_codes: tuple[str, ...]
    record_id: str
    record_version: str
    legacy_binding_sha256: str | None = None
    machine_snapshot_sha256: str | None = None
    rollback_ref: str | None = None

    @property
    def publication_authority(self) -> bool:
        # This selector is not the DP-320 transaction/read authority boundary.
        return False


def _legacy_eligible(
    result: PublicationEligibilityResult | None,
    *,
    record_id: str,
    record_version: str,
    legacy_policy_version: str,
) -> bool:
    return bool(
        isinstance(result, PublicationEligibilityResult)
        and result.disposition == "ELIGIBLE_FOR_PROJECTION_REVALIDATION"
        and not result.blockers
        and result.profile_version == legacy_policy_version
        and result.record_id == record_id
        and result.record_version == record_version
        and isinstance(result.binding_sha256, str)
        and _HEX.fullmatch(result.binding_sha256) is not None
    )


def _machine_receipt_matches(
    result: SignedAuthorityVerdict | None,
    *,
    record_id: str,
    record_version: str,
    machine_policy_version: str | None,
) -> bool:
    return bool(
        isinstance(result, SignedAuthorityVerdict)
        and result.disposition == "PRIVATE_SIGNATURE_VERIFIED"
        and result.private_signature_verified is True
        and result.independent_adjudication_verified is True
        and result.record_id == record_id
        and result.record_version == record_version
        and isinstance(result.snapshot_sha256, str)
        and _HEX.fullmatch(result.snapshot_sha256) is not None
        and isinstance(machine_policy_version, str)
        and machine_policy_version
        and result.policy_version == machine_policy_version
    )


def _decision(
    *,
    mode: str,
    disposition: str,
    selected_path: str,
    reason_codes: tuple[str, ...],
    record_id: str,
    record_version: str,
    legacy_result: PublicationEligibilityResult | None,
    machine_result: SignedAuthorityVerdict | None,
    rollback_ref: str | None = None,
) -> MachineAuthorityCutoverDecision:
    return MachineAuthorityCutoverDecision(
        version=VERSION,
        mode=mode,
        disposition=disposition,
        selected_path=selected_path,
        reason_codes=reason_codes,
        record_id=record_id,
        record_version=record_version,
        legacy_binding_sha256=(
            legacy_result.binding_sha256
            if isinstance(legacy_result, PublicationEligibilityResult)
            else None
        ),
        machine_snapshot_sha256=(
            machine_result.snapshot_sha256
            if isinstance(machine_result, SignedAuthorityVerdict)
            else None
        ),
        rollback_ref=rollback_ref,
    )


def evaluate_machine_authority_cutover(
    *,
    mode: str,
    record_id: str,
    record_version: str,
    legacy_result: PublicationEligibilityResult | None,
    machine_result: SignedAuthorityVerdict | None,
    machine_policy_version: str | None,
    legacy_policy_version: str = PUBLICATION_ELIGIBILITY_VERSION,
    rollback_from_mode: str | None = None,
    rollback_ref: str | None = None,
) -> MachineAuthorityCutoverDecision:
    """Select a versioned review path without granting publication authority.

    LEGACY_ONLY preserves the existing DP-310/311 result and ignores machine
    receipts. DUAL_READ is a shadow comparison: the legacy path remains selected
    even when the machine result is missing, stale, mismatched or unsigned for
    machine signoff. MACHINE_V1 has no legacy fallback and stays HOLD until a
    separate machine-signoff and DP-320 final-read adapter exist.
    """
    if type(record_id) is not str or type(record_version) is not str:
        record_id, record_version = "", ""
    record_id = record_id.strip()
    record_version = record_version.strip()
    if (not isinstance(mode, str) or mode not in CUTOVER_MODES
            or not record_id or len(record_id) > 256
            or not record_version or len(record_version) > 256):
        return _decision(
            mode=str(mode or ""),
            disposition="HOLD",
            selected_path="NONE",
            reason_codes=("DP316_CUTOVER_INPUT_INVALID",),
            record_id=record_id,
            record_version=record_version,
            legacy_result=legacy_result,
            machine_result=machine_result,
        )

    rollback_valid = (
        mode == "LEGACY_ONLY"
        and isinstance(rollback_from_mode, str)
        and rollback_from_mode in {"DUAL_READ", "MACHINE_V1"}
        and isinstance(rollback_ref, str)
        and _REF.fullmatch(rollback_ref) is not None
    )
    if rollback_from_mode is not None and not rollback_valid:
        return _decision(
            mode=mode, disposition="HOLD", selected_path="NONE",
            reason_codes=("DP316_ROLLBACK_REFERENCE_INVALID",),
            record_id=record_id, record_version=record_version,
            legacy_result=legacy_result, machine_result=machine_result,
        )
    if rollback_from_mode is None and rollback_ref is not None:
        return _decision(
            mode=mode, disposition="HOLD", selected_path="NONE",
            reason_codes=("DP316_ROLLBACK_REFERENCE_INVALID",),
            record_id=record_id, record_version=record_version,
            legacy_result=legacy_result, machine_result=machine_result,
        )

    legacy_ok = _legacy_eligible(
        legacy_result, record_id=record_id, record_version=record_version,
        legacy_policy_version=legacy_policy_version,
    )
    machine_ok = _machine_receipt_matches(
        machine_result, record_id=record_id, record_version=record_version,
        machine_policy_version=machine_policy_version,
    )

    if mode == "LEGACY_ONLY":
        if not legacy_ok:
            return _decision(
                mode=mode, disposition="HOLD", selected_path="NONE",
                reason_codes=("DP316_LEGACY_ELIGIBILITY_UNAVAILABLE",),
                record_id=record_id, record_version=record_version,
                legacy_result=legacy_result, machine_result=machine_result,
                rollback_ref=rollback_ref if rollback_valid else None,
            )
        return _decision(
            mode=mode,
            disposition="LEGACY_ROLLBACK_ELIGIBLE" if rollback_valid else "LEGACY_ELIGIBLE",
            selected_path="LEGACY",
            reason_codes=(),
            record_id=record_id, record_version=record_version,
            legacy_result=legacy_result, machine_result=machine_result,
            rollback_ref=rollback_ref if rollback_valid else None,
        )

    if mode == "DUAL_READ":
        if not legacy_ok:
            return _decision(
                mode=mode, disposition="HOLD", selected_path="NONE",
                reason_codes=("DP316_LEGACY_ELIGIBILITY_UNAVAILABLE",),
                record_id=record_id, record_version=record_version,
                legacy_result=legacy_result, machine_result=machine_result,
            )
        if not machine_ok:
            machine_reasons = (
                machine_result.reason_codes
                if isinstance(machine_result, SignedAuthorityVerdict) and machine_result.reason_codes
                else ("DP316_MACHINE_SHADOW_UNAVAILABLE",)
            )
            return _decision(
                mode=mode, disposition="LEGACY_ELIGIBLE_SHADOW_HOLD",
                selected_path="LEGACY", reason_codes=machine_reasons,
                record_id=record_id, record_version=record_version,
                legacy_result=legacy_result, machine_result=machine_result,
            )
        if not machine_result.machine_signoff:
            return _decision(
                mode=mode, disposition="LEGACY_ELIGIBLE_SHADOW_HOLD",
                selected_path="LEGACY",
                reason_codes=("DP316_MACHINE_SIGNOFF_UNAVAILABLE",),
                record_id=record_id, record_version=record_version,
                legacy_result=legacy_result, machine_result=machine_result,
            )
        return _decision(
            mode=mode, disposition="DUAL_READ_MATCHED", selected_path="LEGACY",
            reason_codes=(), record_id=record_id, record_version=record_version,
            legacy_result=legacy_result, machine_result=machine_result,
        )

    # MACHINE_V1 intentionally never falls back to a legacy review event.
    if not machine_ok or machine_result is None or not machine_result.machine_signoff:
        machine_reasons = (
            machine_result.reason_codes
            if isinstance(machine_result, SignedAuthorityVerdict) and machine_result.reason_codes
            else ("DP316_MACHINE_SIGNOFF_UNAVAILABLE",)
        )
        return _decision(
            mode=mode, disposition="HOLD", selected_path="NONE",
            reason_codes=machine_reasons,
            record_id=record_id, record_version=record_version,
            legacy_result=legacy_result, machine_result=machine_result,
        )
    return _decision(
        mode=mode, disposition="MACHINE_ELIGIBLE_FOR_FENCED_REVALIDATION",
        selected_path="MACHINE", reason_codes=(),
        record_id=record_id, record_version=record_version,
        legacy_result=legacy_result, machine_result=machine_result,
    )


__all__ = [
    "VERSION", "CUTOVER_MODES", "MachineAuthorityCutoverDecision",
    "evaluate_machine_authority_cutover",
]
