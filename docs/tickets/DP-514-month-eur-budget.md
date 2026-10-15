# DP-514 — EUR10-month planning envelope with atomic multi-interval dispatch caps

Status: IN PROGRESS
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-512, DP-513, DP-506

## Problem
 USD5 global/day, USD1/source/day, USD0.25/job protect short-term dispatch but are not EUR10/month. USD token estimates can be stale and two workers can pass a non-atomic budget read concurrently. Quota reset and billed invoice may not align with local month; unknown charges cannot prove an economical release.

## Outcome
 Versioned owner-selected monthly **planning** ceiling around EUR10 in addition to existing short caps; actual EUR cash + optional allocated fixed plan + local incremental energy reported separately. Dispatch reserves conservative maximum charge atomically before every chargeable attempt across same billing scope. Cap breach pauses affected work with digest/explicit resume rules; no provider swap, silent overage or cap increase.

## Traceability & constraints
 R30/R31; Q9–Q14. EUR10 is a target subject to empirical measured capacity, not a guaranteed spend, a verified quote, or automatic authorization to buy subscriptions. Cost of electricity is a distinct quantity; optional cost conversion requires known EUR/kWh and measured incremental Wh, else UNKNOWN. FX conversion records source/rate/date/original amount and provisional vs invoice reconciliation. Pre-existing DP-506 caps remain active, never erased.

## Scope
 Policy defines calendar month/timezone explicitly (Europe/Rome or other owner-approved billing boundary, not inferred from provider reset); per-provider invoice period and quota reset tracked separately. Maintain reserved/pending/settled/estimated/unknown buckets; preflight must check all per-job/source-day/global-day/month/provider quotas and failure backoff. Optimistic stale daily snapshots are insufficient for atomic dispatch: reservation + attempt binding, idempotent settled/refunded/released transitions, concurrent claims, crash recovery and expired reservation reconciliation. Provide budget allocation among pilot, important corrections, incremental discovery and bulk so a historical run cannot starve urgent retraction; operator can pause/resume under documented audited threshold. Unknown paid cost blocks prior to dispatch. A verified included-plan no marginal bill can still have quota cap and electricity cost; it is NOT unlimited.

## Non-goals
 Forcing a supposedly measured invoice from modeled rate, auto-buying capacity, raising daily caps without owner signoff, treating subscription prepayments as universally zero marginal cost.

## Dependencies and sequencing
 DP-512 classification first. DP-513 calibrates feasible budget; implementation could test reservation primitive with synthetic costs earlier, but activating unattended paid quota requires owner acceptance of policy and trial. DP-515 uses these caps.

## Acceptance criteria

- [ ] `AC-514.1`: EUR-month reports show total paid EUR, reserved maximum, provisional FX, subscription allocations and incremental energy separately; unknown values remain visibly unknown.
- [ ] `AC-514.2`: At overlapping scheduler/worker dispatch times a tight final EUR cap admits at most the reservations the cap covers; no duplicated retry charge or overspend via lease expiry/replay.
- [ ] `AC-514.3`: A late actual invoice amount, refund or reset reclassifies settlement with immutable adjustment receipt; breach/uncertainty pauses subsequent jobs and pages according to severity, no unapproved overage.
- [ ] `AC-514.4`: Midnight daily, DST/timezone month change and provider reset tests preserve accounting and safe deferral (provider quota can reset without falsely resetting project month).
- [ ] `AC-514.5`: Existing USD day/source/job guards still operate; when any guard disagrees the restrictive applicable guard wins.
- [ ] `AC-514.6`: Costs UNKNOWN, source policy expired or provider outage preserve held work and suppress child jobs; health digest signals pause, cause, owner and earliest legitimate retry.
- [ ] `AC-514.7`: MiniPC isolated concurrent queue/ledger + restart/reconcile drill records pre/post reserved/spent and zero unauthorized/public output; owner-approved monthly threshold is versioned.

## Validation / proof
 Synthetic concurrent reservation and double-failure/restart cases, late provider invoice, 31-day month/DST, FX unavailable, quota reset different from financial period; isolated PostgreSQL on MiniPC; no live provider trial as part of structural check. Report confidence and residual unknown.

## Documentation, data, and migration impact
 Add only necessary reservation/settlement tables and trace IDs to existing operation ledger/queue schema, with migration apply/replay. Update policy, runbook and private digest, no new billing SaaS.

## Completion receipt
 Not implemented; planning only. Future candidate/policy/FX reference, monthly threshold authority, concurrent proof, MiniPC receipt and residual estimate/unknown must be recorded.

## 2026-10-11 — First implementation slice

An owner-versioned, **disabled by default** monthly EUR budget/reservation proposal was added in `ops/cost_policy.py` (commit `e2df061`), with conservative FX and Rome-month/DST boundaries, explicit UNKNOWN holds and no weakening of USD daily guards. 19 focused tests pass including simulated revision/CAS. `dispatch_authorized` stays false; actual transactional persistent multi-worker CAS, billing settlement, owner-approved cap and MiniPC acceptance are still missing.

