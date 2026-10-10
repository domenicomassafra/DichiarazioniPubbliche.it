# DP-314 — Verificatore fattuale generalista per claim type e requirement profile

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-215, DP-224, DP-226, DP-227, DP-228, DP-229, DP-312

## Problem
 `verification_runtime.verify` copre numeri, serie storiche e match testo/legal-status; proposizioni su eventi, sequenze, negazioni storiche e causalità circoscritta non sono trattate come classi fondate su evidenze con conclusioni autonomamente riproducibili. Un LLM che attribuisce un boolean non è una review.

## Outcome
 Un `VerificationRequirementProfile` versionato per classe di claim collega scope, validità temporale, evidence roles/independence, primary record e controprove a verifica autonoma e output strutturato, con no-check/insufficient/conflict/unsupported distinct e confidence/coverage solo interna calibrata.

## Traceability & constraints
 R12/R13/R15/R21/R23/R39; Q9, Q14, Q18. Factual check ≠ autenticità della citazione e ≠ publication approval. `OUTDATED_DATA` non è retroactive falsity; different opinion non è errore fattuale.

## Scope
 Claim type and adjudicable proposition/negation/time/location/jurisdiction -> select current DP-215 requirements -> bounded DP-228 research with primary/independent roles -> verify approved observations/contradictions and challenger material -> append-only decision with claims/evidence hashes, role, rule/model/prompt/requirement versions, source independence, cutoff and limits -> Finding candidate only if eligible, otherwise reasoned insufficiency/unknown. Distinguish `NOT_CHECKED` (no completed run), `CHECKED_INSUFFICIENT_EVIDENCE`, `UNRESOLVED_CONFLICT`, `NON_FACTUAL`, `CHECKABLE_PENDING`, `SUPPORTED`, `FACTUALLY_FALSE` mapping to canonical statuses without misrepresenting implemented enums. Deterministic computations remain the authority for exact arithmetic; model assists source interpretation with adversarial corroboration, not sole truth.

## Non-goals
 No universal verdict without evidence, no guarantee 100% across all domains, no person scoring or instant verdict on newly discovered sources.

## Dependencies and sequencing
 DP-215 roles and approved source-use prerequisite; DP-313 process input; DP-315 denial subtype; DP-316 final machine authority; D budget/retry and C consumer. External primary material and qualified decisions block only relevant family/public outcome.

## Acceptance criteria

- [ ] `AC-314.1`: Claim-type registry includes class→required evidence roles, scope/time compatibility and conflict rules; unsupported class yields explicit `NOT_CHECKABLE_PROFILE_UNAVAILABLE` with no verdict.
- [ ] `AC-314.2`: Event/sequence, documentary legal status, factual denial, numeric and factual text comparisons use independent proof paths; original date cutoff honored; later outcome explicitly separate.
- [ ] `AC-314.3`: One secondary article or duplicated wire copies cannot satisfy two-family threshold; unapproved source, wrong jurisdiction/time, missing primary record or contradictory evidence cannot yield SUPPORTED/FALSE.
- [ ] `AC-314.4`: No retrieval attempt vs attempted-and-insufficient vs conflicting vs purely expressive stance produce distinct persisted reason codes and public-safe labels downstream.
- [ ] `AC-314.5`: Exact replay over same immutable inputs yields same outcome; changed evidence/rule/model/source/policy hashes stales approvals, schedules bounded reanalysis and never silently overwrites Finding history.
- [ ] `AC-314.6`: False verdict, false attribution and abstention are counted separately in DP-321; high-risk case must pass attested challenger B-229 and machine authority DP-316 before future MiniPC public candidate readback.

## Validation / proof
 Blind heterogeneous annotated claims with supporting/refuting/ambiguous variants, source family derivations, temporal changes; checker receipt includes source locator and exact approving evidence, withheld checks are measured as abstentions. MiniPC isolated integration then qualified real-source pilot.
## Documentation, data, and migration impact
 Versioned requirement/rule registry; expand existing verification ledger with optional fields or new narrow attested result, retain old numeric-v1 runs and API compatibility with explicit migration.
## Completion receipt
**2026-10-11 — partial opt-in source-only implementation, NOT a Finding:**
`verification_requirements_v1.py` provides a bounded `VerificationRequirementProfile`
registry for EVENT_SEQUENCE, DOCUMENTARY_LEGAL_STATUS, FACTUAL_DENIAL,
NUMERIC and FACTUAL_TEXT_COMPARISON. It checks caller-declared source-use and
review statuses, roles, date cutoff, jurisdiction, independent original roots
and duplicate source bytes. It distinguishes NOT_CHECKED, NON_FACTUAL,
NOT_CHECKABLE_PROFILE_UNAVAILABLE, CHECKED_INSUFFICIENT_EVIDENCE,
UNRESOLVED_CONFLICT and CHECKABLE_PENDING. No outcome maps to a factually
SUPPORTED/FALSE verdict: the preflight does not verify original provenance,
reviewer identity, source rights, semantic independence, a mathematical rule,
or challenger truth. The existing numeric/text verifier is not replaced.
Input snapshots are deterministic but not cryptographically authenticated.
**10/10 synthetic focused tests PASS; 19/19 existing verification runtime
regressions PASS**, Python compile and diff check PASS. External genuine
source lineage/rights, durable append-only decisions and MiniPC pipeline,
independent blind gold/DP-321, DP-316 authority and DP-229 challenger proof
remain missing. **All AC-314.1–.6 remain unmarked** pending complete evidence.
