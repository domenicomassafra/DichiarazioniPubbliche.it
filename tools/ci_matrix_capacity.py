#!/usr/bin/env python3
"""Read-only capacity report for the CI matrix (DP-602, controlcenter#418).

Why this exists
---------------
The matrix runs four Python versions on `ubuntu-latest` and four on
`macos-latest`. GitHub bills public repositories nothing for hosted runners, but
the *plan concurrency limit* still applies: at most 5 macOS jobs run at once for
the whole account, against 20 jobs in total ("Job concurrency limits for
GitHub-hosted runners", GitHub Docs, read 20/10/2026). Fourteen open pull
requests therefore ask for 56 simultaneous macOS jobs against a pool of 5.

A per-matrix cap never adds capacity. The replay is exploratory, not a causal
measurement: unknown unexecuted work, cross-repository interference and scheduler
ordering cannot be reconstructed from these REST payloads.

Usage
-----
    # measure: per-runner queue/execution time, run wall clock, pool waste
    python3 tools/ci_matrix_capacity.py report --export ~/ci-export

    # would a per-run cap have helped? replay the recorded workload
    python3 tools/ci_matrix_capacity.py replay --export ~/ci-export --max-parallel 2
    python3 tools/ci_matrix_capacity.py replay --export ~/ci-export --macos-per-run 2

The export directory holds GitHub REST payloads only, so the tool never calls
the network:

    runs.json          # GET /repos/{owner}/{repo}/actions/runs  (or bare list)
    jobs-<run_id>.json # GET /repos/{owner}/{repo}/actions/runs/{id}/jobs

`docs/adr/0011-no-per-run-cap-on-the-ci-matrix.md` documents the export contract,
policy and limitations. The original ADR's numbers were invalidated by review.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Re-export the public tool API; keep scheduling separate from REST accounting.
from ci_matrix_replay import percentile, replay

UBUNTU_SLOTS = 20
MACOS_SLOTS = 5
# Names produced by the matrix, in dispatch order, are kept exactly as GitHub
# reports them: the report never renames a check.
MACOS = "macos"
UBUNTU = "ubuntu"
OTHER = "other"


def _timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def job_runner_kind(labels: list[str] | None) -> str:
    """Classify a job by the runner label GitHub reported for it."""
    lowered = [str(label).lower() for label in (labels or [])]
    if any("macos" in label for label in lowered):
        return MACOS
    if any("ubuntu" in label for label in lowered):
        return UBUNTU
    return OTHER


def job_executed(job: dict) -> bool:
    """started_at alone also exists on jobs cancelled before runner assignment."""
    return (job.get("status") != "queued" and bool(job.get("started_at"))
            and bool(job.get("runner_id") or job.get("runner_name") or job.get("steps")))


def run_finished(run_jobs: list[dict]) -> dt.datetime | None:
    return max((_timestamp(j.get("completed_at")) for j in run_jobs
                if j.get("completed_at")), default=None)


def _minutes(later: dt.datetime | None, earlier: dt.datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds() / 60.0


def load_export(directory: Path) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Read the recorded REST payloads; never fetch anything."""
    runs_payload = json.loads((directory / "runs.json").read_text(encoding="utf-8"))
    run_list = runs_payload["workflow_runs"] if isinstance(runs_payload, dict) else runs_payload
    runs = {str(run["id"]): run for run in run_list}
    jobs: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("jobs-*.json")):
        run_id = path.stem.split("jobs-", 1)[1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        jobs[run_id] = payload.get("jobs", [])
    return runs, jobs


def summarize(runs: dict[str, dict], jobs: dict[str, list[dict]]) -> dict:
    """Queue, execution, wall clock and pool waste for one recorded window."""
    samples: dict[str, list[dict]] = {MACOS: [], UBUNTU: [], OTHER: []}
    wall: list[float] = []
    pool_minutes = {MACOS: 0.0, UBUNTU: 0.0}
    wasted_minutes = {MACOS: 0.0, UBUNTU: 0.0}
    window_start: dt.datetime | None = None
    window_end: dt.datetime | None = None

    for run_id, run_jobs in jobs.items():
        run = runs.get(run_id)
        if run is None:
            continue
        created = _timestamp(run.get("created_at"))
        finished = run_finished(run_jobs)
        if created and (window_start is None or created < window_start):
            window_start = created
        if finished and (window_end is None or finished > window_end):
            window_end = finished
        # A run still in flight has no wall clock yet: counting created->updated
        # would report the partial elapsed time as if the run had finished.
        if run.get("status") == "completed" and all(j.get("status") == "completed" for j in run_jobs):
            run_wall = _minutes(finished, created)
            if run_wall is not None:
                wall.append(run_wall)
        for job in run_jobs:
            kind = job_runner_kind(job.get("labels"))
            started = _timestamp(job.get("started_at"))
            completed = _timestamp(job.get("completed_at"))
            began = job_executed(job)
            sample = {
                "run": run_id,
                "name": job.get("name"),
                "conclusion": job.get("conclusion"),
                "queue": _minutes(started, _timestamp(job.get("created_at"))) if began else None,
                "execution": _minutes(completed, started) if began else None,
                "queued": job.get("status") == "queued",
                "not_executed": not began,
            }
            samples[kind].append(sample)
            if kind in pool_minutes and sample["execution"] is not None:
                pool_minutes[kind] += sample["execution"]
                if run.get("conclusion") in {"cancelled", "failure", "timed_out", "startup_failure"}:
                    wasted_minutes[kind] += sample["execution"]

    report: dict = {
        "runs": sum(run_id in runs for run_id in jobs),
        "unmatched_job_exports": sorted(set(jobs) - set(runs)),
        "window_minutes": _minutes(window_end, window_start),
    }
    for kind in (MACOS, UBUNTU, OTHER):
        queued = [s["queue"] for s in samples[kind] if s["queue"] is not None]
        executed = [s["execution"] for s in samples[kind] if s["execution"] is not None]
        report[kind] = {
            "jobs": len(samples[kind]),
            "queue_median": percentile(queued, 0.50),
            "queue_mean": (sum(queued) / len(queued)) if queued else None,
            "queue_p90": percentile(queued, 0.90),
            "queue_max": percentile(queued, 1.0),
            "queue_over_5m": sum(1 for value in queued if value >= 5),
            "queue_over_10m": sum(1 for value in queued if value >= 10),
            "execution_median": percentile(executed, 0.50),
            "queued_now": sum(1 for s in samples[kind] if s["queued"]),
            "started": sum(not s["not_executed"] for s in samples[kind]),
            "not_executed": sum(s["not_executed"] for s in samples[kind]),
            "queue_samples": len(queued),
            "execution_mean": sum(executed) / len(executed) if executed else None,
        }
    report["run_wall"] = {
        "samples": len(wall),
        "mean": sum(wall) / len(wall) if wall else None,
        "median": percentile(wall, 0.50),
        "p90": percentile(wall, 0.90),
        "max": percentile(wall, 1.0),
    }
    report["pool"] = {
        "macos_minutes": pool_minutes[MACOS],
        "ubuntu_minutes": pool_minutes[UBUNTU],
        "macos_minutes_without_verdict": wasted_minutes[MACOS],
        "ubuntu_minutes_without_verdict": wasted_minutes[UBUNTU],
        "macos_share_without_verdict": (
            wasted_minutes[MACOS] / pool_minutes[MACOS] if pool_minutes[MACOS] else None
        ),
    }
    if report["window_minutes"] and report["window_minutes"] > 0:
        capacity = report["window_minutes"] * MACOS_SLOTS
        report["pool"]["macos_utilisation"] = pool_minutes[MACOS] / capacity
    else:
        report["pool"]["macos_utilisation"] = None
    return report


def build_workload(runs: dict[str, dict], jobs: dict[str, list[dict]]) -> list[dict]:
    """Recorded workload: one entry per run with its measured job durations.

    Job order is the order GitHub dispatched them in, which is the matrix
    expansion order. A job with no recorded duration is skipped rather than
    guessed.
    """
    workload: list[dict] = []
    for run_id, run_jobs in jobs.items():
        run = runs.get(run_id)
        if run is None:
            continue
        created = _timestamp(run.get("created_at"))
        if created is None:
            continue
        measured: list[dict] = []
        for job in run_jobs:
            started = _timestamp(job.get("started_at"))
            completed = _timestamp(job.get("completed_at"))
            duration = _minutes(completed, started)
            if not job_executed(job) or duration is None or duration < 0:
                continue
            measured.append({
                "kind": job_runner_kind(job.get("labels")), "name": job.get("name"),
                "minutes": duration,
                "ready_at": (_timestamp(job.get("created_at")) or created).timestamp() / 60,
                "job_id": "backend-minimal" if str(job.get("name", "")).startswith("backend ") else job.get("name"),
            })
        if not measured:
            continue
        entry = {"run": run_id, "arrival": created.timestamp() / 60.0, "jobs": measured}
        if run.get("conclusion") == "cancelled" and run_finished(run_jobs):
            entry["cancelled_at"] = run_finished(run_jobs).timestamp() / 60
        workload.append(entry)
    workload.sort(key=lambda entry: (entry["arrival"], entry["run"]))
    return workload


def _print_report(report: dict) -> None:
    print(f"recorded window: {report['runs']} runs / {_fmt(report['window_minutes'])} minutes")
    if report["unmatched_job_exports"]:
        print(f"  WARNING: missing run metadata for {report['unmatched_job_exports']}")
    for kind in (MACOS, UBUNTU):
        section = report[kind]
        if not section["jobs"]:
            continue
        print(
            f"  {kind:6s} jobs={section['jobs']:4d} queue median={_fmt(section['queue_median'])} "
            f"mean={_fmt(section['queue_mean'])} p90={_fmt(section['queue_p90'])} "
            f"max={_fmt(section['queue_max'])} (>=5m {section['queue_over_5m']}, "
            f">=10m {section['queue_over_10m']}) exec median={_fmt(section['execution_median'])}"
        )
    wall = report["run_wall"]
    print(
        f"  run wall clock median={_fmt(wall['median'])} p90={_fmt(wall['p90'])} max={_fmt(wall['max'])}"
    )
    pool = report["pool"]
    share = pool["macos_share_without_verdict"]
    utilisation = pool["macos_utilisation"]
    print(
        f"  macOS pool minutes={pool['macos_minutes']:.0f} "
        f"without-verdict={pool['macos_minutes_without_verdict']:.0f} "
        f"({percent_text(share)}) utilisation={percent_text(utilisation)}"
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def percent_text(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _print_replay(result: dict) -> None:
    print(
        f"  runs={result['runs']} completion median={_fmt(result['run_completion_median'])} "
        f"p90={_fmt(result['run_completion_p90'])} max={_fmt(result['run_completion_max'])} "
        f"| macOS queue median={_fmt(result['macos_queue_median'])} "
        f"mean={_fmt(result['macos_queue_mean'])} p90={_fmt(result['macos_queue_p90'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("report", "replay"))
    parser.add_argument("--export", required=True, type=Path, help="directory with the REST export")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--max-parallel", type=int, default=None, help="cap only backend-minimal matrix legs")
    parser.add_argument("--macos-per-run", type=int, default=None, help="cap macOS jobs of one run")
    parser.add_argument("--needs-linux", action="store_true", help="start macOS after the Linux jobs")
    parser.add_argument("--macos-slots", type=int, default=MACOS_SLOTS)
    parser.add_argument("--ubuntu-slots", type=int, default=UBUNTU_SLOTS)
    args = parser.parse_args(argv)

    if not args.export.is_dir():
        print(f"export directory not found: {args.export}", file=sys.stderr)
        return 2
    runs, jobs = load_export(args.export)
    if args.command == "report":
        report = summarize(runs, jobs)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_report(report)
        return 0

    workload = build_workload(runs, jobs)
    baseline = replay(workload, args.macos_slots, args.ubuntu_slots)
    capped = replay(
        workload,
        args.macos_slots,
        args.ubuntu_slots,
        max_parallel=args.max_parallel,
        macos_per_run=args.macos_per_run,
        needs_linux=args.needs_linux,
    )
    if args.json:
        print(json.dumps({"workload_runs": len(workload), "baseline": baseline, "capped": capped},
                         indent=2, sort_keys=True))
        return 0
    print(f"recorded workload: {len(workload)} runs")
    print("  today (no per-run cap):")
    _print_replay(baseline)
    print("  with the requested cap:")
    _print_replay(capped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
