# DP-227 — Effective-time, interval and supersession verification

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-215, DP-210

## Problem

Statement-date cutoff prevents future evidence from judging an earlier statement, but that
does not prove which law, policy, dataset, office or record version was actually effective
at the relevant time.

## Outcome

Add first-class deterministic verification for valid-from, valid-to, reference period,
superseded version, observed date and publication date. A source can be authentic yet
temporally inapplicable.

## Acceptance criteria

- [x] Pure selector prevents a version effective after the claim time from proving earlier
  status.
- [x] Reviewed superseded-at state prevents the old version from masquerading as current.
- [x] Open-ended and bounded intervals use explicit start-inclusive/end-exclusive semantics.
- [ ] Publication date, observation date, effective interval and reference period remain
  separate.
- [x] Conflicting overlapping approved versions become UNRESOLVED.
- [x] DP-215 TEMPORAL_CUTOFF now consumes persisted evidence valid_from/valid_until and
  applies start-inclusive/end-exclusive version-at-time semantics before verification.
- [x] SUPERSEDED/RETIRED evidence without a reliable valid_until fails closed rather than
  being treated as current merely because its publication date is old enough.
- [ ] Reanalysis is triggered when a load-bearing source receives a reviewed supersession.
- [ ] Full suite and MiniPC canary cover law, policy and statistical fixtures.

## Completion receipt

Local effective-version selector plus real Source Intelligence/verification-path
valid_from/valid_until integration added 2026-10-05. Supersession-triggered reanalysis and
MiniPC production fixtures remain open.
