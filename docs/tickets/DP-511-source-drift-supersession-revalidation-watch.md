# DP-511 — Source drift, supersession, and provenance revalidation watch

Status: FUTURE
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

- [ ] **AC-511.1:** Changed source bytes/version create a new observation/Capture and never
  mutate the prior preserved source.
- [ ] **AC-511.2:** Identical reobservation is idempotent/deduplicated and does not spam
  reanalysis/alerts.
- [ ] **AC-511.3:** Official dataset/legal-record supersession is evaluated through DP-215
  scope/version rules and can stale the affected evidence assessment.
- [ ] **AC-511.4:** A material change affecting exact quote/speaker/context/rights/evidence
  triggers revalidation and, when safety requires, a DP-510 targeted hold.
- [ ] **AC-511.5:** Temporary source unavailability is distinguished from source-content
  change; historical provenance remains intact.
- [ ] **AC-511.6:** Rights/authority validity expiry produces a hold/review path rather than
  continuing publication from stale clearance.
- [ ] **AC-511.7:** Public output never silently swaps to a newer source/evidence version
  without the required review/verification chain.
- [ ] **AC-511.8:** Operator health identifies affected records and next action with bounded
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

Pending prerequisites and implementation.
