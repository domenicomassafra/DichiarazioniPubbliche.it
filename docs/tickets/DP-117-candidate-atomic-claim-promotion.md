# DP-117 — candidate atomic claim promotion

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-113, DP-115, DP-102 Atomic Claim contract, DP-111 written provenance

## Problem

Without a single promotion seam, new corpus-native extraction could bypass existing provenance rules or create a second incompatible claim model.

## Outcome

Implement one idempotent promotion service that validates a reviewed Claim Candidate, deduplicates/link-resolves it, and either links to an existing Atomic Claim or creates exactly one compliant Atomic Claim with approved source provenance.

## Scope

- Define promotion input/output/reason codes and idempotency key.
- Require stable Content + Capture/segment provenance and sufficient attribution for the selected written/media path.
- Run duplicate/cluster lookup before create.
- Preserve candidate -> Atomic Claim edge and promotion receipt.
- Adapt curated-written intake behind the contract in a compatibility test slice; plan media migration separately if required.
- Prove promotion does not create Evidence approval, Verification Run, Finding or public projection by side effect.

## Non-goals

- No auto-promotion based solely on model confidence.
- No finding/publication action.
- No destructive rewrite of existing 30 Garlasco claims.

## Dependencies and sequencing

DP-113, DP-115, DP-102 Atomic Claim contract, DP-111 written provenance

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-117.1:** Replay returns the same promotion result and does not duplicate Atomic Claim/provenance.
- [x] **AC-117.2:** A duplicate candidate can link to an existing claim with explicit receipt.
- [x] **AC-117.3:** Missing attribution/capture provenance fails closed with stable reason code.
- [x] **AC-117.4:** Written and media provenance channels stay distinct.
- [x] **AC-117.5:** Existing direct intake regression remains green during migration.

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

Private/domain runtime with compatibility adapters; may require additive promotion ledger table.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in two implementation commits:
- `4a9a0a7` — `feat: add claim candidate promotion seam`;
- `5e81376` — `feat: route promotion-ready curated intake`.

Implemented the single reviewed `ClaimCandidate -> AtomicClaim` seam:
- additive `claim_candidate_promotion` ledger with one promotion per candidate/version,
  a unique idempotency key, action (`CREATED` / `LINKED_EXISTING`), provenance channel,
  target claim and exact provenance references;
- deterministic, replayable promotion ids/claim ids and advisory-lock serialization per
  candidate;
- explicit fail-closed blockers for missing candidate/statement review, missing or
  non-public attribution, missing/multiple provenance passages, held/quarantined capture,
  channel mismatch, unresolved media transcript, ambiguous duplicate target and orphaned
  promoted state;
- written promotion reuses approved `claim_text_provenance`; media promotion reuses
  `claim_segment` to an already RESOLVED canonical transcript segment; the channels do
  not cross;
- exact existing-claim or reviewed same-proposition cluster matches use
  `LINKED_EXISTING` rather than duplicating Atomic Claims;
- promotion creates no Evidence, Verification, Finding, Relation or publication record;
- backup/restore inventories include the promotion ledger and Public projection remains
  unaware of it.

Compatibility work:
- existing historical curated-written intake remains unchanged for replay of the 30
  Garlasco Atomic Claims and their existing provenance;
- new `apply_curated_written_batch_via_promotion` accepts only promotion-ready curated
  records carrying a real whole-capture SHA-256 and exact quote character offsets; it
  materializes `ContentCapture -> Passage -> StatementCandidate -> ClaimCandidate`,
  appends explicit review events, then calls the DP-117 promotion seam;
- the adapter refuses old manifests without capture/hash/offset provenance instead of
  fabricating it;
- replay identity for Statement/Claim Candidate now ignores mutable review/promotion
  state, so a reviewed/promoted candidate re-ingests as the same immutable object rather
  than conflicting.

Local proof:
- focused promotion and schema suite: 18/18 PASS before compatibility follow-up;
- final complete suite: **822/822 PASS**;
- deterministic verification benchmark: **5/5 PASS**;
- compileall and `git diff --check`: PASS;
- fixtures prove replay, existing-claim linking, missing review/attribution/provenance
  blockers, capture hold/quarantine blockers, media-resolution blockers, ambiguous
  duplicate fail-closed behavior, written/media separation and legacy direct regression.

Isolated MiniPC proof:
- `dp117_canary` was built from the pre-DP-117 schema; the migration applied and replayed
  idempotently;
- runtime tracer executed written CREATE -> written replay -> legacy exact
  LINKED_EXISTING -> media CREATE; results were 3 promotion receipts (2 CREATED, 1
  LINKED_EXISTING); written had 1 text provenance / 0 segments, media had 0 text provenance
  / 1 canonical segment, the legacy Atomic Claim remained a single row, and seeded
  Evidence/APPROVED claim-evidence remained unchanged with 0 Verification and 0 Finding;
- separate `dp117_compat` tracer first created a direct legacy Atomic Claim, then ran the
  promotion-ready curated adapter against the same source proposition; it produced one
  Capture, Passage, StatementCandidate, ClaimCandidate and one LINKED_EXISTING promotion
  targeting the original claim; replay returned all corpus records as EXISTING and
  `PROMOTION_REPLAYED`; final count remained **1 Atomic Claim**, with 0 Evidence / 0
  Verification / 0 Finding. Both canary schemas were dropped.

Production proof:
- pre-migration state: 49 Content / 0 Claim Candidates / 30 Atomic Claims / 28 text
  provenance / 0 claim segments / 17 Evidence / 9 APPROVED claim-evidence / 9 Verification
  / 9 Finding / 2 PUBLISH / 49 review events;
- full AtomicClaim+provenance+segment+evidence+finding digest before migration:
  `b42cb16e274d3dfa02e6a9a5741dfb92`;
- pre-migration backup `20260929T095515Z`: readable 10,057,800-byte dump;
- migration applied with `ON_ERROR_STOP` and replayed idempotently; promotion ledger began
  empty and all legacy counts plus the digest remained identical;
- production canary created one written and one media candidate, promoted each exactly
  once, then replayed each to the same target/provenance receipt; during the canary
  Evidence stayed 17, APPROVED claim-evidence 9, Verification 9, Finding 9 and PUBLISH 2;
- canary cleanup removed all source/person/content/candidate/promotion/claim/review residues
  and restored the exact digest `b42cb16e274d3dfa02e6a9a5741dfb92`;
- final MiniPC suite: **822/822 PASS**; core benchmark **5/5**; corpus search benchmark
  **13/13 Recall@5**, p95 57.203 ms;
- post-migration backup `20260929T100422Z`: readable 10,062,374-byte dump, 10 valid sets
  retained, manifest includes `claim_candidate_promotion=0`, `claim_candidate=0`,
  `atomic_claim=30`, `evidence=17`, `finding=9`.

No existing Garlasco Atomic Claim was destructively rewritten and no public side effect was
introduced. New curated-written data should use the promotion-ready adapter when capture
provenance is available; historical manifests remain a compatibility/replay path only.
