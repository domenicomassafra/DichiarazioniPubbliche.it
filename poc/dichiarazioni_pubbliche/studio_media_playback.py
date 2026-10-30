"""DP-419: authenticate immutable Capture bytes, source rights, and media interval.

This reader deliberately exposes no source URL, registry receipt or credentials.
Its permission to play is private and per-request, never publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.capture_http_validation import CapturePipelineError
from dichiarazioni_pubbliche.media_capture_proof import derive_media_capture_segment
from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.rights_registry import RightsSubject

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MEDIA_TYPES = {"audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a"}
_RIGHTS_USES = ("FETCH", "STORE_BODY", "ASR_MEDIA", "PLAYBACK")

_BINDING_SQL = """
SELECT inspect_media_capture_segment_binding(:'binding_id')::text;
"""
_MEDIA_SQL = """
SELECT json_build_object(
  'binding_id', b.id,
  'content_id', b.content_id,
  'capture_id', b.capture_id,
  'capture_sha256', b.capture_sha256,
  'canonical_segment_id', b.canonical_segment_id,
  'canonical_text_sha256', b.canonical_text_sha256,
  'start_ms', b.start_ms, 'end_ms', b.end_ms,
  'evidence_sha256', b.evidence_sha256,
  'body_ref', cap.body_ref,
  'final_url', cap.final_url,
  'media_type', cap.media_type,
  'capture_rights', cap.rights_status,
  'source_rights', content.rights_status,
  'has_approved_passage', EXISTS (
    SELECT 1 FROM passage p
    JOIN statement_candidate_passage link
      ON link.passage_id=p.id AND link.content_id=p.content_id
    JOIN statement_candidate candidate
      ON candidate.id=link.statement_candidate_id
     AND candidate.content_id=link.content_id
    WHERE p.content_id=b.content_id
      AND p.canonical_segment_id=b.canonical_segment_id
      AND p.selector_type='MEDIA_SEGMENT_REF'
      AND p.capture_id IS NULL
      AND candidate.status='APPROVED'
  )
)::text
FROM media_capture_segment_binding b
JOIN content_capture cap
  ON cap.id=b.capture_id AND cap.content_id=b.content_id
