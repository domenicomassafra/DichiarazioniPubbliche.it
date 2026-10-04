from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from dichiarazioni_pubbliche.domain_vocabulary import (
    FINDING_PUBLICATION_STATUS_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.verification_runtime import (
    VerificationResult,
)


FINDING_POLICY_VERSION = "finding-policy-v1"


@dataclass(frozen=True)
class FindingDraft:
    finding_id: str
    claim_id: str
    verification_run_id: str
    assessment: str
    assessment_version: str
    rationale: str
    publication_status: str
    publication_status_version: str
    policy_version: str
    evidence_ids: tuple[str, ...]
    model_bundle: dict[str, object]
    supersedes_id: str | None = None


def publication_status_for_verification(
    assessment: VerificationAssessment,
) -> FindingPublicationStatus:
    if assessment == VerificationAssessment.INSUFFICIENT_EVIDENCE:
        return FindingPublicationStatus.NEEDS_MORE_EVIDENCE
    if assessment == VerificationAssessment.UNRESOLVED:
        return FindingPublicationStatus.UNRESOLVED
    # A deterministic verification result is still an internal candidate.
    # Publication requires a separate publication gate, transcript checks,
    # rights/provenance checks and any required human/policy review.
    return FindingPublicationStatus.POLICY_HOLD


def finding_draft_from_verification(
    *,
    verification_run_id: str,
    input_fingerprint: str,
    result: VerificationResult,
    supersedes_id: str | None = None,
    policy_version: str = FINDING_POLICY_VERSION,
) -> FindingDraft:
    publication_status = publication_status_for_verification(result.assessment)
    rationale = "; ".join(result.rationale_codes) or result.assessment.value
    material = {
        "verification_run_id": verification_run_id,
        "policy_version": policy_version,
        "assessment": result.assessment.value,
        "publication_status": publication_status.value,
    }
    finding_id = "finding:" + hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return FindingDraft(
        finding_id=finding_id,
        claim_id=result.claim_id,
        verification_run_id=verification_run_id,
        assessment=result.assessment.value,
        assessment_version=VERIFICATION_ASSESSMENT_VERSION,
        rationale=rationale,
        publication_status=publication_status.value,
        publication_status_version=FINDING_PUBLICATION_STATUS_VERSION,
        policy_version=policy_version,
        evidence_ids=result.evidence_ids,
        model_bundle={
            "verification_version": result.verification_version,
            "verification_input_fingerprint": input_fingerprint,
            "deterministic": True,
        },
        supersedes_id=supersedes_id,
    )
