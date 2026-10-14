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

## Owner round aggiuntivo — 13 ottobre 2026

Q3 richiede filtri per esito verificato della specifica proposizione, non giudizi sulle persone. Esiti non verificati/insufficienti/conflittuali/non-fattuali rimangono distinti e non diventano falsità. Q6 sintesi breve e limiti immediatamente visibili, prove e spiegazione completa raggiungibili; nessuna nuova verifica o pubblicazione attestata.

Decisione/ricerca futura registrata: nessuna implementazione o acceptance nuova, status e criteri originali invariati.

## 2026-10-14 — Private requirement-profile research batch (source-only)

A bounded, opt-in private `requirement_research_batch_v1.py` now composes the
existing per-claim `verification_requirements_v1.py` preflight into a
**deterministic multi-claim research worklist**, without any source body,
provider call or new claim outcome. Every item is bound to an exact input
preflight fingerprint and reports the claim kind, available *operator-declared*
eligible/excluded evidence IDs, current preflight state, exact gap codes and
typed next steps. Distinct required evidence roles, original-root and
source-family independence, mirrored bytes, legal jurisdiction, dates,
unreviewed/withdrawn source use and contradictory observations produce
separate private tasks. Explicit `NON_FACTUAL`, unknown profile, no run,
conflict and checkable-but-not-verified states never turn into a verdict.

Inputs are bounded to 32 claims / 512 metadata evidence rows; mismatched
claim keys, duplicate claim IDs, untyped dictionaries (including private
body fields), list/tuple schema mismatches and excess inputs fail closed.
Deterministic sorted replay produces the same exact fingerprint independent
of claim/evidence input ordering. A source-rights revocation changes only the
affected claim plan and batch fingerprint; no historical Finding/public
projection is overwritten. RED: the new module was absent and the seven
new feature tests failed; GREEN: **25/25** combined DP-314 new/existing
requirement tests PASS. No source identity signer, actual rights decision,
model adjudication, gold challenge, live operator queue or cost is inferred.

This is a **new executable private planning seam**, not a factual verifier,
real-world legal review, accepted rights grant, persistence, provider
integration or production release. DP-314 remains **IN PROGRESS**;
AC-314.1–.6 stay unchecked pending qualified source, evidence and physical
MiniPC acceptance.

An independent read-only reviewer detected a **P2 planning completeness** gap:
`NOT_CHECKED` returned only `START_RESEARCH_RUN` even if existing evidence was
REVOKED/PENDING, independent roots were missing, or required roles uncovered.
The exact case was reproduced RED. The private worklist now retains that run
state **and** surfaces all independently assessed rights/role/lineage tasks,
without launching research or inferring a source approval. New adversarial
RED→GREEN regression verifies withdrawal during a not-started run. This
source-only fix and the original requirement preflight receive another review
before integration; it changes neither the Status nor any original AC.

**Independent post-fix reviewer result:** worker-1, strict read-only, PASS
within source-contract scope. Independently verified **34/34** DP-314
requirement and adjacent wave tests and **11/11** private adversarial
states: NOT_STARTED with all rights revoked, no evidence or pending review;
late/jurisdiction-mismatched sources, coupled root/family roles, conflicts,
nonfactual/unsupported profiles, and separately eligible evidence. A rights
withdrawal changes the affected preflight and overall batch hashes while
`NOT_CHECKED` stays distinct from factual insufficiency. Invalid external
review statuses fail closed. No source body, provider call, public/rights
authority, or factual verdict was observed. Prime's broader targeted matrix
**45/45 PASS**, benchmark **5/5** and Python compilation PASS. This is not
an independent qualified editorial gold-data assessment and does not
complete DP-314.6 or any original AC.

**Final source-branch validation:** one complete Python unittest discovery on
the final `requirement_research_batch_v1.py` + new eight-test regression diff:
**3,447/3,447 PASS**, exit code 0, **355.615 s**. Adjacent DP-314 and
verification-runtime targeted subset **45/45 PASS**, deterministic benchmark
**5/5 PASS**, Python compilation and `git diff --check` PASS. No production
database, external provider, live source capture or real rights approval used
by this branch; the established PostgreSQL tests run in their disposable
fixtures only. All original DP-314 acceptance gates remain open.

