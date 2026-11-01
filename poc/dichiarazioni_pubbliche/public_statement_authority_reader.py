"""Source-bound private reader for all public Statement v3 gates."""
from __future__ import annotations
from typing import Callable, Mapping
from .autonomous_publication import AutonomousProofPacket
from .public_statement_authority_common import (
    AuthorityReviewPacket, _MODEL_REVIEW_KINDS, _review_evidence,
    validate_statement_binding,
)
from .public_statement_authority_store import PublicStatementAuthorityStore
from .public_statement_challenge import PublicStatementChallengeStore


class JournalAuthorityReviewPacketReader:
    """Rehydrate decision-specific review packets from the current authority ledger."""

    def __init__(
        self, *, authority_store: PublicStatementAuthorityStore,
        read_authority_review_packet: Callable[
            [str, str, str, Mapping[str, object]], AuthorityReviewPacket | None
        ],
    ):
        if (not isinstance(authority_store, PublicStatementAuthorityStore)
                or not callable(read_authority_review_packet)):
            raise ValueError("DP468_AUTHORITY_REVIEW_READERS_REQUIRED")
        self.authority_store = authority_store
        self.read_packet = read_authority_review_packet

    def __call__(
        self, statement_id: str, version_id: str,
    ) -> dict[str, AuthorityReviewPacket] | None:
        try:
            rows = self.authority_store.events(statement_id, version_id)
            latest = {
                str(row["authority_kind"]): row for row in rows
                if isinstance(row, Mapping)
            }
            if any(
                kind not in latest or latest[kind].get("status") != "APPROVED"
                or not isinstance(latest[kind].get("payload"), Mapping)
                for kind in _MODEL_REVIEW_KINDS
            ):
                return None
            packets: dict[str, AuthorityReviewPacket] = {}
            for kind in _MODEL_REVIEW_KINDS:
                row = latest[kind]
                packet = self.read_packet(
                    statement_id, version_id, kind, row["payload"],
                )
                if not isinstance(packet, AuthorityReviewPacket):
                    return None
                packets[kind] = packet
            fresh = self.authority_store.events(statement_id, version_id)
            fresh_latest = {
                str(row["authority_kind"]): row for row in fresh
                if isinstance(row, Mapping)
            }
            if any(
                fresh_latest.get(kind, {}).get("event_id")
                != latest[kind].get("event_id")
                or fresh_latest.get(kind, {}).get("payload") != latest[kind].get("payload")
                for kind in _MODEL_REVIEW_KINDS
            ):
                return None
            return packets
        except Exception:
            return None

class PublicStatementAuthorityReader:
    """Bind v3 attestations, model reviews and challenges to current records."""

    def __init__(
        self, *, authority_store: PublicStatementAuthorityStore,
        challenge_store: PublicStatementChallengeStore,
        read_current_binding: Callable[[str, str], Mapping[str, object] | None],
        read_current_autonomous_evidence: Callable[[str, str], object | None],
        read_current_authority_reviews: Callable[
            [str, str], Mapping[str, AuthorityReviewPacket] | None
        ],
        processing_family_approved: Callable[[], bool],
        verify_authority_review: Callable[[Mapping[str, object]], bool] | None = None,
    ):
        if (not callable(read_current_binding)
                or not callable(read_current_autonomous_evidence)
                or not callable(read_current_authority_reviews)
                or not callable(processing_family_approved)):
            raise ValueError("DP468_AUTHORITY_READERS_REQUIRED")
        self.authority_store = authority_store
        self.challenge_store = challenge_store
        self.read_current_binding = read_current_binding
        self.read_review = read_current_autonomous_evidence
        self.read_authority_reviews = read_current_authority_reviews
        self.processing_family_approved = processing_family_approved
        self.verify_authority_review = verify_authority_review

    def statement_publication_attestations(
        self, statement_id: str, version_id: str,
    ) -> dict[str, dict[str, object]] | None:
        try:
            if self.processing_family_approved() is not True:
                return None
            binding = self.read_current_binding(statement_id, version_id)
            packet = self.read_review(statement_id, version_id)
            authority_packets = self.read_authority_reviews(statement_id, version_id)
            if (not isinstance(binding, Mapping)
                    or not isinstance(packet, AutonomousProofPacket)
                    or not isinstance(authority_packets, Mapping)):
                return None
            parsed_binding = validate_statement_binding(binding)
            if (parsed_binding["statement_id"] != statement_id
                    or parsed_binding["version_id"] != version_id):
                return None
            attestations = self.authority_store.current_attestations(
                binding=binding, review_packet=packet,
                authority_review_packets=authority_packets,
                verify_authority_review=self.verify_authority_review,
            )
            if (not attestations or self.processing_family_approved() is not True
                    or self.read_current_binding(statement_id, version_id) != binding
                    or self.read_review(statement_id, version_id) != packet
                    or self.read_authority_reviews(statement_id, version_id) != authority_packets):
                return None
            return attestations
        except Exception:
            return None

    def autonomous_publication_evidence(
        self, statement_id: str, version_id: str,
    ) -> object | None:
        try:
            if self.processing_family_approved() is not True:
                return None
            binding = self.read_current_binding(statement_id, version_id)
            if not isinstance(binding, Mapping):
                return None
            parsed_binding = validate_statement_binding(binding)
            if (parsed_binding["statement_id"] != statement_id
                    or parsed_binding["version_id"] != version_id):
                return None
            packet = self.read_review(statement_id, version_id)
            if not isinstance(packet, AutonomousProofPacket):
                return None
            _review_evidence(packet, parsed_binding)
            if (self.processing_family_approved() is not True
                    or self.read_current_binding(statement_id, version_id) != binding
                    or self.read_review(statement_id, version_id) != packet):
                return None
            return packet
        except Exception:
            return None

    def current_statement_challenge_hold(
        self, statement_id: str, version_id: str,
    ) -> bool | None:
        try:
            if self.processing_family_approved() is not True:
                return None
            binding = self.read_current_binding(statement_id, version_id)
            if not isinstance(binding, Mapping):
                return None
            parsed = validate_statement_binding(binding)
            if (parsed["statement_id"] != statement_id
                    or parsed["version_id"] != version_id):
                return None
            hold = self.challenge_store.current_hold(statement_id, version_id)
            if (self.processing_family_approved() is not True
                    or self.read_current_binding(statement_id, version_id) != binding):
                return None
            return hold
        except Exception:
            return None
