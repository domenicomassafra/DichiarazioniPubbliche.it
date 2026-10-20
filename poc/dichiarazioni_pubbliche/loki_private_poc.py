"""Opt-in fixture-only assessment of three Loki donor stages; no authority."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from dichiarazioni_pubbliche.loki_decompose_poc import Decompose, LokiSpan
from dichiarazioni_pubbliche.loki_checkworthy_poc import Checkworthy
from dichiarazioni_pubbliche.loki_query_generator_poc import QueryGenerator

DONOR_COMMIT = "6e1ee9e5159abe544c342689093afe12b908a419"
DONOR_VERSION = "v0.0.2+6e1ee9e"
ADAPTER_VERSION = "dp160-loki-private-poc-v1"


@dataclass(frozen=True)
class LokiProposal:
    claim: str
    source_start: int
    source_end: int
    claim_type: str
    check_worthy: bool
    query_suggestions: tuple[str, ...]


@dataclass(frozen=True)
class LokiResult:
    status: str
    reason_code: str
    proposals: tuple[LokiProposal, ...]
    receipt: dict[str, object]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LokiPrivatePOC:
    """No dependency injection of clients: every input is an offline string."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = (
            os.environ.get("DP_LOKI_OFFLINE_POC", "") == "1"
            if enabled is None else enabled
        )

    def compare(
        self, *, doc: str, language: str, claim_types: dict[str, str],
        decomposition: str, restoration: str, checkworthiness: str,
        queries: str, reported_speech: bool = False,
    ) -> LokiResult:
        if not self.enabled:
            raise ValueError("LOKI_POC_DISABLED")
        if not all(isinstance(value, str) for value in
                   (doc, language, decomposition, restoration, checkworthiness, queries)):
            raise ValueError("LOKI_POC_FIXTURE_ONLY")
        receipt: dict[str, object] = {
            "adapter": ADAPTER_VERSION, "donor": "Libr-AI/OpenFactVerification",
            "donor_commit": DONOR_COMMIT, "donor_version": DONOR_VERSION,
            "modules": ["Decompose.py", "CheckWorthy.py", "QueryGenerator.py"],
            "input_sha256": _hash(doc), "language": language,
            "provider_calls": 0, "provider_cost_usd": "0",
            "publication_authority": False, "persisted": False,
        }
        reason = "LOKI_PROPOSALS_REQUIRE_REVIEW"
        proposals: tuple[LokiProposal, ...] = ()
        try:
            if language not in {"it", "en", "de", "fr", "es"}:
                raise ValueError("LOKI_LANGUAGE_UNSUPPORTED")
            if not isinstance(claim_types, dict) or len(claim_types) > 12:
                raise ValueError("LOKI_CLAIM_TYPES_INVALID")
            spans: tuple[LokiSpan, ...] = Decompose().getclaims(
                doc, decomposition, restoration,
            )
            claims = tuple(span.claim for span in spans)
            worthy = Checkworthy().identify_checkworthiness(
                claims, claim_types, checkworthiness,
            )
            suggested = QueryGenerator().generate_query(claims, worthy, queries)
            if reported_speech:
                raise ValueError("LOKI_REPORTED_SPEECH_REQUIRES_ATTRIBUTION")
            proposals = tuple(
                LokiProposal(span.claim, span.start, span.end,
                             claim_types[span.claim], check, suggested[span.claim])
                for span, check in zip(spans, worthy)
            )
        except (ValueError, TypeError, KeyError) as exc:
            reason = str(exc) if str(exc).startswith("LOKI_") else "LOKI_MALFORMED_FIXTURE"
        receipt["status"] = "HOLD"
        receipt["reason_code"] = reason
        receipt["proposal_count"] = len(proposals)
        receipt["result_sha256"] = _hash(json.dumps(
            [(row.claim, row.source_start, row.source_end, row.claim_type,
              row.check_worthy, row.query_suggestions) for row in proposals],
            ensure_ascii=False, separators=(",", ":"),
        ))
        return LokiResult("HOLD", reason, proposals, receipt)
