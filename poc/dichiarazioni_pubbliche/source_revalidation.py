from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Mapping


SOURCE_REVALIDATION_VERSION = "source-revalidation-v1"


class ReobservationState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class RevalidationDisposition(StrEnum):
    UNCHANGED = "UNCHANGED"
    AVAILABILITY_RETRY = "AVAILABILITY_RETRY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HOLD_REQUIRED = "HOLD_REQUIRED"


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    observed_at: datetime
    availability: ReobservationState | str
    content_sha256: str | None
    source_version: str | None
    etag: str | None
    canonical_url: str
    supersedes_version: str | None = None
    rights_status: str = "UNKNOWN"
    rights_expires_on: date | None = None
    authority_valid_until: date | None = None
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RevalidationDecision:
    disposition: RevalidationDisposition
    material_change_codes: tuple[str, ...]
    benign_change_codes: tuple[str, ...]
    needs_reanalysis: bool
    needs_targeted_hold: bool
    event_key: str
    previous_snapshot_ref: str
    current_snapshot_ref: str
    version: str = SOURCE_REVALIDATION_VERSION


def _availability(value: ReobservationState | str) -> ReobservationState:
    try:
        return value if isinstance(value, ReobservationState) else ReobservationState(str(value))
    except ValueError as exc:
        raise ValueError("SOURCE_REVALIDATION_AVAILABILITY_INVALID") from exc


