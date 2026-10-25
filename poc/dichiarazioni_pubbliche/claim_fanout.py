"""Bounded, provenance-preserving claim-window admission (DP-203)."""

from __future__ import annotations

import hashlib
from typing import Any

from dichiarazioni_pubbliche.claim_runtime import estimate_claim_request_cost
from dichiarazioni_pubbliche.claim_windows import (
    build_claim_windows,
    canonical_segment_from_row,
)
from dichiarazioni_pubbliche.queue_runtime import deterministic_followup_job_id
from dichiarazioni_pubbliche.worker_errors import BlockedJob, RetryableJob


def prepare_claim_batch(worker: Any, job: Any, content: Any) -> None:
    """Queue at most one small batch after the runtime admission gate is open.

    A subsequent CLAIM_PREPARE is emitted only after every window in the
    preceding batch is completed. No raw text is stored in job payloads.
    """
    variant_id = str(job.payload.get("variant_id") or "").strip()
    if not variant_id:
        raise BlockedJob("CLAIM_PREPARE_VARIANT_ID_MISSING")
    blocker = worker._claim_runtime_blocker()
    if blocker:
        worker.store.update_content_status(
            content.content_id,
            "CLAIM_EXTRACTION_BLOCKED",
            {"runtime_blocker": blocker, "claim_variant_id": variant_id,
             "claim_window_materialized": False},
        )
        raise BlockedJob(blocker)

    rows = worker.store.canonical_segments(content.content_id)
    if not rows:
        raise RetryableJob("CLAIM_PREPARE_CANONICAL_SEGMENTS_MISSING", 60)
    windows = build_claim_windows([canonical_segment_from_row(row) for row in rows])
    if not windows:
        raise BlockedJob("CLAIM_PREPARE_NO_WINDOWS")
    ordered = sorted(
        windows,
        key=lambda window: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(window.priority, 3),
            window.window_index,
        ),
    )
    manifest = hashlib.sha256(
        "\0".join((
            variant_id,
            worker.claim_client.model,
            worker.claim_client.prompt_version,
            str(worker.claim_window_batch_size),
            *(window.input_sha256 for window in ordered),
        )).encode()
    ).hexdigest()
    expected_manifest = job.payload.get("claim_batch_manifest_sha256")
    if expected_manifest is not None and expected_manifest != manifest:
        raise BlockedJob("CLAIM_BATCH_MANIFEST_DRIFT")

    size = worker.claim_window_batch_size
    offset = job.payload.get("claim_window_offset", 0)
    if (isinstance(offset, bool) or not isinstance(offset, int)
            or offset < 0 or offset >= len(ordered) or offset % size != 0):
        raise BlockedJob("CLAIM_BATCH_OFFSET_INVALID")
    batch = ordered[offset:offset + size]
    next_offset = offset + len(batch)
    has_more = next_offset < len(ordered)
    jobs = []
    for window in batch:
        payload = window.queue_payload(
            source_id=content.source_id,
            variant_id=variant_id,
            model=worker.claim_client.model,
            prompt_version=worker.claim_client.prompt_version,
        )
        estimated_cost = estimate_claim_request_cost(
            estimated_input_tokens=window.estimated_input_tokens,
            max_output_tokens=worker.claim_client.max_output_tokens,
            max_usd_per_1k_total_tokens=worker.claim_max_usd_per_1k_total_tokens,
        )
        if estimated_cost is None:
            raise BlockedJob("CLAIM_EXTRACTION_COST_MODEL_MISSING")
        payload.update({
            "estimated_cost_usd": estimated_cost,
            "max_output_tokens": worker.claim_client.max_output_tokens,
            "claim_batch_manifest_sha256": manifest,
            "claim_batch_next_offset": next_offset if has_more else None,
        })
        jobs.append({
            "id": deterministic_followup_job_id(
                "CLAIM_EXTRACT_WINDOW", content.content_id, window.input_sha256
            ),
            "content_id": content.content_id,
            "job_type": "CLAIM_EXTRACT_WINDOW",
            "state": "QUEUED",
            "payload": payload,
            "last_error": "",
        })
    created = worker.store.enqueue_jobs_bulk(jobs)
    worker.store.update_content_status(
        content.content_id,
        "CLAIM_EXTRACTION_QUEUED",
        {
            "claim_window_count": len(ordered),
            "claim_window_new_jobs": created,
            "claim_window_blocked_jobs": 0,
            "claim_window_batch_offset": offset,
            "claim_window_batch_size": len(batch),
            "claim_window_remaining_unqueued": len(ordered) - next_offset,
            "claim_window_estimated_input_tokens": sum(
                window.estimated_input_tokens for window in batch
            ),
            "claim_window_schema_version": "claim-window-v2",
            "claim_prompt_version": worker.claim_client.prompt_version,
        },
    )


def enqueue_next_claim_batch(worker: Any, job: Any) -> bool:
    """After the last completed sibling, enqueue exactly one next parent."""
    next_offset = job.payload.get("claim_batch_next_offset")
    if next_offset is None:
        return False
    variant = str(job.payload.get("variant_id") or "").strip()
    manifest = str(job.payload.get("claim_batch_manifest_sha256") or "").strip()
    if (not variant or len(manifest) != 64 or isinstance(next_offset, bool)
            or not isinstance(next_offset, int) or next_offset <= 0):
        # The last child was already completed by the queue runner. Preserve
        # a visible HOLD instead of crashing that runner after completion.
        worker.store.update_content_status(
            job.content_id, "CLAIM_EXTRACTION_BLOCKED",
            {"runtime_blocker": "CLAIM_BATCH_CONTINUATION_INVALID"},
        )
        return True
    worker.store.enqueue_followup(
        content_id=job.content_id,
        job_type="CLAIM_PREPARE",
        payload={
            "variant_id": variant,
            "estimated_cost_usd": 0.0,
            "claim_window_offset": next_offset,
            "claim_batch_manifest_sha256": manifest,
        },
        variant=f"{variant}:claim-batch:{next_offset}",
    )
    worker.store.update_content_status(
        job.content_id, "CLAIM_EXTRACTION_QUEUED",
        {"claim_window_next_batch_offset": next_offset},
    )
    return True
