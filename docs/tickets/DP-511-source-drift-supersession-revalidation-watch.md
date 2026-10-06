# DP-511 — Source drift, supersession, and provenance revalidation watch

Status: IN PROGRESS
Milestone: M5 — Reliability, security, operations, and data lifecycle
Depends on: DP-210, DP-215, DP-308, DP-510; coordinate with DP-505

## Problem

A public record can be correct when reviewed and become stale later because the source page
changes, an official dataset is revised, a legal/procedural record is superseded, a URL
disappears, rights are revoked, or the project's interpretation depends on a version that
is no longer current. Immutable Captures preserve what was observed, but the system also
needs to know when current-public claims require revalidation.

## Outcome

Add a bounded watch/revalidation mechanism that detects material source-state changes,
preserves the old observed version, and creates explicit review/reanalysis/quarantine work
instead of silently rewriting provenance.

## Scope

- Reobserve launch-set/public load-bearing sources under bounded source-specific policy.
- Detect at least: changed body/hash/version/ETag where reliable, canonical locator change,
  source unavailable, official supersession/revision, rights-state change and authority-
  scope validity expiry.
- Distinguish benign availability/link changes from material provenance/evidence changes.
- A material change creates an append-only event and targeted revalidation/reanalysis need;
  the old Capture/assessment/Finding remains historical.
- If the change can undermine quote attribution, legal status, evidence sufficiency or
  rights, invoke DP-510 hold until reviewed.
- DP-215 authority/temporal/supersession semantics determine what the change means for a
  specific claim; the watch itself does not issue a verdict.
- Feed actionable health/alert information to DP-505 without alert storms; dedupe repeated
  identical observations.

## Non-goals

- No generalized whole-web monitoring.
- No treating HTTP change as proof a claim is false.
- No deleting old captures when a source changes.
- No automatic replacement of old evidence with the newest source version.

## Acceptance criteria

- [x] **AC-511.1:** Changed source bytes/version create a new observation/Capture and never
  mutate the prior preserved source.
- [x] **AC-511.2:** Identical reobservation is idempotent/deduplicated and does not spam
  reanalysis/alerts.
- [x] **AC-511.3:** Official dataset/legal-record supersession is evaluated through DP-215
  scope/version rules and can stale the affected evidence assessment.
- [x] **AC-511.4:** A material change affecting exact quote/speaker/context/rights/evidence
  triggers revalidation and, when safety requires, a DP-510 targeted hold.
- [x] **AC-511.5:** Temporary source unavailability is distinguished from source-content
  change; historical provenance remains intact.
- [x] **AC-511.6:** Rights/authority validity expiry produces a hold/review path rather than
  continuing publication from stale clearance.
- [x] **AC-511.7:** Public output never silently swaps to a newer source/evidence version
  without the required review/verification chain.
- [x] **AC-511.8:** Operator health identifies affected records and next action with bounded
  deduped alerts.
- [ ] **AC-511.9:** MiniPC canary proves unchanged, changed, unavailable, superseded and
  rights-expired paths with correct public/private state.

## Validation / proof

Use local/synthetic controlled HTTP fixtures plus cleared official-style version fixtures.
Run unchanged/changed/unavailable/superseded/rights-expired cases, standard tests and a
MiniPC scheduled/manual canary. No external source is modified as part of testing.

## Documentation, data, and migration impact

Reuse DP-210 capture lifecycle and DP-215 Source Intelligence wherever possible. Add only
bounded watch/revalidation state needed for idempotency and operations; update runbooks and
source-launch-set metadata when implemented.

## Completion receipt

Local `source-revalidation-v1` now provides the pure re-observation decision seam without
performing any network monitoring. It binds immutable before/after snapshot references and a
deterministic event key, distinguishes temporary `UNAVAILABLE` from material content drift,
separates stable-byte locator/ETag churn from changed content, and detects official version
supersession, rights-state changes, rights expiry and authority-scope expiry. Material drift
creates `REVIEW_REQUIRED`; when the source is declared load-bearing for quote, speaker or
evidence proof the same safety-critical change becomes `HOLD_REQUIRED`, ready for the DP-510
domain seam rather than silently swapping evidence. Identical observations are replay-safe
and historical snapshot objects are not mutated.

The durable follow-up now closes AC-511.1 locally: changed source bytes create a new immutable
`content_capture`, while stable bytes with version/locator-only reobservation append a new source
snapshot and reuse the existing Capture without mutation. Append-only
`source_revalidation_snapshot_durable` and `source_revalidation_event_durable` ledgers preserve the
before/after history and deterministic event identity. AC-511.9 remains for the scheduled/manual
MiniPC canary. No whole-web polling or verdict logic is introduced by this local block.

The local DP-511 -> DP-510 bridge is now executable through
`source-revalidation-hold-v1`: a validated `HOLD_REQUIRED` decision creates exactly one
typed DP-510 `SOURCE_PROVIDER_VERSION` hold request for the previous load-bearing source
version. The request binds explicit provider/source/version plus the deterministic DP-511
`event_key`; exact replay returns the same append-only hold event, while altered snapshot
refs/event keys fail closed. `UNCHANGED`, `AVAILABILITY_RETRY` and non-hold
`REVIEW_REQUIRED` decisions create no DP-510 event. Focused integration tests cover changed
bytes/version, official supersession, rights expiry, unchanged, temporary unavailability
and replay. This strengthens the local proof for AC-511.4 without claiming persistence,
public-projection suppression or MiniPC runtime completion.

Local operator-alert integration now reuses the existing DP-504/DP-505
`ops.taxonomy.actionable()` consumer through `source-revalidation-alert-v1`. Material source
drift/review/hold rows map deterministically to the existing `SOURCE` category; rights or
authority-expiry rows map to existing `EVIDENCE`. Severity/page policy therefore comes from
the owned taxonomy rather than a second alert policy. `UNCHANGED` emits no row;
`AVAILABILITY_RETRY` is a non-page `SOURCE` warning. Each row is deduped by DP-511 `event_key`,
includes only bounded source/provider/version/public/hold event IDs, change codes,
disposition and taxonomy codes, and omits URL/body/snapshot hash/private metadata. A DP-510
`HOLD_REQUIRED` alert must bind the matching hold event/scope/impact receipt or fails closed.
The taxonomy's existing operator action remains the next-action authority and is verified by
tests without copying its prose into the alert record.

AC-511.8 is proven at this local operator-record seam because the existing DP-505 consumer
and taxonomy are directly invoked and affected public IDs are bounded/deduped. MiniPC digest
read-back remains part of AC-511.9 and DP-505 runtime acceptance; `health_digest.py` is not
modified by this integration.

Projection follow-up 2026-10-06: the DP-511 -> DP-510 receipt can now participate directly in
production Finding revalidation. A material load-bearing source change activates the previous
provider/source/version scope, and the production hold check omits the affected Finding while the
hold is active or pending revalidation. `REVIEWED_UNHOLD` alone cannot restore it; release requires
a `REVALIDATED` event whose `publication-safety-v1` binding equals the current DP-308 binding.
Changing the load-bearing source binding after release fails closed again. The focused regression
also proves tampered hold chains are rejected. The production path now restores the DP-510
dependency/hold authority from the durable ledgers above and refuses missing/tampered/stale state,
so AC-511.7 is locally closed. The only remaining acceptance criterion is AC-511.9 MiniPC runtime
coverage for unchanged, changed, unavailable, superseded and rights-expired paths.