def _sha(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    cleaned = str(value).lower().strip()
    if len(cleaned) != 64 or any(ch not in "0123456789abcdef" for ch in cleaned):
        raise ValueError("SOURCE_REVALIDATION_CONTENT_HASH_INVALID")
    return cleaned


def _snapshot_payload(snapshot: SourceSnapshot) -> dict[str, object]:
    observed = snapshot.observed_at
    if observed.tzinfo is None:
        raise ValueError("SOURCE_REVALIDATION_OBSERVED_AT_TZ_REQUIRED")
    return {
        "source_id": str(snapshot.source_id).strip(),
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
        "availability": _availability(snapshot.availability).value,
        "content_sha256": _sha(snapshot.content_sha256),
        "source_version": str(snapshot.source_version or "").strip() or None,
        "etag": str(snapshot.etag or "").strip() or None,
        "canonical_url": str(snapshot.canonical_url or "").strip(),
        "supersedes_version": str(snapshot.supersedes_version or "").strip() or None,
        "rights_status": str(snapshot.rights_status or "UNKNOWN").strip().upper(),
        "rights_expires_on": snapshot.rights_expires_on.isoformat() if snapshot.rights_expires_on else None,
        "authority_valid_until": snapshot.authority_valid_until.isoformat() if snapshot.authority_valid_until else None,
    }


def snapshot_ref(snapshot: SourceSnapshot) -> str:
    payload = _snapshot_payload(snapshot)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_key(previous: SourceSnapshot, current: SourceSnapshot, codes: tuple[str, ...]) -> str:
    payload = {
        "version": SOURCE_REVALIDATION_VERSION,
        "source_id": previous.source_id,
        "previous_snapshot_ref": snapshot_ref(previous),
        "current_snapshot_ref": snapshot_ref(current),
        "change_codes": list(codes),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def evaluate_reobservation(
    previous: SourceSnapshot,
    current: SourceSnapshot,
    *,
    as_of: date,
    load_bearing_for_quote: bool = False,
    load_bearing_for_speaker: bool = False,
    load_bearing_for_evidence: bool = False,
) -> RevalidationDecision:
    if not str(previous.source_id).strip() or previous.source_id != current.source_id:
        raise ValueError("SOURCE_REVALIDATION_SOURCE_ID_MISMATCH")
    if current.observed_at < previous.observed_at:
        raise ValueError("SOURCE_REVALIDATION_OBSERVATION_ORDER_INVALID")

    previous_state = _availability(previous.availability)
    current_state = _availability(current.availability)
    previous_hash = _sha(previous.content_sha256)
    current_hash = _sha(current.content_sha256)
    material: list[str] = []
    benign: list[str] = []

    if current_state is ReobservationState.UNAVAILABLE:
        # Temporary disappearance is operationally relevant but is not evidence that
        # previously observed source bytes changed.
        if previous_state is ReobservationState.AVAILABLE:
            benign.append("SOURCE_UNAVAILABLE")
    else:
        if previous_state is ReobservationState.UNAVAILABLE:
            benign.append("SOURCE_AVAILABLE_AGAIN")
        if previous_hash and current_hash and previous_hash != current_hash:
            material.append("CONTENT_HASH_CHANGED")
        if previous.source_version and current.source_version and previous.source_version != current.source_version:
            material.append("SOURCE_VERSION_CHANGED")
        if current.supersedes_version and current.supersedes_version in {
            previous.source_version,
            previous.supersedes_version,
        }:
            material.append("OFFICIAL_VERSION_SUPERSEDED")
        if previous.etag != current.etag and previous.etag and current.etag:
            if previous_hash == current_hash:
                benign.append("ETAG_CHANGED_BYTES_STABLE")
            else:
                material.append("ETAG_CHANGED_WITH_CONTENT")
        if previous.canonical_url != current.canonical_url:
            if previous_hash and previous_hash == current_hash:
                benign.append("CANONICAL_LOCATOR_CHANGED_BYTES_STABLE")
            else:
                material.append("CANONICAL_LOCATOR_CHANGED_UNVERIFIED")

    previous_rights = str(previous.rights_status or "UNKNOWN").strip().upper()
    current_rights = str(current.rights_status or "UNKNOWN").strip().upper()
    if previous_rights != current_rights:
        if current_rights in {"REVOKED", "BLOCKED", "FORBIDDEN", "LEGAL_HOLD", "RIGHTS_HOLD", "TAKEDOWN_HOLD", "REMOVED"}:
            material.append("RIGHTS_STATE_BLOCKED")
        else:
            material.append("RIGHTS_STATE_CHANGED")
    if current.rights_expires_on is not None and as_of >= current.rights_expires_on:
        material.append("RIGHTS_EXPIRED")
    if current.authority_valid_until is not None and as_of >= current.authority_valid_until:
        material.append("AUTHORITY_SCOPE_EXPIRED")

    material_codes = tuple(sorted(set(material)))
    benign_codes = tuple(sorted(set(benign)))
    safety_critical = bool(
        set(material_codes)
        & {
            "CONTENT_HASH_CHANGED",
            "SOURCE_VERSION_CHANGED",
            "OFFICIAL_VERSION_SUPERSEDED",
            "RIGHTS_STATE_BLOCKED",
            "RIGHTS_EXPIRED",
            "AUTHORITY_SCOPE_EXPIRED",
            "CANONICAL_LOCATOR_CHANGED_UNVERIFIED",
        }
    )
    load_bearing = load_bearing_for_quote or load_bearing_for_speaker or load_bearing_for_evidence
    hold_required = safety_critical and load_bearing
    if hold_required:
        disposition = RevalidationDisposition.HOLD_REQUIRED
    elif material_codes:
        disposition = RevalidationDisposition.REVIEW_REQUIRED
    elif "SOURCE_UNAVAILABLE" in benign_codes:
        disposition = RevalidationDisposition.AVAILABILITY_RETRY
    else:
        disposition = RevalidationDisposition.UNCHANGED
    all_codes = tuple(sorted(set(material_codes + benign_codes)))
    return RevalidationDecision(
        disposition=disposition,
        material_change_codes=material_codes,
        benign_change_codes=benign_codes,
        needs_reanalysis=bool(material_codes),
        needs_targeted_hold=hold_required,
        event_key=_event_key(previous, current, all_codes),
        previous_snapshot_ref=snapshot_ref(previous),
        current_snapshot_ref=snapshot_ref(current),
    )


__all__ = [
    "SOURCE_REVALIDATION_VERSION",
    "ReobservationState",
    "RevalidationDecision",
    "RevalidationDisposition",
    "SourceSnapshot",
    "evaluate_reobservation",
    "snapshot_ref",
]