## 2026-10-14 — Private requirement-batch change detection (additional feature)

New opt-in `requirement_research_delta_v1.py` compares two strictly typed,
bounded metadata worklists produced by the DP-314 private requirement planner.
It verifies **both canonical batch fingerprints and separately supplied
expected pins** and rechecks the batch's own digest and row counts. It reports
`UNCHANGED` versus `RECHECK_REQUIRED`, with exact added, removed and changed
claim IDs, evidence ID **eligibility losses/gains**, and typed manual follow-up.
A disappearing claim is never assumed closed; changed source SHA invalidates
the old worklist even if the preflight category is unchanged, and other claims
stay byte-equivalent. No action/research run is triggered.

This is **reconciliation**, not a revocation listener or approval ledger:
eligibility loss does not assert an actual provider revoke, and a correct SHA
is not an authenticated source, rights or reviewer credential. The outputs
remain private with `verdict=None`, `publication_authority=False`,
`source_approval_authority=False`, zero provider calls/source bodies. Bounds
are 32 claims and 512 metadata evidence IDs per batch, with no HTTP, DB,
LLM, source-body, provider, public route or editorial publication calls.

Initial **RED**: seven new tests failed because the source module did not
exist; subsequent **GREEN** exercised exact replay, rights withdrawal,
provenance-only drift, added/removed claims, cross-claim isolation and
malformed metadata. An independent **read-only** reviewer found a genuine P2:
caller-rehashed arbitrary `state`/`next_steps` strings could be reflected in
a delta despite zero source-body-count metadata. The source now accepts
only the canonical preflight state enum and planner's typed action vocabulary;
adversarial tests rehash the malicious strings and assert fail-closed.
The independent reviewer repeated the original repro after the correction:
**PASS**, no remaining reproduced P1/P2 in the bounded source scope.

After correction, **53/53** targeted DP-314/verification runtime tests,
deterministic benchmark **5/5**, Python compilation and `git diff --check`
PASS. The complete Python suite and branch delivery are recorded separately.
Original **DP-314 remains IN PROGRESS**, all AC-314.1–6 unchanged and OPEN;
no MiniPC, real-source, legal/rights, challenger or public-corpus acceptance.

**Final source-branch full suite:** one `PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=poc python3 -B -m unittest discover -s tests -q` run on the new
delta source with adversarial test returned **3,455 tests, OK, exit 0
(359.355 s)**. This synthetic suite includes disposable test fixtures; it
is not a production DB or live provider readback. The independent worker-2
ran 42 focused source/preflight/wave tests and benchmark 5/5 and rechecked
both self-rehashed malicious metadata probes: `DELTA_BATCH_INVALID` on each,
with **no remaining P1/P2 reproduced** in the private delta contract.

## 2026-10-14 — Private cross-claim research recheck queue

New offline `requirement_research_wave_v1.py` and adversarial fixture tests
consume two **separately SHA-pinned, validated** DP-314 metadata batches via
the canonical `compare_research_batches` consumer. The bounded deterministic
owner-only queue prioritizes evidence eligibility loss, deleted claims,
changed requirement profiles, changed preflight inputs, and new claims.
Each entry contains only canonical claim/evidence IDs, typed manual
`next_steps` and a direction explicitly labelled **NOT a provider revocation**
or source permission. A claim removed from the worklist remains a review
task, not silently completed. Shared eligible evidence IDs across two
claims generate a **reuse warning**, never independent corroboration.

Initial real test **RED** (new module unavailable) then GREEN. Source-only
adversarial review found another concrete **RED**: concurrent requirement-
profile change and evidence eligibility loss showed only the loss, concealing
the independent need to re-review the profile. The planner now queues both,
in bounded priority order; combined new/adjacent DP-314 tests **23/23 PASS**.
The return type always has `private_only=True`, zero source bodies/provider
calls, `verdict=None` and no factual, rights, reviewer or publication
authority. Expected SHA values must come from independently controlled owner
state, not caller-rehashed input. The new output is **not a source approval,
source scraper, scheduled research operation, or authorized public record**.