## 2026-10-11 — Disposable SQLite transactional reservation proof

Added `SQLiteMonthlyReservationStore` to the existing cost policy module as an
**isolated reference implementation** for the previously pure reservation plan.
An explicitly bootstrapped synthetic month pins the complete enabled policy
fingerprint and stores the exact revision, state fingerprint and bounded
reservation payload. Each independent SQLite connection starts `BEGIN IMMEDIATE`,
replays the persisted state, executes the existing EUR and USD policy checks,
then commits one compare-and-swap update. A competing request re-reads the
committed reservation before attempting its own. Cross-thread independent
connections with a EUR 0.18 final cap committed **one of two** EUR 0.18
requests; concurrent retries of the **same** attempt produced one reservation.
Restart/replay left the single hold unchanged. Stored policy cap alteration,
disabled policy, existing USD-day exhaustion and fingerprint corruption fail
closed. Only aggregate/attempt IDs and FX reference metadata are stored, with
no provider credentials or prompt/source bodies.

RED before implementation: `tests/test_dp514_sqlite_reservations.py` failed
to import the missing persistent reservation API; the earlier in-memory
simulation could not enforce concurrency across SQLite connections. GREEN:
`test_dp514*.py` **16/16 PASS** (including six real disposable SQLite tests),
`test_ops_cost_policy.py` **9/9 PASS**, compileall and diff check pass.

This independent SQLite state **is not the production PostgreSQL operation
ledger**, owner threshold authority, or an integrated queue/worker lock.
Legacy USD snapshots and provider quota remain caller-supplied, and settlements,
invoice corrections, immutable adjustments and reconciliation are not implemented.
Every committed result deliberately keeps `dispatch_authorized=False`; paid
dispatch is unchanged/disabled. This is concurrency evidence for a structural
subpart of AC-514.2, **not** completion of AC-514.2 or any other unchecked AC.
An approved owner policy/empirical DP-513 values, PostgreSQL atomic multi-gate
transaction, real accounting and isolated MiniPC restart drill are still needed.
DP-514 remains **IN PROGRESS**.

## 2026-10-12 — Cross-period persisted attempt and unresolved liability fence

New distinct functional bug found after the prior SQLite reservation and
reconciliation implementation: a globally unique paid `attempt_id` could
be reserved once on the last October day and again on the first November
day, because each monthly state checked only its own reservations. Worse,
an October UNKNOWN or OVER_BOUND settlement held October only: a fresh
November month bypassed the uncertainty without any authoritative invoice
or clearance. Both were **RED** with real temporary SQLite connections.

The existing `SQLiteMonthlyReservationStore.initialize()` now atomically
backfills previous valid reservation states into an immutable
`monthly_global_attempt` ledger (global attempt-id primary key), rejects
inconsistent cross-month historic duplicates and validates full registry
contents. `reserve()` checks this durable index under its existing
`BEGIN IMMEDIATE` transaction, writes the global attempt and the revised
monthly state in the *same* transaction and rejects a repeated attempt in
another month. It also revalidates previous months' versioned state receipts
and blocks any future month while earlier `unknown_liability` remains
unresolved. A calendar boundary does not attest a refund or clear liability.

Additional adversarial tests cover **simultaneous cross-period reservations**
from separate connections (exactly one winner), simulated crash/SQL trigger
failure after global index insertion (whole transaction rollback, restart
and successful retry), immutable legacy backfill/replay, UNKNOWN and
OVER_BOUND carries, and a clean prior reported observation still allowing a
new distinct attempt in November. Final DP-514 and adjacent cost policy
tests: **43/43 PASS**; scoped Ruff F821/F823 and diff check PASS.

This improves the disposable *private* SQLite reservation/reference ledger;
it neither verifies a real invoice nor authorizes a paid job. No production
PostgreSQL queue/scheduler atomic USD/day EUR/month/provider-quota
transaction, approved monthly cap, authoritative settlement adjustments,
MiniPC canary or external reconciliation exists. The global hold remains
fail-closed until a separate qualified correction mechanism is implemented.
**AC-514.1–.7 remain OPEN, ticket IN PROGRESS and release NO-GO.**

### 2026-10-12 — Operable redacted private month readback

Added an explicit local, **read-only** operator CLI:
python3 tools/dp514_private_month_report.py --db /path/to/isolated.sqlite
--period 2026-10@Europe/Rome. It refuses a missing database, symlink and
invalid accounting period; sqlite mode=ro + PRAGMA query_only forbids writes
and avoids implicitly bootstrapping a new month. It consumes the existing
durable state and independently validated immutable reconciliation receipts,
double-reads the monotone state to reject concurrent CAS drift, and emits
only aggregate reserved/observed attempt counts, provisional EUR, held EUR,
unknown/over-bound counts and public-authority=false flags. No account, task
ID, source, quote, private receipt or credential leaves stdout. Zero billed
authority is explicitly represented as NULL, never a zero invoice.

