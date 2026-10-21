"""#169: exact, current rights guard for private YouTube caption acquisition.

Reuses the versioned rights registry and DP-236 guard; no implied YouTube consent.
"""
from __future__ import annotations

from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject


def caption_source_guard(store: QueueRuntimeStore, *, content_id: str, url: str) -> SourceFamilyUseGuard:
    """Bind an *exact video URL and content* to the current reviewed rights receipt."""
    if (not isinstance(store, QueueRuntimeStore)
            or not isinstance(content_id, str) or not content_id
            or not isinstance(url, str) or not url.startswith("https://")):
        raise SourceUseBlocked("SOURCE_USE_CAPTION_CONTEXT_INVALID")
    subject = RightsSubject(
        source_family="YOUTUBE", locator_kind="URL", locator_value=url, content_id=content_id,
    )
    # Use the production queue's own database endpoint. A caller-supplied job
    # payload can never set an entitlement, record id, reviewer, or policy.
    registry = PrivateRightsRegistryStore(database_url=store.database_url, psql=store.psql)
    try:
        current = registry.read_current(subject)
    except Exception:
        raise SourceUseBlocked("SOURCE_USE_READ_UNAVAILABLE") from None
    if current is None:
        raise SourceUseBlocked("SOURCE_USE_RECORD_MISSING")
    guard = SourceFamilyUseGuard(
        read_current=registry.read_current, subject=subject,
        rights_record_id=current.id, policy_version=current.policy_version,
    )
    guard.bind_capture(content_id=content_id, url=url)
    guard.bind_fetched(final_url=url)
    return guard


__all__ = ["caption_source_guard"]
