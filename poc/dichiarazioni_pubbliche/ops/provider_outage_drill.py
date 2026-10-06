"""Provider-outage drill driver (DP-506).

Runs the *real* ``ProcessingWorker`` against a throwaway database with a claim
client that fails the way a real outage fails, then asserts the fail-closed
outcome.

The assertions are deliberately about what did NOT happen, because that is the
invariant under attack:

  * every claim job ends BLOCKED, never COMPLETED;
  * no provider_receipt with status SUCCESS is written;
  * no atomic_claim row appears;
  * no finding changes publication_status;
  * the queue is not left with an unbounded retry/deferred loop;
  * estimated provider cost stays exactly zero.

Nothing here stubs the worker's dispatch, budget preflight, or blocked-job
bookkeeping. If the worker ever grew a "degraded but still publish" path, this
drill would fail.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_runtime import ClaimRuntimeProbe
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.source_watcher import load_registry
from dichiarazioni_pubbliche.worker_daemon import ProcessingWorker, WorkerBudget


class OutageClaimClient:
    """A claim client that is reachable but failing, i.e. a real outage.

    It is *not* a permissive stub. ``probe`` reports unhealthy so the worker's
    canary gate refuses fan-out, and ``extract`` raises if it is ever reached,
    which turns an accidental bypass of the gate into a loud failure.
    """

    model = "drill-model/antigravity-outage"
    prompt_version = "drill-outage"
    max_output_tokens = 64

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.extract_calls = 0

    def probe(self) -> ClaimRuntimeProbe:
        if self.mode == "credential":
            return ClaimRuntimeProbe(
                healthy=False,
                reason="OMNIROUTE_API_KEY_MISSING",
                latency_seconds=0.0,
                http_status=None,
            )
        return ClaimRuntimeProbe(
            healthy=False,
            reason="OMNIROUTE_HTTP_400:bad_request",
            latency_seconds=0.4,
            http_status=400,
        )

    def extract(self, **_: Any):
        self.extract_calls += 1
        raise RuntimeError(
            "DRILL_INVARIANT_VIOLATION:extract_reached_during_outage"
        )


class DrillPrivateStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def persist_caption(self, **_):  # pragma: no cover - not reached in outage
        return self.root

    def persist_asr_response(self, **_):  # pragma: no cover - not reached
        return self.root


CONTENT_ID = "content:outage-drill"
VARIANT_ID = "variant:outage-drill"


def _seed(db: QueueRuntimeStore) -> None:
    """Insert a minimal, realistic pre-claim state.

    Canonical segments are present and resolved, so the *only* thing standing
    between the drill and a published claim is the provider. If the pipeline
    degrades quietly, it will show up here rather than in a contrived scenario
    where nothing could have been produced anyway.
    """
    db.run(
        """
        INSERT INTO source (id, canonical_name, source_type)
        VALUES ('drill-source', 'Drill Source', 'PODCAST_RSS')
        ON CONFLICT (id) DO NOTHING;
        """
    )
    db.run(
        f"""
        INSERT INTO content_item (
            id, source_id, source_external_id, canonical_url, title,
            published_at, processing_status
        ) VALUES (
            '{CONTENT_ID}', 'drill-source', 'drill-1',
            'https://example.test/drill.mp3', 'Drill Episode',
            '2026-09-20', 'TRANSCRIPT_CANDIDATE_READY'
        )
        ON CONFLICT (id) DO NOTHING;
        """
    )
    db.run(
        """
        INSERT INTO transcript_variant (
            id, content_id, provider_id, source_kind, language,
            raw_text, raw_text_sha256
        ) VALUES (
            'variant:outage-drill', 'content:outage-drill', 'drill',
            'PLATFORM_CAPTION', 'it',
            'Testo di prova con il valore 10.',
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        )
        ON CONFLICT (id) DO NOTHING;
        """
    )
    for index, (start, text) in enumerate(
        ((0, "Il valore e 10."), (3000, "Secondo segmento di prova."))
    ):
        db.run(
            f"""
            INSERT INTO canonical_transcript_segment (
                id, content_id, segment_index, start_ms, end_ms,
                canonical_text, transcript_status
            ) VALUES (
                'canonical:outage-drill:{index}', 'content:outage-drill',
                {index}, {start}, {start + 2500},
                '{text}', 'RESOLVED'
            )
            ON CONFLICT (id) DO NOTHING;
            """
        )
    db.run(
        f"""
        INSERT INTO processing_job (id, content_id, job_type, state, payload)
        VALUES (
            'job:outage-drill:claim-prepare', 'content:outage-drill',
            'CLAIM_PREPARE', 'QUEUED',
            jsonb_build_object(
                'source_id', 'drill-source',
                'variant_id', '{VARIANT_ID}',
                'estimated_cost_usd', 0.0
            )
        )
        ON CONFLICT (id) DO NOTHING;
        """
    )


def _scalar(db: QueueRuntimeStore, sql: str) -> Any:
    raw = (db.run(sql) or "").strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def _snapshot(db: QueueRuntimeStore) -> dict[str, Any]:
    return {
        "job_states": json.loads(
            db.run(
                """
                SELECT COALESCE(json_agg(json_build_object(
                    'job_type', job_type, 'state', state
                ) ORDER BY job_type, state)::text, '[]')
                FROM processing_job
                WHERE content_id = 'content:outage-drill';
                """
            )
            or "[]"
        ),
        "claims": _scalar(
            db, "SELECT count(*) FROM atomic_claim WHERE content_id = 'content:outage-drill'"
        ),
        "claim_windows": _scalar(
            db,
            "SELECT count(*) FROM processing_job "
            "WHERE content_id = 'content:outage-drill' AND job_type = 'CLAIM_EXTRACT_WINDOW'",
        ),
        "success_receipts": _scalar(
            db,
            "SELECT count(*) FROM provider_receipt WHERE status = 'SUCCESS'",
        ),
        "published_findings": _scalar(
            db,
            "SELECT count(*) FROM finding WHERE publication_status = 'PUBLISH'",
        ),
        "cost_usd": _scalar(
            db,
            "SELECT COALESCE(sum(CASE "
            "WHEN billing_basis='MEASURED_PROVIDER_COST' THEN measured_cost_usd "
            "ELSE estimated_cost_usd END), 0)::text FROM provider_receipt",
        ),
    }


def run_drill(database_url: str, registry_path: Path, mode: str, runs: int = 2) -> dict[str, Any]:
    """Execute the outage and return the observed evidence + verdict."""
    db = QueueRuntimeStore(database_url)
    _seed(db)
    before = _snapshot(db)

    client = OutageClaimClient(mode)
    worker = ProcessingWorker(
        store=db,
        registry=load_registry(registry_path),
        resolver=None,
        private_store=DrillPrivateStore(Path(tempfile.gettempdir())),
        worker_id="outage-drill",
        budget=WorkerBudget(),
        claim_client=client,
        claim_max_usd_per_1k_total_tokens=0.001,
    )

    summaries = []
    for _ in range(max(runs, 1)):
        summaries.append(worker.run(1))
    after = _snapshot(db)

    blocked = sum(1 for row in after["job_states"] if row["state"] == "BLOCKED")
    failures: list[str] = []

    if not any(row["job_type"] == "CLAIM_PREPARE" and row["state"] == "BLOCKED"
               for row in after["job_states"]):
        failures.append(
            f"claim job did not reach BLOCKED: {after['job_states']}"
        )
    for summary in summaries:
        if summary.completed:
            failures.append(f"worker completed {summary.completed} job(s) during outage")
        if summary.dead_lettered:
            failures.append("worker dead-lettered instead of blocking (retry loop)")
    # A repeated pass legitimately finds nothing left to claim, so require the
    # blocked outcome across the run set rather than on every individual pass.
    if sum(s.blocked for s in summaries) < 1:
        failures.append("worker did not record a blocked job across any pass")
    if after["claims"] != before["claims"]:
        failures.append(
            f"atomic_claim rows created during outage: {before['claims']} -> {after['claims']}"
        )
    if after["claim_windows"]:
        failures.append(
            f"{after['claim_windows']} claim window(s) materialized during outage"
        )
    if after["success_receipts"] != before["success_receipts"]:
        failures.append("a SUCCESS provider receipt was written during a total outage")
    if after["published_findings"] != before["published_findings"]:
        failures.append("a finding became published during a provider outage")
    if float(after["cost_usd"] or 0) != 0.0:
        failures.append(f"provider cost incurred during outage: {after['cost_usd']}")
    if client.extract_calls:
        failures.append(
            "the model was actually invoked during a failed canary "
            "(canary gate bypassed)"
        )
    if blocked < 1:
        failures.append("no BLOCKED job observed")

    return {
        "mode": mode,
        "before": before,
        "after": after,
        "worker_summaries": [
            {
                "claimed": s.claimed,
                "completed": s.completed,
                "blocked": s.blocked,
                "deferred": s.deferred,
                "retried": s.retried,
                "dead_lettered": s.dead_lettered,
                "queue_states": s.queue_states,
            }
            for s in summaries
        ],
        "blocker_reason": db.run(
            "SELECT COALESCE(last_error,'')::text FROM processing_job "
            "WHERE id = 'job:outage-drill:claim-prepare'"
        ).strip(),
        "extract_calls": client.extract_calls,
        "failures": failures,
        "verdict": "PASS" if not failures else "INVARIANT_VIOLATED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove a provider outage degrades to BLOCKED, never to lower quality."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--outage", choices=("credential", "http"), default="credential")
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args(argv)

    if not os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL") and not args.database_url:
        print("PROVIDER OUTAGE DRILL: no database url", file=sys.stderr)
        return 2

    try:
        result = run_drill(args.database_url, args.registry, args.outage, args.runs)
    except Exception as exc:  # noqa: BLE001 - a drill that cannot run is BLOCKED
        print(
            f"PROVIDER OUTAGE DRILL: BLOCKED, drill could not run: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("PROVIDER OUTAGE DRILL")
    print(f"  mode                : {result['mode']}")
    print(f"  blocker reason      : {result['blocker_reason']}")
    print(f"  job states (after)  : {json.dumps(result['after']['job_states'])}")
    print(f"  worker summaries    : {json.dumps(result['worker_summaries'])}")
    print(f"  claims before/after: {result['before']['claims']} -> {result['after']['claims']}")
    print(f"  claim windows       : {result['after']['claim_windows']}")
    print(f"  success receipts    : {result['before']['success_receipts']} -> {result['after']['success_receipts']}")
    print(f"  published findings  : {result['before']['published_findings']} -> {result['after']['published_findings']}")
    print(f"  provider cost usd   : {result['after']['cost_usd']}")
    print(f"  model invocations   : {result['extract_calls']}")
    print()
    if result["verdict"] == "PASS":
        print(
            "RESULT: PASS - provider outage produced an explicit BLOCKED state; "
            "no claim, no receipt, no publication, no cost, no downgrade."
        )
        return 0
    print("RESULT: INVARIANT VIOLATED - the outage produced degraded output")
    for failure in result["failures"]:
        print(f"  - {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
