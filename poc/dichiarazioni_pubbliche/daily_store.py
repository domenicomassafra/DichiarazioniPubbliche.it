"""DP-638 — persistence of captures, statements, verdicts and runs."""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.daily_capture import Capture
from dichiarazioni_pubbliche.daily_config import SourceSpec
from dichiarazioni_pubbliche.daily_text import sha256_text, utc_now
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

PUBLISHED = "PUBLISHED"
HELD_NO_SPEAKER = "HELD_NO_SPEAKER"
HELD_NO_VERDICT = "HELD_NO_VERDICT"
HELD_DUPLICATE = "HELD_DUPLICATE"

# --------------------------------------------------------------------------

class DailyStore(PsqlRuntime):
    """The four daily tables plus the two rows a capture reuses from the queue."""

    def upsert_source(self, source: SourceSpec) -> None:
        self.run(
            """
            INSERT INTO source (id, canonical_name, source_type, canonical_url, language, country_code, metadata)
            VALUES (:'source_id', :'name', :'kind', :'url', 'it', 'IT', :'metadata'::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                source_type = EXCLUDED.source_type,
                canonical_url = COALESCE(NULLIF(EXCLUDED.canonical_url, ''), source.canonical_url),
                metadata = source.metadata || EXCLUDED.metadata,
                updated_at = now();
            """,
            source_id=source.id,
            name=source.name,
            kind=source.kind,
            url=source.discovery_url,
            metadata=json.dumps({"publisher": source.publisher, "daily_machine": "DP-638"}),
        )

    def save_items(self, rows: Sequence[dict[str, Any]]) -> dict[str, str]:
        if not rows:
            return {}
        raw = self.run(
            """
            WITH input AS (
                SELECT * FROM jsonb_to_recordset(:'items'::jsonb) AS x(
                    content_id text, source_id text, external_id text, title text,
                    description text, canonical_url text, published_at text,
                    duration_ms bigint, metadata jsonb
                )
            ), upserted AS (
                INSERT INTO content_item (
                    id, source_id, source_external_id, canonical_url, title,
                    description, language, published_at, duration_ms, metadata
                )
                SELECT content_id, source_id, external_id, canonical_url, title,
                       NULLIF(description, ''), 'it',
                       NULLIF(published_at, '')::timestamptz, duration_ms, metadata
                FROM input
                ON CONFLICT (source_id, source_external_id) DO UPDATE SET
                    title = COALESCE(NULLIF(EXCLUDED.title, ''), content_item.title),
                    description = COALESCE(EXCLUDED.description, content_item.description),
                    canonical_url = CASE
                        WHEN content_item.canonical_url = '' THEN EXCLUDED.canonical_url
                        ELSE content_item.canonical_url END,
                    published_at = COALESCE(content_item.published_at, EXCLUDED.published_at),
                    duration_ms = COALESCE(content_item.duration_ms, EXCLUDED.duration_ms),
                    metadata = (content_item.metadata || EXCLUDED.metadata) ||
                        CASE WHEN content_item.metadata->'ingestion_relevance'->>'attribution_version'
                                  = 'direct-source-attribution-v2'
                               AND content_item.metadata->'ingestion_relevance'->>'decision'
                                  IN ('RELEVANT', 'UNCONFIRMED')
                             THEN jsonb_build_object('ingestion_relevance', content_item.metadata->'ingestion_relevance')
                             ELSE '{}'::jsonb END
                RETURNING id, source_id, source_external_id
            )
            SELECT COALESCE(jsonb_object_agg(input.content_id, upserted.id), '{}'::jsonb)::text
            FROM upserted JOIN input
              ON input.source_id = upserted.source_id
             AND input.external_id = upserted.source_external_id;
            """,
            items=json.dumps(list(rows), ensure_ascii=False),
        )
        return dict(json.loads(raw.strip() or "{}"))

    def save_capture(
        self,
        *,
        capture_id: str,
        content_id: str,
        source_id: str,
        capture: Capture,
    ) -> None:
        self.run(
            """
            INSERT INTO daily_capture (
                id, content_id, source_id, capture_kind, url,
                char_count, text_sha256, body, metadata
            ) VALUES (
                :'id', :'content_id', :'source_id', :'kind', :'url',
                :'chars'::integer, :'sha', :'body', :'metadata'::jsonb
            )
            ON CONFLICT (id) DO NOTHING;
            """,
            id=capture_id,
            content_id=content_id,
            source_id=source_id,
            kind=capture.kind,
            url=capture.url,
            chars=len(capture.body),
            sha=sha256_text(capture.body),
            body=capture.body,
            metadata=json.dumps(capture.metadata, ensure_ascii=False),
        )

    def set_relevance(self, content_id: str, *, decision: str, reason: str) -> None:
        self.run(
            """UPDATE content_item
               SET metadata = jsonb_set(
                   metadata, '{ingestion_relevance}',
                   COALESCE(metadata->'ingestion_relevance', '{}'::jsonb) ||
                   jsonb_build_object('decision', :'decision', 'reason', :'reason', 'decided_at', now())
               )
               WHERE id = :'content_id';""",
            content_id=content_id, decision=decision, reason=reason,
        )

    def save_statement(self, row: dict[str, Any]) -> None:
        self.run(
            """
            INSERT INTO daily_statement (
                id, content_id, capture_id, source_id, source_url, source_title,
                source_publisher, source_published_at, statement_date, quote,
                quote_offset, moment_label, speaker_name, speaker_role, speaker_key,
                topic, claim_nature, status, status_reason, extraction_model, metadata
            ) VALUES (
                :'id', :'content_id', :'capture_id', :'source_id', :'source_url',
                :'source_title', :'source_publisher',
                NULLIF(:'source_published_at', '')::timestamptz,
                :'statement_date'::date, :'quote', :'quote_offset'::integer,
                :'moment_label', :'speaker_name', :'speaker_role', :'speaker_key',
                :'topic', :'claim_nature', :'status', :'status_reason',
                :'extraction_model', :'metadata'::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                capture_id = EXCLUDED.capture_id,
                source_url = EXCLUDED.source_url,
                source_title = EXCLUDED.source_title,
                source_publisher = EXCLUDED.source_publisher,
                source_published_at = EXCLUDED.source_published_at,
                statement_date = EXCLUDED.statement_date,
                quote = EXCLUDED.quote,
                quote_offset = EXCLUDED.quote_offset,
                moment_label = EXCLUDED.moment_label,
                speaker_name = EXCLUDED.speaker_name,
                speaker_role = EXCLUDED.speaker_role,
                speaker_key = EXCLUDED.speaker_key,
                topic = EXCLUDED.topic,
                claim_nature = EXCLUDED.claim_nature,
                status = EXCLUDED.status,
                status_reason = EXCLUDED.status_reason,
                extraction_model = EXCLUDED.extraction_model,
                metadata = EXCLUDED.metadata;
            """,
            **row,
        )

    def save_verdict(self, statement_id: str, verdict: dict[str, Any]) -> None:
        self.run(
            """
            INSERT INTO daily_verdict (
                statement_id, verdict, explanation, evidence, first_pass,
                check_pass, agreement, models, model_calls, duration_seconds
            ) VALUES (
                :'statement_id', :'verdict', :'explanation', :'evidence'::jsonb,
                :'first_pass'::jsonb, :'check_pass'::jsonb, :'agreement', :'models',
                :'model_calls'::integer, :'duration_seconds'::numeric
            )
            ON CONFLICT (statement_id) DO UPDATE SET
                verdict = EXCLUDED.verdict,
                explanation = EXCLUDED.explanation,
                evidence = EXCLUDED.evidence,
                first_pass = EXCLUDED.first_pass,
                check_pass = EXCLUDED.check_pass,
                agreement = EXCLUDED.agreement,
                models = EXCLUDED.models,
                model_calls = EXCLUDED.model_calls,
                duration_seconds = EXCLUDED.duration_seconds;
            """,
            statement_id=statement_id,
            verdict=verdict["verdict"],
            explanation=verdict["explanation"],
            evidence=json.dumps(verdict["evidence"], ensure_ascii=False),
            first_pass=json.dumps(verdict["first_pass"], ensure_ascii=False),
            check_pass=json.dumps(verdict["check_pass"], ensure_ascii=False),
            agreement=verdict["agreement"],
            models=verdict["models"],
            model_calls=int(verdict["model_calls"]),
            duration_seconds=f"{float(verdict['duration_seconds']):.3f}",
        )

    def write_receipt(
        self,
        *,
        content_id: str,
        provider_id: str,
        model_id: str,
        operation: str,
        request_key: str,
        latency_seconds: float,
        usage: dict[str, Any],
        status: str = "OK",
    ) -> str:
        receipt_id = "receipt:" + hashlib.sha256(
            "\0".join(("dp638", content_id, provider_id, operation, request_key)).encode()
        ).hexdigest()
        self.run(
            """
            INSERT INTO provider_receipt (
                id, content_id, provider_id, model_id, operation, started_at,
                completed_at, input_bytes, estimated_cost_usd, status, receipt,
                operation_key, attempt, billing_basis, total_tokens, request_count,
                ledger_scope
            ) VALUES (
                :'id', :'content_id', :'provider_id', :'model_id', :'operation',
                now() - make_interval(secs => :'latency'::numeric), now(),
                NULL, 0, :'status', :'receipt'::jsonb, :'operation_key', 1,
                'EXTERNAL_PLAN', :'total_tokens'::bigint, 1,
                '{"scope": "DP-638 daily machine", "provider": "omniroute"}'::jsonb
            )
            ON CONFLICT (id) DO NOTHING;
            """,
            id=receipt_id,
            content_id=content_id,
            provider_id=provider_id,
            model_id=model_id or "unknown",
            operation=operation,
            status=status,
            receipt=json.dumps(
                {"latency_seconds": latency_seconds, "usage": usage}, ensure_ascii=False
            ),
            operation_key=request_key,
            total_tokens=int((usage or {}).get("total_tokens") or 0),
            latency=max(latency_seconds, 0.0),
        )
        return receipt_id

    def capture_ids_today(self, run_date: str) -> set[str]:
        raw = self.run(
            """
            SELECT COALESCE(jsonb_agg(content_id), '[]'::jsonb)::text
            FROM daily_capture WHERE fetched_at::date = :'day'::date;
            """,
            day=run_date,
        )
        return set(json.loads(raw.strip() or "[]"))

    def record_run(self, run_date: str, report: dict[str, Any], *, finished: bool) -> None:
        self.run(
            """
            INSERT INTO daily_run (
                run_date, started_at, finished_at, items, captures,
                statements, verdicts, published, report
            ) VALUES (
                :'run_date'::date, :'started_at'::timestamptz,
                CASE WHEN :'finished'::boolean THEN :'finished_at'::timestamptz ELSE NULL END,
                :'items'::integer, :'captures'::integer, :'statements'::integer,
                :'verdicts'::integer, :'published'::integer, :'report'::jsonb
            )
            ON CONFLICT (run_date) DO UPDATE SET
                finished_at = COALESCE(EXCLUDED.finished_at, daily_run.finished_at),
                items = EXCLUDED.items,
                captures = EXCLUDED.captures,
                statements = EXCLUDED.statements,
                verdicts = EXCLUDED.verdicts,
                published = EXCLUDED.published,
                report = EXCLUDED.report;
            """,
            run_date=run_date,
            started_at=report.get("started_at") or utc_now(),
            finished="true" if finished else "false",
            finished_at=utc_now(),
            items=int(report.get("items", 0)),
            captures=int(report.get("captures", 0)),
            statements=int(report.get("statements", 0)),
            verdicts=int(report.get("verdicts", 0)),
            published=int(report.get("published", 0)),
            report=json.dumps(report, ensure_ascii=False),
        )

    def published_since(self, day: str) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'id', statement.id,
                'quote', statement.quote,
                'speaker', statement.speaker_name,
                'source_url', statement.source_url,
                'source_publisher', statement.source_publisher,
                'topic', statement.topic,
                'verdict', COALESCE(verdict.verdict, 'NOT_VERIFIABLE'),
                'explanation', COALESCE(verdict.explanation, '')
            )), '[]'::jsonb)::text
            FROM daily_statement statement
            LEFT JOIN daily_verdict verdict ON verdict.statement_id = statement.id
            WHERE statement.status = 'PUBLISHED' AND statement.statement_date >= :'day'::date;
            """,
            day=day,
        )
        return list(json.loads(raw.strip() or "[]"))

    def statement_count(self, day: str) -> int:
        raw = self.run(
            "SELECT count(*) FROM daily_statement WHERE statement_date = :'day'::date;",
            day=day,
        )
        return int(raw.strip() or 0)
