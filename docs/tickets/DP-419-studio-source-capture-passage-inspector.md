# DP-419 — studio source capture passage inspector

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-210, DP-414

## Problem

Trust in the research corpus requires seeing which exact version was captured and which passage/time range generated a candidate, without dumping copyrighted/raw material into public views.

## Outcome

Implement a private provenance inspector for logical Content, locators, capture versions/hashes, parser/archive receipts, passage selectors, transcript references and derivation candidates.

## Scope

- Version timeline with capture hash/change indicators.
- Safe bounded passage preview according to retention/rights policy.
- Jump from candidate to exact selector/time range.
- Show parser/archive/fetch failure states and derivation candidates.
- Copy stable internal IDs/hashes for audit without exposing credentials/private headers.

## Non-goals

- No public source-body viewer.
- No raw cookie/auth header display.
- No “archived” badge without succeeded receipt.

## Dependencies and sequencing

DP-210, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-419.1:** Two changed captures can be compared at metadata/selector level.
- [ ] **AC-419.2:** Purged-body state remains understandable from hash/receipt metadata.
- [ ] **AC-419.3:** Media candidate jump synchronizes to canonical segment/time range.
- [ ] **AC-419.4:** Sensitive headers/secrets do not render.

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

Private Studio + storage metadata API.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.
