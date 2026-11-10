"""Compose the existing, independently authenticated Senato v3 proof readers.

This only creates a private projection source. It cannot approve a candidate,
issue a rights grant, execute a model review or publish a release.
"""

from __future__ import annotations

from typing import Callable, Mapping

from .autonomous_publication import AutonomousCandidate
from .autonomous_review_reader import JournalReviewPacketReader
from .autonomous_runner_v3 import SQLiteRunJournal
from .public_statement_authority import (
    JournalAuthorityReviewPacketReader, PublicStatementAuthorityReader,
    PublicStatementAuthorityStore, PublicStatementChallengeStore,
)
from .senato_public_v3_source import (
    CurrentSenatoCaptureBytes, PinnedSenatoV3Source, SenatoPublicV3Source,
)
from .senato_v3_postgres_candidates import CurrentSenatoPostgresCandidates


def bind_senato_public_v3(
    *,
    pins: PinnedSenatoV3Source,
    capture_store: object,
    body_store: object,
    private_source_guard: object,
    journal: SQLiteRunJournal,
    read_current_candidate: Callable[[str, str], AutonomousCandidate | None],
    verify_provider_execution: Callable[[Mapping[str, object]], bool],
    verify_authority_review: Callable[[Mapping[str, object]], bool],
    processing_family_approved: Callable[[], bool],
    primary_agent_id: str,
    primary_model_id: str,
    independent_agent_id: str | None = None,
    independent_model_id: str | None = None,
    third_agent_id: str | None = None,
    third_model_id: str | None = None,
) -> SenatoPublicV3Source:
    """Return a fail-closed source bound to real current Capture and review stores.

    The caller must supply independently authenticated provider execution and
    authority witnesses, plus a current GDPR decision reader. A local journal,
    model output, or a bare status flag cannot establish their authenticity.
    """
    if (not isinstance(journal, SQLiteRunJournal)
            or any(not callable(reader) for reader in (
                read_current_candidate, verify_provider_execution,
                verify_authority_review, processing_family_approved,
            ))):
        raise ValueError("DP468_TRUSTED_AUTHORITY_REQUIRED")

    capture = CurrentSenatoCaptureBytes(
        pins, capture_store=capture_store, body_store=body_store,
        private_source_guard=private_source_guard,
    )
    candidates = CurrentSenatoPostgresCandidates(pins, store=capture_store)
    model_reviews = JournalReviewPacketReader(
        journal=journal,
        read_current_candidate=read_current_candidate,
        verify_provider_execution=verify_provider_execution,
        primary_agent_id=primary_agent_id, primary_model_id=primary_model_id,
        independent_agent_id=independent_agent_id,
        independent_model_id=independent_model_id,
        third_agent_id=third_agent_id,
        third_model_id=third_model_id,
    )
    authority_store = PublicStatementAuthorityStore(
        store=capture_store, model_execution_reader=model_reviews,
    )
    authority_reviews = JournalAuthorityReviewPacketReader(
        authority_store=authority_store,
        read_authority_review_packet=model_reviews.authority_packet,
    )
    source_binding = SenatoPublicV3Source(
        pins, read_original_bytes=capture, read_current_candidates=candidates,
    )
    authorities = PublicStatementAuthorityReader(
        authority_store=authority_store,
        challenge_store=PublicStatementChallengeStore(store=capture_store),
        read_current_binding=source_binding.current_statement_binding,
        read_current_autonomous_evidence=model_reviews,
        read_current_authority_reviews=authority_reviews,
        processing_family_approved=processing_family_approved,
        verify_authority_review=verify_authority_review,
    )
    return SenatoPublicV3Source(
        pins, read_original_bytes=capture, read_current_candidates=candidates,
        read_current_attestations=authorities.statement_publication_attestations,
        read_current_autonomous_evidence=authorities.autonomous_publication_evidence,
        read_current_challenge_hold=authorities.current_statement_challenge_hold,
    )
