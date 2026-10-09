"""Private, metadata-only comparison of two persisted capture versions.

DP-419 preparatory reader: no private body, transcript, page URL, provider
receipt, secrets, arbitrary metadata or publication eligibility is returned.
Missing/stale/mismatched captures fail closed; no network or write operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.corpus_repository import (
    CAPTURE_ARCHIVE_STATUSES,
    CAPTURE_HOLD_STATUSES,
    CAPTURE_STATUSES,
)

CAPTURE_INSPECTION_VERSION = "studio-capture-inspection-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")


class CaptureLookup(Protocol):
    def find_capture(self, content_id: str, content_sha256: str) -> dict[str, Any] | None: ...


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_CAPTURE_ID_INVALID")
    return value


def _safe_state(value: object, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"STUDIO_CAPTURE_{label}_INVALID")
    return value


def _has_aware_time(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return stamp.tzinfo is not None and stamp.utcoffset() is not None


def _has_receipt(value: object) -> bool:
    # Never echo the receipt: the private inspector exposes status only.
    return isinstance(value, Mapping) and bool(value)


@dataclass(frozen=True)
class CaptureInspection:
    id: str
    content_sha256: str
    capture_state: str
    hold_state: str
    archive_state: str
    body_state: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "content_sha256": self.content_sha256,
            "capture_state": self.capture_state,
            "hold_state": self.hold_state,
            "archive_state": self.archive_state,
            "body_state": self.body_state,
        }


def _select_metadata(raw: Mapping[str, Any], content_id: str, expected_hash: str) -> CaptureInspection:
    if raw.get("content_id") != content_id or raw.get("content_sha256") != expected_hash:
        raise ValueError("STUDIO_CAPTURE_BINDING_MISMATCH")
    capture_state = _safe_state(raw.get("status"), CAPTURE_STATUSES, "STATUS")
    hold_state = _safe_state(raw.get("hold_status"), CAPTURE_HOLD_STATUSES, "HOLD")
    archive_state = _safe_state(raw.get("archive_status"), CAPTURE_ARCHIVE_STATUSES, "ARCHIVE")
    if archive_state != "NOT_REQUESTED" and (
        not isinstance(raw.get("archive_provider"), str)
        or not raw["archive_provider"].strip()
        or not _has_aware_time(raw.get("archive_requested_at"))
    ):
        raise ValueError("STUDIO_CAPTURE_ARCHIVE_PROOF_INVALID")
    if archive_state in {"SUCCEEDED", "FAILED"} and (
        not _has_aware_time(raw.get("archive_completed_at"))
        or not _has_receipt(raw.get("archive_receipt"))
    ):
        raise ValueError("STUDIO_CAPTURE_ARCHIVE_PROOF_INVALID")
    if capture_state == "PURGED_BODY":
        if (
            raw.get("body_ref") is not None
            or not _has_aware_time(raw.get("body_purged_at"))
            or not isinstance(raw.get("purge_reason"), str)
            or not raw["purge_reason"].strip()
            or not _has_receipt(raw.get("purge_receipt"))
        ):
            raise ValueError("STUDIO_CAPTURE_PURGE_PROOF_INVALID")
    elif raw.get("body_purged_at") is not None:
        # A timestamp cannot independently impersonate a completed purge.
        raise ValueError("STUDIO_CAPTURE_PURGE_PROOF_INVALID")
    body_state = (
        "PURGED" if capture_state == "PURGED_BODY"
        else "STORED_UNVERIFIED" if raw.get("body_ref")
        else "NOT_STORED"
    )
    return CaptureInspection(
        id=_safe_id(raw.get("id")),
        content_sha256=expected_hash,
        capture_state=capture_state,
        hold_state=hold_state,
        archive_state=archive_state,
        body_state=body_state,
    )


def inspect_capture_versions(
    store: CaptureLookup,
    *,
    content_id: str,
    earlier_hash: str,
    later_hash: str,
) -> dict[str, object]:
    content_id = _safe_id(content_id)
    if not isinstance(earlier_hash, str) or not _SHA.fullmatch(earlier_hash):
        raise ValueError("STUDIO_CAPTURE_EARLIER_HASH_INVALID")
    if not isinstance(later_hash, str) or not _SHA.fullmatch(later_hash):
        raise ValueError("STUDIO_CAPTURE_LATER_HASH_INVALID")
    if earlier_hash == later_hash:
        raise ValueError("STUDIO_CAPTURE_DISTINCT_VERSIONS_REQUIRED")
    try:
        earlier_raw = store.find_capture(content_id, earlier_hash)
        later_raw = store.find_capture(content_id, later_hash)
    except Exception:
        raise RuntimeError("STUDIO_CAPTURE_STORE_UNAVAILABLE") from None
    if not isinstance(earlier_raw, Mapping) or not isinstance(later_raw, Mapping):
        raise RuntimeError("STUDIO_CAPTURE_VERSION_MISSING")
    earlier = _select_metadata(earlier_raw, content_id, earlier_hash)
    later = _select_metadata(later_raw, content_id, later_hash)
    if earlier.id == later.id:
        raise RuntimeError("STUDIO_CAPTURE_IDENTITY_COLLISION")
    return {
        "contract_version": CAPTURE_INSPECTION_VERSION,
        "private_only": True,
        "publication_authority": False,
        "content_id": content_id,
        "earlier": earlier.to_dict(),
        "later": later.to_dict(),
        "changes": {
            "body_hash_changed": True,
            "capture_state_changed": earlier.capture_state != later.capture_state,
            "hold_changed": earlier.hold_state != later.hold_state,
            "archive_changed": earlier.archive_state != later.archive_state,
            "body_storage_changed": earlier.body_state != later.body_state,
        },
    }


__all__ = [
    "CAPTURE_INSPECTION_VERSION", "CaptureInspection", "CaptureLookup", "inspect_capture_versions",
]
