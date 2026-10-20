# ADR 0011 — No per-run cap on the CI matrix

Status: Accepted
Date: 2026-10-20

## Context

`ci.yml` runs `backend-minimal` as a 2×4 matrix: four Python versions on
`ubuntu-latest` and the same four on `macos-latest`. GitHub-hosted usage is free
for this public repository, but the *plan concurrency limit* still binds: at most
**5 macOS jobs run at once for the whole account**, against 20 jobs in total
("Job concurrency limits for GitHub-hosted runners", GitHub Docs, read
20/10/2026). On 20/10/2026 fourteen pull requests were open, so the account asked
for 56 simultaneous macOS jobs against a pool of 5 and some jobs waited.

controlcenter#418 proposed fixing that with `jobs.<job_id>.strategy.max-parallel`
(2) or a macOS-only variant. The open question was measured before any workflow
changed: two per-run caps and a `needs` ordering were replayed against the
workload GitHub had already recorded.

## Measurement

`tools/ci_matrix_capacity.py report --export <dir>` over 117 recorded `ci` runs
(20/10/2026, 02:15–14:4x UTC, 464 macOS jobs, 1160 Ubuntu jobs):

| metric | whole window | 13:30 onward, 15 pull requests open |
| --- | --- | --- |
| macOS queue | median 1.1 min, mean 2.1, p90 5.3, max 21.4 (48 jobs ≥ 5 min, 12 ≥ 10 min) | median 2.9, mean 3.5, p90 8.6, max 19.1 (15 of 100 jobs ≥ 5 min) |
| Ubuntu queue | median 0.1, max 1.7 min — not contended | median 0.2, max 1.1 |
| run wall clock | median 5.5 min, p90 10.7, max 28.2 | median 10.0 min, p90 15.9 |
| macOS execution | median 3.9 min | median 4.0 min |
| macOS pool | 1525 minutes, 41.9% of the 5 slots, **20.7% spent on runs that ended without a verdict** | 63.3% utilisation, **45.2% without a verdict** |

`replay` re-dispatches that same recorded workload under each proposed policy
(FIFO, macOS pool 5, Ubuntu pool 20):

| policy | run completion median | p90 | max | macOS queue p90 |
| --- | --- | --- | --- | --- |
| today, no per-run cap | 5.2 | 15.0 | 42.9 | 9.7 |
| `max-parallel: 2` on the whole matrix | 16.2 | 26.6 | 48.7 | 5.0 |
| 2 macOS jobs per run | 8.4 | 21.7 | 48.3 | 6.6 |
| 2 macOS jobs per run + macOS after Linux | 11.3 | 24.6 | 51.1 | 6.5 |

Every cap halves the queue and lengthens the run more than it shortens the wait,
including the worst case: the wait moves from the queue into the run, because
`max-parallel` is a cap on one matrix, not on the pool — "a maximum of two jobs
at a time, even if there are runners available to run all six jobs at once"
(GitHub Docs, *Running variations of jobs in a workflow*, read 20/10/2026).

Gating macOS behind the Linux verdict does not pay either: of the 25 cancelled
runs that had already started macOS, only 3 would have avoided macOS entirely
(cancellation arrives at median 4.9 min, the Linux half finishes at median
2.9 min), saving 16 of 319 wasted minutes while delaying every macOS job. The
burst window makes the point sharper: with fifteen pull requests open the pool
runs at 63.3% and still no per-run cap reduces the time an author waits.

## Decision

Do not add `strategy.max-parallel` and do not serialize macOS behind Linux. The
matrix keeps its eight parallel jobs; the required check names, the matrix
entries and every test stay exactly as branch protection expects them.

A job only measures a queue once a runner picked it up: GitHub fills
`started_at` when the job is enqueued too, so counting queued jobs as zero-wait
understates the load (the tool counts them separately).

Measure again before changing this: the 5-slot pool, the number of open pull
requests and the duration of the suite all move. `tools/ci_matrix_capacity.py`
recomputes both tables from GitHub's own run and job records, offline.

## Consequences

- The queue is a capacity fact, not a configuration defect. Nothing in the
  workflow file can raise the account's macOS pool.
- A future proposal to cap parallelism has to show a replay in which it improves
  run completion, not only the queue.
- The real levers sit outside this repository: fewer macOS entries among the
  required checks (a branch-protection decision), a self-hosted macOS runner, a
  request to GitHub Support to raise the concurrency limit, or fewer concurrent
  pull requests pushing near-simultaneous commits — 19.4% of the macOS pool time
  is spent on runs superseded or failing minutes later.

## Evidence

- `tools/ci_matrix_capacity.py` and `tests/test_ci_matrix_capacity.py`
  (`report`, `replay`).
- controlcenter#418 and the #413 inventory of the nine active repositories.
- [Job concurrency limits for GitHub-hosted runners](https://docs.github.com/en/actions/reference/limits),
  [Running variations of jobs in a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations),
  both read 20/10/2026.
