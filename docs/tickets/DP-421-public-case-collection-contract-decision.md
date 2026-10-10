# DP-421 — public case collection contract decision

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-214, DP-420, M3 policy

## Problem

A rich private Research Collection may justify a public case/topic dossier, but publishing the research workspace itself would leak private/unreviewed material and the term `Published Dossier` already means one finding-versioned record.

## Outcome

Make an evidence-based go/no-go decision on a distinct public Case/Collection read model after the Garlasco pilot proves what information readers need. If GO, specify a sanitized projection contract; if NO-GO, preserve current five-template Public IA.

## Scope

- Evaluate reader jobs: timeline, key public documents, published findings, reviewed statement relations and corrections.
- Define naming so it does not overload Published Dossier.
- If GO, specify projection-only fields, omission gates, routes and mobile hierarchy.
- Require legal/privacy/copyright review for any public source excerpt/document representation.

## Non-goals

- No public raw research collection.
- No unreviewed allegations/claim candidates.
- No person score/ranking/culpability summary.
- No implementation until contract is accepted.

## Dependencies and sequencing

DP-214, DP-420, M3 policy

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-421.1:** Decision is recorded in ADR/spec with evidence from DP-420 tasks.
- [ ] **AC-421.2:** GO contract can be generated solely from approved public-safe projection inputs.
- [ ] **AC-421.3:** NO-GO leaves existing public routes/contracts stable and records the rationale.

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

Architecture/public contract decision; implementation, if any, becomes a separate ticket.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE. First accept DP-420 operator/research results; then choose explicitly between a sanitized public Case/Collection contract or NO-GO/reuse of existing Topic/Content/Trace. Private Research Collection is never auto-published.
