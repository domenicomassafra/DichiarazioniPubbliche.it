# DP-205 — Daily/full-source polling with bounded coverage

Status: DONE
Milestone: M2  
Depends on: M0 and the existing source registry, scheduler, PostgreSQL queue, and source-health contracts

## Problem

The current scheduler is a five-minute one-shot timer. `run_registry()` iterates the
configured entries, but `discover_source()` and `poll_source()` support only
`youtube_channel`; an entry such as `public_creator_accounts` is reported as
`SKIPPED_UNSUPPORTED`. There is no explicit daily full-source contract, no durable
run-level receipt, and no single acceptance bound that covers a sweep across all
registered sources. Repeated runs can discover the same material again and can make
operational cost and coverage difficult to audit.

A daily scan must be an orchestration mode, not an excuse to crawl the open web or
materialize downstream work while a provider is unavailable. The existing five-minute
source-due service remains the normal cadence for eligible sources.

## Outcome

Add a separately scheduled, deterministic full-source mode that:

- visits every entry in the configured source registry once per UTC day;
- still honors each source's `poll_minutes`, failure backoff, and content policy;
- bounds discovery and enqueue work with explicit per-source, per-run, and daily cost
  limits;
- makes a completed run and each source result replayable and auditable;
- is idempotent at content, locator, and job boundaries after a crash or repeated run;
- continues with unrelated sources when one source is unsupported or unavailable;
- leaves expensive downstream work absent or `BLOCKED` when its capability or cost
  gate is unavailable; and
- emits only private, bounded health and receipt data.

The mode must not make a claim, finding, evidence approval, or publication decision.

## Dependencies and authority

The canonical behavior comes from [PRODUCT.md](../../PRODUCT.md),
[CONTEXT.md](../../CONTEXT.md), [ARCHITECTURE.md](../../ARCHITECTURE.md), and the M2
graph in [PLAN.md](../../PLAN.md). In particular, use the existing `Source`,
`Content`, `Locator`, `Processing Job`, `Provider Receipt`, and `Source Health`
concepts. DP-201 through DP-204 remain externally blocked; this ticket must not
materialize their child jobs or use a model/provider substitution to make the scan
look successful.

Relevant existing seams are `poc/dichiarazioni_pubbliche/source_watcher.py`,
`poc/dichiarazioni_pubbliche/scheduler.py`, `poc/dichiarazioni_pubbliche/scheduler_daemon.py`,
`poc/dichiarazioni_pubbliche/queue_runtime.py`, `db/schema.v0.sql`,
`db/job_queue.v0.sql`, and the source-poll systemd units under `deploy/systemd/`.

## Scope

### 1. Full-source run contract

- Keep the existing source-due service for frequent per-source polling.
- Add a `--full-source` mode to `scheduler_daemon` and the separate
  `deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.service` and
  `deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.timer` units that invoke it. The daily
  mode iterates the complete current registry, not the internet and not a dynamically
  discovered source list.
- A run is identified by mode, UTC date, and a hash of the effective registry and
  bounded policy. Repeating the same completed run returns
  `SKIPPED_ALREADY_COMPLETED` without discovery or enqueue.
- `full-source` does not bypass per-source due time or failure backoff. An explicit
  operator force flag may bypass due time for a bounded diagnostic run, but it must
  be separately labelled and still obey all work and cost caps.
- Continue after an individual source failure. Return a non-zero service result if
  any source failed, while recording healthy results for other sources.
- Treat an unsupported source kind as an explicit blocked/unsupported result, never as
  a successful empty poll.

### 2. Durable run and per-source receipts

Add only the operational run records needed to prove daily coverage. The ordered
migration under `db/migrations/` must add a `source_poll_run` record and a
`source_poll_run_source` child record. Each record must contain an ID, mode, run date,
effective config hash, status, start/completion timestamps, bounded counters, and a
sanitized error category. The child record must identify the source and its result.

