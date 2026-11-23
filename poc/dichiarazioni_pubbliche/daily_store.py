"""Private persistence and explicit read contracts for DP-638 daily records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.daily_config import SourceSpec
from dichiarazioni_pubbliche.daily_store_contracts import (
    BILLING_BASES,
    CLAIM_NATURES,
    FACTUAL_VERDICTS,
    STATEMENT_STATUSES,
)
from dichiarazioni_pubbliche.daily_store_reads import DailyStoreReadMixin
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

@dataclass(frozen=True)
class CaptureRecord:
    kind: str
    url: str
    body: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"t", "true", "1"}


class DailyStore(DailyStoreReadMixin, PsqlRuntime):
    """Persistence for private daily records; never a public projection store."""

    def upsert_source(self, source: SourceSpec) -> None:
        self.run(
            """
            INSERT INTO source (
                id, canonical_name, source_type, canonical_url, language,
                country_code, metadata
            )
            VALUES (
                :'source_id', :'name', :'kind', :'url', 'it', 'IT', :'metadata'::jsonb
            )
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
            metadata=json.dumps(
                {"publisher": source.publisher, "daily_machine": "DP-638"},
                ensure_ascii=False,
            ),
        )

    def save_items(self, rows: Sequence[dict[str, Any]]) -> dict[str, str]:
        if not rows:
            return {}
        normalized = [
            {
                **row,
                "metadata": row.get("metadata") or {},
            }
            for row in rows
        ]
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
            items=json.dumps(normalized, ensure_ascii=False),
        )
        return dict(json.loads(raw.strip() or "{}"))

    def save_capture(
        self,
        *,
        capture_id: str,
        content_id: str,
        source_id: str,
        capture: CaptureRecord,
    ) -> bool:
        if not capture.url.strip() or not capture.kind.strip():
            raise ValueError("DAILY_CAPTURE_SOURCE_AND_KIND_REQUIRED")
        raw = self.run(
            """
            INSERT INTO daily_capture (
                id, content_id, source_id, capture_kind, url,
                char_count, text_sha256, body, metadata
            ) VALUES (
                :'id', :'content_id', :'source_id', :'kind', :'url',
                :'chars'::integer, :'sha', :'body', :'metadata'::jsonb
            )
            ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            id=capture_id,
            content_id=content_id,
            source_id=source_id,
            kind=capture.kind,
            url=capture.url,
            chars=len(capture.body),
            sha=_sha256_text(capture.body),
            body=capture.body,
            metadata=json.dumps(dict(capture.metadata), ensure_ascii=False),
        )
        return bool(raw.strip())

    def set_relevance(self, content_id: str, *, decision: str, reason: str) -> None:
        self.run(
            """
            UPDATE content_item
            SET metadata = jsonb_set(
                metadata, '{ingestion_relevance}',
                COALESCE(metadata->'ingestion_relevance', '{}'::jsonb) ||
                jsonb_build_object(
                    'decision', :'decision',
                    'reason', :'reason',
                    'decided_at', now()
                )
            )
            WHERE id = :'content_id';
            """,
            content_id=content_id,
            decision=decision,
            reason=reason,
        )

    def save_statement(self, row: Mapping[str, Any]) -> bool:
        status = str(row.get("status") or "CANDIDATE")
        claim_nature = str(row.get("claim_nature") or "FACTUAL")
        quote = str(row.get("quote") or "")
        if status not in STATEMENT_STATUSES:
            raise ValueError(f"DAILY_STATEMENT_STATUS_INVALID:{status}")
        if claim_nature not in CLAIM_NATURES:
            raise ValueError(f"DAILY_STATEMENT_NATURE_INVALID:{claim_nature}")
        if not quote.strip():
            raise ValueError("DAILY_STATEMENT_QUOTE_REQUIRED")
        quote_offset = row.get("quote_offset", 0)
        if isinstance(quote_offset, bool) or not isinstance(quote_offset, int) or quote_offset < 0:
            raise ValueError("DAILY_STATEMENT_QUOTE_OFFSET_INVALID")

        params = {
            "id": row["id"],
            "content_id": row["content_id"],
            "capture_id": row["capture_id"],
            "source_id": row["source_id"],
            "source_url": row["source_url"],
            "source_title": row["source_title"],
            "source_publisher": row["source_publisher"],
            "source_published_at": row.get("source_published_at") or "",
            "statement_date": row["statement_date"],
            "quote": quote,
            "quote_offset": quote_offset,
            "moment_label": row.get("moment_label") or "",
            "speaker_name": row.get("speaker_name") or "",
            "speaker_role": row.get("speaker_role") or "",
            "speaker_key": row.get("speaker_key") or "",
            "topic": row.get("topic") or "",
            "claim_nature": claim_nature,
            "status": status,
            "status_reason": row.get("status_reason") or "",
            "extraction_model": row.get("extraction_model") or "",
            "metadata": json.dumps(row.get("metadata") or {}, ensure_ascii=False),
        }
        raw = self.run(
            """
            INSERT INTO daily_statement (
                id, content_id, capture_id, source_id, source_url, source_title,
                source_publisher, source_published_at, statement_date, quote,
                quote_offset, moment_label, speaker_name, speaker_role, speaker_key,
                topic, claim_nature, status, status_reason, extraction_model, metadata
            )
            SELECT
                :'id', :'content_id', :'capture_id', :'source_id', :'source_url',
                :'source_title', :'source_publisher',
                NULLIF(:'source_published_at', '')::timestamptz,
                :'statement_date'::date, :'quote', :'quote_offset'::integer,
                :'moment_label', :'speaker_name', :'speaker_role', :'speaker_key',
                :'topic', :'claim_nature', :'status', :'status_reason',
                :'extraction_model', :'metadata'::jsonb
            FROM daily_capture capture
            WHERE capture.id = :'capture_id'
              AND capture.content_id = :'content_id'
              AND capture.source_id = :'source_id'
              AND substr(
                  capture.body,
                  :'quote_offset'::integer + 1,
                  char_length(:'quote')
              ) = :'quote'
            ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            **params,
        )
        return bool(raw.strip())

    def set_statement_status(
        self, statement_id: str, *, status: str, reason: str
    ) -> bool:
        if status not in STATEMENT_STATUSES or status == "CANDIDATE":
            raise ValueError(f"DAILY_STATEMENT_STATUS_TRANSITION_INVALID:{status}")
        raw = self.run(
            """
            UPDATE daily_statement
            SET status = :'status', status_reason = :'reason'
            WHERE id = :'statement_id'
              AND (status = 'CANDIDATE' OR status = :'status')
            RETURNING id;
            """,
            statement_id=statement_id,
            status=status,
            reason=reason,
        )
        return bool(raw.strip())

    def save_verdict(self, statement_id: str, verdict: Mapping[str, Any]) -> bool:
        value = str(verdict.get("verdict") or "")
        if value not in FACTUAL_VERDICTS:
            raise ValueError(f"DAILY_FACTUAL_VERDICT_INVALID:{value}")
        evidence = verdict.get("evidence") or []
        first_pass = verdict.get("first_pass") or {}
        check_pass = verdict.get("check_pass") or {}
        if (
            not isinstance(evidence, list)
            or not isinstance(first_pass, dict)
            or not first_pass
            or not isinstance(check_pass, dict)
            or not check_pass
        ):
            raise ValueError("DAILY_VERDICT_EVIDENCE_OR_PASSES_INVALID")
        model_calls = int(verdict.get("model_calls", 0))
        duration_seconds = float(verdict.get("duration_seconds", 0))
        if model_calls < 2 or duration_seconds < 0 or not str(verdict.get("models") or "").strip():
            raise ValueError("DAILY_VERDICT_METRICS_INVALID")

        raw = self.run(
            """
            WITH saved AS (
                INSERT INTO daily_verdict (
                    statement_id, claim_nature, verdict, explanation, evidence,
                    first_pass, check_pass, agreement, models, model_calls,
                    duration_seconds
                )
                SELECT
                    statement.id, 'FACTUAL', :'verdict', :'explanation',
                    :'evidence'::jsonb, :'first_pass'::jsonb, :'check_pass'::jsonb,
                    :'agreement', :'models', :'model_calls'::integer,
                    :'duration_seconds'::numeric
                FROM daily_statement statement
                WHERE statement.id = :'statement_id'
                  AND statement.claim_nature = 'FACTUAL'
                  AND statement.status = 'CANDIDATE'
                ON CONFLICT (statement_id) DO UPDATE SET
                    verdict = EXCLUDED.verdict,
                    explanation = EXCLUDED.explanation,
                    evidence = EXCLUDED.evidence,
                    first_pass = EXCLUDED.first_pass,
                    check_pass = EXCLUDED.check_pass,
                    agreement = EXCLUDED.agreement,
                    models = EXCLUDED.models,
                    model_calls = EXCLUDED.model_calls,
                    duration_seconds = EXCLUDED.duration_seconds,
                    created_at = now()
                RETURNING statement_id
            )
            SELECT EXISTS (SELECT 1 FROM saved)::text;
            """,
            statement_id=statement_id,
            verdict=value,
            explanation=str(verdict.get("explanation") or ""),
            evidence=json.dumps(evidence, ensure_ascii=False),
            first_pass=json.dumps(first_pass, ensure_ascii=False),
            check_pass=json.dumps(check_pass, ensure_ascii=False),
            agreement=str(verdict.get("agreement") or ""),
            models=str(verdict.get("models") or ""),
            model_calls=model_calls,
            duration_seconds=f"{duration_seconds:.3f}",
        )
        return _as_bool(raw)

    def write_receipt(
        self,
        *,
        content_id: str,
        provider_id: str,
        model_id: str,
        operation: str,
        request_key: str,
        latency_seconds: float,
        usage: Mapping[str, Any],
        status: str = "OK",
        billing_basis: str = "UNKNOWN",
        estimated_cost_usd: float | None = None,
        measured_cost_usd: float | None = None,
    ) -> str:
        if billing_basis not in BILLING_BASES:
            raise ValueError(f"DAILY_RECEIPT_BILLING_BASIS_INVALID:{billing_basis}")
        receipt_id = "receipt:" + hashlib.sha256(
            "\0".join(("dp638", content_id, provider_id, operation, request_key)).encode()
        ).hexdigest()
        self.run(
            """
            INSERT INTO provider_receipt (
                id, content_id, provider_id, model_id, operation, started_at,
                completed_at, input_bytes, estimated_cost_usd, measured_cost_usd,
                status, receipt, operation_key, attempt, billing_basis, total_tokens,
                request_count, ledger_scope
            ) VALUES (
                :'id', :'content_id', :'provider_id', :'model_id', :'operation',
                now() - make_interval(secs => :'latency'::numeric), now(),
                NULL, NULLIF(:'estimated_cost_usd', '')::numeric,
                NULLIF(:'measured_cost_usd', '')::numeric, :'status', :'receipt'::jsonb,
                :'operation_key', 1, :'billing_basis', :'total_tokens'::bigint, 1,
                '{\"scope\": \"DP-638 daily machine\"}'::jsonb
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
                {"latency_seconds": latency_seconds, "usage": dict(usage)},
                ensure_ascii=False,
            ),
            operation_key=request_key,
            billing_basis=billing_basis,
            total_tokens=int(usage.get("total_tokens") or 0),
            latency=max(latency_seconds, 0.0),
            estimated_cost_usd=(
                "" if estimated_cost_usd is None else f"{estimated_cost_usd:.6f}"
            ),
            measured_cost_usd=(
                "" if measured_cost_usd is None else f"{measured_cost_usd:.6f}"
            ),
        )
        return receipt_id

    def record_run(
        self,
        run_date: str,
        report: Mapping[str, Any],
        *,
        finished: bool,
        status: str | None = None,
    ) -> None:
        run_status = status or ("COMPLETED" if finished else "RUNNING")
        if run_status not in {"RUNNING", "COMPLETED", "FAILED"}:
            raise ValueError(f"DAILY_RUN_STATUS_INVALID:{run_status}")
        if (run_status == "RUNNING") == finished:
            raise ValueError("DAILY_RUN_FINISH_STATE_MISMATCH")
        self.run(
            """
            INSERT INTO daily_run (
                run_date, started_at, finished_at, status, items, captures,
                statements, verdicts, held_statements, report
            ) VALUES (
                :'run_date'::date, :'started_at'::timestamptz,
                NULLIF(:'finished_at', '')::timestamptz, :'status',
                :'items'::integer, :'captures'::integer, :'statements'::integer,
                :'verdicts'::integer, :'held_statements'::integer, :'report'::jsonb
            )
            ON CONFLICT (run_date) DO UPDATE SET
                finished_at = EXCLUDED.finished_at,
                status = EXCLUDED.status,
                items = EXCLUDED.items,
                captures = EXCLUDED.captures,
                statements = EXCLUDED.statements,
                verdicts = EXCLUDED.verdicts,
                held_statements = EXCLUDED.held_statements,
                report = EXCLUDED.report;
            """,
            run_date=run_date,
            started_at=str(report.get("started_at") or _utc_now()),
            finished_at=_utc_now() if finished else "",
            status=run_status,
            items=int(report.get("items", 0)),
            captures=int(report.get("captures", 0)),
            statements=int(report.get("statements", 0)),
            verdicts=int(report.get("verdicts", 0)),
            held_statements=int(report.get("held_statements", 0)),
            report=json.dumps(dict(report), ensure_ascii=False),
        )
