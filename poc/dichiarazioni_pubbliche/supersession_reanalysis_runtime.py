from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Protocol

from dichiarazioni_pubbliche.source_revalidation import (
    RevalidationDecision,
    SourceSnapshot,
)
from dichiarazioni_pubbliche.supersession_reanalysis import (
    ReviewedSupersessionReanalysisRequest,
    build_reviewed_supersession_reanalysis_request,
)


class SqlRunner(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


@dataclass(frozen=True)
class PersistedSupersessionReanalysisReceipt:
    request_id: str
    review_event_id: str
    reviewed_entity_ref: str
    decision_event_key: str
    affected_claim_ids: tuple[str, ...]
    affected_finding_ids: tuple[str, ...]
    trigger_ids: tuple[str, ...]
    reanalysis_job_ids: tuple[str, ...]
    persisted_trigger_count: int
    persisted_job_count: int


def _binding_payload(binding: object) -> dict[str, object]:
    return {
        "source_id": getattr(binding, "source_id"),
        "version_id": getattr(binding, "version_id"),
        "content_sha256": getattr(binding, "content_sha256"),
        "valid_from": getattr(binding, "valid_from"),
        "valid_until": getattr(binding, "valid_until"),
    }


def _audit_payload(request: ReviewedSupersessionReanalysisRequest) -> dict[str, object]:
    return {
        "version": request.version,
        "request_id": request.request_id,
        "review_event_id": request.review_event_id,
        "review_action": "APPROVED",
        "reviewed_entity_ref": request.reviewed_entity_ref,
        "decision_event_key": request.decision_event_key,
        "previous_snapshot_ref": request.previous_snapshot_ref,
        "current_snapshot_ref": request.current_snapshot_ref,
        "previous": _binding_payload(request.previous),
        "current": _binding_payload(request.current),
        "affected_claim_ids": list(request.affected_claim_ids),
        "affected_finding_ids": list(request.affected_finding_ids),
    }


_PERSIST_REVIEWED_SUPERSESSION_SQL = r"""
BEGIN;

WITH input AS (
    SELECT *
    FROM jsonb_to_recordset(:'claim_jobs'::jsonb) AS row(
        claim_id text,
        trigger_id text,
        job_id text,
        trigger_type text,
        source_type text,
        source_id text,
        source_hash text
    )
)
INSERT INTO reanalysis_trigger (
    id,
    claim_id,
    trigger_type,
    source_type,
    source_id,
    source_hash,
    status,
    metadata
)
SELECT
    row.trigger_id,
    row.claim_id,
    row.trigger_type,
    row.source_type,
    row.source_id,
    row.source_hash,
    'PENDING',
    :'audit_payload'::jsonb || jsonb_build_object(
        'reanalysis_job_id', row.job_id
    )
FROM input row
JOIN atomic_claim claim ON claim.id = row.claim_id
ON CONFLICT (id) DO NOTHING;

WITH input AS (
    SELECT *
    FROM jsonb_to_recordset(:'claim_jobs'::jsonb) AS row(
        claim_id text,
        trigger_id text,
        job_id text,
        trigger_type text,
        source_type text,
        source_id text,
        source_hash text
    )
)
INSERT INTO processing_job (
    id,
    content_id,
    job_type,
    state,
    payload
)
SELECT
    row.job_id,
    claim.content_id,
    'REANALYZE_CLAIM',
    'QUEUED',
    jsonb_build_object(
        'claim_id', row.claim_id,
        'trigger_id', row.trigger_id,
        'request_id', :'request_id',
        'review_event_id', :'review_event_id',
        'reviewed_entity_ref', :'reviewed_entity_ref',
        'decision_event_key', :'decision_event_key',
        'affected_finding_ids', :'affected_finding_ids'::jsonb,
        'supersession_reanalysis', :'audit_payload'::jsonb,
        'estimated_cost_usd', 0.0
    )
FROM input row
JOIN atomic_claim claim ON claim.id = row.claim_id
ON CONFLICT (id) DO NOTHING;

WITH input AS (
    SELECT *
    FROM jsonb_to_recordset(:'claim_jobs'::jsonb) AS row(
        claim_id text,
        trigger_id text,
        job_id text,
        trigger_type text,
        source_type text,
        source_id text,
        source_hash text
    )
)
UPDATE reanalysis_trigger trigger
SET
    status = CASE
        WHEN trigger.status = 'PENDING' THEN 'ENQUEUED'
        ELSE trigger.status
    END,
    enqueued_job_id = COALESCE(trigger.enqueued_job_id, row.job_id)
FROM input row
WHERE
    trigger.id = row.trigger_id
    AND trigger.status IN ('PENDING', 'ENQUEUED', 'PROCESSED')
    AND (
        trigger.enqueued_job_id IS NULL
        OR trigger.enqueued_job_id = row.job_id
    );

WITH input AS (
    SELECT *
    FROM jsonb_to_recordset(:'claim_jobs'::jsonb) AS row(
        claim_id text,
        trigger_id text,
        job_id text,
        trigger_type text,
        source_type text,
        source_id text,
        source_hash text
    )
),
checks AS (
    SELECT
        (SELECT count(*) FROM input) = :'expected_claim_count'::integer
            AS input_count_ok,
        NOT EXISTS (
            SELECT 1
            FROM input row
            LEFT JOIN atomic_claim claim ON claim.id = row.claim_id
            WHERE claim.id IS NULL
        ) AS claims_exist,
        NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements_text(:'affected_finding_ids'::jsonb) finding_id
            LEFT JOIN finding finding ON finding.id = finding_id.value
            WHERE
                finding.id IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM input row
                    WHERE row.claim_id = finding.claim_id
                )
        ) AS findings_bound,
        NOT EXISTS (
            SELECT 1
            FROM input row
            LEFT JOIN reanalysis_trigger trigger ON trigger.id = row.trigger_id
            WHERE
                trigger.id IS NULL
                OR trigger.claim_id IS DISTINCT FROM row.claim_id
                OR trigger.trigger_type IS DISTINCT FROM row.trigger_type
                OR trigger.source_type IS DISTINCT FROM row.source_type
                OR trigger.source_id IS DISTINCT FROM row.source_id
                OR trigger.source_hash IS DISTINCT FROM row.source_hash
                OR trigger.status NOT IN ('ENQUEUED', 'PROCESSED')
                OR trigger.enqueued_job_id IS DISTINCT FROM row.job_id
                OR NOT (
                    trigger.metadata @> (
                        :'audit_payload'::jsonb || jsonb_build_object(
                            'reanalysis_job_id', row.job_id
                        )
                    )
                )
        ) AS triggers_exact,
        NOT EXISTS (
            SELECT 1
            FROM input row
            JOIN atomic_claim claim ON claim.id = row.claim_id
            LEFT JOIN processing_job job ON job.id = row.job_id
            WHERE
                job.id IS NULL
                OR job.content_id IS DISTINCT FROM claim.content_id
                OR job.job_type IS DISTINCT FROM 'REANALYZE_CLAIM'
                OR NOT (
                    job.payload @> jsonb_build_object(
                        'claim_id', row.claim_id,
                        'trigger_id', row.trigger_id,
                        'request_id', :'request_id',
                        'review_event_id', :'review_event_id',
                        'reviewed_entity_ref', :'reviewed_entity_ref',
                        'decision_event_key', :'decision_event_key',
                        'affected_finding_ids', :'affected_finding_ids'::jsonb,
                        'supersession_reanalysis', :'audit_payload'::jsonb,
                        'estimated_cost_usd', 0.0
                    )
                )
        ) AS jobs_exact
)
SELECT CASE
    WHEN
        input_count_ok
        AND claims_exist
        AND findings_bound
        AND triggers_exact
        AND jobs_exact
    THEN json_build_object(
        'request_id', :'request_id',
        'review_event_id', :'review_event_id',
        'reviewed_entity_ref', :'reviewed_entity_ref',
        'decision_event_key', :'decision_event_key',
        'affected_claim_ids', :'affected_claim_ids'::jsonb,
        'affected_finding_ids', :'affected_finding_ids'::jsonb,
        'trigger_ids', :'trigger_ids'::jsonb,
        'reanalysis_job_ids', :'reanalysis_job_ids'::jsonb,
        'persisted_trigger_count', :'expected_claim_count'::integer,
        'persisted_job_count', :'expected_claim_count'::integer
    )::text
    ELSE (
        'DP227_SUPERSESSION_REANALYSIS_RUNTIME_CONFLICT:'
        || :'request_id'
        || ':input=' || input_count_ok::text
        || ':claims=' || claims_exist::text
        || ':findings=' || findings_bound::text
        || ':triggers=' || triggers_exact::text
        || ':jobs=' || jobs_exact::text
    )::integer::text
END
FROM checks;

COMMIT;
"""


def _persist_request(
    store: SqlRunner,
    request: ReviewedSupersessionReanalysisRequest,
) -> PersistedSupersessionReanalysisReceipt:
    if request.reviewed_entity_ref != request.decision_event_key:
        raise ValueError("SUPERSESSION_REANALYSIS_RUNTIME_REVIEW_EVENT_KEY_MISMATCH")
    if len(request.triggers) != len(request.affected_claim_ids):
        raise ValueError("SUPERSESSION_REANALYSIS_RUNTIME_TRIGGER_COUNT_MISMATCH")
    if len(request.reanalysis_job_ids) != len(request.affected_claim_ids):
        raise ValueError("SUPERSESSION_REANALYSIS_RUNTIME_JOB_COUNT_MISMATCH")

    claim_jobs = []
    for claim_id, trigger, job_id in zip(
        request.affected_claim_ids,
        request.triggers,
        request.reanalysis_job_ids,
        strict=True,
    ):
        if trigger.claim_id != claim_id:
            raise ValueError("SUPERSESSION_REANALYSIS_RUNTIME_TRIGGER_CLAIM_MISMATCH")
        claim_jobs.append(
            {
                "claim_id": claim_id,
                "trigger_id": trigger.trigger_id,
                "job_id": job_id,
                "trigger_type": trigger.trigger_type,
                "source_type": trigger.source_type,
                "source_id": trigger.source_id,
                "source_hash": trigger.source_hash,
            }
        )

    audit_payload = _audit_payload(request)
    raw = store.run(
        _PERSIST_REVIEWED_SUPERSESSION_SQL,
        claim_jobs=json.dumps(claim_jobs, ensure_ascii=False, separators=(",", ":")),
        audit_payload=json.dumps(
            audit_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        request_id=request.request_id,
        review_event_id=request.review_event_id,
        reviewed_entity_ref=request.reviewed_entity_ref,
        decision_event_key=request.decision_event_key,
        affected_claim_ids=json.dumps(list(request.affected_claim_ids)),
        affected_finding_ids=json.dumps(list(request.affected_finding_ids)),
        trigger_ids=json.dumps([trigger.trigger_id for trigger in request.triggers]),
        reanalysis_job_ids=json.dumps(list(request.reanalysis_job_ids)),
        expected_claim_count=len(request.affected_claim_ids),
    )
    payload = json.loads(raw)
    return PersistedSupersessionReanalysisReceipt(
        request_id=str(payload["request_id"]),
        review_event_id=str(payload["review_event_id"]),
        reviewed_entity_ref=str(payload["reviewed_entity_ref"]),
        decision_event_key=str(payload["decision_event_key"]),
        affected_claim_ids=tuple(str(value) for value in payload["affected_claim_ids"]),
        affected_finding_ids=tuple(str(value) for value in payload["affected_finding_ids"]),
        trigger_ids=tuple(str(value) for value in payload["trigger_ids"]),
        reanalysis_job_ids=tuple(
            str(value) for value in payload["reanalysis_job_ids"]
        ),
        persisted_trigger_count=int(payload["persisted_trigger_count"]),
        persisted_job_count=int(payload["persisted_job_count"]),
    )


def consume_reviewed_supersession_reanalysis(
    store: SqlRunner,
    *,
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
    review_event_id: str,
    review_action: str,
    reviewed_entity_ref: str,
    previous_valid_from: str,
    previous_valid_until: str | None,
    current_valid_from: str,
    current_valid_until: str | None,
    affected_claim_ids: Iterable[str],
    affected_finding_ids: Iterable[str] = (),
) -> PersistedSupersessionReanalysisReceipt:
    """Consume one reviewed source supersession into persisted reanalysis work.

    The canonical DP-227 request builder remains the only authority for review/event,
    snapshot, supersession and effective-time validation. This runtime consumer only
    persists the already-authorized reanalysis request as one trigger and one
    `REANALYZE_CLAIM` job per affected claim. It does not update Findings or any
    publication state.
    """

    request = build_reviewed_supersession_reanalysis_request(
        decision=decision,
        previous=previous,
        current=current,
        review_event_id=review_event_id,
        review_action=review_action,
        reviewed_entity_ref=reviewed_entity_ref,
        previous_valid_from=previous_valid_from,
        previous_valid_until=previous_valid_until,
        current_valid_from=current_valid_from,
        current_valid_until=current_valid_until,
        affected_claim_ids=affected_claim_ids,
        affected_finding_ids=affected_finding_ids,
    )
    return _persist_request(store, request)


__all__ = [
    "PersistedSupersessionReanalysisReceipt",
    "SqlRunner",
    "consume_reviewed_supersession_reanalysis",
]
