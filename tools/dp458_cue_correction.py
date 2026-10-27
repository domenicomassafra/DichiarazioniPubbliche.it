"""DP-458 private cue correction, atomic timing repair and pinned VTT evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CAPTION_NAME = "I-293056_INT-SUBTITLE.vtt"


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError("DP458_" + reason)


def pinned_caption(root: Path, *, expected_sha: str, expected_start: int,
                   expected_end: int, exact_quote: str) -> None:
    """Check the actual original VTT bytes, not only its recorded metadata."""
    asset = root / CAPTION_NAME
    _require(asset.is_file() and not asset.is_symlink(), "VTT_SNAPSHOT_MISSING")
    body = asset.read_bytes()
    _require(len(body) <= 100_000 and hashlib.sha256(body).hexdigest() == expected_sha,
             "VTT_VERSION_CHANGED")
    source = body.decode("utf-8-sig")
    cue = re.search(
        r"(?m)^12\r?\n(\d\d:\d\d:\d\d\.\d{3}) --> "
        r"(\d\d:\d\d:\d\d\.\d{3})\r?\n([^\r\n]+)(?:\r?\n|$)", source
    )
    _require(cue is not None, "VTT_CUE_NOT_FOUND")
    def millis(stamp: str) -> int:
        h, m, s = stamp.split(":")
        sec, ms = s.split(".")
        return (int(h) * 3600 + int(m) * 60 + int(sec)) * 1000 + int(ms)
    _require(
        millis(cue.group(1)) == expected_start
        and millis(cue.group(2)) == expected_end
        and cue.group(3) == exact_quote,
        "VTT_CUE_MISMATCH",
    )


def _quoted_pinned_ref(value: str) -> str:
    """All identifiers are code-pinned, never obtained from an operator or URL."""
    _require(bool(re.fullmatch(r"[a-zA-Z0-9_:/.-]{1,180}", value)), "UNSAFE_PINNED_ID")
    return "'" + value.replace("'", "''") + "'"


def _json(db, sql: str, **kwargs):
    raw = db.run(sql, **kwargs)
    return json.loads(raw) if raw else None


def correct_persisted_cue(
    db, *, canonical: str, segment: str, candidate: str, passage: str,
    exact_quote_sha: str, start: int, end: int, vtt_sha: str, version: str,
) -> None:
    """Repair previous 00:14 parsing, only on held/unbound rows.

    Canonical (content, index) is unique, so the correction is a guarded
    update of the existing HELD private revision with an old/new audit trail.
    Two CAS changes share ONE PostgreSQL DO statement/transaction: if either
    update fails, BOTH roll back, allowing an identical safe retry.
    """
    state = _json(db, """SELECT json_build_object(
        'start',c.start_ms,'end',c.end_ms,'transcript',c.transcript_status,
        'blocked',c.publication_blocked,'raw_start',t.start_ms,'raw_end',t.end_ms,
        'candidate_status',s.status,'hash',s.statement_text_hash,
        'binding_count',(SELECT count(*) FROM media_capture_segment_binding b
            WHERE b.canonical_segment_id=c.id))::text
        FROM canonical_transcript_segment c
        JOIN canonical_segment_candidate link ON link.canonical_segment_id=c.id
        JOIN transcript_segment t ON t.id=link.transcript_segment_id
        JOIN statement_candidate s ON s.content_id=c.content_id
        WHERE c.id=:'canonical' AND t.id=:'segment' AND s.id=:'candidate';""",
        canonical=canonical, segment=segment, candidate=candidate)
    _require(
        state and state["hash"] == exact_quote_sha and state["candidate_status"] == "HELD"
        and state["transcript"] == "TRANSCRIPT_UNCERTAIN"
        and state["blocked"] is True and state["binding_count"] == 0,
        "CORRECTION_NOT_PRIVATE_HELD",
    )
    current = (state["start"], state["end"], state["raw_start"], state["raw_end"])
    _require(current in ((14669, 18940, 14669, 18940), (start, end, start, end)),
             "TIMING_STATE_CONFLICT")
    if current == (14669, 18940, 14669, 18940):
        c, t, s = map(_quoted_pinned_ref, (canonical, segment, candidate))
        _require(type(start) is int and type(end) is int and 0 < start < end,
                 "INVALID_TIMING")
        # A single top-level DO command is transactional, including both CAS
        # results; the second failure cannot leave the first committed.
        db.run(f"""DO $dp458$
            DECLARE changed_canonical text; changed_transcript text;
            BEGIN
                UPDATE canonical_transcript_segment
                   SET start_ms={start},end_ms={end}
                 WHERE id={c} AND start_ms=14669 AND end_ms=18940
                   AND transcript_status='TRANSCRIPT_UNCERTAIN'
                   AND publication_blocked=true
                   AND NOT EXISTS (SELECT 1 FROM media_capture_segment_binding
                                   WHERE canonical_segment_id={c})
                   AND EXISTS (SELECT 1 FROM statement_candidate
                               WHERE id={s} AND status='HELD')
                RETURNING id INTO changed_canonical;
                IF changed_canonical IS DISTINCT FROM {c} THEN
                   RAISE EXCEPTION 'DP458_CANONICAL_TIMING_CAS_FAILED';
                END IF;
                UPDATE transcript_segment SET start_ms={start},end_ms={end}
                 WHERE id={t} AND start_ms=14669 AND end_ms=18940
                   AND segment_index=12
                RETURNING id INTO changed_transcript;
                IF changed_transcript IS DISTINCT FROM {t} THEN
                   RAISE EXCEPTION 'DP458_VTT_TIMING_CAS_FAILED';
                END IF;
            END $dp458$;""")
    audit = json.dumps({
        "reason": "DP458_VTT_CUE12_MINUTE_CORRECTION",
        "original_start_ms": 14669, "original_end_ms": 18940,
        "corrected_start_ms": start, "corrected_end_ms": end,
        "vtt_sha256": vtt_sha, "independent_acoustic_alignment": "HOLD",
    })
    db.run("""UPDATE statement_candidate SET extraction_version=:'version',
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND status='HELD' AND statement_text_hash=:'sha';""",
        version=version, audit=audit, id=candidate, sha=exact_quote_sha)
    db.run("""UPDATE passage SET extraction_version=:'version',
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND text_sha256=:'sha';""",
        version=version, audit=audit, id=passage, sha=exact_quote_sha)
    db.run("""UPDATE transcript_segment SET
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND start_ms=:'start'::bigint AND end_ms=:'end'::bigint;""",
        audit=audit, id=segment, start=start, end=end)
