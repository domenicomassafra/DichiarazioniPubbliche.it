# DP-212 — candidate matching clustering runtime

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-115, DP-116, DP-211

## Problem

Mass extraction will produce repeated propositions and already-covered claims unless matching runs before promotion.

## Outcome

Implement a deterministic-first candidate matching cascade that proposes duplicate/same-proposition clusters and links to existing Atomic Claims without silently approving equivalence.

## Scope

- Exact normalized/hash and source-overlap matching first.
- Use trigram + structured entity/topic/time features next.
- Optional embedding/reranking only after DP-116 gate.
- Persist candidate classifications `SAME_PROPOSITION`, `RELATED`, `DIFFERENT`, `UNCERTAIN` with method/version/features.
- Expose reviewed sample evaluation and false-merge/false-split analysis.

## Non-goals

- No auto contradiction/intent finding.
- No delete-on-dedupe.
- No person/source score.

## Dependencies and sequencing

DP-115, DP-116, DP-211

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-212.1:** Known duplicate fixtures rank ahead of related-but-different fixtures.
- [ ] **AC-212.2:** Uncertain candidate is held rather than merged.
- [ ] **AC-212.3:** Existing 30 Garlasco claims are matchable without being recreated.
- [ ] **AC-212.4:** Match algorithm/version is replayable and comparison features are inspectable.

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

Private matching runtime/search. May consume proposition cluster persistence from DP-115.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed and runtime-certified on 2026-09-30 from implementation commit
`03a5cf102b2433b20383439f9f45d6db2a352351` on `main`.

Implemented:
- `candidate-matching-v1` deterministic-first runtime in
  `poc/dichiarazioni_pubbliche/candidate_matching.py` plus CLI
  `tools/match_claim_candidate.py`;
- replayable `candidate_match_run` / `candidate_match_result` ledger with exact input
  fingerprint, ordered target rank, match class/method/features and explicit disposition;
- `DUPLICATE_EXTRACTION`/`SAME_PROPOSITION` create only DP-115 Proposition Cluster
  **candidates**; `UNCERTAIN` becomes `HOLD` with no cluster; `RELATED`/`DIFFERENT` do not
  create cluster proposals;
- existing Atomic Claims are corpus targets only and are never recreated or mutated;
- claim-type and temporal-scope comparison features are persisted alongside the existing
  exact/source-selector/lexical/entity/topic DP-115 features;
- matching persistence is private, included in backup/restore inventory, and cannot create
  Evidence, Verification, Finding or public projection state.

Acceptance fixture proof:
- duplicate extraction ranked ahead of related-but-different fixtures;
- an uncertain pair deterministically produced `UNCERTAIN/HOLD` with no cluster id;
- fingerprint is target-order independent and includes `candidate-matching-v1`;
- structured ClaimType/time agreement and disagreement remain inspectable features.

Isolated MiniPC PostgreSQL proof:
- schema was built from pre-DP-212 commit `1dfcfcb`; migration
  `20260930-add-candidate-matching-runtime.sql` applied and replayed with
  `ON_ERROR_STOP=1`;
- the canary copied the **30 existing production Garlasco Atomic Claims** into an isolated
  schema, then seeded exactly one synthetic Claim Candidate equal to
  `claim:garlasco:bruzzone:2025-05-21:impronta33-tests-negative`;
- first run id
  `candidate-match-run:17960eb13c0453125edbc6af561fc8654ea8d40e64b549332851212c91b5c866`,
  fingerprint
  `ad65fd144e14ad7c7557615a295500ad3dff33d29d55a41553f742f8dc14e000`,
  produced **30** persisted pairwise results;
- rank #1 was the exact existing Atomic Claim above with
  `SAME_PROPOSITION / EXACT_NORMALIZED / PROPOSE_CLUSTER`, lexical score 1.0 and one
  reviewable cluster proposal;
- rank #2 was the related `impronta33-non-sangue` claim but classified
  `UNCERTAIN / HOLD` with **no** cluster id;
- replay returned the same run/fingerprint with `replayed=true`, 30 results total and no
  duplicate run/result/cluster rows;
- canary counts after replay: 30 Atomic Claims / 1 synthetic Claim Candidate / 1 match run /
  30 match results / 1 Proposition Cluster / 2 cluster members;
- Atomic Claim digest exactly matched production on both sides:
  `08f310e9e6d5ecb3ca83e677c66ebb7c`; Evidence / Verification / Finding / Review /
  Claim Candidate Promotion counts stayed zero in the isolated schema;
- the tracer exposed a historical column-order difference between canonical and production
  `atomic_claim`; the copy was correctly repeated with explicit named columns rather than
  relying on `SELECT *`. No production data was changed by that discovery.

Production MiniPC proof:
- Mac/MiniPC key-file digest matched:
  `73045bda2c3bdb4324e97bbf9d97b6ee781dddb79c707a5da5b33a9f6cb37b65`;
- pre-rollout backup `20260930T135149Z`, readable **10,141,926-byte** dump;
- before migration the two matching tables did not exist; legacy counts were
  30 Atomic Claims / 0 Claim Candidates / 0 Proposition Clusters / 0 members /
  17 Evidence / 9 Verification Runs / 9 Findings / 49 Review Events;
- migration applied and replayed idempotently; the matching tables read back empty and the
  review-event constraint remained present with both DP-211 entity-mention and DP-212 match
  result vocabularies;
- legacy data digest before and after was exactly stable:
  `dfe6f3f4773eeacc6303ff52a456aa7c`; the public projection bundle remained byte-stable at
  `2f802df9cb9a67672845513a5516dd9f9fd460dd6f888d89be319c4ab489d5a0`
  with its pre-rollout 2026-09-27 mtime;
- MiniPC complete suite: **956/956 PASS**; deterministic benchmark: **5/5 PASS**;
  corpus-search benchmark: **13/13 Recall@5**, p95 **52.9 ms**;
- post-rollout backup `20260930T135228Z`, readable **10,152,940-byte** dump; manifest reads
  `candidate_match_run=0`, `candidate_match_result=0`, `atomic_claim=30`,
  `claim_candidate=0`, `finding=9`.

No embedding/vector layer was added: DP-116's measured lexical/trigram baseline remains the
candidate-generation seam, while proposition equivalence stays deterministic/reviewable.
