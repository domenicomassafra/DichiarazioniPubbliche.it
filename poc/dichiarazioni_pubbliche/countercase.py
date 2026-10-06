from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable


COUNTERCASE_VERSION = "countercase-v1"
COUNTER_RELATIONS = frozenset({"CONTRADICT", "LIMITATION", "CONTEXT", "UPDATE"})


@dataclass(frozen=True)
class CounterEvidence:
    evidence_id: str
    relation: str
    rationale_code: str
    approved: bool
    suitable: bool
    independence_group: str | None = None

    def __post_init__(self) -> None:
        if not str(self.evidence_id or "").strip():
            raise ValueError("COUNTER_EVIDENCE_ID_REQUIRED")
        if self.relation not in COUNTER_RELATIONS:
            raise ValueError("COUNTER_EVIDENCE_RELATION_INVALID")
        if not str(self.rationale_code or "").strip():
            raise ValueError("COUNTER_EVIDENCE_RATIONALE_REQUIRED")


@dataclass(frozen=True)
class CounterCasePacket:
    packet_id: str
    claim_id: str
    evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    limitation_evidence_ids: tuple[str, ...]
    context_evidence_ids: tuple[str, ...]
    update_evidence_ids: tuple[str, ...]
    rationale_codes: tuple[str, ...]
    independence_groups: tuple[str, ...]
    status: str
    blockers: tuple[str, ...]
    version: str = COUNTERCASE_VERSION

    @property
    def has_material_countercase(self) -> bool:
        return bool(self.contradicting_evidence_ids or self.limitation_evidence_ids)


@dataclass(frozen=True)
class ChallengerReadinessDecision:
    status: str
    packet_id: str
    blockers: tuple[str, ...]
    review_stale: bool
    version: str = COUNTERCASE_VERSION

    @property
    def ready(self) -> bool:
        return self.status == "READY"


def build_countercase_packet(
    *,
    claim_id: str,
    evidence: Iterable[CounterEvidence],
    research_complete: bool,
) -> CounterCasePacket:
    claim = str(claim_id or "").strip()
    if not claim:
        raise ValueError("COUNTERCASE_CLAIM_ID_REQUIRED")
    rows = tuple(evidence)
    admissible = tuple(row for row in rows if row.approved and row.suitable)
    rejected_count = len(rows) - len(admissible)

    by_relation = {
        relation: tuple(
            sorted(
                row.evidence_id
                for row in admissible
                if row.relation == relation
            )
        )
        for relation in COUNTER_RELATIONS
    }
    rationale = tuple(sorted({row.rationale_code for row in admissible}))
    lineages = tuple(
        sorted(
            {
                row.independence_group
                for row in admissible
                if row.independence_group
            }
        )
    )
    blockers: list[str] = []
    if not research_complete:
        blockers.append("CHALLENGER_RESEARCH_INCOMPLETE")
    if rejected_count:
        blockers.append("UNAPPROVED_OR_UNSUITABLE_COUNTEREVIDENCE_IGNORED")

    status = (
        "READY"
        if research_complete
        else "INCOMPLETE"
    )
    material = {
        "claim_id": claim,
        "evidence_ids": sorted(row.evidence_id for row in admissible),
        "relations": {
            key: list(value)
            for key, value in sorted(by_relation.items())
        },
        "rationale_codes": list(rationale),
        "independence_groups": list(lineages),
        "research_complete": bool(research_complete),
        "version": COUNTERCASE_VERSION,
    }
    packet_id = "countercase:" + hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return CounterCasePacket(
        packet_id=packet_id,
        claim_id=claim,
        evidence_ids=tuple(sorted(row.evidence_id for row in admissible)),
        contradicting_evidence_ids=by_relation["CONTRADICT"],
        limitation_evidence_ids=by_relation["LIMITATION"],
        context_evidence_ids=by_relation["CONTEXT"],
        update_evidence_ids=by_relation["UPDATE"],
        rationale_codes=rationale,
        independence_groups=lineages,
        status=status,
        blockers=tuple(blockers),
    )


def evaluate_challenger_readiness(
    packet: CounterCasePacket,
    *,
    incorporated_packet_id: str | None,
    reviewed_packet_id: str | None,
    high_risk: bool = False,
    qualified_policy_waives_challenger: bool = False,
) -> ChallengerReadinessDecision:
    """Bind readiness/review to the exact challenger packet that was incorporated.

    A newly material counter-case cannot inherit readiness from an older packet/review.
    High-risk callers must also show an exact incorporated challenger packet unless a
    separately supplied qualified policy explicitly waives that step.
    """
    blockers: list[str] = []
    if packet.status != "READY":
        blockers.append("CHALLENGER_PACKET_NOT_READY")

    incorporated = str(incorporated_packet_id or "").strip()
    reviewed = str(reviewed_packet_id or "").strip()
    exact_incorporation = incorporated == packet.packet_id
    exact_review = reviewed == packet.packet_id

    if packet.has_material_countercase and not exact_incorporation:
        blockers.append("MATERIAL_CHALLENGER_NOT_INCORPORATED")
    if packet.has_material_countercase and not exact_review:
        blockers.append("CHALLENGER_REVIEW_STALE")

    if high_risk and not qualified_policy_waives_challenger:
        if not exact_incorporation:
            blockers.append("HIGH_RISK_CHALLENGER_REQUIRED")
        if not exact_review:
            blockers.append("HIGH_RISK_CHALLENGER_REVIEW_REQUIRED")

    normalized = tuple(dict.fromkeys(blockers))
    return ChallengerReadinessDecision(
        status="READY" if not normalized else "STALE",
        packet_id=packet.packet_id,
        blockers=normalized,
        review_stale=(
            (packet.has_material_countercase or high_risk)
            and not exact_review
            and not (high_risk and qualified_policy_waives_challenger)
        ),
    )


__all__ = [
    "COUNTERCASE_VERSION",
    "COUNTER_RELATIONS",
    "CounterCasePacket",
    "CounterEvidence",
    "ChallengerReadinessDecision",
    "build_countercase_packet",
    "evaluate_challenger_readiness",
]
