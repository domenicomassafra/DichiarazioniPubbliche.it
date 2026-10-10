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
    PASSAGE_SELECTOR_TYPES,
)

CAPTURE_INSPECTION_VERSION = "studio-capture-inspection-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")


class CaptureLookup(Protocol):
    def find_capture(self, content_id: str, content_sha256: str) -> dict[str, Any] | None: ...
    def list_passage_selectors(self, capture_id: str, *, limit: int, after_id: str | None) -> list[dict[str, Any]]: ...


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
    observed_at: str
    content_sha256: str
    capture_state: str
    hold_state: str
    archive_state: str
    body_state: str
    archive_receipt_recorded: bool
    purge_receipt_recorded: bool
    body_purged_at: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "observed_at": self.observed_at,
            "content_sha256": self.content_sha256,
            "capture_state": self.capture_state,
            "hold_state": self.hold_state,
            "archive_state": self.archive_state,
            "body_state": self.body_state,
            "archive_receipt_recorded": self.archive_receipt_recorded,
            "purge_receipt_recorded": self.purge_receipt_recorded,
            "body_purged_at": self.body_purged_at,
        }


def _select_metadata(raw: Mapping[str, Any], content_id: str, expected_hash: str) -> CaptureInspection:
    if raw.get("content_id") != content_id or raw.get("content_sha256") != expected_hash:
        raise ValueError("STUDIO_CAPTURE_BINDING_MISMATCH")
    if not _has_aware_time(raw.get("observed_at")):
        raise ValueError("STUDIO_CAPTURE_OBSERVED_AT_INVALID")
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
    if archive_state in {"SUCCEEDED", "FAILED"} and (
        datetime.fromisoformat(raw["archive_completed_at"].replace("Z", "+00:00"))
        < datetime.fromisoformat(raw["archive_requested_at"].replace("Z", "+00:00"))
    ):
        # The persisted request and completion transitions each use now().
        # A reversed chronology is not proof of an archived Capture.
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
        observed_at=raw["observed_at"],
        content_sha256=expected_hash,
        capture_state=capture_state,
        hold_state=hold_state,
        archive_state=archive_state,
        body_state=body_state,
        archive_receipt_recorded=(archive_state in {"SUCCEEDED", "FAILED"}
                                  and _has_receipt(raw.get("archive_receipt"))),
        purge_receipt_recorded=(capture_state == "PURGED_BODY"
                                and _has_receipt(raw.get("purge_receipt"))),
        body_purged_at=raw.get("body_purged_at") if capture_state == "PURGED_BODY" else None,
    )


