# DP-203 — Controlled claim-extraction fan-out

Status: BLOCKED  
Milestone: M2  
Depends on: DP-202

## Outcome

Release blocked parent claim work gradually with concurrency, cost, retry, and failure
limits. Do not recreate child jobs before the downstream capability is proven live.

## Acceptance criteria

- bounded batch size and concurrency;
- hard daily/source/job cost breakers active;
- idempotent replay demonstrated;
- provider outage returns work to explicit blocked/deferred states;
- production queue counts and receipts are captured before/after.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** Existing bullets: bounded concurrency, daily/source/job breakers, idempotent replay, outage blocked, before/after queue receipt.

**Target delta and remaining acceptance:** Tie the fanout to controlled *eligible* parents/candidate provenance, provider failure and revocation. Never materialize child jobs on unavailable capability. Preserve pre/post actual queue and cost counts; D owns global EUR budget rules.

**Phase / dependencies:** Phase 1 then 3; hard DP-202; soft D budgets; queue owner.

**Related future specifications (separate ownership):** DP-514. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.
