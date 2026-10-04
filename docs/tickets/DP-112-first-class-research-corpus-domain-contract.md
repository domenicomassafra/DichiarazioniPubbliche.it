# DP-112 — first class research corpus domain contract

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: M1 baseline; ADR 0007; coordinate with DP-111 and public schema DP-105

## Problem

The current canonical domain jumps from Content/transcript provenance to Atomic Claim. That is too late for a serious research product: discovered material, captured versions, passages, unresolved attribution, statement candidates, duplicate propositions and research gaps either disappear or get forced into objects whose semantics are already verification-oriented.

## Outcome

Ratify one vocabulary and boundary map for the private Research Corpus without changing public schema v1. The contract must distinguish logical Content from immutable observed Capture, pre-claim candidates from Atomic Claims, research membership from evidence, and promotion from publication.

## Scope

- Ratify Discovery Run, Discovery Hit, Content Capture, Passage and Research Collection semantics.
- Ratify Topic, Event and Entity Resolution Candidate semantics without silent model-created canonical entities.
- Ratify Statement Candidate, Claim Candidate, Proposition Cluster, Source Derivation Relation and Coverage Need semantics.
- Define promote-not-mutate semantics and compatibility with existing `atomic_claim`, `claim_segment` and `claim_text_provenance`.
- Update canonical PRODUCT/CONTEXT/ARCHITECTURE/PLAN plus accepted ADRs and point implementation tickets at them.
- Perform a collision audit against existing DP-101..111, DP-205/206, DP-405..413 and DP-703.

## Non-goals

- No SQL migration or production DB change.
- No corpus ingestion, crawling, embeddings or new UI.
- No public case/dossier route and no public schema change.

## Dependencies and sequencing

M1 baseline; ADR 0007; coordinate with DP-111 and public schema DP-105

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-112.1:** Canonical docs use one vocabulary for all new corpus objects and explicitly preserve existing public invariants.
- [ ] **AC-112.2:** The contract states `Content != ContentCapture`, `ClaimCandidate != AtomicClaim`, and `ResearchCollection membership != Evidence`.
- [ ] **AC-112.3:** Promotion is explicit/idempotent and cannot create evidence approval, Finding or publication as a side effect.
- [ ] **AC-112.4:** Current written/media provenance paths have a compatibility strategy rather than being rewritten in place.
- [ ] **AC-112.5:** The dependency graph identifies the additive schema/runtime/Studio tickets and no duplicate ticket owns the same contract.
- [ ] **AC-112.6:** No public schema/API field changes are implied by this ticket.

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

Documentation/domain only. No migration. This ticket unlocks DP-113 and is the authority for naming in later migrations.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 as the architecture/domain slice only; no runtime/database mutation
was performed.

Delivered:
- canonical PRODUCT/CONTEXT/ARCHITECTURE/PLAN updated with the Research Corpus boundary;
- `docs/34-research-corpus-knowledge-architecture-v1.md` with the implementation model,
  complete donor disposition, Studio IA direction, Garlasco tracer bullet and dependency
  graph;
- ADR 0007 accepting the first-class private Research Corpus;
- ADR 0008 accepting PostgreSQL-first corpus search/similarity;
- implementation tickets DP-113..118, DP-209..214 and DP-414..421.

Proof:
- plan/ticket collision audit: 85 plan ticket IDs, zero missing ticket specs; all 21 new
  IDs resolve to exactly one spec;
- `python3 -m compileall -q poc tests`: PASS;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v`: 703/703 PASS;
- restore-drill verification emitted by the suite: PASS;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`: 5/5 PASS;
- `git diff --check`: PASS.

MiniPC proof is not required for this documentation-only domain decision. DP-113 is the
first runtime/schema ticket and requires migration/read-back proof before DONE.
