"""DP-302 disabled-by-default right-of-reply intake runtime adapter.

This module composes the pure edge policy with the existing private persistence path in
``review_admin.record_right_of_reply``.  It intentionally exposes a callable service
boundary only: no HTTP listener, DNS, fetch, provider call, or publication action lives
here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Protocol

from dichiarazioni_pubbliche.policy.intake_policy import (
    INTAKE_POLICY_VERSION,
    IntakeDisposition,
    IntakeRejectionReason,
    RateLimitProfile,
    RateLimitState,
    rate_limit_decision,
    validate_intake_payload,
)
from dichiarazioni_pubbliche.review_admin import record_right_of_reply


MAX_ACK_BYTES = 512
MAX_LOGGABLE_RECEIPT_BYTES = 768


class ReplayKind(StrEnum):
    NONE = "NONE"
    DUPLICATE = "DUPLICATE"
    CONCURRENT = "CONCURRENT"


class ServiceState(StrEnum):
    RECEIVED_PRIVATE = "RECEIVED_PRIVATE"
    NOT_RECEIVED = "NOT_RECEIVED"
    DEFERRED = "DEFERRED"


class ServiceReason(StrEnum):
    OK = "OK"
    RATE_DECISION_MISSING = "RATE_DECISION_MISSING"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"
    PERSISTENCE_CONTRACT_ERROR = "PERSISTENCE_CONTRACT_ERROR"


@dataclass(frozen=True)
class RightOfReplyLaunchProfile:
    """Explicit launch posture for the runtime edge.

    Defaults are intentionally disabled.  A caller must configure both this profile and
    the nested rate profile before a submission can reach persistence.
    """

    configured: bool = False
    enabled: bool = False
    rate_profile: RateLimitProfile | None = None


@dataclass(frozen=True)
class IntakeServiceReceipt:
    """Bounded result safe to expose or log without private request material."""

    state: ServiceState
    reason: str
    receipt_time: str
    receipt_id: str | None = None
    replay: ReplayKind = ReplayKind.NONE
    created: bool = False

    @property
    def acknowledgement(self) -> dict[str, str]:
        if self.state is ServiceState.RECEIVED_PRIVATE and self.receipt_id:
            return {
                "receipt_id": self.receipt_id,
                "policy_version": INTAKE_POLICY_VERSION,
                "receipt_time": self.receipt_time,
                "state": ServiceState.RECEIVED_PRIVATE.value,
            }
        return {"state": self.state.value}

    @property
    def loggable_receipt(self) -> dict[str, object]:
        """Operational receipt containing no body, identity, URL, or fingerprint."""

        return {
            "state": self.state.value,
            "reason": self.reason,
            "receipt_time": self.receipt_time,
            "receipt_id": self.receipt_id,
            "replay": self.replay.value,
            "created": self.created,
        }

    def is_bounded(self) -> bool:
        ack = json.dumps(
            self.acknowledgement,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        loggable = json.dumps(
            self.loggable_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        combined = (ack + b" " + loggable).lower()
        forbidden = (b"accepted", b"approved", b"published", b"verified")
        return (
            len(ack) <= MAX_ACK_BYTES
            and len(loggable) <= MAX_LOGGABLE_RECEIPT_BYTES
            and not any(marker in combined for marker in forbidden)
        )


class RightOfReplyIntakeStore(Protocol):
    """Existing store seam consumed by ``record_right_of_reply``."""

    def finding_context(self, finding_id: str) -> dict[str, Any]: ...

    def claim_context(self, claim_id: str) -> dict[str, Any]: ...

    def insert_right_of_reply(self, **kwargs: Any) -> bool: ...

    def enqueue_followup(self, **kwargs: Any) -> tuple[str, bool]: ...

    def attach_reply_reanalysis_job(self, **kwargs: Any) -> bool: ...


class _ObservedStore:
    """Transparent store proxy that observes existing idempotency return values."""

    def __init__(self, delegate: RightOfReplyIntakeStore):
        self._delegate = delegate
        self.reply_inserted: bool | None = None
        self.followup_inserted: bool | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def insert_right_of_reply(self, **kwargs: Any) -> bool:
        inserted = self._delegate.insert_right_of_reply(**kwargs)
        if not isinstance(inserted, bool):
            raise RuntimeError("RIGHT_OF_REPLY_INSERT_RESULT_INVALID")
        self.reply_inserted = inserted
        return inserted

    def enqueue_followup(self, **kwargs: Any) -> tuple[str, bool]:
        result = self._delegate.enqueue_followup(**kwargs)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], str)
            or not isinstance(result[1], bool)
        ):
            raise RuntimeError("RIGHT_OF_REPLY_FOLLOWUP_RESULT_INVALID")
        self.followup_inserted = result[1]
        return result


def _now_utc(clock: Callable[[], datetime] | None) -> str:
    current = clock() if clock is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def _non_received_receipt(
    *,
    disposition: IntakeDisposition,
    reason: str,
    receipt_time: str,
) -> IntakeServiceReceipt:
    state = (
        ServiceState.DEFERRED
        if disposition is IntakeDisposition.DEFERRED_RATE_LIMITED
        else ServiceState.NOT_RECEIVED
    )
    return IntakeServiceReceipt(state=state, reason=reason, receipt_time=receipt_time)


def submit_right_of_reply(
    store: RightOfReplyIntakeStore,
    payload: object,
    *,
    launch_profile: RightOfReplyLaunchProfile | None = None,
    rate_state: RateLimitState | None = None,
    clock: Callable[[], datetime] | None = None,
) -> IntakeServiceReceipt:
    """Validate, quota-check, and persist one private reply submission.

    The adapter is disabled unless an explicit launch profile enables it.  Rate/quota
    state is caller-supplied and evaluated with the pure intake policy; the adapter never
    derives network identity or performs DNS.  Persistence is delegated exclusively to
    ``record_right_of_reply`` so the existing ``PRIVATE/RECEIVED`` + deterministic
    re-analysis contract remains authoritative.
    """

    profile = launch_profile or RightOfReplyLaunchProfile()
    receipt_time = _now_utc(clock)
    validation = validate_intake_payload(
        payload,
        intake_enabled=profile.enabled,
        launch_profile_configured=profile.configured,
    )
    if not validation.accepted:
        return _non_received_receipt(
            disposition=validation.disposition,
            reason=validation.reason.value,
            receipt_time=receipt_time,
        )

    if profile.rate_profile is None or rate_state is None:
        return IntakeServiceReceipt(
            state=ServiceState.NOT_RECEIVED,
            reason=ServiceReason.RATE_DECISION_MISSING.value,
            receipt_time=receipt_time,
        )

    rate_disposition, rate_reason = rate_limit_decision(profile.rate_profile, rate_state)
    if rate_disposition is not IntakeDisposition.ACCEPTED_PRIVATE:
        return _non_received_receipt(
            disposition=rate_disposition,
            reason=rate_reason.value,
            receipt_time=receipt_time,
        )

    if not isinstance(payload, dict) or validation.source_hash is None:
        return IntakeServiceReceipt(
            state=ServiceState.NOT_RECEIVED,
            reason=ServiceReason.PERSISTENCE_CONTRACT_ERROR.value,
            receipt_time=receipt_time,
        )

    # Values are safe to consume only after the exact edge validator has accepted them.
    finding_id = str(payload["finding_id"]).strip()
    body = str(payload["body"]).strip()
    submitter_name = payload.get("submitter_name")
    submitter_role = payload.get("submitter_role")
    normalized_name = str(submitter_name).strip() if submitter_name is not None else None
    normalized_role = str(submitter_role).strip() if submitter_role is not None else None

    observed = _ObservedStore(store)
    try:
        receipt_id = record_right_of_reply(
            observed,  # type: ignore[arg-type] - protocol-compatible proxy
            finding_id=finding_id,
            submitter_name=normalized_name,
            submitter_role=normalized_role,
            body=body,
            evidence_urls=list(validation.normalized_evidence_urls),
        )
    except Exception:  # noqa: BLE001 - public edge must not reflect private/store errors
        return IntakeServiceReceipt(
            state=ServiceState.NOT_RECEIVED,
            reason=ServiceReason.PERSISTENCE_ERROR.value,
            receipt_time=receipt_time,
        )

    if observed.reply_inserted is None or observed.followup_inserted is None:
        return IntakeServiceReceipt(
            state=ServiceState.NOT_RECEIVED,
            reason=ServiceReason.PERSISTENCE_CONTRACT_ERROR.value,
            receipt_time=receipt_time,
        )

    if observed.reply_inserted and observed.followup_inserted:
        replay = ReplayKind.NONE
    elif not observed.reply_inserted and not observed.followup_inserted:
        replay = ReplayKind.DUPLICATE
    else:
        # One side won a deterministic ON CONFLICT race while the other side had not.
        replay = ReplayKind.CONCURRENT

    return IntakeServiceReceipt(
        state=ServiceState.RECEIVED_PRIVATE,
        reason=ServiceReason.OK.value,
        receipt_time=receipt_time,
        receipt_id=receipt_id,
        replay=replay,
        created=observed.reply_inserted,
    )


__all__ = [
    "IntakeServiceReceipt",
    "MAX_ACK_BYTES",
    "MAX_LOGGABLE_RECEIPT_BYTES",
    "ReplayKind",
    "RightOfReplyIntakeStore",
    "RightOfReplyLaunchProfile",
    "ServiceReason",
    "ServiceState",
    "submit_right_of_reply",
]
