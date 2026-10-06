from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.ops.slo import evaluate as evaluate_slos
from dichiarazioni_pubbliche.ops.slo import pageable as pageable_slos
from dichiarazioni_pubbliche.ops.slo import worst_status as worst_slo_status
from dichiarazioni_pubbliche.ops.taxonomy import actionable as actionable_blockers


DEFAULT_OUTPUT = Path.home() / ".local" / "state" / "dichiarazioni-pubbliche" / "health.json"
DEFAULT_PRIVATE_ROOT = Path.home() / ".local" / "share" / "dichiarazioni-pubbliche"
_ERROR_CATEGORY = re.compile(r"^([A-Z][A-Z0-9_]+)")


def error_category(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "NONE"
    match = _ERROR_CATEGORY.match(text)
    return match.group(1) if match else "OTHER"


def private_tree_stats(root: Path) -> dict[str, int]:
    if not root.exists():
        return {"files": 0, "bytes": 0}
    files = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            files += 1
            total += path.stat().st_size
    return {"files": files, "bytes": total}


def _query_json(db: PsqlRuntime, sql: str) -> Any:
    raw = db.run(sql)
    return json.loads(raw or "[]")


def queue_depth(queue: list[dict[str, Any]], state: str) -> int:
    """Total jobs in one state, summed across every job type."""
    return sum(int(row.get("count") or 0) for row in queue if row.get("state") == state)


def build_slo_measurements(
    *,
    queue: list[dict[str, Any]],
    queue_age: dict[str, Any],
    estimated_cost_usd_today: float,
    max_cost_usd_per_day: float,
    max_cost_usd_per_source_day: float,
    provider_receipts_today: list[dict[str, Any]],
    projection_generated_at: str | None,
    now: datetime,
) -> dict[str, Any]:
    """Derive the flat measurement mapping that the pure SLO module consumes.

    Every measurement has exactly one computation site, here, so the SLO
    definitions in ``ops/slo`` stay free of I/O and of the digest's query
    A missing measurement is passed through as ``None`` and surfaces as
    UNKNOWN, never as OK.
    """
    queued = queue_depth(queue, "QUEUED")
    oldest_queued: float | None = None
    if isinstance(queue_age, dict) and "oldest_queued_seconds" in queue_age:
        try:
            oldest_queued = float(queue_age["oldest_queued_seconds"])
        except (TypeError, ValueError):
            oldest_queued = None

    # Drain ratio: 1.0 when nothing is queued, decaying linearly to 0 when the
    # oldest queued job has waited a full worker interval. An empty queue is
    # fully drained, not "no data".
    drain_window = 120.0
    if queued <= 0:
        drain_ratio: float | None = 1.0
    elif oldest_queued is None:
        drain_ratio = None
    else:
        drain_ratio = max(0.0, 1.0 - (oldest_queued / drain_window))

    projection_age: float | None = None
    if projection_generated_at:
        try:
            built = datetime.fromisoformat(projection_generated_at)
            if built.tzinfo is None:
                built = built.replace(tzinfo=timezone.utc)
            projection_age = (now - built).total_seconds()
        except (TypeError, ValueError):
            projection_age = None

    global_cap = max(float(max_cost_usd_per_day), 0.0)
    source_cap = max(float(max_cost_usd_per_source_day), 0.0)
    per_source = max(
        (float(row.get("cost_usd") or 0) for row in provider_receipts_today),
        default=0.0,
    )
    return {
        "queue_oldest_queued_seconds": (
            oldest_queued if queued > 0 else 0.0
        ),
        "queue_drain_ratio": drain_ratio,
        "estimated_cost_usd_today": (
            float(estimated_cost_usd_today) / global_cap if global_cap > 0 else None
        ),
        "provider_receipts_today": (
            per_source / source_cap if source_cap > 0 else None
        ),
        "projection_health": 1.0,
        "projection_generated_at_age_seconds": projection_age,
    }


def build_health_digest(
    db: PsqlRuntime,
    *,
    private_root: Path = DEFAULT_PRIVATE_ROOT,
    now: datetime | None = None,
    max_cost_usd_per_day: float = 5.0,
    max_cost_usd_per_source_day: float = 1.0,
    projection_generated_at: str | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    queue = _query_json(
        db,
        """
        SELECT COALESCE(json_agg(row_to_json(x) ORDER BY job_type, state)::text, '[]')
        FROM (
            SELECT job_type, state, count(*)::integer AS count
            FROM processing_job
            GROUP BY job_type, state
        ) x;
        """,
    )
    queue_age = _query_json(
        db,
        """
        SELECT json_build_object(
            'queued', (SELECT count(*) FROM processing_job WHERE state = 'QUEUED'),
            'oldest_queued_seconds', (
                SELECT COALESCE(
                    EXTRACT(EPOCH FROM (now() - min(created_at)))::bigint, 0
                )
                FROM processing_job
                WHERE state = 'QUEUED'
            )
        )::text;
        """,
    )
    errors = _query_json(
        db,
        """
        SELECT COALESCE(json_agg(row_to_json(x) ORDER BY count DESC, last_error)::text, '[]')
        FROM (
            SELECT COALESCE(last_error, '') AS last_error, count(*)::integer AS count
            FROM processing_job
            WHERE state IN ('BLOCKED', 'DEAD_LETTER')
            GROUP BY COALESCE(last_error, '')
        ) x;
        """,
    )
    source_health = _query_json(
        db,
        """
        SELECT COALESCE(json_agg(row_to_json(x) ORDER BY source_id)::text, '[]')
        FROM (
            SELECT
                source_id,
                status,
                consecutive_failures,
                checked_at::text,
                last_success_at::text
            FROM source_health
        ) x;
        """,
    )
    content = _query_json(
        db,
        """
        SELECT COALESCE(json_agg(row_to_json(x) ORDER BY processing_status)::text, '[]')
        FROM (
            SELECT processing_status, count(*)::integer AS count
            FROM content_item
            GROUP BY processing_status
        ) x;
        """,
    )
    receipts = _query_json(
        db,
        """
        SELECT COALESCE(json_agg(row_to_json(x)
            ORDER BY provider_id, operation, status)::text, '[]')
        FROM (
            SELECT
                provider_id,
                operation,
                status,
                count(*)::integer AS count,
                COALESCE(sum(
                    CASE
                        WHEN billing_basis='MEASURED_PROVIDER_COST'
                            THEN measured_cost_usd
                        ELSE estimated_cost_usd
                    END
                ), 0)::numeric(12,6) AS cost_usd
            FROM provider_receipt
            WHERE COALESCE(completed_at, started_at, now())
                >= date_trunc('day', now())
            GROUP BY provider_id, operation, status
        ) x;
        """,
    )
    transcripts = _query_json(
        db,
        """
        SELECT json_build_object(
            'variants', (SELECT count(*) FROM transcript_variant),
            'raw_segments', (SELECT count(*) FROM transcript_segment),
            'canonical_segments', (SELECT count(*) FROM canonical_transcript_segment),
            'publication_blocked_segments', (
                SELECT count(*) FROM canonical_transcript_segment
                WHERE publication_blocked
            )
        )::text;
        """,
    )
    claims = _query_json(
        db,
        """
        SELECT json_build_object(
            'atomic_claims', (SELECT count(*) FROM atomic_claim),
            'check_worthy_claims', (
                SELECT count(*) FROM atomic_claim WHERE check_worthy
            ),
            'claim_types', (
                SELECT COALESCE(json_object_agg(claim_type, count), '{}'::json)
                FROM (
                    SELECT claim_type, count(*)::integer AS count
                    FROM atomic_claim
                    GROUP BY claim_type
                    ORDER BY claim_type
                ) types
            )
        )::text;
        """,
    )
    evidence = _query_json(
        db,
        """
        SELECT json_build_object(
            'evidence_records', (SELECT count(*) FROM evidence),
            'claim_candidates', (
                SELECT count(*) FROM claim_evidence_candidate
            ),
            'approved_candidates', (
                SELECT count(*) FROM claim_evidence_candidate
                WHERE status = 'APPROVED'
            ),
            'candidate_statuses', (
                SELECT COALESCE(json_object_agg(status, count), '{}'::json)
                FROM (
                    SELECT status, count(*)::integer AS count
                    FROM claim_evidence_candidate
                    GROUP BY status
                    ORDER BY status
                ) statuses
            ),
            'source_types', (
                SELECT COALESCE(json_object_agg(source_type, count), '{}'::json)
                FROM (
                    SELECT source_type, count(*)::integer AS count
                    FROM evidence
                    GROUP BY source_type
                    ORDER BY source_type
                ) types
            )
        )::text;
        """,
    )
    verification = _query_json(
        db,
        """
        SELECT json_build_object(
            'evidence_observations', (
                SELECT count(*) FROM evidence_observation
            ),
            'observation_statuses', (
                SELECT COALESCE(json_object_agg(status, count), '{}'::json)
                FROM (
                    SELECT status, count(*)::integer AS count
                    FROM evidence_observation
                    GROUP BY status
                    ORDER BY status
                ) statuses
            ),
            'verification_runs', (
                SELECT count(*) FROM verification_run
            ),
            'verification_assessments', (
                SELECT COALESCE(json_object_agg(assessment, count), '{}'::json)
                FROM (
                    SELECT assessment, count(*)::integer AS count
                    FROM verification_run
                    GROUP BY assessment
                    ORDER BY assessment
                ) assessments
            ),
            'findings', (SELECT count(*) FROM finding),
            'finding_publication_statuses', (
                SELECT COALESCE(
                    json_object_agg(publication_status, count),
                    '{}'::json
                )
                FROM (
                    SELECT publication_status, count(*)::integer AS count
                    FROM finding
                    GROUP BY publication_status
                    ORDER BY publication_status
                ) statuses
            ),
            'relation_candidates', (
                SELECT count(*) FROM claim_relation_candidate
            ),
            'relation_candidate_statuses', (
                SELECT COALESCE(json_object_agg(status, count), '{}'::json)
                FROM (
                    SELECT status, count(*)::integer AS count
                    FROM claim_relation_candidate
                    GROUP BY status
                    ORDER BY status
                ) statuses
            ),
            'reanalysis_triggers', (
                SELECT count(*) FROM reanalysis_trigger
            ),
            'reanalysis_statuses', (
                SELECT COALESCE(json_object_agg(status, count), '{}'::json)
                FROM (
                    SELECT status, count(*)::integer AS count
                    FROM reanalysis_trigger
                    GROUP BY status
                    ORDER BY status
                ) statuses
            ),
            'review_events', (SELECT count(*) FROM review_event),
            'review_actions', (
                SELECT COALESCE(json_object_agg(action, count), '{}'::json)
                FROM (
                    SELECT action, count(*)::integer AS count
                    FROM review_event
                    GROUP BY action
                    ORDER BY action
                ) actions
            )
        )::text;
        """,
    )
    identity = _query_json(
        db,
        """
        SELECT json_build_object(
            'public_people', (SELECT count(*) FROM person),
            'speaker_candidates', (
                SELECT count(*) FROM speaker_identity_candidate
            ),
            'speaker_candidate_statuses', (
                SELECT COALESCE(json_object_agg(status, count), '{}'::json)
                FROM (
                    SELECT status, count(*)::integer AS count
                    FROM speaker_identity_candidate
                    GROUP BY status
                    ORDER BY status
                ) statuses
            ),
            'speaker_assigned_segments', (
                SELECT count(*)
                FROM canonical_transcript_segment
                WHERE speaker_person_id IS NOT NULL
            ),
            'speaker_assigned_claims', (
                SELECT count(*)
                FROM atomic_claim
                WHERE speaker_person_id IS NOT NULL
            )
        )::text;
        """,
    )

    blocker_counts: dict[str, int] = {}
    for row in errors:
        category = error_category(row.get("last_error"))
        blocker_counts[category] = blocker_counts.get(category, 0) + int(row["count"])

    total_cost = sum(float(row.get("cost_usd") or 0) for row in receipts)
    measurements = build_slo_measurements(
        queue=queue,
        queue_age=queue_age,
        estimated_cost_usd_today=total_cost,
        max_cost_usd_per_day=max_cost_usd_per_day,
        max_cost_usd_per_source_day=max_cost_usd_per_source_day,
        provider_receipts_today=receipts,
        projection_generated_at=projection_generated_at,
        now=current,
    )
    slo_results = evaluate_slos(measurements)
    blockers = [
        {"category": key, "count": blocker_counts[key]}
        for key in sorted(blocker_counts)
    ]
    return {
        "schema_version": 1,
        "generated_at": current.astimezone(timezone.utc).isoformat(),
        "queue": queue,
        "queue_age": queue_age,
        "blockers": blockers,
        # DP-504: each distinct blocker cause becomes exactly one actionable
        # row with an operator action, so N identical blocked jobs are one
        # alert rather than N.
        "blocker_actions": actionable_blockers(blockers),
        "slo": {
            "overall": worst_slo_status(slo_results),
            "page": list(pageable_slos(slo_results)),
            "objectives": list(slo_results),
        },
        "source_health": source_health,
        "content": content,
        "provider_receipts_today": receipts,
        "estimated_cost_usd_today": round(total_cost, 6),
        "transcripts": transcripts,
        "claims": claims,
        "evidence": evidence,
        "verification": verification,
        "identity": identity,
        "private_runtime_storage": private_tree_stats(private_root),
        "privacy": {
            "contains_transcript_text": False,
            "contains_raw_error_messages": False,
            "contains_secrets": False,
        },
    }


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dichiarazioni Pubbliche private runtime health digest")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument(
        "--private-root",
        type=Path,
        default=Path(
            os.environ.get("DICHIARAZIONI_PUBBLICHE_PRIVATE_DATA_ROOT", str(DEFAULT_PRIVATE_ROOT))
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-cost-usd-day",
        type=float,
        default=float(os.environ.get("DICHIARAZIONI_PUBBLICHE_MAX_COST_USD_DAY", "5")),
    )
    parser.add_argument(
        "--max-cost-usd-source-day",
        type=float,
        default=float(os.environ.get("DICHIARAZIONI_PUBBLICHE_MAX_COST_USD_SOURCE_DAY", "1")),
    )
    parser.add_argument(
        "--projection-generated-at",
        default=os.environ.get("DICHIARAZIONI_PUBBLICHE_PROJECTION_GENERATED_AT"),
    )
    args = parser.parse_args()
    digest = build_health_digest(
        PsqlRuntime(args.database_url),
        private_root=args.private_root,
        max_cost_usd_per_day=args.max_cost_usd_day,
        max_cost_usd_per_source_day=args.max_cost_usd_source_day,
        projection_generated_at=args.projection_generated_at,
    )
    write_private_json(args.output, digest)
    print(
        json.dumps(
            {
                "generated_at": digest["generated_at"],
                "estimated_cost_usd_today": digest["estimated_cost_usd_today"],
                "queue": digest["queue"],
                "blockers": digest["blockers"],
                "slo": digest["slo"],
                "output": str(args.output.expanduser()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
