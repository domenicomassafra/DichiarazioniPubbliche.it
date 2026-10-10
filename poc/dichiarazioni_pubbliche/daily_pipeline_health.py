"""Read-only, private daily-ingestion health classification.

This checks *actual stage data*, not whether a systemd timer succeeded.
It grants no source rights, model access, review or publication authority.
Only aggregate counters may leave the runtime authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any


COUNTER_NAMES = (
    "daily_runs_completed", "daily_runs_failed", "daily_items_discovered",
    "discovery_hits", "captures", "passages", "statement_candidates",
    "claim_candidates", "jobs_queued", "jobs_blocked", "provider_receipts",
)


@dataclass(frozen=True)
class DailyPipelineHealth:
    state: str
    reasons: tuple[str, ...]
    counters: dict[str, int]
    latest_daily_run_date: str | None
    private_only: bool = True
    publication_authority: bool = False
    paid_calls_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reasons": list(self.reasons),
            "counters": self.counters,
            "latest_daily_run_date": self.latest_daily_run_date,
            "private_only": self.private_only,
            "publication_authority": self.publication_authority,
            "paid_calls_authorized": self.paid_calls_authorized,
        }


def classify_daily_pipeline(
    snapshot: Mapping[str, object], *, today: date,
) -> DailyPipelineHealth:
    if not isinstance(snapshot, Mapping) or set(snapshot) != set(COUNTER_NAMES) | {
        "latest_daily_run_date"
    }:
        raise ValueError("DAILY_PIPELINE_COUNTER_SCHEMA_DRIFT")
    counters: dict[str, int] = {}
    for name in COUNTER_NAMES:
        value = snapshot[name]
        if type(value) is not int or value < 0:
            raise ValueError("DAILY_PIPELINE_COUNTER_INVALID:" + name)
        counters[name] = value
    last = snapshot["latest_daily_run_date"]
    if last is not None:
        if not isinstance(last, str):
            raise ValueError("DAILY_PIPELINE_DATE_INVALID")
        try:
            parsed = date.fromisoformat(last)
        except ValueError as exc:
            raise ValueError("DAILY_PIPELINE_DATE_INVALID") from exc
        if parsed.isoformat() != last or parsed > today:
            raise ValueError("DAILY_PIPELINE_DATE_INVALID")
    else:
        parsed = None

    reasons: list[str] = []
    if counters["daily_runs_completed"] == 0:
        reasons.append("NO_COMPLETED_DAILY_RUN")
    elif parsed != today:
        reasons.append("DAILY_RUN_NOT_CURRENT")
    if counters["daily_runs_failed"]:
        reasons.append("FAILED_DAILY_RUN_PRESENT")
    if counters["daily_items_discovered"] == 0 and counters["discovery_hits"] == 0:
        reasons.append("NO_ACTUAL_DISCOVERY_RESULTS")
    if counters["daily_items_discovered"] and counters["captures"] == 0:
        reasons.append("POLLED_METADATA_NOT_CAPTURED")
    if counters["discovery_hits"] and counters["captures"] == 0:
        reasons.append("DISCOVERY_NOT_CAPTURED")
    if counters["captures"] == 0:
        reasons.append("NO_PRIVATE_CAPTURES")
    if counters["captures"] and counters["passages"] == 0:
        reasons.append("CAPTURE_NOT_PARSED")
    if counters["passages"] and counters["statement_candidates"] == 0:
        reasons.append("PASSAGES_NOT_PROMOTED_TO_PRIVATE_CANDIDATES")
    if counters["jobs_blocked"] > 0:
        reasons.append("BLOCKED_JOBS_PRESENT")
    if counters["jobs_queued"] > 0:
        reasons.append("UNPROCESSED_QUEUE_PRESENT")
    if counters["statement_candidates"] > 0:
        reasons.append("PRIVATE_REVIEW_STILL_REQUIRED")
    # Even when all technical stages are populated there is no authority to
    # infer an independently reviewed, licensed public projection.
    state = "NEEDS_OPERATOR_ACTION" if reasons else "TECHNICAL_STAGES_PRESENT_REVIEW_REQUIRED"
    return DailyPipelineHealth(state, tuple(reasons), counters, last)


DAILY_PIPELINE_COUNTS_SQL = """
BEGIN TRANSACTION READ ONLY;
WITH recent_daily AS (
  SELECT run_date, discovered, status
  FROM source_poll_run
  WHERE mode = 'full-source' AND diagnostic = false
), snapshots AS (
  SELECT
    (SELECT count(*) FROM recent_daily WHERE status='COMPLETED')::integer AS daily_runs_completed,
    (SELECT count(*) FROM recent_daily WHERE status='FAILED')::integer AS daily_runs_failed,
    (SELECT coalesce(sum(discovered), 0) FROM recent_daily WHERE status='COMPLETED')::integer AS daily_items_discovered,
    (SELECT count(*) FROM research_discovery_hit)::integer AS discovery_hits,
    (SELECT count(*) FROM content_capture)::integer AS captures,
    (SELECT count(*) FROM passage)::integer AS passages,
    (SELECT count(*) FROM statement_candidate)::integer AS statement_candidates,
    (SELECT count(*) FROM claim_candidate)::integer AS claim_candidates,
    (SELECT count(*) FROM processing_job WHERE state IN ('QUEUED', 'PENDING', 'RETRY'))::integer AS jobs_queued,
    (SELECT count(*) FROM processing_job WHERE state IN ('BLOCKED', 'FAILED'))::integer AS jobs_blocked,
    (SELECT count(*) FROM provider_receipt)::integer AS provider_receipts,
    (SELECT max(run_date)::text FROM recent_daily WHERE status='COMPLETED') AS latest_daily_run_date
)
SELECT row_to_json(snapshots)::text FROM snapshots;
COMMIT;
"""


__all__ = [
    "COUNTER_NAMES", "DAILY_PIPELINE_COUNTS_SQL",
    "DailyPipelineHealth", "classify_daily_pipeline",
]
