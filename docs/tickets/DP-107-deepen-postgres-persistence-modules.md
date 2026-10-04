# DP-107 — Deepen PostgreSQL persistence modules

Status: FUTURE  
Milestone: M1  
Depends on: DP-101..DP-106

## Problem

`QueueRuntimeStore` exposes unrelated queue, transcript, claim/evidence, verification,
review, correction, and publication mutations through one broad class.

## Outcome

Split the concrete PostgreSQL persistence surface into a small set of deep domain stores
sharing the existing execution primitive, without introducing speculative repository
interfaces or changing behavior.

## Acceptance criteria

- queue execution/cost operations have a narrow store;
- transcript/canonical-segment operations have a narrow store;
- claim/evidence/observation operations have a narrow store;
- review/finding/reanalysis/reply/correction operations have a narrow store;
- SQL transactions that enforce one invariant remain atomic and co-located;
- no generic repository/protocol layer is added without a second backend;
- existing test suite remains green plus focused store contract tests;
- schema/public behavior unchanged;
- MiniPC worker/review/runtime acceptance passes.

## Non-goals

Changing database technology, adding an ORM, rewriting SQL, or redesigning the domain.
