"""Bound the opt-in public Statement serializer to independent agent decisions."""

from __future__ import annotations

import hashlib
from typing import Any

from dichiarazioni_pubbliche.autonomous_publication import (
    AutonomousCandidate,
    AutonomousProofPacket,
    evaluate_autonomous_publication,
)


def require_autonomous_publication(
    row: dict[str, Any], source: object, immutable_text: str,
    original: str, locator: dict[str, Any],
) -> None:
    """Refuse any Statement whose current original, reviewers or holds disagree.

    Production readers must resolve these records from separately authenticated,
    durable capture and review stores; the candidate row has no authority.
    """
    read_packet = getattr(source, "autonomous_publication_evidence", None)
    read_challenge = getattr(source, "current_statement_challenge_hold", None)
    if not callable(read_packet) or not callable(read_challenge):
        raise ValueError("Statement autonomous authority or challenge reader absent")
    packet = read_packet(row["statement_id"], row["version_id"])
    if not isinstance(packet, AutonomousProofPacket):
        raise ValueError("Statement autonomous evidence packet absent")
    candidate = packet.candidate
    if not isinstance(candidate, AutonomousCandidate):
        raise ValueError("Statement autonomous candidate invalid")
    try:
        expected_start, expected_end = (
            (locator["start_ms"] / 1000, locator["end_ms"] / 1000)
            if row["source_kind"] == "TIMED"
            else (locator["start_char"], locator["end_char"])
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Statement autonomous locator invalid") from exc
    if (
        candidate.record_id != row["statement_id"]
        or candidate.source_url != row["source_url"]
        or candidate.source_kind != row["source_kind"]
        or candidate.snapshot_sha256 != hashlib.sha256(immutable_text.encode()).hexdigest()
        or candidate.quote != original
        or candidate.transcript_segment != original
        or candidate.speaker_id != row["person_id"]
        or candidate.source_length_chars != len(immutable_text)
        or candidate.segment_start != expected_start
        or candidate.segment_end != expected_end
    ):
        raise ValueError("Statement autonomous evidence differs from original source")
    active_challenge = read_challenge(row["statement_id"], row["version_id"])
    if type(active_challenge) is not bool:
        raise ValueError("Statement current challenge status unavailable")
    decision = evaluate_autonomous_publication(
        candidate, packet.primary, packet.independent,
        active_challenge=active_challenge,
    )
    if not decision.publishable:
        raise ValueError("Statement autonomous review HOLD: " + ",".join(decision.reason_codes))


__all__ = ["require_autonomous_publication"]
