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
- [ ] DP-215 requirement profiles can require effective-version-at-time.
- [ ] Reanalysis is triggered when a load-bearing source receives a reviewed supersession.
- [ ] Full suite and MiniPC canary cover law, policy and statistical fixtures.

## Completion receipt

Local effective-version selector + focused tests added 2026-10-05. Source Intelligence,
evidence persistence, reanalysis and MiniPC integration remain open.