The older independent PASS of DP-314 batch/delta source does **not** apply
automatically to this new wave module. Independent final reviewer status is
tracked separately; physical MiniPC, legal/rights/source authority and all
original DP-314 AC remain OPEN, ticket Status stays IN PROGRESS.

**Independent reviewer P2: simultaneous eligibility turnover.** Worker-9
reproduced a canonical DP-314 change losing `evidence:alpha` and gaining
`evidence:gamma` for the same claim; the first queue showed the loss but
silently omitted the independent manual check of the newly eligible gamma.
Deterministic RED asserted both evidence IDs and `NEW_EVIDENCE_ELIGIBILITY`.
The corrected planner emits distinct human-review steps for both directions
and does not suppress a simultaneous changed requirement profile.
New and adjacent DP-314 tests **24/24 PASS**; neither newly eligible source
nor repeated evidence IDs constitute independent corroboration, source
approval, factual verification or publication. Final independent re-review
of the patched source remains separately tracked.

**2026-10-14 follow-up independent P2: batch after-validation TOCTOU.**
Worker-9 showed that an inherited `PrivateResearchBatch` subclass could
return its canonical `items` during the upstream delta SHA/preflight checks
and then replace `next_steps` on a later read, causing an unreviewed private
action marker to appear in the priority queue despite unchanged externally
expected pins. A new deterministic subclass reproducer first **RED** (queue
accepted the modified DTO); `plan_research_wave` now requires exact typed
immutable `PrivateResearchBatch`/`ResearchGapItem` fields and snapshots both
batches via deep copy **before** any SHA validation or later use. Only those
copies feed `compare_research_batches` and subsequent action/reuse/queue
reads. The old mutable subclass now refuses `WAVE_BATCH_INVALID`.
Targeted new and adjacent tests **25/25 PASS**; status IN PROGRESS and all
original DP-314 acceptance remain unchanged. This is a private contract
security fix, not proof of authorized sources, legal/factual verification,
provider behavior, editorial rights, or physical MiniPC readiness.

**Independent final read-only re-review:** worker-9 replayed combined loss `evidence:alpha` and gain `evidence:gamma` with exact two priority buckets, plus simultaneous changed requirement profile. Its extended DP-314 test subset **50/50 PASS**, no further P1/P2 reproduced in this bounded private metadata source contract. The reviewer did not edit code, Git, sources, provider or host. Eligible evidence IDs never attest independent corroboration, source rights, verified facts or editorial publication; original DP-314 AC remain OPEN.

**Final codefreeze validation:** combined source-only Python full suite with final DP-320/DP-440/DP-439/DP-314 file byte identity **3,503/3,503 PASS, exit 0, 306.597 s**; deterministic benchmark **5/5 PASS**, Ruff/format PASS; research-wave+adjacent DP-314 targeted **24/24 PASS**, independent reviewer 50-case source subset PASS. Simultaneous alpha loss/gamma gain is now visible with separate review steps. The prefinal whole suite was intentionally interrupted exit143 after a subsequently fixed security finding and is not claimed as PASS. Original status and AC remain open, source rights/provider/physical checks unproven.

**Definitive combined source-only validation (2026-10-14):** one completed full Python suite on detached clean main with 15 exact byte-identical source/test files for DP-314/320/439/440 and new private DP-231: **3,517/3,517 PASS, exit 0 in 299.292 seconds**. New+adjacent DP-314 **25/25 PASS**, deterministic benchmark **5/5 PASS**, Ruff check/format PASS. Reviewer independently reproduced the mutable batch subclass P2 before the RED→GREEN source fix; only an actual independent re-review of that final exact code, not this author's tests, can clear the reviewer gate. All original DP-314 Status/AC remain unchanged and physical/rights/editorial/MiniPC/provider acceptances remain OPEN.

