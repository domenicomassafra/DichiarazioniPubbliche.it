"""DP-516 source-only, bounded historical backfill *review plan*.

Pilot, rights, watch and budget receipts are caller-supplied claims.
This seam cannot authenticate external receipts, reserve funds, fetch, dispatch,
or publish. Synthetic checks never establish DP-443 acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Mapping

from dichiarazioni_pubbliche.historical_corpus_preflight_v1 import (
    HistoricalManifest,
    preflight_historical_corpus,
)
from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchPolicy,
    WatchReadiness,
    WatchState,
    plan_watch_poll,
)
from dichiarazioni_pubbliche.ops.cost_policy import (
    BudgetPolicy,
    CostSnapshot,
    MonthlyBudgetState,
    MonthlyEurPolicy,
    MonthlyFxQuote,
    monthly_budget_preflight,
)


VERSION = "historical-batch-private-plan-v1"
MAX_BATCH_ITEMS = 8
MAX_CHECKPOINT_RECEIPTS = 8
_SHA = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_COMMIT = re.compile(r"^[a-f0-9]{12,40}$")


def _hash(material: object) -> str:
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _CODE.fullmatch(value) is None:
        raise ValueError(f"DP516_{label}_INVALID")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError(f"DP516_{label}_INVALID")
    return value


def _at(value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("DP516_AWARE_TIME_REQUIRED")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class BatchPilotAcceptance:
    """Untrusted external *claim* until a separate trusted verifier authenticates it."""

    ticket: str
    decision: str
    scope_id: str
    signed_receipt_ref: str
    signer_ref: str
    signature: str
    runtime_host: str
    runtime_commit: str
    real_source_readback_sha256: str
    correction_readback_sha256: str
    rights_readback_sha256: str


@dataclass(frozen=True)
class BatchCost:
    content_id: str
    operation: str
    upper_bound_usd: Decimal | None


@dataclass(frozen=True)
class BatchWatch:
    content_id: str
    policy: WatchPolicy
    state: WatchState
    readiness: WatchReadiness


@dataclass(frozen=True)
class CompletedCapture:
    item_key: str
    person_id: str
    content_id: str
    source_family: str
    capture_sha256: str
    persisted_receipt_sha256: str


@dataclass(frozen=True)
class BatchCheckpoint:
    batch_id: str
    manifest_fingerprint: str
    completed: tuple[CompletedCapture, ...]
    revision: int
    failed: bool
    integrity_sha256: str
    version: str = VERSION


@dataclass(frozen=True)
class HistoricalBatchItemProposal:
    item_key: str
    person_id: str
    source_family: str
    content_id: str
    capture_sha256: str
    original_language: str
    source_kind: str
    operation: str
    upper_bound_usd: Decimal
    budget_attempt_id: str
    root_content_id: str | None
    # No job payload/permission. Can only be persisted after real authority/CAS.
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class HistoricalBatchDecision:
    status: str
    holds: tuple[str, ...]
    batch_id: str
    manifest_fingerprint: str
    proposals: tuple[HistoricalBatchItemProposal, ...]
    completed_keys: tuple[str, ...]
    checkpoint_fingerprint: str | None
    proposed_budget_state: MonthlyBudgetState | None
    coverage_state: str = "SCOPED_UNVERIFIED"
    pilot_accepted_by_system: bool = False
    dispatch_authorized: bool = False
    public_eligible: bool = False


def _checkpoint_material(
    batch_id: str,
    manifest_fingerprint: str,
    completed: tuple[CompletedCapture, ...],
    revision: int,
    failed: bool,
) -> dict[str, object]:
    return {
        "version": VERSION,
        "batch_id": batch_id,
        "manifest": manifest_fingerprint,
        "revision": revision,
        "failed": failed,
        "completed": [
            (
                r.item_key,
                r.person_id,
                r.content_id,
                r.source_family,
                r.capture_sha256,
                r.persisted_receipt_sha256,
            )
            for r in completed
        ],
    }


def create_checkpoint(
    batch_id: str,
    manifest_fingerprint: str,
    completed: tuple[CompletedCapture, ...],
    *,
    revision: int,
    failed: bool = False,
) -> BatchCheckpoint:
    """Create a deterministic checksum, never an authenticated commit receipt."""
    _id(batch_id, "BATCH_ID")
    _sha(manifest_fingerprint, "MANIFEST_HASH")
    if (
        not isinstance(completed, tuple)
        or len(completed) > MAX_CHECKPOINT_RECEIPTS
        or type(revision) is not int
        or revision < 0
        or type(failed) is not bool
    ):
        raise ValueError("DP516_CHECKPOINT_SHAPE_INVALID")
    seen: dict[str, CompletedCapture] = {}
    for receipt in completed:
        if not isinstance(receipt, CompletedCapture):
            raise ValueError("DP516_CHECKPOINT_RECEIPT_INVALID")
        for name in ("item_key", "person_id", "content_id", "source_family"):
            _id(getattr(receipt, name), "CHECKPOINT_" + name.upper())
        _sha(receipt.capture_sha256, "CHECKPOINT_CAPTURE")
        _sha(receipt.persisted_receipt_sha256, "CHECKPOINT_RECEIPT")
        if receipt.item_key in seen and seen[receipt.item_key] != receipt:
            raise ValueError("DP516_CHECKPOINT_REPLAY_CONFLICT")
        if receipt.item_key in seen:
            raise ValueError("DP516_CHECKPOINT_DUPLICATE")
        seen[receipt.item_key] = receipt
    ordered = tuple(sorted(completed, key=lambda receipt: receipt.item_key))
    if ordered != completed:
        raise ValueError("DP516_CHECKPOINT_NOT_CANONICAL")
    fingerprint = _hash(
        _checkpoint_material(
            batch_id, manifest_fingerprint, completed, revision, failed
        )
    )
    return BatchCheckpoint(
        batch_id, manifest_fingerprint, completed, revision, failed, fingerprint
    )


def _pilot_shape(pilot: BatchPilotAcceptance | None, scope_id: str) -> bool:
    if not isinstance(pilot, BatchPilotAcceptance):
        return False
    try:
        if (
            pilot.ticket != "DP-443"
            or pilot.decision != "GO_FOR_SCALING"
            or pilot.scope_id != scope_id
            or pilot.runtime_host != "MiniPC"
            or _COMMIT.fullmatch(pilot.runtime_commit) is None
        ):
            return False
        for field in ("signed_receipt_ref", "signer_ref", "signature"):
            _id(getattr(pilot, field), "PILOT_" + field.upper())
        for field in (
            "real_source_readback_sha256",
            "correction_readback_sha256",
            "rights_readback_sha256",
        ):
            _sha(getattr(pilot, field), "PILOT_" + field.upper())
    except ValueError:
        return False
    return True


def _work_key(
    person_id: str, source_family: str, content_id: str, capture_sha256: str
) -> str:
    return "item:" + _hash(
        [VERSION, person_id, source_family, content_id, capture_sha256]
    )


def plan_historical_batch(
    *,
    manifests: tuple[HistoricalManifest, ...],
    at: datetime,
    scope_id: str,
    pilot: BatchPilotAcceptance | None,
    verify_pilot: Callable[[BatchPilotAcceptance, str], bool] | None,
    costs: tuple[BatchCost, ...],
    watches: tuple[BatchWatch, ...],
    monthly_policy: MonthlyEurPolicy,
    monthly_state: MonthlyBudgetState,
    fx_quote: MonthlyFxQuote | None,
    legacy_policy: BudgetPolicy,
    legacy_snapshots: Mapping[str, CostSnapshot],
    checkpoint: BatchCheckpoint | None = None,
    verify_checkpoint: Callable[[BatchCheckpoint, str], bool] | None = None,
) -> HistoricalBatchDecision:
    """Deterministic private planning. Input receipts are never self-authenticating.

    verify_pilot and verify_checkpoint MUST live outside this module with
    independent trusted key/ledger access. A fake verifier can only demonstrate
    source-only consistency, not real pilot acceptance or durable authorization.
    All produced budget states are hypothetical and must NOT be committed here.
    """
    now = _at(at)
    _id(scope_id, "SCOPE")
    try:
        corpus = preflight_historical_corpus(manifests, now=now)
    except (ValueError, TypeError, AttributeError):
        return HistoricalBatchDecision(
            "HELD",
            ("DP243_MANIFEST_INVALID",),
            "batch:invalid",
            "",
            (),
            (),
            None,
            None,
        )
    batch_id = "batch:" + _hash([VERSION, scope_id, corpus.manifest_fingerprint])
    holds: set[str] = set()
    checkpoint_fingerprint = None
    completed: set[str] = set()
    if corpus.missing_primary_subjects:
        holds.add("MISSING_PRIMARY_SOURCE")
    if any(row.state != "PRIVATE_REVIEW_ONLY" or row.holds for row in corpus.rows):
        holds.add("DP243_ENTRY_HELD")
    if not corpus.rows or len(corpus.rows) > MAX_BATCH_ITEMS:
        holds.add("BATCH_ITEMS_OUT_OF_RANGE")
    if (
        not _pilot_shape(pilot, scope_id)
        or verify_pilot is None
        or not callable(verify_pilot)
    ):
        holds.add("DP443_PILOT_SIGNED_ACCEPTANCE_REQUIRED")
    else:
        try:
            if verify_pilot(pilot, scope_id) is not True:
                holds.add("DP443_PILOT_TRUST_NOT_VERIFIED")
        except Exception:
            holds.add("DP443_PILOT_TRUST_NOT_VERIFIED")

    if checkpoint is not None:
        if not isinstance(checkpoint, BatchCheckpoint):
            holds.add("CHECKPOINT_INVALID")
        else:
            try:
                regenerated = create_checkpoint(
                    checkpoint.batch_id,
                    checkpoint.manifest_fingerprint,
                    checkpoint.completed,
                    revision=checkpoint.revision,
                    failed=checkpoint.failed,
                )
                if checkpoint != regenerated or checkpoint.version != VERSION:
                    holds.add("CHECKPOINT_INTEGRITY_INVALID")
                elif (
                    checkpoint.batch_id != batch_id
                    or checkpoint.manifest_fingerprint != corpus.manifest_fingerprint
                ):
                    holds.add("CHECKPOINT_SCOPE_CHANGED")
                elif checkpoint.failed:
                    holds.add("FAILED_BATCH_NEEDS_EXTERNAL_REVIEW")
                elif verify_checkpoint is None or not callable(verify_checkpoint):
                    holds.add("CHECKPOINT_EXTERNAL_TRUST_REQUIRED")
                elif verify_checkpoint(checkpoint, batch_id) is not True:
                    holds.add("CHECKPOINT_EXTERNAL_TRUST_FAILED")
                else:
                    checkpoint_fingerprint = checkpoint.integrity_sha256
                    completed = {item.item_key for item in checkpoint.completed}
            except (ValueError, TypeError, AttributeError):
                holds.add("CHECKPOINT_INTEGRITY_INVALID")
            except Exception:
                holds.add("CHECKPOINT_EXTERNAL_TRUST_FAILED")

    # Reject checkpoint items from a different person/source/capture.
    by_content = {e.content_id: (m.person_id, e) for m in manifests for e in m.entries}
    eligible_keys: dict[str, tuple[str, str, str, str]] = {
        _work_key(person, e.source_family, e.content_id, e.source_version_sha256): (
            person,
            e.content_id,
            e.source_family,
            e.source_version_sha256,
        )
        for person, e in by_content.values()
    }
    if checkpoint is not None and completed:
        if any(
            eligible_keys.get(r.item_key)
            != (r.person_id, r.content_id, r.source_family, r.capture_sha256)
            for r in checkpoint.completed
        ):
            holds.add("CHECKPOINT_FOREIGN_ITEM")
    if not isinstance(costs, tuple) or not isinstance(watches, tuple):
        holds.add("BATCH_INPUT_INVALID")
        costs, watches = (), ()
    if (
        tuple.__len__(costs) > MAX_BATCH_ITEMS
        or tuple.__len__(watches) > MAX_BATCH_ITEMS
    ):
        holds.add("BATCH_ITEM_CAP")
    if type(costs) is not tuple or type(watches) is not tuple:
        holds.add("BATCH_INPUT_INVALID")
    if "BATCH_ITEM_CAP" in holds or "BATCH_INPUT_INVALID" in holds:
        return HistoricalBatchDecision(
            "HELD", tuple(sorted(holds)), batch_id, corpus.manifest_fingerprint,
            (), tuple(sorted(completed)), checkpoint_fingerprint, None,
        )
    cost_map: dict[str, BatchCost] = {}
    watch_map: dict[str, BatchWatch] = {}
    for row in costs[:MAX_BATCH_ITEMS]:
        if not isinstance(row, BatchCost) or row.content_id in cost_map:
            holds.add("BATCH_COST_DUPLICATE_OR_INVALID")
        else:
            cost_map[row.content_id] = row
    for row in watches[:MAX_BATCH_ITEMS]:
        if not isinstance(row, BatchWatch) or row.content_id in watch_map:
            holds.add("BATCH_WATCH_DUPLICATE_OR_INVALID")
        else:
            watch_map[row.content_id] = row
    if set(cost_map) != set(by_content) or set(watch_map) != set(by_content):
        holds.add("BATCH_SOURCE_SCOPE_MISMATCH")

    proposals: list[HistoricalBatchItemProposal] = []
    proposed_month = monthly_state
    dedupe: set[tuple[str, str, str, str]] = set()
    for person_id, item in sorted(
        by_content.values(),
        key=lambda part: (
            part[0],
            part[1].source_kind != "PRIMARY_ORIGINAL",
            part[1].content_id,
        ),
    ):
        key = _work_key(
            person_id, item.source_family, item.content_id, item.source_version_sha256
        )
        # Deduplicate immutable captures, including archive copies; keep DP-243 membership.
        dedupe_key = (
            person_id,
            item.source_family,
            item.source_version_sha256,
            item.origin_content_id or item.content_id,
        )
        if key in completed or dedupe_key in dedupe:
            # Recheck rights/version on skipped captures without polling or charging.
            hold_prefix = "WATCH_COMPLETED" if key in completed else "WATCH_SKIPPED"
            watch = watch_map.get(item.content_id)
            if watch is None:
                holds.add("BATCH_WATCH_MISSING")
            else:
                try:
                    watch_check = plan_watch_poll(
                        watch.policy,
                        watch.state,
                        watch.readiness,
                        attempt_id="batch-attempt:"
                        + _hash([batch_id, key, "CHECK_SKIPPED"]),
                        attempted_at=now,
                    )
                    if (
                        watch.content_id != item.content_id
                        or watch.policy.source_id != item.content_id
                        or watch.policy.source_family != item.source_family
                        or watch.policy.corpus_id
                        not in {
                            m.collection_id
                            for m in manifests
                            if m.person_id == person_id
                        }
                        or not watch.policy.enabled
                        or watch.readiness.source_id != watch.policy.source_id
                        or watch.readiness.corpus_id != watch.policy.corpus_id
                        or watch.readiness.policy_fingerprint
                        != watch_check.policy_fingerprint
                    ):
                        holds.add(hold_prefix + "_SCOPE_MISMATCH")
                    if (
                        watch.readiness.rights_status != "READY"
                        or not isinstance(watch.readiness.rights_receipt, str)
                        or not 0 < len(watch.readiness.rights_receipt) <= 256
                        or watch.readiness.rights_receipt
                        != watch.readiness.rights_receipt.strip()
                        or any(
                            ord(char) < 32 or ord(char) == 127
                            for char in watch.readiness.rights_receipt
                        )
                    ):
                        holds.add(hold_prefix + "_RIGHTS_NOT_READY")
                    if (
                        watch.state.content_sha256 is not None
                        and watch.state.content_sha256 != item.source_version_sha256
                    ):
                        holds.add(hold_prefix + "_SOURCE_CHANGED")
                except (ValueError, TypeError, AttributeError):
                    holds.add(hold_prefix + "_CONTRACT_INVALID")
            # A trusted completed root also covers identical archive copies.
            dedupe.add(dedupe_key)
            continue
        dedupe.add(dedupe_key)
        cost = cost_map.get(item.content_id)
        watch = watch_map.get(item.content_id)
        if cost is None or cost.operation not in {
            "CLAIM_EXTRACT",
            "AUDIO_TRANSCRIPTION",
        }:
            holds.add("BATCH_COST_UNKNOWN")
            continue
        if watch is None:
            holds.add("BATCH_WATCH_MISSING")
            continue
        if not isinstance(watch.state, WatchState):
            holds.add("WATCH_CONTRACT_INVALID")
            continue
        if (
            watch.state.content_sha256 is not None
            and watch.state.content_sha256 != item.source_version_sha256
        ):
            # A changed observed source requires a new DP-243 immutable version
            # and manifest acceptance, never work against stale pinned bytes.
            holds.add("WATCH_SOURCE_CHANGED")
            continue
        if (
            watch.state.content_sha256 == item.source_version_sha256
            and watch.state.last_successful_observed_at is not None
        ):
            # A successful source re-observation is NOT proof that a durable
            # immutable Capture was committed. Only an independently verified
            # DP-516 checkpoint can skip this cost unit safely.
            holds.add("WATCH_OBSERVED_CAPTURE_NOT_CHECKPOINTED")
            continue
        attempt_id = "batch-attempt:" + _hash([batch_id, key, cost.operation])
        try:
            ready = plan_watch_poll(
                watch.policy,
                watch.state,
                watch.readiness,
                attempt_id=attempt_id,
                attempted_at=now,
            )
            if (
                not ready.allowed
                or watch.content_id != item.content_id
                or watch.policy.source_id != item.content_id
                or watch.policy.source_family != item.source_family
                or watch.policy.corpus_id
                not in {m.collection_id for m in manifests if m.person_id == person_id}
            ):
                holds.add(
                    "WATCH_" + (ready.reason if not ready.allowed else "SCOPE_MISMATCH")
                )
        except (ValueError, TypeError, AttributeError):
            holds.add("WATCH_CONTRACT_INVALID")
        if item.content_id not in legacy_snapshots:
            holds.add("LEGACY_COST_SNAPSHOT_MISSING")
            continue
        try:
            monthly = monthly_budget_preflight(
                policy=monthly_policy,
                state=proposed_month,
                attempt_id=attempt_id,
                operation=cost.operation,
                upper_bound_usd=cost.upper_bound_usd,
                billing_basis="ESTIMATED_ONLY",
                at=now,
                fx_quote=fx_quote,
                legacy_policy=legacy_policy,
                legacy_snapshot=legacy_snapshots[item.content_id],
                expected_revision=proposed_month.revision,
            )
            if not monthly.eligible or monthly.proposed_state is None:
                holds.add("BUDGET_" + monthly.reason)
                continue
            proposed_month = monthly.proposed_state
            proposals.append(
                HistoricalBatchItemProposal(
                    key,
                    person_id,
                    item.source_family,
                    item.content_id,
                    item.source_version_sha256,
                    item.original_language,
                    item.source_kind,
                    cost.operation,
                    cost.upper_bound_usd,
                    attempt_id,
                    next(
                        (
                            row.root_content_id
                            for row in corpus.rows
                            if row.content_id == item.content_id
                        ),
                        None,
                    ),
                )
            )
        except (ValueError, TypeError, AttributeError):
            holds.add("BUDGET_CONTRACT_INVALID")
    if holds:
        return HistoricalBatchDecision(
            "HELD",
            tuple(sorted(holds)),
            batch_id,
            corpus.manifest_fingerprint,
            (),
            tuple(sorted(completed)),
            checkpoint_fingerprint,
            None,
        )
    return HistoricalBatchDecision(
        "PRIVATE_REVIEW_PLAN",
        (),
        batch_id,
        corpus.manifest_fingerprint,
        tuple(proposals),
        tuple(sorted(completed)),
        checkpoint_fingerprint,
        proposed_month if proposals else None,
    )


__all__ = [
    "VERSION",
    "BatchPilotAcceptance",
    "BatchCost",
    "BatchWatch",
    "CompletedCapture",
    "BatchCheckpoint",
    "HistoricalBatchItemProposal",
    "HistoricalBatchDecision",
    "create_checkpoint",
    "plan_historical_batch",
]
