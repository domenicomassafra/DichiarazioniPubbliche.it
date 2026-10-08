"""Allowlisted metadata-only private Discovery provenance and blocker presentation."""

from __future__ import annotations

import re
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_STATE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_FAMILY = re.compile(r"^[A-Za-z0-9_:-]{1,128}$")
_DISPOSITIONS = frozenset({
    "NEW_CONTENT", "EXISTING_CONTENT", "DUPLICATE_WITHIN_RUN",
    "HOST_LIMIT", "RESULT_LIMIT", "OUTSIDE_DATE_WINDOW",
    "REJECTED_POLICY", "AMBIGUOUS_CONTENT_IDENTITY",
})


def _id(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_DISCOVERY_DETAIL_ID_INVALID")
    return value


def _state(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _STATE.fullmatch(value):
        raise ValueError("STUDIO_DISCOVERY_DETAIL_STATE_INVALID")
    return value


def present_discovery_detail(row: dict[str, Any]) -> dict[str, object]:
    """Do not copy caller-controlled DB metadata into the private API response."""
    if not isinstance(row, dict):
        raise ValueError("STUDIO_DISCOVERY_DETAIL_ROW_INVALID")
    path = {key: _id(row.get(key), optional=(key == "attempt_id"))
            for key in ("id", "run_id", "attempt_id", "query_id",
                        "manifest_id", "collection_id")}
    disposition = row.get("disposition")
    if disposition not in _DISPOSITIONS:
        raise ValueError("STUDIO_DISCOVERY_DETAIL_DISPOSITION_INVALID")
    family = row.get("source_family")
    if not isinstance(family, str) or not _FAMILY.fullmatch(family):
        raise ValueError("STUDIO_DISCOVERY_DETAIL_FAMILY_INVALID")
    content_id = _id(row.get("content_id"), optional=True)
    reason = _state(row.get("reason_code"), optional=True)
    statuses = {
        key: _state(row.get(key), optional=key in (
            "attempt_status", "membership_status", "content_rights_status"))
        for key in ("collection_status", "manifest_status", "run_status",
                    "attempt_status", "membership_status", "content_rights_status")
    }
    flags = ("lineage_ok", "manifest_digest_ok", "family_ok",
             "adapter_ok", "url_ok", "capture_authorized")
    if any(type(row.get(flag)) is not bool for flag in flags):
        raise ValueError("STUDIO_DISCOVERY_DETAIL_FLAGS_INVALID")
    checks = (
        (statuses["collection_status"] != "ACTIVE", "COLLECTION_NOT_ACTIVE", "REVIEW_COLLECTION_STATE"),
        (statuses["manifest_status"] != "ACTIVE", "MANIFEST_NOT_ACTIVE", "REVIEW_MANIFEST_STATUS"),
        (statuses["run_status"] not in {"COMPLETED", "PARTIAL"}, "DISCOVERY_RUN_NOT_COMPLETE", "COMPLETE_OR_RETRY_RUN"),
        (statuses["attempt_status"] != "HEALTHY", "DISCOVERY_ATTEMPT_NOT_HEALTHY", "RETRY_OR_REVIEW_ATTEMPT"),
        (not row["lineage_ok"], "DISCOVERY_LINEAGE_MISMATCH", "REPLAY_VALID_DISCOVERY_LINEAGE"),
        (not row["manifest_digest_ok"], "DISCOVERY_MANIFEST_DIGEST_MISMATCH", "REPLAY_CURRENT_MANIFEST"),
        (not row["family_ok"], "DISCOVERY_FAMILY_NOT_ALLOWED", "REVIEW_SOURCE_FAMILY_SCOPE"),
        (not row["adapter_ok"], "DISCOVERY_ADAPTER_NOT_ALLOWED", "REVIEW_ADAPTER_SCOPE"),
        (disposition not in {"NEW_CONTENT", "EXISTING_CONTENT"}, "DISCOVERY_DISPOSITION_REJECTED", "REVIEW_OR_RERUN_DISCOVERY"),
        (content_id is None, "DISCOVERY_CONTENT_UNRESOLVED", "RESOLVE_CONTENT_IDENTITY"),
        (not row["url_ok"], "DISCOVERY_URL_BINDING_MISMATCH", "REVIEW_CONTENT_IDENTITY"),
        (statuses["membership_status"] != "INCLUDED", "DISCOVERY_MEMBERSHIP_NOT_INCLUDED", "REVIEW_COLLECTION_MEMBERSHIP"),
        (not row["capture_authorized"], "DISCOVERY_CAPTURE_NOT_AUTHORIZED", "REVIEW_CAPTURE_AUTHORITY"),
        (statuses["content_rights_status"] != "CLEARED", "DISCOVERY_CONTENT_RIGHTS_UNCLEARED", "REVIEW_CONTENT_RIGHTS"),
    )
    lineage_blockers = [(code, unblock) for flagged, code, unblock in checks if flagged]
    # These decisions require separate current, durable review/rights authority.
    # A healthy Discovery hit and a Content.CLEARED status are NOT such proof.
    blockers = lineage_blockers + [
        ("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", "VERIFY_CURRENT_PRIVATE_SOURCE_RIGHTS_RECORD"),
        ("DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE", "OBTAIN_DURABLE_TRIAGE_REVIEW_AUTHORITY"),
    ]
    return {
        "contract_version": "studio-operator-queues-v1",
        "private_only": True, "read_only": True,
        "publication_authority": False, "triage_action_authorized": False,
        "capture_authorized": False,
        "provenance_path": path,
        "content_id": content_id, "source_family": family,
        "disposition": disposition, "reason_code": reason,
        "statuses": statuses,
        "lineage_blockers": [code for code, _ in lineage_blockers],
        "lineage_checks_passed": not bool(lineage_blockers),
        "blockers": [code for code, _ in blockers],
        "unblock_conditions": [
            {"blocker": code, "condition": unblock} for code, unblock in blockers
        ],
    }