## 2026-10-14 — Private requirement-profile transition snapshots (independent additive lane)

The new opt-in `private_requirement_profile_transitions_v1.py` accepts bounded
canonical `RequirementClaim` and `RequirementEvidence` declarations (at most
32 claims, 512 total evidence rows and 128 per claim). It deep-snapshots **exact
typed** input dataclasses and dictionary rows before canonical preflight or
digest, sorts IDs deterministically, and binds each claim's full policy,
proposition SHA, source provenance, rights/review declarations, profile/rule,
cutoff and preflight to a private snapshot SHA. Comparisons require **two
separately held expected SHA pins** and recompute canonical preflight,
profiles, row SHA and batch SHA before producing any result. An SHA is integrity
metadata, not authenticated identity, provenance or source clearance.

The change planner distinguishes added and removed claims, requirement-profile
changes, changed claim inputs, preflight state/reasons, evidence bytes/role/root
or other metadata, source-use and evidence-review declaration changes, and
**simultaneous** eligible ID losses and gains. All changed claims remain manual
recheck tasks; disappearing claims are not silently resolved, and a new
eligible evidence ID is never automatically approved. Explicit external
authority gates remain required for source rights, independent evidence
review, fact verification and publication. Outputs have `verdict=None`,
`private_only=True`, no source bodies/provider calls, no source approval,
fact/Finding or publication authority, regardless of caller-declared
`APPROVED` statuses. Opaque IDs only; no provider/source fetches, persistence,
public routes, adjudication, or machine-authority replacement.

**RED → GREEN source-only proof:** the 13 new canonical-fixture and adversarial
tests first produced `ModuleNotFoundError` for the absent source module;
after implementation and deterministic defensive input validation they
passed **13/13**. Joined with existing canonical DP-314 preflight, batch,
delta and wave tests they passed **56/56** (2026-10-14, Mac source host).
Cases include same-state source bytes/policy drift; simultaneous profile
change and evidence eligibility loss/gain; caller object mutation after
snapshot; stale independent pins; forged, self-rehashed preflight eligibility;
malformed/unbounded inputs; non-factual and unsupported kinds. Scoped Ruff
check and format checks PASS. This additive lane has **not** established real
rights authorization, independently attested reviewer/source provenance,
source gold/factual assessment, MiniPC operation, provider/billing approval,
public projection or original DP-314 acceptance. **Status: IN PROGRESS;
AC-314.1–6 remain unchecked.** Independent diff review and any broader
source-branch integration checks are separate.

**2026-10-14 — Post-review independent and combined codefreeze receipt.**
Reviewer `worker-9` performed an actual strict READONLY review against the
committed new profile transitions source/test (`787acf2076d21691545a8e84a119b3e5fe463b39`,
parent `cd4a5ff595e772ad61690c6eb289cc030429382b`), with no edits or
provider access: new **13/13**, all DP-314 **64/64**, external SHA pin and
self-rehashed eligibility forgery rejected, rights/reviewer/profile/evidence
transitions and private metadata non-echo checked; **no new P1/P2 reproduced
in this bounded source-only scope**. The final 30-file detached cross-lane
overlay (byte-identical to the published source/test files) completed its
**single post-review Python full suite: 3,572/3,572 PASS, exit 0,
384.450 seconds**. Benchmark deterministic 5/5 and scoped new-source Ruff
lint/format PASS. One inherited DP-314 research-batch test retains a historic
Ruff F401 unused import in the broad overlay; do not call that global Ruff
invocation PASS. Combined source manifest SHA-256:
`15badae206c51cfda9976c86d8eaf6fce10b0e8ccc3ff12480a376db21d3320f`.
The full suite emitted ResourceWarnings on temporary fixture resources but
finished OK. Not PR CI or physical, editorial, owner/source-rights, real
factual adjudication, MiniPC or provider acceptance. **Status IN PROGRESS,
AC-314.1–6 still unchecked**, no merge/publication/production write.
