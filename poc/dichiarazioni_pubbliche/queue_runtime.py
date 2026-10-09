from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.citation_assurance import (
    assertion_text_sha256,
    finding_assertion_id,
)
from dichiarazioni_pubbliche.operation_ledger import OperationLedgerSummary


@dataclass(frozen=True)
class ProcessingJob:
    job_id: str
    content_id: str
    job_type: str
    attempt: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class ContentRecord:
    content_id: str
    source_id: str
    canonical_url: str
    title: str
    published_at: str
    duration_ms: int | None
    processing_status: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CostSnapshot:
    global_day_usd: float
    source_day_usd: float


def deterministic_receipt_id(
    job_id: str,
    provider_id: str,
    operation: str,
    request_key: str = "",
    attempt: int | None = None,
) -> str:
    material = "\0".join((job_id, provider_id, operation, request_key)).encode()
    legacy_id = "receipt:" + hashlib.sha256(material).hexdigest()
    if attempt is None:
        return legacy_id
    parsed_attempt = int(attempt)
    if parsed_attempt < 1:
        raise ValueError("PROVIDER_RECEIPT_ATTEMPT_INVALID")
    return f"{legacy_id}:attempt:{parsed_attempt}"


def deterministic_followup_job_id(
    job_type: str,
    content_id: str,
    variant: str = "",
) -> str:
    material = "\0".join((job_type, content_id, variant)).encode()
    return "job:" + hashlib.sha256(material).hexdigest()


def deterministic_variant_id(
    content_id: str,
    provider_id: str,
    source_kind: str,
    raw_text_sha256: str,
) -> str:
    material = "\0".join(
        (content_id, provider_id, source_kind, raw_text_sha256)
    ).encode()
    return "transcript:" + hashlib.sha256(material).hexdigest()


def deterministic_segment_id(variant_id: str, segment_index: int) -> str:
    material = f"{variant_id}\0{segment_index}".encode()
    return "segment:" + hashlib.sha256(material).hexdigest()


def deterministic_canonical_segment_id(content_id: str, segment_index: int) -> str:
    material = f"{content_id}\0{segment_index}".encode()
    return "canonical-segment:" + hashlib.sha256(material).hexdigest()


def _valid_source_ref(source_ref: dict[str, Any]) -> bool:
    url = str(source_ref.get("url") or "").strip()
    parsed = urlsplit(url)
    return bool(parsed.scheme in {"http", "https"} and parsed.hostname)


def _clean(value: object) -> str:
    return str(value).replace("\x00", "")


def _dollar_quote(value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:16]
    tag = f"$dichiarazionipubbliche_{digest}$"
    if tag in value:
        raise ValueError("Unable to construct safe PostgreSQL dollar quote")
    return f"{tag}{value}{tag}"


