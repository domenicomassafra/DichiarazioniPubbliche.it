# DP-113 — research corpus persistence

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-112; DP-107 persistence conventions; ADR 0007

## Problem

The domain contract is not useful until private corpus state is durable. `content_item.content_sha256` cannot represent multiple observed versions, and no tables currently model collections, passages, statement candidates or claim candidates.

## Outcome

Add an additive PostgreSQL migration, repository APIs and tests for the minimum first-class corpus: `content_capture`, `passage`, `research_collection`, collection membership, `statement_candidate`, and `claim_candidate`, while leaving existing Atomic Claim and public read paths unchanged.

## Scope

- Create additive tables with stable text IDs, timestamps, method/version fields, status vocabularies, JSON metadata only for non-core extension data and explicit FK/delete semantics.
- Content Capture must be immutable in identity/hash semantics; repeated identical replay resolves idempotently instead of producing uncontrolled duplicates.
- Passage must support written selectors and a reference path to canonical media segments without duplicating transcript truth.
- Candidate tables must preserve extraction/provenance version and status; no Finding/publication FK is created from ingestion.
- Create focused repository functions with typed result shapes and idempotency conflict checks.
- Add migration-forward tests, schema parity checks and rollback/documented reversal strategy appropriate to additive production migrations.

## Non-goals

- No search ranking.
- No model extraction implementation.
- No entity/topic/event canonicalization.
- No public projection consumption of private corpus rows.

## Dependencies and sequencing

DP-112; DP-107 persistence conventions; ADR 0007

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-113.1:** Fresh schema and migration-upgraded schema expose identical new contracts.
- [x] **AC-113.2:** Two captures of one Content with different body hashes coexist; replay of one capture is idempotent.
- [x] **AC-113.3:** A Passage cannot exist without valid capture/segment provenance.
- [x] **AC-113.4:** A Claim Candidate can exist without Atomic Claim/Finding and remains private.
- [x] **AC-113.5:** Public projection regression tests prove zero corpus rows leak.
- [x] **AC-113.6:** MiniPC migration canary/read-back succeeds before DONE.

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

Additive SQL migration + Python persistence. Requires MiniPC DB proof; no destructive rewrite of current rows.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `b310d9c` (`feat: add research corpus persistence`).

Implemented:
- additive `content_capture`, `research_collection`, `research_collection_content`,
  `passage`, `statement_candidate`, `statement_candidate_passage` and `claim_candidate`
  schema plus migration `20260929-add-research-corpus-core.sql`;
- same-content composite foreign keys preventing passage/statement cross-content links;
- canonical ClaimType/check-worthiness constraints on Claim Candidate;
- Python typed records/normalizers and replay/conflict-aware repository SQL;
- backup/restore load-bearing inventories expanded to include all seven corpus tables;
- public projection remains unaware of private corpus tables.

Local proof:
- focused corpus/restore suite: 25/25 PASS;
- full suite: **722/722 PASS**;
- deterministic benchmark: **5/5 PASS**;
- `python3 -m compileall -q poc tests`: PASS;
- `git diff --check`: PASS.

MiniPC proof:
- exact hashes for migration, `corpus_repository.py` and backup script matched Mac;
- isolated `dp113_canary` schema was created from the pre-DP-113 schema, migration applied
  successfully, replayed successfully, and all seven corpus tables plus the expanded
  review constraint were read back before the schema was dropped;
- pre-production backup: `20260929T082823Z`, readable dump size 9,979,060 bytes;
- production pre-state: 49 Content, 30 Atomic Claims, 9 Findings, 2 `PUBLISH`, 28 text
  provenance rows, 49 review events; corpus tables absent;
- production migration applied with `ON_ERROR_STOP` and replayed idempotently; the same
  six legacy counts remained exactly unchanged and all seven new corpus tables read 0;
- production rollback-only canary inserted Capture -> Passage -> Statement Candidate ->
  Claim Candidate -> Research Collection/member, read back 7/7, then `ROLLBACK`; residual
  canary rows read 0;
- post-migration backup: `20260929T083011Z`, readable dump size 10,003,752 bytes, manifest
  explicitly contains all seven new tables at count 0;
- MiniPC full suite: **722/722 PASS**; deterministic benchmark: **5/5 PASS**; compileall
  PASS; source-poll timers active.

Rollback posture: the migration is additive except for replay-safe replacement of the
`review_event_entity_type_check` constraint. No existing row was rewritten. Emergency
rollback can restore the pre-migration backup; normal forward evolution should leave the
empty/additive tables in place rather than destructively dropping them.