The source result and its successful enqueue operations must commit atomically. A
process crash may repeat a discovery fetch, but it must not create a second
`content_item`, `content_locator`, or `processing_job` for the same deterministic
identity. The run receipt must never contain credentials, cookies, raw response
bodies, transcript text, or unsanitized upstream errors.

### 3. Bounds and budget gates

Use explicit configuration with hard upper bounds:

- maximum discovered items per source per run: 20;
- maximum new processing jobs per full-source run: 20;
- maximum full-source runs per source per UTC day: 1, unless an operator-authorized
  diagnostic run is labelled as such;
- preserve the existing global USD 5/day, USD 1/source/day, and USD 0.25/job
  circuit breakers;
- preserve the existing discovery response limit of 4 MiB, timeout, HTTPS, DNS,
  redirect, and size checks.

If a budget is reached, discovery and safe content/locator persistence may continue,
but no new expensive job is enqueued. The outcome must say `BUDGET_BLOCKED`; it must
not retry until the cap or fabricate a downstream result. Unsupported or blocked
downstream capabilities must not be expanded into child jobs.

### 4. Observability

Extend the private health output with run ID, mode, per-source status, counts, and
sanitized blocker categories. A run summary must make it possible to answer which
sources were visited, which were not due, which were unsupported, which were
budget-blocked, and which jobs were duplicate jobs. Do not change the public schema
or publish operational receipts.

## Non-goals

- general-purpose crawling, sitemap discovery, or an unbounded web search;
- adding a new source family (that is DP-206);
- downloading or probing media in the scheduler process;
- changing transcript, claim, evidence, verification, or publication semantics;
- switching model/provider to hide DP-201 or DP-204;
- creating child jobs when the downstream capability is unavailable;
- selecting sources for political coverage or adding a person/source ranking; and
- introducing Kafka, Kubernetes, a graph database, or a new queue service.

## Acceptance criteria

- **AC-205.1 — Full registry coverage:** Given a registry containing at least three
  entries, one normal full-source run emits a result for every entry, including an
  unsupported entry, and the run summary has no silent omissions.
- **AC-205.2 — Daily identity:** Repeating a completed run with the same UTC date,
  mode, and effective config hash performs no discovery and enqueues no job; a
  changed config hash creates a distinct auditable run.
- **AC-205.3 — Due and backoff:** A source that is not due is reported as
  `SKIPPED_NOT_DUE`; a source with consecutive failures follows the existing
  exponential backoff, and a full-source run does not erase that state.
- **AC-205.4 — Bounded work:** A fixture with more than 20 items and more than 20
  eligible jobs proves the per-source and per-run caps. The receipt records the
  omitted counts without dropping source health.
- **AC-205.5 — Idempotent replay:** Running the same fixture twice yields the same
  content and locator IDs, no additional jobs, and a duplicate-job count. A crash
  simulation after a source result commits has the same no-duplicate outcome.
- **AC-205.6 — Budget behavior:** At or above the global, source, or job cap, content
  discovery/upsert remains safe and new jobs are counted as blocked/deferred; no
  provider call is made by the scheduler.
- **AC-205.7 — Failure isolation:** A timeout, malformed response, SSRF rejection, or
  unsupported adapter marks only that source as failed/blocked; unrelated sources
  still produce their normal result and the service exits non-zero when required.
- **AC-205.8 — Existing contracts:** The existing five-minute source-due behavior,
  deterministic job IDs, source health transitions, queue leases, and private
  transcript/media boundaries remain unchanged.
- **AC-205.9 — Security:** The implementation reuses HTTPS/DNS/redirect/size checks,
  stores no secrets or raw bodies, and emits no public operational data.
- **AC-205.10 — Regression proof:** Focused scheduler/source tests, the full test
  suite, deterministic benchmark, compile check, and `git diff --check` pass.

## Test-first seams

Use the public seams, not private helper implementation details:

