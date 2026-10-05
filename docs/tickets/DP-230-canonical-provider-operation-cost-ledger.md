# DP-230 — Canonical provider-operation receipt and cost ledger v2

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-209, DP-211, DP-506

## Problem

The project already has budget caps, provider receipts, operation keys and cost fields, but
usage is fragmented across jobs and runs. It cannot yet reconstruct one canonical cost and
usage ledger for a claim, content item or research collection while distinguishing measured
cost, estimated cost, external-plan usage and unknown/unallocated usage.

## Outcome

Adopt the current donor receipt lesson: every paid-capable operation has a stable operation
identity across retry/restart, a durable attempt/usage receipt, and a reconstructable
aggregate. Unknown cost is never displayed as zero.

## Acceptance criteria

- [ ] Persisted provider receipt records operation key, provider/model/task, attempt, start/end,
  duration, token/seconds/request usage where available, estimate, measured cost and billing
  basis.
- [x] Pure ledger uses a stable provider/model/input-scoped operation key and keeps retries
  visible without inflating logical operation count.
- [ ] Cancellation/failure after provider start remains ambiguous/charge-possible unless a
  provider receipt proves otherwise.
- [x] Pure ledger filters/group inputs by claim/content/source/collection/provider/task
  dimensions; persisted day/query aggregation remains to wire.
- [x] Measured total, estimated-only total, external-plan usage and unknown usage are
  reported separately.
- [x] Unknown/unallocated usage cannot be coerced to a complete zero-cost result.
- [ ] Existing DP-506 caps use the same canonical receipt identities.
- [ ] Full failure-injection and MiniPC restart/replay canary pass.

## Completion receipt

Local operation identity, receipt model, aggregation/filtering contract and focused tests
added 2026-10-05. Database migration, existing-receipt adapters, DP-506 integration and
MiniPC replay proof remain open.