The new actual subprocess/temp-SQLite tests assert real UNKNOWN carry and
readback, symlink/nonexistent/invalid period refusal, unchanged disk bytes
and SQLite UPDATE denial in read-only mode. DP514 + adjacent cost suite:
**46/46 PASS**, scoped Ruff and diff checks pass. This is private
synthetic operational usability, **not** production billing or a provider
invoice, MiniPC activation, USD/EUR combined dispatch or AC completion.

An extra adversarial real-file test committed a second EUR reservation
between the CLI's before-state read and its independently validated receipt
report. The CLI refuses the mixed revision rather than printing stale totals
with a new state SHA. Combined DP514/cost tests now **47/47 PASS**.

## 2026-10-11 — Write-once SQLite observation resolution, no cap release

The existing disposable `SQLiteMonthlyReservationStore` persisted a bounded
reservation but had **no durable per-attempt observation resolution**. An
unknown later cost, observed amount above the original USD upper bound or
replayed usage report could not be correlated with the held attempt while
preserving crash-safe month accounting.

This strictly local reference store now supports `reconcile(policy, period,
observation)` for an **explicit** period and a typed
`MonthlySettlementObservation`. An observation identifies the exact existing
attempt/operation and either `UNKNOWN` or a nonnegative USD amount plus a
bounded **caller-reported, unverified** source reference and SHA-256. These
fields are not proof of authentic provider billing, a settled invoice or
reviewed source rights. A known USD value is converted using the rate **pinned
in the original reservation**, rounded conservatively to micro-EUR, and
reported only as `PROVISIONAL_HELD`. `UNKNOWN` or an observed cost exceeding
the original USD/EUR ceiling records `UNKNOWN_HELD` or `OVER_BOUND_HELD` and
persists `unknown_liability=True`, preventing new monthly reservations.
Late observations from the following calendar month still bind the **original
reserved month**; no implicit quota/month reset or new FX authority occurs.

The additive **isolated SQLite-only** `monthly_reconciliation_receipt` table
stores one fingerprinted immutable receipt per attempt and unique observation
ID. Independent connections serialize through `BEGIN IMMEDIATE`, perform
state revision/fingerprint CAS and insert the receipt in **one transaction**;
UPDATE/DELETE triggers reject later mutation. Repeating the exact observation
after restart returns `MONTHLY_OBSERVATION_ALREADY_RECORDED`, not a second
charge; different data or an observation ID reused for another attempt fails
closed. A synthetic receipt-insert failure after the state CAS rolls back
**both** changes and permits a clean retry. The private, consistent
`reconciliation_report` verifies receipt hashes, state revisions, reservation
IDs, pinned FX and implied disposition before distinguishing held EUR, observed
provisional EUR, unknown attempts and over-bound attempts.

**No money is released, refunded or newly marked billed.** In particular,
a caller-reported zero or lower amount still leaves the **full original EUR
reservation in the cap**; `settled_eur` is not rewritten, `invoice_attested`
and `dispatch_authorized` remain `False`, and verified billed EUR stays
`None`. All prior USD/day/source/job guard values remain caller-supplied and
unverified against a real operation ledger. This slice implements only a
single write-once provisional/unknown observation per attempt; subsequent
authentic invoice corrections, refunds, supersession and owner-authorized
release need separately designed append-only authority and PostgreSQL schema
admission, **not** ad hoc edits to a stored observation.

TDD RED→GREEN: the new settlement import initially failed, then synthetic
SQLite tests exercised two independent concurrent writers with identical and
conflicting payloads, restarts, late observations, UNKNOWN/over-bound holds,
zero-cost non-refunds, ID collisions, append-only triggers, tampering and
atomic crash-style rollback. **36/36 focused tests PASS** across
`test_dp514_sqlite_reservations.py`, `test_dp514_monthly_budget.py` and
`test_ops_cost_policy.py`; scoped compileall, Ruff F821/F823 and
`git diff --check` pass. No paid provider, invoice source, actual settlement,
MiniPC, operational queue/worker, production database or deployment was
accessed. The local receipt SHA is an integrity check, **not** an external
signature or accounting authority.

**All original AC-514.1–.7 remain unchecked / IN PROGRESS**. Still missing:
genuine signed/provider usage and settlement/refund authority, capped USD and
EUR multi-worker **PostgreSQL** coordination with live dispatch, owner-signed
policy and plan quotas, real FX/billing period and energy evidence, durable
operator alerts/retry, and MiniPC acceptance/currentness/revocation drills.

## 2026-10-12 — Canonical PostgreSQL cross-month liability reference (partial)

An independent **local-only**, read-only-by-default monthly cost aggregation
was added as `poc/dichiarazioni_pubbliche/ops/monthly_liability_pg_v1.py`,
with `tests/test_dp514_monthly_liability_pg_next.py`. It intentionally
reuses the existing DP-512 disposable PostgreSQL guard/database,
`provider_receipt` canonical rows, DP-512 append-only classification events,
and DP-513's independent read-only operation attribution. No production
migration or scheduler/worker integration was made. The additive
`dp514_pg_state` and `dp514_pg_event` tables/functions install only
with an explicit opt-in on a `dp512_test_*` local database containing the
canonical schema and DP-512's installed reference ledger.

