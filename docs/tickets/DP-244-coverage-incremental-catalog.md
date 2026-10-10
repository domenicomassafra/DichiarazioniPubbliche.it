# DP-244 — Source coverage inventory, version refresh and incremental catalog

Status: IN PROGRESS
Milestone: M7 — stable v1 launch
Depends on: DP-209, DP-213, DP-215, DP-511

## Problem

A permanent corpus needs source-specific completeness statements and refresh. A fixed historic person still gains new archival scans/transcripts; a monitored active public figure or source may change daily. Re-fetching identical body and re-running models every day wastes budget; a new source may supersede an old quotation. A missing item is not evidence the person never spoke.

## Outcome

A versioned private source/collection catalog displays exactly **what source families and time windows were attempted, accepted, incomplete, blocked, stale or changed**, with conditional reobservations and replayable delta proposals for D's future economical background scheduler; sanitized freshness/coverage information can later inform C's public readers.

## Traceability & constraints

R10/R23/R27/R33; Q09–Q20. Continuity for followed people/topics/sources with allowance for new events; no virality-only selection, global completeness claim, inferred intention or person ranking.

## Scope

Family/format/language/time/subject coverage unit, official-source-first candidates, observed version/hash/ETag/Last-Modified where reliable, `source_revalidation` deltas, derivation dedup, change significance, failure/rights status, work budget, retry and provenance. Distinguish stable historical backfill from current source subscription; formalize new digitization and manual correction triggers. Expose bounded `UNKNOWN`, `NOT_COVERED`, `PARTIAL`, `STALE`, `CURRENT_WITHIN_OBSERVED_SCOPE` vocabulary; no fabricated completeness ratio.

## Non-goals

Unlimited crawling or subscription, automatic publication, all-world corpus assurance, installing a scheduler or payment provider, changing a model to fit costs.

## Dependencies and sequencing

Hard existing discovery, Coverage Needs, evidence roles, revalidation; soft D scheduler/cap/health, DP-237 version locator, DP-243 historical collections, B holds/updates and C freshness display. Permissions and feed robots/rates are external source-family inputs.

## Acceptance criteria


- [ ] `AC-244.1`: Inventory describes actual source families/interval/language/format, last successful observation, failed/blocked attempts, expected content class and unknown gaps, with provenance and versioned decision reasons.
- [ ] `AC-244.2`: Re-observing unchanged permitted source produces cheap idempotent no-op; a materially changed version generates new immutable Capture/reanalysis/coverage work (after rights/relevance guards).
- [ ] `AC-244.3`: Expired/denied source permit, outage, retried fetch, HTTP conditional inconclusive and missing catalog item remain distinct and do not become false full coverage or free-cost success.
- [ ] `AC-244.4`: Backfill and subscribed incremental changes report separate work/cost counts; priority honors followed source/person/topic continuity plus newly relevant events with explicit fairness and source-scope criteria, no political scoring.
- [ ] `AC-244.5`: New official archival digitization, corrected transcript and missing original reopening show exact affected record/locator versions, without using later evidence to judge prior-date knowledge.
- [ ] `AC-244.6`: On MiniPC a frozen small permitted source set yields reproducible baseline/unchanged/changed/outage receipts and a sanitized public-ready freshness descriptor containing zero private membership/rights notes.

## Validation / proof

Bounded online source-family acceptance **in later implementation only**, independent source version hashes before/after, run/attempt ledger, conditional fetch negative tests and MiniPC DB counters; D cost-by-stage receipt and B correction trigger readback. No guessed total-universe coverage denominator.

## Documentation, data, and migration impact

Extend Discovery/Source Health/Coverage Need/DP-511 version store rather than standalone catalog DB. Do not activate timers; D governs scheduled execution and cap.

## Completion receipt

Historical planning-only note, superseded solely for the local slice below.

## 2026-10-11 — Bounded observed-coverage catalog (partial)

Added opt-in `coverage_catalog_v1.py` with 10 focused synthetic tests PASS.
The private read model records precise source family, format, language,
scope/time, historical backfill versus incremental subscription, separate
last attempted/last **successful** observation, reviewed enumeration
completeness *only within the declared bounded source scope*, rights status
and exact source version/hash. The five explicit states distinguish
`NOT_COVERED`, `UNKNOWN`, `PARTIAL`, `STALE` and
`CURRENT_WITHIN_OBSERVED_SCOPE`; changed hashes trigger **only** a new
review proposal when downstream cost/rights/capability are ready and keep
current public derived views stale until reanalysis. Unchanged source
versions, retries and outages do not invent new jobs or general coverage.
An optional redacted freshness descriptor omits private collection/source
identities and corpus membership. No runtime watcher/timer/provider/DB has
been activated. **All original AC-244.1–.6 remain unchecked** pending
authenticated rights and source receipts, persistent idempotent scheduling,
freshness invalidation of actual readers and MiniPC permitted-source proof.
