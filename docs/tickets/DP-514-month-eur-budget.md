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
