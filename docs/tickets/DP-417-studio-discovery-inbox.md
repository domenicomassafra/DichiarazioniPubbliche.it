# DP-417 — studio discovery inbox

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-209, DP-212, DP-414

## Problem

Newly discovered material needs triage. Without an Inbox, automation either stops at logs or silently makes decisions that should be reviewable.

## Outcome

Implement persisted triage queues for new content, duplicate/existing hits, changed captures, unresolved entities, statement candidates, already-covered claim candidates, Coverage Needs and blocked/quarantined items.

## Scope

- Queues derive from database state/query contracts rather than copied counters.
- Row actions: inspect, link/merge candidate, reject, add to collection, extract, promote when eligible, open/target Coverage Need.
- Bulk actions only where semantics are safely identical and reversible.
- Show provider/rights/budget blocks with stable reason codes.

## Non-goals

- No inbox-zero gamification.
- No mass approval of identity/claims from one similarity threshold.
- No automatic publication button.

## Dependencies and sequencing

DP-209, DP-212, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-417.1:** Every queue row has an inspectable provenance path.
- [ ] **AC-417.2:** Action replay is idempotent or explicitly conflict-detected.
- [ ] **AC-417.3:** Blocked rows explain the exact blocker and retry/unblock condition.
- [ ] **AC-417.4:** Bulk actions cannot cross incompatible review states.

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

Private Studio workflow over real processing state.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Read-only blocked-state inspector — 2026-10-08

`StudioReadOnlyWorkspace.tsx` now supports source-bound inbox row selection,
`ready/blocked` filters, explicit provenance display and fail-closed blocker
explanations for the fixture. No triage action is enabled: it would be unsafe to
turn a UI click into a review/merge/promotion without current persisted authority,
idempotency, rights and state-transition verification. Real queue reads, replay,
bulk-action compatibility, runtime canary and full acceptance criteria remain open.
