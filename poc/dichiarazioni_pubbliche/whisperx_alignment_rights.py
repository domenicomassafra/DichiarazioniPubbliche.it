"""DP-165: current DP-305 source-use authority for the private WhisperX lane.

An approvals flag on a job payload, a syntactically valid receipt ID or an
inert callback is never a rights grant for acoustic alignment of private media.
The independent DP-305 registry is the current rights authority, so the adapter
guard must re-read it around every inference boundary.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from dichiarazioni_pubbliche.private_capture_rights import (
    SourceFamilyUseGuard, SourceUseBlocked,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, PrivateRightsRegistryStore, RightsSubject,
)
from dichiarazioni_pubbliche.whisperx_alignment_private import AlignmentHold

# Word-time alignment of an already authorized private recording is the same
# private media use as local ASR: no publication, no new source, no derivative.
ALIGNMENT_SOURCE_USE = "ASR_MEDIA"

SCOPE_REQUIRED = "WHISPERX_ALIGNMENT_SOURCE_USE_SCOPE_REQUIRED"
READER_REQUIRED = "WHISPERX_ALIGNMENT_SOURCE_USE_READER_REQUIRED"
RECORD_MISSING = "WHISPERX_ALIGNMENT_SOURCE_USE_RECORD_MISSING"
RECEIPT_MISMATCH = "WHISPERX_ALIGNMENT_SOURCE_USE_RECEIPT_MISMATCH"
READ_UNAVAILABLE = "WHISPERX_ALIGNMENT_SOURCE_USE_READ_UNAVAILABLE"


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


@dataclass(frozen=True)
class AlignmentRightsScope:
    """Exact reviewed source-use subject for one private alignment."""

    subject: RightsSubject
    rights_record_id: str
    policy_version: str
    rights_receipt_ref: str


def read_alignment_rights_scope(
    *, store: PsqlRuntime, content_id: str, canonical_url: str,
    payload: Mapping[str, object],
) -> AlignmentRightsScope:
    """Resolve the reviewed DP-305 record a caller claims for this alignment."""
    record_id = _text(payload.get("rights_record_id"))
    policy_version = _text(payload.get("rights_policy_version"))
    receipt_id = _text(payload.get("rights_receipt_id"))
    if (not record_id or not policy_version or not receipt_id
            or not _text(content_id) or not _text(canonical_url)):
        raise AlignmentHold(SCOPE_REQUIRED)
    if not isinstance(store, PsqlRuntime):
        raise AlignmentHold(READER_REQUIRED)
    try:
        registry = PrivateRightsRegistryStore(
            database_url=store.database_url, psql=store.psql,
        )
        reviewed = registry.read_record(record_id)
    except Exception:
        raise AlignmentHold(READ_UNAVAILABLE) from None
    if not isinstance(reviewed, PrivateRightsRecord):
        raise AlignmentHold(RECORD_MISSING)
    if reviewed.rights_receipt_ref != receipt_id:
        raise AlignmentHold(RECEIPT_MISMATCH)
    subject = RightsSubject(
        source_family=reviewed.source_family, locator_kind="URL",
        locator_value=canonical_url, content_id=content_id,
    )
    return AlignmentRightsScope(
        subject=subject, rights_record_id=record_id,
        policy_version=policy_version, rights_receipt_ref=receipt_id,
    )


def alignment_authorization_guard(
    scope: AlignmentRightsScope, *,
    read_current: Callable[[RightsSubject], PrivateRightsRecord | None],
    clock: Callable[[], datetime] | None = None,
) -> Callable[[], None]:
    """Build the adapter guard that re-reads the current decision each time."""
    if not isinstance(scope, AlignmentRightsScope):
        raise AlignmentHold(SCOPE_REQUIRED)
    if not callable(read_current):
        raise AlignmentHold(READER_REQUIRED)
    try:
        guard = SourceFamilyUseGuard(
            read_current=read_current, subject=scope.subject,
            rights_record_id=scope.rights_record_id,
            policy_version=scope.policy_version, clock=clock,
        )
        guard.bind_capture(
            content_id=scope.subject.content_id or "",
            url=scope.subject.locator_value,
        )
    except SourceUseBlocked as exc:
        raise AlignmentHold(exc.code) from None
    except AlignmentHold:
        raise
    except Exception:
        raise AlignmentHold(READ_UNAVAILABLE) from None

    def require_current_rights() -> None:
        try:
            guard.require(ALIGNMENT_SOURCE_USE)
        except SourceUseBlocked as exc:
            raise AlignmentHold(exc.code) from None
        except Exception:
            raise AlignmentHold(READ_UNAVAILABLE) from None

    return require_current_rights


def registry_alignment_authorization_guard(
    scope: AlignmentRightsScope, *, store: PsqlRuntime,
    clock: Callable[[], datetime] | None = None,
) -> Callable[[], None]:
    """Production guard: every boundary re-reads the live DP-305 registry."""
    if not isinstance(store, PsqlRuntime):
        raise AlignmentHold(READER_REQUIRED)
    try:
        registry = PrivateRightsRegistryStore(
            database_url=store.database_url, psql=store.psql,
        )
    except Exception:
        raise AlignmentHold(READ_UNAVAILABLE) from None
    return alignment_authorization_guard(
        scope, read_current=registry.read_current, clock=clock,
    )


__all__ = [
    "ALIGNMENT_SOURCE_USE", "AlignmentRightsScope",
    "alignment_authorization_guard", "read_alignment_rights_scope",
    "registry_alignment_authorization_guard",
]