class PsqlRuntime:
    def __init__(self, database_url: str | None = None, psql: str = "psql") -> None:
        self.database_url = database_url or None
        self.psql = psql

    def _args(self) -> list[str]:
        args = [self.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
        if self.database_url:
            args.extend(["--dbname", self.database_url])
        return args

    def run(self, sql: str, **variables: object) -> str:
        args = self._args()
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
            raise RuntimeError(message[:1200])
        return proc.stdout.strip()

    def run_literal(self, sql: str) -> str:
        return self.run(sql)

    def require_current_ingestion_relevance(
        self,
        *,
        content_ref: str,
        canonical_url: str,
    ):
        from dichiarazioni_pubbliche.ingestion_relevance import (
            require_current_ingestion_relevance,
        )

        return require_current_ingestion_relevance(
            self.run,
            content_ref=content_ref,
            canonical_url=canonical_url,
        )

    def issue_ingestion_acquisition_permit(
        self,
        *,
        content_ref: str,
        canonical_url: str,
        operation_kind: str,
        operation_ref: str,
    ):
        from dichiarazioni_pubbliche.ingestion_relevance import (
            issue_ingestion_acquisition_permit,
        )

        return issue_ingestion_acquisition_permit(
            self.run,
            content_ref=content_ref,
            canonical_url=canonical_url,
            operation_kind=operation_kind,
            operation_ref=operation_ref,
        )

    def require_ingestion_acquisition_permit(
        self,
        *,
        permit_id: str,
        content_ref: str,
        canonical_url: str,
        operation_kind: str,
        operation_ref: str,
    ):
        from dichiarazioni_pubbliche.ingestion_relevance import (
            require_ingestion_acquisition_permit,
        )

        return require_ingestion_acquisition_permit(
            self.run,
            permit_id=permit_id,
            content_ref=content_ref,
            canonical_url=canonical_url,
            operation_kind=operation_kind,
            operation_ref=operation_ref,
        )


class QueueRuntimeStore(PsqlRuntime):
    def reap_expired(self, max_attempts: int = 5) -> int:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.reap_expired(self, max_attempts=max_attempts)

    def register_public_person(
        self,
        *,
        person_id: str,
        canonical_name: str,
        public_role: str | None = None,
        country_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO person (
                    id, canonical_name, public_role, country_code,
                    is_public_figure, metadata
                ) VALUES (
                    :'person_id', :'canonical_name', NULLIF(:'public_role',''),
                    NULLIF(:'country_code',''), true, :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            existing AS (
                SELECT id
                FROM person
                WHERE
                    id = :'person_id'
                    AND canonical_name = :'canonical_name'
                    AND is_public_figure = true
            )
            SELECT (
                EXISTS(SELECT 1 FROM inserted)
                OR EXISTS(SELECT 1 FROM existing)
            )::text;
            """,
            person_id=person_id,
            canonical_name=canonical_name,
            public_role=public_role or "",
            country_code=country_code or "",
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def register_organization(
        self,
        *,
        organization_id: str,
        canonical_name: str,
        organization_type: str | None = None,
        country_code: str | None = None,
        canonical_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO organization (
                    id, canonical_name, organization_type, country_code,
                    canonical_url, metadata
                ) VALUES (
                    :'organization_id', :'canonical_name',
                    COALESCE(NULLIF(:'organization_type',''), 'GENERAL'),
                    NULLIF(:'country_code',''), NULLIF(:'canonical_url',''),
                    :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            existing AS (
                SELECT id
                FROM organization
                WHERE
                    id = :'organization_id'
                    AND canonical_name = :'canonical_name'
            )
            SELECT (
                EXISTS(SELECT 1 FROM inserted)
                OR EXISTS(SELECT 1 FROM existing)
            )::text;
            """,
            organization_id=organization_id,
            canonical_name=canonical_name,
            organization_type=organization_type or "",
            country_code=country_code or "",
            canonical_url=canonical_url or "",
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def register_person_role_interval(
        self,
        *,
        interval_id: str,
        person_id: str,
        organization_id: str,
        role: str,
        start_date: str,
        end_date: str | None = None,
        is_public_role: bool = True,
        source_ref: dict[str, Any],
        supersedes_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else None
        if end is not None and end < start:
            raise ValueError("ROLE_INTERVAL_END_BEFORE_START")
        if is_public_role and not _valid_source_ref(source_ref):
            raise ValueError("ROLE_INTERVAL_SOURCE_REF_REQUIRED")
        encoded_ref = json.dumps(
            source_ref, ensure_ascii=False, separators=(",", ":")
        )
        encoded_meta = json.dumps(
            metadata or {}, ensure_ascii=False, separators=(",", ":")
        )
        sql = ["BEGIN;"]
        if supersedes_id:
            sql.append(
                """
                UPDATE person_role_interval target
                SET status = 'SUPERSEDED', updated_at = now()
                WHERE
                    target.id = :'supersedes_id'
                    AND target.person_id = :'person_id'
                    AND target.organization_id = :'organization_id'
                    AND target.status = 'ACTIVE';
                """
            )
            sql.append(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM person_role_interval
                        WHERE
                            id = :'supersedes_id'
                            AND person_id = :'person_id'
                            AND organization_id = :'organization_id'
                            AND status = 'SUPERSEDED'
                    ) THEN
                        RAISE EXCEPTION 'ROLE_INTERVAL_SUPERSEDE_TARGET_MISSING';
                    END IF;
                END
                $$;
                """
            )
        sql.append(
            """
            WITH inserted AS (
                INSERT INTO person_role_interval (
                    id, person_id, organization_id, role, start_date, end_date,
                    is_public_role, source_ref, status, supersedes_id, metadata
                ) VALUES (
                    :'interval_id', :'person_id', :'organization_id', :'role',
                    :'start_date'::date, NULLIF(:'end_date','')::date,
                    :'is_public_role'::boolean, :'source_ref'::jsonb, 'ACTIVE',
                    :'supersedes_id', :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            existing AS (
                SELECT id
                FROM person_role_interval
                WHERE
                    id = :'interval_id'
                    AND person_id = :'person_id'
                    AND organization_id = :'organization_id'
                    AND role = :'role'
                    AND start_date = :'start_date'::date
                    AND end_date IS NOT DISTINCT FROM
                        NULLIF(:'end_date','')::date
                    AND is_public_role = :'is_public_role'::boolean
                    AND status = 'ACTIVE'
            )
            SELECT (
                EXISTS(SELECT 1 FROM inserted)
                OR EXISTS(SELECT 1 FROM existing)
            )::text;
            """
        )
        sql.append("COMMIT;")
        raw = self.run(
            "\n".join(sql),
            interval_id=interval_id,
            person_id=person_id,
            organization_id=organization_id,
            role=role,
            start_date=start_date,
            end_date=end_date or "",
            is_public_role="true" if is_public_role else "false",
            source_ref=encoded_ref,
            supersedes_id=supersedes_id or "",
            metadata=encoded_meta,
        )
        return raw.lower() in {"t", "true", "1"}

    def role_intervals_at(
        self,
        *,
        person_id: str,
        on_date: str,
    ) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'interval_id', id,
                'person_id', :'person_id',
                'organization_id', organization_id,
                'role', role,
                'start_date', start_date::text,
                'end_date', end_date::text,
                'is_public_role', is_public_role,
                'source_ref', source_ref
            ) ORDER BY start_date, role)::text, '[]')
            FROM person_role_interval_at(:'person_id', :'on_date'::date);
            """,
            person_id=person_id,
            on_date=on_date,
        )
        return json.loads(raw or "[]")

    def approve_person_role_interval_with_review(
        self,
        *,
        interval_id: str,
        person_id: str,
        organization_id: str,
        role: str,
        start_date: str,
        end_date: str | None,
        is_public_role: bool,
        source_ref: dict[str, Any],
        event_id: str,
        actor_ref: str,
        reason: str | None,
        supersedes_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else None
        if end is not None and end < start:
            raise ValueError("ROLE_INTERVAL_END_BEFORE_START")
        if is_public_role and not _valid_source_ref(source_ref):
            raise ValueError("ROLE_INTERVAL_SOURCE_REF_REQUIRED")
        raw = self.run(
            """
            BEGIN;
            UPDATE person_role_interval
            SET status = 'SUPERSEDED', updated_at = now()
            WHERE NULLIF(:'supersedes_id', '') IS NOT NULL
              AND id = :'supersedes_id'
              AND person_id = :'person_id'
              AND organization_id = :'organization_id'
              AND status = 'ACTIVE';

            INSERT INTO person_role_interval (
                id, person_id, organization_id, role, start_date, end_date,
                is_public_role, source_ref, status, supersedes_id, metadata
            )
            SELECT
                :'interval_id', :'person_id', :'organization_id', :'role',
                :'start_date'::date, NULLIF(:'end_date','')::date,
                :'is_public_role'::boolean, :'source_ref'::jsonb, 'ACTIVE',
                NULLIF(:'supersedes_id', ''), :'metadata'::jsonb
            WHERE NULLIF(:'supersedes_id', '') IS NULL
               OR EXISTS (
                   SELECT 1
                   FROM person_role_interval
                   WHERE id = :'supersedes_id'
                     AND person_id = :'person_id'
                     AND organization_id = :'organization_id'
                     AND status = 'SUPERSEDED'
               )
            ON CONFLICT (id) DO NOTHING;

            INSERT INTO review_event (
                id, entity_type, entity_id, action, actor_ref, reason
            ) VALUES (
                :'event_id', 'PERSON_ROLE_INTERVAL', :'interval_id',
                'APPROVED', :'actor_ref', :'reason'
            )
            ON CONFLICT (id) DO NOTHING;

            SELECT ((EXISTS (
                SELECT 1
                FROM person_role_interval
                WHERE id = :'interval_id' AND status = 'ACTIVE'
            ))
            AND EXISTS (
                SELECT 1
                FROM review_event
                WHERE id = :'event_id'
                  AND entity_type = 'PERSON_ROLE_INTERVAL'
                  AND entity_id = :'interval_id'
                  AND action = 'APPROVED'
            ))::text;
            COMMIT;
            """,
            interval_id=interval_id,
            person_id=person_id,
            organization_id=organization_id,
            role=role,
            start_date=start_date,
            end_date=end_date or "",
            is_public_role="true" if is_public_role else "false",
            source_ref=json.dumps(
                source_ref, ensure_ascii=False, separators=(",", ":")
            ),
            event_id=event_id,
            actor_ref=actor_ref,
            reason=reason or "",
            supersedes_id=supersedes_id or "",
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def insert_speaker_identity_candidate(
        self,
        *,
        candidate_id: str,
        content_id: str,
        person_id: str,
        start_ms: int,
        end_ms: int,
        speaker_label: str | None,
        attribution_method: str,
        attribution_version: str,
        source_ref: dict[str, Any],
        confidence: float | None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO speaker_identity_candidate (
                    id, content_id, person_id, start_ms, end_ms,
                    speaker_label, attribution_method, attribution_version,
                    source_ref, confidence, status, metadata
                ) VALUES (
                    :'candidate_id', :'content_id', :'person_id',
                    :'start_ms'::bigint, :'end_ms'::bigint,
                    NULLIF(:'speaker_label',''), :'attribution_method',
                    :'attribution_version', :'source_ref'::jsonb,
                    NULLIF(:'confidence','')::numeric, 'CANDIDATE',
                    :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            candidate_id=candidate_id,
            content_id=content_id,
            person_id=person_id,
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            speaker_label=speaker_label or "",
            attribution_method=attribution_method,
            attribution_version=attribution_version,
            source_ref=json.dumps(
                source_ref, ensure_ascii=False, separators=(",", ":")
            ),
            confidence="" if confidence is None else float(confidence),
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def insert_claim_text_provenance(
        self,
        *,
        candidate_id: str,
        claim_id: str,
        content_id: str,
        person_id: str,
        selector_type: str,
        quote_sha256: str,
        source_sha256: str | None,
        start_char: int | None,
        end_char: int | None,
        attribution_method: str,
        attribution_version: str,
        source_ref: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH eligible AS (
                SELECT claim.id
                FROM atomic_claim claim
                WHERE
                    claim.id = :'claim_id'
                    AND claim.content_id = :'content_id'
                    AND claim.speaker_person_id = :'person_id'
            ),
            inserted AS (
                INSERT INTO claim_text_provenance (
                    id, claim_id, content_id, person_id, selector_type,
                    quote_sha256, source_sha256, start_char, end_char,
                    attribution_method, attribution_version, source_ref,
                    status, metadata
                )
                SELECT
                    :'candidate_id', :'claim_id', :'content_id', :'person_id',
                    :'selector_type', :'quote_sha256', NULLIF(:'source_sha256',''),
                    NULLIF(:'start_char','')::integer,
                    NULLIF(:'end_char','')::integer,
                    :'attribution_method', :'attribution_version',
                    :'source_ref'::jsonb, 'CANDIDATE', :'metadata'::jsonb
                FROM eligible
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            existing AS (
                SELECT provenance.id
                FROM claim_text_provenance provenance
                JOIN eligible ON eligible.id = provenance.claim_id
                WHERE
                    provenance.id = :'candidate_id'
                    AND provenance.content_id = :'content_id'
                    AND provenance.person_id = :'person_id'
                    AND provenance.selector_type = :'selector_type'
                    AND provenance.quote_sha256 = :'quote_sha256'
                    AND provenance.source_sha256 IS NOT DISTINCT FROM
                        NULLIF(:'source_sha256','')
                    AND provenance.start_char IS NOT DISTINCT FROM
                        NULLIF(:'start_char','')::integer
                    AND provenance.end_char IS NOT DISTINCT FROM
                        NULLIF(:'end_char','')::integer
                    AND provenance.attribution_method = :'attribution_method'
                    AND provenance.attribution_version = :'attribution_version'
                    AND provenance.source_ref = :'source_ref'::jsonb
                    AND provenance.status IN ('CANDIDATE', 'APPROVED')
            )
            SELECT (
                EXISTS(SELECT 1 FROM inserted)
                OR EXISTS(SELECT 1 FROM existing)
            )::text;
            """,
            candidate_id=candidate_id,
            claim_id=claim_id,
            content_id=content_id,
            person_id=person_id,
            selector_type=selector_type,
            quote_sha256=quote_sha256,
            source_sha256=source_sha256 or "",
            start_char="" if start_char is None else int(start_char),
            end_char="" if end_char is None else int(end_char),
            attribution_method=attribution_method,
            attribution_version=attribution_version,
            source_ref=json.dumps(
                source_ref, ensure_ascii=False, separators=(",", ":")
            ),
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def approve_claim_text_provenance_with_review(
        self,
        *,
        candidate_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH candidate AS (
                SELECT provenance.*
                FROM claim_text_provenance provenance
                JOIN atomic_claim claim ON claim.id = provenance.claim_id
                WHERE
                    provenance.id = :'candidate_id'
                    AND provenance.status IN ('CANDIDATE', 'APPROVED')
                    AND provenance.content_id = claim.content_id
                    AND provenance.person_id = claim.speaker_person_id
                FOR UPDATE OF provenance
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id', 'CLAIM_TEXT_PROVENANCE', candidate.id,
                    'APPROVED', :'actor_ref', NULLIF(:'reason',''),
                    jsonb_build_object(
                        'claim_id', candidate.claim_id,
                        'content_id', candidate.content_id,
                        'person_id', candidate.person_id,
                        'quote_sha256', candidate.quote_sha256
                    )
                FROM candidate
                ON CONFLICT (id) DO NOTHING
                RETURNING entity_id
            ),
            reviewable AS (
                SELECT candidate.*
                FROM candidate
                WHERE
                    EXISTS (
                        SELECT 1 FROM logged
                        WHERE logged.entity_id = candidate.id
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM review_event review
                        WHERE review.entity_type = 'CLAIM_TEXT_PROVENANCE'
                          AND review.entity_id = candidate.id
                          AND review.action = 'APPROVED'
                    )
            ),
            changed AS (
                UPDATE claim_text_provenance target
                SET status = 'APPROVED'
                FROM reviewable
                WHERE target.id = reviewable.id
                RETURNING target.id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            candidate_id=candidate_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def approve_speaker_identity_with_review(
        self,
        *,
        candidate_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH candidate AS (
                SELECT *
                FROM speaker_identity_candidate
                WHERE id = :'candidate_id'
                FOR UPDATE
            ),
            eligible AS (
                SELECT c.*
                FROM candidate c
                WHERE
                    c.attribution_method IN (
                        'MANUAL_REVIEW',
                        'TRANSCRIPT_LABEL',
                        'OFFICIAL_RECORD'
                    )
                    AND
                    EXISTS (
                        SELECT 1
                        FROM canonical_transcript_segment segment
                        WHERE
                            segment.content_id = c.content_id
                            AND segment.start_ms >= c.start_ms
                            AND segment.end_ms <= c.end_ms
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM speaker_identity_candidate other
                        WHERE
                            other.content_id = c.content_id
                            AND other.id <> c.id
                            AND other.status = 'APPROVED'
                            AND other.person_id <> c.person_id
                            AND other.start_ms < c.end_ms
                            AND other.end_ms > c.start_ms
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM canonical_transcript_segment segment
                        WHERE
                            segment.content_id = c.content_id
                            AND segment.start_ms >= c.start_ms
                            AND segment.end_ms <= c.end_ms
                            AND segment.speaker_person_id IS NOT NULL
                            AND segment.speaker_person_id <> c.person_id
                    )
            ),
            changed AS (
                UPDATE speaker_identity_candidate target
                SET status = 'APPROVED'
                FROM eligible
                WHERE target.id = eligible.id
                RETURNING
                    target.id,
                    target.content_id,
                    target.person_id,
                    target.start_ms,
                    target.end_ms,
                    target.confidence,
                    target.attribution_method,
                    target.attribution_version
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'SPEAKER_IDENTITY_CANDIDATE',
                    changed.id,
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    jsonb_build_object(
                        'content_id', changed.content_id,
                        'person_id', changed.person_id
                    )
                FROM changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            applied_segments AS (
                UPDATE canonical_transcript_segment segment
                SET
                    speaker_person_id = changed.person_id,
                    updated_at = now()
                FROM changed
                WHERE
                    segment.content_id = changed.content_id
                    AND segment.start_ms >= changed.start_ms
                    AND segment.end_ms <= changed.end_ms
                    AND (
                        segment.speaker_person_id IS NULL
                        OR segment.speaker_person_id = changed.person_id
                    )
                RETURNING segment.id
            ),
            appearance_upsert AS (
                INSERT INTO appearance (
                    content_id, person_id, role, confidence, start_ms, end_ms,
                    evidence
                )
                SELECT
                    changed.content_id,
                    changed.person_id,
                    'SPEAKER',
                    changed.confidence,
                    changed.start_ms,
                    changed.end_ms,
                    jsonb_build_object(
                        'speaker_identity_candidate_id', changed.id,
                        'attribution_method', changed.attribution_method,
                        'attribution_version', changed.attribution_version
                    )
                FROM changed
                ON CONFLICT (content_id, person_id, role, start_ms) DO UPDATE SET
                    end_ms = EXCLUDED.end_ms,
                    confidence = EXCLUDED.confidence,
                    evidence = EXCLUDED.evidence
                RETURNING content_id
            ),
            resolved_claims AS (
                SELECT
                    claim.id AS claim_id,
                    changed.person_id
                FROM changed
                JOIN atomic_claim claim
                    ON claim.content_id = changed.content_id
                WHERE
                    EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        WHERE link.claim_id = claim.id
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE
                            link.claim_id = claim.id
                            AND NOT (
                                segment.speaker_person_id =
                                    changed.person_id
                                OR (
                                    segment.speaker_person_id IS NULL
                                    AND segment.content_id =
                                        changed.content_id
                                    AND segment.start_ms >=
                                        changed.start_ms
                                    AND segment.end_ms <= changed.end_ms
                                )
                            )
                    )
            ),
            applied_claims AS (
                UPDATE atomic_claim claim
                SET speaker_person_id = resolved.person_id
                FROM resolved_claims resolved
                WHERE
                    claim.id = resolved.claim_id
                    AND (
                        claim.speaker_person_id IS NULL
                        OR claim.speaker_person_id = resolved.person_id
                    )
                RETURNING claim.id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            candidate_id=candidate_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def publish_finding_with_review(
        self,
        *,
        finding_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.publish_finding_with_review(self, finding_id=finding_id, event_id=event_id, actor_ref=actor_ref, reason=reason)

    def claim(self, worker_id: str, lease_seconds: int = 300) -> ProcessingJob | None:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.claim(
            self,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def renew(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.renew(
            self,
            job_id=job_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def complete(self, job_id: str, worker_id: str) -> bool:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.complete(self, job_id=job_id, worker_id=worker_id)

    def retry(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        delay_seconds: int,
        max_attempts: int,
    ) -> str:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.retry(
            self,
            job_id=job_id,
            worker_id=worker_id,
            error=error,
            delay_seconds=delay_seconds,
            max_attempts=max_attempts,
        )

    def defer(
        self,
        job_id: str,
        worker_id: str,
        reason: str,
        *,
        delay_seconds: int,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.defer(
            self,
            job_id=job_id,
            worker_id=worker_id,
            reason=reason,
            delay_seconds=delay_seconds,
        )

    def block(self, job_id: str, worker_id: str, reason: str) -> bool:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.block(
            self,
            job_id=job_id,
            worker_id=worker_id,
            reason=reason,
        )

    def content(self, content_id: str) -> ContentRecord:
        raw = self.run(
            """
            SELECT json_build_object(
                'content_id', id,
                'source_id', source_id,
                'canonical_url', canonical_url,
                'title', COALESCE(title, ''),
                'published_at', COALESCE(published_at::text, ''),
                'duration_ms', duration_ms,
                'processing_status', processing_status,
                'metadata', metadata
            )::text
            FROM content_item
            WHERE id = :'content_id';
            """,
            content_id=content_id,
        )
        if not raw:
            raise KeyError(f"Unknown content_id: {content_id}")
        row = json.loads(raw)
        return ContentRecord(
            content_id=row["content_id"],
            source_id=row["source_id"],
            canonical_url=row["canonical_url"],
            title=row["title"],
            published_at=row["published_at"],
            duration_ms=row["duration_ms"],
            processing_status=row["processing_status"],
            metadata=row.get("metadata") or {},
        )

    def update_content_status(
        self,
        content_id: str,
        status: str,
        metadata_patch: dict[str, Any] | None = None,
    ) -> None:
        metadata = json.dumps(
            metadata_patch or {}, ensure_ascii=False, separators=(",", ":")
        )
        self.run(
            """
            UPDATE content_item
            SET
                processing_status = :'status',
                metadata = metadata || :'metadata'::jsonb
            WHERE id = :'content_id';
            """,
            content_id=content_id,
            status=status,
            metadata=metadata,
        )

    def upsert_locator(
        self,
        content_id: str,
        *,
        platform: str,
        external_id: str,
        canonical_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
        self.run(
            """
            INSERT INTO content_locator (
                content_id, platform, external_id, canonical_url, metadata
            ) VALUES (
                :'content_id', :'platform', :'external_id', :'canonical_url',
                :'metadata'::jsonb
            )
            ON CONFLICT (platform, external_id) DO UPDATE SET
                content_id = EXCLUDED.content_id,
                canonical_url = EXCLUDED.canonical_url,
                metadata = content_locator.metadata || EXCLUDED.metadata;
            """,
            content_id=content_id,
            platform=platform,
            external_id=external_id,
            canonical_url=canonical_url,
            metadata=payload,
        )

    def enqueue_followup(
        self,
        *,
        content_id: str,
        job_type: str,
        payload: dict[str, Any],
        variant: str = "",
    ) -> tuple[str, bool]:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.enqueue_followup(
            self,
            content_id=content_id,
            job_type=job_type,
            payload=payload,
            variant=variant,
        )

    def enqueue_jobs_bulk(self, jobs: list[dict[str, Any]]) -> int:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.enqueue_jobs_bulk(self, jobs=jobs)

    def cost_snapshot(self, source_id: str) -> CostSnapshot:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.cost_snapshot(self, source_id)

    def operation_ledger_receipts(
        self,
        *,
        source_id: str | None = None,
        content_id: str | None = None,
        claim_id: str | None = None,
        collection_id: str | None = None,
        provider_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ):
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.operation_ledger_receipts(
            self,
            source_id=source_id,
            content_id=content_id,
            claim_id=claim_id,
            collection_id=collection_id,
            provider_id=provider_id,
            operation=operation,
            since=since,
            until=until,
        )

    def operation_ledger_summary(self, **filters: object) -> OperationLedgerSummary:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.operation_ledger_summary(self, **filters)

    def record_receipt(
        self,
        *,
        job_id: str,
        content_id: str,
        provider_id: str,
        model_id: str | None,
        operation: str,
        request_id: str | None,
        input_bytes: int | None,
        input_seconds: float | None,
        estimated_cost_usd: float,
        status: str,
        receipt: dict[str, Any],
        request_key: str = "",
        measured_cost_usd: float | None = None,
        billing_basis: str | None = None,
        total_tokens: int | None = None,
        request_count: int = 1,
        ledger_scope: dict[str, Any] | None = None,
    ) -> str:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.record_receipt(
            self,
            job_id=job_id,
            content_id=content_id,
            provider_id=provider_id,
            model_id=model_id,
            operation=operation,
            request_id=request_id,
            input_bytes=input_bytes,
            input_seconds=input_seconds,
            estimated_cost_usd=estimated_cost_usd,
            status=status,
            receipt=receipt,
            request_key=request_key,
            measured_cost_usd=measured_cost_usd,
            billing_basis=billing_basis,
            total_tokens=total_tokens,
            request_count=request_count,
            ledger_scope=ledger_scope,
        )

    def insert_transcript_variant(
        self,
        *,
        content_id: str,
        provider_id: str,
        source_kind: str,
        language: str,
        raw_text: str,
        raw_text_sha256: str,
        is_platform_caption: bool,
        is_manual_caption: bool,
        metadata: dict[str, Any],
    ) -> tuple[str, bool]:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.insert_transcript_variant(
            self,
            content_id=content_id,
            provider_id=provider_id,
            source_kind=source_kind,
            language=language,
            raw_text=raw_text,
            raw_text_sha256=raw_text_sha256,
            is_platform_caption=is_platform_caption,
            is_manual_caption=is_manual_caption,
            metadata=metadata,
        )

    def insert_transcript_segments(
        self,
        *,
        variant_id: str,
        segments: list[dict[str, Any]],
    ) -> None:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.insert_transcript_segments(
            self,
            variant_id=variant_id,
            segments=segments,
        )

    def transcript_segments(self, variant_id: str) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.transcript_segments(self, variant_id=variant_id)

    def canonical_candidate_variant_ids(self, content_id: str) -> set[str]:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.canonical_candidate_variant_ids(
            self,
            content_id=content_id,
        )

    def canonical_segments(self, content_id: str) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.canonical_segments(self, content_id=content_id)

    def insert_atomic_claims(self, claims: list[dict[str, Any]]) -> int:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.insert_atomic_claims(self, claims=claims)

    def claim_count(self, content_id: str) -> int:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.claim_count(self, content_id=content_id)

    def unfinished_sibling_jobs(
        self,
        *,
        content_id: str,
        job_type: str,
        exclude_job_id: str,
    ) -> int:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.unfinished_sibling_jobs(
            self,
            content_id=content_id,
            job_type=job_type,
            exclude_job_id=exclude_job_id,
        )

    def upsert_evidence(
        self,
        *,
        evidence_id: str,
        canonical_url: str,
        publisher: str,
        source_type: str,
        fetched_at: str,
        content_sha256: str,
        publication_date: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        record_status: str | None = None,
        excerpt: str | None = None,
        reference_period: str | None = None,
        independence_group: str | None = None,
        rights_status: str = "UNKNOWN",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.upsert_evidence(
            self,
            evidence_id=evidence_id,
            canonical_url=canonical_url,
            publisher=publisher,
            source_type=source_type,
            publication_date=publication_date,
            valid_from=valid_from,
            valid_until=valid_until,
            record_status=record_status,
            fetched_at=fetched_at,
            content_sha256=content_sha256,
            excerpt=excerpt,
            reference_period=reference_period,
            independence_group=independence_group,
            rights_status=rights_status,
            metadata=metadata,
        )

    def link_claim_evidence(
        self,
        *,
        claim_id: str,
        evidence_id: str,
        retrieval_method: str,
        retrieval_version: str,
        relation_candidate: str = "UNKNOWN",
        status: str = "RETRIEVED",
        score: float | None = None,
        statement_cutoff: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.link_claim_evidence(
            self,
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
            status=status,
            score=score,
            statement_cutoff=statement_cutoff,
            metadata=metadata,
        )

    def claim_evidence_count(self, claim_id: str) -> int:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.claim_evidence_count(self, claim_id=claim_id)

    def insert_evidence_observation(
        self,
        *,
        observation_id: str,
        evidence_id: str,
        observation_type: str,
        metric: str | None,
        value_numeric: float | None,
        value_text: str | None,
        unit: str | None,
        reference_period: str | None,
        dimensions: dict[str, Any],
        extraction_method: str,
        extraction_version: str,
        source_pointer: dict[str, Any],
        status: str = "CANDIDATE",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.insert_evidence_observation(
            self,
            observation_id=observation_id,
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=metric,
            value_numeric=value_numeric,
            value_text=value_text,
            unit=unit,
            reference_period=reference_period,
            dimensions=dimensions,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=source_pointer,
            status=status,
            metadata=metadata,
        )

    def update_evidence_observation_status(
        self,
        observation_id: str,
        status: str,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.update_evidence_observation_status(
            self,
            observation_id=observation_id,
            status=status,
        )

    def update_claim_evidence_status(
        self,
        *,
        claim_id: str,
        evidence_id: str,
        retrieval_version: str,
        status: str,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.update_claim_evidence_status(
            self,
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_version=retrieval_version,
            status=status,
        )

    def approve_claim_evidence_with_review(
        self,
        *,
        claim_id: str,
        evidence_id: str,
        retrieval_version: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        entity_id = f"{claim_id}|{evidence_id}|{retrieval_version}"
        metadata = json.dumps(
            {
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "retrieval_version": retrieval_version,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raw = self.run(
            """
            WITH locked_candidate AS (
                SELECT claim_id, status
                FROM claim_evidence_candidate
                WHERE
                    claim_id = :'claim_id'
                    AND evidence_id = :'evidence_id'
                    AND retrieval_version = :'retrieval_version'
                FOR UPDATE
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'CLAIM_EVIDENCE_CANDIDATE',
                    :'entity_id',
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    :'metadata'::jsonb
                FROM locked_candidate
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            replayed_exact_review AS (
                -- Replaying an already-persisted APPROVED event is idempotent
                -- only if the same entity/actor/reason is still APPROVED.
                -- A stale reviewed event cannot reapprove a previously
                -- demoted or modified RETRIEVED candidate.
                SELECT reviewer.id
                FROM review_event reviewer
                JOIN locked_candidate candidate ON candidate.status = 'APPROVED'
                WHERE reviewer.id = :'event_id'
                  AND reviewer.entity_type = 'CLAIM_EVIDENCE_CANDIDATE'
                  AND reviewer.entity_id = :'entity_id'
                  AND reviewer.action = 'APPROVED'
                  AND reviewer.actor_ref = :'actor_ref'
                  AND reviewer.reason IS NOT DISTINCT FROM NULLIF(:'reason','')
            ),
            changed AS (
                UPDATE claim_evidence_candidate
                SET status = 'APPROVED'
                WHERE
                    claim_id = :'claim_id'
                    AND evidence_id = :'evidence_id'
                    AND retrieval_version = :'retrieval_version'
                    AND (
                        EXISTS (SELECT 1 FROM logged)
                        OR EXISTS (SELECT 1 FROM replayed_exact_review)
                    )
                RETURNING claim_id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_version=retrieval_version,
            event_id=event_id,
            entity_id=entity_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
            metadata=metadata,
        )
        return raw.lower() in {"t", "true", "1"}

    def approve_evidence_observation_with_review(
        self,
        *,
        observation_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH changed AS (
                UPDATE evidence_observation
                SET status = 'APPROVED'
                WHERE id = :'observation_id'
                RETURNING id
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'EVIDENCE_OBSERVATION',
                    :'observation_id',
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    '{}'::jsonb
                FROM changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            observation_id=observation_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def claim_context(self, claim_id: str) -> dict[str, Any]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.claim_context(self, claim_id=claim_id)

    def finding_context(self, finding_id: str) -> dict[str, Any]:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.finding_context(self, finding_id)

    def approved_verification_evidence(
        self,
        claim_id: str,
    ) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.approved_verification_evidence(
            self,
            claim_id=claim_id,
        )

    def source_intelligence_relations(self) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.source_intelligence_relations(self)

    def insert_evidence_set_assessment(
        self,
        *,
        assessment_id: str,
        atomic_claim_id: str | None,
        claim_candidate_id: str | None,
        requirement_profile_id: str,
        requirement_profile_version: str,
        input_fingerprint: str,
        assessment: str,
        qualifying_evidence_ids: list[str],
        rejected_evidence: list[dict[str, Any]],
        satisfied_rules: list[str],
        missing_rules: list[str],
        conflict_groups: list[dict[str, Any]],
        coverage_need_candidates: list[dict[str, Any]],
        rationale_codes: list[str],
        assessment_version: str,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.insert_evidence_set_assessment(
            self,
            assessment_id=assessment_id,
            atomic_claim_id=atomic_claim_id,
            claim_candidate_id=claim_candidate_id,
            requirement_profile_id=requirement_profile_id,
            requirement_profile_version=requirement_profile_version,
            input_fingerprint=input_fingerprint,
            assessment=assessment,
            qualifying_evidence_ids=qualifying_evidence_ids,
            rejected_evidence=rejected_evidence,
            satisfied_rules=satisfied_rules,
            missing_rules=missing_rules,
            conflict_groups=conflict_groups,
            coverage_need_candidates=coverage_need_candidates,
            rationale_codes=rationale_codes,
            assessment_version=assessment_version,
        )

    def coverage_collection_ids_for_claim(self, claim_id: str) -> list[str]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.coverage_collection_ids_for_claim(
            self,
            claim_id=claim_id,
        )

    def upsert_coverage_need(
        self,
        *,
        id: str,
        collection_id: str,
        atomic_claim_id: str,
        claim_candidate_id: str,
        source_intelligence_assessment_id: str,
        need_type: str,
        requirement_kind: str,
        requirement_fingerprint: str,
        question: str,
        required_roles: str,
        authority_scope: str,
        temporal_constraints: str,
        independence_requirement: str,
        max_attempts: str,
        created_by: str,
        metadata: str,
        created_event_id: str,
        observed_event_id: str,
    ) -> str:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.upsert_coverage_need(
            self,
            id=id,
            collection_id=collection_id,
            atomic_claim_id=atomic_claim_id,
            claim_candidate_id=claim_candidate_id,
            source_intelligence_assessment_id=source_intelligence_assessment_id,
            need_type=need_type,
            requirement_kind=requirement_kind,
            requirement_fingerprint=requirement_fingerprint,
            question=question,
            required_roles=required_roles,
            authority_scope=authority_scope,
            temporal_constraints=temporal_constraints,
            independence_requirement=independence_requirement,
            max_attempts=max_attempts,
            created_by=created_by,
            metadata=metadata,
            created_event_id=created_event_id,
            observed_event_id=observed_event_id,
        )

    def searchable_coverage_needs(
        self,
        *,
        collection_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.searchable_coverage_needs(
            self,
            collection_id=collection_id,
            limit=limit,
        )

    def record_coverage_need_attempt(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        actor_ref: str = "system",
        reason: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.record_coverage_need_attempt(
            self,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            actor_ref=actor_ref,
            reason=reason,
            metadata=metadata,
        )

    def satisfy_coverage_need(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        content_id: str | None = None,
        evidence_id: str | None = None,
        source_profile_id: str | None = None,
        actor_ref: str = "system",
        reason: str = "",
    ) -> str:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.satisfy_coverage_need(
            self,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            content_id=content_id,
            evidence_id=evidence_id,
            source_profile_id=source_profile_id,
            actor_ref=actor_ref,
            reason=reason,
        )

    def coverage_need_original_source_preflight(
        self,
        *,
        coverage_need_id: str,
        content_id: str,
    ) -> dict[str, Any]:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.coverage_need_original_source_preflight(
            self,
            coverage_need_id=coverage_need_id,
            content_id=content_id,
        )

    def block_coverage_need(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        blocker_code: str,
        actor_ref: str = "system",
        reason: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore

        return ClaimEvidenceObservationStore.block_coverage_need(
            self,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            blocker_code=blocker_code,
            actor_ref=actor_ref,
            reason=reason,
            metadata=metadata,
        )

    def insert_verification_run(
        self,
        *,
        run_id: str,
        claim_id: str,
        source_intelligence_assessment_id: str | None,
        verification_kind: str,
        verification_version: str,
        verification_rule: dict[str, Any],
        input_fingerprint: str,
        statement_cutoff: str,
        assessment: str,
        evidence_ids: list[str],
        observation_ids: list[str],
        blockers: list[str],
        rationale_codes: list[str],
        result: dict[str, Any],
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_verification_run(self, run_id=run_id, claim_id=claim_id, source_intelligence_assessment_id=source_intelligence_assessment_id, verification_kind=verification_kind, verification_version=verification_version, verification_rule=verification_rule, input_fingerprint=input_fingerprint, statement_cutoff=statement_cutoff, assessment=assessment, evidence_ids=evidence_ids, observation_ids=observation_ids, blockers=blockers, rationale_codes=rationale_codes, result=result)

    def latest_verification_template(
        self,
        claim_id: str,
    ) -> dict[str, Any] | None:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.latest_verification_template(self, claim_id)

    def latest_finding_id(
        self,
        claim_id: str,
        *,
        exclude_finding_id: str | None = None,
    ) -> str | None:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.latest_finding_id(self, claim_id, exclude_finding_id=exclude_finding_id)

    def insert_finding_draft(self, draft: dict[str, Any]) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_finding_draft(self, draft)

    def insert_relation_candidate(self, row: dict[str, Any]) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_relation_candidate(self, row=row)

    def insert_inference_candidate(self, row: dict[str, Any]) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_inference_candidate(self, row=row)

    def approve_relation_candidate_with_review(
        self,
        *,
        relation_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.approve_relation_candidate_with_review(self, relation_id=relation_id, event_id=event_id, actor_ref=actor_ref, reason=reason)

    def public_relation_candidates(
        self,
    ) -> list[dict[str, Any]]:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.public_relation_candidates(self)

    def insert_reanalysis_trigger(self, row: dict[str, Any]) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_reanalysis_trigger(self, row=row)

    def advance_reanalysis_trigger(
        self,
        trigger_id: str,
        *,
        status: str,
        enqueued_job_id: str | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.advance_reanalysis_trigger(
            self,
            trigger_id,
            status=status,
            enqueued_job_id=enqueued_job_id,
        )

    def record_review_event(
        self,
        *,
        event_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_ref: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.record_review_event(self, event_id=event_id, entity_type=entity_type, entity_id=entity_id, action=action, actor_ref=actor_ref, reason=reason, metadata=metadata)

    def insert_right_of_reply(
        self,
        *,
        reply_id: str,
        finding_id: str,
        submitter_name: str | None,
        submitter_role: str | None,
        body: str,
        evidence_urls: list[str],
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_right_of_reply(self, reply_id=reply_id, finding_id=finding_id, submitter_name=submitter_name, submitter_role=submitter_role, body=body, evidence_urls=evidence_urls)

    def attach_reply_reanalysis_job(
        self,
        *,
        reply_id: str,
        job_id: str,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.attach_reply_reanalysis_job(self, reply_id=reply_id, job_id=job_id)

    def publish_right_of_reply_with_review(
        self,
        *,
        reply_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.publish_right_of_reply_with_review(self, reply_id=reply_id, event_id=event_id, actor_ref=actor_ref, reason=reason)

    def insert_correction(
        self,
        *,
        correction_id: str,
        finding_id: str,
        previous_finding_id: str,
        reason: str,
        changed_fields: dict[str, Any],
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.insert_correction(self, correction_id=correction_id, finding_id=finding_id, previous_finding_id=previous_finding_id, reason=reason, changed_fields=changed_fields)

    def publish_correction_with_review(
        self,
        *,
        correction_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore

        return ReviewPublicationDecisionStore.publish_correction_with_review(self, correction_id=correction_id, event_id=event_id, actor_ref=actor_ref, reason=reason)

    def upsert_canonical_segments(
        self,
        *,
        content_id: str,
        variant_id: str,
        rows: list[dict[str, Any]],
    ) -> None:
        from dichiarazioni_pubbliche.queue_store import TranscriptCanonicalStore

        return TranscriptCanonicalStore.upsert_canonical_segments(
            self,
            content_id=content_id,
            variant_id=variant_id,
            rows=rows,
        )

    def state_counts(self) -> dict[str, int]:
        from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

        return QueueExecutionCostStore.state_counts(self)
