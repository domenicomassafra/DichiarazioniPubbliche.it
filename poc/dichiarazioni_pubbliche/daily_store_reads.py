"""Explicit private read contracts for DP-638 daily records."""

from __future__ import annotations

import json
from typing import Any

from dichiarazioni_pubbliche.daily_store_contracts import STATEMENT_STATUSES


def _json_object(raw: str) -> dict[str, Any]:
    value = json.loads(raw.strip() or "{}")
    if not isinstance(value, dict):
        raise ValueError("DAILY_STORE_READ_CONTRACT_INVALID_OBJECT")
    return value


def _json_array(raw: str) -> list[dict[str, Any]]:
    value = json.loads(raw.strip() or "[]")
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("DAILY_STORE_READ_CONTRACT_INVALID_ARRAY")
    return value


class DailyStoreReadMixin:
    """Read-only methods mixed into DailyStore; all projections are private."""

    def capture_ids_today(self, run_date: str) -> set[str]:
        raw = self.run(
            """
            SELECT COALESCE(jsonb_agg(content_id), '[]'::jsonb)::text
            FROM daily_capture
            WHERE fetched_at::date = :'day'::date;
            """,
            day=run_date,
        )
        return set(json.loads(raw.strip() or "[]"))

    def read_capture_metadata(self, capture_id: str) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT COALESCE((
                SELECT to_jsonb(capture_row)
                FROM (
                    SELECT id, content_id, source_id, capture_kind, url,
                           fetched_at, char_count, text_sha256, metadata
                    FROM daily_capture
                    WHERE id = :'capture_id'
                ) capture_row
            ), '{}'::jsonb)::text;
            """,
            capture_id=capture_id,
        )
        return _json_object(raw)

    def read_capture_body(self, capture_id: str) -> str:
        return self.run(
            "SELECT body FROM daily_capture WHERE id = :'capture_id';",
            capture_id=capture_id,
        )

    def read_statement(self, statement_id: str) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT COALESCE((
                SELECT to_jsonb(statement_row)
                FROM (
                    SELECT statement.id, statement.content_id, statement.capture_id,
                           statement.source_id, statement.source_url, statement.source_title,
                           statement.source_publisher, statement.source_published_at,
                           statement.statement_date, statement.quote, statement.quote_offset,
                           statement.moment_label, statement.speaker_name, statement.speaker_role,
                           statement.speaker_key, statement.topic, statement.claim_nature,
                           statement.status, statement.status_reason, statement.extraction_model,
                           statement.created_at, verdict.verdict, verdict.explanation
                    FROM daily_statement statement
                    LEFT JOIN daily_verdict verdict ON verdict.statement_id = statement.id
                    WHERE statement.id = :'statement_id'
                ) statement_row
            ), '{}'::jsonb)::text;
            """,
            statement_id=statement_id,
        )
        return _json_object(raw)

    def read_statements(
        self,
        *,
        since: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in STATEMENT_STATUSES:
            raise ValueError(f"DAILY_STATEMENT_STATUS_INVALID:{status}")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("DAILY_STATEMENT_READ_LIMIT_INVALID")
        raw = self.run(
            """
            SELECT COALESCE(
                jsonb_agg(to_jsonb(statement_row)
                          ORDER BY statement_row.statement_date DESC,
                                   statement_row.created_at DESC),
                '[]'::jsonb
            )::text
            FROM (
                SELECT statement.id, statement.content_id, statement.capture_id,
                       statement.source_id, statement.source_url, statement.source_title,
                       statement.source_publisher, statement.source_published_at,
                       statement.statement_date, statement.quote, statement.quote_offset,
                       statement.moment_label, statement.speaker_name, statement.speaker_role,
                       statement.speaker_key, statement.topic, statement.claim_nature,
                       statement.status, statement.status_reason, statement.extraction_model,
                       statement.created_at, verdict.verdict, verdict.explanation
                FROM daily_statement statement
                LEFT JOIN daily_verdict verdict ON verdict.statement_id = statement.id
                WHERE statement.statement_date >= :'since'::date
                  AND (NULLIF(:'status', '') IS NULL OR statement.status = :'status')
                ORDER BY statement.statement_date DESC, statement.created_at DESC
                LIMIT :'limit'::integer
            ) statement_row;
            """,
            since=since,
            status=status or "",
            limit=limit,
        )
        return _json_array(raw)

    def read_verdict(self, statement_id: str) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT COALESCE((
                SELECT to_jsonb(verdict_row)
                FROM (
                    SELECT statement_id, verdict, explanation, evidence,
                           first_pass, check_pass, agreement, models, model_calls,
                           duration_seconds, created_at
                    FROM daily_verdict
                    WHERE statement_id = :'statement_id'
                ) verdict_row
            ), '{}'::jsonb)::text;
            """,
            statement_id=statement_id,
        )
        return _json_object(raw)

    def read_run(self, run_date: str) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT COALESCE((
                SELECT to_jsonb(run_row)
                FROM (
                    SELECT run_date, started_at, finished_at, status, items,
                           captures, statements, verdicts, held_statements, report
                    FROM daily_run
                    WHERE run_date = :'run_date'::date
                ) run_row
            ), '{}'::jsonb)::text;
            """,
            run_date=run_date,
        )
        return _json_object(raw)

    def statement_count(self, day: str) -> int:
        raw = self.run(
            "SELECT count(*) FROM daily_statement WHERE statement_date = :'day'::date;",
            day=day,
        )
        return int(raw.strip() or 0)
