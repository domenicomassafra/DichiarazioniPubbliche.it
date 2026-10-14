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

## 2026-10-11 — Future Last-Modified poisoning guard

An adversarial offline HTTP fixture exposed a real conditional-watch freshness
defect. A `200` response observed in October 2026 with a `Last-Modified`
validator dated January 2035 was incorrectly accepted as `UNCHANGED` or
`CHANGED`, recording a false successful check and saving that future validator
for subsequent `If-Modified-Since` polls. Such a conditional request could
mask a genuine intervening amendment. Persisted legacy state could also emit
the future validator despite its earlier successful observation, and an
in-memory `WatchPlan` admitted in 2036 could be altered back to 2026 before
reconciliation if its state did not yet contain a successful timestamp.

The pure source watcher now fails the response as
`UNAVAILABLE/LAST_MODIFIED_IN_FUTURE`, preserving old version/hash/validators,
the previous success timestamp and zero child proposals. Persisted state whose
validator is later than its last successful observation is rejected, and both
planning and reconciliation reject an attempted time earlier than the cached
validator. Error path retains the existing bounded source backoff, without
assuming HTTP success, triggering a fetch or authorizing publication.

The real regression was RED before implementation (two false success
dispositions and one accepted poisoned state); an additional forged-plan
reconciliation variant was RED after the first fix and GREEN after sealing the
reconciliation seam. Final targeted DP-515/DP-516 regression: **37/37 PASS**;
source/test compileall and `git diff --check` pass. All observations and
timestamps are synthetic; no provider, live source, MiniPC or runtime state
was accessed. AC-515.1–515.7 remain unchecked pending durable admission,
rights/cost/lease authority, public revocation/cache proof and MiniPC canary.

## 2026-10-11 — Private daily source-health/coverage digest (source-only)

The initial watcher operated on individual poll decisions and did not provide
the operator-facing, daily coverage/health read model in AC-515.4/6. A new
`build_private_watch_daily_digest(day, as_of, snapshots, committed_attempts)`
pure function accepts a bounded UTC-day set of *externally persisted* source
snapshots and attempt readbacks. It produces a deterministic private digest
with source family/corpus cutoff, watched/disabled/blocked state, per-source
attempted vs last successfully observed times, backoff/failure health, and
explicit known gaps; totals separately count NEW, MODIFIED, UNCHANGED,
UNAVAILABLE, BLOCKED and HTTP 429 checks. Metered micro-EUR cost is aggregated
only when an actual cost measurement is supplied; missing measurements remain
an explicit unknown-attempt count, never an invented zero or cost estimate.

Every counted attempt replays its source-bound admission plan and observation
decision, verifies status and source/corpus/policy lineage, unique attempt IDs,
in-day chronological state revisions and the final snapshot. Gaps, duplicates,
future readbacks, forged decisions, wrong source, mismatched state and malformed
cost fail closed. A downstream change remains a proposal under the existing
capability/rights/budget rules. The only output is a private read model; the
presence of a last successfully *observed* version never claims full corpus
coverage, approval, publication or global currency. Corpus cutoff is always
called out as a limitation, and there is no inferred correction lag without
actual correction/review readback.

RED proof: adding acceptance tests first made the module fail to import the
new digest and receipt types. GREEN proof: **21/21** focused tests, **80/80**
DP-515/DP-516/source-watcher/coverage/cost tests; synthetic fixtures exercise
200/new/amended/304/429, revoked rights, capped budget, disabled watch,
missing cost and duplicate/missing/forged receipt rejection. No HTTP, DB,
provider, scheduler, production or MiniPC execution occurred. The adapter
must still authenticate current rights/capability/budget receipts and load
atomically committed snapshots/attempts/metered costs; this pure projection
does not implement those integrations or provide an operator permission layer.
Original AC-515.1–515.7 remain **unchecked** and unattended watch remains
**NO-GO** until the original durable and runtime evidence is available.

## 2026-10-12 — Opt-in private SQLite watch attempt/state CAS and replay

Added `poc/dichiarazioni_pubbliche/source_watch_store_v1.py` and
`tests/test_dp515_durable_watch_next.py` as an **isolated, disposable
on-disk SQLite fixture adapter** to the existing pure
`plan_watch_poll` / `reconcile_watch_observation` contracts. This is
not the canonical PostgreSQL watcher, a new scheduler, or a live fetcher.
The operator seeds a private, source-exact policy/state/readiness fixture;
the adapter pins the canonical policy fingerprint, source identity and
conditional ETag/Last-Modified and version/hash state to an atomic
`BEGIN IMMEDIATE` attempt record, allowing at most one active poll per
source. It then reconciles an **externally supplied** HTTP observation under
the newly reread, source-scoped rights/capability/budget gate and writes the
new state, committed attempt, observed metadata and at most one deterministic
`SOURCE_REVALIDATION_REVIEW` **held private proposal** in the same
transaction. No provider/HTTP calls, Capture or child jobs occur.

The durable gate revision is pinned separately from the source/state CAS.
A revocation between plan and observation results in `BLOCKED` while
retaining prior successful source hash/version/validators and generating
zero proposals; a revoke-then-restore cycle cannot reuse a plan from the
old rights epoch. An explicit CAS `abandon_stale_attempt` records the
orphaned attempt as `ABANDONED` without advancing attempted/successful
freshness, then permits a distinct new attempt. Revocation after a changed
observation permanently withdraws its held proposals, even if a gate is
restored. Existing receipt replay is accepted only for identical bytes and
the current source/gate revision; stale/out-of-order retries and conflicting
observation payloads fail. Changed source SHA/version produces exactly one
durably deduplicated private proposal; unchanged `304` or same-body `200`
creates none; `429` preserves last success and source backoff across restart.

