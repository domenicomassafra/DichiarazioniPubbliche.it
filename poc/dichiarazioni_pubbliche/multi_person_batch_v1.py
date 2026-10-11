"""DP-240 bounded, private, multi-source/multi-speaker candidate batch preflight.

Builds *isolated* source items from an existing private CandidateBatch. A speaker
candidate is never a proved identity, and model output is never public. No
provider calls, rights grants, reviews, or automatic child job creation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
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
        ):
            raise ValueError("MULTIPERSON_PLAN_ITEM_INVALID")
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
