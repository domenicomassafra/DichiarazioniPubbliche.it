from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from dichiarazioni_pubbliche.machine_authority_cutover_v1 import (
    evaluate_machine_authority_cutover,
)
from dichiarazioni_pubbliche.machine_authority_signed_v1 import SignedAuthorityVerdict
from dichiarazioni_pubbliche.publication_eligibility import (
    PUBLICATION_ELIGIBILITY_VERSION,
    PublicationEligibilityResult,
)


@dataclass(frozen=True)
class MachineAuthorityProjectionGate:
    """Optional host-local selector; the safe default is the existing legacy path."""

    mode: str = "LEGACY_ONLY"
    policy_version: str | None = None
    verifier: Callable[[str, str], SignedAuthorityVerdict | None] | None = None
    rollback_from_mode: str | None = None
    rollback_ref: str | None = None


def production_projection_cutover_allows(
    gate: MachineAuthorityProjectionGate,
    *,
    record_id: str,
    record_version: str,
    legacy_result: PublicationEligibilityResult,
) -> bool:
    """Apply the versioned selector; never treat this as final public-read authority."""
    machine_result = None
    if gate.mode in {"DUAL_READ", "MACHINE_V1"} and gate.verifier is not None:
        try:
            machine_result = gate.verifier(record_id, record_version)
        except Exception:
            # Shadow-read failure must never alter the already-computed legacy decision.
            machine_result = None
    cutover = evaluate_machine_authority_cutover(
        mode=gate.mode,
        record_id=record_id,
        record_version=record_version,
        legacy_result=legacy_result,
        machine_result=machine_result,
        machine_policy_version=gate.policy_version,
        legacy_policy_version=PUBLICATION_ELIGIBILITY_VERSION,
        rollback_from_mode=gate.rollback_from_mode,
        rollback_ref=gate.rollback_ref,
    )
    if gate.mode == "MACHINE_V1":
        # DP-320 transaction/final-public-read adapter is not connected here.
        return False
    return (
        cutover.selected_path == "LEGACY"
        and cutover.disposition in {
            "LEGACY_ELIGIBLE",
            "LEGACY_ROLLBACK_ELIGIBLE",
            "LEGACY_ELIGIBLE_SHADOW_HOLD",
            "DUAL_READ_MATCHED",
        }
        and cutover.publication_authority is False
    )


__all__ = ["MachineAuthorityProjectionGate", "production_projection_cutover_allows"]
