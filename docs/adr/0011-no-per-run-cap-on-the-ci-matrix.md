# ADR 0011 — Reduce macOS service time, not required coverage

Status: Proposed (pending hosted measurement and integration)
Date: 2026-10-20
Supersedes: the original unvalidated no-change decision in PR #235
Tracker: https://github.com/domenicomassafra/controlcenter/issues/418

## Decision

Keep all eight real backend OS/Python combinations, their exact required names,
`fail-fast: false`, and the existing PR/ref cancellation policy. Do not add a
matrix cap based on an uncalibrated replay. Instead move the OS-independent
`check_contributor_acceptance.py` invocation from each backend leg to the already
required `repository contract` job. That job runs the **complete** entry point,
not a subset; its four previously duplicated static commands are subsumed by it.
Keep its additional privacy-inventory check. The detached clean-clone job retains
its independent contributor acceptance to prove the committed clone contract.

Every backend leg still builds its own package, installs/smokes a fresh venv,
compiles, runs the full unittest suite, installs/tests the optional account extra,
runs its deterministic benchmark, checks whitespace and rejects a dirty tree.
No required job is skipped, made optional, renamed, or converted to a fake pass.
No paths filter, self-hosted runner, new dependency or paid service is introduced.

This removes redundant work from a measured scarce resource. In PR #235's
original hosted run `39444175052`, the static acceptance step alone occupied
72/73/73/74 seconds of four macOS allocations. It has no matrix input. The
backend suite and interpreter/OS-specific checks remain on **all** versions.
Hosted before/after evidence, exact HEAD and installation belong in #418 and
PR #235; this ADR is not an acceptance receipt.

## Why the original measurement was withdrawn

The original 111/117-run tables and percentages are invalid and must not be used.
Three independent review regressions were red on `171c827`: a completed but
never assigned cancellation was counted as execution; replay included that
nonexistent workload; a matrix cap throttled independent workflow jobs.

Accounting now requires evidence of runner assignment (`runner_id`, runner name
or nonempty steps) as well as a non-queued start. Queue is **job**
`started_at - created_at`, never run creation; missing timestamps are unknown,
not zero. Completed run duration is last job `completed_at - run.created_at`,
never `run.updated_at`. In-flight runs do not supply final duration. Pool minutes
exclude never-executed jobs; "without verdict" means measured executions in a
run whose conclusion is cancelled/failure/timed_out/startup_failure, including
its successful constituent jobs. A sample's pool utilisation is only the share
observed for that export, not a measurement of the whole account.

The replay lives separately in `tools/ci_matrix_replay.py`, caps only
`backend-minimal` (identified by the workflow's `backend …` naming contract),
keeps independent jobs independent, retains job readiness times and removes
cancelled runs at the last recorded job completion. That is an observed terminal
cutoff, **not** the cancellation request instant, which REST does not expose.
Cancelled runs are not reported as completed verdicts. Legacy replay inputs
named `seconds` actually contained minutes; new exports use `minutes` explicitly.

The model is exploratory. It omits unexecuted work, unobserved account/repository
contention, retries and unknown dependency graphs. It cannot prove a policy's
before/after improvement. Holdout cohort B below exposes the mismatch: observed
mean run completion is 38.91 min while isolated FIFO replay gives 6.75 min;
with matrix cap 2 that model gives 14.11 min. That is reason **not to infer a
causal scheduler decision**, rather than evidence that every possible cap loses.

## Reproducible REST export

These are public Actions records, not fixtures invented to justify the decision.
Run IDs are fixed; fetch each payload once, retain collection time and run attempt,
and do not merge partial job snapshots with final run states. `jobs?filter=latest`
selects the current attempt; historical reruns need the matching attempt endpoint.
The listed records had 14 jobs, so one `per_page=100` page is complete.

```bash
repo=domenicomassafra/DichiarazioniPubbliche.it
export_dir=/tmp/dp418-baseline
mkdir -p "$export_dir"
ids=(39434814480 39435013235 39435472686 39436013073 39436083883)
for id in "${ids[@]}"; do
  gh api "repos/$repo/actions/runs/$id" > "$export_dir/run-$id.json"
  gh api "repos/$repo/actions/runs/$id/jobs?per_page=100&filter=latest" \
    > "$export_dir/jobs-$id.json"
done
jq -s '.' "$export_dir"/run-*.json > "$export_dir/runs.json"
python3 tools/ci_matrix_capacity.py report --export "$export_dir" --json
python3 tools/ci_matrix_capacity.py replay --export "$export_dir" --max-parallel 2 --json
```

Cohort A: the five IDs above (PR #226/#227/#229/#230/#231, overlapping at
14:06 UTC on 20 October). Corrected report: 20 executed macOS jobs, mean queue
16.48 min, mean execution 4.085 min, five-run mean completion 37.9367 min.

Cohort B, separate export: `39448052187 39447300876 39448274656 39448503398
39448717385` (PR #244–#248, overlapping at 15:28:30 UTC). Corrected report:
20 executed macOS jobs, mean queue 21.3375 min, mean execution 3.92583 min,
five-run mean completion 38.9133 min. Both cohorts precede any installed fix;
they are **not** a before/after pair.

Real never-executed counterexample: run `39439000195`, jobs `118683584137`,
`118683584270`, `118683584288`, `118683584414`; all runner_id=0, steps=[],
started=created at 14:25:08Z, completed at 14:35:53Z. Correct accounting: zero
macOS starts, zero macOS execution minutes, zero macOS replay jobs.

## Evidence and reuse (consulted 20 October 2026)

* [GitHub matrix scope and max-parallel](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations).
* [Required checks and dependency failures](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
* [Native workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), already installed by #413.
* [Actions limits](https://docs.github.com/en/actions/reference/limits): five standard hosted macOS jobs is the documented plan limit; repository REST inventory has zero self-hosted runners. Neither proves the account quota endpoint was read.
* [ITK #6074](https://github.com/InsightSoftwareConsortium/ITK/issues/6074), opened 16 April and updated 23 September 2026: real five-slot cross-repository contention and pressure reduction options, not a benchmark of this repository.

Reuse is the existing native workflow and repository-owned contributor checker;
no donor code or extra package is adopted. `gh` is `cli/cli` (MIT); the already
used `actions/setup-python@v6` is MIT, observed commit
`ece7cb06caefa5fff74198d8649806c4678c61a1`. Third-party sources remain untouched.
