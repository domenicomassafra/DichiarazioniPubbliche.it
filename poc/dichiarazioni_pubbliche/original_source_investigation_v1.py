"""DP-241: private, bounded source-recovery investigation over existing contracts.

This pure module neither discovers a URL nor performs an attempt. Input receipts,
discovery queries, rights decisions and candidate sources must be authenticated by
their existing owners before calling it. In particular a caller-provided receipt
hash is a binding, not proof that a search was performed or a source was approved.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
)
from dichiarazioni_pubbliche.original_source_resolver import (
    DerivationEdge,
    ExactSourceLocator,
    ObservedMediaSegment,
    resolve_exact_source_locator,
    resolve_reviewed_original_source,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceUseDecision
from dichiarazioni_pubbliche.research_plan import (
    RESEARCH_PLAN_VERSION,
    ResearchAssignment,
)


VERSION = "original-source-investigation-v1"
MAX_METHODS = 8
MAX_ATTEMPTS = 8
MAX_RECEIPTS = 32
MAX_COST_USD = Decimal("10")
SHA = re.compile(r"^[0-9a-f]{64}$")
LANE_METHODS = {
    "PRIMARY_SOURCE": "ORIGINAL_PUBLISHER",
    "ORIGINAL_MEDIA": "ORIGINAL_PUBLISHER",
    "OFFICIAL_STRUCTURED": "OFFICIAL_RECORD",
    "ARCHIVE_HISTORY": "CONTEMPORARY_ARCHIVE",
    "INDEPENDENT_REPORTING": "INDEPENDENT_CONTEXT",
}
RESULTS = frozenset(
    {
        "NOT_FOUND",
        "CHECKED_INSUFFICIENT",
        "OUTAGE",
        "RIGHTS_BLOCKED",
        "COST_BLOCKED",
        "FOUND_CANDIDATE",
    }
)


def _required(value: object, field: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"DP241_{field}_INVALID")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"DP241_{field}_HASH_INVALID")
    return value


def _cost(value: object, field: str) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or not Decimal(0) <= value <= MAX_COST_USD
    ):
        raise ValueError(f"DP241_{field}_INVALID")
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _method_material(row: PlannedMethod) -> dict[str, str]:
    return {
        "assignment_id": row.assignment_id,
        "family": row.method_family,
        "source_family": row.source_family,
        "adapter_id": row.adapter_id,
        "query_ref": row.validated_query_ref,
        "query_sha256": row.query_validation_sha256,
        "discover_sha256": row.discover_permission_sha256,
        "fetch_sha256": row.fetch_permission_sha256,
        "estimated_cost": str(row.estimated_cost_usd),
    }


def _plan_id(
    *,
    need_id: str,
    question: str,
    content_id: str,
    locator_sha256: str,
    source_sha256: str,
    quote_sha256: str,
    person_id: str | None,
    event_date: str | None,
    max_attempts: int,
    cost_cap_usd: Decimal,
    method_material: list[dict[str, str]],
) -> str:
    return "original-source-plan:" + _fingerprint(
        {
            "version": VERSION,
            "need_id": need_id,
            "question": question,
            "content_id": content_id,
            "locator": locator_sha256,
            "source_sha256": source_sha256,
            "quote_sha256": quote_sha256,
            "person": person_id,
            "event_date": event_date,
            "cap": max_attempts,
            "budget": str(cost_cap_usd),
            "methods": method_material,
        }
    )


def _permitted(decision: SourceUseDecision, operation: str) -> bool:
    return (
        isinstance(decision, SourceUseDecision)
        and decision.use == operation
        and decision.permitted
        and bool(decision.record_id)
        and isinstance(decision.decision_fingerprint, str)
        and SHA.fullmatch(decision.decision_fingerprint) is not None
    )


@dataclass(frozen=True)
class SourceRecoveryTarget:
    need_id: str
    question: str
    expected_person_id: str | None
    event_date: str | None  # validated existing source metadata, never inferred
    locator: ExactSourceLocator
    passage: PassageRecord
    quote_text: str
    capture: ContentCaptureRecord | None = None
    source_body: bytes | None = None
    canonical_text: str | None = None
    page_text: str | None = None
    media_segment: ObservedMediaSegment | None = None


@dataclass(frozen=True)
class RecoveryMethod:
    assignment: ResearchAssignment
    source_family: str
    adapter_id: str
    validated_query_ref: str
    query_validation_sha256: str
    discover_permission: SourceUseDecision
    fetch_permission: SourceUseDecision
    estimate_usd: Decimal = Decimal("0")


@dataclass(frozen=True)
class PlannedMethod:
    attempt_id: str
    assignment_id: str
    method_family: str
    source_family: str
    adapter_id: str
    validated_query_ref: str
    query_validation_sha256: str
    discover_permission_sha256: str
    fetch_permission_sha256: str
    estimated_cost_usd: Decimal


@dataclass(frozen=True)
class RecoveryPlan:
    plan_id: str
    need_id: str
    question: str
    target_content_id: str
    target_locator_fingerprint: str
    target_version_sha256: str
    target_quote_sha256: str
    expected_person_id: str | None
    expected_event_date: str | None
    methods: tuple[PlannedMethod, ...]
    max_attempts: int
    cost_cap_usd: Decimal
    status: str
    reason_code: str
    version: str = VERSION
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class OriginalCandidateProof:
    """Untrusted observed data to verify; no authority to identify a speaker."""

    locator: ExactSourceLocator
    passage: PassageRecord
    quote_text: str
    capture: ContentCaptureRecord | None = None
    source_body: bytes | None = None
    canonical_text: str | None = None
    page_text: str | None = None
    media_segment: ObservedMediaSegment | None = None
    approved_families: tuple[dict[str, str], ...] = ()
    approved_edges: tuple[DerivationEdge, ...] = ()
    observed_person_id: str | None = None
    observed_event_date: str | None = None


@dataclass(frozen=True)
class RecoveryReceipt:
    attempt_id: str
    plan_id: str
    result: str
    discovery_receipt_sha256: str
    spent_usd: Decimal
    candidate: OriginalCandidateProof | None = None


@dataclass(frozen=True)
class RecoveryDecision:
    status: str
    reason_code: str
    plan_id: str
    proposed_attempt_id: str | None
    checked_methods: tuple[str, ...]
    prior_attempts: int
    remaining_attempts: int
    spent_usd: Decimal
    verified_root_content_ids: tuple[str, ...]
    private_source_candidates: int
    next_trigger: str
    reanalysis_required: bool = False
    publication_authority: bool = False


def make_recovery_plan(
    target: SourceRecoveryTarget,
    methods: tuple[RecoveryMethod, ...],
    *,
    max_attempts: int,
    cost_cap_usd: Decimal,
) -> RecoveryPlan:
    """Reconstruct source selector and compile existing *approved lookup references*.

    Distinct method families require distinct DP-228 lanes. Two adapters or
    syndication mirrors in the same method family cannot satisfy that minimum.
    """
    _required(target.need_id, "NEED_ID")
    _required(target.question, "QUESTION", 1024)
    if (
        len(target.question.strip()) < 12
        or target.question.strip().endswith("?") is False
    ):
        raise ValueError("DP241_TARGET_QUESTION_NOT_SPECIFIC")
    if target.expected_person_id is not None:
        _required(target.expected_person_id, "PERSON")
    if target.event_date is not None:
        _required(target.event_date, "EVENT_DATE", 64)
        try:
            if date.fromisoformat(target.event_date).isoformat() != target.event_date:
                raise ValueError("DP241_EVENT_DATE_INVALID")
        except ValueError as exc:
            raise ValueError("DP241_EVENT_DATE_INVALID") from exc
    if type(max_attempts) is not int or not 2 <= max_attempts <= MAX_ATTEMPTS:
        raise ValueError("DP241_ATTEMPT_CAP_INVALID")
    _cost(cost_cap_usd, "COST_CAP")
    if not isinstance(methods, tuple) or not 2 <= len(methods) <= MAX_METHODS:
        raise ValueError("DP241_METHOD_COUNT_INVALID")
    if target.capture is not None and target.capture.rights_status != "CLEARED":
        raise ValueError("DP241_TARGET_SOURCE_RIGHTS_UNCLEARED")
    exact = resolve_exact_source_locator(
        target.locator,
        passage=target.passage,
        quote_text=target.quote_text,
        capture=target.capture,
        source_body=target.source_body,
        canonical_text=target.canonical_text,
        page_text=target.page_text,
        media_segment=target.media_segment,
    )
    if (
        not exact.located
        or not exact.locator_fingerprint
        or not exact.source_version_sha256
    ):
        raise ValueError(
            "DP241_TARGET_LOCATOR_"
            + (exact.blockers[0] if exact.blockers else "INVALID")
        )
    accepted: list[dict[str, object]] = []
    distinct: set[str] = set()
    duplicate_keys: set[tuple[str, str, str]] = set()
    blocked_rights = False
    for row in methods:
        if not isinstance(row, RecoveryMethod):
            raise ValueError("DP241_METHOD_INVALID")
        assignment = row.assignment
        if (
            assignment.plan_version != RESEARCH_PLAN_VERSION
            or assignment.status != "READY"
            or assignment.coverage_need_id != target.need_id
            or assignment.question != target.question
            or assignment.lane not in LANE_METHODS
            or assignment.max_queries < 1
            or assignment.max_results < 1
            or row.adapter_id not in assignment.adapter_ids
        ):
            raise ValueError("DP241_RESEARCH_ASSIGNMENT_MISMATCH")
        method_family = LANE_METHODS[assignment.lane]
        _required(row.source_family, "SOURCE_FAMILY")
        _required(row.validated_query_ref, "VALIDATED_QUERY_REF")
        _sha(row.query_validation_sha256, "QUERY_VALIDATION")
        _cost(row.estimate_usd, "METHOD_ESTIMATE")
        if row.estimate_usd > assignment.cost_cap_usd:
            raise ValueError("DP241_ASSIGNMENT_COST_CAP_EXCEEDED")
        key = (method_family, row.source_family, row.validated_query_ref)
        if key in duplicate_keys:
            raise ValueError("DP241_DUPLICATE_METHOD_REFERENCE")
        duplicate_keys.add(key)
        # Scope source family is not granted by ResearchAssignment alone;
        # the future executor must re-read the exact reviewed rights subject.
        if not (
            _permitted(row.discover_permission, "DISCOVER_METADATA")
            and _permitted(row.fetch_permission, "FETCH")
            and row.discover_permission.record_id == row.fetch_permission.record_id
        ):
            blocked_rights = True
            continue
        accepted.append(
            {
                "assignment_id": assignment.assignment_id,
                "family": method_family,
                "source_family": row.source_family,
                "adapter_id": row.adapter_id,
                "query_ref": row.validated_query_ref,
                "query_sha256": row.query_validation_sha256,
                "discover_sha256": row.discover_permission.decision_fingerprint,
                "fetch_sha256": row.fetch_permission.decision_fingerprint,
                "estimated_cost": str(row.estimate_usd),
            }
        )
        distinct.add(method_family)
    accepted.sort(
        key=lambda item: (
            str(item["family"]),
            str(item["source_family"]),
            str(item["assignment_id"]),
            str(item["query_ref"]),
        )
    )
    plan_id = _plan_id(
        need_id=target.need_id,
        question=target.question,
        content_id=target.locator.content_id,
        locator_sha256=exact.locator_fingerprint,
        source_sha256=exact.source_version_sha256,
        quote_sha256=target.locator.quote_sha256,
        person_id=target.expected_person_id,
        event_date=target.event_date,
        max_attempts=max_attempts,
        cost_cap_usd=cost_cap_usd,
        method_material=accepted,
    )
    planned = tuple(
        PlannedMethod(
            attempt_id="original-source-attempt:"
            + _fingerprint({"plan": plan_id, "method": row}),
            assignment_id=str(row["assignment_id"]),
            method_family=str(row["family"]),
            source_family=str(row["source_family"]),
            adapter_id=str(row["adapter_id"]),
            validated_query_ref=str(row["query_ref"]),
            query_validation_sha256=str(row["query_sha256"]),
            discover_permission_sha256=str(row["discover_sha256"]),
            fetch_permission_sha256=str(row["fetch_sha256"]),
            estimated_cost_usd=Decimal(str(row["estimated_cost"])),
        )
        for row in accepted
    )
    if len(distinct) < 2:
        status, reason = (
            "WAIT_EXTERNAL",
            "RECOVERY_INSUFFICIENT_PERMITTED_DISTINCT_METHODS"
            if blocked_rights
            else "RECOVERY_TWO_DISTINCT_METHODS_REQUIRED",
        )
    elif sum((row.estimated_cost_usd for row in planned), Decimal(0)) > cost_cap_usd:
        status, reason = "WAIT_EXTERNAL", "RECOVERY_METHOD_COST_CAP_BLOCKED"
    else:
        status, reason = "READY_PRIVATE_PLAN", "RECOVERY_TWO_METHODS_PLANNED"
    return RecoveryPlan(
        plan_id,
        target.need_id,
        target.question,
        target.locator.content_id,
        exact.locator_fingerprint,
        exact.source_version_sha256,
        target.locator.quote_sha256,
        target.expected_person_id,
        target.event_date,
        planned,
        max_attempts,
        cost_cap_usd,
        status,
        reason,
    )


def _verify_found(
    plan: RecoveryPlan,
    target: SourceRecoveryTarget,
    candidate: OriginalCandidateProof,
) -> tuple[str | None, str | None]:
    """Return (approved root, hold code). Copies are collapsed by reviewed root."""
    if (
        not isinstance(candidate, OriginalCandidateProof)
        or len(candidate.approved_families) > 16
        or len(candidate.approved_edges) > 64
        or not isinstance(candidate.quote_text, str)
        or len(candidate.quote_text) > 16_384
        or (
            candidate.source_body is not None and len(candidate.source_body) > 4_194_304
        )
    ):
        return None, "RECOVERY_CANDIDATE_INPUT_UNBOUNDED"
    approved_families = {
        row.get("family_id")
        for row in candidate.approved_families
        if isinstance(row, dict)
        and row.get("status") == "APPROVED"
        and isinstance(row.get("family_id"), str)
        and row.get("family_id")
    }
    if not approved_families or any(
        not isinstance(edge, DerivationEdge)
        or (edge.status == "APPROVED" and edge.family_id not in approved_families)
        for edge in candidate.approved_edges
    ):
        return None, "RECOVERY_UNAPPROVED_LINEAGE_FAMILY"
    if candidate.capture is not None and candidate.capture.rights_status != "CLEARED":
        return None, "RECOVERY_CANDIDATE_RIGHTS_UNCLEARED"
    exact = resolve_exact_source_locator(
        candidate.locator,
        passage=candidate.passage,
        quote_text=candidate.quote_text,
        capture=candidate.capture,
        source_body=candidate.source_body,
        canonical_text=candidate.canonical_text,
        page_text=candidate.page_text,
        media_segment=candidate.media_segment,
    )
    if (
        not exact.located
        or not exact.source_version_sha256
        or not exact.locator_fingerprint
    ):
        return None, "RECOVERY_CANDIDATE_LOCATOR_INVALID"
    # Root is established by an approved family/chain, not candidate metadata
    # or similarity. A copy's own Capture can be intact without being original.
    resolution = resolve_reviewed_original_source(
        plan.target_content_id,
        families=candidate.approved_families,
        edges=candidate.approved_edges,
    )
    if (
        not resolution.resolved
        or resolution.root_content_id != candidate.locator.content_id
    ):
        return None, "RECOVERY_UNPROVEN_ROOT_LINEAGE"
    candidate_root = resolve_reviewed_original_source(
        candidate.locator.content_id,
        families=candidate.approved_families,
        edges=candidate.approved_edges,
    )
    if (
        not candidate_root.resolved
        or candidate_root.root_content_id != candidate.locator.content_id
    ):
        return None, "RECOVERY_DERIVED_MIRROR_NOT_ROOT"
    if (
        plan.expected_person_id is None
        or candidate.observed_person_id != plan.expected_person_id
    ):
        return None, "RECOVERY_PERSON_MISMATCH_OR_UNVERIFIED"
    if (
        plan.expected_event_date is None
        or candidate.observed_event_date != plan.expected_event_date
    ):
        return None, "RECOVERY_EVENT_DATE_MISMATCH_OR_UNVERIFIED"
    # A shorter edited quote must appear contiguously within the selected
    # longer text; a montage cannot be silently stitched into a source quote.
    if target.quote_text not in candidate.quote_text or len(
        candidate.quote_text
    ) <= len(target.quote_text):
        return None, "RECOVERY_FULL_CONTEXT_UNPROVEN"
    if (
        exact.source_version_sha256 == plan.target_version_sha256
        and candidate.locator.content_id == plan.target_content_id
    ):
        return None, "RECOVERY_NOT_A_NEW_OR_LONGER_ORIGINAL"
    return candidate.locator.content_id, None


def assess_recovery(
    plan: RecoveryPlan,
    target: SourceRecoveryTarget,
    receipts: tuple[RecoveryReceipt, ...],
    *,
    current_target_version_sha256: str | None = None,
    rights_current: bool = True,
    budget_ready: bool = True,
) -> RecoveryDecision:
    """Read-only reconciliation. `NOT_FOUND` concerns attempted narrow scope only."""
    if not isinstance(receipts, tuple) or len(receipts) > MAX_RECEIPTS:
        raise ValueError("DP241_RECEIPT_INPUT_UNBOUNDED")
    if current_target_version_sha256 is not None:
        _sha(current_target_version_sha256, "CURRENT_TARGET_VERSION")
    if (
        plan.version != VERSION
        or target.need_id != plan.need_id
        or target.question != plan.question
    ):
        raise ValueError("DP241_PLAN_TARGET_MISMATCH")
    if (
        len(plan.methods) > MAX_METHODS
        or type(plan.max_attempts) is not int
        or not 2 <= plan.max_attempts <= MAX_ATTEMPTS
        or plan.status not in {"READY_PRIVATE_PLAN", "WAIT_EXTERNAL"}
        or plan.dispatch_authorized is not False
        or len({row.attempt_id for row in plan.methods}) != len(plan.methods)
    ):
        raise ValueError("DP241_PLAN_BOUNDS_INVALID")
    _cost(plan.cost_cap_usd, "PLAN_COST_CAP")
    for method in plan.methods:
        if method.method_family not in LANE_METHODS.values():
            raise ValueError("DP241_PLAN_METHOD_INVALID")
        _cost(method.estimated_cost_usd, "PLAN_METHOD_COST")
        for field in (
            method.query_validation_sha256,
            method.discover_permission_sha256,
            method.fetch_permission_sha256,
        ):
            _sha(field, "METHOD_PERMISSION_OR_QUERY")
    method_material = [_method_material(row) for row in plan.methods]
    canonical_methods = sorted(
        method_material,
        key=lambda row: (
            row["family"],
            row["source_family"],
            row["assignment_id"],
            row["query_ref"],
        ),
    )
    if method_material != canonical_methods:
        raise ValueError("DP241_PLAN_METHOD_ORDER_CHANGED")
    fingerprint = _plan_id(
        need_id=plan.need_id,
        question=plan.question,
        content_id=plan.target_content_id,
        locator_sha256=plan.target_locator_fingerprint,
        source_sha256=plan.target_version_sha256,
        quote_sha256=plan.target_quote_sha256,
        person_id=plan.expected_person_id,
        event_date=plan.expected_event_date,
        max_attempts=plan.max_attempts,
        cost_cap_usd=plan.cost_cap_usd,
        method_material=method_material,
    )
    if plan.plan_id != fingerprint or any(
        row.attempt_id
        != "original-source-attempt:"
        + _fingerprint({"plan": fingerprint, "method": material})
        for row, material in zip(plan.methods, method_material)
    ):
        raise ValueError("DP241_PLAN_FINGERPRINT_MISMATCH")
    if plan.status == "READY_PRIVATE_PLAN" and (
        len({row.method_family for row in plan.methods}) < 2
        or sum((row.estimated_cost_usd for row in plan.methods), Decimal(0))
        > plan.cost_cap_usd
    ):
        raise ValueError("DP241_PLAN_PERMISSION_OR_COST_MISMATCH")
    current = resolve_exact_source_locator(
        target.locator,
        passage=target.passage,
        quote_text=target.quote_text,
        capture=target.capture,
        source_body=target.source_body,
        canonical_text=target.canonical_text,
        page_text=target.page_text,
        media_segment=target.media_segment,
    )
    if (
        not current.located
        or current.locator_fingerprint != plan.target_locator_fingerprint
        or current.source_version_sha256 != plan.target_version_sha256
        or plan.target_quote_sha256 != target.locator.quote_sha256
        or target.expected_person_id != plan.expected_person_id
        or target.event_date != plan.expected_event_date
    ):
        raise ValueError("DP241_PLAN_TARGET_SOURCE_CHANGED")
    attempts = {method.attempt_id: method for method in plan.methods}
    seen: dict[str, RecoveryReceipt] = {}
    discovery_owners: dict[str, str] = {}
    for row in receipts:
        if (
            not isinstance(row, RecoveryReceipt)
            or row.attempt_id not in attempts
            or row.plan_id != plan.plan_id
        ):
            raise ValueError("DP241_FOREIGN_RECEIPT")
        if row.result not in RESULTS:
            raise ValueError("DP241_RECEIPT_RESULT_INVALID")
        _sha(row.discovery_receipt_sha256, "DISCOVERY_RECEIPT")
        _cost(row.spent_usd, "SPENT")
        if row.result == "FOUND_CANDIDATE" and not isinstance(
            row.candidate, OriginalCandidateProof
        ):
            raise ValueError("DP241_FOUND_PROOF_REQUIRED")
        if row.result != "FOUND_CANDIDATE" and row.candidate is not None:
            raise ValueError("DP241_NONFOUND_PROOF_FORBIDDEN")
        old = seen.get(row.attempt_id)
        if old is not None and old != row:
            raise ValueError("DP241_RECEIPT_REPLAY_CONFLICT")
        prior_attempt = discovery_owners.get(row.discovery_receipt_sha256)
        if prior_attempt is not None and prior_attempt != row.attempt_id:
            raise ValueError("DP241_DISCOVERY_RECEIPT_REUSED")
        discovery_owners[row.discovery_receipt_sha256] = row.attempt_id
        seen[row.attempt_id] = row
    if len(seen) > plan.max_attempts:
        raise ValueError("DP241_RECEIPT_ATTEMPT_CAP_EXCEEDED")
    rows = tuple(seen[key] for key in sorted(seen))
    spent = sum((row.spent_usd for row in rows), Decimal(0))
    checked_families = tuple(
        sorted(
            {
                attempts[row.attempt_id].method_family
                for row in rows
                if row.result
                in {"NOT_FOUND", "CHECKED_INSUFFICIENT", "FOUND_CANDIDATE"}
            }
        )
    )
    roots: set[str] = set()
    conflict_codes: list[str] = []
    for row in rows:
        if row.result != "FOUND_CANDIDATE":
            continue
        root, hold = _verify_found(plan, target, row.candidate)
        if root is not None:
            roots.add(root)
        if hold is not None:
            conflict_codes.append(hold)

    def decision(
        status: str, reason: str, trigger: str, proposed: str | None = None
    ) -> RecoveryDecision:
        return RecoveryDecision(
            status=status,
            reason_code=reason,
            plan_id=plan.plan_id,
            proposed_attempt_id=proposed,
            checked_methods=checked_families,
            prior_attempts=len(rows),
            remaining_attempts=max(0, plan.max_attempts - len(rows)),
            spent_usd=spent,
            verified_root_content_ids=tuple(sorted(roots)),
            private_source_candidates=len(roots),
            next_trigger=trigger,
            reanalysis_required=bool(roots)
            or (
                current_target_version_sha256 is not None
                and current_target_version_sha256 != plan.target_version_sha256
            ),
        )

    if (
        current_target_version_sha256 is not None
        and current_target_version_sha256 != plan.target_version_sha256
    ):
        return decision(
            "STALE", "RECOVERY_TARGET_VERSION_CHANGED", "DP511_SOURCE_REVALIDATION"
        )
    if not rights_current or plan.status != "READY_PRIVATE_PLAN":
        return decision(
            "WAIT_EXTERNAL",
            "RECOVERY_RIGHTS_REVALIDATION_REQUIRED"
            if not rights_current
            else plan.reason_code,
            "REVIEW_SOURCE_PERMISSIONS_OR_METHODS",
        )
    if not budget_ready or spent > plan.cost_cap_usd:
        return decision(
            "WAIT_EXTERNAL",
            "RECOVERY_COST_CAP_OR_RECEIPTS_UNAVAILABLE",
            "REFRESH_COST_LEDGER",
        )
    if conflict_codes:
        return decision(
            "CONFLICT",
            sorted(set(conflict_codes))[0],
            "REVIEW_ROOT_IDENTITY_DATE_AND_CONTEXT",
        )
    if roots:
        return decision(
            "VERIFIED_PRIVATE_SOURCE_CANDIDATE",
            "RECOVERY_ROOT_AND_SELECTOR_BOUND",
            "DP511_REVALIDATE_AND_B_REVIEW",
        )
    if any(row.result == "RIGHTS_BLOCKED" for row in rows):
        return decision(
            "WAIT_EXTERNAL",
            "RECOVERY_FETCH_RIGHTS_BLOCKED",
            "REVIEW_SOURCE_PERMISSIONS",
        )
    if any(row.result == "COST_BLOCKED" for row in rows):
        return decision(
            "WAIT_EXTERNAL", "RECOVERY_ATTEMPT_COST_BLOCKED", "REFRESH_COST_LEDGER"
        )
    if any(row.result == "OUTAGE" for row in rows):
        return decision(
            "WAIT_EXTERNAL", "RECOVERY_PROVIDER_OUTAGE", "RETRY_ON_PROVIDER_RECOVERY"
        )
    untried = tuple(method for method in plan.methods if method.attempt_id not in seen)
    if not untried:
        if len(checked_families) >= 2:
            return decision(
                "CHECKED_INSUFFICIENT",
                "RECOVERY_AUTHORIZED_SCOPES_CHECKED_NO_ORIGINAL",
                "NEW_SOURCE_VERSION_OR_NEW_AUTHORIZED_METHOD",
            )
        return decision(
            "WAIT_EXTERNAL",
            "RECOVERY_INSUFFICIENT_INDEPENDENT_CHECKS",
            "ADD_DISTINCT_AUTHORIZED_METHOD",
        )
    if len(rows) >= plan.max_attempts:
        return decision(
            "EXHAUSTED", "RECOVERY_ATTEMPT_LIMIT", "NEW_SOURCE_VERSION_OR_NEW_AUTHORITY"
        )
    available = [
        row for row in untried if row.estimated_cost_usd <= plan.cost_cap_usd - spent
    ]
    if not available:
        return decision(
            "WAIT_EXTERNAL", "RECOVERY_NEXT_METHOD_COST_BLOCKED", "REFRESH_COST_LEDGER"
        )
    return decision(
        "READY_PRIVATE_PROPOSAL",
        "RECOVERY_NEXT_APPROVED_METHOD_READY",
        "RUN_AUTHORIZED_EXTERNAL_ADAPTER",
        available[0].attempt_id,
    )


__all__ = [
    "VERSION",
    "LANE_METHODS",
    "SourceRecoveryTarget",
    "RecoveryMethod",
    "PlannedMethod",
    "RecoveryPlan",
    "OriginalCandidateProof",
    "RecoveryReceipt",
    "RecoveryDecision",
    "make_recovery_plan",
    "assess_recovery",
]
