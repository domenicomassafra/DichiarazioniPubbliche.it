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

## 2026-10-11 — Independent source-family fence (local follow-up)

The existing private preflight counted two differently named `primary_root_ref`
values and distinct bytes as a complete two-source research proposal even if
both came from the same `source_family_ref` (such as two articles from one
publisher family). A new test reproduced **RED**: those records incorrectly
produced `CHECKABLE_PENDING`. The preflight now separately enforces both
the original-root count and the source-family count, returning
`INDEPENDENT_SOURCE_FAMILY_MISSING` and
`CHECKED_INSUFFICIENT_EVIDENCE` for the duplicate family.

The new regression is **GREEN**: the DP-314 suite plus existing verification
runtime tests pass **30/30**, scoped Ruff F821 and `git diff --check` PASS.
This local fixture does not authenticate caller-supplied source-family
identities or confer a factual verdict, reviewer authority or publication
eligibility. Real approved source lineage, benchmark, durable ledger and
MiniPC acceptance remain outstanding. All original acceptance criteria
remain unchecked; **Status: IN PROGRESS**.

## 2026-10-11 — Bounded private deterministic event-sequence comparison

The earlier DP-314 module stopped at eligible evidence-role preflight. It
could not compare an actual proposition such as event A occurring before
event B, even when immutable source observation identifiers and their dates
were supplied. A new opt-in `compare_private_event_sequence` now accepts
`SequenceEventObservation` records with an exact `evidence_id`, matching
`evidence_sha256`, event reference and day-precision occurrence date. The
comparison explicitly binds to the existing claim, policy, original source
root, source-family, role, statement-time and rights/reviewer *declared*
preflight. Both events need a PRIMARY_RECORD and an INDEPENDENT_RECORD from
at least two distinct roots and source families each. Evidence observed only
after the statement, outside jurisdiction, after its own publication date,
or with nonapproved rights cannot make the comparison computable.

If both event dates have independently labeled agreement, the pure rule
reports `OBSERVATIONS_AGREE` or `OBSERVATIONS_DISAGREE` relative to the exact
BEFORE/AFTER proposition. Disagreeing source dates yield
`UNRESOLVED_CONFLICT`, insufficient source roles/families produce
`CHECKED_INSUFFICIENT_EVIDENCE`, and no completed run remains `NOT_CHECKED`.
Events on the **same calendar day** do not prove either order: a separate
RED→GREEN regression forced `CHECKED_INSUFFICIENT_EVIDENCE` with
`SAME_DAY_EVENT_ORDER_UNRESOLVED` instead of a spurious contradiction.
Unsupported claim kinds remain `NOT_CHECKABLE_PROFILE_UNAVAILABLE`.

Input-order-independent snapshot SHA-256 binds preflight, question, policy,
evidence hashes and event dates; exact replay has the same typed private
result. This is a **deterministic comparison of caller-supplied observation
declarations**, NOT a verified factual outcome. There is no independent
authentication of approved source rights, observation provenance, reviewer
identity, immutable database storage, challenger evidence, or gold truth.
Result properties remain `verdict=None`, `source_proof_attested=False`,
`finding_authority=False`, `publication_authority=False` and `private_only=True`.
It never creates a Finding, changes a public projection, fetches a provider,
or grants a machine publication signoff.

RED: the test suite initially could not import the missing event-sequence API;
a second regression reproduced false ordering confidence when two separately
observed events shared one date. GREEN: focused DP-314 + adjacent DP-316
**31/31 PASS**, existing verification test files **34/34 PASS**;
`python3 -m compileall -q poc tests` and `git diff --check` PASS.
All fixtures are synthetic, no MiniPC/production write, provider charge,
commit, push or deploy. **AC-314.1–.6 remain unchecked, ticket IN PROGRESS:**
real independently approved immutable observations, original source-use,
documentary legal status/factual denial production paths, durable append-only
result ledger, calibrated blind DP-321, qualified DP-229 challenger and
DP-316 machine authority plus MiniPC public candidate readback are absent.

