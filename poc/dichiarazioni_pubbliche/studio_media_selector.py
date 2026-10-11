"""Metadata-only candidate→Passage→canonical media time-range inspector.

No transcript text, person identification, source URL, preview permission,
review decision, player control or publication authority is conferred.
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.corpus_repository import (
    CAPTURE_HOLD_STATUSES,
    CAPTURE_RETENTION_CLASSES,
    CAPTURE_STATUSES,
    STATEMENT_CANDIDATE_STATUSES,
)

MEDIA_SELECTOR_INSPECTION_VERSION = 'studio-media-selector-inspection-v1'
MEDIA_CAPTURE_CONTEXT_VERSION = 'studio-media-capture-context-v1'
_ID = re.compile(r'^[A-Za-z0-9_:/.-]{1,180}$')
_SHA = re.compile(r'^[0-9a-f]{64}$')
_SEGMENT_STATUSES = frozenset({
    'RESOLVED', 'CANDIDATE_DISAGREEMENT', 'TRANSCRIPT_UNCERTAIN',
})


class MediaSelectorStore(Protocol):
    def read_candidate_media_selector(
        self, *, content_id: str, statement_candidate_id: str, passage_id: str,
    ) -> dict[str, Any] | None: ...


class MediaCaptureContextStore(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


def _id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('STUDIO_MEDIA_ID_INVALID')
    return value


def inspect_candidate_media_selector(
    store: MediaSelectorStore,
    *,
    content_id: str,
    statement_candidate_id: str,
    passage_id: str,
) -> dict[str, object]:
    """Inspect an exact persisted chain, not an inferred timestamp or attribution."""
    content_id = _id(content_id)
    statement_candidate_id = _id(statement_candidate_id)
    passage_id = _id(passage_id)
    try:
        row = store.read_candidate_media_selector(
            content_id=content_id,
            statement_candidate_id=statement_candidate_id, passage_id=passage_id,
        )
    except Exception:
        raise RuntimeError('STUDIO_MEDIA_STORE_UNAVAILABLE') from None
    return _project_candidate_media(row, content_id, statement_candidate_id, passage_id)


def _project_candidate_media(
    row: object, content_id: str, statement_candidate_id: str, passage_id: str,
) -> dict[str, object]:
    if not isinstance(row, Mapping) or not row:
        raise RuntimeError('STUDIO_MEDIA_LINK_MISSING')
    if (
        row.get('statement_candidate_id') != statement_candidate_id
        or row.get('passage_id') != passage_id
        or any(row.get(key) != content_id for key in (
            'candidate_content_id', 'passage_content_id', 'segment_content_id',
        ))
        or row.get('passage_capture_id') is not None
        or row.get('selector_type') != 'MEDIA_SEGMENT_REF'
    ):
        raise ValueError('STUDIO_MEDIA_BINDING_INVALID')
    segment_id = _id(row.get('segment_id'))
    if row.get('passage_segment_id') != segment_id:
        raise ValueError('STUDIO_MEDIA_SEGMENT_BINDING_INVALID')
    digest = row.get('text_sha256')
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise ValueError('STUDIO_MEDIA_HASH_INVALID')
    candidate_state = row.get('candidate_status')
    transcript_state = row.get('transcript_status')
    if (not isinstance(candidate_state, str) or candidate_state not in STATEMENT_CANDIDATE_STATUSES
            or not isinstance(transcript_state, str) or transcript_state not in _SEGMENT_STATUSES
            or type(row.get('publication_blocked')) is not bool):
        raise ValueError('STUDIO_MEDIA_STATE_INVALID')
    index, start, end = (row.get(key) for key in ('segment_index', 'start_ms', 'end_ms'))
    if (type(index) is not int or index < 0 or type(start) is not int
            or type(end) is not int or start < 0 or end <= start):
        raise ValueError('STUDIO_MEDIA_TIME_RANGE_INVALID')
    return {
        'contract_version': MEDIA_SELECTOR_INSPECTION_VERSION,
        'private_only': True,
        'publication_authority': False,
        'rights_clearance': False,
        'attribution_authority': False,
        'content_id': content_id,
        'statement_candidate_id': statement_candidate_id,
        'passage_id': passage_id,
        'passage_text_sha256': digest,
        'candidate_status': candidate_state,
        'canonical_segment': {
            'id': segment_id,
            'segment_index': index,
            'start_ms': start,
            'end_ms': end,
            'transcript_status': transcript_state,
            'publication_blocked': row['publication_blocked'],
        },
    }


def inspect_candidate_media_capture_context(
    store: MediaCaptureContextStore,
    *,
    content_id: str,
    statement_candidate_id: str,
    passage_id: str,
    capture_id: str,
    capture_sha256: str,
) -> dict[str, object]:
    """Read one persisted PG snapshot of a media locator and a Capture version.

    The canonical media segment is Content-scoped, not Capture-scoped: current
    schema has no durable FK from this Segment to a Capture. A same-Content
    Capture is therefore *context* only; seeking remains held even if its
    stored rights status says CLEARED. No source URL, body or receipt is read.
    """
    content_id = _id(content_id)
    statement_candidate_id = _id(statement_candidate_id)
    passage_id = _id(passage_id)
    capture_id = _id(capture_id)
    if not isinstance(capture_sha256, str) or not _SHA.fullmatch(capture_sha256):
        raise ValueError('STUDIO_MEDIA_CAPTURE_HASH_INVALID')

    # One read-only SELECT enforces the exact persisted join and avoids
    # constructing a timeline from independent, potentially stale queries.
    sql = """
        SELECT json_build_object(
            'statement_candidate_id', candidate.id,
            'candidate_content_id', candidate.content_id,
            'candidate_status', candidate.status,
            'passage_id', passage.id,
            'passage_content_id', passage.content_id,
            'passage_capture_id', passage.capture_id,
            'selector_type', passage.selector_type,
            'text_sha256', passage.text_sha256,
            'passage_segment_id', passage.canonical_segment_id,
            'segment_id', segment.id,
            'segment_content_id', segment.content_id,
            'segment_index', segment.segment_index,
            'start_ms', segment.start_ms,
            'end_ms', segment.end_ms,
            'transcript_status', segment.transcript_status,
            'publication_blocked', segment.publication_blocked,
            'capture_id', capture.id,
            'capture_content_id', capture.content_id,
            'capture_sha256', capture.content_sha256,
            'capture_observed_at', capture.observed_at,
            'capture_status', capture.status,
            'capture_hold_status', capture.hold_status,
            'capture_retention_class', capture.retention_class,
            'capture_rights_status', capture.rights_status,
            'capture_has_body_ref', (capture.body_ref IS NOT NULL),
            'capture_has_purge_at', (capture.body_purged_at IS NOT NULL),
            'duration_ms', content.duration_ms
        )::text
        FROM content_capture AS capture
        JOIN content_item AS content ON content.id=capture.content_id
        JOIN statement_candidate AS candidate ON candidate.content_id=content.id
        JOIN statement_candidate_passage AS link
          ON link.statement_candidate_id=candidate.id
         AND link.content_id=candidate.content_id
        JOIN passage ON passage.id=link.passage_id AND passage.content_id=link.content_id
        JOIN canonical_transcript_segment AS segment
          ON segment.id=passage.canonical_segment_id
         AND segment.content_id=passage.content_id
        WHERE content.id=:'content_id'
          AND candidate.id=:'statement_candidate_id'
          AND passage.id=:'passage_id'
          AND passage.selector_type='MEDIA_SEGMENT_REF'
          AND passage.capture_id IS NULL
          AND capture.id=:'capture_id'
          AND capture.content_sha256=:'capture_sha256'
        LIMIT 1;
    """
    try:
        raw = store.run(
            sql, content_id=content_id, statement_candidate_id=statement_candidate_id,
            passage_id=passage_id, capture_id=capture_id,
            capture_sha256=capture_sha256,
        )
    except Exception:
        raise RuntimeError('STUDIO_MEDIA_CAPTURE_STORE_UNAVAILABLE') from None
    if not raw:
        raise RuntimeError('STUDIO_MEDIA_CAPTURE_CONTEXT_NOT_FOUND')
    try:
        row = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('STUDIO_MEDIA_CAPTURE_CONTEXT_INVALID') from None
    media = _project_candidate_media(row, content_id, statement_candidate_id, passage_id)
    if (
        not isinstance(row, Mapping)
        or row.get('capture_id') != capture_id
        or row.get('capture_content_id') != content_id
        or row.get('capture_sha256') != capture_sha256
    ):
        raise ValueError('STUDIO_MEDIA_CAPTURE_BINDING_INVALID')
    captured_at = row.get('capture_observed_at')
    try:
        captured_time = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
        if captured_time.tzinfo is None or captured_time.utcoffset() is None:
            raise ValueError('naive')
    except (AttributeError, TypeError, ValueError):
        raise ValueError('STUDIO_MEDIA_CAPTURE_TIMESTAMP_INVALID') from None
    if (
        not isinstance(row.get('capture_status'), str)
        or row['capture_status'] not in CAPTURE_STATUSES
        or not isinstance(row.get('capture_hold_status'), str)
        or row['capture_hold_status'] not in CAPTURE_HOLD_STATUSES
        or not isinstance(row.get('capture_retention_class'), str)
        or row['capture_retention_class'] not in CAPTURE_RETENTION_CLASSES
        or not isinstance(row.get('capture_rights_status'), str)
        or row['capture_rights_status'] not in {
            'UNKNOWN', 'CLEARED', 'DENIED', 'REVOKED', 'EXPIRED', 'REVIEW_REQUIRED',
        }
        or type(row.get('capture_has_body_ref')) is not bool
        or type(row.get('capture_has_purge_at')) is not bool
    ):
        raise ValueError('STUDIO_MEDIA_CAPTURE_POLICY_INVALID')
    if (
        row['capture_status'] == 'PURGED_BODY'
        and (row['capture_has_body_ref'] or not row['capture_has_purge_at'])
    ) or (row['capture_status'] != 'PURGED_BODY' and row['capture_has_purge_at']):
        raise ValueError('STUDIO_MEDIA_CAPTURE_PURGE_INVALID')
    duration = row.get('duration_ms')
    if duration is not None and (
        type(duration) is not int or duration < 0
        or media['canonical_segment']['end_ms'] > duration
    ):
        raise ValueError('STUDIO_MEDIA_DURATION_RANGE_INVALID')

    reasons = ['STUDIO_MEDIA_CAPTURE_SEGMENT_BINDING_UNPROVEN',
               'STUDIO_MEDIA_INDEPENDENT_RIGHTS_CHECK_REQUIRED']
    if media['canonical_segment']['transcript_status'] != 'RESOLVED':
        reasons.append('STUDIO_MEDIA_TRANSCRIPT_UNRESOLVED')
    if media['canonical_segment']['publication_blocked']:
        reasons.append('STUDIO_MEDIA_SEGMENT_PUBLICATION_BLOCKED')
    if media['candidate_status'] != 'APPROVED':
        reasons.append('STUDIO_MEDIA_CANDIDATE_NOT_APPROVED')
    if duration is None:
        reasons.append('STUDIO_MEDIA_DURATION_UNKNOWN')
    if row['capture_rights_status'] != 'CLEARED':
        reasons.append('STUDIO_MEDIA_CAPTURE_RIGHTS_UNCLEARED')
    if row['capture_retention_class'] == 'POLICY_PENDING':
        reasons.append('STUDIO_MEDIA_RETENTION_POLICY_PENDING')
    if row['capture_hold_status'] != 'NONE':
        reasons.append('STUDIO_MEDIA_CAPTURE_ON_HOLD')
    if row['capture_status'] == 'PURGED_BODY':
        reasons.append('STUDIO_MEDIA_CAPTURE_PURGED')
    elif row['capture_status'] != 'CAPTURED' or not row['capture_has_body_ref']:
        reasons.append('STUDIO_MEDIA_CAPTURE_BODY_UNAVAILABLE')
    return {
        **media,
        'contract_version': MEDIA_CAPTURE_CONTEXT_VERSION,
        'duration_ms': duration,
        'capture': {
            'id': capture_id,
            'content_sha256': capture_sha256,
            'observed_at': captured_at,
            'retention_class': row['capture_retention_class'],
            'hold_status': row['capture_hold_status'],
            'rights_status': row['capture_rights_status'],
            'status': row['capture_status'],
            'body_state': (
                'PURGED' if row['capture_status'] == 'PURGED_BODY'
                else 'STORED_UNVERIFIED' if row['capture_has_body_ref']
                else 'NOT_STORED'
            ),
        },
        'capture_segment_binding': 'UNPROVEN',
        'seek_authorized': False,
        'hold_reasons': reasons,
    }


__all__ = [
    'MEDIA_SELECTOR_INSPECTION_VERSION', 'MEDIA_CAPTURE_CONTEXT_VERSION',
    'MediaSelectorStore', 'MediaCaptureContextStore',
    'inspect_candidate_media_selector', 'inspect_candidate_media_capture_context',
]
