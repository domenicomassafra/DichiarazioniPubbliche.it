"""Exact, private DP-418 candidate/target source binding validation.

The persisted PostgreSQL reader is the source of truth, not the matcher's
suggested source fields. This guard validates bounded identity, capture
version and state without exposing source text or granting any authority.
"""

from __future__ import annotations

import re
from typing import Mapping

_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RIGHTS = {"CLEARED", "UNKNOWN", "REVOKED", "EXPIRED", "DENIED"}
_CAPTURE_STATES = {"CAPTURED", "PURGED_BODY", "QUARANTINED"}
_CAPTURE_HOLDS = {
    "NONE", "RIGHTS", "RIGHTS_HOLD", "PRIVACY_HOLD", "COPYRIGHT_HOLD",
    "LEGAL_HOLD", "DISPUTE_HOLD",
}
_KEYS = (
    "member_id", "member_type", "content_id", "passage_id", "capture_id",
    "capture_sha256", "rights_status", "capture_status", "capture_hold_status",
)


def validate_source_context(
    raw: object,
    *,
    target_type: str,
    target_id: str,
    content_id: str,
    provenance_key: str,
) -> dict[str, str] | None:
    """Require a separately persisted, exact and non-ambiguous source tuple."""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("DP418_COMPARISON_TARGET_BINDING_INVALID")
    if (
        raw.get("member_type") != target_type
        or raw.get("member_id") != target_id
        or raw.get("content_id") != content_id
        or raw.get("passage_id") != provenance_key
    ):
        raise ValueError("DP418_COMPARISON_TARGET_BINDING_INVALID")
    if any(not isinstance(raw.get(key), str) or not _REF.fullmatch(raw[key])
           for key in _KEYS[:5]):
        raise ValueError("STUDIO_REVIEW_UI_REFERENCE_INVALID")
    if not isinstance(raw.get("capture_sha256"), str) or not _SHA.fullmatch(
        raw["capture_sha256"]
    ):
        raise ValueError("STUDIO_REVIEW_UI_HASH_INVALID")
    if (
        raw.get("rights_status") not in _RIGHTS
        or raw.get("capture_status") not in _CAPTURE_STATES
        or raw.get("capture_hold_status") not in _CAPTURE_HOLDS
    ):
        raise ValueError("DP418_COMPARISON_TARGET_SOURCE_STATE_INVALID")
    return {key: str(raw[key]) for key in _KEYS}


__all__ = ["validate_source_context"]
