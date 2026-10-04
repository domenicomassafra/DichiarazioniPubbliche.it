# DP-214 — garlasco research collection tracer bullet

Status: FUTURE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-117, DP-209..213

## Problem

The architecture is not proven until a messy real-world corpus can be collected, searched, deduplicated and promoted without corrupting existing claims or creating public side effects.

## Outcome

Build the first real `research:garlasco` collection using a bounded set of 100 real Content items across direct interviews/articles, video/podcast, official/procedural material where available, secondary reporting and deliberate duplicate/derivation examples.

## Scope

- Create a versioned source/query manifest and ingest exactly the bounded pilot set.
- Read back Captures, Passages, entity candidates, Statement/Claim Candidates, clusters and Coverage Needs.
- Link/dedupe against the 30 existing Bruzzone/Lucarelli Garlasco Atomic Claims.
- Review a stratified sample of entity matches and proposition clusters.
- Run idempotent replay and record cost/capture/search metrics.
- Promote at least a small approved candidate slice through DP-117 only when provenance is sufficient; do not publish automatically.

## Non-goals

- No claim that 100 items are exhaustive coverage.
- No “who is more truthful” comparison.
- No automatic guilt/culpability inference.
- No public release of raw corpus bodies.

## Dependencies and sequencing

DP-117, DP-209..213

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-214.1:** 100 logical items have discovery/source provenance and successful items have immutable capture receipts.
- [ ] **AC-214.2:** Duplicate/derivation examples are surfaced without deleting source records.
- [ ] **AC-214.3:** Existing 30 claims remain unique and discoverable/linkable.
- [ ] **AC-214.4:** Search benchmark can answer the agreed Garlasco research questions with measured Recall@K.
- [ ] **AC-214.5:** Open authoritative-source gaps are Coverage Needs.
- [ ] **AC-214.6:** Replay leaves logical counts stable except for intentionally new Capture versions.
- [ ] **AC-214.7:** Public Finding/PUBLISH counts do not increase merely from ingestion.
- [ ] **AC-214.8:** MiniPC read-back and private/public leak checks pass.

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

Real private production corpus on MiniPC. Rights/retention policy governs body storage; no public launch.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.