**TDD:** the ten-method new integration suite was initially RED because
the persistence module did not exist; GREEN against a real temporary disk
database. Tests include closing/reopening SQLite between commits/retries,
ETag/Last-Modified replay, simultaneous competing writer connections,
revoked/mismatched gate/policy, source-state ordering, legacy successful
version preservation, injected SQL trigger failure rolling back state **and**
proposal atomically, safe obsolete-attempt abandonment and permanent
private proposal withdrawal. Combined
`tests.test_dp515_durable_watch_next`,
`tests.test_dp515_incremental_watch` and `tests.test_source_watcher`
**46/46 PASS**, plus Ruff lint/format, targeted `compileall` and
`git diff --check` PASS. The test's supplied READY strings and status-code
observations are **synthetic and not authenticated rights, DP-514 metering,
HTTP readback, signed origin, release epoch or production permission**.
The adapter never dispatches a task and makes no freshness/public claims.

Original **AC-515.1–515.7 remain unchecked**, status **IN PROGRESS**,
unattended production watch **NO-GO**. Still required: canonical PG
transactional writer/lease integration, actually authorized source rights,
capability/cost records and downstream DP-511/510 admission, persisted
health digest from authenticated data, MiniPC canary and public cache/rights
revocation acceptance. No production DB, provider, HTTP, real source,
MiniPC, deploy, commit or push used in this slice.

## 2026-10-14 — Stale changed-200 validator regression (source-only)

An offline adversarial fixture exposed that a changed HTTP `200` carrying an
older `Last-Modified` than the last successfully admitted source version
replaced the confirmed hash/version and recorded a new successful observation.
For example, a source with version v2 and `Last-Modified` 10 October could be
silently regressed to v1 with `Last-Modified` 9 October, even though that
response might come from a stale origin or cache.

The pure reconciliation now marks a changed body/version with regressed
`Last-Modified` as `UNAVAILABLE/LAST_MODIFIED_REGRESSED`, retains the confirmed
source version/hash/ETag/validator and last successful timestamp, applies the
existing bounded backoff, and raises a private source-review flag without any
child proposal. A full `200` with independently verified identical content and
version remains `UNCHANGED` even if validators are rewritten. A changed `200`
without comparable validators follows the existing content/hash review path.

The pure-function and real disposable SQLite regressions were both **RED**
before the patch (`CHANGED` instead of `UNAVAILABLE`) and **GREEN** after.
The focused DP-515/source-watcher suite passes **48/48**; Ruff lint, targeted
compile and diff checks pass. HTTP, rights/cost receipts, MiniPC and public
cache were not exercised. All original **AC-515.1–515.7 remain unchecked**, the
ticket stays **IN PROGRESS**, and unattended production watching stays **NO-GO**.

## 2026-10-14 — Non-invasive MiniPC consumer readback and original-AC blocker

Read-only, strict batch SSH to the actual MiniPC (`minipc`, Linux) confirmed the
deploy mirror `/home/udodo/src/DichiarazioniPubbliche.it`. Its installed
`poc/dichiarazioni_pubbliche/source_watcher.py` SHA-256 is
`74ff8cd36017fbeb8d886c7b90c88053168be4073e68d47434e3e96e02b4737f`,
identical to the integration checkout at `08629895c811bd3a9b6b4861f2523f6489d4cff4`.
Neither `incremental_source_watch.py` nor `source_watch_store_v1.py` exists in
the MiniPC mirror; this is not a deployed DP-515 incremental consumer.

The existing user `dichiarazioni-pubbliche-source-poll.timer` and
`dichiarazioni-pubbliche-source-poll-daily.timer` are both loaded, active and
enabled. The two corresponding oneshot services were observed loaded/inactive,
with `Result=success`. The actual `source-poll.service` executes
`python3 -m dichiarazioni_pubbliche.scheduler_daemon` from the deploy mirror:
this is the pre-existing source polling route, **not** the DP-515 opt-in
SQLite watcher. No timer, service, provider, HTTP fetch, queue, DB, stored user
data, migration, deployment or public reader was changed or exercised.

Local verification on the integration checkout:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest
tests.test_dp515_incremental_watch tests.test_dp515_durable_watch_next
tests.test_source_watcher -q` passed **48/48**; source/store compile passed,
`git diff --check` passed before this receipt and the pre-receipt worktree
was clean. The SQLite test DBs are disposable local fixtures: their `READY`
values, observations, costs and restart scenarios are synthetic. They prove
bounded private CAS/dedup/backoff behavior only, not authenticated rights,
real source changes, durable canonical PostgreSQL admission or real consumers.

**Decision: `NO_CHANGE` to source/runtime.** No newly reproduced technical RED
in the owned watch/store seam independently completes any original AC.
**AC-515.1–AC-515.7 remain unchecked / IN PROGRESS / unattended DP-515 NO-GO.**
The dependency is an owner/operations decision and independent acceptance:
source-specific legally usable acquisition and revalidation rights with genuine
current receipts (source/editorial-rights owner); a versioned approved DP-514
EUR/month budget plus actual provider/quota/charge authority and atomic USD/EUR
queue reservation (budget/operator owner); canonical PostgreSQL watch/admission
and DP-511/DP-510 downstream review/hold wiring (integration owner); then a
governed isolated MiniPC changed/unchanged/revoked-rights canary and public
freshness/cache negative readback (MiniPC/release and editorial acceptance
owners). Resume only after those observable source, approval, cost and install
prerequisites change. Retain the existing polling units unchanged; their
presence is not DP-515 authorization or public freshness evidence.
