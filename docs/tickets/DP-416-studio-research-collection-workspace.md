# DP-416 — studio research collection workspace

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-113, DP-114, DP-414

## Problem

Research around a case/topic is currently scattered across claims and source notes. Operators need one bounded workspace where sources, chronology, entities, candidates and gaps can be inspected together.

## Outcome

Implement the Research Collection workspace with corpus rail/filters, selected source/passage/timeline view and contextual inspector for entities/statements/claims/provenance/actions.

## Scope

- Collection header contains scope/status, not a truth summary.
- Provide source-oriented and chronology views; graph view is not default.
- Show Coverage Needs and saved filters/views only when persisted.
- Selecting a candidate highlights exact passage/source moment.
- Collection membership actions create reviewed/provenanced edges.

## Non-goals

- No person ranking/statistics.
- No guilt/intent summary.
- No decorative graph/timeline when chronology is not task-relevant.

## Dependencies and sequencing

DP-113, DP-114, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-416.1:** Garlasco pilot can be navigated from collection -> source -> passage -> candidate -> existing/promoted claim.
- [ ] **AC-416.2:** Removing color/icons preserves hierarchy.
- [ ] **AC-416.3:** Large corpus does not require loading all records client-side.
- [ ] **AC-416.4:** Unknown/private/unreviewed public states remain private.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Private Studio UI/API. Must use real corpus fixtures, not lorem ipsum.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.
