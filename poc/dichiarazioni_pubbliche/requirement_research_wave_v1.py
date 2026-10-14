"""DP-314 private, deterministic queue for manually reviewing research deltas.

Consumes two strictly validated and independently SHA-pinned *metadata* work
lists; never fetches evidence, sends a provider request, declares an approval,
decides a proposition or publishes anything. A shared evidence ID is NOT
independent corroboration or a public source; only a private operator warning.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass

from .requirement_research_batch_v1 import (
    PrivateResearchBatch,
    ResearchGapItem,
    _digest,
)
from .requirement_research_delta_v1 import compare_research_batches

VERSION = "private-requirement-research-wave-v1"
_PRIORITY = {
    "EVIDENCE_ELIGIBILITY_LOSS": 0,
    "REMOVED_CLAIM_NOT_RESOLVED": 1,
    "NEW_EVIDENCE_ELIGIBILITY": 2,
    "CHANGED_REQUIREMENT_PROFILE": 3,
    "CHANGED_INPUT_RECHECK": 4,
    "NEW_CLAIM_REVIEW": 5,
}


@dataclass(frozen=True)
class ResearchWaveStep:
    reason: str
    priority: int
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    current_review_actions: tuple[str, ...]
    change_direction: str
    provider_calls: int = 0
    source_approval_authority: bool = False
    finding_authority: bool = False
    publication_authority: bool = False


@dataclass(frozen=True)
class PrivateResearchWave:
    version: str
    status: str
    previous_batch_sha256: str
    current_batch_sha256: str
    recheck_claim_ids: tuple[str, ...]
    queue: tuple[ResearchWaveStep, ...]
    reused_evidence_ids: tuple[str, ...]
    claim_count: int
    snapshot_sha256: str
    independent_corroboration_established: bool = False
    source_approval_authority: bool = False
    finding_authority: bool = False
    publication_authority: bool = False
    private_only: bool = True
    source_body_count: int = 0
    provider_calls: int = 0
    verdict: None = None


def plan_research_wave(
    *,
    previous: PrivateResearchBatch,
    current: PrivateResearchBatch,
    expected_previous_sha256: str,
    expected_current_sha256: str,
) -> PrivateResearchWave:
    """Build bounded priority buckets, never a source-rights/action mandate.

    Expected digests must come from a separate owner-held state, not from
    self-rehashing these mutable inputs. Even unchanged output is *not* an
    endorsement of evidence or an instruction to publish.
    """
    # The upstream delta validator admits subclasses via isinstance. A
    # mutable subclass can switch `items` after that validator's SHA check
    # and inject arbitrary `next_steps` into our later output. Refuse
    # dynamic subclasses, detach the exact typed rows ONCE, and exclusively
    # read these snapshots both during validation and queue construction.
    for candidate in (previous, current):
        if (
            type(candidate) is not PrivateResearchBatch
            or type(candidate.items) is not tuple
            or any(type(item) is not ResearchGapItem for item in candidate.items)
        ):
            raise ValueError("WAVE_BATCH_INVALID")
    previous, current = deepcopy(previous), deepcopy(current)
    delta = compare_research_batches(
        previous, current, expected_previous_sha256, expected_current_sha256
    )
    after_by_id = {row.claim_id: row for row in current.items}
    steps: dict[str, dict[str, set[str]]] = {}

    def add(reason: str, claim_id: str, evidence: tuple[str, ...] = ()) -> None:
        target = steps.setdefault(
            reason, {"claims": set(), "evidence": set(), "actions": set()}
        )
        target["claims"].add(claim_id)
        target["evidence"].update(evidence)
        if claim_id in after_by_id:
            target["actions"].update(after_by_id[claim_id].next_steps)

    for change in delta.changed_claims:
        if change.lost_eligible_ids:
            add("EVIDENCE_ELIGIBILITY_LOSS", change.claim_id, change.lost_eligible_ids)
        if change.gained_eligible_ids:
            add("NEW_EVIDENCE_ELIGIBILITY", change.claim_id, change.gained_eligible_ids)
        if "REVIEW_CHANGED_REQUIREMENT_PROFILE" in change.actions:
            add("CHANGED_REQUIREMENT_PROFILE", change.claim_id)
        if (
            not change.lost_eligible_ids
            and not change.gained_eligible_ids
            and "REVIEW_CHANGED_REQUIREMENT_PROFILE" not in change.actions
        ):
            add("CHANGED_INPUT_RECHECK", change.claim_id)
    for claim_id in delta.removed_claim_ids:
        add("REMOVED_CLAIM_NOT_RESOLVED", claim_id)
    for claim_id in delta.added_claim_ids:
        add("NEW_CLAIM_REVIEW", claim_id)

    queue = tuple(
        ResearchWaveStep(
            reason=reason,
            priority=_PRIORITY[reason],
            claim_ids=tuple(sorted(data["claims"])),
            evidence_ids=tuple(sorted(data["evidence"])),
            current_review_actions=tuple(sorted(data["actions"])),
            change_direction=(
                "LOST_ELIGIBILITY_NOT_PROVEN_REVOKE"
                if reason == "EVIDENCE_ELIGIBILITY_LOSS"
                else "PENDING_HUMAN_RECHECK_NOT_SOURCE_APPROVAL"
            ),
        )
        for reason, data in sorted(steps.items(), key=lambda item: _PRIORITY[item[0]])
    )
    eligible_id_frequency = Counter(
        evidence_id
        for row in current.items
        for evidence_id in row.eligible_evidence_ids
    )
    shared = tuple(
        sorted(
            identifier
            for identifier, occurrences in eligible_id_frequency.items()
            if occurrences > 1
        )
    )
    material = {
        "version": VERSION,
        "before": previous.snapshot_sha256,
        "after": current.snapshot_sha256,
        "delta": delta.snapshot_sha256,
        "queue": [asdict(step) for step in queue],
        "shared_eligible_ids": shared,
        "recheck_claim_ids": delta.recheck_claim_ids,
        "claim_count": current.claim_count,
    }
    return PrivateResearchWave(
        version=VERSION,
        status="MANUAL_RECHECK_REQUIRED"
        if delta.recheck_claim_ids
        else "IDLE_NO_AUTO_APPROVAL",
        previous_batch_sha256=previous.snapshot_sha256,
        current_batch_sha256=current.snapshot_sha256,
        recheck_claim_ids=delta.recheck_claim_ids,
        queue=queue,
        reused_evidence_ids=shared,
        claim_count=current.claim_count,
        snapshot_sha256=_digest(material),
    )