## 2026-10-12 — Jurisdiction and unsupported-profile fail-closed preflight

An independently reproduced legal-status defect admitted a primary legal
record tagged `jurisdiction:fr` for a claim whose jurisdiction was `None`:
the previous preflight returned `CHECKABLE_PENDING` because it compared
jurisdictions only when the *claim* jurisdiction was truthy. A record with
`jurisdiction_ref=None` reproduced the same false eligibility. A completed
documentary legal-status preflight now requires an explicitly specified
claim jurisdiction. Missing scope yields `LEGAL_JURISDICTION_UNSPECIFIED`,
excludes the evidence declaration, and reports
`CHECKED_INSUFFICIENT_EVIDENCE`; an explicitly matching legal jurisdiction
retains the existing private pending path.

A second regression found that an unsupported claim class with `NOT_STARTED`
masked the absent profile as `NOT_CHECKED`. The preflight now selects
`NOT_CHECKABLE_PROFILE_UNAVAILABLE` before handling the run state while a
supported class with `NOT_STARTED` remains `NOT_CHECKED`. Even a
caller-declared APPROVED evidence row for an unsupported class had previously
appeared in `eligible_evidence_ids`; it now appears among excluded evidence
with `PROFILE_UNAVAILABLE`, and non-factual sources are likewise marked
inapplicable to factual verification.

The new independent six-case regression produced three initial RED failures
and one further RED for the unsupported-class eligible-evidence leak, then
six GREEN results. Existing DP-314 regressions and adjacent DP-316
machine-authority tests also passed (22 + 15 tests).
No attested source jurisdiction/rights, claim semantics, date-effective legal
version, independent gold, authorized reviewer, durable ledger, provider,
or publication authority is created by these local source-only checks.
**All original AC-314.1–.6 remain open; status IN PROGRESS.**

## 2026-10-13 — Role-bound root/family independence (isolated worker follow-up)

Two new synthetic regressions exposed a further false `CHECKABLE_PENDING`:
the preflight counted two distinct roots and two distinct source families
separately while satisfying the required `PRIMARY_RECORD` and
`INDEPENDENT_RECORD` roles from overlapping combinations. For example,
`PRIMARY(root:a, family:a)`, `INDEPENDENT(root:b, family:a)`, and
`PRIMARY(root:b, family:b)` passed despite **no** primary/independent pair
having both distinct roots and distinct families. The private event-sequence
comparison likewise reported a computable date order when this invalid
combination appeared for one event and another event had valid records.

Both new tests reproduced **RED** on `83588bdb`: the preflight incorrectly
returned `CHECKABLE_PENDING`, and the sequence comparator incorrectly treated
the event observations as eligible. The narrow correction now requires a
role-covering assignment of independently rooted and independently familied
evidence, both at profile preflight and **per event**. Defective combinations
return `CHECKED_INSUFFICIENT_EVIDENCE`; the preflight also reports
`INDEPENDENT_ROLE_SOURCE_PAIR_MISSING` and the comparator retains its existing
`EVENT_INDEPENDENCE_MISSING`. Positive controls with a genuinely independent
record still yield `CHECKABLE_PENDING` and the expected *private observation*
comparison. The pre-existing cross-root identical-byte, source-rights,
review-approval, date-cutoff, jurisdiction, same-day ordering and
unsupported-profile fences remain in force.

**GREEN:** both new regressions, existing DP-314/DP-314 wave closure,
DP-316 authority and deterministic verification-runtime tests **60/60 PASS**;
scoped Ruff, Python compileall and `git diff --check` PASS. This is a
source-only synthetic correction in an isolated worktree, with no live source,
provider, database or publication proof. Declared source-family identities
are unauthenticated; external approved origins and immutable lineage,
review/rights authority, challenger/gold verification, append-only decisions,
MiniPC deployment and public readback are still absent. **AC-314.1–.6 remain
OPEN; Status: IN PROGRESS.**
