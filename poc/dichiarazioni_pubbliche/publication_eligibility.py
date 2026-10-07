from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from dichiarazioni_pubbliche.countercase import ChallengerReadinessDecision
from dichiarazioni_pubbliche.high_risk_assertion import HighRiskDecision
from dichiarazioni_pubbliche.publication_review_control import (
    PublicationReviewEvent,
    ReviewRiskClass,
    evaluate_publication_review,
    high_risk_binding_sha256,
)
from dichiarazioni_pubbliche.publication_review_persistence import (
    PublicationReviewPersistenceStore,
    ReviewerIdentityAuthority,
)
from dichiarazioni_pubbliche.publication_safety import PublicationSafetyResult


PUBLICATION_ELIGIBILITY_VERSION = "publication-eligibility-v1"


@dataclass(frozen=True)
class PublicationEligibilityResult:
    disposition: str
    blockers: tuple[str, ...]
    safety_binding_sha256: str
    high_risk_binding_sha256: str
    review_policy_version: str
    review_risk_class: ReviewRiskClass
    counted_review_event_ids: tuple[str, ...]
    binding_sha256: str
    challenger_packet_id: str | None = None
    challenger_version: str | None = None
    challenger_waiver_policy_decision_ref: str | None = None
    profile_version: str = PUBLICATION_ELIGIBILITY_VERSION


