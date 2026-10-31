"""Read only currently approved Senato candidates from the existing corpus DB.

This reader grants no public quotation rights. The v3 producer independently
requires current rights, identity, agent review and challenge authorities.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .senato_public_v3_source import PinnedSenatoV3Source


_CURRENT = """
SELECT COALESCE(json_agg(item)::text, '[]') FROM (
    SELECT json_build_object(
        'statement_id', s.id,
        'version_id', s.metadata->>'public_version_id',
        'status', s.status,
        'content_id', s.content_id,
        'source_version', c.content_sha256,
        'speech_id', s.metadata->>'source_speech_id',
        'official_person_uri', s.metadata->>'source_official_person_uri',
        'person_id', s.speaker_person_id,
        'speaker_name', person.canonical_name,
        'start_char', p.start_char,
        'end_char', p.end_char,
        'quote', p.private_text,
        'quote_sha256', p.text_sha256
    ) AS item
    FROM statement_candidate s
    JOIN statement_candidate_passage link
      ON link.statement_candidate_id=s.id AND link.content_id=s.content_id
    JOIN passage p ON p.id=link.passage_id AND p.content_id=s.content_id
    JOIN content_capture c ON c.id=p.capture_id AND c.content_id=s.content_id
    JOIN person ON person.id=s.speaker_person_id AND person.is_public_figure=true
    WHERE s.content_id=:'content_id' AND s.status='APPROVED'
      AND s.metadata->>'source_content_sha256'=:'source_sha256'
      AND s.metadata->>'speaker_resolution_status'='APPROVED'
      AND s.metadata->>'quote_review_status'='APPROVED'
      AND s.metadata->>'public_version_id' IS NOT NULL
      AND s.metadata->>'source_speech_id'=p.metadata->>'source_speech_id'
      AND s.normalized_statement=p.private_text
      AND s.statement_text_hash=p.text_sha256
      AND c.content_sha256=:'source_sha256' AND c.final_url=:'source_url'
      AND c.status='CAPTURED' AND c.hold_status='NONE'
      AND c.rights_status='CLEARED' AND c.body_purged_at IS NULL
    ORDER BY s.id, p.id LIMIT 33
) selected;
"""


class CurrentSenatoPostgresCandidates:
    """Replay exact existing PostgreSQL rows; fail closed on ambiguity or errors."""

    def __init__(self, pins: PinnedSenatoV3Source, *, store: object):
        if not isinstance(pins, PinnedSenatoV3Source) or not callable(getattr(store, "run", None)):
            raise ValueError("DP468_CANDIDATE_STORE_REQUIRED")
        self.pins = pins
        self.store = store

    def __call__(self) -> list[dict[str, Any]]:
        raw = self.store.run(
            _CURRENT, content_id=self.pins.content_id,
            source_sha256=self.pins.xml_sha256,
            source_url=self.pins.source_raw_url,
        )
        try:
            rows = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("DP468_CANDIDATE_REPLAY_INVALID") from exc
        if not isinstance(rows, list) or len(rows) > 32:
            raise ValueError("DP468_CANDIDATE_REPLAY_INVALID")
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "statement_id", "version_id", "status", "content_id", "source_version",
                "speech_id", "official_person_uri", "person_id", "speaker_name",
                "start_char", "end_char", "quote", "quote_sha256",
            }:
                raise ValueError("DP468_CANDIDATE_REPLAY_INVALID")
            quote, checksum = row.pop("quote"), row.pop("quote_sha256")
            if (not isinstance(quote, str) or not quote.strip()
                    or hashlib.sha256(quote.encode()).hexdigest() != checksum
                    or not isinstance(row["statement_id"], str)
                    or row["statement_id"] in seen
                    or row["status"] != "APPROVED"
                    or row["content_id"] != self.pins.content_id
                    or row["source_version"] != self.pins.xml_sha256
                    or not isinstance(row["version_id"], str)
                    or not row["version_id"].strip()):
                raise ValueError("DP468_CANDIDATE_REPLAY_INVALID")
            seen.add(row["statement_id"])
            result.append(row)
        return result
