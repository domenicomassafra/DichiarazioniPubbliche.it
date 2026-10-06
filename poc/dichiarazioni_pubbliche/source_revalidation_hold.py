from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from dichiarazioni_pubbliche.provenance_quarantine import (
    BoundedDependencyGraph,
    HoldReceipt,
    HoldScopeTarget,
    InMemoryProvenanceHoldRegistry,
)
from dichiarazioni_pubbliche.source_revalidation import (
    SOURCE_REVALIDATION_VERSION,
    RevalidationDecision,
    RevalidationDisposition,
    SourceSnapshot,
    snapshot_ref,
)


SOURCE_REVALIDATION_HOLD_ADAPTER_VERSION = "source-revalidation-hold-v1"


class SourceRevalidationHoldError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "SOURCE_REVALIDATION_HOLD_ERROR").strip().upper()[:200]
        super().__init__(self.code)


def _text(value: object, name: str, *, maximum: int = 256) -> str:
    if isinstance(value, bool):
        raise SourceRevalidationHoldError(f"SOURCE_REVALIDATION_HOLD_{name}_INVALID")
    text = str(value or "").strip()
    if not text:
        raise SourceRevalidationHoldError(f"SOURCE_REVALIDATION_HOLD_{name}_REQUIRED")
    if len(text) > maximum:
        raise SourceRevalidationHoldError(f"SOURCE_REVALIDATION_HOLD_{name}_TOO_LONG")
    return text


def _sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _expected_event_key(
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
) -> str:
    codes = tuple(
        sorted(
            set(decision.material_change_codes + decision.benign_change_codes)
        )
    )
    return _sha(
        {
            "version": SOURCE_REVALIDATION_VERSION,
            "source_id": previous.source_id,
            "previous_snapshot_ref": snapshot_ref(previous),
            "current_snapshot_ref": snapshot_ref(current),
            "change_codes": list(codes),
        }
    )


@dataclass(frozen=True)
class SourceRevalidationHoldRequest:
    request_id: str
    hold_id: str
    reason_code: str
    incident_id: str
    scope: HoldScopeTarget
    decision_event_key: str
    previous_snapshot_ref: str
    current_snapshot_ref: str
    adapter_version: str = SOURCE_REVALIDATION_HOLD_ADAPTER_VERSION


@dataclass(frozen=True)
class SourceRevalidationHoldReceipt:
    decision_event_key: str
    previous_snapshot_ref: str
    current_snapshot_ref: str
    request: SourceRevalidationHoldRequest
    hold: HoldReceipt
    material_change_codes: tuple[str, ...]
    adapter_version: str = SOURCE_REVALIDATION_HOLD_ADAPTER_VERSION


def build_source_revalidation_hold_request(
    *,
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
    provider_id: str,
) -> SourceRevalidationHoldRequest | None:
    provider = _text(provider_id, "PROVIDER_ID")
    if decision.version != SOURCE_REVALIDATION_VERSION:
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_DECISION_VERSION_MISMATCH")
    if str(previous.source_id or "").strip() != str(current.source_id or "").strip():
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_SOURCE_ID_MISMATCH")

    previous_ref = snapshot_ref(previous)
    current_ref = snapshot_ref(current)
    if decision.previous_snapshot_ref != previous_ref:
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_PREVIOUS_REF_MISMATCH")
    if decision.current_snapshot_ref != current_ref:
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_CURRENT_REF_MISMATCH")
    if decision.event_key != _expected_event_key(decision, previous, current):
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_EVENT_KEY_MISMATCH")

    if decision.disposition in {
        RevalidationDisposition.UNCHANGED,
        RevalidationDisposition.AVAILABILITY_RETRY,
        RevalidationDisposition.REVIEW_REQUIRED,
    }:
        if decision.needs_targeted_hold:
            raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_DECISION_CONFLICT")
        return None
    if decision.disposition is not RevalidationDisposition.HOLD_REQUIRED:
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_DISPOSITION_INVALID")
    if not decision.needs_targeted_hold:
        raise SourceRevalidationHoldError("SOURCE_REVALIDATION_HOLD_DECISION_CONFLICT")

    source_version = _text(previous.source_version, "SOURCE_VERSION")
    source_id = _text(previous.source_id, "SOURCE_ID")
    event_key = _text(decision.event_key, "EVENT_KEY", maximum=64)
    scope = HoldScopeTarget.source(
        provider_id=provider,
        source_id=source_id,
        source_version=source_version,
    )
    identity = {
        "provider_id": provider,
        "source_id": source_id,
        "source_version": source_version,
        "event_key": event_key,
        "adapter_version": SOURCE_REVALIDATION_HOLD_ADAPTER_VERSION,
    }
    identity_sha256 = _sha(identity)
    return SourceRevalidationHoldRequest(
        request_id=f"source-revalidation:{event_key}",
        hold_id=f"source-revalidation-hold:{identity_sha256}",
        reason_code="SOURCE_REVALIDATION_HOLD",
        incident_id=f"source-revalidation:{event_key}",
        scope=scope,
        decision_event_key=event_key,
        previous_snapshot_ref=previous_ref,
        current_snapshot_ref=current_ref,
    )


def activate_source_revalidation_hold(
    *,
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
    provider_id: str,
    actor_id: str,
    graph: BoundedDependencyGraph,
    registry: InMemoryProvenanceHoldRegistry,
) -> SourceRevalidationHoldReceipt | None:
    request = build_source_revalidation_hold_request(
        decision=decision,
        previous=previous,
        current=current,
        provider_id=provider_id,
    )
    if request is None:
        return None
    hold = registry.activate(
        request_id=request.request_id,
        hold_id=request.hold_id,
        actor_id=actor_id,
        reason_code=request.reason_code,
        incident_id=request.incident_id,
        scope=request.scope,
        graph=graph,
    )
    return SourceRevalidationHoldReceipt(
        decision_event_key=request.decision_event_key,
        previous_snapshot_ref=request.previous_snapshot_ref,
        current_snapshot_ref=request.current_snapshot_ref,
        request=request,
        hold=hold,
        material_change_codes=tuple(sorted(set(decision.material_change_codes))),
    )


__all__ = [
    "SOURCE_REVALIDATION_HOLD_ADAPTER_VERSION",
    "SourceRevalidationHoldError",
    "SourceRevalidationHoldReceipt",
    "SourceRevalidationHoldRequest",
    "activate_source_revalidation_hold",
    "build_source_revalidation_hold_request",
]