def _binding_sha256(
    *,
    record_id: str,
    record_version: str,
    safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
    high_risk_binding: str,
    review_policy_version: str,
    review_risk_class: ReviewRiskClass,
    review_disposition: str,
    counted_event_ids: tuple[str, ...],
    challenger_readiness: ChallengerReadinessDecision | None,
    challenger_waiver_policy_decision_ref: str | None,
) -> str:
    payload = {
        "profile_version": PUBLICATION_ELIGIBILITY_VERSION,
        "record_id": str(record_id),
        "record_version": str(record_version),
        "publication_safety": {
            "profile_version": str(safety.profile_version),
            "binding_sha256": str(safety.binding_sha256),
            "disposition": str(safety.disposition),
        },
        "high_risk": {
            "version": str(high_risk.version),
            "binding_sha256": high_risk_binding,
            "disposition": str(high_risk.disposition),
        },
        "publication_review": {
            "policy_version": str(review_policy_version),
            "risk_class": str(review_risk_class),
            "disposition": str(review_disposition),
            "counted_event_ids": list(counted_event_ids),
        },
        "challenger": (
            None
            if challenger_readiness is None
            else {
                "version": str(challenger_readiness.version),
                "packet_id": str(challenger_readiness.packet_id),
                "status": str(challenger_readiness.status),
                "blockers": list(challenger_readiness.blockers),
                "review_stale": bool(challenger_readiness.review_stale),
            }
        ),
        "challenger_waiver_policy_decision_ref": challenger_waiver_policy_decision_ref,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evaluate_publication_eligibility_from_events(
    *,
    record_id: str,
    record_version: str,
    publication_safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
    high_risk_input_binding_sha256: str,
    review_events: Iterable[PublicationReviewEvent],
    upstream_actor_refs: Iterable[str] = (),
    upstream_credential_fingerprints: Iterable[str] = (),
    challenger_readiness: ChallengerReadinessDecision | None = None,
    challenger_waiver_policy_decision_ref: str | None = None,
) -> PublicationEligibilityResult:
    """Pure DP-308/309/310 composition over caller-supplied events.

    This is a deterministic policy/testing primitive, not a runtime publication-authority
    boundary. Runtime callers must use :func:`evaluate_publication_eligibility`, which obtains
    review events only through authority-attested durable replay.
    """

    review = evaluate_publication_review(
        record_id=record_id,
        record_version=record_version,
        publication_safety=publication_safety,
        high_risk=high_risk,
        high_risk_input_binding_sha256=high_risk_input_binding_sha256,
        events=review_events,
        upstream_actor_refs=upstream_actor_refs,
        upstream_credential_fingerprints=upstream_credential_fingerprints,
    )
    high_risk_binding = high_risk_binding_sha256(
        high_risk,
        input_binding_sha256=high_risk_input_binding_sha256,
    )

    blockers = list(review.blockers)
    waiver_ref = str(challenger_waiver_policy_decision_ref or "").strip()
    qualified_challenger_waiver = bool(
        high_risk.signals.requires_escalation
        and high_risk.publication_allowed
        and waiver_ref
        and waiver_ref == str(high_risk.policy_decision_ref or "")
    )
    if high_risk.signals.requires_escalation and not qualified_challenger_waiver:
        if challenger_readiness is None:
            blockers.append("HIGH_RISK_CHALLENGER_REQUIRED")
        elif not challenger_readiness.ready:
            blockers.append("HIGH_RISK_CHALLENGER_NOT_READY")
            blockers.extend(challenger_readiness.blockers)
    if not publication_safety.eligible:
        if "UPSTREAM_PUBLICATION_SAFETY_NOT_ELIGIBLE" not in blockers:
            blockers.append("UPSTREAM_PUBLICATION_SAFETY_NOT_ELIGIBLE")
    if not review.review_complete:
        blockers.append("PUBLICATION_REVIEW_INCOMPLETE")
    if (
        review.risk_class in {ReviewRiskClass.HIGH, ReviewRiskClass.LEGAL}
        and not review.dual_control_satisfied
    ):
        blockers.append("REVIEW_SEPARATION_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    disposition = (
        "ELIGIBLE_FOR_PROJECTION_REVALIDATION"
        if not blockers
        else "HOLD_FOR_PUBLICATION_REVIEW"
    )
    binding = _binding_sha256(
        record_id=record_id,
        record_version=record_version,
        safety=publication_safety,
        high_risk=high_risk,
        high_risk_binding=high_risk_binding,
        review_policy_version=review.policy_version,
        review_risk_class=review.risk_class,
        review_disposition=review.disposition,
        counted_event_ids=review.counted_event_ids,
        challenger_readiness=challenger_readiness,
        challenger_waiver_policy_decision_ref=(waiver_ref or None),
    )
    return PublicationEligibilityResult(
        disposition=disposition,
        blockers=tuple(blockers),
        safety_binding_sha256=publication_safety.binding_sha256,
        high_risk_binding_sha256=high_risk_binding,
        review_policy_version=review.policy_version,
        review_risk_class=review.risk_class,
        counted_review_event_ids=review.counted_event_ids,
        binding_sha256=binding,
        challenger_packet_id=(
            challenger_readiness.packet_id if challenger_readiness is not None else None
        ),
        challenger_version=(
            challenger_readiness.version if challenger_readiness is not None else None
        ),
        challenger_waiver_policy_decision_ref=(waiver_ref or None),
    )


def evaluate_publication_eligibility(
    *,
    record_id: str,
    record_version: str,
    publication_safety: PublicationSafetyResult,
    high_risk: HighRiskDecision,
    high_risk_input_binding_sha256: str,
    review_store: PublicationReviewPersistenceStore,
    review_authority: ReviewerIdentityAuthority | None,
    upstream_actor_refs: Iterable[str] = (),
    upstream_credential_fingerprints: Iterable[str] = (),
    challenger_readiness: ChallengerReadinessDecision | None = None,
    challenger_waiver_policy_decision_ref: str | None = None,
) -> PublicationEligibilityResult:
    """Runtime eligibility from authority-attested durable review history only.

    The caller cannot supply a completion boolean, reviewer identity, or a self-consistent
    in-memory hash chain as review authority. The exact durable history is replayed through the
    independently controlled reviewer authority first. Any replay/authority blocker is carried
    into the fail-closed eligibility result.

    Challenger readiness/waiver values are currently pure policy/testing inputs only. There is
    no durable challenger packet/review authority equivalent to the reviewer authority in this
    runtime, so caller-supplied challenger values are rejected and never forwarded into the pure
    eligibility composer. A future runtime integration must resolve challenger state through a
    real durable/authority mechanism before this boundary may consume it.
    """

    runtime_blockers: list[str] = []
    if challenger_readiness is not None:
        runtime_blockers.append("CHALLENGER_READINESS_AUTHORITY_UNAVAILABLE")
    if str(challenger_waiver_policy_decision_ref or "").strip():
        runtime_blockers.append("CHALLENGER_WAIVER_AUTHORITY_UNAVAILABLE")

    replay = review_store.replay_attested_chain(
        record_id,
        authority=review_authority,
    )
    result = _evaluate_publication_eligibility_from_events(
        record_id=record_id,
        record_version=record_version,
        publication_safety=publication_safety,
        high_risk=high_risk,
        high_risk_input_binding_sha256=high_risk_input_binding_sha256,
        review_events=replay.events,
        upstream_actor_refs=upstream_actor_refs,
        upstream_credential_fingerprints=upstream_credential_fingerprints,
        challenger_readiness=None,
        challenger_waiver_policy_decision_ref=None,
    )
    if not replay.blockers and not runtime_blockers:
        return result
    blockers = tuple(
        dict.fromkeys((*replay.blockers, *runtime_blockers, *result.blockers))
    )
    return PublicationEligibilityResult(
        disposition="HOLD_FOR_PUBLICATION_REVIEW",
        blockers=blockers,
        safety_binding_sha256=result.safety_binding_sha256,
        high_risk_binding_sha256=result.high_risk_binding_sha256,
        review_policy_version=result.review_policy_version,
        review_risk_class=result.review_risk_class,
        counted_review_event_ids=(),
        binding_sha256=result.binding_sha256,
        challenger_packet_id=None,
        challenger_version=None,
        challenger_waiver_policy_decision_ref=None,
    )


__all__ = [
    "PUBLICATION_ELIGIBILITY_VERSION",
    "PublicationEligibilityResult",
    "evaluate_publication_eligibility",
]