The private report reads a PostgreSQL `REPEATABLE READ READ ONLY` canonical
snapshot **before and after** the independent DP-513 reader and requires
consistent identity, per-attempt classification revision and ledger parity.
It groups attempts by the original `started_at` accounting month in the
explicit Europe/Rome or UTC zone, preserving an October liability when an
attempt finishes in November. Unclassified, unpriced, external-plan,
unverified zero and source-reference-missing attempts remain UNKNOWN and
carry across calendar months; a provider reset never authorizes new spend.
Recorded measured USD, provisional estimated USD and asserted refund claims
are separate amounts. Verified billed/refunded EUR, FX, energy, subscription
allocation, current daily USD guard and provider quota evidence remain
`None`/unverified. The new-spend hold remains enabled even when all known
canonical costs are nonzero provisional estimates, because no authentic
budget admission, independently sourced FX or daily cap is present. The
report and every event explicitly set `dispatch_authorized=False`.

A separate opt-in `append()` executes a **real PostgreSQL transaction**,
locking the actual canonical `provider_receipt` and DP-512 classification,
rejecting duplicate canonical operation+attempt identity, changed receipt
bytes, absent/stale classification, invalid amount, stale revision or
conflicting event replay. It stores one append-only local
`OBSERVED`/`REFUND_CLAIM` event with CAS. Concurrent writers race on the
same receipt and exactly one revision wins; replay of the identical event
returns its durable receipt even after process restart. A global advisory
transaction lock on the event ID also prevents the same event from being
replayed for a different receipt/attempt. A failed INSERT
rolls back both state and event, allowing a clean retry. A self-reported
refund is never a negative expense, confirmed credit, verified invoice,
quota entitlement or reason to reduce a held month.

**Proof:** the new test failed to import before implementation (RED).
Disposable real PostgreSQL 17 tests cover cross-month/delayed receipt,
UNKNOWN or plan vs estimated/measured, provider reference redaction,
concurrent CAS, exact replay/conflict/restart, actual DB rollback,
append-only triggers, source fingerprint drift, duplicate logical attempt
across months, DP-512 revision invalidation, cross-transaction read drift,
an absent estimate normalized to UNKNOWN, an estimated-only no-grant,
and direct comparison with the existing pure DP-514 SQLite monthly policy.
Final focused `test_dp514_monthly_liability_pg_next`: **16/16 PASS**
on disposable PostgreSQL 17, including cross-attempt event collision.
Adjacent DP-512, DP-513, existing DP-514 and cost-policy regressions:
**64/64 PASS**. Scoped Ruff, compilation and `git diff --check` PASS.
The practical scope is an incremental **billing-liability evidence fence**,
not a pre-dispatch EUR reservation or provider money authority.

**Original AC status remains unchanged, all AC-514.1–.7 open.**
AC-514.1 has only private recorded USD and UNKNOWN classification, without
verified paid EUR, FX, plan or electricity. AC-514.2/5 still lack live
atomic monthly EUR reservation combined with USD/day/source/job and provider
quota locks. AC-514.3 still lacks independently verified invoice/refund
authority, alerts and signed adjustment clearance. AC-514.4 has synthetic
Rome/UTC month rollover only; actual provider quota resets are unverified.
AC-514.6 lacks live scheduler hold and child-job suppression. AC-514.7
requires MiniPC transaction/queue/restore evidence, a versioned approved
owner cap and measured actual bills. Release remains **NO-GO**.

## 2026-10-12 — Strict USD legacy guard validation before synthetic EUR CAS

New adversarial reproduction demonstrated a real fail-open path in the shared
USD `preflight`: `CostSnapshot(global_day_usd=float('nan'))` admitted a
**positive** paid `CLAIM_EXTRACT` estimate, because every `NaN` cap comparison
was false. Negative day/source counters also invented budget headroom; a
non-finite/negative job cap could admit the same paid estimate. With the
DP-514 disposable SQLite reservation store, this wrote a real EUR hold and
`monthly_global_attempt` record despite the untrusted USD guard. The bug
crossed the very USD/EUR guard boundary covered by AC-514.5.

`preflight` now rejects non-finite/negative cost estimates, non-finite/negative
USD policy caps and untrustworthy negative/non-finite USD day/source counters
with explicit `COST_ESTIMATE_INVALID`, `COST_POLICY_INVALID` and
`COST_SNAPSHOT_INVALID` outcomes, respectively. Valid normal USD limits,
zero-cost paths and existing restrictive cap reasons are preserved.
`tests/test_dp514_monthly_budget_wave_close.py` uses a disposable **real
SQLite** reservation/global-attempt ledger; negative/NaN USD counters, bad
limits, restart, Europe/Rome month rollover and cross-month replay establish
that rejected attempts leave no reservation and legitimate requests remain
functional. RED: 14 failed assertions across the four new scenarios, including
actual unwanted SQLite commits. GREEN: **4/4** new tests and **39/39** adjacent
existing tests passed; `git diff --check` passed.

