# DP-414 — studio ia v3 corpus inbox collections verify

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-112, DP-113; supersedes only the private two-template constraint of DP-413

## Problem

The previous Verify Studio 2-template model assumes a source is already chosen. It has no coherent place for corpus search, new discovery triage, collection-level research or candidate promotion.

## Outcome

Ratify an implementable Studio IA with four operator jobs: Corpus Search, Discovery Inbox, Research Collection and Verify, all backed by persisted domain objects and one shared design language.

## Scope

- Define navigation, route/state contracts and screen responsibilities.
- Map every visible panel/counter/status to a persisted object/query; no fake AI activity.
- Specify desktop-first layout, keyboard model, loading/blocked/empty/error states.
- Preserve Verify three-pane source/claim/evidence workflow as one mode.
- Define mobile degradation without requiring full mobile operator parity.
- Update DESIGN/UX docs only where the new private IA supersedes old guidance.

## Non-goals

- No visual-polish bakeoff.
- No public IA rewrite.
- No enterprise sidebar/KPI wall by default.

## Dependencies and sequencing

DP-112, DP-113; supersedes only the private two-template constraint of DP-413

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-414.1:** An operator can describe where to search existing corpus, triage new hits, investigate a collection and verify a promoted claim without route ambiguity.
- [ ] **AC-414.2:** No screen conflates analysis with publication.
- [ ] **AC-414.3:** Every status displayed has a domain/query source.
- [ ] **AC-414.4:** One dominant task remains visually clear per screen.

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

Design/IA contract first; implementation follows DP-415..419.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.