JOIN content_item content ON content.id=b.content_id
WHERE b.id=:'binding_id';
"""
_RIGHTS_SQL = """
SELECT coalesce(json_agg(rights ORDER BY rights.id), '[]'::json)::text
FROM (
 SELECT record.id,record.source_family,record.policy_version
 FROM private_source_rights_record record
 WHERE record.content_id=:'content_id'
   AND record.locator_kind='URL'
   AND record.locator_value=:'final_url'
   AND record.canonical_segment_id IS NULL
   AND record.transcript_segment_id IS NULL
   AND record.passage_id IS NULL AND record.evidence_id IS NULL
   AND NOT EXISTS (
      SELECT 1 FROM private_source_rights_record child
      WHERE child.supersedes_id=record.id
   )
 LIMIT 2
) rights;
"""


@dataclass(frozen=True)
class VerifiedMedia:
    body: bytes
    start_ms: int
    end_ms: int
    media_type: str


def _decode(raw: object, expected_type: type) -> Any:
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        decoded = None
    if type(decoded) is not expected_type:
        raise ValueError("MEDIA_PLAYBACK_DATA_INVALID")
    return decoded


def _assert_binding(capture_reader: Any, binding_id: str) -> dict[str, object]:
    state = _decode(capture_reader.run(_BINDING_SQL, binding_id=binding_id), dict)
    if (
        state.get("binding_id") != binding_id
        or state.get("binding_state") != "ATTESTED"
        or state.get("hold_reasons") != ["RIGHTS_NOT_INDEPENDENTLY_APPROVED"]
        or not isinstance(state.get("capture_sha256"), str)
        or not _SHA.fullmatch(state["capture_sha256"])
    ):
        raise ValueError("MEDIA_PLAYBACK_BINDING_HELD")
    return state


def _assert_rights(capture_reader: Any, rights_reader: Any, row: dict[str, object]) -> None:
    candidates = _decode(capture_reader.run(
        _RIGHTS_SQL, content_id=row["content_id"], final_url=row["final_url"],
    ), list)
    if len(candidates) != 1 or type(candidates[0]) is not dict:
        raise ValueError("MEDIA_PLAYBACK_RIGHTS_MISSING")
    match = candidates[0]
    if not all(
        isinstance(match.get(key), str) and match[key]
        for key in ("id", "source_family", "policy_version")
    ):
        raise ValueError("MEDIA_PLAYBACK_RIGHTS_INVALID")
    subject = RightsSubject(
        source_family=match["source_family"], locator_kind="URL",
        locator_value=row["final_url"], content_id=row["content_id"],
    )
    current = rights_reader.read_current(subject)
    timestamp = datetime.now(timezone.utc)
    for use in _RIGHTS_USES:
        decision = evaluate_source_use(
            current, subject=subject, rights_record_id=match["id"],
            policy_version=match["policy_version"], use=use, now=timestamp,
        )
        if not decision.permitted:
            raise ValueError("MEDIA_PLAYBACK_RIGHTS_HELD")


def verified_media_playback(
    *, capture_reader: Any, rights_reader: Any, body_store: Any, binding_id: str,
) -> VerifiedMedia:
    """Return only read-back verified authorized bytes for a loopback bearer client."""
    if not isinstance(binding_id, str) or not _REF.fullmatch(binding_id):
        raise ValueError("MEDIA_PLAYBACK_ID_INVALID")
    original_state = _assert_binding(capture_reader, binding_id)
    row = _decode(capture_reader.run(_MEDIA_SQL, binding_id=binding_id), dict)
    for key in ("content_id", "capture_id", "canonical_segment_id"):
        if not isinstance(row.get(key), str) or not _REF.fullmatch(row[key]):
            raise ValueError("MEDIA_PLAYBACK_ID_INVALID")
    for key in ("capture_sha256", "canonical_text_sha256", "evidence_sha256"):
        if not isinstance(row.get(key), str) or not _SHA.fullmatch(row[key]):
            raise ValueError("MEDIA_PLAYBACK_HASH_INVALID")
    if (
        row.get("binding_id") != binding_id
        or row["capture_sha256"] != original_state["capture_sha256"]
        or (type(row.get("start_ms")) is not int or type(row.get("end_ms")) is not int)
        or row["start_ms"] < 0 or row["end_ms"] <= row["start_ms"]
        or row.get("capture_rights") != "CLEARED"
        or row.get("source_rights") != "CLEARED"
        or row.get("has_approved_passage") is not True
        or not isinstance(row.get("final_url"), str)
        or not row["final_url"].startswith("https://")
        or not isinstance(row.get("body_ref"), str)
        or not row["body_ref"]
        or row.get("media_type") not in _MEDIA_TYPES
    ):
        raise ValueError("MEDIA_PLAYBACK_SOURCE_HELD")
    _assert_rights(capture_reader, rights_reader, row)
    try:
        body = body_store.read(
            row["body_ref"], expected_sha256=row["capture_sha256"],
            max_bytes=64 * 1024 * 1024,
        )
    except (CapturePipelineError, OSError):
        raise ValueError("MEDIA_PLAYBACK_BODY_UNAVAILABLE") from None
    with tempfile.TemporaryDirectory(prefix="dp419-decode-") as temp:
        source = Path(temp) / ("media" + _MEDIA_TYPES[row["media_type"]])
        source.write_bytes(body)
        proof = derive_media_capture_segment(
            media_path=source, capture_sha256=row["capture_sha256"],
            content_id=row["content_id"], capture_id=row["capture_id"],
            canonical_segment_id=row["canonical_segment_id"],
            canonical_text_sha256=row["canonical_text_sha256"],
            start_ms=row["start_ms"], end_ms=row["end_ms"],
        )
    if proof["evidence_sha256"] != row["evidence_sha256"]:
        raise ValueError("MEDIA_PLAYBACK_DERIVATION_MISMATCH")
    # Late mutation of binding or CURRENT rights cannot reuse earlier clearance.
    if (_assert_binding(capture_reader, binding_id) != original_state
            or _decode(capture_reader.run(_MEDIA_SQL, binding_id=binding_id), dict) != row):
        raise ValueError("MEDIA_PLAYBACK_SOURCE_CHANGED")
    _assert_rights(capture_reader, rights_reader, row)
    return VerifiedMedia(
        body=body, start_ms=row["start_ms"], end_ms=row["end_ms"],
        media_type=row["media_type"],
    )