This hardens a concrete local subcondition of **AC-514.5**, but is not the
atomic cross-provider dispatch admission sought in that AC. USD snapshots
remain caller-supplied rather than transactionally reconciled with the
production PostgreSQL operation ledger; invoices, append-only authenticated
corrections, owner-signed EUR policy, provider quota, actual FX and MiniPC
acceptance are still missing. **All AC-514.1–.7 remain OPEN; no live paid
dispatch authority and no production release.**

## 2026-10-13 — Two real GitHub CI PostgreSQL failures, root cause unresolved (NO_CHANGE)

There were **two genuine failed CI attempts** on different already-committed
source revisions in the same PostgreSQL-only regression
`test_dp514_monthly_liability_pg_next.MonthlyLiabilityPgTests.test_claimed_refund_is_append_only_but_never_offsets_spend`:

- PR #11 SHA `d7ff0f7aca4f86332fe3cb4cdf1febe2793afc78`, GitHub Actions
  run `38372931586` attempt 1, Ubuntu Python 3.13 (job `115214120750`);
- PR #3 SHA `fa54df104a4d1319f1630dc342aaf6d2d5dd660a`, GitHub Actions
  run `38380803651` attempt 1, detached clean-clone smoke Python 3.12
  (job `115240437103`).

Both errors reach `DisposableMonthlyLiabilityPg._snapshot()` through
`read()` and end at `_run()` with `DP514_PG_TRANSACTION_FAILED` before
validating the refund output. `_run()` captures but discards the actual
`psql` stderr on an unrecognized non-zero exit. No diagnostic SQLSTATE,
return code, server log or artifact was retained in the examined Actions
receipts, so **the original underlying SQL/PostgreSQL cause is unknown**.
Both failed job sets were rerun on their *unchanged* respective SHAs and
passed; this does **not** retroactively classify either first failure as
benign, nor does it establish a fixed source bug.

The independent 2026-10-13 forensic worker ran local PostgreSQL 17.11
(disposable, isolated from any real service): 96 sequential repetitions of
the exact test (192 snapshot calls), another 80 repetitions over four
concurrent independent disposable clusters (160 snapshots), and the full
16-test class. **All passed**, with no observed PostgreSQL leftover. The
first CI error's elapsed time is compatible with a possible SQL/lock timeout,
but no original stderr or deterministic failing reproduction establishes it.

**NO_CHANGE:** no generic retry, assertion relaxation, SQL migration,
production DB operation, scheduler change or billing-authority shortcut is
justified. If reproduced again, first collect only bounded diagnostic
metadata on the disposable CI test path (psql exit/SQLSTATE or sanitized
error category and elapsed time, plus bounded redacted disposable server
log if safe); never log receipt bodies, secrets or raw SQL containing
private values. Then isolate the exact failure with a RED test before any
behavioral fix. All AC-514.1–.7 and MiniPC/financial authority gates remain
open.

## 2026-10-13 — Two additional independent failing CI attempts (four total)

After the two original DP-514 intermittent PostgreSQL failures recorded above,
**two further first-attempt failures on new unrelated PR source revisions**
reproduced the *same* test, at `DisposableMonthlyLiabilityPg._snapshot()` to
`_run()` and the generic `DP514_PG_TRANSACTION_FAILED`:

- PR #14 `061279868b5205c80b45514329dce5cc5815a46b`, GitHub Actions
  run `38393006211`, Ubuntu Python 3.12, job `115281164284` (failed).
- PR #16 `379e38bb24299f3f93b7b6615a72b85df957133f`, GitHub Actions
  run `38393010633`, Ubuntu Python 3.14, job `115281179638` (failed).

All four failures are confined to
`test_claimed_refund_is_append_only_but_never_offsets_spend` despite different
workflow matrices and source changes. Both new CI jobs completed with exactly
one unittest ERROR in the full backend suite; the other reported backend
checks passing does **not** prove root-cause resolution. The original stderr
was captured inside `subprocess.run` but not recorded by `_run`, and the
original SQLSTATE/return code and server log have not been recovered. The
reproduction is real, but a specific PostgreSQL lock, timeout, deadlock,
SQL error or environmental cause remains **unproven**. No rerun, generic
retry, timeout increase, changed assertion, production DB mutation, or
financial release is justified from these observations.

**Release gate OPEN:** affected PR #14/#16 remain Draft. A future scoped,
privacy-safe CI diagnostic should emit only allowlisted numeric SQLSTATE,
psql exit status, a bounded elapsed time and a fixed statement family code
under an explicitly disposable/test-only path; never raw SQL, receipt
material, database strings, logs with secrets or full stderr. Review and
validate redaction before using it to gather subsequent evidence. All
DP-514 AC and real MiniPC/expense authority remain OPEN.

## 2026-10-13 — Strict disposable CI-only PostgreSQL failure metadata (NO behavioral fix)

