"""Native PostgreSQL receipt read methods shared by the source scheduler."""

from __future__ import annotations

import json
from typing import Any


class ReceiptReadStoreMixin:
    def get_source_poll_run(self, run_id: str) -> dict[str, Any] | None:
        raw = self._run(
            """
            SELECT json_build_object(
                'run_id', id,
                'mode', mode,
                'run_date', run_date::text,
                'effective_config_hash', effective_config_hash,
                'status', status,
                'diagnostic', diagnostic,
                'started_at', started_at::text,
                'completed_at', completed_at::text,
                'source_count', source_count,
                'discovered', discovered,
                'content_upserts', content_upserts,
                'jobs_enqueued', jobs_enqueued,
                'duplicate_jobs', duplicate_jobs,
                'budget_blocked', budget_blocked,
                'omitted_items', omitted_items,
                'error_category', error_category
            )::text
            FROM source_poll_run
            WHERE id = :'run_id';
            """,
            run_id=run_id,
        )
        return json.loads(raw) if raw else None

    def get_source_poll_source(self, run_id: str, source_id: str) -> dict[str, Any] | None:
        raw = self._run(
            """
            SELECT json_build_object(
                'receipt_id', id,
                'run_id', run_id,
                'source_id', source_id,
                'mode', mode,
                'run_date', run_date::text,
                'effective_config_hash', effective_config_hash,
                'diagnostic', diagnostic,
                'status', status,
                'discovered', discovered,
                'content_upserts', content_upserts,
                'jobs_enqueued', jobs_enqueued,
                'duplicate_jobs', duplicate_jobs,
                'budget_blocked', budget_blocked,
                'omitted_items', omitted_items,
                'error', error_category,
                'error_category', error_category,
                'started_at', started_at::text,
                'completed_at', completed_at::text
            )::text
            FROM source_poll_run_source
            WHERE run_id = :'run_id' AND source_id = :'source_id';
            """,
            run_id=run_id,
            source_id=source_id,
        )
        return json.loads(raw) if raw else None

    def list_source_poll_sources(self, run_id: str) -> list[dict[str, Any]]:
        raw = self._run(
            """
            SELECT COALESCE(json_agg(row_to_json(x) ORDER BY source_id)::text, '[]')
            FROM (
                SELECT
                    id AS receipt_id,
                    run_id,
                    source_id,
                    mode,
                    run_date::text,
                    effective_config_hash,
                    diagnostic,
                    status,
                    discovered,
                    content_upserts,
                    jobs_enqueued,
                    duplicate_jobs,
                    budget_blocked,
                    omitted_items,
                    error_category AS error,
                    error_category,
                    started_at::text,
                    completed_at::text
                FROM source_poll_run_source
                WHERE run_id = :'run_id'
            ) x;
            """,
            run_id=run_id,
        )
        return [dict(row) for row in json.loads(raw or "[]")]


def receipts_verified(run_id: str, source_ids: list[str], rows: list[dict],
                      context: Any) -> bool:
    """The persisted child set must cover exactly the configured source set."""
    if len(source_ids) != len(set(source_ids)) or len(rows) != len(source_ids):
        return False
    if {row.get("source_id") for row in rows} != set(source_ids):
        return False
    return all(
        row.get("receipt_id")
        and row.get("run_id") == run_id
        and row.get("mode") == context.mode
        and row.get("run_date") == context.run_date
        and row.get("effective_config_hash") == context.effective_config_hash
        and row.get("diagnostic") == context.diagnostic
        and row.get("status") not in (None, "RUNNING")
        and row.get("completed_at")
        for row in rows
    )
