"""DP-240 bounded, private, multi-source/multi-speaker candidate batch preflight.

Builds *isolated* source items from an existing private CandidateBatch. A speaker
candidate is never a proved identity, and model output is never public. No
provider calls, rights grants, reviews, or automatic child job creation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields
from typing import Mapping

from dichiarazioni_pubbliche.private_candidate_batch import (
    CandidateBatch,
    MAX_ITEMS,
    _validate_batch,
)


VERSION = "multi-person-candidate-isolation-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BCP47 = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}\Z")
_ROLES = {"DIRECT_SPEAKER", "AUTHOR", "REPORTER", "QUOTED_SPEAKER", "UNRESOLVED"}
_KIND = {
    "DIRECT_ASSERTION",
    "OPINION",
    "REPORTED_QUOTE",
    "CRITICISM",
    "IRONY",
    "UNKNOWN",
}
_MAX_TOKENS_PER_ITEM = 16_384


def _required(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or "\x00" in value
    ):
        raise ValueError(f"MULTIPERSON_{field}_INVALID")
    return value


def _stable_hash(material: object) -> str:
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _plan_digest(
    collection_id: str,
    manifest_sha256: str,
    rows: tuple[IsolatedBatchItem, ...] | list[IsolatedBatchItem],
) -> str:
    """Bind replay identity to the exact ordered upstream manifest."""
    return _stable_hash(
        {
            "version": VERSION,
            "collection": collection_id,
            "manifest_sha256": manifest_sha256,
            "items": [vars(row) for row in rows],
        }
    )


@dataclass(frozen=True)
class ReviewedPassageContext:
    passage_id: str
    capture_id: str
    source_sha256: str
    passage_sha256: str
    selector_fingerprint: str
    content_id: str
    source_family: str
    language_tag: str
    speaker_candidate_id: str | None
    identity_review_status: str
    speech_role: str
    speech_act: str
    context_version: str
    context_review_id: str | None
    rights_status: str
    estimated_tokens: int

    def __post_init__(self) -> None:
        for field in (
            "passage_id",
            "capture_id",
            "selector_fingerprint",
            "content_id",
            "source_family",
            "context_version",
        ):
            _required(getattr(self, field), field.upper())
        for field in ("source_sha256", "passage_sha256"):
            if not isinstance(getattr(self, field), str) or not _SHA.fullmatch(
                getattr(self, field)
            ):
                raise ValueError(f"MULTIPERSON_{field.upper()}_INVALID")
        if not isinstance(self.language_tag, str) or not _BCP47.fullmatch(
            self.language_tag
        ):
            raise ValueError("MULTIPERSON_LANGUAGE_INVALID")
        if self.speaker_candidate_id is not None:
            _required(self.speaker_candidate_id, "SPEAKER_CANDIDATE")
        if self.context_review_id is not None:
            _required(self.context_review_id, "CONTEXT_REVIEW")
        if (
            self.identity_review_status
            not in {"UNRESOLVED", "CANDIDATE_MATCH", "REVIEWED_SAME_PERSON"}
            or self.speech_role not in _ROLES
            or self.speech_act not in _KIND
            or self.rights_status
            not in {"CLEARED", "UNKNOWN", "EXPIRED", "REVOKED", "DENIED"}
        ):
            raise ValueError("MULTIPERSON_CONTEXT_CLASS_INVALID")
        if (
            type(self.estimated_tokens) is not int
            or not 1 <= self.estimated_tokens <= _MAX_TOKENS_PER_ITEM
        ):
            raise ValueError("MULTIPERSON_TOKENS_INVALID")


@dataclass(frozen=True)
class IsolatedBatchItem:
    passage_id: str
    capture_id: str
    content_id: str
    source_family: str
    source_sha256: str
    passage_sha256: str
    selector_fingerprint: str
    speaker_candidate_id: str | None
    language_tag: str
    context_version: str
    partition_id: str
    status: str
    reason_code: str
    estimated_tokens: int
    public_attribution_authority: bool = False
    identity_review_status: str = "UNRESOLVED"
    speech_role: str = "UNRESOLVED"
    speech_act: str = "UNKNOWN"
    context_review_id: str | None = None
    rights_status: str = "UNKNOWN"


@dataclass(frozen=True)
class IsolatedBatchPlan:
    version: str
    collection_id: str
    manifest_sha256: str
    plan_sha256: str
    items: tuple[IsolatedBatchItem, ...]
    total_estimated_tokens: int
    proposed_group_count: int
    provider_calls: int = 0
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class PrivateBatchResult:
    passage_id: str
    content_id: str
    capture_id: str
    passage_sha256: str
    result: str  # FAILED, HELD, CANDIDATE_EXTRACTED
    failure_reason: str | None
    extraction_version: str | None


@dataclass(frozen=True)
class PrivateBatchReadback:
    plan_sha256: str
    statuses: tuple[tuple[str, str], ...]
    private_candidate_count: int
    failed_count: int
    held_count: int
    publication_authority: bool = False


@dataclass(frozen=True)
class PrivateBatchItemReceipt:
    """Private, source-exact per-Passage receipt; no Person identity approval."""

    passage_id: str
    content_id: str
    capture_id: str
    source_family: str
    source_sha256: str
    passage_sha256: str
    selector_fingerprint: str
    partition_id: str
    speaker_candidate_id: str | None
    language_tag: str
    context_version: str
    identity_review_status: str
    speech_role: str
    speech_act: str
    context_review_id: str | None
    rights_status: str
    status: str  # HELD, UNOBSERVED, FAILED, PRIVATE_CANDIDATE_UNVERIFIED
    reason_code: str
    observation_result: str | None
    failure_reason: str | None
    extraction_version: str | None
    public_attribution_authority: bool = False


@dataclass(frozen=True)
class PrivateBatchReceiptIndex:
    """Persistable deterministic receipt snapshot; SHA is NOT a signature."""

    plan_sha256: str
    items: tuple[PrivateBatchItemReceipt, ...]
    receipt_sha256: str
    observed_count: int
    pending_count: int
    failed_count: int
    held_count: int
    private_candidate_count: int
    version: str = VERSION
    publication_authority: bool = False
    dispatch_authorized: bool = False


def plan_isolated_candidate_batch(
    batch: CandidateBatch,
    contexts: Mapping[str, ReviewedPassageContext],
    *,
    total_token_cap: int,
    provider_capability_ready: bool,
) -> IsolatedBatchPlan:
    """Every item is evaluated separately; no source/speaker text is combined."""
    _validate_batch(batch)
    if type(provider_capability_ready) is not bool:
        raise ValueError("MULTIPERSON_PROVIDER_CAPABILITY_INVALID")
    if not isinstance(contexts, Mapping) or set(contexts) != {
        item.passage_id for item in batch.items
    }:
        raise ValueError("MULTIPERSON_CONTEXT_CARDINALITY_INVALID")
    if type(total_token_cap) is not int or not 1 <= total_token_cap <= 262_144:
        raise ValueError("MULTIPERSON_BATCH_BUDGET_INVALID")
    rows: list[IsolatedBatchItem] = []
    used = 0
    for item in sorted(batch.items, key=lambda row: row.passage_id):
        context = contexts[item.passage_id]
        if not isinstance(context, ReviewedPassageContext):
            raise ValueError("MULTIPERSON_CONTEXT_TYPE_INVALID")
        if (
            context.passage_id,
            context.capture_id,
            context.content_id,
            context.source_family,
            context.passage_sha256,
        ) != (
            item.passage_id,
            item.capture_id,
            item.content_id,
            item.source_family,
            item.passage_sha256,
        ):
            raise ValueError("MULTIPERSON_CROSS_SOURCE_REFERENCE")
        # Distinct Content, Capture, source, contextual span and speaker never
        # share one extraction partition. Mixed-source batches are manifests,
        # not a single trusted prompt or stitched quotation.
        partition_id = "batch-partition:" + _stable_hash(
            (
                context.passage_id,
                context.passage_sha256,
                context.content_id,
                context.capture_id,
                context.source_sha256,
                context.selector_fingerprint,
                context.context_version,
                context.language_tag,
                context.speaker_candidate_id,
                context.speech_role,
                context.speech_act,
            )
        )
        status, reason = "HELD", "MULTIPERSON_UNATTRIBUTED_CONTEXT"
        if context.rights_status != "CLEARED":
            reason = "MULTIPERSON_SOURCE_RIGHTS_HELD"
        elif not context.context_review_id:
            reason = "MULTIPERSON_CONTEXT_UNREVIEWED"
        elif (
            context.speaker_candidate_id is None
            or context.identity_review_status == "UNRESOLVED"
            or context.speech_role == "UNRESOLVED"
            or context.speech_act == "UNKNOWN"
        ):
            reason = "MULTIPERSON_SPEAKER_AMBIGUOUS"
        elif context.speech_role in {
            "REPORTER",
            "QUOTED_SPEAKER",
        } or context.speech_act in {"REPORTED_QUOTE", "CRITICISM", "IRONY"}:
            reason = "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT"
        elif not provider_capability_ready:
            reason = "MULTIPERSON_PROVIDER_CAPABILITY_UNAVAILABLE"
        elif used + context.estimated_tokens > total_token_cap:
            reason = "MULTIPERSON_BATCH_TOKEN_CAP"
        else:
            status, reason = (
                "PRIVATE_EXTRACTION_PROPOSED",
                "MULTIPERSON_ISOLATED_SOURCE_READY",
            )
            used += context.estimated_tokens
        rows.append(
            IsolatedBatchItem(
                item.passage_id,
                item.capture_id,
                item.content_id,
                item.source_family,
                context.source_sha256,
                item.passage_sha256,
                context.selector_fingerprint,
                context.speaker_candidate_id,
                context.language_tag,
                context.context_version,
                partition_id,
                status,
                reason,
                context.estimated_tokens,
                identity_review_status=context.identity_review_status,
                speech_role=context.speech_role,
                speech_act=context.speech_act,
                context_review_id=context.context_review_id,
                rights_status=context.rights_status,
            )
        )
    return IsolatedBatchPlan(
        VERSION,
        batch.collection_id,
        batch.sha256,
        _plan_digest(batch.collection_id, batch.sha256, rows),
        tuple(rows),
        used,
        len({row.partition_id for row in rows}),
    )


def _validate_isolated_plan(plan: IsolatedBatchPlan) -> None:
    """Detect corrupted/replayed plans; a digest is NOT a trusted signature.

    This is a local consistency check, not authorization to dispatch a provider,
    attribute a speaker, or to publish a model extraction.
    """
    if not isinstance(plan, IsolatedBatchPlan) or plan.version != VERSION:
        raise ValueError("MULTIPERSON_PLAN_SCHEMA_INVALID")
    _required(plan.collection_id, "COLLECTION")
    if (
        not isinstance(plan.manifest_sha256, str)
        or not _SHA.fullmatch(plan.manifest_sha256)
        or not isinstance(plan.plan_sha256, str)
        or not _SHA.fullmatch(plan.plan_sha256)
        or not isinstance(plan.items, tuple)
        or not 1 <= len(plan.items) <= MAX_ITEMS
    ):
        raise ValueError("MULTIPERSON_PLAN_SCHEMA_INVALID")
    if (
        plan.provider_calls != 0
        or type(plan.provider_calls) is not int
        or plan.dispatch_authorized is not False
    ):
        raise ValueError("MULTIPERSON_PLAN_AUTHORITY_INVALID")
    passages: set[str] = set()
    partitions: set[str] = set()
    used = 0
    for item in plan.items:
        if not isinstance(item, IsolatedBatchItem):
            raise ValueError("MULTIPERSON_PLAN_ITEM_INVALID")
        for key in (
            "passage_id",
            "capture_id",
            "content_id",
            "source_family",
            "selector_fingerprint",
            "language_tag",
            "context_version",
            "partition_id",
            "reason_code",
        ):
            _required(getattr(item, key), key.upper())
        if (
            not isinstance(item.source_sha256, str)
            or not _SHA.fullmatch(item.source_sha256)
            or not isinstance(item.passage_sha256, str)
            or not _SHA.fullmatch(item.passage_sha256)
            or item.speaker_candidate_id is not None
            and not isinstance(item.speaker_candidate_id, str)
            or type(item.estimated_tokens) is not int
            or not 1 <= item.estimated_tokens <= _MAX_TOKENS_PER_ITEM
            or item.public_attribution_authority is not False
            or item.status not in {"HELD", "PRIVATE_EXTRACTION_PROPOSED"}
            or item.identity_review_status not in {
                "UNRESOLVED", "CANDIDATE_MATCH", "REVIEWED_SAME_PERSON"
            }
            or item.speech_role not in _ROLES
            or item.speech_act not in _KIND
            or item.rights_status not in {
                "CLEARED", "UNKNOWN", "EXPIRED", "REVOKED", "DENIED"
            }
        ):
            raise ValueError("MULTIPERSON_PLAN_ITEM_INVALID")
        if item.context_review_id is not None:
            _required(item.context_review_id, "CONTEXT_REVIEW")
        if item.speaker_candidate_id is not None:
            if (
                not item.speaker_candidate_id.strip()
                or len(item.speaker_candidate_id) > 256
                or "\x00" in item.speaker_candidate_id
            ):
                raise ValueError("MULTIPERSON_PLAN_ITEM_INVALID")
        if item.passage_id in passages or item.partition_id in partitions:
            raise ValueError("MULTIPERSON_PLAN_ITEM_DUPLICATE")
        passages.add(item.passage_id)
        partitions.add(item.partition_id)
        if item.status == "PRIVATE_EXTRACTION_PROPOSED":
            if (
                item.reason_code != "MULTIPERSON_ISOLATED_SOURCE_READY"
                or item.speaker_candidate_id is None
                or item.rights_status != "CLEARED"
                or item.context_review_id is None
                or item.identity_review_status == "UNRESOLVED"
                or item.speech_role in {"UNRESOLVED", "REPORTER", "QUOTED_SPEAKER"}
                or item.speech_act in {
                    "UNKNOWN", "REPORTED_QUOTE", "CRITICISM", "IRONY"
                }
            ):
                raise ValueError("MULTIPERSON_PLAN_STATUS_INVALID")
            used += item.estimated_tokens
        elif item.reason_code not in {
            "MULTIPERSON_UNATTRIBUTED_CONTEXT",
            "MULTIPERSON_SOURCE_RIGHTS_HELD",
            "MULTIPERSON_CONTEXT_UNREVIEWED",
            "MULTIPERSON_SPEAKER_AMBIGUOUS",
            "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT",
            "MULTIPERSON_PROVIDER_CAPABILITY_UNAVAILABLE",
            "MULTIPERSON_BATCH_TOKEN_CAP",
        }:
            raise ValueError("MULTIPERSON_PLAN_STATUS_INVALID")
        if item.status == "HELD":
            # The reason must agree with the persisted source/identity context,
            # even when an untrusted caller recalculates the plan checksum.
            if item.rights_status != "CLEARED":
                expected_hold = "MULTIPERSON_SOURCE_RIGHTS_HELD"
            elif item.context_review_id is None:
                expected_hold = "MULTIPERSON_CONTEXT_UNREVIEWED"
            elif (
                item.speaker_candidate_id is None
                or item.identity_review_status == "UNRESOLVED"
                or item.speech_role == "UNRESOLVED"
                or item.speech_act == "UNKNOWN"
            ):
                expected_hold = "MULTIPERSON_SPEAKER_AMBIGUOUS"
            elif item.speech_role in {"REPORTER", "QUOTED_SPEAKER"} or item.speech_act in {
                "REPORTED_QUOTE", "CRITICISM", "IRONY"
            }:
                expected_hold = "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT"
            else:
                expected_hold = None  # Provider and token-cap holds are external.
            if expected_hold is not None and item.reason_code != expected_hold:
                raise ValueError("MULTIPERSON_PLAN_STATUS_INVALID")
    if tuple(row.passage_id for row in plan.items) != tuple(
        sorted(row.passage_id for row in plan.items)
    ):
        raise ValueError("MULTIPERSON_PLAN_ORDER_INVALID")
    if (
        type(plan.total_estimated_tokens) is not int
        or plan.total_estimated_tokens != used
        or type(plan.proposed_group_count) is not int
        or plan.proposed_group_count != len(partitions)
    ):
        raise ValueError("MULTIPERSON_PLAN_COUNTS_INVALID")
    if plan.plan_sha256 != _plan_digest(plan.collection_id, plan.manifest_sha256, plan.items):
        raise ValueError("MULTIPERSON_PLAN_TAMPERED")


def reconcile_isolated_private_results(
    plan: IsolatedBatchPlan,
    observations: tuple[PrivateBatchResult, ...],
) -> PrivateBatchReadback:
    """Unreported/failed items remain HELD; no provider completion inferred."""
    if not isinstance(observations, tuple) or len(observations) > MAX_ITEMS * 4:
        raise ValueError("MULTIPERSON_RESULT_INPUT_INVALID")
    _validate_isolated_plan(plan)
    by_passage = {row.passage_id: row for row in plan.items}
    seen: dict[str, PrivateBatchResult] = {}
    for row in observations:
        if not isinstance(row, PrivateBatchResult):
            raise ValueError("MULTIPERSON_RESULT_SCHEMA_INVALID")
        item = by_passage.get(row.passage_id)
        if item is None or (row.content_id, row.capture_id, row.passage_sha256) != (
            item.content_id,
            item.capture_id,
            item.passage_sha256,
        ):
            raise ValueError("MULTIPERSON_RESULT_SOURCE_MISMATCH")
        if row.result not in {"FAILED", "HELD", "CANDIDATE_EXTRACTED"}:
            raise ValueError("MULTIPERSON_RESULT_STATUS_INVALID")
        if row.result == "CANDIDATE_EXTRACTED":
            if (
                item.status != "PRIVATE_EXTRACTION_PROPOSED"
                or not row.extraction_version
                or row.failure_reason is not None
            ):
                raise ValueError("MULTIPERSON_RESULT_UNAUTHORIZED_SUCCESS")
            _required(row.extraction_version, "EXTRACTION_VERSION")
        elif row.result == "FAILED":
            if item.status != "PRIVATE_EXTRACTION_PROPOSED":
                raise ValueError("MULTIPERSON_RESULT_UNAUTHORIZED_RESULT")
            if not row.failure_reason:
                raise ValueError("MULTIPERSON_RESULT_FAILURE_REASON_MISSING")
            _required(row.failure_reason, "FAILURE_REASON")
            if row.extraction_version is not None:
                raise ValueError("MULTIPERSON_RESULT_STATUS_INVALID")
        elif row.failure_reason is not None or row.extraction_version is not None:
            raise ValueError("MULTIPERSON_RESULT_STATUS_INVALID")
        prior = seen.get(row.passage_id)
        if prior is not None and prior != row:
            raise ValueError("MULTIPERSON_RESULT_REPLAY_CONFLICT")
        seen[row.passage_id] = row
    statuses: list[tuple[str, str]] = []
    for item in plan.items:
        row = seen.get(item.passage_id)
        # The absence of a provider result is not a completed analysis.
        state = (
            "PRIVATE_CANDIDATE_UNVERIFIED"
            if row and row.result == "CANDIDATE_EXTRACTED"
            else ("FAILED" if row and row.result == "FAILED" else "HELD")
        )
        statuses.append((item.passage_id, state))
    return PrivateBatchReadback(
        plan.plan_sha256,
        tuple(statuses),
        sum(state == "PRIVATE_CANDIDATE_UNVERIFIED" for _, state in statuses),
        sum(state == "FAILED" for _, state in statuses),
        sum(state == "HELD" for _, state in statuses),
    )


def _build_receipt_snapshot(
    plan: IsolatedBatchPlan,
    observations: tuple[PrivateBatchResult, ...],
) -> PrivateBatchReceiptIndex:
    # Reuse the established source/authorization/replay gate before making any
    # independently indexable record. No provider result is inferred.
    reconcile_isolated_private_results(plan, observations)
    observed = {row.passage_id: row for row in observations}
    items: list[PrivateBatchItemReceipt] = []
    for source in plan.items:
        row = observed.get(source.passage_id)
        if row is None:
            status = "HELD" if source.status == "HELD" else "UNOBSERVED"
            reason = (
                source.reason_code
                if source.status == "HELD"
                else "MULTIPERSON_RESULT_UNOBSERVED"
            )
        elif row.result == "CANDIDATE_EXTRACTED":
            status, reason = (
                "PRIVATE_CANDIDATE_UNVERIFIED",
                "MULTIPERSON_CANDIDATE_NEEDS_REVIEW",
            )
        elif row.result == "FAILED":
            status, reason = "FAILED", "MULTIPERSON_ITEM_FAILED"
        else:
            status, reason = "HELD", (
                source.reason_code
                if source.status == "HELD"
                else "MULTIPERSON_OBSERVED_HELD"
            )
        items.append(
            PrivateBatchItemReceipt(
                passage_id=source.passage_id,
                content_id=source.content_id,
                capture_id=source.capture_id,
                source_family=source.source_family,
                source_sha256=source.source_sha256,
                passage_sha256=source.passage_sha256,
                selector_fingerprint=source.selector_fingerprint,
                partition_id=source.partition_id,
                speaker_candidate_id=source.speaker_candidate_id,
                language_tag=source.language_tag,
                context_version=source.context_version,
                identity_review_status=source.identity_review_status,
                speech_role=source.speech_role,
                speech_act=source.speech_act,
                context_review_id=source.context_review_id,
                rights_status=source.rights_status,
                status=status,
                reason_code=reason,
                observation_result=row.result if row is not None else None,
                failure_reason=row.failure_reason if row is not None else None,
                extraction_version=row.extraction_version if row is not None else None,
            )
        )
    frozen = tuple(items)
    counts = {
        "observed_count": sum(item.observation_result is not None for item in frozen),
        "pending_count": sum(item.status == "UNOBSERVED" for item in frozen),
        "failed_count": sum(item.status == "FAILED" for item in frozen),
        "held_count": sum(item.status == "HELD" for item in frozen),
        "private_candidate_count": sum(
            item.status == "PRIVATE_CANDIDATE_UNVERIFIED" for item in frozen
        ),
    }
    fingerprint = _stable_hash(
        {"version": VERSION, "plan": plan.plan_sha256,
         "items": [asdict(item) for item in frozen], "counts": counts}
    )
    return PrivateBatchReceiptIndex(plan.plan_sha256, frozen, fingerprint, **counts)


def _validate_receipt_index(
    plan: IsolatedBatchPlan,
    index: PrivateBatchReceiptIndex,
) -> tuple[PrivateBatchResult, ...]:
    _validate_isolated_plan(plan)
    if not isinstance(index, PrivateBatchReceiptIndex):
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    if index.plan_sha256 != plan.plan_sha256:
        raise ValueError("MULTIPERSON_RECEIPT_PLAN_MISMATCH")
    if (
        index.version != VERSION
        or index.publication_authority is not False
        or index.dispatch_authorized is not False
        or not isinstance(index.items, tuple)
        or len(index.items) != len(plan.items)
        or any(
            type(getattr(index, key)) is not int
            for key in (
                "observed_count",
                "pending_count",
                "failed_count",
                "held_count",
                "private_candidate_count",
            )
        )
    ):
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    observations: list[PrivateBatchResult] = []
    for source, receipt in zip(plan.items, index.items):
        if not isinstance(receipt, PrivateBatchItemReceipt):
            raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
        if receipt.passage_id != source.passage_id:
            raise ValueError("MULTIPERSON_RECEIPT_ORDER_INVALID")
        if (
            receipt.content_id,
            receipt.capture_id,
            receipt.source_family,
            receipt.source_sha256,
            receipt.passage_sha256,
            receipt.selector_fingerprint,
            receipt.partition_id,
            receipt.speaker_candidate_id,
            receipt.language_tag,
            receipt.context_version,
            receipt.identity_review_status,
            receipt.speech_role,
            receipt.speech_act,
            receipt.context_review_id,
            receipt.rights_status,
            receipt.public_attribution_authority,
        ) != (
            source.content_id,
            source.capture_id,
            source.source_family,
            source.source_sha256,
            source.passage_sha256,
            source.selector_fingerprint,
            source.partition_id,
            source.speaker_candidate_id,
            source.language_tag,
            source.context_version,
            source.identity_review_status,
            source.speech_role,
            source.speech_act,
            source.context_review_id,
            source.rights_status,
            False,
        ):
            raise ValueError("MULTIPERSON_RECEIPT_PROVENANCE_INVALID")
        if receipt.observation_result is not None:
            observations.append(
                PrivateBatchResult(
                    receipt.passage_id,
                    receipt.content_id,
                    receipt.capture_id,
                    receipt.passage_sha256,
                    receipt.observation_result,
                    receipt.failure_reason,
                    receipt.extraction_version,
                )
            )
        elif receipt.failure_reason is not None or receipt.extraction_version is not None:
            raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    try:
        reconstructed = _build_receipt_snapshot(plan, tuple(observations))
    except (TypeError, ValueError) as exc:
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID") from exc
    if index.items != reconstructed.items:
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    if (
        index.observed_count,
        index.pending_count,
        index.failed_count,
        index.held_count,
        index.private_candidate_count,
    ) != (
        reconstructed.observed_count,
        reconstructed.pending_count,
        reconstructed.failed_count,
        reconstructed.held_count,
        reconstructed.private_candidate_count,
    ):
        raise ValueError("MULTIPERSON_RECEIPT_COUNTS_INVALID")
    if index.receipt_sha256 != reconstructed.receipt_sha256:
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    return tuple(observations)


def build_private_batch_receipt_index(
    plan: IsolatedBatchPlan,
    observations: tuple[PrivateBatchResult, ...],
    *,
    previous_index: PrivateBatchReceiptIndex | None = None,
) -> PrivateBatchReceiptIndex:
    """Pure deterministic index/reconcile of durable *caller-held* receipts.

    Only a formerly unobserved ready item may gain its first result in a
    subsequent import. A FAILED/HELD/extracted observation cannot silently
    turn into a different outcome on retry for the same exact plan. Distinct
    authorized retry attempts require their own external durable job scope.
    No receipt proves a provider actually ran or a named Person spoke.
    """
    _validate_isolated_plan(plan)
    if not isinstance(observations, tuple):
        raise ValueError("MULTIPERSON_RESULT_INPUT_INVALID")
    earlier = (
        _validate_receipt_index(plan, previous_index)
        if previous_index is not None
        else ()
    )
    merged = {row.passage_id: row for row in earlier}
    for row in observations:
        if not isinstance(row, PrivateBatchResult):
            raise ValueError("MULTIPERSON_RESULT_SCHEMA_INVALID")
        prior = merged.get(row.passage_id)
        if prior is not None and prior != row:
            raise ValueError("MULTIPERSON_RECEIPT_REPLAY_CONFLICT")
        merged[row.passage_id] = row
    return _build_receipt_snapshot(plan, tuple(merged.values()))


def lookup_private_batch_item_receipt(
    plan: IsolatedBatchPlan,
    index: PrivateBatchReceiptIndex,
    *,
    passage_id: str,
    content_id: str,
    capture_id: str,
    source_sha256: str,
) -> PrivateBatchItemReceipt:
    """Exact-scoped read-only Passage lookup, never a homonym/Person lookup."""
    _validate_receipt_index(plan, index)
    matches = [row for row in index.items if row.passage_id == passage_id]
    if len(matches) != 1 or (
        matches[0].content_id,
        matches[0].capture_id,
        matches[0].source_sha256,
    ) != (content_id, capture_id, source_sha256):
        raise ValueError("MULTIPERSON_RECEIPT_SOURCE_MISMATCH")
    return matches[0]


def export_private_batch_receipt_index(
    plan: IsolatedBatchPlan,
    index: PrivateBatchReceiptIndex,
) -> dict[str, object]:
    """Return a JSON-serializable *private* receipt; never an approval token."""
    _validate_receipt_index(plan, index)
    return asdict(index)


def load_private_batch_receipt_index(
    plan: IsolatedBatchPlan,
    payload: Mapping[str, object],
) -> PrivateBatchReceiptIndex:
    """Rebuild and validate a caller-persisted receipt without trusting its SHA.

    The caller owns durable storage, authenticated retrieval, and any actual
    provider/job evidence. Extra fields and forged counts/statuses are refused.
    """
    _validate_isolated_plan(plan)
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {field.name for field in fields(PrivateBatchReceiptIndex)}
        or not isinstance(payload["items"], list)
        or len(payload["items"]) != len(plan.items)
    ):
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    item_keys = {field.name for field in fields(PrivateBatchItemReceipt)}
    if any(
        not isinstance(row, Mapping) or set(row) != item_keys
        for row in payload["items"]
    ):
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID")
    try:
        index = PrivateBatchReceiptIndex(
            **{
                **payload,
                "items": tuple(
                    PrivateBatchItemReceipt(**row) for row in payload["items"]
                ),
            }
        )
    except (ValueError, TypeError):
        raise ValueError("MULTIPERSON_RECEIPT_INTEGRITY_INVALID") from None
    _validate_receipt_index(plan, index)
    return index