Following four separately confirmed CI failures without retained PostgreSQL
stderr, the opt-in diagnostic path now runs **only** under `CI=true`, an
explicit `DP514_CI_PG_DIAGNOSTIC=1`, and the existing canonical loopback,
no-password `dp512_test_` disposable database URL. The backend regression
workflow sets the second flag only around its unit test step. The test seam
requests PostgreSQL's verbose error format internally and, **only on a generic
psql non-zero outcome**, prints a fixed operation family (`SNAPSHOT`, `APPEND`,
`SCHEMA_INSTALL` or `OTHER`), bounded process exit code/elapsed milliseconds,
strict allowlisted five-character SQLSTATE (otherwise `UNKNOWN`), and a
constant category code. It never prints SQL, raw stderr, DSNs, server logs,
receipt IDs, provider payloads or other source content. Domain errors retain
their original exception class and message; the statement/lock/process timeout
policy and append-only semantics are unchanged, and **no retry was added**.

The new mocked test suite was RED before the diagnostic seam and is GREEN with
fake passwords, personal/receipt identifiers and SQL deliberately injected
into PostgreSQL stderr: none appears in diagnostics. Six negative/positive
diagnostic tests and 16 real disposable PostgreSQL DP-514 tests pass in the
prime integrator, plus the worker's wider 50-test DP-512/513/514/diagnostic
matrix. Ruff, compile and diff-check pass. The historical four failures have
**no** recoverable SQLSTATE; the new signal is for future CI failures only,
not a root-cause finding, remediation, budget approval or production release.
All AC-514.1–7 remain OPEN. Source/provider work, real billing and MiniPC
release remain blocked by their independent gates.

### 2026-10-13 — Simulated no-psql macOS CI regression (same diagnostic PR)

The first cross-platform PR #19 CI found a real test-only harness defect:
all four macOS Python jobs failed the synthetic diagnostic tests because
`DisposableBillingPgFence` correctly checks `shutil.which('psql')` during
construction, but macOS CI intentionally has no `psql` installed. The tests
were already mocking `subprocess.run`, not the preceding executable check.
This was not evidence that PostgreSQL production code or receipt policy
should change. A local simulation making `shutil.which` return `None`
reproduced **five failures and two errors** with `BILLING_PSQL_MISSING`
before the test fix. The mock-only synthetic test class now explicitly
stubs the preflight executable result for its lifetime, and does not change
or weaken the actual executable/DSN check. The same absent-psql simulation
is **6/6 GREEN**, as are 22 local DP-514 diagnostics/real disposable
PostgreSQL tests, Ruff and diff check. The new CI must be rerun on the
updated exact commit before technical integration. No original PostgreSQL
SQLSTATE has been recovered and all DP-514 AC remain OPEN.

### 2026-10-13 — Ignore unrelated interpreter warnings in synthetic stderr assertions

The second exact-SHA PR #19 CI completed 11/12 substantive backend jobs but
failed macOS Python 3.13 in a single synthetic test: the strict assertion
that temporarily captured `sys.stderr` must be *completely* empty was
interrupted by an unrelated CPython `ResourceWarning` about previously
unclosed SQLite objects emitted during garbage collection from another
repository test. This is not a diagnostic SQLSTATE, SQL statement or provider
payload, and the PR does not own that other test fixture. The same scoped
mock test still asserts that neither its private synthetic source data nor
`DP514_CI_PG_DIAGNOSTIC` appears in the forbidden paths, without treating
unrelated interpreter warnings as diagnostic leakage. Existing allowed
metadata checks and private text redaction remain strict. Six dedicated
synthetic tests and 22 isolated disposable PG and diagnostic tests PASS,
Ruff and diff-check PASS. The exact new CI SHA must be verified before any
technical merge. The original DP-514 SQL failure is still unexplained; no
retry, provider billing action or changed PG timeout has been introduced.

### 2026-10-13 — Fifth real failure yields SQLSTATE 57014 in disposable CI

The diagnostics above have now captured the *first original PostgreSQL error
class* on a new, real (not rerun) backend job: Draft PR #19 source SHA
`db92016275f640a32a64165225399734a79cec02`, GitHub Actions run
`38397519673`, Ubuntu Python 3.12 job `115296427545` failed the same
`test_claimed_refund_is_append_only_but_never_offsets_spend` during
`SNAPSHOT` on a local `dp512_test_` PostgreSQL fixture. Its bounded output:

`DP514_CI_PG_DIAGNOSTIC operation=SNAPSHOT exit_code=3 sqlstate=57014 category=QUERY_CANCELED elapsed_ms=10953`

This is **strong evidence of PostgreSQL query cancellation** after about
10.95 seconds. The same `_run()` sets `statement_timeout='10000ms'`, making
statement timeout a plausible immediate cause, but the redacted diagnostic
does **not** establish whether the root trigger was CPU contention, an
unexpected row/plan cost, blocked lock, other CI capacity pressure, or an
explicit cancellation. The test fixture inserts only synthetic receipt
material; the original unredacted PostgreSQL message was intentionally not
retained. The same test continues to fail a CI gate: **NO root-cause fix,
NO generic retry and NO unconditional timeout increase**. Investigate the
bounded `_SNAPSHOT` query and disposable PostgreSQL EXPLAIN/lock evidence
before any transaction behavior change. Existing refund claims never offset
spending, `dispatch_authorized` stays false, and all AC-514.1–7 remain OPEN.

