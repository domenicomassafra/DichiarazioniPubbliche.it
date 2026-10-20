"""Exploratory FIFO replay, not a prediction of GitHub's account scheduler.

Only measured executions enter the workload. Unexecuted demand, other repositories,
retries and unknown dependency graphs are not inferred. All times are in minutes.
"""
from __future__ import annotations

import math


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))]


def matrix_job(job: dict) -> bool:
    # REST jobs expose the display name, not the workflow YAML job_id. This is
    # the documented ci.yml naming contract, not a guess based on runner OS.
    return job.get("job_id", "") == "backend-minimal" or str(job.get("name", "")).startswith("backend ")


def replay(workload: list[dict], macos_slots: int = 5, ubuntu_slots: int = 20,
           max_parallel: int | None = None, macos_per_run: int | None = None,
           needs_linux: bool = False) -> dict:
    """Cap only backend-minimal; stop cancelled runs at the observed terminal cutoff.

    cancelled_at is the last recorded job completion, NOT the unexposed cancellation
    request time. The model cannot recover the duration of jobs never executed.
    """
    for value in (macos_slots, ubuntu_slots, max_parallel, macos_per_run):
        if value is not None and value <= 0:
            raise ValueError("runner slots and caps must be positive")
    state = [dict(run=e["run"], arrival=e["arrival"], pending=list(e["jobs"]),
                  cancelled_at=e.get("cancelled_at"), cancelled=False,
                  matrix_active=0, macos_active=0,
                  linux_left=sum(j["kind"] == "ubuntu" for j in e["jobs"]), done_at=None)
             for e in sorted(workload, key=lambda e: (e["arrival"], e["run"]))]
    ready: dict[str, list] = {"macos": [], "ubuntu": []}
    busy: dict[str, list] = {"macos": [], "ubuntu": []}
    slots = {"macos": macos_slots, "ubuntu": ubuntu_slots}
    queues: list[float] = []
    arrival_waits: list[float] = []
    macos_minutes = 0.0
    clock = min((r["arrival"] for r in state), default=0)

    while True:
        # Finish every job at this instant before admitting the next matrix leg.
        for pool in busy:
            for finish, run, job in list(busy[pool]):
                if finish <= clock:
                    busy[pool].remove((finish, run, job))
                    run["matrix_active"] -= int(matrix_job(job))
                    run["macos_active"] -= int(job["kind"] == "macos")
                    run["linux_left"] -= int(job["kind"] == "ubuntu")
                    run["done_at"] = finish
        for run in state:
            cutoff = run["cancelled_at"]
            if cutoff is not None and cutoff <= clock and not run["cancelled"]:
                run["cancelled"] = True
                run["pending"].clear()
                for pool in ready:
                    ready[pool] = [entry for entry in ready[pool] if entry[0] is not run]
            if run["cancelled"] or run["arrival"] > clock:
                continue
            for job in list(run["pending"]):
                if job.get("ready_at", run["arrival"]) > clock:
                    continue
                if matrix_job(job) and max_parallel is not None and run["matrix_active"] >= max_parallel:
                    continue
                if job["kind"] == "macos":
                    if needs_linux and run["linux_left"]:
                        continue
                    if macos_per_run is not None and run["macos_active"] >= macos_per_run:
                        continue
                run["pending"].remove(job)
                run["matrix_active"] += int(matrix_job(job))
                run["macos_active"] += int(job["kind"] == "macos")
                pool = "macos" if job["kind"] == "macos" else "ubuntu"
                ready[pool].append((run, job, clock))
        for pool in busy:
            while ready[pool] and len(busy[pool]) < slots[pool]:
                run, job, released = ready[pool].pop(0)
                # 'seconds' was the legacy input key, although its values were minutes.
                duration = job.get("minutes", job.get("seconds"))
                if duration is None or duration < 0:
                    raise ValueError("job duration must be nonnegative minutes")
                finish = clock + duration
                if run["cancelled_at"] is not None:
                    finish = min(finish, run["cancelled_at"])
                busy[pool].append((finish, run, job))
                if pool == "macos":
                    queues.append(clock - released)
                    arrival_waits.append(clock - run["arrival"])
                    macos_minutes += finish - clock
        next_times = [finish for entries in busy.values() for finish, _, _ in entries]
        next_times += [r["arrival"] for r in state if r["arrival"] > clock]
        next_times += [r["cancelled_at"] for r in state
                       if r["cancelled_at"] is not None and r["cancelled_at"] > clock]
        next_times += [j["ready_at"] for r in state for j in r["pending"]
                       if j.get("ready_at", clock) > clock]
        if not next_times:
            if any(r["pending"] for r in state) or any(ready.values()):
                raise ValueError("workload cannot make progress")
            break
        clock = min(next_times)

    completion = [r["done_at"] - r["arrival"] for r in state
                  if r["done_at"] is not None and r["cancelled_at"] is None]
    return {
        "exploratory": True,
        "runs": len(completion),
        "cancelled_runs": sum(r["cancelled_at"] is not None for r in state),
        "run_completion_median": percentile(completion, .5),
        "run_completion_mean": sum(completion) / len(completion) if completion else None,
        "run_completion_p90": percentile(completion, .9),
        "run_completion_max": percentile(completion, 1),
        "macos_queue_median": percentile(queues, .5),
        "macos_queue_p90": percentile(queues, .9),
        "macos_queue_mean": sum(queues) / len(queues) if queues else None,
        "macos_wait_from_arrival_mean": sum(arrival_waits) / len(arrival_waits) if arrival_waits else None,
        "macos_minutes": macos_minutes,
    }
