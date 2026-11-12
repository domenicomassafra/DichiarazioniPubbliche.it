"""Read-only daily-machine health classification.

This checks the last 24 hours of the DP-638 daily machine, not the lifetime of
the database: a blocked job from September is history, not a current failure.
It grants no rights, model access, review or publication authority, and only
aggregate counters leave the runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any


COUNTER_NAMES = (
    "daily_runs_completed", "daily_runs_failed", "daily_items_discovered",
    "captures", "statements", "verdicts", "published", "jobs_blocked",
    "provider_receipts",
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

    reasons: list[str] = []
    if counters["daily_runs_completed"] == 0:
        reasons.append("NO_COMPLETED_DAILY_RUN")
    if counters["daily_runs_failed"]:
        reasons.append("FAILED_DAILY_RUN_PRESENT")
    if counters["daily_items_discovered"] == 0:
        reasons.append("NO_DISCOVERED_ITEMS")
    if counters["daily_items_discovered"] and counters["captures"] == 0:
        reasons.append("ITEMS_NOT_CAPTURED")
    if counters["captures"] and counters["statements"] == 0:
        reasons.append("CAPTURES_WITHOUT_STATEMENTS")
    if counters["statements"] and counters["verdicts"] == 0:
        reasons.append("STATEMENTS_WITHOUT_VERDICTS")
    if counters["statements"] and counters["published"] == 0:
        reasons.append("NOTHING_PUBLISHED")
    if counters["jobs_blocked"] > 0:
        reasons.append("BLOCKED_JOBS_PRESENT")
    state = "HEALTHY" if not reasons else "NEEDS_OPERATOR_ACTION"
    return DailyPipelineHealth(state, tuple(reasons), counters, last)


# Every counter is windowed to the last 24 hours on purpose: the machine is
# judged on what it did today, never on rows that keep a counter red forever.
DAILY_PIPELINE_COUNTS_SQL = """
BEGIN TRANSACTION READ ONLY;
WITH window_since AS (
  SELECT now() - interval '24 hours' AS since
), snapshots AS (
  SELECT
    (SELECT count(*) FROM daily_run
      WHERE finished_at >= now() - interval '24 hours')::integer AS daily_runs_completed,
    (SELECT count(*) FROM source_poll_run
      WHERE status = 'FAILED' AND run_date >= current_date - 1)::integer AS daily_runs_failed,
    (SELECT coalesce(sum(items), 0) FROM daily_run
      WHERE run_date >= current_date - 1)::integer AS daily_items_discovered,
    (SELECT count(*) FROM daily_capture, window_since
      WHERE daily_capture.fetched_at >= window_since.since)::integer AS captures,
    (SELECT count(*) FROM daily_statement, window_since
      WHERE daily_statement.created_at >= window_since.since)::integer AS statements,
    (SELECT count(*) FROM daily_verdict, window_since
      WHERE daily_verdict.created_at >= window_since.since)::integer AS verdicts,
    (SELECT count(*) FROM daily_statement, window_since
      WHERE daily_statement.metadata->'publication'->>'public_url' IS NOT NULL
        AND daily_statement.created_at >= window_since.since)::integer AS published,
    (SELECT count(*) FROM processing_job, window_since
      WHERE processing_job.state IN ('BLOCKED', 'FAILED')
        AND processing_job.created_at >= window_since.since)::integer AS jobs_blocked,
    (SELECT count(*) FROM provider_receipt, window_since
      WHERE provider_receipt.started_at >= window_since.since)::integer AS provider_receipts,
    (SELECT max(run_date)::text FROM daily_run) AS latest_daily_run_date
)
SELECT row_to_json(snapshots)::text FROM snapshots;
COMMIT;
"""


__all__ = [
    "COUNTER_NAMES", "DAILY_PIPELINE_COUNTS_SQL",
    "DailyPipelineHealth", "classify_daily_pipeline",
]
