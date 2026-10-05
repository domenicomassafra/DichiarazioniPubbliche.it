# DP-308 — Publication evidence invariants and fail-closed safety profile

Status: FUTURE
Milestone: M3 — Editorial, correction, privacy, and legal policy
Depends on: DP-215, DP-216..DP-224, DP-301..DP-305

## Problem

The repository already separates retrieval, approval, verification, finding review and
publication, but the new attribution hardening must converge into one explicit publication
contract. Otherwise each pipeline component can be locally correct while the final public
projection accidentally accepts a record whose quote, speaker, identity, context, rights
or evidence state is incomplete.

A numeric/model confidence score is not a substitute for proof. The publication decision
must answer a finite set of evidence questions with inspectable pass/hold reasons.

## Outcome

Create a versioned **Publication Safety Profile** consumed by finding review and public
projection. For each public record it composes the required proof classes and records a
deterministic eligibility result without becoming a second Finding or a mutable
`publish=true` authority.

For the relevant record type, the gate must be able to require:

- immutable source/capture identity;
- DP-216 source-bound exact wording when represented as a quote;
- DP-217 transcript-verbatim eligibility for media quotes;
- DP-218 approved speaker-span coverage;
- DP-219 original-vs-reported speech integrity;
- DP-220 context-integrity approval;
- DP-221 wording/translation type integrity;
- DP-222 stable Person identity/role-at-time integrity;
- DP-224 material-assertion citation assurance;
- DP-215 evidence suitability and independence requirements;
- DP-304 privacy/minimization decision;
- DP-305 rights/excerpt decision;
- verification/finding review state; and
- correction/reply/takedown holds.

## Scope

- Define a versioned rule/profile, reason codes and deterministic evaluator.
- Revalidate at projection time under ADR 0001. Persisted eligibility may be a receipt or
  cache, never sole authority.
- Distinguish `ELIGIBLE`, specific `HOLD_*`/`MISSING_*`, `STALE_*`, and policy-blocked
  outcomes. Do not collapse them into a 0–100 score.
- A profile may vary by surface/record type (direct quote, paraphrase, translated wording,
  factual Finding, legal-status claim) but may not silently relax a required proof.
- Staleness propagates when any load-bearing source, transcript, person, context, evidence,
  rights, review or policy version changes.
- Public projection must omit/hold records whose required invariants are not all satisfied.
- Studio/operator UI may explain missing gates and next actions without exposing private
  bodies or legal notes.

## Non-goals

- No universal trust/reliability/confidence score.
- No automatic truth verdict from publication eligibility.
- No replacing Finding review, rights review or qualified legal decisions.
- No fail-open `warning` mode for attribution/provenance failures.

## Acceptance criteria

- [ ] **AC-308.1:** One versioned evaluator composes every applicable load-bearing proof
  class and returns explicit reason codes; there is no numeric safety score.
- [ ] **AC-308.2:** Direct quote, paraphrase and translation records require different
  appropriate invariants and cannot masquerade as one another.
- [ ] **AC-308.3:** A verified factual claim with invalid quote/speaker/context provenance
  remains non-public; truth verification cannot compensate for attribution failure.
- [ ] **AC-308.4:** Correct attribution with insufficient/conflicting DP-215 evidence cannot
  produce a stronger factual Finding.
- [ ] **AC-308.5:** Direct DB/status tampering cannot bypass missing review/provenance;
  projection-time revalidation omits the record.
- [ ] **AC-308.6:** Changing any load-bearing hash/version/review makes the previous safety
  receipt stale and blocks projection until re-evaluated/reviewed.
- [ ] **AC-308.7:** Rights/privacy/legal holds dominate eligibility and cannot be converted
  to warnings by a caller.
- [ ] **AC-308.8:** Public output exposes only bounded method/reason metadata approved by
  schema; private notes and raw bodies remain private.
- [ ] **AC-308.9:** DP-223 adversarial benchmark is a mandatory regression input and passes
  with zero known false public attribution/fabricated quote.
- [ ] **AC-308.10:** Full suite, benchmark, schema/migration replay and MiniPC canary prove
  the evaluator and projection behavior.

## Validation / proof

Build a matrix over quote/speaker/context/identity/evidence/rights/privacy/review states,
including direct persistence tampering and stale-version cases. Run standard repo checks,
DP-223, isolated database replay, public-bundle leak scans and MiniPC read-back.

## Documentation, data, and migration impact

Update ADR 0001 only if needed to name the frozen profile/evaluator seam. Keep `PLAN.md`
as sequencing authority and `CONTEXT.md` as vocabulary authority. Any persisted receipt is
append-only/versioned and must not become a shortcut around projection revalidation.

## Completion receipt

Pending DP-216..DP-223 and M3 policy integration.
