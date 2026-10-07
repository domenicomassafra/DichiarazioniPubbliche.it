# DP-116 — postgres corpus search benchmark

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-113; ADR 0008

## Problem

The operator needs one fast way to locate sources/passages/candidates before collecting or verifying again. Introducing a new search service without a benchmark would add operational complexity without proving recall.

## Outcome

Implement and benchmark a PostgreSQL-first internal search contract using structured filters, full-text search and `pg_trgm`; define an explicit go/no-go gate for optional embeddings/pgvector.

## Scope

- Create a versioned search request/result contract spanning content, passage, statement candidate, claim candidate, Atomic Claim, Person, Topic, Event and Collection.
- Add FTS/trigram indexes only after EXPLAIN/query-shape review.
- Support filters for collection/entity/topic/event/date/source/content/candidate/check-worthiness/claim type/state.
- Every result includes stable kind/id and a jump-to-source/passage target.
- Create real Italian benchmark queries from Garlasco and synthetic edge cases.
- Measure Recall@K, latency and operator-relevant duplicate/entity candidate precision; record semantic-search gate thresholds before enabling embeddings.

## Non-goals

- No Elasticsearch/OpenSearch.
- No standalone vector DB.
- No semantic similarity as approval.
- No change to public DP-409 search contract.

## Dependencies and sequencing

DP-113; ADR 0008

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-116.1:** Benchmark dataset/query set is versioned and repeatable.
- [x] **AC-116.2:** Lexical/structured baseline meets the ticketed recall/latency floor or records exact misses.
- [x] **AC-116.3:** Typos/near duplicates exercise `pg_trgm` index-supported path.
- [x] **AC-116.4:** Provider/model outage does not break baseline search.
- [x] **AC-116.5:** Embeddings remain disabled unless measured incremental recall justifies them.

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

May add PostgreSQL extensions/indexes and private API/runtime. Any extension activation requires migration and MiniPC proof.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `0a3ad6a` (`feat: add postgres corpus search`).

Implemented:
- `corpus-search-v1` private query contract spanning Content, Passage, Statement
  Candidate, Claim Candidate, Atomic Claim, Person, Organization, Topic, Event and
  Research Collection;
- structured collection/person/topic/event/source/content/status/claim-type/
  check-worthiness/date/result-kind filters;
- PostgreSQL Italian FTS + `pg_trgm` candidate retrieval with deterministic ordering and
  exact content/passage jump fields;
- migration `20260929-add-corpus-search.sql` with `CREATE INDEX CONCURRENTLY` on existing
  runtime tables;
- versioned 13-case Garlasco benchmark including spelling-error probes;
- no provider, embedding, vector database, verification or publication dependency in the
  search path.

Canary proof:
- isolated DP-116 schema built from the pre-search baseline; migration applied and
  replayed successfully;
- typo `impronta 33 sangie` returned the seeded imprint/blood claim with trigram score
  about 0.632;
- `EXPLAIN` showed `Bitmap Index Scan on atomic_claim_text_trgm_idx`;
- canary schema was dropped and its schema-local `pg_trgm` extension disappeared; public
  production remained untouched before rollout.

Production MiniPC proof:
- source/migration/fixture hashes matched the Mac source;
- pre-rollout backup `20260929T085036Z`, readable dump 10,027,133 bytes;
- migration applied with `ON_ERROR_STOP`, then replayed idempotently;
- `pg_trgm` is installed in `public`; 22 FTS/trigram indexes exist and sampled load-bearing
  indexes report `indisvalid=true`, `indisready=true`;
- benchmark: **13/13 = 100% Recall@5**, first measured p95 57.2 ms; repeated JSON receipt
  **13/13**, p95 **50.792 ms**;
- filter smokes passed for person, claim type + check-worthiness, result kind and source;
- MiniPC full suite: **756/756 PASS**; core deterministic benchmark: **5/5 PASS**;
- post-rollout backup `20260929T085130Z`, readable dump 10,035,862 bytes;
- legacy state remains 49 Content / 30 Atomic Claims / 9 Findings / 2 PUBLISH / 49
  review events.

Measured semantic-search decision: **do not add embeddings/pgvector now**. The lexical +
trigram baseline meets the current recall gate with low latency and deterministic offline
fallback. Reopen only when a larger versioned corpus benchmark demonstrates a material
recall/latency gap. Runtime receipt: `docs/ops/corpus-search-benchmark-2026-09-29.json`.
