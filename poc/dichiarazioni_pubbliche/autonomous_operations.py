"""DP #413: orchestrate independent review and protective public readback.

The adapters are *authority boundaries*: a production integration must verify
immutable capture bytes, model-execution identities, rights, durable receipts,
and every externally served surface. This module never infers that a claimed
receipt authenticates its own issuer or that a successful local readback fences
CDN/static caches. Incomplete authority is a HOLD, not publication authority.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

from dichiarazioni_pubbliche.autonomous_publication import (
    AgentReview,
    AutonomousCandidate,
    AutonomousProofPacket,
    AutonomousDecision,
    CHECKS,
    candidate_fingerprint,
    evaluate_autonomous_publication,
)


class PublicationSafetyError(RuntimeError):
    """The public item could not be proven absent following a denial."""


class CaptureAuthority(Protocol):
    def current(self, record_id: str) -> AutonomousCandidate | None: ...


class ChallengeAuthority(Protocol):
    def current(self, record_id: str) -> bool: ...


class ReviewAuthority(Protocol):
    agent_id: str
    model_id: str

    def review(self, candidate: AutonomousCandidate, evidence_sha256: str) -> AgentReview: ...


class PublicSurface(Protocol):
    def publish(self, packet: AutonomousProofPacket) -> None: ...

    def withdraw(self, record_id: str) -> None: ...

    def current_evidence_sha256(self, record_id: str) -> str | None: ...


@dataclass(frozen=True)
class RunReceipt:
    record_id: str
    disposition: str
    evidence_sha256: str | None
    reason_codes: tuple[str, ...]
    at: datetime


class EventJournal(Protocol):
    def append(self, event: RunReceipt) -> None: ...


class AuditPacketAuthority(Protocol):
    def current_packet(self, record_id: str) -> AutonomousProofPacket | None: ...


def _now(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("AUTONOMOUS_OPERATION_REQUIRES_TZ_AWARE_INSTANT")
    return now.astimezone(timezone.utc)


def _matches(item: AutonomousCandidate | None, expected_sha256: str) -> bool:
    if not isinstance(item, AutonomousCandidate):
        return False
    try:
        return candidate_fingerprint(item) == expected_sha256
    except (TypeError, ValueError, OverflowError):
        return False


def _review_identity_ok(review: AgentReview | None, issuer: ReviewAuthority) -> bool:
    if not isinstance(review, AgentReview):
        return False
    try:
        return (
            review.agent_id.strip().casefold() == issuer.agent_id.strip().casefold()
            and review.model_id.strip().casefold() == issuer.model_id.strip().casefold()
            and bool(issuer.agent_id.strip())
            and bool(issuer.model_id.strip())
        )
    except (AttributeError, TypeError):
        return False


class AutonomousOperations:
    """Evaluate private evidence and apply publication with protective rollback.

    The writer and reader adapters must be *separate trusted authorities* in
    production. Failure to observe withdrawal raises, so callers never report
    a successful HOLD while public bytes are still visible.
    """

    def __init__(
        self, *, capture: CaptureAuthority, challenge: ChallengeAuthority,
        first: ReviewAuthority, second: ReviewAuthority,
        public_surface: PublicSurface, journal: EventJournal,
    ) -> None:
        self.capture = capture
        self.challenge = challenge
        self.first = first
        self.second = second
        self.surface = public_surface
        self.journal = journal

    def _record(
        self, record_id: str, disposition: str, evidence_sha256: str | None,
        codes: tuple[str, ...], now: datetime,
    ) -> RunReceipt:
        receipt = RunReceipt(record_id, disposition, evidence_sha256, codes, now)
        self.journal.append(receipt)
        return receipt

    def _withdraw(self, record_id: str) -> None:
        try:
            self.surface.withdraw(record_id)
            if self.surface.current_evidence_sha256(record_id) is not None:
                raise PublicationSafetyError("PUBLIC_WITHDRAWAL_UNCONFIRMED")
        except PublicationSafetyError:
            raise
        except Exception as exc:
            raise PublicationSafetyError("PUBLIC_WITHDRAWAL_UNCONFIRMED") from exc

    def _hold(
        self, record_id: str, evidence_sha256: str | None,
        codes: tuple[str, ...], now: datetime,
    ) -> RunReceipt:
        self._withdraw(record_id)
        return self._record(record_id, "HOLD", evidence_sha256, codes, now)

    def _read_capture(self, record_id: str) -> AutonomousCandidate | None:
        try:
            item = self.capture.current(record_id)
            return item if isinstance(item, AutonomousCandidate) else None
        except Exception:
            return None

    def _read_challenge(self, record_id: str) -> bool | None:
        try:
            held = self.challenge.current(record_id)
            return held if type(held) is bool else None
        except Exception:
            return None

    def evaluate_and_apply(self, record_id: str, *, now: datetime) -> RunReceipt:
        at = _now(now)
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("AUTONOMOUS_RECORD_ID_REQUIRED")
        item = self._read_capture(record_id)
        if item is None or item.record_id != record_id:
            return self._hold(record_id, None, ("ORIGINAL_UNAVAILABLE",), at)
        try:
            binding = candidate_fingerprint(item)
        except (ValueError, TypeError, OverflowError):
            return self._hold(record_id, None, ("ORIGINAL_INVALID",), at)
        held = self._read_challenge(record_id)
        if held is not False:
            # Withdraw before incurring any model work, even if the challenge
            # authority is unavailable rather than explicitly affirmative.
            return self._hold(
                record_id, binding,
                ("CHALLENGE_HOLD" if held else "CHALLENGE_STATUS_UNKNOWN",), at,
            )
        # Deterministic checks precede model calls; no costly independent
        # review is necessary when a source, rights or safety gate already fails.
        try:
            preliminary = evaluate_autonomous_publication(item, None, None)
        except (ValueError, TypeError, AttributeError):
            return self._hold(record_id, binding, ("EVIDENCE_INVALID",), at)
        failures = tuple(code for code in preliminary.reason_codes if code != "INDEPENDENT_REVIEW")
        if failures:
            return self._hold(record_id, binding, failures, at)
        try:
            first = self.first.review(item, binding)
            second = self.second.review(item, binding)
        except Exception:
            return self._hold(record_id, binding, ("INDEPENDENT_REVIEW_UNAVAILABLE",), at)
        if not (_review_identity_ok(first, self.first) and _review_identity_ok(second, self.second)):
            return self._hold(record_id, binding, ("REVIEW_EXECUTION_IDENTITY_MISMATCH",), at)
        try:
            decision: AutonomousDecision = evaluate_autonomous_publication(item, first, second)
        except (ValueError, TypeError, AttributeError):
            return self._hold(record_id, binding, ("INDEPENDENT_REVIEW_INVALID",), at)
        if not decision.publishable:
            return self._hold(record_id, binding, decision.reason_codes, at)
        if not _matches(self._read_capture(record_id), binding):
            return self._hold(record_id, binding, ("STALE_ORIGINAL",), at)
        if self._read_challenge(record_id) is not False:
            return self._hold(record_id, binding, ("CHALLENGE_HOLD",), at)
        packet = AutonomousProofPacket(item, first, second)
        self._record(record_id, "INTENT", binding, (), at)
        try:
            self.surface.publish(packet)
            readback = self.surface.current_evidence_sha256(record_id)
        except Exception:
            readback = None
        if readback != binding:
            return self._hold(record_id, binding, ("PUBLIC_READBACK_FAILED",), at)
        if not _matches(self._read_capture(record_id), binding):
            return self._hold(record_id, binding, ("STALE_ORIGINAL",), at)
        if self._read_challenge(record_id) is not False:
            return self._hold(record_id, binding, ("CHALLENGE_HOLD",), at)
        try:
            return self._record(record_id, "PUBLISH", binding, (), at)
        except Exception:
            self._withdraw(record_id)
            raise

    def audit_and_apply(
        self, packet: AutonomousProofPacket, auditor: ReviewAuthority,
        *, now: datetime,
    ) -> RunReceipt:
        at = _now(now)
        if not isinstance(packet, AutonomousProofPacket) or not isinstance(
            packet.candidate, AutonomousCandidate
        ):
            raise ValueError("AUTONOMOUS_AUDIT_PACKET_INVALID")
        item = packet.candidate
        record_id = item.record_id
        binding = candidate_fingerprint(item)
        try:
            prior = evaluate_autonomous_publication(item, packet.primary, packet.independent)
            visible = self.surface.current_evidence_sha256(record_id)
        except Exception:
            prior = None
            visible = None
        unchanged = (
            prior is not None and prior.publishable
            and _matches(self._read_capture(record_id), binding)
            and self._read_challenge(record_id) is False
            and visible == binding
        )
        model_ids = {
            review.model_id.strip().casefold() for review in (packet.primary, packet.independent)
            if isinstance(review, AgentReview) and isinstance(review.model_id, str)
        }
        actor_ids = {
            review.agent_id.strip().casefold() for review in (packet.primary, packet.independent)
            if isinstance(review, AgentReview) and isinstance(review.agent_id, str)
        }
        independent = (
            isinstance(getattr(auditor, "model_id", None), str)
            and isinstance(getattr(auditor, "agent_id", None), str)
            and bool(auditor.model_id.strip()) and bool(auditor.agent_id.strip())
            and auditor.model_id.strip().casefold() not in model_ids
            and auditor.agent_id.strip().casefold() not in actor_ids
        )
        third = None
        if unchanged and independent:
            try:
                third = auditor.review(item, binding)
            except Exception:
                pass
        if (
            not unchanged or not independent
            or not _review_identity_ok(third, auditor)
            or third.evidence_sha256 != binding
            or third.checked_stages != CHECKS
            or third.accepted is not True
            or not _matches(self._read_capture(record_id), binding)
            or self._read_challenge(record_id) is not False
            or not self._publicly_current(record_id, binding)
        ):
            self._withdraw(record_id)
            return self._record(
                record_id, "AUDIT_HOLD", binding, ("THIRD_REVIEW_FAILED",), at
            )
        return self._record(record_id, "AUDIT_PASS", binding, (), at)

    def _publicly_current(self, record_id: str, binding: str) -> bool:
        try:
            return self.surface.current_evidence_sha256(record_id) == binding
        except Exception:
            return False

    def audit_nightly_sample(
        self, *, journal_events: object, day: date, packet_authority: AuditPacketAuthority,
        third: ReviewAuthority, now: datetime,
    ) -> tuple[RunReceipt, ...]:
        """Execute the deterministic sample with a third independent model.

        A missing durable packet forces withdrawal and a visible AUDIT_HOLD.
        The scheduler must call this once per UTC night with trusted adapters.
        """
        at = _now(now)
        outcomes: list[RunReceipt] = []
        for record_id in nightly_sample(journal_events, day):
            try:
                packet = packet_authority.current_packet(record_id)
            except Exception:
                packet = None
            if not isinstance(packet, AutonomousProofPacket) or (
                not isinstance(packet.candidate, AutonomousCandidate)
                or packet.candidate.record_id != record_id
            ):
                self._withdraw(record_id)
                outcomes.append(self._record(
                    record_id, "AUDIT_HOLD", None, ("AUDIT_PACKET_UNAVAILABLE",), at,
                ))
            else:
                outcomes.append(self.audit_and_apply(packet, third, now=at))
        return tuple(outcomes)


def _events_on_day(events: object, day: date) -> tuple[RunReceipt, ...]:
    if not isinstance(day, date):
        raise TypeError("AUTONOMOUS_DAY_REQUIRED")
    return tuple(
        event for event in events
        if isinstance(event, RunReceipt) and event.at.astimezone(timezone.utc).date() == day
    )


def daily_metrics(events: object, day: date) -> dict[str, int | str]:
    """Privacy-safe UTC counters over an append-only, authority-read journal."""
    daily = _events_on_day(events, day)
    return {
        "day": day.isoformat(),
        "published": sum(e.disposition == "PUBLISH" for e in daily),
        "held": sum(e.disposition == "HOLD" for e in daily),
        "audited": sum(e.disposition in {"AUDIT_PASS", "AUDIT_HOLD"} for e in daily),
        "audit_holds": sum(e.disposition == "AUDIT_HOLD" for e in daily),
    }


def nightly_sample(events: object, day: date) -> tuple[str, ...]:
    """Deterministic 10% sample (at least one) of still-published daily items.

    Source/subject names and other private fields never enter the sample list.
    Its stable hash orders records regardless of query/ledger read order.
    """
    latest: dict[str, RunReceipt] = {}
    for event in sorted(
        _events_on_day(events, day),
        key=lambda e: (
            e.at, e.record_id,
            {"PUBLISH": 1, "HOLD": 2, "AUDIT_HOLD": 3}.get(e.disposition, 0),
            e.evidence_sha256 or "",
        ),
    ):
        if event.disposition in {"PUBLISH", "HOLD", "AUDIT_HOLD"}:
            latest[event.record_id] = event
    eligible = [
        event for event in latest.values() if event.disposition == "PUBLISH"
        and event.evidence_sha256 is not None
    ]
    eligible.sort(key=lambda event: (
        hashlib.sha256(
            f"{day.isoformat()}\0{event.record_id}\0{event.evidence_sha256}".encode()
        ).hexdigest(),
        event.record_id,
    ))
    return tuple(e.record_id for e in eligible[:math.ceil(len(eligible) / 10)])


__all__ = [
    "AutonomousOperations", "PublicationSafetyError", "RunReceipt", "daily_metrics",
    "nightly_sample",
]
