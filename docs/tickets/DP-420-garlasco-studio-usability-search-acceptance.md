# DP-420 — garlasco studio usability search acceptance

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-214, DP-415..419

## Problem

A technically complete corpus can still be unusable. The user specifically rejected the current experience as poor, so acceptance must measure whether real research questions can be answered efficiently.

## Outcome

Run a task-based acceptance on the real Garlasco collection across search, collection navigation, source provenance, duplicate/cluster review, coverage gaps and promotion. Use findings to close UX/contract defects before mass ingestion.

## Scope

- Version 15-25 concrete operator tasks/questions.
- Measure success, top-K recall where search applies, time-to-source and navigation/action errors.
- Test wide desktop, keyboard, 200% zoom, reduced motion and representative narrow viewport.
- Run a visual-critique pass against actual screens with corpus data.
- Record defects as separate implementation tickets rather than silently widening DP-420.

## Non-goals

- No subjective “looks cool” acceptance.
- No political judgment/ranking.
- No corpus exhaustiveness claim.

## Dependencies and sequencing

DP-214, DP-415..419

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-420.1:** All critical tasks are completable without DB shell/manual JSON inspection.
- [ ] **AC-420.2:** Search benchmark meets accepted threshold.
- [ ] **AC-420.3:** Candidate/source provenance can be reached in bounded interactions.
- [ ] **AC-420.4:** No critical accessibility/runtime defect remains.
- [ ] **AC-420.5:** User-visible design has one dominant task and no dashboard/card-wall regression.

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

Acceptance/QA; may spawn bounded defects. Does not publish corpus.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE until real Garlasco source rights and DP-214/215 corpus path are accepted and the private Studio DP-416..419 workflows are usable. Test real researcher tasks/accessibility/retrieval with measured acceptance; no synthetic-only UX DONE.
