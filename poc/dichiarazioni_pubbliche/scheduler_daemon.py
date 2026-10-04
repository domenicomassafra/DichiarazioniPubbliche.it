from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from dichiarazioni_pubbliche.scheduler import (
    deterministic_content_id,
    plan_initial_job,
    provisional_content_key,
)
from dichiarazioni_pubbliche.source_adapters import (
    SUPPORTED_SOURCE_KINDS,
    SourceAdapterError,
)
from dichiarazioni_pubbliche.source_watcher import discover_source, load_registry


FULL_SOURCE_MODE = "full-source"
SOURCE_DUE_MODE = "source-due"
MAX_DISCOVERED_ITEMS_PER_SOURCE = 20
MAX_NEW_JOBS_PER_FULL_SOURCE_RUN = 20
MAX_FULL_SOURCE_RUNS_PER_SOURCE_DAY = 1
MAX_SOURCES_PER_FULL_SOURCE_RUN = 1000


@dataclass(frozen=True)
class RuntimeBudget:
    max_new_jobs_per_run: int = 20
    max_cost_usd_per_day: float = 5.0
    max_cost_usd_per_source_day: float = 1.0
    max_discovered_items_per_source: int = MAX_DISCOVERED_ITEMS_PER_SOURCE


@dataclass(frozen=True)
class SourceHealthState:
    checked_at: datetime | None
    consecutive_failures: int


@dataclass(frozen=True)
class PollOutcome:
    source_id: str
    status: str
    discovered: int = 0
    content_upserts: int = 0
    jobs_enqueued: int = 0
    duplicate_jobs: int = 0
    budget_blocked: int = 0
    omitted_items: int = 0
    error: str | None = None
    error_category: str | None = None
    receipt_id: str | None = None


@dataclass(frozen=True)
class SourceRunContext:
    run_id: str
    mode: str
    run_date: str
    effective_config_hash: str
    diagnostic: bool = False


@dataclass
class _RunBudgetState:
    jobs_enqueued: int = 0


class FullSourceResult(list):
    def __init__(
        self,
        outcomes: list[PollOutcome] | tuple[PollOutcome, ...] = (),
        *,
        run_id: str,
        mode: str,
        run_date: str,
        effective_config_hash: str,
        status: str,
        started_at: str | None = None,
        completed_at: str | None = None,
        diagnostic: bool = False,
    ) -> None:
        super().__init__(outcomes)
        self.run_id = run_id
        self.mode = mode
        self.run_date = run_date
        self.effective_config_hash = effective_config_hash
        self.config_hash = effective_config_hash
        self.status = status
        self.started_at = started_at
        self.completed_at = completed_at
        self.diagnostic = diagnostic

    @property
    def source_results(self) -> list[PollOutcome]:
        return list(self)

    @property
    def counters(self) -> dict[str, int]:
        return {
            "source_count": len(self),
            "discovered": sum(row.discovered for row in self),
            "content_upserts": sum(row.content_upserts for row in self),
            "jobs_enqueued": sum(row.jobs_enqueued for row in self),
            "duplicate_jobs": sum(row.duplicate_jobs for row in self),
            "budget_blocked": sum(row.budget_blocked for row in self),
            "omitted_items": sum(row.omitted_items for row in self),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "run_date": self.run_date,
            "effective_config_hash": self.effective_config_hash,
            "status": self.status,
            "diagnostic": self.diagnostic,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "counters": self.counters,
            "sources": [asdict(row) for row in self],
        }


PollRunResult = FullSourceResult


def _clean(value: object) -> str:
    return str(value if value is not None else "").replace("\x00", "")


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonicalize(item) for item in value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_registry_policy_hash(
    registry: dict[str, Any],
    *,
    budget: RuntimeBudget | None = None,
    limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
    force: bool = False,
) -> str:
    policy = budget or RuntimeBudget()
    material = {
        "registry": registry,
        "policy": {
            "limit": max(int(limit), 0),
            "max_discovered_items_per_source": min(
                max(int(policy.max_discovered_items_per_source), 0),
                MAX_DISCOVERED_ITEMS_PER_SOURCE,
            ),
            "max_new_jobs_per_run": min(
                max(int(policy.max_new_jobs_per_run), 0),
                MAX_NEW_JOBS_PER_FULL_SOURCE_RUN,
            ),
            "max_cost_usd_per_day": float(policy.max_cost_usd_per_day),
            "max_cost_usd_per_source_day": float(policy.max_cost_usd_per_source_day),
            "max_sources_per_run": MAX_SOURCES_PER_FULL_SOURCE_RUN,
            "force": bool(force),
        },
    }
    return hashlib.sha256(_canonical_json(material).encode()).hexdigest()


effective_config_hash = canonical_registry_policy_hash


def utc_run_date(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).date().isoformat()


def deterministic_run_id(mode: str, run_date: str, config_hash: str) -> str:
    material = f"{str(mode).strip().lower()}\0{run_date}\0{config_hash}"
    return "source-poll:" + hashlib.sha256(material.encode()).hexdigest()


def deterministic_source_receipt_id(run_id: str, source_id: str) -> str:
    material = f"{run_id}\0{source_id}"
    return "source-poll-source:" + hashlib.sha256(material.encode()).hexdigest()


def _error_category(value: object) -> str:
    if isinstance(value, TimeoutError):
        return "TIMEOUT"
    text = str(value or "").upper()
    if any(marker in text for marker in ("DISCOVERY_URL", "NONPUBLIC_IP", "SSRF", "PRIVATE_IP")):
        return "SSRF_REJECTED"
    if any(marker in text for marker in ("PARSE", "XML", "MALFORMED", "FEED")):
        return "MALFORMED_RESPONSE"
    if "UNSUPPORTED" in text:
        return "UNSUPPORTED"
    if "BUDGET" in text or "COST" in text:
        return "BUDGET_BLOCKED"
    name = type(value).__name__ if isinstance(value, BaseException) else ""
    if "PARSE" in name.upper():
        return "MALFORMED_RESPONSE"
    category = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return category[:80] or "SOURCE_FAILURE"