### 2026-10-13 — Bounded real-PG17 snapshot plan versus synthetic lock control

A post-merge, **read-only forensic reproduction** ran in a fresh disposable
PostgreSQL 17.11 cluster created by the existing
`tests/test_dp512_billing_pg_fence_next.py` fixture, with exactly one synthetic
provider receipt, one synthetic billing classification, and one append-only
`REFUND_CLAIM`. The original DP-514 refund test completed successfully without
any real provider or production database access. An `EXPLAIN (ANALYZE,
BUFFERS, FORMAT JSON)` of the existing `_SNAPSHOT` SELECT yielded planning
**0.972 ms** and execution **0.385 ms** (top node Aggregate, one returned
row). Twelve subsequent app-level `_snapshot()` calls, including new `psql`
processes, took **27.284 ms minimum / 29.981 ms median / 80.012 ms maximum**;
all returned one synthetic receipt. These measurements demonstrate that the
small deterministic local fixture is not inherently a 10-second query. They
**do not** profile GitHub-hosted runner contention or explain historical
transient failures.

To discriminate error families without changing `_run` or timeouts, a second
fresh disposable PG17 fixture deliberately held an `ACCESS EXCLUSIVE` lock on
`provider_receipt` in a separate synthetic transaction while `_snapshot()`
ran with the existing `statement_timeout=10000ms` and `lock_timeout=8000ms`.
The expected fail-closed result was **SQLSTATE 55P03 (`LOCK_UNAVAILABLE`)**,
`exit_code=3`, elapsed **8030 ms**, with the original generic
`DP514_PG_TRANSACTION_FAILED` preserved. By contrast, the real GitHub CI
failure emitted **SQLSTATE 57014 (`QUERY_CANCELED`)**, elapsed **10953 ms**.
This is evidence *against a simple single lock wait as reproduced here*,
because that case is interrupted by the smaller lock timeout; it cannot rule
out other lock sequences, query/CPU/resource contention, or independent
cancellation under GitHub CI. No raw stderr, SQL logs, receipt bodies, DSN,
provider payloads or secrets were stored as evidence.

**Decision: NO BEHAVIORAL CHANGE.** Retain the exact 10-second statement and
8-second lock limits, 25-second subprocess cap, no automatic retry, and the
existing append-only financial invariants. Only a future specific disposable
CI lock/activity/timing witness or deterministic RED reproducer may justify a
scoped fix, subject to separate review and CI. The observed `57014` is now
documented; the **latency mechanism, financial authority, manual MiniPC and
all DP-514 AC remain OPEN**.

### 2026-10-13 — Strict disposable-CI PostgreSQL wait witness, diagnostic only

The PR #23 Ubuntu Python 3.14 job failed in DP-514 SNAPSHOT with PostgreSQL
SQLSTATE `57014`; DP-240 regressions passed. A separate macOS 3.14 job was
cancelled, not proven to fail. The cause of the hosted timeout is unknown.

An optional observer now samples read-only `pg_stat_activity`, `pg_locks`
and `pg_blocking_pids` only for a loopback `dp512_test_*` PostgreSQL fixture
with explicit CI, redacted-diagnostic and wait-witness flags. It reduces the
samples to a bounded allowlist of activity/wait state and lock/blocker
indicators, never printing SQL, DSNs, private identifiers, payloads or raw
PostgreSQL errors. It emits one sanitized witness line only on SNAPSHOT
`57014`, or `NO_SAMPLE` when unavailable. The original 10s/8s/25s
statement/lock/process timeouts and all financial logic remain unchanged.

Deterministic test **RED→GREEN**, including private-data rejection, and
disposable real PG17 test forced `57014` using `pg_sleep(11)` with correct
`Timeout/PgSleep`, no blocker. DP-514 focused tests **28/28 PASS**;
complete Python suite **3427/3427 PASS** (387.299 s), Ruff/compileall PASS.
No hosted-runner witness has yet proved whether the intermittent error comes
from CPU/scheduling, locks or other cancellation. DP-514 original AC,
financial authority and MiniPC acceptance remain OPEN; no production DB or
provider account was changed.

### 2026-10-13 — Detached clean-clone CI witness coverage

GitHub PR #3 run `38448667971`, detached clean-clone job
`115473617994`, failed on the same DP-514 monthly-refund snapshot test
under Python 3.12, while the backend matrix passed. The detached-clone
workflow executed the Python test suite without the optional diagnostic
flags, preventing a safe wait-state observation for that runner failure.
The existing disposable-fixture-only flags now also apply **only** to its
backend/package test step, alongside the previously covered backend matrix
unit step; a deterministic workflow regression verifies both scopes.

No production, public build or provider operation is included. This change
provides an eventual safe witness, not a fix or proof of the intermittent
timeout mechanism. The existing timeouts, no-retry policy, unresolved
financial authority, MiniPC readback and all original DP-514 AC remain OPEN.

### 2026-10-14 — Linux LLVM-JIT cold-plan finding and transaction-local mitigation

