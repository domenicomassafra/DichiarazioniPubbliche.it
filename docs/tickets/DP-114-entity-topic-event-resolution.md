# DP-114 — entity topic event resolution

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-113; DP-101 role intervals; non-biometric identity invariant

## Problem

Research needs people, organizations, topics and events to be findable across sources, but fuzzy/model output must not silently create duplicates or merge different identities.

## Outcome

Persist stable Topic/Event records and reviewable entity-resolution candidates whose supporting and contradicting features are inspectable, with narrow deterministic auto-link rules only for pre-approved stable identifiers.

## Scope

- Add Topic and Event persistence with stable IDs, aliases/scope and status/version.
- Add mention/entity-resolution candidate records anchored to Passage or source metadata.
- Store method/version, candidate target, supporting features, contradicting features, optional retrieval score and review state.
- Define exact-identifier/known-alias auto-link rules and fail closed on ambiguity.
- Expose repository/query functions required by extraction and Studio; log review events for durable approvals/rejections.
- Test same-name/different-person, changed role, alias, organization/date context and ambiguous topic cases.

## Non-goals

- No face/voice biometrics.
- No ideology/sentiment classification.
- No model-created canonical entity without a stable decision path.
- No public entity graph from unreviewed candidates.

## Dependencies and sequencing

DP-113; DP-101 role intervals; non-biometric identity invariant

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-114.1:** Ambiguous same-name examples produce candidates, not merges.
- [x] **AC-114.2:** Contradicting features remain queryable after a decision.
- [x] **AC-114.3:** Approved stable-identifier rules are deterministic/versioned.
- [x] **AC-114.4:** Topic/Event merge/rename is append-only or superseding, not silent overwrite.
- [x] **AC-114.5:** Existing Person role-at-date behavior remains green.

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

Additive schema/runtime; may later feed public Topic records only through separately approved projection contracts.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `6a7b268` (`feat: add explainable entity resolution`).

Implemented:
- canonical private `topic` and `event` entities with alias tables and explicit
  supersession lineage;
- `organization_alias` plus versioned `entity_identifier` records for stable external
  identifiers;
- `entity_resolution_candidate` anchored to Content/optional Passage with exactly one
  typed target, supporting features, contradicting features, optional retrieval score,
  method/version and review status;
- exact active identifier uniqueness enforced in PostgreSQL;
- pure runtime resolver: exact stable identifiers may auto-link only when unique; names
  and known aliases only generate review candidates;
- atomic approval SQL writes an `ENTITY_RESOLUTION_CANDIDATE` review event before the
  candidate becomes APPROVED;
- backup/restore inventories include all seven new knowledge tables; public projection
  does not read the private resolution tables.

Local proof:
- focused knowledge suite: 21/21 PASS;
- full suite: **743/743 PASS**;
- deterministic benchmark: **5/5 PASS**;
- compileall and `git diff --check`: PASS.

MiniPC proof:
- isolated `dp114_canary` schema built from the DP-113 baseline; migration applied and
  replayed successfully; all seven tables and `entity_identifier_active_unique` read
  back, then the canary schema was dropped;
- pre-migration backup: `20260929T083804Z`, readable dump size 10,003,772 bytes;
- production migration applied with `ON_ERROR_STOP` and replayed idempotently; legacy
  counts remained 49 Content, 30 Atomic Claims, 9 Findings, 2 `PUBLISH`, 49 review events;
- rollback-only production canary inserted two distinct people with the same canonical
  name and same alias; two resolution candidates remained distinct; a duplicate exact
  identifier was rejected by the unique constraint; one candidate was explicitly
  approved with a review event; one candidate remained CANDIDATE with a contradictory
  feature; Topic supersession lineage was exercised; transaction rolled back;
- residual read-back: zero canary people/identifiers/candidates/reviews/topics and legacy
  Finding/PUBLISH counts unchanged;
- post-migration backup: `20260929T083909Z`, readable dump size 10,027,210 bytes; manifest
  contains all seven new knowledge tables at count 0;
- MiniPC full suite: **743/743 PASS**; benchmark **5/5 PASS**.

No biometric method, ideology classification, person score or public entity graph was
introduced.
