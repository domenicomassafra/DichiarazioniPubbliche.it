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

- [x] Existing provider_receipt persistence now carries operation key, attempt,
  provider/model/task, start/end, input seconds, request count, optional token usage,
  estimate, measured cost, billing basis and private ledger scope.
- [x] Pure ledger uses a stable provider/model/input-scoped operation key and keeps retries
  visible without inflating logical operation count.
- [x] Candidate-extraction failures after a provider call are stored conservatively as
  UNKNOWN with a non-zero cost bound (or ZERO_COST only when the recorded bound is zero);
  successful provider-reported cost is MEASURED_PROVIDER_COST.
- [x] QueueRuntime can reconstruct persisted receipts and filter by content/source,
  provider/task, date window and claim/collection scope where the writer supplies it.
- [x] EVIDENCE_FETCH writes claim scope; content/source are derived from the canonical
  Content relation. DP-209 discovery writes collection + manifest/run/query/attempt scope.
- [x] Measured total, estimated-only total, external-plan usage and unknown usage are
  reported separately.
- [x] Unknown/unallocated usage cannot be coerced to a complete zero-cost result.
- [x] Worker/scheduler daily/source cost paths, health digest and outage drill now use
  measured cost when available and otherwise the conservative estimate, matching the
  canonical ledger billing semantics.
- [x] DP-209 discovery attempts bridge every invoked adapter call to a collection-scoped
  canonical operation receipt; `test_collection_ledger_aggregates_invoked_discovery_operations_idempotently`
  proves collection aggregation and stable replay identity.
- [ ] Full failure-injection and MiniPC restart/replay canary pass.

## Completion receipt

Provider receipt v2 schema/migration, worker + candidate-extraction writers, persisted
ledger query/aggregation, DP-506 cost-path integration, and the DP-209 collection-scoped
discovery bridge were added and locally tested 2026-10-05. MiniPC restart/replay proof
remains open.
