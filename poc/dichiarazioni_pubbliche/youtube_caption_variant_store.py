"""#169: one transaction locks reviewed source rights while storing raw captions.

Every SQL operation runs through the existing queue store. Locking the current
rights row FOR UPDATE also blocks a concurrent superseding rights INSERT via
its foreign key until commit; the subsequent statement gets a fresh snapshot.
"""
from __future__ import annotations

import json

from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.queue_runtime import (
    QueueRuntimeStore, _dollar_quote, deterministic_segment_id, deterministic_variant_id,
)
from dichiarazioni_pubbliche.rights_registry import rights_subject_fingerprint


def insert_rights_bound_caption_variant(
    store: QueueRuntimeStore, guard: SourceFamilyUseGuard, *,
    content_id: str, provider_id: str, source_kind: str, language: str,
    raw_text: str, raw_text_sha256: str, is_platform_caption: bool,
    is_manual_caption: bool, metadata: dict, segments: list[dict],
) -> tuple[str, bool]:
    """Fail closed if rights were superseded before raw text INSERT commits."""
    if (not isinstance(store, QueueRuntimeStore)
            or not isinstance(guard, SourceFamilyUseGuard)
            or guard.subject.content_id != content_id
            or guard.subject.source_family != "YOUTUBE"
            or provider_id != "youtube" or not is_platform_caption):
        raise SourceUseBlocked("SOURCE_USE_ATOMIC_VARIANT_CONTEXT_INVALID")
    try:
        variant_id = deterministic_variant_id(
            content_id, provider_id, source_kind, raw_text_sha256,
        )
        serialized = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        rows = [
            {
                "id": deterministic_segment_id(variant_id, int(item["segment_index"])),
                "variant_id": variant_id,
                "segment_index": int(item["segment_index"]),
                "start_ms": int(item["start_ms"]),
                "end_ms": int(item["end_ms"]),
                "text": str(item["text"]),
                "metadata": item.get("metadata") or {},
            }
            for item in segments
        ]
        if not rows or len(rows) > 512:
            raise ValueError("CAPTION_SEGMENTS_INVALID")
        quoted = {key: _dollar_quote(value) for key, value in {
            "variant_id": variant_id,
            "content_id": content_id,
            "provider_id": provider_id,
            "source_kind": source_kind,
            "language": language,
            "raw_text": raw_text,
            "raw_text_sha256": raw_text_sha256,
            "metadata": serialized,
            "segments": json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
            "rights_id": guard.rights_record_id,
            "subject_fp": rights_subject_fingerprint(guard.subject),
            "policy": guard.policy_version,
            "video_url": guard.subject.locator_value,
        }.items()}
        # Separate SELECT statements in one transaction matter: after the
        # parent-row lock is granted, the fresh snapshot sees any successor
        # that committed while waiting for that lock.
        sql = f"""
            BEGIN;
            SELECT id FROM private_source_rights_record
            WHERE id={quoted['rights_id']} FOR UPDATE;
            WITH permitted AS MATERIALIZED (
                SELECT rights.id FROM private_source_rights_record rights
                WHERE rights.id={quoted['rights_id']}
                  AND rights.subject_fingerprint={quoted['subject_fp']}
                  AND rights.content_id={quoted['content_id']}
                  AND rights.source_family='YOUTUBE'
                  AND rights.locator_kind='URL'
                  AND rights.locator_value={quoted['video_url']}
                  AND rights.policy_version={quoted['policy']}
                  AND rights.record_version='private-rights-record-v1'
                  AND rights.record_visibility='PRIVATE'
                  AND rights.rights_status='CLEARED'
                  AND rights.permitted_uses @> ARRAY['FETCH','STORE_BODY']::text[]
                  AND rights.rights_receipt_ref IS NOT NULL
                  AND rights.reviewer_ref IS NOT NULL
                  AND rights.reviewed_at <= now()
                  AND rights.expires_at > now()
                  AND NOT EXISTS (
                      SELECT 1 FROM private_source_rights_record successor
                      WHERE successor.supersedes_id=rights.id
                  )
            ), inserted AS (
                INSERT INTO transcript_variant (
                    id, content_id, provider_id, source_kind, language,
                    raw_text_sha256, raw_text, is_platform_caption,
                    is_manual_caption, metadata
                ) SELECT
                    {quoted['variant_id']}, {quoted['content_id']},
                    {quoted['provider_id']}, {quoted['source_kind']},
                    {quoted['language']}, {quoted['raw_text_sha256']},
                    {quoted['raw_text']}, {str(is_platform_caption).lower()},
                    {str(is_manual_caption).lower()}, {quoted['metadata']}::jsonb
                FROM permitted
                WHERE true
                ON CONFLICT (id) DO NOTHING RETURNING id
            ), inserted_segments AS (
                INSERT INTO transcript_segment (
                    id, variant_id, segment_index, start_ms, end_ms, text, metadata
                ) SELECT
                    x.id, x.variant_id, x.segment_index, x.start_ms,
                    x.end_ms, x.text, x.metadata
                FROM jsonb_to_recordset({quoted['segments']}::jsonb) AS x(
                    id text, variant_id text, segment_index integer,
                    start_ms bigint, end_ms bigint, text text, metadata jsonb
                )
                JOIN inserted ON inserted.id=x.variant_id
                ON CONFLICT (variant_id, segment_index) DO NOTHING RETURNING id
            ) SELECT (SELECT count(*) FROM permitted)::text || '|' ||
                (EXISTS (SELECT 1 FROM inserted))::text || '|' ||
                (SELECT count(*) FROM inserted_segments)::text;
            COMMIT;
        """
        output = store.run_literal(sql).splitlines()
        outcome = output[-1].strip().lower() if output else ""
    except Exception:
        raise SourceUseBlocked("SOURCE_USE_ATOMIC_VARIANT_UNAVAILABLE") from None
    if not (outcome.startswith("1|true|") or outcome.startswith("1|false|")
            or outcome.startswith("1|t|") or outcome.startswith("1|f|")):
        raise SourceUseBlocked("SOURCE_USE_NOT_CURRENT_AT_VARIANT_COMMIT")
    return variant_id, outcome.split("|")[1] in {"t", "true"}


__all__ = ["insert_rights_bound_caption_variant"]
