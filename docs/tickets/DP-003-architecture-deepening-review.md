# DP-003 — Architecture deepening review of current modules

Status: DONE  
Milestone: M0  
Depends on: DP-001

## Problem

The current package grew feature-by-feature. Large runtime files (`queue_runtime`,
`worker_daemon`, `public_projection`) may hide good or bad seams; file count alone does
not answer whether a refactor is useful.

## Outcome

Review the codebase using module depth, locality, leverage, adapter seams, deletion test,
and test surface. Produce before/after candidates without implementing speculative
interfaces.

## Acceptance criteria

- inspect actual call/data flow, not only file sizes;
- identify deep modules worth keeping and shallow seams worth collapsing;
- identify any god-module responsibilities that should move behind domain interfaces;
- each candidate states files, problem, solution, benefit, test impact, and confidence;
- no rewrite ticket is created without a concrete improvement hypothesis.

## Validation

Architecture review artifact plus code-navigation evidence; no production change.

## Completion receipt

See `docs/reviews/architecture-deepening-2026-09-22.md`. The review inspected module
sizes, public method surfaces, imports/call responsibilities, and test concentration.
