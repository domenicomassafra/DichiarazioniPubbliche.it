"""Current, exact source-use admission for the private faster-whisper lane.

A queue payload's approval flag or opaque receipt ID is never a rights grant.
The existing independent DP-305 registry is the current rights authority.
"""

from __future__ import annotations

from collections.abc import Mapping

from dichiarazioni_pubbliche.private_capture_rights import (
    SourceFamilyUseGuard, SourceUseBlocked,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.remote_asr import AsrRequestRejected
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, PrivateRightsRegistryStore, RightsSubject,
)


def require_faster_whisper_media_rights(
    *, store: PsqlRuntime, content_id: str, canonical_url: str,
    payload: Mapping[str, object],
) -> None:
    """Re-read a currently reviewed URL/Content right for each ASR boundary."""
    record_id = payload.get("rights_record_id")
    policy_version = payload.get("rights_policy_version")
    receipt_id = payload.get("rights_receipt_id")
    if (not isinstance(record_id, str) or not record_id.strip()
            or not isinstance(policy_version, str) or not policy_version.strip()
            or not isinstance(receipt_id, str) or not receipt_id.strip()
            or not isinstance(content_id, str) or not content_id
            or not isinstance(canonical_url, str) or not canonical_url):
        raise AsrRequestRejected("FASTER_WHISPER_SOURCE_USE_SCOPE_REQUIRED")
    if not isinstance(store, PsqlRuntime):
        raise AsrRequestRejected("FASTER_WHISPER_SOURCE_USE_READER_REQUIRED")
    try:
        registry = PrivateRightsRegistryStore(
            database_url=store.database_url, psql=store.psql,
        )
        reviewed = registry.read_record(record_id)
        if not isinstance(reviewed, PrivateRightsRecord):
            raise AsrRequestRejected("FASTER_WHISPER_SOURCE_USE_RECORD_MISSING")
        subject = RightsSubject(
            source_family=reviewed.source_family, locator_kind="URL",
            locator_value=canonical_url, content_id=content_id,
        )
        guard = SourceFamilyUseGuard(
            read_current=registry.read_current, subject=subject,
            rights_record_id=record_id, policy_version=policy_version,
        )
        guard.bind_capture(content_id=content_id, url=canonical_url)
        guard.require("ASR_MEDIA")
        if reviewed.rights_receipt_ref != receipt_id:
            raise AsrRequestRejected("FASTER_WHISPER_SOURCE_USE_RECEIPT_MISMATCH")
    except AsrRequestRejected:
        raise
    except SourceUseBlocked as exc:
        raise AsrRequestRejected(exc.code) from None
    except Exception:
        # Never expose connection details, source labels or registry failures.
        raise AsrRequestRejected("FASTER_WHISPER_SOURCE_USE_READ_UNAVAILABLE") from None


__all__ = ["require_faster_whisper_media_rights"]