New readback of the **actual** GitHub Actions failure run `38460425665`
(2026-10-13, canonical `main` SHA `35b69df20e4919b062769bef4eab2b47c537061d`)
found two independent Ubuntu snapshots canceled with `SQLSTATE 57014`:
Python 3.13 after **12446 ms** and Python 3.14 after **10251 ms**. Both emitted
the bounded CI wait witness with **16 samples** and the same terminal state:
`active`, `wait_type=NONE`, `wait_event=NONE`, `ungranted_lock=0`,
`blocker=0`, `historical_blocker_seen=0`. These readings supply evidence
against an observed PostgreSQL lock wait at this seam; they do not identify
which non-waiting activity occupied the hosted runner's timeout interval.

The exact `_SNAPSHOT` SELECT, against a freshly initialized **disposable**
PostgreSQL database containing one synthetic canonical receipt, one DP-512
classification and one DP-514 `REFUND_CLAIM`, had a cold planner cost of
**200424.06**, although actual SQL execution on local Homebrew PostgreSQL
17.11 was **0.410 ms**. Its initial missing table statistics overestimate
the query by enough to exceed PostgreSQL's default `jit_above_cost=100000`.
The Mac build reports `jit=on` but `pg_jit_available()=false` and therefore
cannot reproduce LLVM compilation. After `ANALYZE` of these disposable tables,
the same query's cost fell to **8.28** and execution to **0.381 ms**.

An independent, short-lived **PostgreSQL 18.6 Ubuntu disposable cluster**
was created on the MiniPC with a temporary scratch copy of the synthetic
fixture (no service/database/paid-provider/production connection; the cluster
was stopped and its temporary directory removed). There `jit=on`,
`pg_jit_available()=true`, and the unchanged cold SELECT compiled **58 JIT
functions** (JIT total **28.605 ms**) and executed in **42.304 ms** with
estimated cost **200424.06**. In the same synthetic DB, switching only
`jit=off` yielded **0.669 ms** execution and identical one-row result;
after `ANALYZE`, `jit=on` no longer invoked JIT (cost **8.28**,
execution **0.521 ms**). Thus unnecessary cold-plan LLVM compilation is
**demonstrated**, but the ~10–12-second GitHub-hosted cancellations were **not
deterministically reproduced**: their full latency cause remains OPEN, and a
single green runner is not proof of resolution.

To eliminate that measured, unnecessary compilation from this bounded
disposable read, `_SNAPSHOT` now issues **`SET LOCAL jit=off` inside its
existing `REPEATABLE READ READ ONLY` transaction**. It does not change
the process/session/server defaults, statement timeout **10000 ms**, lock
timeout **8000 ms**, process timeout **25 s**, SQL result or any receipt,
USD/EUR accounting, invoice/FX authority or dispatch policy; no retry was
added. A new real-PostgreSQL regression was **RED** before the change
(`jit=on` inside the transaction), then **GREEN** afterward (`jit=off`
inside, a separate subsequent session still `on`, same USD 0.21 measured
liability and USD 0.21 unverified refund claim, `hold_new_spend=True`,
`dispatch_authorized=False`). The focused 34 tests pass on local PostgreSQL
17.11 and independently on disposable Linux PostgreSQL 18.6 with JIT
available; a broader DP-512/513/514 + existing cost-policy matrix passes
**141/141** on the Mac, including real PG and SQLite fixtures. Compileall
and scoped `git diff --check` pass. These are
development/isolated-host observations, not MiniPC integration acceptance.

**Classification:** scoped JIT overhead mitigation verified on disposable
databases; historical `SQLSTATE 57014` end-to-end root-cause/hosted-CI
regression gate **OPEN** until an integrated exact-SHA CI run and additional
diagnostic evidence justify closure. All original **AC-514.1–.7 remain
OPEN**, as do owner monthly threshold/FX/invoice/provider authority,
canonical USD+EUR atomic queue admission, real MiniPC restart proof and
any paid/public dispatch approval. Source delivery on the integration
branch is separate from a reviewed exact-SHA CI run, protected-main merge,
deployment, and financial acceptance.

## 2026-10-15 — CoS02 adjacent DP-512 credential safety contract

The first integrated full run on the DP-512 refund/correction and
password-in-argv hardening revision completed 3703 tests with **one
DP-514 diagnostic test ERROR**, not a PASS. The existing DP-514 synthetic
diagnostic test still expected a disposable client containing a password
in the psql DSN to launch its mocked subprocess and raise a transaction
error. The corrected shared DP-512 fence now rejects that DSN before
spawning psql, as required by the no-secrets-in-argv rule. The DP-514
regression was adapted **without weakening diagnostic redaction**: credentials
in the URI must raise the sanitized disposable-DSN error and the subprocess
mock must remain uncalled; passwordless disposable DSNs retain the original
sanitized RuntimeError/no-diagnostic checks. The scoped DP-514+DP-512 suite
then passed **37/37** with Ruff and diff checks green. The full-suite failure
and this targeted repair are both recorded; no previous failing full run
is relabeled as a pass. This is test/contract reconciliation, not monthly
EUR authorization, provider attestation, deployment or closure of AC-514.1–7.