1. `scheduler_daemon.run_registry()` and `poll_source()` for due, bound, replay,
   budget, and failure-isolation behavior.
2. The adapter-facing `discover_source()` contract for normalized
   `DiscoveredContent` values and bounded responses.
3. The PostgreSQL boundary for transactional run/source receipts, deterministic
   content/locator identity, and duplicate enqueue behavior.
4. The systemd command contract for normal versus `--full-source` invocation.

Write one red test and one minimal implementation slice at a time. At minimum,
cover all-registry iteration, same-day replay, source backoff, a 21-item fixture,
a 21-job fixture, budget exhaustion, unsupported source kind, malformed feed, SSRF,
and crash-after-commit recovery. Use a fake store for unit tests and an isolated
canary database for transaction tests; do not mutate production data to obtain a
pass.

## Runtime proof

Development proof is not completion proof. On the MiniPC deployment mirror:

1. synchronize the implementation and apply the additive migration with
   `ON_ERROR_STOP` in an isolated canary schema/database;
2. run the focused scheduler tests and the repository checks:

   ```text
   python3 -m compileall -q poc tests
   PYTHONPATH=poc python3 -m unittest discover -s tests -v
   PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
   git diff --check
   ```

3. run the daily service twice against the same effective registry and verify the
   second result is `SKIPPED_ALREADY_COMPLETED`, with unchanged content/locator/job
   counts;
4. run a bounded fixture with more than the configured item/job limits and verify
   the recorded caps and budget-blocked counts;
5. inspect the private health digest and run/source receipts for complete source
   outcomes without secrets or raw response bodies; and
6. run one failure injection against a canary source and verify unrelated source
   results remain valid and the service reports the intended non-zero status.

Record the MiniPC commit/mirror hash, migration result, run IDs, counters, queue
state, and service exit codes in the completion receipt. A Mac-only result is not
runtime proof.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the run as incomplete if any of these occurs:

- the effective source registry or its allowlist is unavailable or ambiguous;
- the database migration or transaction cannot preserve run/source idempotence;
- a source requires credentials, browser cookies, or an unapproved provider path;
- HTTPS/DNS/redirect/size or ToS policy cannot be enforced;
- the registry would exceed the declared source bound;
- a daily run cannot report unsupported/degraded sources distinctly;
- MiniPC runtime proof is unavailable; or
- another worker has claimed the same ticket/file and would create a collision.

A provider outage is not permission to retry unboundedly, switch providers, or
claim a clean source poll. The source may be `DEGRADED`/`FAILED`, and downstream
work remains blocked.

## Documentation, data, and migration impact

- Update `docs/22-runtime-scheduler-and-omniroute-canary.md` with the final daily
  timer, run receipt, bounds, and MiniPC receipt.
- Update the source-policy/config documentation if the mode introduces a new
  machine-readable field.
- Add only the additive run/receipt migration under `db/migrations/`; do not alter
  public schema or operational transcript/media tables.
- Keep the public read model independent of this run ledger.

## Completion receipt

To be filled only after implementation and proof:

- implementation commit and MiniPC mirror hash:
- migration name and idempotent replay result:
- full-source run IDs and effective config hashes:
- per-source status/counts and queue before/after counts:
- focused/full test and benchmark results:
- MiniPC service exit codes and health-digest path:
- residual blocked conditions, if any:

## Recorded implementation proof

- `--full-source` now creates deterministic daily run/source receipts, shares the hard
  20-job cap across sources, preserves due/backoff behavior, and isolates source failure.
- The first MiniPC run visited both configured sources and recorded
  `SKIPPED_NOT_DUE` for Pulp plus `SKIPPED_UNSUPPORTED` for the pre-DP-206 creator source.
- An immediate replay returned `SKIPPED_ALREADY_COMPLETED` with zero new discovery or
  enqueue work.
- Daily systemd service/timer is installed and active; focused scheduler tests, the full
  234-test suite, compileall, benchmark 5/5, and `git diff --check` passed.
