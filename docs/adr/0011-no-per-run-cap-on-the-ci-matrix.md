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

`tools/ci_matrix_capacity.py report --export <dir>` over 111 recorded `ci` runs
(20/10/2026, 02:15–14:06 UTC, 440 macOS jobs, 1100 Ubuntu jobs):

| metric | value |
| --- | --- |
| macOS queue | median 0.8 min, mean 2.0, p90 5.2, max 21.4 (48 jobs ≥ 5 min, 12 ≥ 10 min) |
| Ubuntu queue | median 0.1, max 1.7 min — not contended |
| run wall clock | median 5.1 min, p90 10.7, max 28.2 |
| macOS execution | median 3.9 min |
| macOS pool | 1501 minutes used, 41.9% of the available 5 slots, **19.4% spent on runs that ended without a verdict** (cancelled or failed) |

`replay` re-dispatches that same recorded workload under each proposed policy
(FIFO, macOS pool 5, Ubuntu pool 20):

| policy | run completion median | p90 | max | macOS queue p90 |
| --- | --- | --- | --- | --- |
| today, no per-run cap | 5.3 | 15.0 | 42.9 | 10.0 |
| `max-parallel: 2` on the whole matrix | 16.4 | 27.3 | 48.7 | 5.0 |
| 2 macOS jobs per run | 8.6 | 22.0 | 48.3 | 6.6 |
| 2 macOS jobs per run + macOS after Linux | 11.3 | 24.9 | 51.1 | 6.6 |

Every cap halves the queue and lengthens the run more than it shortens the wait,
including the worst case: the wait moves from the queue into the run, because
`max-parallel` is a cap on one matrix, not on the pool — "a maximum of two jobs
at a time, even if there are runners available to run all six jobs at once"
(GitHub Docs, *Running variations of jobs in a workflow*, read 20/10/2026).

Gating macOS behind the Linux verdict does not pay either: of the 25 cancelled
runs that had already started macOS, only 3 would have avoided macOS entirely
(cancellation arrives at median 4.9 min, the Linux half finishes at median
2.9 min), saving 16 of 319 wasted minutes while delaying every macOS job.

## Decision

Do not add `strategy.max-parallel` and do not serialize macOS behind Linux. The
matrix keeps its eight parallel jobs; the required check names, the matrix
entries and every test stay exactly as branch protection expects them.

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
