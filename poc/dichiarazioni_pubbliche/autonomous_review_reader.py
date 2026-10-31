"""DP-413: replay private model execution receipts for the Statement v3 gate.

This reader has no authority to grant rights or approve a source. Its candidate
reader must independently recheck the current, durable capture and permissions.
The private journal must be writable only by the trusted OmniRoute adapter.
Missing, ambiguous or stale evidence always yields no publication packet.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Callable, Mapping

from dichiarazioni_pubbliche.autonomous_agent_review import PROMPT_VERSION
from dichiarazioni_pubbliche.autonomous_publication import (
    AgentReview, AutonomousCandidate, AutonomousProofPacket, CHECKS,
    POLICY_VERSION, candidate_fingerprint, independent_review_models_authorized,
)
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal
from dichiarazioni_pubbliche.claim_runtime import matches_returned_model

_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class JournalReviewPacketReader:
    """Read exactly one verified completion per configured independent agent.

    Bind this to `SenatoPublicV3Source.read_current_autonomous_evidence`.
    The source still needs independent attestation and challenge readers.
    """

    def __init__(
        self, *,
        journal: SQLiteRunJournal,
        read_current_candidate: Callable[[str, str], AutonomousCandidate | None],
        verify_provider_execution: Callable[[Mapping[str, object]], bool] | None = None,
        primary_agent_id: str,
        primary_model_id: str,
        independent_agent_id: str,
        independent_model_id: str,
    ) -> None:
        if not isinstance(journal, SQLiteRunJournal) or not callable(read_current_candidate):
            raise ValueError("DP413_REVIEW_AUTHORITY_REQUIRED")
        for agent in (primary_agent_id, independent_agent_id):
            if type(agent) is not str or not agent or agent != agent.strip():
                raise ValueError("DP413_REVIEW_AGENT_INVALID")
        if primary_agent_id.casefold() == independent_agent_id.casefold():
            raise ValueError("DP413_REVIEW_AGENTS_NOT_INDEPENDENT")
        if not independent_review_models_authorized(
            primary_model_id, independent_model_id,
        ):
            raise ValueError("DP413_REVIEW_MODELS_NOT_INDEPENDENT")
        self.journal = journal
        self.read_current_candidate = read_current_candidate
        # This MUST query an independently authenticated OmniRoute execution
        # authority and bind the actual request, key/connection scope, returned
        # model, prompt/evidence hash and usage to this exact receipt. A local
        # journal entry, HMAC from the same writer or hardcoded True is not proof.
        self.verify_provider_execution = verify_provider_execution
        self.identities = (
            (primary_agent_id, primary_model_id),
            (independent_agent_id, independent_model_id),
        )

    @staticmethod
    def _matches(
        receipt: object, candidate: AutonomousCandidate, binding: str,
        agent_id: str, model_id: str,
    ) -> bool:
        if not isinstance(receipt, dict):
            return False
        usage = receipt.get("usage")
        citations = receipt.get("stage_citations")
        if (not isinstance(usage, dict)
                or type(usage.get("prompt_tokens")) is not int
                or usage["prompt_tokens"] <= 0
                or type(usage.get("completion_tokens")) is not int
                or usage["completion_tokens"] < 0
                or not isinstance(citations, dict)
                or set(citations) != set(CHECKS)
                or any(not isinstance(values, list)
                       or not values or any(type(value) is not str or not value
                                            for value in values)
                       for values in citations.values())):
            return False
        canonical_sources = {
            "PROVENANCE": {candidate.source_url, candidate.snapshot_url},
            "WORDING": {candidate.snapshot_url},
            "SPEAKER": {candidate.public_role_source_url or candidate.public_context_source_url},
            "PERSON": {candidate.public_role_source_url or candidate.public_context_source_url},
            "RIGHTS_PRIVACY": {candidate.rights_citation_url, candidate.privacy_citation_url},
        }
        return (
            receipt.get("agent_id") == agent_id
            and receipt.get("requested_model") == model_id
            and matches_returned_model(model_id, receipt.get("returned_model"))
            and receipt.get("provider") == "omniroute"
            and type(receipt.get("provider_request_id")) is str
            and bool(receipt["provider_request_id"].strip())
            and receipt.get("policy_version") == POLICY_VERSION
            and receipt.get("prompt_version") == PROMPT_VERSION
            and type(receipt.get("prompt_sha256")) is str
            and _SHA256.fullmatch(receipt["prompt_sha256"]) is not None
            and receipt.get("record_id") == candidate.record_id
            and receipt.get("record_version_id") == candidate.record_version_id
            and receipt.get("source_version") == candidate.source_version
            and receipt.get("source_sha256") == candidate.snapshot_sha256
            and receipt.get("statement_sha256") == candidate.source_text_sha256
            and receipt.get("rights_attestation_sha256") == candidate.rights_attestation_sha256
            and receipt.get("evidence_sha256") == binding
            and receipt.get("accepted") is True
            and all(required <= set(citations[stage])
                    for stage, required in canonical_sources.items())
        )

    def __call__(self, record_id: str, version_id: str) -> AutonomousProofPacket | None:
        if (type(record_id) is not str or not record_id
                or type(version_id) is not str or not version_id
                or not callable(self.verify_provider_execution)):
            return None
        try:
            candidate = self.read_current_candidate(record_id, version_id)
            if (not isinstance(candidate, AutonomousCandidate)
                    or candidate.record_id != record_id
                    or candidate.record_version_id != version_id):
                return None
            binding = candidate_fingerprint(candidate)
            receipts = self.journal.review_executions(binding)
            reviews = []
            for agent_id, model_id in self.identities:
                matching = [
                    receipt for receipt in receipts
                    if isinstance(receipt, dict) and receipt.get("agent_id") == agent_id
                ]
                if len(matching) != 1 or not self._matches(
                    matching[0], candidate, binding, agent_id, model_id,
                ):
                    return None
                # A syntactically valid journal row is only a local claim:
                # require an independent, currently authenticated execution
                # witness before it can become a publication review.
                if self.verify_provider_execution(
                    MappingProxyType(matching[0]),
                ) is not True:
                    return None
                reviews.append(AgentReview(agent_id, model_id, binding, CHECKS, True))
            # Refuse a mid-read revocation, version change or rights change.
            if self.read_current_candidate(record_id, version_id) != candidate:
                return None
            return AutonomousProofPacket(candidate, reviews[0], reviews[1])
        except Exception:
            # Reader errors must never create a publishable packet.
            return None


__all__ = ["JournalReviewPacketReader"]