def inspect_capture_versions(
    store: CaptureLookup,
    *,
    content_id: str,
    earlier_hash: str,
    later_hash: str,
    include_selector_diff: bool = False,
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
    # Hashes are caller-supplied. A displayed "earlier" / "later" timeline
    # must be backed by persisted observation instants, not input field names.
    if (datetime.fromisoformat(earlier.observed_at.replace("Z", "+00:00"))
            >= datetime.fromisoformat(later.observed_at.replace("Z", "+00:00"))):
        raise ValueError("STUDIO_CAPTURE_VERSION_ORDER_INVALID")
    result: dict[str, object] = {
        "contract_version": CAPTURE_INSPECTION_VERSION,
        "private_only": True,
        "publication_authority": False,
        "rights_clearance": False,
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
    if include_selector_diff:
        result["selector_comparison"] = _compare_capture_selectors(
            store, content_id=content_id,
            earlier_capture_id=earlier.id, later_capture_id=later.id,
        )
    return result


def _selector(raw: Mapping[str, Any], *, content_id: str, capture_id: str) -> dict[str, Any]:
    if (raw.get("content_id") != content_id or raw.get("capture_id") != capture_id
            or raw.get("canonical_segment_id") is not None):
        raise ValueError("STUDIO_CAPTURE_PASSAGE_BINDING_INVALID")
    kind = raw.get("selector_type")
    if not isinstance(kind, str) or kind not in PASSAGE_SELECTOR_TYPES or kind == "MEDIA_SEGMENT_REF":
        # Media segments refer to logical Content, not one capture version.
        raise ValueError("STUDIO_CAPTURE_PASSAGE_SELECTOR_INVALID")
    digest = raw.get("text_sha256")
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise ValueError("STUDIO_CAPTURE_PASSAGE_HASH_INVALID")
    coords = ("start_char", "end_char") if kind == "TEXT_POSITION" else ("page_start", "page_end")
    other = ("page_start", "page_end") if kind == "TEXT_POSITION" else ("start_char", "end_char")
    first, last = (raw.get(coord) for coord in coords)
    if (type(first) is not int or type(last) is not int
            or first < (0 if kind == "TEXT_POSITION" else 1)
            or (last <= first if kind == "TEXT_POSITION" else last < first)):
        raise ValueError("STUDIO_CAPTURE_PASSAGE_RANGE_INVALID")
    if any(raw.get(coord) is not None for coord in other):
        raise ValueError("STUDIO_CAPTURE_PASSAGE_EXTRA_RANGE_INVALID")
    return {
        "id": _safe_id(raw.get("id")),
        "selector_type": kind,
        "text_sha256": digest,
        coords[0]: first,
        coords[1]: last,
    }


def _compare_capture_selectors(
    store: CaptureLookup, *, content_id: str,
    earlier_capture_id: str, later_capture_id: str,
) -> dict[str, object]:
    """Compare at most 20 persisted written passage anchors per Capture.

    A passage ID belongs to a Capture version, not a stable cross-version
    identity. Only selector coordinates identify the comparison anchor; hashes
    express changed wording without returning the wording. Never infer a
    missing/added Passage from a truncated page.
    """
    maximum = 20

    def read(capture_id: str) -> tuple[dict[tuple[object, ...], dict[str, Any]], bool]:
        try:
            rows = store.list_passage_selectors(capture_id, limit=maximum, after_id=None)
        except Exception:
            raise RuntimeError("STUDIO_CAPTURE_STORE_UNAVAILABLE") from None
        if not isinstance(rows, list) or len(rows) > maximum + 1:
            raise ValueError("STUDIO_CAPTURE_SELECTOR_PAGE_INVALID")
        found: dict[tuple[object, ...], dict[str, Any]] = {}
        previous = ""
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise ValueError("STUDIO_CAPTURE_SELECTOR_ROW_INVALID")
            item = _selector(raw, content_id=content_id, capture_id=capture_id)
            if item["id"] <= previous:
                raise ValueError("STUDIO_CAPTURE_SELECTOR_CURSOR_INVALID")
            previous = item["id"]
            anchor = (
                item["selector_type"], item.get("start_char"), item.get("end_char"),
                item.get("page_start"), item.get("page_end"),
            )
            if anchor in found:
                raise ValueError("STUDIO_CAPTURE_SELECTOR_ANCHOR_DUPLICATE")
            found[anchor] = item
        return found, len(rows) > maximum

    earlier, earlier_truncated = read(earlier_capture_id)
    later, later_truncated = read(later_capture_id)
    if earlier_truncated or later_truncated:
        return {
            "status": "TRUNCATED", "complete": False,
            "max_per_version": maximum,
            "earlier_truncated": earlier_truncated,
            "later_truncated": later_truncated,
            "reason_code": "CAPTURE_SELECTOR_COMPARISON_TRUNCATED",
            "unblock_condition": "INSPECT_CAPTURE_PAGINATED_SELECTORS",
            "changes": [],
        }

    counts = {kind: 0 for kind in ("UNCHANGED", "CHANGED", "REMOVED", "ADDED")}
    changes: list[dict[str, object]] = []
    for anchor in sorted(earlier.keys() | later.keys()):
        before, after = earlier.get(anchor), later.get(anchor)
        kind = (
            "ADDED" if before is None else
            "REMOVED" if after is None else
            "UNCHANGED" if before["text_sha256"] == after["text_sha256"] else
            "CHANGED"
        )
        counts[kind] += 1
        changes.append({
            "selector_type": anchor[0],
            "start_char": anchor[1], "end_char": anchor[2],
            "page_start": anchor[3], "page_end": anchor[4],
            "earlier_passage_id": before["id"] if before else None,
            "later_passage_id": after["id"] if after else None,
            "earlier_text_sha256": before["text_sha256"] if before else None,
            "later_text_sha256": after["text_sha256"] if after else None,
            "change": kind,
        })
    return {
        "status": "COMPLETE", "complete": True, "max_per_version": maximum,
        "counts": counts, "changes": changes,
    }


def inspect_capture_passage_selectors(
    store: CaptureLookup,
    *,
    content_id: str,
    capture_hash: str,
    limit: int = 20,
    after_id: str | None = None,
) -> dict[str, object]:
    """Bounded, capture-version-exact selector metadata; never a source preview."""
    content_id = _safe_id(content_id)
    if not isinstance(capture_hash, str) or not _SHA.fullmatch(capture_hash):
        raise ValueError("STUDIO_CAPTURE_HASH_INVALID")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("STUDIO_CAPTURE_PASSAGE_LIMIT_INVALID")
    if after_id is not None:
        after_id = _safe_id(after_id)
    try:
        raw_capture = store.find_capture(content_id, capture_hash)
    except Exception:
        raise RuntimeError("STUDIO_CAPTURE_STORE_UNAVAILABLE") from None
    if not isinstance(raw_capture, Mapping):
        raise RuntimeError("STUDIO_CAPTURE_VERSION_MISSING")
    capture = _select_metadata(raw_capture, content_id, capture_hash)
    try:
        rows = store.list_passage_selectors(capture.id, limit=limit, after_id=after_id)
    except Exception:
        raise RuntimeError("STUDIO_CAPTURE_STORE_UNAVAILABLE") from None
    if not isinstance(rows, list) or len(rows) > limit + 1:
        raise ValueError("STUDIO_CAPTURE_PASSAGE_PAGE_INVALID")
    previous = after_id or ""
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("STUDIO_CAPTURE_PASSAGE_ROW_INVALID")
        pid = _safe_id(raw.get("id"))
        if pid <= previous:
            raise ValueError("STUDIO_CAPTURE_PASSAGE_CURSOR_INVALID")
        previous = pid
    shown = [_selector(row, content_id=content_id, capture_id=capture.id)
             for row in rows[:limit]]
    has_more = len(rows) > limit
    return {
        "contract_version": CAPTURE_INSPECTION_VERSION,
        "private_only": True,
        "publication_authority": False,
        "rights_clearance": False,
        "content_id": content_id,
        "capture": capture.to_dict(),
        "selectors": shown,
        "has_more": has_more,
        "next_after_id": shown[-1]["id"] if has_more else None,
    }


__all__ = [
    "CAPTURE_INSPECTION_VERSION", "CaptureInspection", "CaptureLookup",
    "inspect_capture_versions", "inspect_capture_passage_selectors",
]
