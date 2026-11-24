"""Persistence for DP-638 records; shared source/content/capture stores remain authoritative."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.daily_store_contracts import (
    CLAIM_NATURES,
    FACTUAL_VERDICTS,
    STATEMENT_STATUSES,
)
from dichiarazioni_pubbliche.daily_store_reads import DailyStoreReadMixin
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class DailyCaptureRecord:
    """Reference to an existing capture plus the normalized-text fingerprint."""

    id: str
    content_capture_id: str
    content_id: str
    source_id: str
    kind: str
    url: str
    char_count: int
    content_sha256: str
    text_sha256: str
    media_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "id",
            "content_capture_id",
            "content_id",
            "source_id",
            "kind",
            "url",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"DAILY_CAPTURE_FIELD_REQUIRED:{field_name}")
        parsed = urlsplit(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("DAILY_CAPTURE_URL_INVALID")
        if isinstance(self.char_count, bool) or not isinstance(self.char_count, int) or self.char_count < 0:
            raise ValueError("DAILY_CAPTURE_CHAR_COUNT_INVALID")
        if not _SHA256_RE.fullmatch(self.content_sha256):
            raise ValueError("DAILY_CAPTURE_CONTENT_SHA256_INVALID")
        if not _SHA256_RE.fullmatch(self.text_sha256):
            raise ValueError("DAILY_CAPTURE_TEXT_SHA256_INVALID")
        if self.media_type is not None:
            base_media_type = (
                self.media_type.split(";", 1)[0].strip().lower()
                if isinstance(self.media_type, str)
                else ""
            )
            if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", base_media_type):
                raise ValueError("DAILY_CAPTURE_MEDIA_TYPE_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("DAILY_CAPTURE_METADATA_INVALID")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_use_metadata(
    source_use_guard: SourceFamilyUseGuard,
    capture: DailyCaptureRecord,
) -> dict[str, str]:
    source_use_guard.bind_capture(content_id=capture.content_id, url=capture.url)
    source_use_guard.bind_fetched(final_url=capture.url)
    decision = source_use_guard.require(
        "EXTRACT_CANDIDATES",
        content_sha256=capture.content_sha256,
        media_type=capture.media_type,
    )
    if (
        not decision.permitted
        or not decision.record_id
        or not decision.decision_fingerprint
    ):
        raise ValueError("DAILY_CAPTURE_SOURCE_USE_NOT_PROVEN")
    return {
        "use": decision.use,
        "status": decision.status,
        "reason_code": decision.reason_code,
        "action_code": decision.action_code,
        "record_id": decision.record_id,
        "decision_fingerprint": decision.decision_fingerprint,
    }


class DailyStore(DailyStoreReadMixin, PsqlRuntime):
    """Writes only DP-638 tables and rechecks capture rights at each use."""

    def save_capture(
        self,
        capture: DailyCaptureRecord,
        *,
        captured_text: str,
        source_use_guard: SourceFamilyUseGuard,
    ) -> bool:
        """Link an authorized content_capture; captured_text must come from its parser."""
        if len(captured_text) != capture.char_count:
            raise ValueError("DAILY_CAPTURE_TEXT_CHAR_COUNT_MISMATCH")
        if _sha256_text(captured_text) != capture.text_sha256:
            raise ValueError("DAILY_CAPTURE_TEXT_HASH_MISMATCH")
        use_decision = _source_use_metadata(source_use_guard, capture)
        metadata = dict(capture.metadata)
        metadata["source_use_decision"] = use_decision
        raw = self.run(
            """
            INSERT INTO daily_capture (
                id, content_id, content_capture_id, source_id, capture_kind, url,
                char_count, content_sha256, text_sha256, metadata
            )
            SELECT :'id', item.id, existing_capture.id, item.source_id, :'kind',
                   existing_capture.final_url, :'char_count'::integer,
                   existing_capture.content_sha256, :'text_sha256', :'metadata'::jsonb
            FROM content_capture existing_capture
            JOIN content_item item ON item.id = existing_capture.content_id
            JOIN source source ON source.id = item.source_id
            WHERE existing_capture.id = :'content_capture_id'
              AND existing_capture.content_id = :'content_id'
              AND item.source_id = :'source_id'
              AND existing_capture.final_url = :'url'
              AND existing_capture.content_sha256 = :'content_sha256'
              AND existing_capture.media_type IS NOT DISTINCT FROM NULLIF(:'media_type', '')
              AND lower(source.source_type) NOT IN ('public_rss', 'rss')
              AND existing_capture.rights_status = 'CLEARED'
              AND existing_capture.hold_status = 'NONE'
              AND existing_capture.retention_class IN ('DURABLE_PRIVATE', 'DURABLE_PROVENANCE')
              AND existing_capture.status = 'CAPTURED'
              AND existing_capture.body_ref IS NOT NULL
              AND existing_capture.body_purged_at IS NULL
            ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            id=capture.id,
            content_capture_id=capture.content_capture_id,
            content_id=capture.content_id,
            source_id=capture.source_id,
            kind=capture.kind,
            url=capture.url,
            char_count=capture.char_count,
            content_sha256=capture.content_sha256,
            text_sha256=capture.text_sha256,
            media_type=capture.media_type or "",
            metadata=json.dumps(metadata, ensure_ascii=False),
        )
        return bool(raw.strip())

    def save_statement(
        self,
        row: Mapping[str, Any],
        *,
        capture: DailyCaptureRecord,
        captured_text: str,
        source_use_guard: SourceFamilyUseGuard,
    ) -> bool:
        """Persist a quote verified against the same normalized text and current rights."""
        status = str(row.get("status") or "CANDIDATE").strip().upper()
        claim_nature = str(row.get("claim_nature") or "").strip().upper()
        if status not in STATEMENT_STATUSES:
            raise ValueError(f"DAILY_STATEMENT_STATUS_INVALID:{status}")
        if not claim_nature:
            raise ValueError("DAILY_STATEMENT_NATURE_REQUIRED")
        if claim_nature not in CLAIM_NATURES:
            raise ValueError(f"DAILY_STATEMENT_NATURE_INVALID:{claim_nature}")
        quote = str(row.get("quote") or "")
        quote_offset = row.get("quote_offset")
        if isinstance(quote_offset, bool) or not isinstance(quote_offset, int) or quote_offset < 0:
            raise ValueError("DAILY_STATEMENT_QUOTE_OFFSET_INVALID")
        if not quote or captured_text[quote_offset : quote_offset + len(quote)] != quote:
            raise ValueError("DAILY_STATEMENT_QUOTE_NOT_IN_CAPTURE")
        if len(captured_text) != capture.char_count:
            raise ValueError("DAILY_STATEMENT_CAPTURE_CHAR_COUNT_MISMATCH")
        if _sha256_text(captured_text) != capture.text_sha256:
            raise ValueError("DAILY_STATEMENT_CAPTURE_TEXT_HASH_MISMATCH")
        if (
            str(row.get("capture_id") or "") != capture.id
            or str(row.get("content_id") or "") != capture.content_id
            or str(row.get("source_id") or "") != capture.source_id
            or str(row.get("source_url") or "") != capture.url
        ):
            raise ValueError("DAILY_STATEMENT_CAPTURE_BINDING_MISMATCH")

        use_decision = _source_use_metadata(source_use_guard, capture)
        metadata = dict(row.get("metadata") or {})
        metadata["source_use_decision"] = use_decision
        raw = self.run(
            """
            INSERT INTO daily_statement (
                id, content_id, capture_id, source_id, source_url, source_title,
                source_publisher, source_published_at, statement_date, quote,
                quote_offset, moment_label, speaker_name, speaker_role, speaker_key,
                topic, claim_nature, status, status_reason, extraction_model, metadata
            )
            SELECT :'id', daily_capture.content_id, daily_capture.id,
                   daily_capture.source_id, daily_capture.url, :'source_title',
                   :'source_publisher', NULLIF(:'source_published_at', '')::timestamptz,
                   :'statement_date'::date, :'quote', :'quote_offset'::integer,
                   :'moment_label', :'speaker_name', :'speaker_role', :'speaker_key',
                   :'topic', :'claim_nature', :'status', :'status_reason',
                   :'extraction_model', :'metadata'::jsonb
            FROM daily_capture
            JOIN content_capture existing_capture
              ON existing_capture.id = daily_capture.content_capture_id
            JOIN source ON source.id = daily_capture.source_id
            WHERE daily_capture.id = :'capture_id'
              AND daily_capture.content_id = :'content_id'
              AND daily_capture.source_id = :'source_id'
              AND daily_capture.url = :'source_url'
              AND daily_capture.content_capture_id = :'content_capture_id'
              AND daily_capture.content_sha256 = :'content_sha256'
              AND daily_capture.text_sha256 = :'text_sha256'
              AND existing_capture.media_type IS NOT DISTINCT FROM NULLIF(:'media_type', '')
              AND lower(source.source_type) NOT IN ('public_rss', 'rss')
              AND existing_capture.rights_status = 'CLEARED'
              AND existing_capture.hold_status = 'NONE'
              AND existing_capture.retention_class IN ('DURABLE_PRIVATE', 'DURABLE_PROVENANCE')
              AND existing_capture.status = 'CAPTURED'
              AND existing_capture.body_ref IS NOT NULL
              AND existing_capture.body_purged_at IS NULL
            ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            id=str(row.get("id") or ""),
            capture_id=capture.id,
            content_capture_id=capture.content_capture_id,
            content_id=capture.content_id,
            source_id=capture.source_id,
            source_url=capture.url,
            content_sha256=capture.content_sha256,
            text_sha256=capture.text_sha256,
            media_type=capture.media_type or "",
            source_title=str(row.get("source_title") or ""),
            source_publisher=str(row.get("source_publisher") or ""),
            source_published_at=str(row.get("source_published_at") or ""),
            statement_date=str(row.get("statement_date") or ""),
            quote=quote,
            quote_offset=quote_offset,
            moment_label=str(row.get("moment_label") or ""),
            speaker_name=str(row.get("speaker_name") or ""),
            speaker_role=str(row.get("speaker_role") or ""),
            speaker_key=str(row.get("speaker_key") or ""),
            topic=str(row.get("topic") or ""),
            claim_nature=claim_nature,
            status=status,
            status_reason=str(row.get("status_reason") or ""),
            extraction_model=str(row.get("extraction_model") or ""),
            metadata=json.dumps(metadata, ensure_ascii=False),
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
        value = str(verdict.get("verdict") or "").strip().upper()
        if value not in FACTUAL_VERDICTS:
            raise ValueError(f"DAILY_VERDICT_INVALID:{value}")
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
        models = str(verdict.get("models") or "").strip()
        if model_calls < 2 or duration_seconds < 0 or not models:
            raise ValueError("DAILY_VERDICT_METRICS_INVALID")
        raw = self.run(
            """
            INSERT INTO daily_verdict (
                statement_id, claim_nature, verdict, explanation, evidence,
                first_pass, check_pass, agreement, models, model_calls, duration_seconds
            )
            SELECT statement.id, statement.claim_nature, :'verdict',
                   :'explanation', :'evidence'::jsonb, :'first_pass'::jsonb,
                   :'check_pass'::jsonb, :'agreement', :'models',
                   :'model_calls'::integer, :'duration_seconds'::numeric
            FROM daily_statement statement
            WHERE statement.id = :'statement_id'
              AND statement.claim_nature = 'FACTUAL'
              AND statement.status = 'CANDIDATE'
            ON CONFLICT (statement_id) DO NOTHING
            RETURNING statement_id;
            """,
            statement_id=statement_id,
            verdict=value,
            explanation=str(verdict.get("explanation") or ""),
            evidence=json.dumps(evidence, ensure_ascii=False),
            first_pass=json.dumps(first_pass, ensure_ascii=False),
            check_pass=json.dumps(check_pass, ensure_ascii=False),
            agreement=str(verdict.get("agreement") or ""),
            models=models,
            model_calls=model_calls,
            duration_seconds=duration_seconds,
        )
        return bool(raw.strip())

    def record_run(
        self,
        run_date: str,
        report: Mapping[str, Any],
        *,
        finished: bool,
        status: str | None = None,
        started_at: str | None = None,
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
            )
            VALUES (
                :'run_date'::date, :'started_at'::timestamptz,
                CASE WHEN :'finished' = 'true' THEN now() ELSE NULL END,
                :'status', :'items'::integer, :'captures'::integer,
                :'statements'::integer, :'verdicts'::integer,
                :'held_statements'::integer, :'report'::jsonb
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
            started_at=started_at or _utc_now(),
            finished="true" if finished else "false",
            status=run_status,
            items=int(report.get("items", 0)),
            captures=int(report.get("captures", 0)),
            statements=int(report.get("statements", 0)),
            verdicts=int(report.get("verdicts", 0)),
            held_statements=int(report.get("held_statements", 0)),
            report=json.dumps(dict(report), ensure_ascii=False),
        )
