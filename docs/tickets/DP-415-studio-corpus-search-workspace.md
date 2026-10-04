# DP-415 — studio corpus search workspace

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-116, DP-414

## Problem

Operators need to search before recollecting or rechecking, but existing public Explore/search is intentionally sanitized and too narrow for private corpus work.

## Outcome

Implement the private Corpus Search workspace with mixed typed results, structured filters, keyboard-accessible query state and a selected-result inspector that jumps to exact source/passages.

## Scope

- Use DP-116 internal query contract, not public search API.
- Result kinds content/passage/statement/claim/person/topic/event/collection with clear type labels.
- Filters by collection/person/topic/event/date/source/type/state/check-worthiness/claim type.
- Persist shareable/local query state only as approved; no secret query payload leakage.
- Selected result shows capture/provenance and source jump without requiring a verification run.

## Non-goals

- No public raw-corpus search.
- No chatbot as primary search UI.
- No search-generated truth answer.

## Dependencies and sequencing

DP-116, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-415.1:** Keyboard-only user can query/filter/open/return while retaining state.
- [ ] **AC-415.2:** Known benchmark questions return expected top-K records.
- [ ] **AC-415.3:** Private result bodies never enter public build artifacts.
- [ ] **AC-415.4:** Provider offline state does not break lexical baseline.

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

Private web/API/runtime; web acceptance + accessibility/runtime proof required.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.
