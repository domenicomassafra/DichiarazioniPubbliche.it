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
