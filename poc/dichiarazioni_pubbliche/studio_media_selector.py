"""Metadata-only candidate→Passage→canonical media time-range inspector.

No transcript text, person identification, source URL, preview permission,
review decision, player control or publication authority is conferred.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.corpus_repository import STATEMENT_CANDIDATE_STATUSES

MEDIA_SELECTOR_INSPECTION_VERSION = 'studio-media-selector-inspection-v1'
_ID = re.compile(r'^[A-Za-z0-9_:/.-]{1,180}$')
_SHA = re.compile(r'^[0-9a-f]{64}$')
_SEGMENT_STATUSES = frozenset({
    'RESOLVED', 'CANDIDATE_DISAGREEMENT', 'TRANSCRIPT_UNCERTAIN',
})


class MediaSelectorStore(Protocol):
    def read_candidate_media_selector(
        self, *, content_id: str, statement_candidate_id: str, passage_id: str,
    ) -> dict[str, Any] | None: ...


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


__all__ = ['MEDIA_SELECTOR_INSPECTION_VERSION', 'MediaSelectorStore', 'inspect_candidate_media_selector']
