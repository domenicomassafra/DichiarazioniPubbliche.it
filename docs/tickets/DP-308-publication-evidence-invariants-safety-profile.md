# DP-308 — Publication evidence invariants and fail-closed safety profile

Status: DONE
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

- [x] **AC-308.1:** One versioned evaluator composes every applicable load-bearing proof
  class and returns explicit reason codes; there is no numeric safety score.
- [x] **AC-308.2:** Direct quote, paraphrase and translation records require different
  appropriate invariants and cannot masquerade as one another.
- [x] **AC-308.3:** A verified factual claim with invalid quote/speaker/context provenance
  remains non-public; truth verification cannot compensate for attribution failure.
- [x] **AC-308.4:** Correct attribution with insufficient/conflicting DP-215 evidence cannot
  produce a stronger factual Finding.
- [x] **AC-308.5:** Direct DB/status tampering cannot bypass missing review/provenance;
  projection-time revalidation omits the record.
- [x] **AC-308.6:** Changing any load-bearing hash/version/review makes the previous safety
  receipt stale and blocks projection until re-evaluated/reviewed.
- [x] **AC-308.7:** Rights/privacy/legal holds dominate eligibility and cannot be converted
  to warnings by a caller.
- [x] **AC-308.8:** Public output exposes only bounded method/reason metadata approved by
  schema; private notes and raw bodies remain private.
- [x] **AC-308.9:** DP-223 adversarial benchmark is a mandatory regression input and passes
  with zero known false public attribution/fabricated quote.
- [x] **AC-308.10:** Full suite, benchmark, schema/migration replay and MiniPC canary prove
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

Local `publication-safety-v1` now freezes the test-first evaluator contract while upstream
dependencies are still closing. It consumes explicit upstream proof states and a bounded set
of load-bearing hash/version/review references; it returns only `ELIGIBLE`, fail-closed
dispositions and ordered reason codes, with no numeric safety/trust score. Direct media
quotes require exact-wording + transcript-verbatim proof, translations require translation
review, and paraphrases cannot inherit direct-quote requirements/authority. Missing
speaker/origin/context/identity proof blocks even when verification/finding review passes;
missing evidence suitability or citation assurance also blocks. Privacy, rights and challenge
holds always yield `POLICY_HOLD`. The receipt binding changes when any caller-supplied
load-bearing reference changes.

AC-308.5 is closed by the production projection-time revalidation boundary described below;
AC-308.8 is closed by the public schema/serializer allowlists plus public-projection leak
regressions for raw transcript/evidence bodies, private wording/reviewer data and unbounded
method metadata. AC-308.9 is closed by the
standard deterministic contributor acceptance path: it unconditionally executes the DP-223
offline benchmark CLI, whose own release gate requires zero known false public attribution
and zero fabricated public quote and returns non-zero on failure. AC-308.10 still waits for
integration, replay and MiniPC proof. The additive `publication-eligibility-v1` composition
seam now makes DP-310 review separation load-bearing for `HIGH/LEGAL` candidates without
introducing a dependency cycle: it recomputes review completeness from exact review events and
binds the safety/high-risk/review receipts before returning only
`ELIGIBLE_FOR_PROJECTION_REVALIDATION` or a hold. Neither evaluator is a second Finding and
neither publishes anything by itself.

Projection integration audit 2026-10-06: the current repository does not yet expose a complete
persisted/current input contract from which `public_projection.py` can truthfully rebuild
`PublicationSafetyInput` and the DP-309 decision. The projection query can recompute several
provenance, attribution, citation and verification facts, but it has no authoritative per-record
DP-304 privacy/public-interest decision, no DP-305 versioned rights decision with permitted use,
expiry and review binding, and no persisted DP-309 reviewed risk packet/qualified-policy decision
covering source framing, sensitivity/minor-victim signals, official-record scope, jurisdiction
and effective time. The previously missing canonical Finding `record_version` producer is now
provided privately by `finding-record-version-v1`; it does not make those policy inputs exist and
does not itself authorize projection.

These gaps cannot be filled by mapping legacy status columns or caller booleans to `PASSED`.
The persisted projection acceptance fixture demonstrates the problem directly: it remains
projectable with `evidence.rights_status = 'UNKNOWN'`, which DP-305 explicitly says cannot grant
public rights. The focused ephemeral-PostgreSQL proof for that baseline path is **1/1 PASS**.
That audit captured the pre-wiring state. The follow-up now consumes those exact inputs plus the
canonical record-version producer during projection-time revalidation; no fail-open compatibility
path was added. At that receipt stage AC-308.10 remained open for the required full-suite/replay/MiniPC proof.

Finding record-version follow-up 2026-10-06: `finding_record_version.py` now computes
`finding-record-version-v1:<sha256>` only from current persisted state. Its scope is deliberately
finding-level: the Finding envelope and publication/policy/version fields; the linked verification
run's versioned/input/result references; the selected `finding_evidence` edges; and the Finding's
assertion/citation identities, versions and stored binding references. It hashes current assertion
text separately from the stored assertion hash so a direct text-only database rewrite cannot keep
the same version. Set-like verification evidence/observation references are canonicalized, making
replay deterministic rather than row/order dependent.

The record version does **not** decide whether the referenced source/evidence/provenance is still
valid. Current source/capture/transcript/quote/speaker/context/identity state, evidence freshness
and suitability, privacy, rights and policy/challenge holds remain DP-308 safety inputs; DP-309
risk/policy inputs retain their own binding. This separation means a change to an evidence body's
current hash or rights state does not redundantly change the Finding record version, while changing
which evidence/assertion/citation the Finding binds does. Disposable PostgreSQL proof is **5/5
PASS** and the existing DP-310 control/eligibility/persistence regression set is **34/34 PASS**.

Production projection follow-up 2026-10-06: the CLI now builds through
`ProductionPublicProjectionStore`, which treats the existing SQL projection as a candidate finder
and revalidates each candidate before serialization. The boundary recomputes the current canonical
Finding record version, replays the current DP-304 privacy decision against the current normalized
text, requires current non-expired DP-305 rights decisions, consumes the DP-303 challenge hold,
replays the current hash-bound DP-309 reviewed packet, and finally requires DP-310 durable review
through the DP-311 off-DB reviewer authority. Privacy, rights and high-risk review actors are fed
into DP-310 separation checks. Missing authority or any missing/stale/tampered proof omits the
candidate. A disposable-PostgreSQL acceptance fixture proves that a legacy DB-approved candidate
still returned by `projectable_findings()` is omitted by the production projection when those
current private gates are absent. Focused validation for the composed publication boundary is now
**139/139 PASS** across publication safety/eligibility/review/authority, public
projection/persisted tamper and projection-time hold/revalidation tests. At that receipt stage AC-308.10 remained open
for the required full-suite, benchmark/schema-migration replay and MiniPC canary.

Final closure receipt at clean HEAD `5a86666b` (2026-10-06): AC-308.10 is satisfied. The clean
archived commit passes the complete local suite **1720/1720**, deterministic benchmark **5/5**,
and focused DP-223/projection/citation set **22/22**. An isolated MiniPC `/tmp` archive of the
same commit passes the combined M3 safety/review canary (**346 tests**) plus benchmark **5/5**;
the PostgreSQL-backed classes initially skipped because `initdb/pg_ctl` were outside the SSH PATH
were rerun with `/usr/lib/postgresql/18/bin` and passed **69/69** against disposable PostgreSQL.
Temporary trees were removed; no production DB/provider was used. This closes engineering only
and does not answer Q-306 or DP-307.
