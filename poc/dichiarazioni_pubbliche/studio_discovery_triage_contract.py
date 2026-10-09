"""Pure, private Discovery triage request and persisted receipt boundary.

This module neither performs a write nor grants the caller review authority.
The caller must separately establish operator identity, row scope and durable
state-transition authority before submitting any validated intent to a store.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Mapping


STUDIO_DISCOVERY_TRIAGE_VERSION = "studio-discovery-triage-v1"
TRIAGE_DECISIONS = frozenset({"NEEDS_REVIEW", "DEFERRED", "REJECTED"})
_RECEIPT_CODES = frozenset({
    "CREATED", "REPLAY", "SCOPE_NOT_FOUND", "IDEMPOTENCY_CONFLICT",
    "REVISION_CONFLICT",
})
_ID = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z", re.ASCII)
_OPAQUE = re.compile(r"[A-Za-z0-9_:/.-]{1,128}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MAX_BIGINT = (1 << 63) - 1


def _validated_ref(value: object, *, opaque: bool = False) -> str:
    if not isinstance(value, str) or not (_OPAQUE if opaque else _ID).fullmatch(value):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_REFERENCE_INVALID")
    return value


def _validated_revision(value: object, *, expected: bool = False) -> int:
    # The persisted revision is a PostgreSQL signed bigint. A requested
    # expected_revision must leave room for a successful revision increment.
    if type(value) is not int or not 0 <= value <= _MAX_BIGINT - int(expected):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_REVISION_INVALID")
    return value


def _validated_decision(value: object) -> str:
    if not isinstance(value, str) or value not in TRIAGE_DECISIONS:
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_DECISION_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class StudioDiscoveryTriageRequest:
    """An immutable intent only; all fields contribute to its replay fingerprint."""

    collection_id: str
    hit_id: str
    request_key: str = field(repr=False)
    decision: str
    expected_revision: int
    actor_ref: str = field(repr=False)
    payload_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _validated_ref(self.collection_id)
        _validated_ref(self.hit_id)
        _validated_ref(self.request_key, opaque=True)
        _validated_decision(self.decision)
        _validated_revision(self.expected_revision, expected=True)
        _validated_ref(self.actor_ref, opaque=True)
        # JSON field order and separators are fixed; no string coercion or trimming.
        # An actor or expected-revision change must conflict for the same request key.
        canonical = json.dumps(
            {
                "collection_id": self.collection_id,
                "hit_id": self.hit_id,
                "request_key": self.request_key,
                "decision": self.decision,
                "expected_revision": self.expected_revision,
                "actor_ref": self.actor_ref,
            },
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")
        object.__setattr__(self, "payload_sha256", hashlib.sha256(canonical).hexdigest())


def make_triage_request(
    *, collection_id: str, hit_id: str, request_key: str, decision: str,
    expected_revision: int, actor_ref: str,
) -> StudioDiscoveryTriageRequest:
    """Validate a private Discovery intent without scheduling any action."""
    return StudioDiscoveryTriageRequest(
        collection_id=collection_id, hit_id=hit_id, request_key=request_key,
        decision=decision, expected_revision=expected_revision,
        actor_ref=actor_ref,
    )


def present_triage_receipt(
    row: Mapping[str, object], *, request: StudioDiscoveryTriageRequest,
) -> dict[str, object]:
    """Check a store result and return only bounded, explicit receipt fields.

    The store must perform the durable idempotency check against its existing
    record before assigning REPLAY; its receipt echoes the requested fingerprint
    for all codes, including conflicts. This parser checks the echoed request,
    and discards all extra columns, URLs and private metadata.
    """
    if not isinstance(request, StudioDiscoveryTriageRequest):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_REQUEST_INVALID")
    if not isinstance(row, Mapping):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_RECEIPT_INVALID")
    result_code = row.get("result_code")
    if not isinstance(result_code, str) or result_code not in _RECEIPT_CODES:
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_RESULT_INVALID")
    collection_id = _validated_ref(row.get("collection_id"))
    hit_id = _validated_ref(row.get("hit_id"))
    request_key = _validated_ref(row.get("request_key"), opaque=True)
    if (collection_id, hit_id, request_key) != (
        request.collection_id, request.hit_id, request.request_key,
    ):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_SCOPE_MISMATCH")
    decision = _validated_decision(row.get("decision"))
    expected_revision = _validated_revision(row.get("expected_revision"), expected=True)
    payload_sha256 = row.get("payload_sha256")
    if not isinstance(payload_sha256, str) or not _SHA256.fullmatch(payload_sha256):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_FINGERPRINT_INVALID")
    revision = row.get("revision")
    if result_code == "SCOPE_NOT_FOUND":
        if revision is not None:
            raise ValueError("STUDIO_DISCOVERY_TRIAGE_NOT_FOUND_INVALID")
    else:
        revision = _validated_revision(revision)

    # The result's safe identity must always bind to this exact request. The
    # preexisting fingerprint in a key conflict is validated inside the store;
    # it is not part of the current SQL receipt.
    if (
        decision != request.decision
        or expected_revision != request.expected_revision
        or payload_sha256 != request.payload_sha256
    ):
        raise ValueError("STUDIO_DISCOVERY_TRIAGE_REQUEST_ECHO_MISMATCH")

    if result_code in {"CREATED", "REPLAY"}:
        if revision != request.expected_revision + 1:
            raise ValueError("STUDIO_DISCOVERY_TRIAGE_REPLAY_MISMATCH")
    elif result_code == "REVISION_CONFLICT":
        if revision == request.expected_revision:
            raise ValueError("STUDIO_DISCOVERY_TRIAGE_CONFLICT_INVALID")

    # Scope-less SQL returns NULL rather than revealing another Collection's
    # Hit revisions. This is enforced here as part of the persisted contract.

    return {
        "contract_version": STUDIO_DISCOVERY_TRIAGE_VERSION,
        "private_only": True,
        "publication_authority": False,
        "triage_action_authorized": False,
        "result_code": result_code,
        "collection_id": collection_id,
        "hit_id": hit_id,
        "request_key": request_key,
        "decision": decision,
        "expected_revision": expected_revision,
        "revision": revision,
        "payload_sha256": payload_sha256,
    }


__all__ = [
    "STUDIO_DISCOVERY_TRIAGE_VERSION", "TRIAGE_DECISIONS",
    "StudioDiscoveryTriageRequest", "make_triage_request", "present_triage_receipt",
]
