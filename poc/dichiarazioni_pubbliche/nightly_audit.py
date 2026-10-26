"""DP-413E: persisted, deterministic nightly sampling over trusted v3 adapters.

The caller supplies the production journal, correction ledger and independently
attested audit adapters. Nothing in this coordinator grants review authority.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from dichiarazioni_pubbliche.autonomous_publication import (
    AgentReview, AutonomousCandidate, AutonomousProofPacket, candidate_fingerprint,
)
from dichiarazioni_pubbliche.autonomous_operations import (
    AuditPacketAuthority, AutonomousOperations, CorrectionMetricEvent,
    ReviewAuthority, RunReceipt, _now, daily_metrics, nightly_sample,
)


@dataclass(frozen=True)
class NightlyManifest:
    run_id: str
    day: date
    denominator: int
    sampled: tuple[str, ...]
    started_at: datetime


@dataclass(frozen=True)
class NightlyResult:
    run_id: str
    day: date
    denominator: int
    sampled: tuple[str, ...]
    audited: int
    metrics: dict[str, int | str]


class NightlyLedger(Protocol):
    def begin(self, manifest: NightlyManifest) -> NightlyManifest: ...
    def recorded(self, run_id: str) -> dict[str, RunReceipt]: ...
    def append(self, run_id: str, receipt: RunReceipt, evidence: dict[str, object]) -> None: ...
    def complete(self, run_id: str, metrics: dict[str, int | str], at: datetime) -> None: ...
    def readback(self, run_id: str) -> dict[str, int | str] | None: ...


class _CapturedPacket:
    def __init__(self, authority: AuditPacketAuthority):
        self.authority = authority
        self.packet: AutonomousProofPacket | None = None

    def current_packet(self, record_id: str) -> AutonomousProofPacket | None:
        self.packet = self.authority.current_packet(record_id)
        return self.packet


class _CapturedThird:
    def __init__(self, third: ReviewAuthority):
        self.third = third
        actor = getattr(third, 'agent_id', '')
        model = getattr(third, 'model_id', '')
        self.agent_id = actor if isinstance(actor, str) else ''
        self.model_id = model if isinstance(model, str) else ''
        self.review_result: AgentReview | None = None

    def review(self, candidate, evidence_sha256):
        self.review_result = self.third.review(candidate, evidence_sha256)
        return self.review_result


def _audit_evidence(packet: AutonomousProofPacket | None,
                    third: _CapturedThird, receipt: RunReceipt) -> dict[str, object]:
    result: dict[str, object] = {
        'auditor_agent_id': third.agent_id,
        'auditor_model_id': third.model_id,
        'verified_third_review': False,
    }
    if isinstance(packet, AutonomousProofPacket) and isinstance(packet.candidate, AutonomousCandidate):
        candidate = packet.candidate
        result.update({
            'record_version_id': candidate.record_version_id,
            'source_version': candidate.source_version,
            'source_url': candidate.source_url,
            'snapshot_sha256': candidate.snapshot_sha256,
            'source_text_sha256': candidate.source_text_sha256,
            'rights_attestation_sha256': candidate.rights_attestation_sha256,
            'rights_citation_url': candidate.rights_citation_url,
            'original_reviewers': [
                {'agent_id': review.agent_id, 'model_id': review.model_id,
                 'evidence_sha256': review.evidence_sha256}
                for review in (packet.primary, packet.independent)
                if isinstance(review, AgentReview)
            ],
            'packet_matches_outcome': candidate_fingerprint(candidate) == receipt.evidence_sha256,
        })
    if isinstance(third.review_result, AgentReview):
        review = third.review_result
        result['third_review'] = {
            'agent_id': review.agent_id, 'model_id': review.model_id,
            'evidence_sha256': review.evidence_sha256,
            'accepted': review.accepted, 'checked_stages': list(review.checked_stages),
        }
        result['verified_third_review'] = (
            isinstance(review.agent_id, str)
            and isinstance(review.model_id, str)
            and review.agent_id.strip().casefold() == third.agent_id.strip().casefold()
            and review.model_id.strip().casefold() == third.model_id.strip().casefold()
            and review.evidence_sha256 == receipt.evidence_sha256
        )
    return result


class NightlyAuditCoordinator:
    def __init__(self, ledger: NightlyLedger):
        self.ledger = ledger

    def run(
        self, *, operations: AutonomousOperations, packet_authority: AuditPacketAuthority,
        third: ReviewAuthority, events: tuple[RunReceipt, ...],
        corrections: tuple[CorrectionMetricEvent, ...], day: date, now: datetime,
    ) -> NightlyResult:
        at = _now(now)
        if type(day) is not date or day > at.date():
            raise ValueError('NIGHTLY_AUDIT_DAY_INVALID')
        # The day is UTC, including after downtime/backfill; sample only states
        # in the durable journal as of that day, never later evidence.
        selected = nightly_sample(events, day)
        state = daily_metrics(events, day, corrections=corrections)
        denominator = state['published']
        run_id = 'nightly:' + hashlib.sha256(f'dp413e-v1\0{day.isoformat()}'.encode()).hexdigest()
        manifest = self.ledger.begin(NightlyManifest(run_id, day, denominator, selected, at))
        if manifest.run_id != run_id or manifest.day != day or manifest.denominator < len(manifest.sampled):
            raise ValueError('NIGHTLY_AUDIT_MANIFEST_INVALID')
        # Reuse the frozen first-run sample on retries, even if an earlier HOLD
        # changed the current public set. Completion is read back before work.
        completed = self.ledger.readback(run_id)
        recorded = self.ledger.recorded(run_id)
        if completed is None:
            for record_id in manifest.sampled:
                if record_id in recorded:
                    continue
                captured_packet = _CapturedPacket(packet_authority)
                captured_third = _CapturedThird(third)
                receipt = operations.audit_nightly_record(
                    record_id, packet_authority=captured_packet,
                    third=captured_third, now=at,
                )
                self.ledger.append(
                    run_id, receipt,
                    _audit_evidence(captured_packet.packet, captured_third, receipt),
                )
            recorded = self.ledger.recorded(run_id)
            if set(recorded) != set(manifest.sampled):
                raise RuntimeError('NIGHTLY_AUDIT_INCOMPLETE')
            # After a crash, the operational journal may already include some
            # of these same audit receipts. Reconcile by persisted record ID so
            # a resumed run is counted once, not once per attempted delivery.
            existing = tuple(
                event for event in events
                if not (event.record_id in recorded
                        and event.disposition in {'AUDIT_PASS', 'AUDIT_HOLD'})
            )
            metrics = daily_metrics(
                (*existing, *recorded.values()), at.date(), corrections=corrections,
            )
            metrics['audited'] = len(recorded)
            metrics['audit_holds'] = sum(
                item.disposition == 'AUDIT_HOLD' for item in recorded.values()
            )
            metrics['audit_day'] = day.isoformat()
            metrics['run_at'] = at.isoformat()
            metrics['denominator'] = manifest.denominator
            metrics['sampled'] = len(manifest.sampled)
            self.ledger.complete(run_id, metrics, at)
            completed = self.ledger.readback(run_id)
        if completed is None:
            raise RuntimeError('NIGHTLY_AUDIT_READBACK_FAILED')
        return NightlyResult(
            run_id, day, manifest.denominator, manifest.sampled,
            len(recorded), completed,
        )
