# DP-244 — Source coverage inventory, version refresh and incremental catalog

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
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

**Milestone reconciliation (2026-10-11): M2.** The scoped source/version coverage inventory supports private discovery and pipeline readiness, based on M2 discovery and suitability contracts DP-209/213/215. Later periodic execution and cost governance remain in M5 (DP-515), while accepted historical scale is separately gated in M7 (DP-243/516). An offline coverage proposal is not a source canary or launch receipt.

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

### 2026-10-11 — Replay/scope and rights fail-closed follow-up (partial)

Five additional focused regressions reproduced concrete false status/delta or
identity behavior before repair (RED) and now pass (15/15 total GREEN):

- A later revoked or blocked rights attempt retains `UNKNOWN` / no review work,
  even when an earlier permitted source hash differs from the derived baseline.
- A latest outage preserves its unverified-attempt reason and no child work; a
  previous changed observation cannot hide the latest failed fetch.
- Two successful, differing body hashes require `STALE` and conditional
  `REVIEW_CHANGED_SOURCE` when no reviewed derived baseline is supplied. A
  verified baseline matching the latest hash restores scoped freshness; a
  version-label change with identical bytes stays a cheap no-op.
- Observations now require a `scope_fingerprint` computed from the exact
  `CoverageUnit` source, collection, interval, language, format, class, policy
  and mode. Cross-interval, collection, language or mode receipt reuse fails
  `COVERAGE_MIXED_SCOPE`. This is an input-lineage guard, not authentication of
  an external enumerator or source permission.
- An observation-ledger fingerprint is stable across evaluation clock changes
  and incorporates actual observation receipt identity and staleness policy.
  Time passing can still change the separately computed freshness decision.

Proof: `PYTHONPATH=poc python3 -m unittest tests.test_dp244_coverage_catalog -v`
**15/15 PASS**; targeted `compileall` and `git diff --check` PASS. This is a
local source-only contract improvement. No scheduler, crawler, persistent
idempotent work ledger, rights approval, source canary, MiniPC runtime, or public
release was exercised. Original **AC-244.1–.6 remain unchecked**.

### 2026-10-13 — No currentness claim before the observed interval has ended

An independent source-only regression showed that a `CoverageUnit` with an
`interval_end` **after** its last independently provided successful observation
could return `CURRENT_WITHIN_OBSERVED_SCOPE` merely because its enumeration
flag was true. The committed test fixture evaluates a bounded incremental
subscription on **2026-10-11 at 17:00 UTC** with an interval ending
**2026-10-13 at 17:00 UTC**: an already-complete result could not possibly
attest the future portion of the interval. A separate local pre-fix
reproduction also used a November-ended interval, with the same defect.

For an otherwise eligible, fresh, unchanged observation, the
`build_source_coverage` read model now returns `PARTIAL` with the explicit
`COVERAGE_INTERVAL_NOT_YET_OBSERVED` reason and a conditional gap-review
proposal until an externally supplied authorized successful observation is at
or after that unit's exact interval end. Existing higher-priority revocation,
outage, stale-reanalysis and missing-permission states continue to take
precedence. None exposes a false public-currentness descriptor for the
incomplete interval, and this read model never authorizes dispatch.
The test proves the same scope can become current once a later eligible
observation actually exists. The future timestamp is an isolated test fixture,
not a source observation manufactured in production.

Proof: `test_future_scope_end_cannot_be_attested_complete_by_earlier_observation`
was **RED** (`CURRENT_WITHIN_OBSERVED_SCOPE` vs expected `PARTIAL`), then
**GREEN**; full `tests.test_dp244_coverage_catalog` suite **16/16 PASS**, source
`compileall` and `git diff --check` PASS. No source was fetched, permission
granted, watch enabled, DB modified or public site updated. All AC-244.1–.6
remain OPEN until the separately required real rights, persistence, runtime
and MiniPC evidence is available.


## Owner round aggiuntivo — 13 ottobre 2026

Q9 breve indicazione della copertura/lacune/freshness nelle pagine Persona/Tema interessate, dettagli raggiungibili. Non convertire campione osservato in copertura globale né dati non acquisiti in assenza di dichiarazioni.

Decisione/ricerca futura registrata: nessuna implementazione o acceptance nuova, status e criteri originali invariati.

### 2026-10-14 — First changed source observation without a reviewed baseline (source-only partial)

The bounded reconciler had a false-currentness branch: a first authorized,
completely enumerated observation explicitly marked `CHANGED`, with no reviewed
derived `baseline_sha256` and no earlier in-scope success to compare, produced
`CURRENT_WITHIN_OBSERVED_SCOPE` and allowed the opt-in public freshness descriptor.
The independently supplied changed-source status already signals a prior version
transition, but it did not establish that public derivations were refreshed.

`test_first_changed_observation_without_derived_baseline_cannot_claim_public_freshness`
reproduced **RED** (`CURRENT_WITHIN_OBSERVED_SCOPE` instead of `STALE`), then **GREEN**:
the read model now keeps that first `CHANGED` body `STALE`, with the normal
capability/budget/rights-gated `REVIEW_CHANGED_SOURCE` proposal and no public
freshness descriptor. A later `UNCHANGED` re-observation of the same bytes does
not silently clear the hold. Explicit reviewed baseline matching the new body
restores scoped currentness; a first complete `UNCHANGED` observation remains
eligible; a subsequent metadata/version-label change with an identical body
remains an economical no-op. Dispatch remains unauthorized in all cases.

Verification: **17/17** `tests.test_dp244_coverage_catalog` pass and **93/93**
focused plus neighboring coverage/revalidation/watch tests pass; source/test
`compileall`, targeted Ruff and `git diff --check` pass. No production data,
fetch, provider, scheduler, MiniPC, reader or publication gate was exercised.
The original **AC-244.1–.6 remain OPEN** pending authenticated source receipts,
persistent ledger/cost evidence and real permitted-source/runtime proof.

### 2026-10-15 — Freshness-policy replay authority cannot be widened

The private coverage scope fingerprint bound interval, mode, language, source,
collection and policy *version*, but omitted the actual
`CoverageUnit.max_staleness_seconds` value. A caller could replay an
unchanged observation from a 60-second freshness window using a new unit
with a 365-day window **without changing the purported receipt's scope
fingerprint**. The source's actual last observation was already stale;
the widened policy incorrectly returned `CURRENT_WITHIN_OBSERVED_SCOPE`.
This is a real receipt-scope integrity bug, not a remote-source fixture
that supplies independent license or freshness authority.

The unit's scoped fingerprint now includes the exact integer staleness
allowance, so a receipt bound to one window raises
`COVERAGE_MIXED_SCOPE` when reused under another. Previously issued
opt-in fixture scope fingerprints do not silently upgrade: they must be
independently re-attested under the new policy. Existing exact-scope
idempotency, rights blocks, outage precedence, source-change holds and
non-publication guarantees are unchanged.

**RED:** `test_longer_staleness_policy_cannot_reuse_short_window_source_receipt`
failed because no `ValueError` was raised. **GREEN:** the guard now
rejects the scope swap, while the genuine short scope reports
`STALE`. The full focused coverage catalog suite passes **18/18**;
Ruff check, targeted compileall and `git diff --check` PASS.
Technical issue DP-521 records the bounded source-only closure
separately. Original **DP-244 AC-244.1–.6 remain OPEN /
IN PROGRESS** pending authenticated source observations and rights,
durable store/conditional requests, cost and MiniPC permitted canary.
No source provider or production runtime was invoked.
