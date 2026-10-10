from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from dichiarazioni_pubbliche.high_risk_assertion import HighRiskDecision


COUNTERCASE_VERSION = "countercase-v2"
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
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip() or len(self.evidence_id) > 512:
            raise ValueError("COUNTER_EVIDENCE_ID_REQUIRED")
        if self.relation not in COUNTER_RELATIONS:
            raise ValueError("COUNTER_EVIDENCE_RELATION_INVALID")
        if not isinstance(self.rationale_code, str) or not self.rationale_code.strip() or len(self.rationale_code) > 512:
            raise ValueError("COUNTER_EVIDENCE_RATIONALE_REQUIRED")
        if type(self.approved) is not bool or type(self.suitable) is not bool:
            raise ValueError("COUNTER_EVIDENCE_APPROVAL_MUST_BE_BOOLEAN")
        if self.independence_group is not None and (
            not isinstance(self.independence_group, str)
            or not self.independence_group.strip()
            or len(self.independence_group) > 512
        ):
            raise ValueError("COUNTER_EVIDENCE_LINEAGE_INVALID")


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
        # CONTEXT/UPDATE are not verdicts, but newly approved contextual or
        # later-outcome evidence must also stale a previously reviewed packet.
        return bool(
            self.contradicting_evidence_ids or self.limitation_evidence_ids
            or self.context_evidence_ids or self.update_evidence_ids
        )


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
    if not isinstance(claim_id, str) or not claim or len(claim) > 512:
        raise ValueError("COUNTERCASE_CLAIM_ID_REQUIRED")
    if type(research_complete) is not bool:
        raise ValueError("COUNTERCASE_RESEARCH_COMPLETE_MUST_BE_BOOLEAN")
    rows = tuple(evidence)
    # Never allow two versions or reviewer interpretations of one evidence ID
    # to masquerade as separate independent challenger material.
    identities = [row.evidence_id for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("COUNTERCASE_DUPLICATE_EVIDENCE_ID")
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
        # A reviewed packet must bind each approved source to its exact
        # rationale and lineage. Aggregate sets alone allow swapping those
        # assignments without changing packet_id (and hence review freshness).
        "evidence_bindings": [
            {
                "evidence_id": row.evidence_id,
                "relation": row.relation,
                "rationale_code": row.rationale_code,
                "independence_group": row.independence_group,
            }
            for row in sorted(
                admissible,
                key=lambda row: (
                    row.evidence_id,
                    row.relation,
                    row.rationale_code,
                    row.independence_group or "",
                ),
            )
        ],
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


def evaluate_high_risk_challenger_readiness(
    packet: CounterCasePacket,
    *,
    high_risk_decision: HighRiskDecision,
    incorporated_packet_id: str | None,
    reviewed_packet_id: str | None,
    challenger_waiver_policy_decision_ref: str | None = None,
) -> ChallengerReadinessDecision:
    """Bind DP-229 readiness to the actual DP-309 high-risk decision.

    A waiver is accepted only when it names the exact qualified policy decision already
    carried by an otherwise publication-eligible DP-309 decision. Passing a free boolean
    is deliberately insufficient at this integration seam.
    """

    high_risk = bool(high_risk_decision.signals.requires_escalation)
    waiver_ref = str(challenger_waiver_policy_decision_ref or "").strip()
    qualified_waiver = bool(
        high_risk
        and high_risk_decision.publication_allowed
        and waiver_ref
        and waiver_ref == str(high_risk_decision.policy_decision_ref or "")
    )
    return evaluate_challenger_readiness(
        packet,
        incorporated_packet_id=incorporated_packet_id,
        reviewed_packet_id=reviewed_packet_id,
        high_risk=high_risk,
        qualified_policy_waives_challenger=qualified_waiver,
    )


__all__ = [
    "COUNTERCASE_VERSION",
    "COUNTER_RELATIONS",
    "CounterCasePacket",
    "CounterEvidence",
    "ChallengerReadinessDecision",
    "build_countercase_packet",
    "evaluate_challenger_readiness",
    "evaluate_high_risk_challenger_readiness",
]
