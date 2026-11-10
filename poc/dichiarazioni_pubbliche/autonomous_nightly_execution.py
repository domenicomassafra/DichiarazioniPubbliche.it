"""One nightly sample revalidation and protective public withdrawal.

Ordinary records have one prior editorial proof. An uncertain record is
accepted only with its three independently witnessed prepublication proofs.
"""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from .autonomous_publication import (
    AgentReview, AutonomousCandidate, AutonomousProofPacket, CHECKS,
    candidate_fingerprint, evaluate_autonomous_publication, review_model_authorized,
)
from .autonomous_execution_witness import review_execution_witnessed
from .autonomous_operations import _now, _matches, _review_identity_ok

if TYPE_CHECKING:
    from .autonomous_operations import AutonomousOperations, ReviewAuthority, RunReceipt


def audit_and_apply(
    self, packet: AutonomousProofPacket, auditor: ReviewAuthority,
    *, now: datetime,
) -> RunReceipt:
    """Recheck persisted authority; only uncertain items require 2+1.

    The third execution for an uncertain item precedes publication and is
    present in the durable packet. Nightly verification must not turn a
    certain item into a universal third provider call.
    """
    at = _now(now)
    if not isinstance(packet, AutonomousProofPacket) or not isinstance(
        packet.candidate, AutonomousCandidate
    ):
        raise ValueError("AUTONOMOUS_AUDIT_PACKET_INVALID")
    item = packet.candidate
    record_id = item.record_id
    binding = candidate_fingerprint(item)
    try:
        prior = evaluate_autonomous_publication(
            item, packet.primary, packet.independent, third=packet.third,
        )
        visible = self.surface.current_evidence_sha256(record_id)
    except Exception:
        prior = None
        visible = None
    uncertain = bool(item.uncertainty_reasons)
    executions = [packet.primary]
    issuers = [self.first]
    if packet.independent is not None or uncertain:
        executions.append(packet.independent)
        issuers.append(self.second)
    if uncertain:
        executions.append(packet.third)
        issuers.append(self.uncertainty_auditor)
    receipts = [
        review.provider_request_id for review in executions
        if isinstance(review, AgentReview)
    ]
    valid = (
        prior is not None and prior.publishable
        and len(receipts) == len(executions)
        and len(set(receipts)) == len(executions)
        and all(issuer is not None and _review_identity_ok(review, issuer)
                and review_execution_witnessed(review, self.verify_provider_execution)
                for review, issuer in zip(executions, issuers))
        and _matches(self._read_capture(record_id), binding)
        and self._read_challenge(record_id) is False
        and visible == binding
    )
    if valid and not uncertain:
        # A bounded nightly spot audit is separate from the prepublication
        # 2+1 escalation. It never delays an ordinary ready record.
        actor_ids = {review.agent_id.casefold() for review in executions}
        model_ids = {review.model_id for review in executions}
        allowed_auditor = (
            isinstance(getattr(auditor, "agent_id", None), str)
            and bool(auditor.agent_id.strip())
            and isinstance(getattr(auditor, "model_id", None), str)
            and review_model_authorized(auditor.model_id)
            and auditor.agent_id.strip().casefold() not in actor_ids
            and auditor.model_id not in model_ids
        )
        third = None
        if allowed_auditor:
            try:
                third = auditor.review(item, binding)
            except Exception:
                pass
        valid = (
            allowed_auditor
            and _review_identity_ok(third, auditor)
            and third.evidence_sha256 == binding
            and third.checked_stages == CHECKS
            and third.accepted is True
            and third.provider_request_id not in receipts
            and review_execution_witnessed(third, self.verify_provider_execution)
            and _matches(self._read_capture(record_id), binding)
            and self._read_challenge(record_id) is False
            and self._publicly_current(record_id, binding)
        )
    if not valid:
        self._withdraw(record_id)
        return self._record(
            record_id, "AUDIT_HOLD", binding, ("THIRD_REVIEW_FAILED",), at
        )
    return self._record(record_id, "AUDIT_PASS", binding, (), at)
