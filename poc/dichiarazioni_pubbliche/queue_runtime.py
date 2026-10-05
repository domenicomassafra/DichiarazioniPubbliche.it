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
from dichiarazioni_pubbliche.original_source_resolver import (
    resolve_reviewed_original_source,
)


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
) -> str:
    material = "\0".join((job_id, provider_id, operation, request_key)).encode()
    return "receipt:" + hashlib.sha256(material).hexdigest()


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


class QueueRuntimeStore(PsqlRuntime):
    def reap_expired(self, max_attempts: int = 5) -> int:
        raw = self.run(
            "SELECT reap_expired_processing_jobs(:'max_attempts'::integer)::text;",
            max_attempts=max(max_attempts, 1),
        )
        return int(raw or 0)

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
        raw = self.run(
            """
            WITH eligible AS (
                SELECT
                    finding.id,
                    finding.claim_id,
                    finding.verification_run_id
                FROM finding
                JOIN atomic_claim claim ON claim.id = finding.claim_id
                JOIN verification_run verification
                    ON verification.id = finding.verification_run_id
                WHERE
                    finding.id = :'finding_id'
                    AND verification.claim_id = claim.id
                    AND finding.assessment = verification.assessment
                    AND finding.publication_status IN ('POLICY_HOLD', 'PUBLISH')
                    AND jsonb_array_length(verification.blockers) = 0
                    AND jsonb_typeof(verification.evidence_ids) = 'array'
                    AND jsonb_array_length(verification.evidence_ids) > 0
                    AND jsonb_typeof(verification.observation_ids) = 'array'
                    AND jsonb_array_length(verification.observation_ids) > 0
                    AND (
                        EXISTS (
                            SELECT 1
                            FROM claim_segment link
                            WHERE link.claim_id = claim.id
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM claim_text_provenance provenance
                            WHERE
                                provenance.claim_id = claim.id
                                AND provenance.content_id = claim.content_id
                                AND provenance.person_id = claim.speaker_person_id
                                AND provenance.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event provenance_review
                                    WHERE
                                        provenance_review.entity_type =
                                            'CLAIM_TEXT_PROVENANCE'
                                        AND provenance_review.entity_id = provenance.id
                                        AND provenance_review.action = 'APPROVED'
                                )
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE
                            link.claim_id = claim.id
                            AND segment.publication_blocked = true
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM finding_evidence finding_source
                        WHERE finding_source.finding_id = finding.id
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence finding_source
                        WHERE
                            finding_source.finding_id = finding.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM claim_evidence_candidate candidate
                                WHERE
                                    candidate.claim_id = claim.id
                                    AND candidate.evidence_id =
                                        finding_source.evidence_id
                                    AND candidate.status = 'APPROVED'
                                    AND EXISTS (
                                        SELECT 1
                                        FROM review_event evidence_review
                                        WHERE
                                            evidence_review.entity_type =
                                                'CLAIM_EVIDENCE_CANDIDATE'
                                            AND evidence_review.entity_id =
                                                candidate.claim_id || '|' ||
                                                candidate.evidence_id || '|' ||
                                                candidate.retrieval_version
                                            AND evidence_review.action = 'APPROVED'
                                    )
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence finding_source
                        WHERE
                            finding_source.finding_id = finding.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM evidence_observation observation
                                WHERE
                                    observation.evidence_id =
                                        finding_source.evidence_id
                                    AND observation.status = 'APPROVED'
                                    AND verification.observation_ids ? observation.id
                                    AND EXISTS (
                                        SELECT 1
                                        FROM review_event observation_review
                                        WHERE
                                            observation_review.entity_type =
                                                'EVIDENCE_OBSERVATION'
                                            AND observation_review.entity_id =
                                                observation.id
                                            AND observation_review.action = 'APPROVED'
                                    )
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(
                            verification.evidence_ids
                        ) expected(evidence_id)
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM finding_evidence finding_source
                            WHERE
                                finding_source.finding_id = finding.id
                                AND finding_source.evidence_id =
                                    expected.evidence_id
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence finding_source
                        WHERE
                            finding_source.finding_id = finding.id
                            AND NOT (
                                verification.evidence_ids ?
                                    finding_source.evidence_id
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(
                            verification.observation_ids
                        ) expected(observation_id)
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM evidence_observation observation
                            JOIN finding_evidence finding_source
                                ON finding_source.evidence_id =
                                    observation.evidence_id
                            WHERE
                                finding_source.finding_id = finding.id
                                AND observation.id = expected.observation_id
                                AND observation.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event observation_review
                                    WHERE
                                        observation_review.entity_type =
                                            'EVIDENCE_OBSERVATION'
                                        AND observation_review.entity_id =
                                            observation.id
                                        AND observation_review.action =
                                            'APPROVED'
                                )
                        )
                    )
                    AND claim.speaker_person_id IS NOT NULL
                    AND NOT EXISTS (
                            SELECT 1
                            FROM claim_segment link
                            JOIN canonical_transcript_segment segment
                                ON segment.id = link.segment_id
                            WHERE
                                link.claim_id = claim.id
                                AND (
                                    segment.speaker_person_id IS DISTINCT FROM
                                        claim.speaker_person_id
                                    OR NOT EXISTS (
                                        SELECT 1
                                        FROM speaker_identity_candidate speaker
                                        WHERE
                                            speaker.content_id =
                                                segment.content_id
                                            AND speaker.person_id =
                                                claim.speaker_person_id
                                            AND speaker.status = 'APPROVED'
                                            AND EXISTS (
                                                SELECT 1
                                                FROM review_event speaker_review
                                                WHERE
                                                    speaker_review.entity_type =
                                                        'SPEAKER_IDENTITY_CANDIDATE'
                                                    AND speaker_review.entity_id =
                                                        speaker.id
                                                    AND speaker_review.action =
                                                        'APPROVED'
                                            )
                                            AND segment.start_ms >=
                                                speaker.start_ms
                                            AND segment.end_ms <= speaker.end_ms
                                    )
                                )
                        )
                FOR UPDATE OF finding
            ),
            changed AS (
                UPDATE finding target
                SET publication_status = 'PUBLISH'
                FROM eligible
                WHERE target.id = eligible.id
                RETURNING
                    target.id,
                    target.claim_id,
                    target.verification_run_id
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'FINDING',
                    changed.id,
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    jsonb_build_object(
                        'claim_id', changed.claim_id,
                        'verification_run_id', changed.verification_run_id,
                        'publication_status', 'PUBLISH'
                    )
                FROM changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            finding_id=finding_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def claim(self, worker_id: str, lease_seconds: int = 300) -> ProcessingJob | None:
        raw = self.run(
            """
            SELECT COALESCE(row_to_json(job)::text, '')
            FROM claim_processing_job(
                :'worker_id',
                :'lease_seconds'::integer
            ) AS job;
            """,
            worker_id=worker_id,
            lease_seconds=max(lease_seconds, 1),
        )
        if not raw:
            return None
        row = json.loads(raw)
        return ProcessingJob(
            job_id=row["id"],
            content_id=row["content_id"],
            job_type=row["job_type"],
            attempt=int(row.get("attempt") or 0),
            payload=row.get("payload") or {},
        )

    def renew(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        raw = self.run(
            """
            SELECT renew_processing_job_lease(
                :'job_id', :'worker_id', :'lease_seconds'::integer
            )::text;
            """,
            job_id=job_id,
            worker_id=worker_id,
            lease_seconds=max(lease_seconds, 1),
        )
        return raw.lower() in {"t", "true", "1"}

    def complete(self, job_id: str, worker_id: str) -> bool:
        raw = self.run(
            "SELECT complete_processing_job(:'job_id', :'worker_id')::text;",
            job_id=job_id,
            worker_id=worker_id,
        )
        return raw.lower() in {"t", "true", "1"}

    def retry(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        delay_seconds: int,
        max_attempts: int,
    ) -> str:
        return self.run(
            """
            SELECT retry_processing_job(
                :'job_id',
                :'worker_id',
                :'error',
                :'delay_seconds'::integer,
                :'max_attempts'::integer
            );
            """,
            job_id=job_id,
            worker_id=worker_id,
            error=error[:1000],
            delay_seconds=max(delay_seconds, 0),
            max_attempts=max(max_attempts, 1),
        )

    def defer(
        self,
        job_id: str,
        worker_id: str,
        reason: str,
        *,
        delay_seconds: int,
    ) -> bool:
        raw = self.run(
            """
            SELECT defer_processing_job(
                :'job_id',
                :'worker_id',
                :'reason',
                :'delay_seconds'::integer
            )::text;
            """,
            job_id=job_id,
            worker_id=worker_id,
            reason=reason[:1000],
            delay_seconds=max(delay_seconds, 0),
        )
        return raw.lower() in {"t", "true", "1"}

    def block(self, job_id: str, worker_id: str, reason: str) -> bool:
        raw = self.run(
            """
            SELECT block_processing_job(
                :'job_id', :'worker_id', :'reason'
            )::text;
            """,
            job_id=job_id,
            worker_id=worker_id,
            reason=reason[:1000],
        )
        return raw.lower() in {"t", "true", "1"}

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
        job_id = deterministic_followup_job_id(job_type, content_id, variant)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        raw = self.run(
            """
            SELECT enqueue_processing_job(
                :'job_id', :'content_id', :'job_type', :'payload'::jsonb
            )::text;
            """,
            job_id=job_id,
            content_id=content_id,
            job_type=job_type,
            payload=encoded,
        )
        return job_id, raw.lower() in {"t", "true", "1"}

    def enqueue_jobs_bulk(self, jobs: list[dict[str, Any]]) -> int:
        if not jobs:
            return 0
        encoded = json.dumps(jobs, ensure_ascii=False, separators=(",", ":"))
        quoted = _dollar_quote(encoded)
        raw = self.run_literal(
            f"""
            WITH input AS (
                SELECT *
                FROM jsonb_to_recordset({quoted}::jsonb) AS x(
                    id text,
                    content_id text,
                    job_type text,
                    state text,
                    payload jsonb,
                    last_error text
                )
            ),
            inserted AS (
                INSERT INTO processing_job (
                    id, content_id, job_type, state, payload, last_error
                )
                SELECT
                    id,
                    content_id,
                    job_type,
                    state,
                    COALESCE(payload, '{{}}'::jsonb),
                    NULLIF(last_error, '')
                FROM input
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT count(*)::text FROM inserted;
            """
        )
        return int(raw or 0)

    def cost_snapshot(self, source_id: str) -> CostSnapshot:
        raw = self.run(
            """
            SELECT json_build_object(
                'global', COALESCE(sum(r.estimated_cost_usd), 0),
                'source', COALESCE(sum(r.estimated_cost_usd)
                    FILTER (WHERE c.source_id = :'source_id'), 0)
            )::text
            FROM provider_receipt r
            LEFT JOIN content_item c ON c.id = r.content_id
            WHERE COALESCE(r.completed_at, r.started_at, now())
                >= date_trunc('day', now());
            """,
            source_id=source_id,
        )
        row = json.loads(raw or '{"global":0,"source":0}')
        return CostSnapshot(float(row["global"]), float(row["source"]))

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
    ) -> str:
        receipt_id = deterministic_receipt_id(
            job_id, provider_id, operation, request_key
        )
        encoded = json.dumps(
            {**receipt, "job_id": job_id},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.run(
            """
            WITH inserted AS (
                INSERT INTO provider_receipt (
                    id, content_id, provider_id, model_id, operation, request_id,
                    started_at, completed_at, input_bytes, input_seconds,
                    estimated_cost_usd, status, receipt
                ) VALUES (
                    :'receipt_id', :'content_id', :'provider_id',
                    NULLIF(:'model_id',''), :'operation', NULLIF(:'request_id',''),
                    now(), now(), NULLIF(:'input_bytes','')::bigint,
                    NULLIF(:'input_seconds','')::numeric,
                    :'estimated_cost_usd'::numeric, :'status', :'receipt'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING estimated_cost_usd
            )
            UPDATE processing_job
            SET cost_usd = cost_usd + COALESCE(
                (SELECT estimated_cost_usd FROM inserted), 0
            )
            WHERE id = :'job_id';
            """,
            receipt_id=receipt_id,
            content_id=content_id,
            provider_id=provider_id,
            model_id=model_id or "",
            operation=operation,
            request_id=request_id or "",
            input_bytes="" if input_bytes is None else input_bytes,
            input_seconds="" if input_seconds is None else input_seconds,
            estimated_cost_usd=max(float(estimated_cost_usd), 0.0),
            status=status,
            receipt=encoded,
            job_id=job_id,
        )
        return receipt_id

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
        variant_id = deterministic_variant_id(
            content_id, provider_id, source_kind, raw_text_sha256
        )
        encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        raw = self.run_literal(
            f"""
            WITH inserted AS (
                INSERT INTO transcript_variant (
                    id, content_id, provider_id, source_kind, language,
                    raw_text_sha256, raw_text, is_platform_caption,
                    is_manual_caption, metadata
                ) VALUES (
                    {_dollar_quote(variant_id)},
                    {_dollar_quote(content_id)},
                    {_dollar_quote(provider_id)},
                    {_dollar_quote(source_kind)},
                    {_dollar_quote(language)},
                    {_dollar_quote(raw_text_sha256)},
                    {_dollar_quote(raw_text)},
                    {'true' if is_platform_caption else 'false'},
                    {'true' if is_manual_caption else 'false'},
                    {_dollar_quote(encoded)}::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """
        )
        return variant_id, raw.lower() in {"t", "true", "1"}

    def insert_transcript_segments(
        self,
        *,
        variant_id: str,
        segments: list[dict[str, Any]],
    ) -> None:
        rows = []
        for item in segments:
            rows.append(
                {
                    "id": deterministic_segment_id(
                        variant_id, int(item["segment_index"])
                    ),
                    "variant_id": variant_id,
                    "segment_index": int(item["segment_index"]),
                    "start_ms": int(item["start_ms"]),
                    "end_ms": int(item["end_ms"]),
                    "text": str(item["text"]),
                    "metadata": item.get("metadata") or {},
                }
            )
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        quoted = _dollar_quote(payload)
        self.run_literal(
            f"""
            INSERT INTO transcript_segment (
                id, variant_id, segment_index, start_ms, end_ms, text, metadata
            )
            SELECT
                x.id, x.variant_id, x.segment_index, x.start_ms, x.end_ms,
                x.text, x.metadata
            FROM jsonb_to_recordset({quoted}::jsonb) AS x(
                id text,
                variant_id text,
                segment_index integer,
                start_ms bigint,
                end_ms bigint,
                text text,
                metadata jsonb
            )
            ON CONFLICT (variant_id, segment_index) DO NOTHING;
            """
        )

    def transcript_segments(self, variant_id: str) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'id', id,
                'segment_index', segment_index,
                'start_ms', start_ms,
                'end_ms', end_ms,
                'text', text
            ) ORDER BY segment_index)::text, '[]')
            FROM transcript_segment
            WHERE variant_id = :'variant_id';
            """,
            variant_id=variant_id,
        )
        return json.loads(raw or "[]")

    def canonical_candidate_variant_ids(self, content_id: str) -> set[str]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(DISTINCT s.variant_id)::text, '[]')
            FROM canonical_transcript_segment c
            JOIN canonical_segment_candidate cc
                ON cc.canonical_segment_id = c.id
            JOIN transcript_segment s
                ON s.id = cc.transcript_segment_id
            WHERE c.content_id = :'content_id';
            """,
            content_id=content_id,
        )
        return {str(value) for value in json.loads(raw or "[]")}

    def canonical_segments(self, content_id: str) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'id', id,
                'segment_index', segment_index,
                'start_ms', start_ms,
                'end_ms', end_ms,
                'canonical_text', canonical_text,
                'transcript_status', transcript_status,
                'publication_blocked', publication_blocked,
                'sensitive_signature', sensitive_signature
            ) ORDER BY segment_index)::text, '[]')
            FROM canonical_transcript_segment
            WHERE content_id = :'content_id';
            """,
            content_id=content_id,
        )
        return json.loads(raw or "[]")

    def insert_atomic_claims(self, claims: list[dict[str, Any]]) -> int:
        if not claims:
            return 0
        encoded = json.dumps(claims, ensure_ascii=False, separators=(",", ":"))
        quoted = _dollar_quote(encoded)
        raw = self.run_literal(
            f"""
            WITH input AS (
                SELECT *
                FROM jsonb_to_recordset({quoted}::jsonb) AS x(
                    id text,
                    content_id text,
                    normalized_claim text,
                    claim_type text,
                    claim_type_version text,
                    temporal_scope jsonb,
                    check_worthy boolean,
                    extraction_model text,
                    extraction_version text,
                    metadata jsonb,
                    segment_ids jsonb
                )
            ),
            inserted AS (
                INSERT INTO atomic_claim (
                    id,
                    content_id,
                    normalized_claim,
                    claim_type,
                    claim_type_version,
                    temporal_scope,
                    check_worthy,
                    extraction_model,
                    extraction_version,
                    metadata
                )
                SELECT
                    id,
                    content_id,
                    normalized_claim,
                    claim_type,
                    'atomic-claim-v1',
                    COALESCE(temporal_scope, '{{}}'::jsonb),
                    COALESCE(check_worthy, true),
                    extraction_model,
                    extraction_version,
                    COALESCE(metadata, '{{}}'::jsonb)
                FROM input
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            replayed AS (
                SELECT claim.id
                FROM atomic_claim claim
                JOIN input ON input.id = claim.id
                WHERE claim.content_id = input.content_id
                  AND claim.normalized_claim = input.normalized_claim
                  AND claim.claim_type = input.claim_type
                  AND claim.claim_type_version = 'atomic-claim-v1'
                  AND claim.temporal_scope = COALESCE(input.temporal_scope, '{{}}'::jsonb)
                  AND claim.check_worthy = COALESCE(input.check_worthy, true)
                  AND claim.extraction_model IS NOT DISTINCT FROM input.extraction_model
                  AND claim.extraction_version IS NOT DISTINCT FROM input.extraction_version
                  AND claim.metadata = COALESCE(input.metadata, '{{}}'::jsonb)
            ),
            rejected AS (
                SELECT input.id
                FROM input
                LEFT JOIN inserted ON inserted.id = input.id
                LEFT JOIN replayed ON replayed.id = input.id
                WHERE inserted.id IS NULL AND replayed.id IS NULL
            ),
            blocked AS (
                SELECT CASE WHEN count(*) > 0 THEN 1 ELSE 0 END AS has_rejected
                FROM rejected
            ),
            linked AS (
                INSERT INTO claim_segment (claim_id, segment_id)
                SELECT
                    input.id,
                    segment.value
                FROM input
                JOIN inserted ON inserted.id = input.id
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    COALESCE(input.segment_ids, '[]'::jsonb)
                ) AS segment(value)
                JOIN canonical_transcript_segment canonical
                    ON canonical.id = segment.value
                    AND canonical.content_id = input.content_id
                ON CONFLICT DO NOTHING
                RETURNING claim_id
            )
            SELECT CASE
                WHEN (SELECT has_rejected FROM blocked) = 1 THEN '0'
                ELSE (
                    (SELECT count(*) FROM inserted) +
                    (SELECT count(*) FROM replayed)
                )::text
            END;
            """
        )
        return int(raw or 0)

    def claim_count(self, content_id: str) -> int:
        raw = self.run(
            """
            SELECT count(*)::text
            FROM atomic_claim
            WHERE content_id = :'content_id';
            """,
            content_id=content_id,
        )
        return int(raw or 0)

    def unfinished_sibling_jobs(
        self,
        *,
        content_id: str,
        job_type: str,
        exclude_job_id: str,
    ) -> int:
        raw = self.run(
            """
            SELECT count(*)::text
            FROM processing_job
            WHERE
                content_id = :'content_id'
                AND job_type = :'job_type'
                AND id <> :'exclude_job_id'
                AND state <> 'COMPLETED';
            """,
            content_id=content_id,
            job_type=job_type,
            exclude_job_id=exclude_job_id,
        )
        return int(raw or 0)

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
        excerpt: str | None = None,
        reference_period: str | None = None,
        independence_group: str | None = None,
        rights_status: str = "UNKNOWN",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        encoded = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO evidence (
                    id,
                    canonical_url,
                    publisher,
                    source_type,
                    publication_date,
                    fetched_at,
                    content_sha256,
                    excerpt,
                    reference_period,
                    independence_group,
                    rights_status,
                    metadata
                ) VALUES (
                    :'evidence_id',
                    :'canonical_url',
                    :'publisher',
                    :'source_type',
                    NULLIF(:'publication_date','')::date,
                    NULLIF(:'fetched_at','')::timestamptz,
                    :'content_sha256',
                    NULLIF(:'excerpt',''),
                    NULLIF(:'reference_period',''),
                    NULLIF(:'independence_group',''),
                    :'rights_status',
                    :'metadata'::jsonb
                )
                ON CONFLICT (id) DO UPDATE SET
                    fetched_at = COALESCE(EXCLUDED.fetched_at, evidence.fetched_at),
                    metadata = evidence.metadata || EXCLUDED.metadata
                RETURNING (xmax = 0) AS created
            )
            SELECT COALESCE(bool_or(created), false)::text FROM inserted;
            """,
            evidence_id=evidence_id,
            canonical_url=canonical_url,
            publisher=publisher,
            source_type=source_type,
            publication_date=publication_date or "",
            fetched_at=fetched_at,
            content_sha256=content_sha256,
            excerpt=excerpt or "",
            reference_period=reference_period or "",
            independence_group=independence_group or "",
            rights_status=rights_status,
            metadata=encoded,
        )
        return raw.lower() in {"t", "true", "1"}

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
        if relation_candidate not in {
            "SUPPORT",
            "CONTRADICT",
            "CONTEXT",
            "UPDATE",
            "UNKNOWN",
        }:
            raise ValueError("invalid relation_candidate")
        if status == "APPROVED":
            raise ValueError("APPROVED evidence requires review ledger")
        if status not in {"RETRIEVED", "REJECTED", "QUARANTINED"}:
            raise ValueError("invalid evidence candidate status")
        if score is not None and not 0 <= float(score) <= 1:
            raise ValueError("evidence score must be in [0,1]")
        encoded = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO claim_evidence_candidate (
                    claim_id,
                    evidence_id,
                    retrieval_method,
                    retrieval_version,
                    relation_candidate,
                    status,
                    score,
                    statement_cutoff,
                    metadata
                ) VALUES (
                    :'claim_id',
                    :'evidence_id',
                    :'retrieval_method',
                    :'retrieval_version',
                    :'relation_candidate',
                    :'status',
                    NULLIF(:'score','')::numeric,
                    NULLIF(:'statement_cutoff','')::date,
                    :'metadata'::jsonb
                )
                ON CONFLICT (claim_id, evidence_id, retrieval_version)
                DO UPDATE SET
                    relation_candidate = EXCLUDED.relation_candidate,
                    status = EXCLUDED.status,
                    score = EXCLUDED.score,
                    statement_cutoff = EXCLUDED.statement_cutoff,
                    metadata = claim_evidence_candidate.metadata || EXCLUDED.metadata
                RETURNING (xmax = 0) AS created
            )
            SELECT COALESCE(bool_or(created), false)::text FROM inserted;
            """,
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
            status=status,
            score="" if score is None else float(score),
            statement_cutoff=statement_cutoff or "",
            metadata=encoded,
        )
        return raw.lower() in {"t", "true", "1"}

    def claim_evidence_count(self, claim_id: str) -> int:
        raw = self.run(
            """
            SELECT count(*)::text
            FROM claim_evidence_candidate
            WHERE claim_id = :'claim_id';
            """,
            claim_id=claim_id,
        )
        return int(raw or 0)

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
        if status == "APPROVED":
            raise ValueError("APPROVED observation requires review ledger")
        if status not in {"CANDIDATE", "REJECTED", "QUARANTINED"}:
            raise ValueError("invalid evidence observation status")
        if value_numeric is None and value_text is None:
            raise ValueError("evidence observation requires a value")
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO evidence_observation (
                    id, evidence_id, observation_type, metric, value_numeric,
                    value_text, unit, reference_period, dimensions,
                    extraction_method, extraction_version, source_pointer,
                    status, metadata
                ) VALUES (
                    :'observation_id', :'evidence_id', :'observation_type',
                    NULLIF(:'metric',''), NULLIF(:'value_numeric','')::numeric,
                    NULLIF(:'value_text',''), NULLIF(:'unit',''),
                    NULLIF(:'reference_period',''), :'dimensions'::jsonb,
                    :'extraction_method', :'extraction_version',
                    :'source_pointer'::jsonb, :'status', :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            observation_id=observation_id,
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=metric or "",
            value_numeric="" if value_numeric is None else float(value_numeric),
            value_text=value_text or "",
            unit=unit or "",
            reference_period=reference_period or "",
            dimensions=json.dumps(dimensions, ensure_ascii=False, separators=(",", ":")),
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=json.dumps(
                source_pointer, ensure_ascii=False, separators=(",", ":")
            ),
            status=status,
            metadata=json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def update_evidence_observation_status(
        self,
        observation_id: str,
        status: str,
    ) -> bool:
        if status == "APPROVED":
            raise ValueError("APPROVED observation requires review ledger")
        if status not in {"CANDIDATE", "REJECTED", "QUARANTINED"}:
            raise ValueError("invalid evidence observation status")
        raw = self.run(
            """
            WITH changed AS (
                UPDATE evidence_observation
                SET status = :'status'
                WHERE id = :'observation_id'
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            observation_id=observation_id,
            status=status,
        )
        return raw.lower() in {"t", "true", "1"}

    def update_claim_evidence_status(
        self,
        *,
        claim_id: str,
        evidence_id: str,
        retrieval_version: str,
        status: str,
    ) -> bool:
        if status == "APPROVED":
            raise ValueError("APPROVED evidence requires review ledger")
        if status not in {"RETRIEVED", "REJECTED", "QUARANTINED"}:
            raise ValueError("invalid evidence candidate status")
        raw = self.run(
            """
            WITH changed AS (
                UPDATE claim_evidence_candidate
                SET status = :'status'
                WHERE
                    claim_id = :'claim_id'
                    AND evidence_id = :'evidence_id'
                    AND retrieval_version = :'retrieval_version'
                RETURNING claim_id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_version=retrieval_version,
            status=status,
        )
        return raw.lower() in {"t", "true", "1"}

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
            WITH changed AS (
                UPDATE claim_evidence_candidate
                SET status = 'APPROVED'
                WHERE
                    claim_id = :'claim_id'
                    AND evidence_id = :'evidence_id'
                    AND retrieval_version = :'retrieval_version'
                RETURNING claim_id
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
                FROM changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
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
        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'claim_id', claim.id,
                'content_id', claim.content_id,
                'normalized_claim', claim.normalized_claim,
                'claim_type', claim.claim_type,
                'temporal_scope', claim.temporal_scope,
                'metadata', claim.metadata,
                'statement_date', COALESCE(
                    NULLIF(claim.temporal_scope->>'statement_date', ''),
                    ''
                )
            )::text, '')
            FROM atomic_claim claim
            JOIN content_item content ON content.id = claim.content_id
            WHERE claim.id = :'claim_id';
            """,
            claim_id=claim_id,
        )
        if not raw:
            raise KeyError(f"Unknown claim_id: {claim_id}")
        return json.loads(raw)

    def finding_context(self, finding_id: str) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'finding_id', finding.id,
                'claim_id', finding.claim_id,
                'content_id', claim.content_id,
                'publication_status', finding.publication_status,
                'supersedes_id', finding.supersedes_id
            )::text, '')
            FROM finding
            JOIN atomic_claim claim ON claim.id = finding.claim_id
            WHERE finding.id = :'finding_id';
            """,
            finding_id=finding_id,
        )
        if not raw:
            raise KeyError(f"Unknown finding_id: {finding_id}")
        return json.loads(raw)

    def approved_verification_evidence(
        self,
        claim_id: str,
    ) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'evidence_id', evidence.id,
                'observation_id', observation.id,
                'source_id', COALESCE(evidence.metadata->>'evidence_source_id', ''),
                'source_type', evidence.source_type,
                'publisher', evidence.publisher,
                'publication_date', evidence.publication_date::text,
                'valid_from', evidence.valid_from::text,
                'valid_until', evidence.valid_until::text,
                'record_status', evidence.status,
                'metric', observation.metric,
                'value_numeric', observation.value_numeric,
                'value_text', observation.value_text,
                'unit', observation.unit,
                'reference_period', COALESCE(
                    observation.reference_period,
                    evidence.reference_period
                ),
                'independence_group', evidence.independence_group,
                'rights_status', evidence.rights_status,
                'dimensions', observation.dimensions,
                'authoritative', COALESCE(
                    evidence.metadata->>'authoritative', 'false'
                ) = 'true',
                'status', observation.status,
                'metadata', evidence.metadata || observation.metadata || jsonb_build_object(
                    'observation_type', observation.observation_type,
                    'extraction_method', observation.extraction_method,
                    'extraction_version', observation.extraction_version,
                    'source_pointer', observation.source_pointer
                )
            ) ORDER BY evidence.id, observation.id)::text, '[]')
            FROM claim_evidence_candidate link
            JOIN evidence ON evidence.id = link.evidence_id
            JOIN evidence_observation observation
                ON observation.evidence_id = evidence.id
            WHERE
                link.claim_id = :'claim_id'
                AND link.status = 'APPROVED'
                AND observation.status = 'APPROVED'
                AND evidence.publication_date IS NOT NULL;
            """,
            claim_id=claim_id,
        )
        return json.loads(raw or "[]")

    def source_intelligence_relations(self) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'from_profile_id', from_source_profile_id,
                'to_profile_id', to_source_profile_id,
                'relation_type', relation_type,
                'status', status,
                'evidence_basis', evidence_basis,
                'derivation_candidate_id', derivation_candidate_id
            ) ORDER BY id)::text, '[]')
            FROM source_relation
            WHERE status IN ('CANDIDATE', 'APPROVED');
            """
        )
        return json.loads(raw or "[]")

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
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO evidence_set_assessment (
                    id, atomic_claim_id, claim_candidate_id, requirement_profile_id,
                    requirement_profile_version, input_fingerprint, assessment,
                    qualifying_evidence_ids, rejected_evidence, satisfied_rules,
                    missing_rules, conflict_groups, coverage_need_candidates,
                    rationale_codes, assessment_version, metadata
                ) VALUES (
                    :'assessment_id', NULLIF(:'atomic_claim_id',''),
                    NULLIF(:'claim_candidate_id',''), :'requirement_profile_id',
                    :'requirement_profile_version', :'input_fingerprint', :'assessment',
                    :'qualifying_evidence_ids'::jsonb, :'rejected_evidence'::jsonb,
                    :'satisfied_rules'::jsonb, :'missing_rules'::jsonb,
                    :'conflict_groups'::jsonb, :'coverage_need_candidates'::jsonb,
                    :'rationale_codes'::jsonb, :'assessment_version', '{}'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            assessment_id=assessment_id,
            atomic_claim_id=atomic_claim_id or "",
            claim_candidate_id=claim_candidate_id or "",
            requirement_profile_id=requirement_profile_id,
            requirement_profile_version=requirement_profile_version,
            input_fingerprint=input_fingerprint,
            assessment=assessment,
            qualifying_evidence_ids=json.dumps(
                qualifying_evidence_ids, ensure_ascii=False, separators=(",", ":")
            ),
            rejected_evidence=json.dumps(
                rejected_evidence, ensure_ascii=False, separators=(",", ":")
            ),
            satisfied_rules=json.dumps(satisfied_rules, separators=(",", ":")),
            missing_rules=json.dumps(missing_rules, separators=(",", ":")),
            conflict_groups=json.dumps(
                conflict_groups, ensure_ascii=False, separators=(",", ":")
            ),
            coverage_need_candidates=json.dumps(
                coverage_need_candidates, ensure_ascii=False, separators=(",", ":")
            ),
            rationale_codes=json.dumps(rationale_codes, separators=(",", ":")),
            assessment_version=assessment_version,
        )
        return raw.lower() in {"t", "true", "1"}

    def coverage_collection_ids_for_claim(self, claim_id: str) -> list[str]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(link.collection_id ORDER BY link.collection_id)::text, '[]')
            FROM atomic_claim claim
            JOIN research_collection_content link
              ON link.content_id=claim.content_id AND link.status='INCLUDED'
            JOIN research_collection collection
              ON collection.id=link.collection_id AND collection.status='ACTIVE'
            WHERE claim.id=:'claim_id';
            """,
            claim_id=claim_id,
        )
        return [str(item) for item in json.loads(raw or "[]")]

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
        raw = self.run(
            """
            WITH inserted AS (
              INSERT INTO coverage_need(
                id,collection_id,atomic_claim_id,claim_candidate_id,
                source_intelligence_assessment_id,need_type,requirement_kind,
                requirement_fingerprint,question,required_roles,authority_scope,
                temporal_constraints,independence_requirement,status,attempt_count,
                max_attempts,created_by,metadata
              ) VALUES (
                :'id',NULLIF(:'collection_id',''),NULLIF(:'atomic_claim_id',''),
                NULLIF(:'claim_candidate_id',''),NULLIF(:'source_intelligence_assessment_id',''),
                :'need_type',:'requirement_kind',:'requirement_fingerprint',:'question',
                :'required_roles'::jsonb,:'authority_scope'::jsonb,
                :'temporal_constraints'::jsonb,NULLIF(:'independence_requirement','')::integer,
                'OPEN',0,:'max_attempts'::integer,:'created_by',:'metadata'::jsonb
              ) ON CONFLICT (id) DO NOTHING RETURNING id
            ), compatible AS (
              SELECT need.id, need.status, need.source_intelligence_assessment_id
              FROM coverage_need need
              WHERE need.id=:'id'
                AND need.collection_id IS NOT DISTINCT FROM NULLIF(:'collection_id','')
                AND need.atomic_claim_id IS NOT DISTINCT FROM NULLIF(:'atomic_claim_id','')
                AND need.claim_candidate_id IS NOT DISTINCT FROM NULLIF(:'claim_candidate_id','')
                AND need.need_type=:'need_type'
                AND need.requirement_kind=:'requirement_kind'
                AND need.requirement_fingerprint=:'requirement_fingerprint'
                AND need.question=:'question'
                AND need.required_roles=:'required_roles'::jsonb
                AND need.authority_scope=:'authority_scope'::jsonb
                AND need.temporal_constraints=:'temporal_constraints'::jsonb
                AND need.independence_requirement IS NOT DISTINCT FROM NULLIF(:'independence_requirement','')::integer
                AND need.max_attempts=:'max_attempts'::integer
                AND need.created_by=:'created_by'
            ), refreshed AS (
              UPDATE coverage_need need
              SET source_intelligence_assessment_id=NULLIF(:'source_intelligence_assessment_id',''),
                  updated_at=now()
              FROM compatible current
              WHERE need.id=current.id
                AND current.status IN ('OPEN','SEARCHING')
                AND current.source_intelligence_assessment_id IS DISTINCT FROM NULLIF(:'source_intelligence_assessment_id','')
              RETURNING need.id, current.status
            ), created_event AS (
              INSERT INTO coverage_need_event(
                id,coverage_need_id,event_type,from_status,to_status,
                source_intelligence_assessment_id,actor_ref,reason,metadata
              )
              SELECT :'created_event_id',:'id','CREATED',NULL,'OPEN',
                     NULLIF(:'source_intelligence_assessment_id',''),'system',
                     'SOURCE_INTELLIGENCE_REQUIREMENT_MISSING','{}'::jsonb
              FROM inserted
              ON CONFLICT (id) DO NOTHING RETURNING id
            ), observed_event AS (
              INSERT INTO coverage_need_event(
                id,coverage_need_id,event_type,from_status,to_status,
                source_intelligence_assessment_id,actor_ref,reason,metadata
              )
              SELECT :'observed_event_id',:'id','OBSERVED_AGAIN',status,status,
                     NULLIF(:'source_intelligence_assessment_id',''),'system',
                     'SOURCE_INTELLIGENCE_REQUIREMENT_STILL_MISSING','{}'::jsonb
              FROM refreshed
              ON CONFLICT (id) DO NOTHING RETURNING id
            )
            SELECT CASE
              WHEN EXISTS(SELECT 1 FROM inserted) THEN 'CREATED'
              WHEN EXISTS(SELECT 1 FROM refreshed) THEN 'UPDATED'
              WHEN EXISTS(SELECT 1 FROM compatible) THEN 'EXISTING'
              ELSE 'CONFLICT'
            END;
            """,
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
        if raw == "CONFLICT":
            raise RuntimeError("COVERAGE_NEED_IDENTITY_CONFLICT")
        return raw

    def searchable_coverage_needs(
        self,
        *,
        collection_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not 1 <= int(limit) <= 500:
            raise ValueError("COVERAGE_NEED_LIMIT_INVALID")
        raw = self.run(
            """
            SELECT COALESCE(json_agg(row_to_json(need) ORDER BY need.updated_at, need.id)::text, '[]')
            FROM (
              SELECT id,collection_id,atomic_claim_id,claim_candidate_id,need_type,
                     requirement_kind,question,required_roles,authority_scope,
                     temporal_constraints,independence_requirement,status,attempt_count,
                     max_attempts,updated_at
              FROM coverage_need
              WHERE status IN ('OPEN','SEARCHING')
                AND attempt_count < max_attempts
                AND (NULLIF(:'collection_id','') IS NULL OR collection_id=:'collection_id')
              ORDER BY updated_at,id
              LIMIT :'limit'::integer
            ) need;
            """,
            collection_id=collection_id or "",
            limit=limit,
        )
        return json.loads(raw or "[]")

    def record_coverage_need_attempt(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        actor_ref: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        raw = self.run(
            """
            WITH current AS (
              SELECT * FROM coverage_need WHERE id=:'coverage_need_id' FOR UPDATE
            ), changed AS (
              UPDATE coverage_need need
              SET attempt_count=current.attempt_count+1,
                  status=CASE WHEN current.attempt_count+1 >= current.max_attempts THEN 'BLOCKED' ELSE 'SEARCHING' END,
                  blocker_code=CASE WHEN current.attempt_count+1 >= current.max_attempts THEN 'MAX_ATTEMPTS_REACHED' ELSE NULL END,
                  resolved_at=CASE WHEN current.attempt_count+1 >= current.max_attempts THEN now() ELSE NULL END,
                  updated_at=now()
              FROM current
              WHERE need.id=current.id
                AND current.status IN ('OPEN','SEARCHING')
                AND current.attempt_count < current.max_attempts
              RETURNING need.id,current.status AS from_status,need.status AS to_status,need.attempt_count
            ), logged AS (
              INSERT INTO coverage_need_event(
                id,coverage_need_id,event_type,from_status,to_status,attempt_number,
                actor_ref,reason,metadata
              )
              SELECT :'event_id',id,'SEARCH_ATTEMPT',from_status,to_status,attempt_count,
                     :'actor_ref',NULLIF(:'reason',''),'{}'::jsonb
              FROM changed ON CONFLICT (id) DO NOTHING RETURNING id
            )
            SELECT COALESCE(json_build_object(
              'changed', EXISTS(SELECT 1 FROM changed),
              'status', COALESCE((SELECT to_status FROM changed),(SELECT status FROM current)),
              'attempt_count', COALESCE((SELECT attempt_count FROM changed),(SELECT attempt_count FROM current)),
              'searchable', COALESCE((SELECT to_status IN ('OPEN','SEARCHING') FROM changed), false)
            )::text, '{}');
            """,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            actor_ref=actor_ref,
            reason=reason,
        )
        return json.loads(raw or "{}")

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
        if not any((content_id, evidence_id, source_profile_id)):
            raise ValueError("COVERAGE_NEED_SATISFACTION_LINK_REQUIRED")
        if content_id:
            preflight = self.coverage_need_original_source_preflight(
                coverage_need_id=coverage_need_id,
                content_id=content_id,
            )
            if preflight["required"] and not preflight["accepted"]:
                blocker = str(preflight.get("blocker") or "ORIGINAL_SOURCE_REQUIRED")
                root = str(preflight.get("root_content_id") or "")
                suffix = f":{root}" if root else ""
                raise ValueError(
                    f"COVERAGE_NEED_ORIGINAL_SOURCE_REFUSED:{blocker}{suffix}"
                )
        raw = self.run(
            """
            WITH current AS (
              SELECT * FROM coverage_need WHERE id=:'coverage_need_id' FOR UPDATE
            ), changed AS (
              UPDATE coverage_need need
              SET status='SATISFIED', resolved_at=now(), updated_at=now(), blocker_code=NULL,
                  satisfied_by_content_id=NULLIF(:'content_id',''),
                  satisfied_by_evidence_id=NULLIF(:'evidence_id',''),
                  satisfied_by_source_profile_id=NULLIF(:'source_profile_id','')
              FROM current
              WHERE need.id=current.id AND current.status IN ('OPEN','SEARCHING')
              RETURNING need.id,current.status AS from_status
            ), logged AS (
              INSERT INTO coverage_need_event(
                id,coverage_need_id,event_type,from_status,to_status,content_id,evidence_id,
                source_profile_id,actor_ref,reason,metadata
              )
              SELECT :'event_id',id,'SATISFIED',from_status,'SATISFIED',
                     NULLIF(:'content_id',''),NULLIF(:'evidence_id',''),NULLIF(:'source_profile_id',''),
                     :'actor_ref',NULLIF(:'reason',''),'{}'::jsonb
              FROM changed ON CONFLICT (id) DO NOTHING RETURNING id
            )
            SELECT CASE
              WHEN EXISTS(SELECT 1 FROM changed) THEN 'SATISFIED'
              WHEN EXISTS(SELECT 1 FROM current WHERE status='SATISFIED'
                AND satisfied_by_content_id IS NOT DISTINCT FROM NULLIF(:'content_id','')
                AND satisfied_by_evidence_id IS NOT DISTINCT FROM NULLIF(:'evidence_id','')
                AND satisfied_by_source_profile_id IS NOT DISTINCT FROM NULLIF(:'source_profile_id','')) THEN 'EXISTING'
              WHEN EXISTS(SELECT 1 FROM current) THEN 'TERMINAL_CONFLICT'
              ELSE 'NOT_FOUND'
            END;
            """,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            content_id=content_id or "",
            evidence_id=evidence_id or "",
            source_profile_id=source_profile_id or "",
            actor_ref=actor_ref,
            reason=reason,
        )
        return raw

    def coverage_need_original_source_preflight(
        self,
        *,
        coverage_need_id: str,
        content_id: str,
    ) -> dict[str, Any]:
        need_raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'id', id,
                'need_type', need_type,
                'status', status
            )::text, '')
            FROM coverage_need
            WHERE id=:'coverage_need_id';
            """,
            coverage_need_id=coverage_need_id,
        )
        if not need_raw:
            return {
                "required": False,
                "accepted": True,
                "status": "NOT_FOUND",
            }
        need = json.loads(need_raw)
        need_type = str(need.get("need_type") or "")
        if need_type not in {"PRIMARY_SOURCE", "ORIGINAL_MEDIA", "ATTRIBUTION_GAP"}:
            return {
                "required": False,
                "accepted": True,
                "status": "NOT_APPLICABLE",
            }

        context_raw = self.run(
            """
            WITH matching_family AS (
              SELECT DISTINCT family.id, family.root_content_id, family.status
              FROM content_derivation_family family
              LEFT JOIN content_derivation_candidate edge
                ON edge.family_id=family.id
              WHERE family.status='APPROVED'
                AND (
                  family.root_content_id=:'content_id'
                  OR edge.derived_content_id=:'content_id'
                  OR edge.origin_content_id=:'content_id'
                )
            )
            SELECT json_build_object(
              'families', COALESCE((
                SELECT json_agg(json_build_object(
                  'id', family.id,
                  'root_content_id', family.root_content_id,
                  'status', family.status
                ) ORDER BY family.id)
                FROM matching_family family
              ), '[]'::json),
              'edges', COALESCE((
                SELECT json_agg(json_build_object(
                  'id', edge.id,
                  'family_id', edge.family_id,
                  'derived_content_id', edge.derived_content_id,
                  'origin_content_id', edge.origin_content_id,
                  'relation_type', edge.relation_type,
                  'status', edge.status
                ) ORDER BY edge.family_id, edge.id)
                FROM content_derivation_candidate edge
                JOIN matching_family family ON family.id=edge.family_id
                WHERE edge.status IN ('CANDIDATE','APPROVED')
              ), '[]'::json)
            )::text;
            """,
            content_id=content_id,
        )
        context = json.loads(context_raw or '{"families":[],"edges":[]}')
        resolution = resolve_reviewed_original_source(
            content_id,
            families=context.get("families") or [],
            edges=context.get("edges") or [],
        )
        blocker = resolution.blockers[0] if resolution.blockers else None
        accepted = resolution.resolved and resolution.root_content_id == content_id
        if resolution.resolved and not accepted:
            blocker = "DERIVED_CONTENT_NOT_ORIGINAL_ROOT"
        return {
            "required": True,
            "accepted": accepted,
            "status": resolution.status,
            "root_content_id": resolution.root_content_id,
            "path_content_ids": list(resolution.path_content_ids),
            "path_edge_ids": list(resolution.path_edge_ids),
            "blocker": blocker,
        }

    def block_coverage_need(
        self,
        *,
        coverage_need_id: str,
        event_id: str,
        blocker_code: str,
        actor_ref: str = "system",
        reason: str = "",
    ) -> str:
        if not str(blocker_code).strip():
            raise ValueError("COVERAGE_NEED_BLOCKER_REQUIRED")
        raw = self.run(
            """
            WITH current AS (
              SELECT * FROM coverage_need WHERE id=:'coverage_need_id' FOR UPDATE
            ), changed AS (
              UPDATE coverage_need need
              SET status='BLOCKED',blocker_code=:'blocker_code',resolved_at=now(),updated_at=now()
              FROM current
              WHERE need.id=current.id AND current.status IN ('OPEN','SEARCHING')
              RETURNING need.id,current.status AS from_status
            ), logged AS (
              INSERT INTO coverage_need_event(
                id,coverage_need_id,event_type,from_status,to_status,actor_ref,reason,metadata
              )
              SELECT :'event_id',id,'BLOCKED',from_status,'BLOCKED',:'actor_ref',
                     NULLIF(:'reason',''),jsonb_build_object('blocker_code',:'blocker_code')
              FROM changed ON CONFLICT (id) DO NOTHING RETURNING id
            )
            SELECT CASE
              WHEN EXISTS(SELECT 1 FROM changed) THEN 'BLOCKED'
              WHEN EXISTS(SELECT 1 FROM current WHERE status='BLOCKED' AND blocker_code=:'blocker_code') THEN 'EXISTING'
              WHEN EXISTS(SELECT 1 FROM current) THEN 'TERMINAL_CONFLICT'
              ELSE 'NOT_FOUND'
            END;
            """,
            coverage_need_id=coverage_need_id,
            event_id=event_id,
            blocker_code=str(blocker_code).strip(),
            actor_ref=actor_ref,
            reason=reason,
        )
        return raw

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
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO verification_run (
                    id, claim_id, source_intelligence_assessment_id,
                    verification_kind, verification_version,
                    verification_rule, input_fingerprint, statement_cutoff,
                    assessment, evidence_ids, observation_ids, blockers,
                    rationale_codes, result
                ) VALUES (
                    :'run_id', :'claim_id', NULLIF(:'source_intelligence_assessment_id',''),
                    :'verification_kind',
                    :'verification_version', :'verification_rule'::jsonb,
                    :'input_fingerprint', :'statement_cutoff'::date,
                    :'assessment', :'evidence_ids'::jsonb,
                    :'observation_ids'::jsonb, :'blockers'::jsonb,
                    :'rationale_codes'::jsonb, :'result'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            run_id=run_id,
            claim_id=claim_id,
            source_intelligence_assessment_id=source_intelligence_assessment_id or "",
            verification_kind=verification_kind,
            verification_version=verification_version,
            verification_rule=json.dumps(
                verification_rule, ensure_ascii=False, separators=(",", ":")
            ),
            input_fingerprint=input_fingerprint,
            statement_cutoff=statement_cutoff,
            assessment=assessment,
            evidence_ids=json.dumps(evidence_ids, separators=(",", ":")),
            observation_ids=json.dumps(observation_ids, separators=(",", ":")),
            blockers=json.dumps(blockers, separators=(",", ":")),
            rationale_codes=json.dumps(rationale_codes, separators=(",", ":")),
            result=json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        )
        return raw.lower() in {"t", "true", "1"}

    def latest_verification_template(
        self,
        claim_id: str,
    ) -> dict[str, Any] | None:
        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'verification_kind', verification_kind,
                'verification_rule', verification_rule,
                'statement_cutoff', statement_cutoff::text,
                'verification_version', verification_version
            )::text, '')
            FROM verification_run
            WHERE claim_id = :'claim_id'
            ORDER BY created_at DESC, id DESC
            LIMIT 1;
            """,
            claim_id=claim_id,
        )
        return json.loads(raw) if raw else None

    def latest_finding_id(
        self,
        claim_id: str,
        *,
        exclude_finding_id: str | None = None,
    ) -> str | None:
        raw = self.run(
            """
            SELECT COALESCE(id, '')
            FROM finding
            WHERE
                claim_id = :'claim_id'
                AND (
                    NULLIF(:'exclude_finding_id','') IS NULL
                    OR id <> :'exclude_finding_id'
                )
            ORDER BY created_at DESC, id DESC
            LIMIT 1;
            """,
            claim_id=claim_id,
            exclude_finding_id=exclude_finding_id or "",
        )
        return raw or None

    def insert_finding_draft(self, draft: dict[str, Any]) -> bool:
        evidence_ids = json.dumps(
            list(draft.get("evidence_ids") or []),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        rationale = str(draft["rationale"])
        assertion_id = finding_assertion_id(draft["finding_id"], rationale)
        assertion_sha256 = assertion_text_sha256(rationale)
        raw = self.run(
            """
            WITH eligible AS (
                SELECT verification.observation_ids
                FROM verification_run verification
                WHERE
                    verification.id = :'verification_run_id'
                    AND verification.claim_id = :'claim_id'
                    AND verification.assessment = :'assessment'
                    AND verification.evidence_ids @> :'evidence_ids'::jsonb
                    AND :'evidence_ids'::jsonb @> verification.evidence_ids
            ),
            inserted AS (
                INSERT INTO finding (
                    id, claim_id, assessment, assessment_version, rationale,
                    publication_status, publication_status_version,
                    policy_version, model_bundle, verification_run_id,
                    supersedes_id
                )
                SELECT
                    :'finding_id', :'claim_id', :'assessment',
                    'deterministic-verification-v2', :'rationale',
                    :'publication_status', 'finding-publication-v1',
                    :'policy_version',
                    :'model_bundle'::jsonb, :'verification_run_id',
                    NULLIF(:'supersedes_id','')
                FROM eligible
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            existing_exact AS (
                SELECT finding.id
                FROM finding
                CROSS JOIN eligible
                WHERE
                    finding.id = :'finding_id'
                    AND finding.claim_id = :'claim_id'
                    AND finding.assessment = :'assessment'
                    AND finding.assessment_version = 'deterministic-verification-v2'
                    AND finding.rationale = :'rationale'
                    AND finding.publication_status = :'publication_status'
                    AND finding.publication_status_version = 'finding-publication-v1'
                    AND finding.policy_version = :'policy_version'
                    AND finding.model_bundle = :'model_bundle'::jsonb
                    AND finding.verification_run_id = :'verification_run_id'
                    AND finding.supersedes_id IS NOT DISTINCT FROM
                        NULLIF(:'supersedes_id','')
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(
                            :'evidence_ids'::jsonb
                        ) expected(evidence_id)
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM finding_evidence existing_link
                            WHERE
                                existing_link.finding_id = finding.id
                                AND existing_link.evidence_id =
                                    expected.evidence_id
                                AND existing_link.relation =
                                    'VERIFICATION_INPUT'
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence existing_link
                        WHERE
                            existing_link.finding_id = finding.id
                            AND existing_link.relation =
                                'VERIFICATION_INPUT'
                            AND NOT (
                                :'evidence_ids'::jsonb ?
                                existing_link.evidence_id
                            )
                    )
            ),
            finding_current AS (
                SELECT id FROM inserted
                UNION ALL
                SELECT id FROM existing_exact
            ),
            linked AS (
                INSERT INTO finding_evidence (finding_id, evidence_id, relation)
                SELECT inserted.id, evidence_id_row.value, 'VERIFICATION_INPUT'
                FROM inserted
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    :'evidence_ids'::jsonb
                ) evidence_id_row(value)
                JOIN evidence source ON source.id = evidence_id_row.value
                ON CONFLICT DO NOTHING
                RETURNING finding_id
            ),
            assertion_inserted AS (
                INSERT INTO finding_assertion (
                    id, finding_id, assertion_text, assertion_text_sha256,
                    assertion_type, material, required_relation,
                    assertion_version, metadata
                )
                SELECT
                    :'assertion_id', current.id, :'rationale',
                    :'assertion_sha256', 'RATIONALE_MATERIAL', true,
                    'SUPPORT', 'finding-assertion-v1',
                    jsonb_build_object(
                        'verification_run_id', :'verification_run_id'
                    )
                FROM finding_current current
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            ),
            assertion_current AS (
                SELECT id FROM assertion_inserted
                UNION ALL
                SELECT assertion.id
                FROM finding_assertion assertion
                JOIN finding_current current
                  ON current.id = assertion.finding_id
                WHERE
                    assertion.id = :'assertion_id'
                    AND assertion.assertion_text = :'rationale'
                    AND assertion.assertion_text_sha256 =
                        :'assertion_sha256'
                    AND assertion.assertion_type =
                        'RATIONALE_MATERIAL'
                    AND assertion.material = true
                    AND assertion.required_relation = 'SUPPORT'
                    AND assertion.assertion_version =
                        'finding-assertion-v1'
            ),
            citation_inserted AS (
                INSERT INTO finding_assertion_citation (
                    id, assertion_id, evidence_id, observation_id,
                    passage_id, relation, citation_version, metadata
                )
                SELECT
                    assertion.id || '|citation|' ||
                        evidence_id_row.value || '|' || observation.id,
                    assertion.id,
                    evidence_id_row.value,
                    observation.id,
                    NULL,
                    'SUPPORT',
                    'finding-citation-v1',
                    jsonb_build_object(
                        'verification_run_id', :'verification_run_id'
                    )
                FROM assertion_current assertion
                CROSS JOIN eligible
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    :'evidence_ids'::jsonb
                ) evidence_id_row(value)
                JOIN evidence_observation observation
                  ON observation.evidence_id=evidence_id_row.value
                 AND eligible.observation_ids ? observation.id
                 AND observation.status='APPROVED'
                ON CONFLICT DO NOTHING
                RETURNING assertion_id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            finding_id=draft["finding_id"],
            claim_id=draft["claim_id"],
            assessment=draft["assessment"],
            rationale=rationale,
            assertion_id=assertion_id,
            assertion_sha256=assertion_sha256,
            publication_status=draft["publication_status"],
            policy_version=draft["policy_version"],
            model_bundle=json.dumps(
                draft.get("model_bundle") or {},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            verification_run_id=draft["verification_run_id"],
            supersedes_id=draft.get("supersedes_id") or "",
            evidence_ids=evidence_ids,
        )
        return raw.lower() in {"t", "true", "1"}

    def insert_relation_candidate(self, row: dict[str, Any]) -> bool:
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO claim_relation_candidate (
                    id, subject_claim_id, object_claim_id, relation_type,
                    relation_version, status, confidence, rationale_codes,
                    metadata
                ) VALUES (
                    :'id', :'subject_claim_id', :'object_claim_id',
                    :'relation_type', :'relation_version', :'status',
                    NULLIF(:'confidence','')::numeric,
                    :'rationale_codes'::jsonb, :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            id=row["id"],
            subject_claim_id=row["subject_claim_id"],
            object_claim_id=row["object_claim_id"],
            relation_type=row["relation_type"],
            relation_version=row["relation_version"],
            status=row.get("status") or "CANDIDATE",
            confidence="" if row.get("confidence") is None else row["confidence"],
            rationale_codes=json.dumps(
                row.get("rationale_codes") or [], separators=(",", ":")
            ),
            metadata=json.dumps(
                row.get("metadata") or {},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def insert_inference_candidate(self, row: dict[str, Any]) -> bool:
        from dichiarazioni_pubbliche.inference_repository import (
            INSERT_INFERENCE_CANDIDATE_SQL_V1,
            inference_candidate_to_sql_parameters,
        )

        params = inference_candidate_to_sql_parameters(row)
        raw = self.run(INSERT_INFERENCE_CANDIDATE_SQL_V1, **params)
        return raw.lower() in {"t", "true", "1"}

    def approve_relation_candidate_with_review(
        self,
        *,
        relation_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        """Record an explicit approval for a relation candidate.

        The relation status is only advanced to APPROVED when the append-only
        review ledger accepts the event. Public visibility is never granted
        here: it stays derived from this ledger at projection time.
        """
        raw = self.run(
            """
            WITH candidate AS (
                SELECT
                    relation.id,
                    relation.subject_claim_id,
                    relation.object_claim_id
                FROM claim_relation_candidate relation
                WHERE
                    relation.id = :'relation_id'
                    AND relation.status = 'CANDIDATE'
                    AND relation.subject_claim_id <> relation.object_claim_id
            ),
            recorded AS (
                INSERT INTO review_event (
                    id,
                    entity_type,
                    entity_id,
                    action,
                    actor_ref,
                    reason
                )
                SELECT
                    :'event_id', 'RELATION_CANDIDATE', candidate.id,
                    'APPROVED', :'actor_ref', NULLIF(:'reason','')
                FROM candidate
                ON CONFLICT (id) DO NOTHING
                RETURNING entity_id
            ),
            advanced AS (
                UPDATE claim_relation_candidate relation
                SET status = 'APPROVED'
                FROM recorded
                WHERE relation.id = recorded.entity_id
                RETURNING relation.id
            )
            SELECT json_build_object(
                'relation_id', relation.id,
                'subject_claim_id', relation.subject_claim_id,
                'object_claim_id', relation.object_claim_id
            )::text
            FROM claim_relation_candidate relation
            JOIN advanced ON advanced.id = relation.id;
            """,
            relation_id=relation_id,
            event_id=event_id,
            actor_ref=actor_ref,
            reason=reason or "",
        )
        return json.loads(raw) if raw else None

    def public_relation_candidates(
        self,
    ) -> list[dict[str, Any]]:
        """Return relations whose public eligibility the policy confirms.

        Public visibility stays derived from the review ledger plus both
        published endpoint findings. No stored PUBLISHED state exists.
        """
        raw = self.run(
            """
            SELECT COALESCE(json_agg(row_data ORDER BY subject_claim_id, object_claim_id)::text, '[]')
            FROM (
                SELECT json_build_object(
                    'id', relation.id,
                    'subject_claim_id', relation.subject_claim_id,
                    'object_claim_id', relation.object_claim_id,
                    'relation_type', relation.relation_type,
                    'relation_version', relation.relation_version,
                    'status', relation.status,
                    'rationale_codes', relation.rationale_codes,
                    'review_event_id', review.id,
                    'subject_claim', subject.normalized_claim,
                    'object_claim', object.normalized_claim,
                    'subject_statement_date',
                        subject.temporal_scope->>'statement_date',
                    'object_statement_date',
                        object.temporal_scope->>'statement_date'
                ) AS row_data
                FROM claim_relation_candidate relation
                JOIN atomic_claim subject
                    ON subject.id = relation.subject_claim_id
                JOIN atomic_claim object
                    ON object.id = relation.object_claim_id
                JOIN review_event review
                    ON review.entity_type = 'RELATION_CANDIDATE'
                    AND review.entity_id = relation.id
                    AND review.action = 'APPROVED'
                WHERE
                    relation.status = 'APPROVED'
                    AND EXISTS (
                        SELECT 1
                        FROM finding endpoint
                        WHERE endpoint.claim_id = relation.subject_claim_id
                          AND endpoint.publication_status = 'PUBLISH'
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM finding endpoint
                        WHERE endpoint.claim_id = relation.object_claim_id
                          AND endpoint.publication_status = 'PUBLISH'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM review_event superseded
                        WHERE superseded.entity_type = 'RELATION_CANDIDATE'
                          AND superseded.entity_id = relation.id
                          AND superseded.action IN ('REJECTED', 'SUPERSEDED')
                          AND superseded.created_at > review.created_at
                    )
            ) AS relations;
            """,
        )
        return json.loads(raw or "[]")

    def insert_reanalysis_trigger(self, row: dict[str, Any]) -> bool:
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO reanalysis_trigger (
                    id, claim_id, trigger_type, source_type, source_id,
                    source_hash, status, metadata
                ) VALUES (
                    :'id', :'claim_id', :'trigger_type', :'source_type',
                    :'source_id', NULLIF(:'source_hash',''), 'PENDING',
                    :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            id=row["id"],
            claim_id=row["claim_id"],
            trigger_type=row["trigger_type"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            source_hash=row.get("source_hash") or "",
            metadata=json.dumps(
                row.get("metadata") or {},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def advance_reanalysis_trigger(
        self,
        trigger_id: str,
        *,
        status: str,
        enqueued_job_id: str | None = None,
    ) -> bool:
        if status not in {"ENQUEUED", "PROCESSED"}:
            raise ValueError("invalid reanalysis trigger transition")
        raw = self.run(
            """
            WITH changed AS (
                UPDATE reanalysis_trigger
                SET
                    status = :'new_status',
                    enqueued_job_id = COALESCE(
                        NULLIF(:'enqueued_job_id',''),
                        enqueued_job_id
                    ),
                    processed_at = CASE
                        WHEN :'new_status' = 'PROCESSED' THEN now()
                        ELSE processed_at
                    END
                WHERE
                    id = :'trigger_id'
                    AND (
                        status = :'new_status'
                        OR (status = 'PENDING' AND :'new_status' = 'ENQUEUED')
                        OR (
                            status IN ('PENDING', 'ENQUEUED')
                            AND :'new_status' = 'PROCESSED'
                        )
                    )
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            trigger_id=trigger_id,
            new_status=status,
            enqueued_job_id=enqueued_job_id or "",
        )
        return raw.lower() in {"t", "true", "1"}

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
        if entity_type not in {
            "CLAIM_EVIDENCE_CANDIDATE",
            "EVIDENCE_OBSERVATION",
            "RELATION_CANDIDATE",
            "FINDING",
            "SPEAKER_IDENTITY_CANDIDATE",
            "RIGHT_OF_REPLY",
            "CORRECTION",
        }:
            raise ValueError("invalid review entity_type")
        if action not in {
            "APPROVED",
            "REJECTED",
            "QUARANTINED",
            "SUPERSEDED",
        }:
            raise ValueError("invalid review action")
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                ) VALUES (
                    :'event_id', :'entity_type', :'entity_id', :'action',
                    :'actor_ref', NULLIF(:'reason',''), :'metadata'::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            event_id=event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
            metadata=json.dumps(
                metadata or {},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return raw.lower() in {"t", "true", "1"}

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
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO right_of_reply (
                    id, finding_id, submitter_name, submitter_role, body,
                    evidence_urls, status, public_visibility
                ) VALUES (
                    :'reply_id', :'finding_id', NULLIF(:'submitter_name',''),
                    NULLIF(:'submitter_role',''), :'body',
                    :'evidence_urls'::jsonb, 'RECEIVED', 'PRIVATE'
                )
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM inserted)::text;
            """,
            reply_id=reply_id,
            finding_id=finding_id,
            submitter_name=submitter_name or "",
            submitter_role=submitter_role or "",
            body=body,
            evidence_urls=json.dumps(
                evidence_urls,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def attach_reply_reanalysis_job(
        self,
        *,
        reply_id: str,
        job_id: str,
    ) -> bool:
        raw = self.run(
            """
            WITH changed AS (
                UPDATE right_of_reply
                SET
                    reanalysis_job_id = :'job_id',
                    status = CASE
                        WHEN status = 'RECEIVED' THEN 'UNDER_REVIEW'
                        ELSE status
                    END
                WHERE id = :'reply_id'
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            reply_id=reply_id,
            job_id=job_id,
        )
        return raw.lower() in {"t", "true", "1"}

    def publish_right_of_reply_with_review(
        self,
        *,
        reply_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH eligible AS (
                SELECT reply.id, reply.finding_id
                FROM right_of_reply reply
                JOIN finding ON finding.id = reply.finding_id
                WHERE
                    reply.id = :'reply_id'
                    AND reply.status IN (
                        'UNDER_REVIEW', 'ACCEPTED', 'PUBLISHED'
                    )
                    AND reply.reanalysis_job_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM reanalysis_trigger trigger
                        WHERE
                            trigger.claim_id = finding.claim_id
                            AND trigger.trigger_type = 'RIGHT_OF_REPLY'
                            AND trigger.source_type = 'RIGHT_OF_REPLY'
                            AND trigger.source_id = reply.id
                            AND trigger.status = 'PROCESSED'
                    )
                    AND finding.publication_status IN (
                        'PUBLISH', 'DISPUTED', 'CORRECTED', 'RETRACTED'
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM review_event finding_review
                        WHERE
                            finding_review.entity_type = 'FINDING'
                            AND finding_review.entity_id = finding.id
                            AND finding_review.action = 'APPROVED'
                    )
                FOR UPDATE OF reply
            ),
            changed AS (
                UPDATE right_of_reply reply
                SET
                    status = 'PUBLISHED',
                    public_visibility = 'PUBLIC'
                FROM eligible
                WHERE reply.id = eligible.id
                RETURNING reply.id, reply.finding_id
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'RIGHT_OF_REPLY',
                    changed.id,
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    jsonb_build_object('finding_id', changed.finding_id)
                FROM changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed)::text;
            """,
            reply_id=reply_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def insert_correction(
        self,
        *,
        correction_id: str,
        finding_id: str,
        previous_finding_id: str,
        reason: str,
        changed_fields: dict[str, Any],
    ) -> bool:
        raw = self.run(
            """
            WITH eligible AS (
                SELECT current.id
                FROM finding current
                JOIN finding previous
                    ON previous.id = :'previous_finding_id'
                WHERE
                    current.id = :'finding_id'
                    AND current.supersedes_id = previous.id
                    AND current.claim_id = previous.claim_id
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding child
                        WHERE child.supersedes_id = current.id
                    )
            ),
            inserted AS (
                INSERT INTO correction (
                    id, finding_id, previous_finding_id, reason,
                    changed_fields, public_visibility
                )
                SELECT
                    :'correction_id', :'finding_id',
                    :'previous_finding_id', :'reason',
                    :'changed_fields'::jsonb, 'PRIVATE'
                FROM eligible
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT (
                EXISTS(SELECT 1 FROM inserted)
                OR EXISTS(
                    SELECT 1
                    FROM correction
                    WHERE
                        id = :'correction_id'
                        AND finding_id = :'finding_id'
                        AND previous_finding_id = :'previous_finding_id'
                        AND reason = :'reason'
                        AND changed_fields = :'changed_fields'::jsonb
                )
            )::text;
            """,
            correction_id=correction_id,
            finding_id=finding_id,
            previous_finding_id=previous_finding_id,
            reason=reason,
            changed_fields=json.dumps(
                changed_fields,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return raw.lower() in {"t", "true", "1"}

    def publish_correction_with_review(
        self,
        *,
        correction_id: str,
        event_id: str,
        actor_ref: str,
        reason: str | None = None,
    ) -> bool:
        raw = self.run(
            """
            WITH eligible AS (
                SELECT
                    correction.id,
                    correction.finding_id,
                    correction.previous_finding_id
                FROM correction
                JOIN finding current
                    ON current.id = correction.finding_id
                JOIN finding previous
                    ON previous.id = correction.previous_finding_id
                WHERE
                    correction.id = :'correction_id'
                    AND current.supersedes_id = previous.id
                    AND current.claim_id = previous.claim_id
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding child
                        WHERE child.supersedes_id = current.id
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM reanalysis_trigger trigger
                        WHERE
                            trigger.claim_id = current.claim_id
                            AND trigger.trigger_type = 'CORRECTION'
                            AND trigger.source_type = 'CORRECTION'
                            AND trigger.source_id = correction.id
                            AND trigger.status = 'PROCESSED'
                    )
                    AND current.publication_status IN (
                        'PUBLISH', 'DISPUTED', 'CORRECTED'
                    )
                    AND previous.publication_status IN (
                        'PUBLISH', 'DISPUTED', 'CORRECTED', 'RETRACTED'
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM review_event current_review
                        WHERE
                            current_review.entity_type = 'FINDING'
                            AND current_review.entity_id = current.id
                            AND current_review.action = 'APPROVED'
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM review_event previous_review
                        WHERE
                            previous_review.entity_type = 'FINDING'
                            AND previous_review.entity_id = previous.id
                            AND previous_review.action = 'APPROVED'
                    )
                FOR UPDATE OF correction, previous
            ),
            changed_correction AS (
                UPDATE correction target
                SET public_visibility = 'PUBLIC'
                FROM eligible
                WHERE target.id = eligible.id
                RETURNING
                    target.id,
                    target.finding_id,
                    target.previous_finding_id
            ),
            changed_previous AS (
                UPDATE finding previous
                SET publication_status = 'CORRECTED'
                FROM changed_correction changed
                WHERE previous.id = changed.previous_finding_id
                RETURNING previous.id
            ),
            logged AS (
                INSERT INTO review_event (
                    id, entity_type, entity_id, action, actor_ref, reason,
                    metadata
                )
                SELECT
                    :'event_id',
                    'CORRECTION',
                    changed.id,
                    'APPROVED',
                    :'actor_ref',
                    NULLIF(:'reason',''),
                    jsonb_build_object(
                        'finding_id', changed.finding_id,
                        'previous_finding_id', changed.previous_finding_id
                    )
                FROM changed_correction changed
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM changed_correction)::text;
            """,
            correction_id=correction_id,
            event_id=event_id,
            actor_ref=actor_ref or "local-operator",
            reason=reason or "",
        )
        return raw.lower() in {"t", "true", "1"}

    def upsert_canonical_segments(
        self,
        *,
        content_id: str,
        variant_id: str,
        rows: list[dict[str, Any]],
    ) -> None:
        payload = []
        for item in rows:
            segment_index = int(item["segment_index"])
            payload.append(
                {
                    "id": deterministic_canonical_segment_id(
                        content_id, segment_index
                    ),
                    "content_id": content_id,
                    "segment_index": segment_index,
                    "start_ms": int(item["start_ms"]),
                    "end_ms": int(item["end_ms"]),
                    "canonical_text": str(item["canonical_text"]),
                    "transcript_status": str(item["transcript_status"]),
                    "publication_blocked": bool(item["publication_blocked"]),
                    "sensitive_signature": item.get("sensitive_signature") or [],
                    "candidate_id": deterministic_segment_id(
                        variant_id, segment_index
                    ),
                }
            )
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        quoted = _dollar_quote(encoded)
        self.run_literal(
            f"""
            WITH input AS (
                SELECT *
                FROM jsonb_to_recordset({quoted}::jsonb) AS x(
                    id text,
                    content_id text,
                    segment_index integer,
                    start_ms bigint,
                    end_ms bigint,
                    canonical_text text,
                    transcript_status text,
                    publication_blocked boolean,
                    sensitive_signature jsonb,
                    candidate_id text
                )
            ),
            upserted AS (
                INSERT INTO canonical_transcript_segment (
                    id, content_id, segment_index, start_ms, end_ms,
                    canonical_text, transcript_status, publication_blocked,
                    sensitive_signature
                )
                SELECT
                    id, content_id, segment_index, start_ms, end_ms,
                    canonical_text, transcript_status, publication_blocked,
                    sensitive_signature
                FROM input
                ON CONFLICT (content_id, segment_index) DO UPDATE SET
                    start_ms = EXCLUDED.start_ms,
                    end_ms = EXCLUDED.end_ms,
                    canonical_text = EXCLUDED.canonical_text,
                    transcript_status = EXCLUDED.transcript_status,
                    publication_blocked = EXCLUDED.publication_blocked,
                    sensitive_signature = EXCLUDED.sensitive_signature,
                    updated_at = now()
                RETURNING id, segment_index
            )
            INSERT INTO canonical_segment_candidate (
                canonical_segment_id, transcript_segment_id
            )
            SELECT u.id, i.candidate_id
            FROM upserted u
            JOIN input i USING (segment_index)
            ON CONFLICT DO NOTHING;
            """
        )

    def state_counts(self) -> dict[str, int]:
        raw = self.run(
            """
            SELECT COALESCE(json_object_agg(state, count)::text, '{}')
            FROM (
                SELECT state, count(*)::integer AS count
                FROM processing_job
                GROUP BY state
            ) q;
            """
        )
        return {str(k): int(v) for k, v in json.loads(raw or "{}").items()}
