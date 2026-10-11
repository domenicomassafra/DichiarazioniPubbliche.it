# DP-515 — Economical incremental source monitoring with coverage and safe backoff

Status: IN PROGRESS
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-209, DP-210, DP-211, DP-511, DP-512, DP-514

## Problem
 Source polling exists, but permanent historical corpus and public-interest changes require adaptive, economical monitoring. Reprocessing unchanged content daily would exhaust quotas; missing/disabled sources, parser drift and inaccessible upstream material must not be misrepresented as full coverage.

## Outcome
 Versioned opt-in watch policies by source, Person, Topic and relevant Event, with per-family cadence and conditional fetch/metadata-first stages. New/amended/removed source versions enqueue only bounded, rights-authorized affected work. An auditable digest shows last successful observation, attempted checks, coverage basis/unknown gaps and source health. Ongoing monitoring is different from initial backfill.

## Traceability & constraints
 R24/R25/R32/R33/R38, Q10. Discovery by continuity AND new significant events, not viral/political rankings. No autonomous new full-site crawl, private-life mining, unsupported generic model URL guesses or publishing discoveries directly.

## Scope
 Extend existing source_watcher/scheduler/coverage_needs/queue_runtime/DP-511. Use configured source seeds/identities/robots/access policy, ETag/Last-Modified when supported, content-hash/version checks, source-family lineage/dedup and explicit event relevance rules. Work item identity includes source/locator/version/policy and stage; repeated unchanged check is cheap metadata, not full LLM/ASR. Bounded source/person/topic discovery permits a new person through standard identity/rights acceptance; relevance cannot be an ideological score. Separate high-priority correction/rights/supersession reanalysis from regular polling and paused historical backfill, with explicit cost quotas and fairness. Retry exponential backoff plus jitter, source-level outage circuit breaker, cap pause, lease expiration and dead-letter/manual concise exception queue. Enqueue downstream child only when capability and rights/cost guards are READY; failure is isolated per source. Public freshness is based on last successful *observed/approved* update with corpus/cutoff/version and coverage limitations, never “the whole world is up to date.”

## Non-goals
 Guaranteed real-time social monitoring, complete web coverage, new Kafka/Kubernetes/crawler cluster, daily re-verification of unchanged entire corpus, person ranking.

## Dependencies and sequencing
 A defines source-family coverage, B defines exactly which change invalidates findings/corrected statements, C consumes sanitized freshness metadata. DP-514 budget and DP-511 invalidation are hard gates. Initial mini-corpus full path must be accepted before scaling recurring data.

## Acceptance criteria

- [ ] `AC-515.1`: Repeated unchanged ETag/hash source poll creates no duplicate Content/Capture or expensive child job; receipts record checked vs changed vs unavailable.
- [ ] `AC-515.2`: Changed version/new primary source and withdrawn/expired rights trigger bounded, source-linked review/reanalysis and public freshness/hold updates with hashes, idempotent restarts.
- [ ] `AC-515.3`: Broken provider, source 429/timeout, bad conditional response, source-specific license change or budget exhaustion blocks only affected work and never fabricates a fresh check.
- [ ] `AC-515.4`: Coverage rows distinguish watched/not watched, last attempted/successful date, source families, known gaps and corpus cutoff; same-person chronology stays ordered even for late discovered material.
- [ ] `AC-515.5`: Quota reset/backoff/lease/replay, two workers on same changed Content, and no-child-without-capability tests pass.
- [ ] `AC-515.6`: Private daily health ledger gives counts of attempts, new/modified/unchanged, blocked, costs, coverage, freshness and correction lag without leaking private content.
- [ ] `AC-515.7`: Real MiniPC bounded source/candidate replay and public cache/readback are accepted before enabling unattended production watch.

## Validation / proof
 Local fake feed with 200 unchanged/304/429/new/amended/withdrawn, isolated queue restarts and cost-cap tests; one genuinely approved source-family MiniPC canary later. Deterministic expected number of downstream jobs; no live provider/background schedule now.

## Documentation, data, and migration impact
 Reuse source registry/health, discovery run, coverage needs and operation ledger, adding only conditional-validator/version/watch state where absent; private watch rule + public safe freshness projection. Rollback pauses the watcher, preserves source history, leaves unrelated public readers available.

## Completion receipt
Not implemented; planning only. Future policy hash, source-version before/after, job/no-child counts, MiniPC digest and public freshness/projection fingerprints.

## 2026-10-11 — First implementation slice

Source-only commit `3cb5d93` adds opt-in, disabled-by-default
`incremental_source_watch.py` plus `test_dp515_incremental_watch.py`.
Seventeen focused tests and 50 related source/cost/regression tests pass.
The bounded pure policy evaluates source version/hash/ETag, conditional
304/no-change, changed source, rate-limit/outage backoff, private attempted
versus last-successful timestamps and rights/capability/cost before proposing
any child. No actual fetch, DB store, scheduler or provider was run.

All original AC are still unchecked. The real watcher remains **NO-GO**
until authenticated permission/quota records, atomic durable state/lease/CAS
with job admission, downstream DP-511 revoke/reanalysis, source-family
MiniPC proof, operator authorization and cost measurement are accepted.

## 2026-10-11 — Attempt replay guard regression

Local source-only review found that a previously authorized `WatchPlan` could
be altered before reconciliation: changing its attempt ID to the previous ID,
or moving its timestamp back before a recorded attempt/backoff window, bypassed
the admission checks. A naive timestamp instead raised `TypeError`. This could
corrupt the private attempted-check ledger or admit a replay on a stale attempt.

`reconcile_watch_observation` now revalidates attempt ID, aware timestamp,
monotonic ordering and source backoff against the original state before
reconciling any supplied HTTP result. Regression
`test_forged_attempt_identity_and_clock_cannot_replay_or_regress_state` in
`tests/test_dp515_incremental_watch.py` was **RED before the fix** (4 assertion
failures, 1 `TypeError`) and **GREEN after** (five adversarial variants).
All 18 DP-515 and 15 DP-516 tests pass locally; Python compile and
`git diff --check` pass. Tests use only synthetic observations and receipts.

This local hardening does not authorize polling, supply a durable transaction,
prove a real source/cost/rights receipt or satisfy the MiniPC/public readback.
DP-515 remains **IN PROGRESS** with all AC unchecked and unattended monitoring
**NO-GO**.
