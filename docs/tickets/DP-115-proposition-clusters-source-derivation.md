# DP-115 — proposition clusters source derivation

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-113, DP-114; Claim Polygraph donor concepts; DP-104 relation policy

## Problem

The corpus will contain repeated extraction, paraphrases and syndicated reporting. Treating each as independent creates claim duplication and evidence amplification. Existing longitudinal `claim_relation` is not the same thing as pre-verification equivalence/derivation.

## Outcome

Introduce private proposition-cluster membership and source/content derivation candidates with reviewed states, while keeping same-proposition, source-dependence and longitudinal contradiction as separate concepts.

## Scope

- Persist Proposition Cluster and membership candidates with method/version/features/review state.
- Persist content-derivation candidates for republication, syndication, quotation, press-release-derived and unknown derivation.
- Generate exact/source-overlap/lexical candidates first; semantic methods remain optional candidate generators.
- Define approved derivation -> evidence-independence handoff as an explicit later operation, never silent evidence mutation.
- Provide reviewed fixtures for duplicate extraction, paraphrase, related-but-different proposition and copied-news families.

## Non-goals

- No public “same claim” relation without separate projection policy.
- No truth conclusion from cluster membership.
- No automatic contradiction/position-change approval.
- No global source reliability score.

## Dependencies and sequencing

DP-113, DP-114; Claim Polygraph donor concepts; DP-104 relation policy

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-115.1:** Same source/selector duplicate is distinguishable from same-proposition across sources.
- [ ] **AC-115.2:** Related-but-different propositions can be rejected from one cluster without data loss.
- [ ] **AC-115.3:** Ten copied articles can be represented as one derivation family without deleting records.
- [ ] **AC-115.4:** Cluster/derivation suggestions cannot change existing approved evidence by side effect.

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

Additive private knowledge schema/runtime. No public projection changes.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `11a323f` (`feat: add proposition clusters and derivation`).
A backup-rotation defect discovered during rollout was fixed separately in `eb731b6`
(`fix: make backup rotation fail closed`) before this ticket was closed.

Implemented:
- private `proposition_cluster` and `proposition_cluster_member` persistence with reviewed
  `DUPLICATE_EXTRACTION`, `SAME_PROPOSITION`, `RELATED`, `DIFFERENT`, and `UNCERTAIN`
  membership semantics;
- private `content_derivation_family` and `content_derivation_candidate` persistence for
  republication, syndication, quotation, press-release-derived and unresolved derivation;
- deterministic exact-normalized/source-selector/lexical matching helpers with explicit
  features and no truth or contradiction conclusion;
- exact-body-hash derivation proposal remains CANDIDATE until review;
- derivation -> evidence independence handoff is a pure proposal object and requires an
  APPROVED family plus APPROVED edges; it never updates `evidence`;
- atomic review-event approval SQL for cluster, member, family and derivation candidate;
- backup/restore inventories include all four new private tables; Public projection reads
  none of them.

Local proof:
- focused DP-115 tests: 19/19 PASS;
- complete suite after backup regression fix: **798/798 PASS**;
- deterministic verification benchmark: **5/5 PASS**;
- compileall, shell syntax and `git diff --check`: PASS;
- fixtures distinguish same-selector duplicate extraction, same proposition across
  sources, related-but-different propositions, unrelated propositions and ten copied
  articles in one derivation family.

MiniPC canary proof before production:
- isolated `dp115_canary` was built from the pre-DP-115 production schema; migration
  applied and replayed idempotently; all four tables read back;
- functional canary persisted one family with **10 derivation edges / 10 distinct derived
  Content items**, one proposition cluster/member and four explicit review events;
- a seeded evidence row and APPROVED claim-evidence candidate retained the exact same
  independence group/status through clustering/derivation operations; canary schema was
  then dropped.

Production proof:
- pre-migration state: 49 Content / 30 Atomic Claims / 17 Evidence / 9 APPROVED
  claim-evidence candidates / 9 Findings / 2 PUBLISH / 49 review events;
- evidence-ledger digest before migration: `62b9e2aba90ff199f76e0e5e40c75c72`;
- pre-migration backup: `20260929T093745Z`, readable dump 10,040,994 bytes;
- migration applied with `ON_ERROR_STOP` and replayed idempotently; all four new tables
  started at zero, Finding/PUBLISH/review counts were unchanged, and the evidence digest
  remained exactly `62b9e2aba90ff199f76e0e5e40c75c72`;
- rollback-only production canary created 1 family + 10 edges + 1 cluster + 1 member + 4
  reviews, asserted the same evidence digest inside the transaction, then rolled back;
  residual content/claim/cluster/derivation/review canary counts all read zero;
- search benchmark remained **13/13 Recall@5**, p95 47.108 ms;
- core deterministic benchmark remained **5/5 PASS**.

Backup regression discovered and fixed during closure:
- the previous count-rotation loop deleted the newest backup once more than KEEP valid sets
  existed, and could then print a false `BACKUP OK`;
- `eb731b6` now deletes the oldest excess sets, refuses KEEP < 1, makes same-second backup
  directories unique, and re-checks the current dump after rotation before reporting OK;
- four dedicated backup tests PASS locally and on MiniPC;
- replacement post-migration backup `20260929T094221Z` is present/readable at
  **10,057,854 bytes**, keeps exactly 10 valid sets, removed the oldest set rather than the
  new one, and its manifest includes all four DP-115 tables at count 0;
- MiniPC full suite after this fix: **798/798 PASS**.

No public same-claim relation, truth score, source reliability score, evidence mutation,
contradiction approval or publication side effect was introduced.