def _normalized_timestamp(value: str | None) -> str:
    value = _clean(value).strip()
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _utc_datetime(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def scheduler_ingest_plan(content: Any) -> dict[str, Any]:
    if content.platform == "podcast_rss":
        return {
            "action": "RESOLVE_PLATFORM_TRANSCRIPT_THEN_AUDIO",
            "download_media": False,
            "prefer_audio_only": True,
        }
    if content.platform == "youtube":
        return {
            "action": "PROBE_PLATFORM_TRANSCRIPT",
            "download_media": False,
        }
    return {"action": "DISCOVERY_ONLY", "download_media": False}


def source_due(
    health: SourceHealthState,
    *,
    poll_minutes: int,
    now: datetime,
) -> bool:
    if health.checked_at is None:
        return True
    base = max(int(poll_minutes), 1)
    backoff = min(2 ** max(health.consecutive_failures, 0), 16)
    return now >= health.checked_at + timedelta(minutes=base * backoff)


class PsqlStore:
    def __init__(self, database_url: str | None = None, psql: str = "psql") -> None:
        self.database_url = database_url or None
        self.psql = psql

    def _run(self, sql: str, **variables: object) -> str:
        args = [self.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
        if self.database_url:
            args.extend(["--dbname", self.database_url])
        for key, value in variables.items():
            args.extend(["-v", f"{key}={_clean(value)}"])
        proc = subprocess.run(
            args,
            input=sql,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            message = detail[-1] if detail else f"psql exited {proc.returncode}"
            raise RuntimeError(message[:1000])
        return proc.stdout.strip()

    def upsert_source(self, source: dict[str, Any]) -> None:
        metadata = json.dumps(
            {"priority": source.get("priority"), "registry_schema": 1},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._run(
            """
            INSERT INTO source (
                id, canonical_name, source_type, canonical_url,
                language, country_code, metadata
            ) VALUES (
                :'id', :'name', :'kind', NULLIF(:'url',''),
                'it', 'IT', :'metadata'::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                source_type = EXCLUDED.source_type,
                canonical_url = EXCLUDED.canonical_url,
                metadata = source.metadata || EXCLUDED.metadata,
                updated_at = now();
            """,
            id=source["id"],
            name=source.get("name", source["id"]),
            kind=source.get("kind", "unknown"),
            url=source.get("channel_url") or source.get("discovery_url") or "",
            metadata=metadata,
        )

    def health(self, source_id: str) -> SourceHealthState:
        raw = self._run(
            """
            SELECT COALESCE(extract(epoch FROM checked_at)::bigint::text, ''),
                   consecutive_failures::text
            FROM source_health
            WHERE source_id = :'source_id';
            """,
            source_id=source_id,
        )
        if not raw:
            return SourceHealthState(None, 0)
        epoch_raw, failures_raw = raw.split("|", 1)
        checked_at = (
            datetime.fromtimestamp(int(epoch_raw), tz=timezone.utc)
            if epoch_raw
            else None
        )
        return SourceHealthState(checked_at, int(failures_raw))

    def cost_today(self, source_id: str | None = None) -> float:
        source_filter = ""
        variables: dict[str, object] = {}
        if source_id is not None:
            source_filter = "AND c.source_id = :'source_id'"
            variables["source_id"] = source_id
        raw = self._run(
            f"""
            SELECT COALESCE(sum(r.estimated_cost_usd), 0)::text
            FROM provider_receipt r
            LEFT JOIN content_item c ON c.id = r.content_id
            WHERE COALESCE(r.completed_at, r.started_at, now()) >= date_trunc('day', now())
            {source_filter};
            """,
            **variables,
        )
        return float(raw or 0)

    def resolve_content_id(
        self,
        platform: str,
        external_id: str,
        fallback_id: str,
    ) -> str:
        raw = self._run(
            """
            SELECT content_id
            FROM content_locator
            WHERE platform = :'platform' AND external_id = :'external_id'
            LIMIT 1;
            """,
            platform=platform,
            external_id=external_id,
        )
        return raw or fallback_id

    def upsert_content(self, content: Any, content_id: str) -> None:
        metadata = json.dumps(
            {
                "platform": content.platform,
                "author": content.author,
                "media_type": content.media_type,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._run(
            """
            INSERT INTO content_item (
                id, source_id, source_external_id, canonical_url, title,
                description, language, published_at, duration_ms, metadata
            ) VALUES (
                :'content_id', :'source_id', :'external_id', :'url', :'title',
                NULLIF(:'description',''), 'it', NULLIF(:'published_at','')::timestamptz,
                NULLIF(:'duration_ms','')::bigint, :'metadata'::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                canonical_url = CASE
                    WHEN content_item.canonical_url = '' THEN EXCLUDED.canonical_url
                    ELSE content_item.canonical_url
                END,
                title = COALESCE(NULLIF(EXCLUDED.title, ''), content_item.title),
                description = COALESCE(EXCLUDED.description, content_item.description),
                published_at = COALESCE(content_item.published_at, EXCLUDED.published_at),
                duration_ms = COALESCE(content_item.duration_ms, EXCLUDED.duration_ms),
                metadata = content_item.metadata || EXCLUDED.metadata;

            INSERT INTO content_locator (
                content_id, platform, external_id, canonical_url, metadata
            ) VALUES (
                :'content_id', :'platform', :'external_id', :'url', '{}'::jsonb
            )
            ON CONFLICT (platform, external_id) DO UPDATE SET
                content_id = EXCLUDED.content_id,
                canonical_url = EXCLUDED.canonical_url;
            """,
            content_id=content_id,
            source_id=content.source_id,
            external_id=content.external_id,
            url=content.canonical_url,
            title=content.title,
            description=content.description or "",
            published_at=_normalized_timestamp(content.published_at),
            duration_ms=(
                str(content.duration_seconds * 1000)
                if content.duration_seconds is not None
                else ""
            ),
            metadata=metadata,
            platform=content.platform,
        )

    def enqueue(self, job: Any, content_id: str) -> bool:
        payload = json.dumps(job.payload, ensure_ascii=False, separators=(",", ":"))
        raw = self._run(
            """
            SELECT enqueue_processing_job(
                :'job_id', :'content_id', :'job_type', :'payload'::jsonb
            )::text;
            """,
            job_id=job.job_id,
            content_id=content_id,
            job_type=job.job_type,
            payload=payload,
        )
        return raw.lower() in {"t", "true", "1"}

    def mark_success(self, source_id: str, last_item_at: str) -> None:
        self._run(
            """
            INSERT INTO source_health (
                source_id, status, last_success_at, last_item_at,
                consecutive_failures, last_error, checked_at
            ) VALUES (
                :'source_id', 'HEALTHY', now(), NULLIF(:'last_item_at','')::timestamptz,
                0, NULL, now()
            )
            ON CONFLICT (source_id) DO UPDATE SET
                status = 'HEALTHY',
                last_success_at = now(),
                last_item_at = COALESCE(EXCLUDED.last_item_at, source_health.last_item_at),
                consecutive_failures = 0,
                last_error = NULL,
                checked_at = now();
            """,
            source_id=source_id,
            last_item_at=last_item_at,
        )

    def mark_failure(self, source_id: str, error: str) -> None:
        self._run(
            """
            INSERT INTO source_health (
                source_id, status, consecutive_failures, last_error, checked_at
            ) VALUES (
                :'source_id', 'DEGRADED', 1, :'error', now()
            )
            ON CONFLICT (source_id) DO UPDATE SET
                consecutive_failures = source_health.consecutive_failures + 1,
                status = CASE
                    WHEN source_health.consecutive_failures + 1 >= 3 THEN 'FAILED'
                    ELSE 'DEGRADED'
                END,
                last_error = EXCLUDED.last_error,
                checked_at = now();
            """,
            source_id=source_id,
            error=error[:1000],
        )

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

    def start_source_poll_run(
        self,
        *,
        run_id: str,
        mode: str,
        run_date: str,
        effective_config_hash: str,
        diagnostic: bool,
    ) -> str:
        return self._run(
            """
            INSERT INTO source_poll_run (
                id, mode, run_date, effective_config_hash, status, diagnostic
            ) VALUES (
                :'run_id', :'mode', :'run_date'::date,
                :'effective_config_hash', 'RUNNING', :'diagnostic'::boolean
            )
            ON CONFLICT (mode, run_date, effective_config_hash) DO UPDATE SET
                status = CASE
                    WHEN source_poll_run.status = 'FAILED' THEN 'RUNNING'
                    ELSE source_poll_run.status
                END,
                started_at = CASE
                    WHEN source_poll_run.status = 'FAILED' THEN now()
                    ELSE source_poll_run.started_at
                END,
                completed_at = CASE
                    WHEN source_poll_run.status = 'FAILED' THEN NULL
                    ELSE source_poll_run.completed_at
                END
            RETURNING status;
            """,
            run_id=run_id,
            mode=mode,
            run_date=run_date,
            effective_config_hash=effective_config_hash,
            diagnostic="true" if diagnostic else "false",
        )

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

    def source_poll_day_status(
        self,
        *,
        run_date: str,
        source_ids: list[str],
        exclude_run_id: str,
    ) -> dict[str, dict[str, str]]:
        raw = self._run(
            """
            SELECT COALESCE(json_object_agg(source_id, row_to_json(x))::text, '{}')
            FROM (
                SELECT DISTINCT ON (child.source_id)
                    child.source_id,
                    child.run_id,
                    child.status
                FROM source_poll_run_source child
                JOIN source_poll_run run ON run.id = child.run_id
                WHERE run.mode = :'mode'
                  AND run.run_date = :'run_date'::date
                  AND run.status IN ('COMPLETED', 'FAILED')
                  AND run.id <> :'exclude_run_id'
                  AND child.source_id = ANY(string_to_array(:'source_ids', ',') )
                ORDER BY child.source_id, run.completed_at DESC NULLS LAST, run.started_at DESC
            ) x;
            """,
            mode=FULL_SOURCE_MODE,
            run_date=run_date,
            exclude_run_id=exclude_run_id,
            source_ids=",".join(sorted(source_ids)),
        )
        return {
            str(key): dict(value)
            for key, value in (json.loads(raw or "{}").items())
        }

    def commit_source_poll(
        self,
        source: dict[str, Any],
        items: list[Any],
        *,
        context: SourceRunContext,
        max_new_jobs: int,
        cost_blocked: bool,
        latest: str,
        omitted_items: int,
        started_at: datetime,
    ) -> dict[str, int | str | bool]:
        rows: list[dict[str, Any]] = []
        for content in items:
            key = provisional_content_key(content)
            job = plan_initial_job(content, scheduler_ingest_plan(content))
            rows.append(
                {
                    "source_id": content.source_id,
                    "platform": content.platform,
                    "external_id": content.external_id,
                    "content_id": deterministic_content_id(key),
                    "title": content.title,
                    "description": content.description or "",
                    "canonical_url": content.canonical_url,
                    "published_at": _normalized_timestamp(content.published_at),
                    "duration_ms": (
                        content.duration_seconds * 1000
                        if content.duration_seconds is not None
                        else None
                    ),
                    "metadata": {
                        "platform": content.platform,
                        "author": content.author,
                        "media_type": content.media_type,
                    },
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "payload": job.payload,
                }
            )
        metadata = json.dumps(
            {"priority": source.get("priority"), "registry_schema": 1},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raw = self._run(
            """
            BEGIN;
            INSERT INTO source (
                id, canonical_name, source_type, canonical_url,
                language, country_code, metadata
            ) VALUES (
                :'source_id', :'source_name', :'source_kind',
                NULLIF(:'source_url',''), 'it', 'IT', :'source_metadata'::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                source_type = EXCLUDED.source_type,
                canonical_url = EXCLUDED.canonical_url,
                metadata = source.metadata || EXCLUDED.metadata,
                updated_at = now();
            CREATE TEMP TABLE _source_poll_input (
                ordinal integer,
                source_id text,
                platform text,
                external_id text,
                content_id text,
                title text,
                description text,
                canonical_url text,
                published_at text,
                duration_ms bigint,
                metadata jsonb,
                job_id text,
                job_type text,
                payload jsonb
            ) ON COMMIT DROP;
            INSERT INTO _source_poll_input (
                ordinal, source_id, platform, external_id, content_id,
                title, description, canonical_url, published_at, duration_ms,
                metadata, job_id, job_type, payload
            )
            SELECT
                ordinal::integer,
                value->>'source_id',
                value->>'platform',
                value->>'external_id',
                value->>'content_id',
                value->>'title',
                value->>'description',
                value->>'canonical_url',
                value->>'published_at',
                NULLIF(value->>'duration_ms','')::bigint,
                value->'metadata',
                value->>'job_id',
                value->>'job_type',
                value->'payload'
            FROM jsonb_array_elements(:'items'::jsonb)
                WITH ORDINALITY AS item(value, ordinal);
            UPDATE _source_poll_input i
            SET content_id = c.id
            FROM content_item c
            WHERE c.source_id = i.source_id
              AND c.source_external_id = i.external_id;
            UPDATE _source_poll_input i
            SET content_id = locator.content_id
            FROM content_locator locator
            WHERE locator.platform = i.platform
              AND locator.external_id = i.external_id;
            INSERT INTO content_item (
                id, source_id, source_external_id, canonical_url, title,
                description, language, published_at, duration_ms, metadata
            )
            SELECT
                content_id, source_id, external_id, canonical_url, title,
                NULLIF(description, ''), 'it', NULLIF(published_at, '')::timestamptz,
                duration_ms, metadata
            FROM _source_poll_input
            ON CONFLICT (id) DO UPDATE SET
                canonical_url = CASE
                    WHEN content_item.canonical_url = '' THEN EXCLUDED.canonical_url
                    ELSE content_item.canonical_url
                END,
                title = COALESCE(NULLIF(EXCLUDED.title, ''), content_item.title),
                description = COALESCE(EXCLUDED.description, content_item.description),
                published_at = COALESCE(content_item.published_at, EXCLUDED.published_at),
                duration_ms = COALESCE(content_item.duration_ms, EXCLUDED.duration_ms),
                metadata = content_item.metadata || EXCLUDED.metadata;
            INSERT INTO content_locator (
                content_id, platform, external_id, canonical_url, metadata
            )
            SELECT content_id, platform, external_id, canonical_url, '{}'::jsonb
            FROM _source_poll_input
            ON CONFLICT (platform, external_id) DO UPDATE SET
                content_id = EXCLUDED.content_id,
                canonical_url = EXCLUDED.canonical_url;
            CREATE TEMP TABLE _source_poll_job_result ON COMMIT DROP AS
            WITH ordered AS (
                SELECT
                    i.*,
                    row_number() OVER (ORDER BY ordinal)::integer AS rn,
                    NOT EXISTS (
                        SELECT 1 FROM processing_job existing
                        WHERE existing.id = i.job_id
                    ) AS is_new
                FROM _source_poll_input i
            ),
            marked AS (
                SELECT
                    ordered.*,
                    (
                        NOT :'cost_blocked'::boolean
                        AND sum(
                            CASE WHEN is_new THEN 1 ELSE 0 END
                        ) OVER (
                            ORDER BY rn
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        ) <= :'max_new_jobs'::integer
                    ) AS may_enqueue
                FROM ordered
            ),
            called AS (
                SELECT
                    marked.*,
                    CASE
                        WHEN may_enqueue THEN enqueue_processing_job(
                            job_id, content_id, job_type, payload
                        )
                        ELSE false
                    END AS inserted
                FROM marked
            )
            SELECT * FROM called;
            INSERT INTO source_health (
                source_id, status, last_success_at, last_item_at,
                consecutive_failures, last_error, checked_at
            )
            VALUES (
                :'source_id', 'HEALTHY', now(), NULLIF(:'latest','')::timestamptz,
                0, NULL, now()
            )
            ON CONFLICT (source_id) DO UPDATE SET
                status = 'HEALTHY',
                last_success_at = now(),
                last_item_at = COALESCE(EXCLUDED.last_item_at, source_health.last_item_at),
                consecutive_failures = 0,
                last_error = NULL,
                checked_at = now();
            WITH counts AS (
                SELECT
                    count(*)::integer AS discovered,
                    count(*) FILTER (WHERE inserted)::integer AS jobs_enqueued,
                    count(*) FILTER (WHERE may_enqueue AND NOT inserted)::integer AS duplicate_jobs,
                    count(*) FILTER (WHERE NOT may_enqueue)::integer AS budget_blocked
                FROM _source_poll_job_result
            )
            INSERT INTO source_poll_run_source (
                id, run_id, source_id, mode, run_date, effective_config_hash,
                diagnostic, status, discovered, content_upserts, jobs_enqueued,
                duplicate_jobs, budget_blocked, omitted_items, error_category,
                started_at, completed_at
            )
            SELECT
                :'receipt_id', :'run_id', :'source_id', :'mode', :'run_date'::date,
                :'effective_config_hash', :'diagnostic'::boolean,
                CASE WHEN budget_blocked > 0 THEN 'BUDGET_BLOCKED' ELSE 'HEALTHY' END,
                discovered, discovered, jobs_enqueued, duplicate_jobs,
                budget_blocked, :'omitted_items', NULL,
                :'started_at'::timestamptz, now()
            FROM counts
            ON CONFLICT (run_id, source_id) DO UPDATE SET
                status = EXCLUDED.status,
                discovered = EXCLUDED.discovered,
                content_upserts = EXCLUDED.content_upserts,
                jobs_enqueued = EXCLUDED.jobs_enqueued,
                duplicate_jobs = EXCLUDED.duplicate_jobs,
                budget_blocked = EXCLUDED.budget_blocked,
                omitted_items = EXCLUDED.omitted_items,
                error_category = EXCLUDED.error_category,
                completed_at = EXCLUDED.completed_at;
            SELECT json_build_object(
                'content_upserts', (SELECT count(*) FROM _source_poll_input),
                'jobs_enqueued', (SELECT count(*) FROM _source_poll_job_result WHERE inserted),
                'duplicate_jobs', (SELECT count(*) FROM _source_poll_job_result WHERE may_enqueue AND NOT inserted),
                'budget_blocked', (SELECT count(*) FROM _source_poll_job_result WHERE NOT may_enqueue),
                'latest', :'latest',
                'health_committed', true
            )::text;
            COMMIT;
            """,
            source_id=source["id"],
            source_name=source.get("name", source["id"]),
            source_kind=source.get("kind", "unknown"),
            source_url=source.get("channel_url") or source.get("discovery_url") or "",
            source_metadata=metadata,
            items=json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
            receipt_id=deterministic_source_receipt_id(context.run_id, source["id"]),
            run_id=context.run_id,
            mode=context.mode,
            run_date=context.run_date,
            effective_config_hash=context.effective_config_hash,
            diagnostic="true" if context.diagnostic else "false",
            cost_blocked="true" if cost_blocked else "false",
            max_new_jobs=min(max(int(max_new_jobs), 0), MAX_NEW_JOBS_PER_FULL_SOURCE_RUN),
            latest=latest,
            omitted_items=max(int(omitted_items), 0),
            started_at=_utc_datetime(started_at).isoformat(),
        )
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("SOURCE_POLL_COMMIT_EMPTY")
        return json.loads(lines[-1])

    def record_source_poll_source(
        self,
        source: dict[str, Any],
        outcome: PollOutcome,
        *,
        context: SourceRunContext,
        started_at: datetime,
        completed_at: datetime,
        failure_category: str = "",
    ) -> None:
        metadata = json.dumps(
            {"priority": source.get("priority"), "registry_schema": 1},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        failure_sql = ""
        if failure_category:
            failure_sql = """
            INSERT INTO source_health (
                source_id, status, consecutive_failures, last_error, checked_at
            ) VALUES (
                :'source_id', 'DEGRADED', 1, :'failure_category', now()
            )
            ON CONFLICT (source_id) DO UPDATE SET
                consecutive_failures = source_health.consecutive_failures + 1,
                status = CASE
                    WHEN source_health.consecutive_failures + 1 >= 3 THEN 'FAILED'
                    ELSE 'DEGRADED'
                END,
                last_error = EXCLUDED.last_error,
                checked_at = now();
            """
        self._run(
            f"""
            BEGIN;
            INSERT INTO source (
                id, canonical_name, source_type, canonical_url,
                language, country_code, metadata
            ) VALUES (
                :'source_id', :'source_name', :'source_kind',
                NULLIF(:'source_url',''), 'it', 'IT', :'source_metadata'::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                source_type = EXCLUDED.source_type,
                canonical_url = EXCLUDED.canonical_url,
                metadata = source.metadata || EXCLUDED.metadata,
                updated_at = now();
            INSERT INTO source_poll_run_source (
                id, run_id, source_id, mode, run_date, effective_config_hash,
                diagnostic, status, discovered, content_upserts, jobs_enqueued,
                duplicate_jobs, budget_blocked, omitted_items, error_category,
                started_at, completed_at
            ) VALUES (
                :'receipt_id', :'run_id', :'source_id', :'mode', :'run_date'::date,
                :'effective_config_hash', :'diagnostic'::boolean, :'status', :'discovered',
                :'content_upserts', :'jobs_enqueued', :'duplicate_jobs',
                :'budget_blocked', :'omitted_items', NULLIF(:'error_category',''),
                :'started_at'::timestamptz, :'completed_at'::timestamptz
            )
            ON CONFLICT (run_id, source_id) DO UPDATE SET
                status = EXCLUDED.status,
                discovered = EXCLUDED.discovered,
                content_upserts = EXCLUDED.content_upserts,
                jobs_enqueued = EXCLUDED.jobs_enqueued,
                duplicate_jobs = EXCLUDED.duplicate_jobs,
                budget_blocked = EXCLUDED.budget_blocked,
                omitted_items = EXCLUDED.omitted_items,
                error_category = EXCLUDED.error_category,
                completed_at = EXCLUDED.completed_at;
            {failure_sql}
            COMMIT;
            """,
            source_id=source["id"],
            source_name=source.get("name", source["id"]),
            source_kind=source.get("kind", "unknown"),
            source_url=source.get("channel_url") or source.get("discovery_url") or "",
            source_metadata=metadata,
            receipt_id=deterministic_source_receipt_id(context.run_id, source["id"]),
            run_id=context.run_id,
            mode=context.mode,
            run_date=context.run_date,
            effective_config_hash=context.effective_config_hash,
            diagnostic="true" if context.diagnostic else "false",
            status=outcome.status,
            discovered=max(int(outcome.discovered), 0),
            content_upserts=max(int(outcome.content_upserts), 0),
            jobs_enqueued=max(int(outcome.jobs_enqueued), 0),
            duplicate_jobs=max(int(outcome.duplicate_jobs), 0),
            budget_blocked=max(int(outcome.budget_blocked), 0),
            omitted_items=max(int(outcome.omitted_items), 0),
            error_category=outcome.error_category or "",
            started_at=_utc_datetime(started_at).isoformat(),
            completed_at=_utc_datetime(completed_at).isoformat(),
            failure_category=failure_category,
        )

    def complete_source_poll_run(
        self,
        *,
        run_id: str,
        status: str,
        source_count: int,
        discovered: int,
        content_upserts: int,
        jobs_enqueued: int,
        duplicate_jobs: int,
        budget_blocked: int,
        omitted_items: int,
        error_category: str,
        completed_at: datetime,
    ) -> None:
        self._run(
            """
            UPDATE source_poll_run
            SET status = :'status',
                source_count = :'source_count',
                discovered = :'discovered',
                content_upserts = :'content_upserts',
                jobs_enqueued = :'jobs_enqueued',
                duplicate_jobs = :'duplicate_jobs',
                budget_blocked = :'budget_blocked',
                omitted_items = :'omitted_items',
                error_category = NULLIF(:'error_category',''),
                completed_at = :'completed_at'::timestamptz
            WHERE id = :'run_id';
            """,
            run_id=run_id,
            status=status,
            source_count=max(int(source_count), 0),
            discovered=max(int(discovered), 0),
            content_upserts=max(int(content_upserts), 0),
            jobs_enqueued=max(int(jobs_enqueued), 0),
            duplicate_jobs=max(int(duplicate_jobs), 0),
            budget_blocked=max(int(budget_blocked), 0),
            omitted_items=max(int(omitted_items), 0),
            error_category=error_category,
            completed_at=_utc_datetime(completed_at).isoformat(),
        )


def _legacy_persist_items(
    source: dict[str, Any],
    items: list[Any],
    store: Any,
    *,
    cost_blocked: bool,
    budget: RuntimeBudget,
) -> dict[str, int | str]:
    upserts = 0
    enqueued = 0
    duplicates = 0
    blocked = 0
    latest = ""
    for content in items:
        key = provisional_content_key(content)
        fallback_id = deterministic_content_id(key)
        content_id = store.resolve_content_id(
            content.platform,
            content.external_id,
            fallback_id,
        )
        store.upsert_content(content, content_id)
        upserts += 1
        normalized_published = _normalized_timestamp(content.published_at)
        if normalized_published > latest:
            latest = normalized_published
        if cost_blocked or enqueued >= max(int(budget.max_new_jobs_per_run), 0):
            blocked += 1
            continue
        job = plan_initial_job(content, scheduler_ingest_plan(content))
        if store.enqueue(job, content_id):
            enqueued += 1
        else:
            duplicates += 1
    return {
        "content_upserts": upserts,
        "jobs_enqueued": enqueued,
        "duplicate_jobs": duplicates,
        "budget_blocked": blocked,
        "latest": latest,
    }


def _outcome_from_receipt(row: dict[str, Any]) -> PollOutcome:
    return PollOutcome(
        source_id=str(row.get("source_id") or ""),
        status=str(row.get("status") or "FAILED"),
        discovered=int(row.get("discovered") or 0),
        content_upserts=int(row.get("content_upserts") or 0),
        jobs_enqueued=int(row.get("jobs_enqueued") or 0),
        duplicate_jobs=int(row.get("duplicate_jobs") or 0),
        budget_blocked=int(row.get("budget_blocked") or 0),
        omitted_items=int(row.get("omitted_items") or 0),
        error=row.get("error_category"),
        error_category=row.get("error_category"),
        receipt_id=row.get("receipt_id") or row.get("id"),
    )


def _record_full_source_result(
    store: Any,
    source: dict[str, Any],
    outcome: PollOutcome,
    context: SourceRunContext,
    *,
    started_at: datetime,
    completed_at: datetime,
    failure_category: str = "",
) -> None:
    store.record_source_poll_source(
        source,
        outcome,
        context=context,
        started_at=started_at,
        completed_at=completed_at,
        failure_category=failure_category,
    )


def poll_source(
    source: dict[str, Any],
    store: Any,
    *,
    now: datetime,
    budget: RuntimeBudget,
    force: bool = False,
    limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
    discover: Callable[[dict[str, Any]], list[Any]] = discover_source,
    context: SourceRunContext | None = None,
    run_state: _RunBudgetState | None = None,
) -> PollOutcome:
    source_id = str(source.get("id") or "")
    started_at = _utc_datetime(now)
    if context is not None and source.get("kind") not in SUPPORTED_SOURCE_KINDS:
        outcome = PollOutcome(
            source_id,
            "SKIPPED_UNSUPPORTED",
            error="UNSUPPORTED",
            error_category="UNSUPPORTED",
            receipt_id=deterministic_source_receipt_id(context.run_id, source_id),
        )
        try:
            _record_full_source_result(
                store,
                source,
                outcome,
                context,
                started_at=started_at,
                completed_at=started_at,
            )
        except Exception as exc:
            return PollOutcome(
                source_id,
                "FAILED",
                error=_error_category(exc),
                error_category=_error_category(exc),
                receipt_id=deterministic_source_receipt_id(context.run_id, source_id),
            )
        return outcome

    try:
        store.upsert_source(source)
        health = store.health(source_id)
        if not force and not source_due(
            health,
            poll_minutes=int(source.get("poll_minutes", 60)),
            now=started_at,
        ):
            outcome = PollOutcome(
                source_id,
                "SKIPPED_NOT_DUE",
                error="NOT_DUE",
                error_category="NOT_DUE",
                receipt_id=(
                    deterministic_source_receipt_id(context.run_id, source_id)
                    if context is not None
                    else None
                ),
            )
            if context is not None:
                _record_full_source_result(
                    store,
                    source,
                    outcome,
                    context,
                    started_at=started_at,
                    completed_at=started_at,
                )
            return outcome

        discovered = list(discover(source))
        source_limit = max(int(limit), 0)
        if context is not None:
            source_limit = min(
                source_limit,
                MAX_DISCOVERED_ITEMS_PER_SOURCE,
            )
        items = discovered[:source_limit]
        omitted_items = max(len(discovered) - len(items), 0)
        cost_blocked = (
            store.cost_today() >= float(budget.max_cost_usd_per_day)
            or store.cost_today(source_id)
            >= float(budget.max_cost_usd_per_source_day)
        )
        if context is not None:
            remaining = min(
                MAX_NEW_JOBS_PER_FULL_SOURCE_RUN
                - (run_state.jobs_enqueued if run_state is not None else 0),
                MAX_NEW_JOBS_PER_FULL_SOURCE_RUN,
            )
            latest = max(
                (_normalized_timestamp(item.published_at) for item in items),
                default="",
            )
            persisted = store.commit_source_poll(
                source,
                items,
                context=context,
                max_new_jobs=max(remaining, 0),
                cost_blocked=cost_blocked,
                latest=latest,
                omitted_items=omitted_items,
                started_at=started_at,
            )
            jobs_enqueued = int(persisted.get("jobs_enqueued", 0))
            if run_state is not None:
                run_state.jobs_enqueued += jobs_enqueued
            blocked = int(persisted.get("budget_blocked", 0))
            status = "BUDGET_BLOCKED" if blocked else "HEALTHY"
            return PollOutcome(
                source_id,
                status,
                discovered=len(items),
                content_upserts=int(persisted.get("content_upserts", 0)),
                jobs_enqueued=jobs_enqueued,
                duplicate_jobs=int(persisted.get("duplicate_jobs", 0)),
                budget_blocked=blocked,
                omitted_items=omitted_items,
                error_category="BUDGET_BLOCKED" if blocked else None,
                receipt_id=deterministic_source_receipt_id(context.run_id, source_id),
            )

        persisted = _legacy_persist_items(
            source,
            items,
            store,
            cost_blocked=cost_blocked,
            budget=budget,
        )
        store.mark_success(source_id, str(persisted.get("latest", "")))
        return PollOutcome(
            source_id,
            "HEALTHY",
            discovered=len(items),
            content_upserts=int(persisted.get("content_upserts", 0)),
            jobs_enqueued=int(persisted.get("jobs_enqueued", 0)),
            duplicate_jobs=int(persisted.get("duplicate_jobs", 0)),
            budget_blocked=int(persisted.get("budget_blocked", 0)),
            omitted_items=omitted_items,
        )
    except Exception as exc:
        category = _error_category(exc)
        status = "BLOCKED" if isinstance(exc, SourceAdapterError) and exc.blocked else "FAILED"
        outcome = PollOutcome(
            source_id,
            status,
            error=category,
            error_category=category,
            receipt_id=(
                deterministic_source_receipt_id(context.run_id, source_id)
                if context is not None
                else None
            ),
        )
        if context is not None:
            try:
                _record_full_source_result(
                    store,
                    source,
                    outcome,
                    context,
                    started_at=started_at,
                    completed_at=_utc_datetime(now),
                    failure_category=category,
                )
            except Exception:
                pass
        elif status == "FAILED":
            try:
                store.mark_failure(source_id, category)
            except Exception:
                pass
        return outcome


def _counters(outcomes: list[PollOutcome]) -> dict[str, int]:
    return {
        "source_count": len(outcomes),
        "discovered": sum(row.discovered for row in outcomes),
        "content_upserts": sum(row.content_upserts for row in outcomes),
        "jobs_enqueued": sum(row.jobs_enqueued for row in outcomes),
        "duplicate_jobs": sum(row.duplicate_jobs for row in outcomes),
        "budget_blocked": sum(row.budget_blocked for row in outcomes),
        "omitted_items": sum(row.omitted_items for row in outcomes),
    }


def _result_from_run(
    receipt: dict[str, Any],
    children: list[dict[str, Any]],
    *,
    status: str,
) -> FullSourceResult:
    return FullSourceResult(
        [_outcome_from_receipt(row) for row in children],
        run_id=str(receipt["run_id"]),
        mode=str(receipt["mode"]),
        run_date=str(receipt["run_date"]),
        effective_config_hash=str(receipt["effective_config_hash"]),
        status=status,
        started_at=receipt.get("started_at"),
        completed_at=receipt.get("completed_at"),
        diagnostic=bool(receipt.get("diagnostic", False)),
    )


def run_full_source(
    registry_path: Path | None,
    store: Any,
    *,
    force: bool = False,
    limit: int = MAX_DISCOVERED_ITEMS_PER_SOURCE,
    budget: RuntimeBudget | None = None,
    now: datetime | None = None,
    source_id: str | None = None,
    discover: Callable[[dict[str, Any]], list[Any]] = discover_source,
) -> FullSourceResult:
    policy = budget or RuntimeBudget()
    registry = load_registry(registry_path)
    current = _utc_datetime(now)
    configured_sources = registry.get("sources", [])
    sources = configured_sources
    if source_id:
        sources = [source for source in configured_sources if source.get("id") == source_id]
        if not sources:
            raise KeyError(f"Unknown source_id: {source_id}")
    if len(sources) > MAX_SOURCES_PER_FULL_SOURCE_RUN:
        raise ValueError("FULL_SOURCE_REGISTRY_BOUND_EXCEEDED")
    config_hash = canonical_registry_policy_hash(
        registry,
        budget=policy,
        limit=limit,
        force=force,
    )
    run_date = utc_run_date(current)
    run_id = deterministic_run_id(FULL_SOURCE_MODE, run_date, config_hash)
    context = SourceRunContext(
        run_id=run_id,
        mode=FULL_SOURCE_MODE,
        run_date=run_date,
        effective_config_hash=config_hash,
        diagnostic=force,
    )
    existing = store.get_source_poll_run(run_id)
    if existing and existing.get("status") == "COMPLETED":
        return _result_from_run(
            existing,
            store.list_source_poll_sources(run_id),
            status="SKIPPED_ALREADY_COMPLETED",
        )
    started = store.start_source_poll_run(
        run_id=run_id,
        mode=context.mode,
        run_date=context.run_date,
        effective_config_hash=context.effective_config_hash,
        diagnostic=context.diagnostic,
    )
    if started == "COMPLETED":
        receipt = store.get_source_poll_run(run_id) or {
            "run_id": run_id,
            "mode": context.mode,
            "run_date": context.run_date,
            "effective_config_hash": context.effective_config_hash,
            "status": "COMPLETED",
            "diagnostic": context.diagnostic,
        }
        return _result_from_run(
            receipt,
            store.list_source_poll_sources(run_id),
            status="SKIPPED_ALREADY_COMPLETED",
        )

    source_ids = [str(source.get("id") or "") for source in sources]
    previous = {} if force else store.source_poll_day_status(
        run_date=context.run_date,
        source_ids=source_ids,
        exclude_run_id=run_id,
    )
    state = _RunBudgetState()
    outcomes: list[PollOutcome] = []
    for source in sources:
        source_id_value = str(source.get("id") or "")
        existing_child = store.get_source_poll_source(run_id, source_id_value)
        if existing_child and existing_child.get("status") != "FAILED":
            outcomes.append(_outcome_from_receipt(existing_child))
            continue
        if not force and source_id_value in previous:
            prior = previous[source_id_value]
            if prior.get("status") != "FAILED":
                outcome = PollOutcome(
                    source_id_value,
                    "SKIPPED_DAILY_LIMIT",
                    error="DAILY_SOURCE_RUN_LIMIT",
                    error_category="DAILY_SOURCE_RUN_LIMIT",
                    receipt_id=deterministic_source_receipt_id(run_id, source_id_value),
                )
                try:
                    _record_full_source_result(
                        store,
                        source,
                        outcome,
                        context,
                        started_at=current,
                        completed_at=current,
                    )
                except Exception as exc:
                    outcome = PollOutcome(
                        source_id_value,
                        "FAILED",
                        error=_error_category(exc),
                        error_category=_error_category(exc),
                        receipt_id=deterministic_source_receipt_id(
                            run_id, source_id_value
                        ),
                    )
                outcomes.append(outcome)
                continue
        outcome = poll_source(
            source,
            store,
            now=current,
            budget=policy,
            force=force,
            limit=min(max(int(limit), 0), MAX_DISCOVERED_ITEMS_PER_SOURCE),
            discover=discover,
            context=context,
            run_state=state,
        )
        outcomes.append(outcome)

    counters = _counters(outcomes)
    failed = any(row.status == "FAILED" for row in outcomes)
    run_status = "FAILED" if failed else "COMPLETED"
    error_category = "SOURCE_FAILURE" if failed else ""
    completed_at = _utc_datetime(now)
    try:
        store.complete_source_poll_run(
            run_id=run_id,
            status=run_status,
            source_count=counters["source_count"],
            discovered=counters["discovered"],
            content_upserts=counters["content_upserts"],
            jobs_enqueued=counters["jobs_enqueued"],
            duplicate_jobs=counters["duplicate_jobs"],
            budget_blocked=counters["budget_blocked"],
            omitted_items=counters["omitted_items"],
            error_category=error_category,
            completed_at=completed_at,
        )
    except Exception:
        run_status = "FAILED"
        error_category = "RECEIPT_WRITE_FAILED"
    return FullSourceResult(
        outcomes,
        run_id=run_id,
        mode=context.mode,
        run_date=context.run_date,
        effective_config_hash=context.effective_config_hash,
        status=run_status,
        started_at=current.isoformat(),
        completed_at=completed_at.isoformat(),
        diagnostic=context.diagnostic,
    )


def run_registry(
    registry_path: Path | None,
    store: Any,
    *,
    source_id: str | None,
    force: bool,
    limit: int,
    budget: RuntimeBudget,
    now: datetime | None = None,
    full_source: bool = False,
    discover: Callable[[dict[str, Any]], list[Any]] = discover_source,
) -> list[PollOutcome] | FullSourceResult:
    if full_source:
        return run_full_source(
            registry_path,
            store,
            force=force,
            limit=limit,
            budget=budget,
            now=now,
            source_id=source_id,
            discover=discover,
        )
    registry = load_registry(registry_path)
    current = _utc_datetime(now)
    sources = registry.get("sources", [])
    if source_id:
        sources = [source for source in sources if source.get("id") == source_id]
        if not sources:
            raise KeyError(f"Unknown source_id: {source_id}")
    return [
        poll_source(
            source,
            store,
            now=current,
            budget=budget,
            force=force,
            limit=limit,
            discover=discover,
        )
        for source in sources
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Dichiarazioni Pubbliche source scheduler one-shot")
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--source-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--full-source", action="store_true")
    parser.add_argument("--limit", type=int, default=MAX_DISCOVERED_ITEMS_PER_SOURCE)
    parser.add_argument("--max-new-jobs", type=int, default=20)
    parser.add_argument("--max-cost-usd-day", type=float, default=5.0)
    parser.add_argument("--max-cost-usd-source-day", type=float, default=1.0)
    args = parser.parse_args()
    registry = args.registry
    budget = RuntimeBudget(
        max_new_jobs_per_run=max(args.max_new_jobs, 0),
        max_cost_usd_per_day=max(args.max_cost_usd_day, 0.0),
        max_cost_usd_per_source_day=max(args.max_cost_usd_source_day, 0.0),
    )
    if args.full_source:
        result = run_full_source(
            registry,
            PsqlStore(args.database_url),
            force=args.force,
            limit=args.limit,
            budget=budget,
            source_id=args.source_id,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        if result.status == "FAILED":
            raise SystemExit(1)
        return
    outcomes = run_registry(
            registry,
        PsqlStore(args.database_url),
        source_id=args.source_id,
        force=args.force,
        limit=args.limit,
        budget=budget,
    )
    print(json.dumps([asdict(row) for row in outcomes], ensure_ascii=False, indent=2))
    if any(row.status == "FAILED" for row in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
