# DP-316 — Machine verification authority, review migration e eligibility per risultato

Status: IN PROGRESS
Milestone: M3 — editorial, correction, privacy, and legal policy
Depends on: DP-308, DP-309, DP-310, DP-311, DP-229, DP-301, DP-304, DP-314, DP-321

## Problem
 Attualmente HIGH/LEGAL richiede human_review/dual_control e per ogni classe publication replay attested reviewer. L'owner ha **zero editor testuali ordinari** e sceglie autonomia futura. Convertire `human_review_approved` in boolean machine, due bot names, o permettere `READY` caller-supplied invaliderebbe la sicurezza del DONE precedente.

## Outcome
 Un percorso *machine-authorized* versionato che distingue model generation, independent evidence gathering, challenge, verifier, bounded safety/privacy/rights/legal applicability, signing/persisted authority, final eligibility e publication trigger dopo acceptance; produce per record `ELIGIBLE`, `HOLD`, `NEEDS_EXTERNAL_DECISION`, `RECHECK` con prove riproducibili e conserva legacy review fino al cutover ufficiale.

## Traceability & constraints
 R11/R13/R14/R21/R25/R39; Q14/Q18. No routine text editor; **qualified counsel/owner decision** su source-family, policy e deployment non è machine approval. Nessuna auto-publication prima del rollout governato.

## Scope
 Versioned `MachineAuthorityProfile` per claim type/risk class/required evidence/challenger/gold gate/actor identity and key authority; immutable approved observation set, rule+model+prompt hashes, blind evidence independence, policy decision refs, rights, quote/source/context/person, challenger and correction state -> deterministic replay of attested machine decision in separate private ledger with signer, fencing token/sequence and exact record/material hash -> publication eligibility composed with DP-308/309/310/311 boundaries → future gated per-result trigger. Distinguish `machine_evidence_signoff`, `machine_verdict_signoff`, `eligibility`, `legal_owner_signoff`; two evaluations are *not* two human reviewers. Preserve audit of rejected alternative/support/counterevidence, no private leakage. Define migration policy ADR for replacing old human-only gate; dual-read old/new only when versioned profile explicitly authorized; no unreviewed legacy auto-upgrade.

## Non-goals
 No impersonated reviewers, magic confidence clearance, legal certification by model, privilege-bearing public accounts or arbitrary model prompt selecting release policy.

## Dependencies and sequencing
 Fase 0 policy/authority/schema and adjudication gold; fase 2 private full slice; fase 3 isolated MiniPC fence/canary and owner release acceptance in D; routine publication activation explicitly future. DP-307 independent external gate for affected public use and risk family.

## Acceptance criteria

- [ ] `AC-316.1`: No arbitrary model output, caller boolean, manual DB edit, forged signer/key/event ID or two responses from one model grants eligibility; missing exact off-DB authority or qualified decisions hold.
- [ ] `AC-316.2`: For each enabled claim/risk class, sealed machine receipt binds all load-bearing input versions, primary/independence set, completed challenger, procedure/rights/privacy, rule/model/prompt/policy and publication eligibility version.
- [ ] `AC-316.3`: Legacy human-path publication still behaves as proven until deliberate versioned cutover; after cutover old events cannot auto-authorize a new machine policy and vice versa. Replay/rollback prove holds on schema migration.
- [ ] `AC-316.4`: High-risk processual case with accepted jurisdictional/qualified policy, proper official source and no conflicting information can traverse autonomous pipeline in isolated acceptance; allegation-only, missing waiver, wrong identity, absent challenger or unresolved legal decision cannot.
- [ ] `AC-316.5`: Concurrent evidence update/rights revoke/correction/new challenger/corpus supersession invalidates readiness atomically at eligibility/write and publication read: no TOCTOU window accepted without formal fence DP-320.
- [ ] `AC-316.6`: Versioned golden-reference and false-verdict/false-attribution/abstention gates and cost/health telemetry are satisfied on representative mixed claims before any feature flag eligible on MiniPC; absent gold remains NO-GO, no fabricated thresholds.
- [ ] `AC-316.7`: Release receipt records owner-authorized per-result activation scope; test source→public projection→correction/retraction readback and rollback at current MiniPC runtime; public reader never receives internal review/model/person scores.

## Validation / proof
 Red team direct SQL/status/signature replay, same-key reviews, participant correlation and shared evidence family; mixed automated procedural/legal, historical and numeric corpus; mandatory failure-mode table; actual MiniPC end-to-end rehearsal after policy/signoff.
## Documentation, data, and migration impact
 ADR explicitly superseding applicable human-only default in PRODUCT/AGENTS/ADR 0001 (prime owns), additive attestation/ledger or alternate existing authority reuse with verified signature sequence; external DP-307 register unchanged until duly decided.
## Completion receipt
**2026-10-11 local source-only *preflight*, not a machine authority — IN PROGRESS.**
`machine_authority_preflight_v1.py` models immutable policy/profile, role-bound
exact material/epoch hashes, independent generator/challenger root identifiers,
per-record risk-class consistency and a checked DP-320 *structural* fence.
It integrates current DP-314 requirement, DP-308 publication safety and DP-309
high-risk result types for conditional HOLD/RECHECK/NEEDS_EXTERNAL_DECISION.
It rejects claimed approvals, same-generator/challenger, stale materials,
revoked rights and missing material roles. **Even its coherent synthetic case
never signs off**: `machine_signoff`, `publication_authority` and
`dispatch_authorized` are always false. The existing DP-310/311 human-only
policy and production gate remain untouched. Focused negative/source-only tests
run locally; no signed off-DB machine principal, qualified accepted policy,
authenticated independent gold, MiniPC transaction fence, legacy migration or
real high-risk pilot exists. Therefore all AC-316.1–.7 remain unchecked.
