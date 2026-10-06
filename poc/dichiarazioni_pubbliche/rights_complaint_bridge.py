from __future__ import annotations

import hashlib

from dichiarazioni_pubbliche.challenge_persistence import (
    ChallengeAppendResult,
    ChallengeHoldResult,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
)
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore


RIGHTS_COMPLAINT_BRIDGE_VERSION = "rights-complaint-dp303-v1"


class RightsComplaintBridgeError(ValueError):
    pass


def _text(value: object, code: str, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or "\x00" in text:
        raise RightsComplaintBridgeError(code)
    return text


class RightsComplaintBridge:
    """Durable DP-305 complaint bridge using DP-303's append-only TAKEDOWN ledger.

    Intake creates private triage only. A public hold requires a separate explicit
    TRIAGE_REVIEWER approval; this class never infers rights or legal authority.
    """

    def __init__(self, database_url: str, psql: str = "psql") -> None:
        self.rights = PrivateRightsRegistryStore(database_url, psql)
        self.challenges = PrivateChallengeLedgerStore(database_url, psql)

    def _record_is_bound_to_finding(self, *, finding_id: str, content_id: str | None, evidence_id: str | None) -> bool:
        if content_id is None and evidence_id is None:
            return False
        raw = self.rights.run(
            """
            SELECT EXISTS (
                SELECT 1
                FROM finding finding
                JOIN atomic_claim claim ON claim.id=finding.claim_id
                WHERE finding.id=:'finding_id'
                  AND (
                    (NULLIF(:'content_id','') IS NOT NULL AND claim.content_id=:'content_id')
                    OR
                    (NULLIF(:'evidence_id','') IS NOT NULL AND EXISTS (
                        SELECT 1 FROM finding_evidence edge
                        WHERE edge.finding_id=finding.id
                          AND edge.evidence_id=:'evidence_id'
                    ))
                  )
            )::text;
            """,
            finding_id=finding_id,
            content_id=content_id or "",
            evidence_id=evidence_id or "",
        )
        return str(raw or "").lower() in {"t", "true", "1"}

    def submit(
        self,
        *,
        finding_id: str,
        rights_record_id: str,
        complaint_ref: str,
        actor_ref: str,
    ) -> ChallengeAppendResult:
        finding = _text(finding_id, "RIGHTS_COMPLAINT_FINDING_INVALID")
        rights_id = _text(rights_record_id, "RIGHTS_COMPLAINT_RECORD_INVALID")
        complaint = _text(complaint_ref, "RIGHTS_COMPLAINT_REF_INVALID")
        actor = _text(actor_ref, "RIGHTS_COMPLAINT_ACTOR_INVALID", 256)
        record = self.rights.read_record(rights_id)
        if record is None:
            raise RightsComplaintBridgeError("RIGHTS_COMPLAINT_RECORD_NOT_FOUND")
        if record.version_state != "CURRENT":
            raise RightsComplaintBridgeError("RIGHTS_COMPLAINT_RECORD_NOT_CURRENT")
        if not self._record_is_bound_to_finding(
            finding_id=finding,
            content_id=record.content_id,
            evidence_id=record.evidence_id,
        ):
            raise RightsComplaintBridgeError("RIGHTS_COMPLAINT_RECORD_NOT_BOUND_TO_FINDING")
        source_hash = hashlib.sha256(
            (RIGHTS_COMPLAINT_BRIDGE_VERSION + "\x00" + rights_id + "\x00" + complaint).encode()
        ).hexdigest()
        root = self.challenges.initiate_request(
            kind=ChallengeKind.TAKEDOWN,
            target_finding_id=finding,
            source_request_ref=f"rights-complaint:{source_hash}",
            actor_ref=actor,
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            reason="Rights complaint requires private review",
        )
        replay = self.challenges.replay_request(root.request.request_id)
        if not root.created and replay.current_state is not ChallengeState.PRIVATE_RECEIVED:
            return ChallengeAppendResult(replay.request, replay.events[-1], False)
        return self.challenges.transition_request(
            root.request.request_id,
            actor_ref="rights-complaint-intake",
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            reason="Route rights complaint to private triage",
        )

    def approve_hold(
        self,
        request_id: str,
        *,
        reviewer_actor_ref: str,
        reason: str = "Reviewed rights complaint hold",
    ) -> ChallengeAppendResult:
        clean_request = _text(request_id, "RIGHTS_COMPLAINT_REQUEST_INVALID")
        replay = self.challenges.replay_request(clean_request)
        if (
            not replay.blockers
            and replay.request is not None
            and replay.current_state is ChallengeState.PUBLIC_HOLD_APPROVED
        ):
            return ChallengeAppendResult(replay.request, replay.events[-1], False)
        return self.challenges.transition_request(
            clean_request,
            actor_ref=_text(reviewer_actor_ref, "RIGHTS_COMPLAINT_REVIEWER_INVALID", 256),
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            reason=_text(reason, "RIGHTS_COMPLAINT_REASON_INVALID", 8000),
            challenge_review_approved=True,
        )

    def current_hold(self, finding_id: str) -> ChallengeHoldResult:
        return self.challenges.current_hold_for_finding(
            _text(finding_id, "RIGHTS_COMPLAINT_FINDING_INVALID")
        )


__all__ = ["RIGHTS_COMPLAINT_BRIDGE_VERSION", "RightsComplaintBridge", "RightsComplaintBridgeError"]
