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

`jobs.<job_id>.strategy.max-parallel` looks like the fix and is not: it caps the
jobs of one matrix "even if there are runners available to run all six jobs at
once" (GitHub Docs, *Running variations of jobs in a workflow*, read 20/10/2026).
A per-run cap moves the wait from the queue into the run; it never adds pool
capacity. `replay` here measures that trade on data already recorded by GitHub,
so the decision is taken on numbers instead of on a recipe.

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

`docs/ops/ci-matrix-capacity-20261020.md` records how to rebuild the export and
what the recorded measurement says.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

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


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile; deterministic for a given input list."""
    if not values:
        return None
    ordered = sorted(values)
    if fraction <= 0:
        return ordered[0]
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


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
        finished = _timestamp(run.get("updated_at"))
        if created and (window_start is None or created < window_start):
            window_start = created
        if finished and (window_end is None or finished > window_end):
            window_end = finished
        # A run still in flight has no wall clock yet: counting created->updated
        # would report the partial elapsed time as if the run had finished.
        if run.get("status") == "completed":
            run_wall = _minutes(finished, created)
            if run_wall is not None:
                wall.append(run_wall)
        for job in run_jobs:
            kind = job_runner_kind(job.get("labels"))
            started = _timestamp(job.get("started_at"))
            completed = _timestamp(job.get("completed_at"))
            sample = {
                "run": run_id,
                "name": job.get("name"),
                "conclusion": job.get("conclusion"),
                "queue": _minutes(started, created),
                "execution": _minutes(completed, started),
            }
            samples[kind].append(sample)
            if kind in pool_minutes and sample["execution"] is not None:
                pool_minutes[kind] += sample["execution"]
                if job.get("conclusion") in {"cancelled", "failure"}:
                    wasted_minutes[kind] += sample["execution"]

    report: dict = {
        "runs": len(jobs),
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
        }
    report["run_wall"] = {
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
            if duration is None:
                continue
            measured.append(
                {"kind": job_runner_kind(job.get("labels")), "name": job.get("name"), "seconds": duration}
            )
        if not measured:
            continue
        workload.append(
            {"run": run_id, "arrival": created.timestamp() / 60.0, "jobs": measured}
        )
    workload.sort(key=lambda entry: (entry["arrival"], entry["run"]))
    return workload


def replay(
    workload: list[dict],
    macos_slots: int = MACOS_SLOTS,
    ubuntu_slots: int = UBUNTU_SLOTS,
    max_parallel: int | None = None,
    macos_per_run: int | None = None,
    needs_linux: bool = False,
) -> dict:
    """Re-dispatch the recorded workload under a different per-run policy.

    `max_parallel` mirrors `strategy.max-parallel`; `macos_per_run` is the same
    idea restricted to macOS jobs of one run; `needs_linux` delays a run's macOS
    jobs until its Linux jobs finished. FIFO on both pools, no retries, no
    speculative speed-ups.
    """
    state = []
    for entry in workload:
        state.append(
            {
                "run": entry["run"],
                "arrival": entry["arrival"],
                "pending": list(entry["jobs"]),
                "running": 0,
                "macos_running": 0,
                "linux_pending": sum(1 for job in entry["jobs"] if job["kind"] == UBUNTU),
                "done_at": None,
                "macos_queue": [],
            }
        )
    state.sort(key=lambda run: (run["arrival"], run["run"]))
    pending = list(state)
    macos_ready: list[tuple[dict, dict, float]] = []
    ubuntu_ready: list[tuple[dict, dict, float]] = []
    macos_busy: list[tuple[float, dict, dict]] = []
    ubuntu_busy: list[tuple[float, dict, dict]] = []

    def release(run: dict, now: float) -> None:
        index = 0
        while index < len(run["pending"]):
            if max_parallel is not None and run["running"] >= max_parallel:
                return
            job = run["pending"][index]
            if job["kind"] == MACOS:
                # A blocked macOS job never blocks the Linux jobs behind it.
                if needs_linux and run["linux_pending"] > 0:
                    index += 1
                    continue
                if macos_per_run is not None and run["macos_running"] >= macos_per_run:
                    index += 1
                    continue
            run["pending"].pop(index)
            run["running"] += 1
            if job["kind"] == MACOS:
                run["macos_running"] += 1
                macos_ready.append((run, job, now))
            else:
                ubuntu_ready.append((run, job, now))

    clock = min((run["arrival"] for run in state), default=0.0)
    while True:
        for run in list(pending):
            if run["arrival"] <= clock:
                pending.remove(run)
                release(run, clock)
        while len(macos_busy) < macos_slots and macos_ready:
            run, job, released_at = macos_ready.pop(0)
            run["macos_queue"].append(clock - released_at)
            macos_busy.append((clock + job["seconds"], run, job))
        while len(ubuntu_busy) < ubuntu_slots and ubuntu_ready:
            run, job, _released_at = ubuntu_ready.pop(0)
            ubuntu_busy.append((clock + job["seconds"], run, job))
        if not macos_busy and not ubuntu_busy and not macos_ready and not ubuntu_ready and not pending:
            break
        next_times = [entry[0] for entry in macos_busy] + [entry[0] for entry in ubuntu_busy]
        next_times += [run["arrival"] for run in pending]
        clock = min(next_times)
        finished_macos = [entry for entry in macos_busy if entry[0] <= clock]
        finished_ubuntu = [entry for entry in ubuntu_busy if entry[0] <= clock]
        macos_busy = [entry for entry in macos_busy if entry[0] > clock]
        ubuntu_busy = [entry for entry in ubuntu_busy if entry[0] > clock]
        for finish, run, _job in finished_macos:
            run["running"] -= 1
            run["macos_running"] -= 1
            run["done_at"] = finish if run["done_at"] is None else max(run["done_at"], finish)
            release(run, finish)
        for finish, run, job in finished_ubuntu:
            run["running"] -= 1
            if job["kind"] == UBUNTU:
                run["linux_pending"] -= 1
            run["done_at"] = finish if run["done_at"] is None else max(run["done_at"], finish)
            release(run, finish)

    completion = sorted(
        run["done_at"] - run["arrival"] for run in state if run["done_at"] is not None
    )
    macos_queue = sorted(q for run in state for q in run["macos_queue"])
    return {
        "runs": len(completion),
        "run_completion_median": percentile(completion, 0.50),
        "run_completion_p90": percentile(completion, 0.90),
        "run_completion_max": percentile(completion, 1.0),
        "macos_queue_median": percentile(macos_queue, 0.50),
        "macos_queue_p90": percentile(macos_queue, 0.90),
        "macos_queue_mean": (sum(macos_queue) / len(macos_queue)) if macos_queue else None,
    }


def _print_report(report: dict) -> None:
    print(f"recorded window: {report['runs']} runs / {report['window_minutes']:.0f} minutes")
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
    parser.add_argument("--max-parallel", type=int, default=None, help="cap all jobs of one run")
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
