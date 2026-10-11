# DP-418 — studio candidate promotion cluster review

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-117, DP-212, DP-414

## Problem

Matching/promotion decisions are too consequential to live only in logs or implicit model output.

## Outcome

Implement a candidate review surface that compares source wording/passages, normalized proposition, match candidates, cluster features and promotion blockers before an explicit approve/link/create/reject action.

## Scope

- Side-by-side source context + candidate proposition + candidate existing claims/clusters.
- Expose supporting/contradicting match features and algorithm/version; do not render score as truth confidence.
- Promotion action calls DP-117 and displays durable receipt/result.
- Rejection/hold/split-cluster actions preserve candidate history.

## Non-goals

- No person/source trust score.
- No one-click auto-publish.
- No equivalence approval based solely on vector similarity.

## Dependencies and sequencing

DP-117, DP-212, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-418.1:** Reviewer can distinguish duplicate extraction, same proposition, related proposition and uncertain cases.
- [ ] **AC-418.2:** Promotion blocker is visible before mutation.
- [ ] **AC-418.3:** Replay/refresh shows the persisted decision, not reconstructed model state.
- [ ] **AC-418.4:** Keyboard and 200% zoom workflow remains operable.

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

Private Studio review UI; promotion service is backend authority.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Persisted match-run read-only inspection — 2026-10-08

`studio_candidate_review.py` reads an existing DP-212 `candidate_match_run`
and its persisted `candidate_match_result` rows using the canonical
`CandidateMatchingStore.get_run/load_results` methods. It requires an exact run
and candidate binding, completed state, bounded count, valid fingerprint,
deterministic rank and match class/disposition consistency. It returns only
bounded IDs, match classes and feature **codes**, never raw match features,
private candidate/source text, numeric similarity scores or reviewer notes.

The response explicitly states `currentness=UNVERIFIED`,
`review_authority=false`, `publication_authority=false` and
`promotion_enabled=false`: a persisted matching suggestion is **not** a
currentness decision, review decision or promotion permit. No database mutation,
cluster materialization, HTTP endpoint or public build change is introduced.

This is an internal read-only prerequisite, not the completed DP-418 workflow.
The authenticated private Studio UI, exact source/passage comparison, blocker
before mutation, canonical currentness/authority checks, review/approval replay
and keyboard/MiniPC acceptance all remain open. Synthetic focused tests cover
normal, missing/stale/conflicting and private-feature-leak paths.

Follow-up 2026-10-08: persisted match-run inspection now has a token-
authenticated local read-only HTTP/HTML transport with PostgreSQL
transaction-level read-only enforcement and bounded network/DB timeouts.
No write endpoint exists. Matching currentness and reviewer authority
remain unverified, so the UI cannot promote, accept or merge candidates.

### 2026-10-09 persisted match-read binding and safe feature semantics

The read-only inspector now checks deterministic DP-212 run/result
identities against the requested candidate, run, target type and
target ID. It rejects duplicate targets, noninteger/boolean ranks,
unrecognized matching methods and unexpected structured feature
codes before returning a private Studio suggestion. Existing
ClaimType/temporal-scope contradiction codes can force `HOLD`
even when lexical similarity yielded `SAME_PROPOSITION`; the
inspector refuses a persisted `PROPOSE_CLUSTER` in that case.
This keeps the audit from repeating altered suggestion rows as if
they were valid matching output. Focused RED→GREEN tests exercise
cross-run IDs, retargeting and conflicting scope, with the actual
DP-212 matching algorithm remaining authoritative.

`currentness=UNVERIFIED`, `review_authority=false`,
`publication_authority=false` and disabled promotion are
unchanged. No persisted review mutation, source rights, real
MiniPC match canary, keyboard workflow or authority acceptance
is introduced; DP-418 stays IN PROGRESS.

### 2026-10-09 Wave 14 — persisted matching version and result-state binding

The read-only Studio inspector displayed the current `matching_version`
constant without validating `candidate_match_run.matching_version` or
each persisted `candidate_match_result.matching_version/status`. A stale
row could therefore appear to use the current algorithm even when it did
not. The SQL reader now returns these actual persisted fields and the
inspector refuses missing/mismatched versions and non-`CANDIDATE` status
before presenting a suggestion. Six adversarial RED subtests became
GREEN. Its output still declares `currentness=UNVERIFIED`, no reviewer
or publication authority and disabled promotion. This is not real
reviewer authorization or a closed DP-418 runtime acceptance.

### 2026-10-09 Wave 19 — stored class feature integrity

The read-only inspector previously checked known feature code names,
match class and method, but not whether the classifier's persisted
explanatory feature signature actually justified that class. An altered
row could show SAME_PROPOSITION without exact normalized or lexical/context
support, DUPLICATE_EXTRACTION without same-selector support, or another
class without its canonical evidence code. Duplicated codes and mutually
inconsistent ClaimType/time evidence were also accepted.

The narrow fail-closed check follows the existing deterministic DP-212
classifier without reprocessing private source words. Duplicate requires
same selector and exact normalized text; exact same proposition requires
exact normalized text; lexical same proposition requires high overlap
plus shared entities or topics; related, different and uncertain require
their own primary supporting/contradicting codes. Duplicate and
contradictory feature codes are refused. Eight adversarial RED subtests
and seven canonical positive signatures became GREEN.

This validates persisted feature codes, not the underlying private
text, mutable feature values, reviewer currentness, cluster equivalence
or authority. No score, source body, promotion, cluster write or public
output is exposed. DP-418 stays IN PROGRESS.

### 2026-10-10 — Currentness/blocker and persisted handoff readback

The operator-local authenticated `/v1/candidate/review-readiness` exposes
the existing deterministic DP-212 input/result replay and current DP-117
promotion blockers **before mutation**. Optional read-only
`/v1/candidate/handoff-receipt` loads an immutable previously enqueued
candidate review request from an explicitly configured owner-private 0700
spool, enforces exact Candidate/Run binding, and redacts reviewer identity
and credential references. It cannot approve, promote, record a decision
or claim persisted request currentness; the spool defaults to disabled.
Mac full test suite 2266/2266 and isolated MiniPC focused 44/44 passed;
benchmark 5/5. No live candidate/match/capture data is present on MiniPC.
Actual reviewer decision readback, rights and keyboard/200% acceptance
remain open; no AC is marked complete by this metadata-only prerequisite.

### 2026-10-10 — persisted review-currentness and duplicate classification guard

DP-117's persisted preflight and each promotion mutation previously used
`EXISTS(review_event ... action='APPROVED')`, which treated an old approval
as current even when a later REJECTED or QUARANTINED event existed. The
canonical context and all three SQL mutation branches now require the
**latest event by `created_at DESC, id DESC`** for the exact candidate or
statement identity to be APPROVED. The preflight propagates this state to
Studio blockers and remains a read-only preview until DP-117 revalidates.

Matching an identical normalized proposition is insufficient to prove the
same source extraction. The preflight exposes it as
`same_proposition_target_ids`, separately from approved, matched
`DUPLICATE_EXTRACTION` cluster edges. A same-proposition target now blocks
promotion with `PROMOTION_SAME_PROPOSITION_REVIEW_REQUIRED`, and the
`LINKED_EXISTING` mutation refuses the previous exact-wording shortcut or
SAME_PROPOSITION cluster edges. New-claim mutation SQL continues to refuse
creation while a known equivalent or duplicate target exists. Studio displays
the distinction and refuses a direct `REVIEW_LINK` handoff for a mere
SAME_PROPOSITION model suggestion; review request storage remains private
and grants no promotion/review/publication authority.

Persisted promotion replay now checks its exact candidate ID, promotion
version, deterministic receipt/key, selected provenance channel, candidate
status/target and a single bounded provenance reference before returning an
existing receipt. Inconsistent rows report `PROMOTION_REPLAY_CONFLICT`.

Focused tests cover revoked approvals, same-proposition preflight, replay
conflicts, Studio blockers and review-link handoff refusal. Two tests on an
isolated real PostgreSQL database using `db/schema.v1.sql` confirm the
latest persisted review actions and the actual distinction between exact
proposition and reviewed duplicate cluster members.

These changes are prerequisites only. Original AC-418.1–AC-418.4 stay open:
the reviewer still lacks the full authenticated compare/decision workflow,
the complete channel/rights blocker preview, independently persisted human
decision readback, and measured 200%-zoom/keyboard acceptance. Concurrent
review-event writers are not serialized with all DP-117 SQL transactions;
the statement snapshot checks the latest committed event visible when its
query starts, and additional transaction-authority design is still needed
before claiming a universal race-free legal/human approval gate. No MiniPC
live runtime acceptance or public enablement is asserted.

## Post-grilling planning reconciliation — 2026-10-10

Keep IN PROGRESS: existing private reviewer read model, latest events and dry-run have not completed AC-418.1–.4. DP-242 owns Studio source-to-candidate machine handoff; DP-316 owns attested machine authority, DP-320 owns revocation and DP-312 preserves quotation/reporting meaning. A candidate decision is durable and provenance-versioned; machine path must never be written as a human reviewer signoff. Race with changed source/rights or revoked permission HOLDS before promotion; real authorized MiniPC positive/negative and accessibility proof still required. Planning-only delta; no new AC marked complete, no production or provider mutation.

### 2026-10-11 second-wave — scoped currentness/preview identity fence

The existing read-only `/v1/candidate/review-readiness` path correctly replayed
the DP-212 input fingerprint and all matching results but did not verify that
the **reloaded MatchingInput** still identified the requested Claim Candidate,
nor that the separately persisted DP-117 promotion context belonged to that
exact Candidate **and Content**. A foreign promotion context containing a
plausible candidate state, reviewer flags and private passage could therefore
yield `currentness=CURRENT` and `review_queue_eligible=true` for the wrong
Content. This would also taint the private passage references and review
handoff context digest, without granting actual DP-117 approval.

The inspector now requires a `CLAIM_CANDIDATE` MatchingInput whose member ID
equals the requested candidate and whose Content ID is a valid identifier.
It also requires the promotion context's `candidate_id` and `content_id` to
match that exact input **before** inspecting its blockers, passage references
or review eligibility. Cross-identity input/context refuses the read with a
stable private validation error; the authenticated local HTTP handler maps
this to a generic 422. Missing context still follows the existing explicit
`PROMOTION_CONTEXT_UNAVAILABLE` blocker, and legitimate exact-bound reads
remain unchanged. All flags granting review, promotion or publication
authority remain false.

Adversarial **RED**: five failures across two tests proved that foreign or
missing Candidate/Content bindings and a forged deterministic match run
carrying another Candidate's MatchingInput were accepted without error.
**GREEN**: the same cases are refused; an exact-bound case remains CURRENT
and private-review eligible. A further regression proves a credentialed
`submit_candidate_review_handoff` cannot write an owner-private queue entry
with a foreign Content context. The existing handoff/machine-preview callers
continue to revalidate the exact input before any handoff. This is a local
source/test improvement, not a claim of live persisted MiniPC currentness.

Validation receipt: `PYTHONPATH=poc python3 -m unittest
tests.test_studio_candidate_review tests.test_studio_candidate_review_handoff
tests.test_studio_local_api tests.test_dp242_studio_machine_handoff
tests.test_dp242_studio_machine_http tests.test_candidate_matching
tests.test_claim_promotion -q` — **111 tests PASS**. `python3 -m
compileall -q poc tests`, Ruff lint on the two source/test files, and
`git diff --check` pass. The optional full-file Ruff formatter check was
already failing for both files at the unedited HEAD; no unrelated
mass-formatting was introduced. No full-suite/production acceptance is
asserted from the focused check.

**AC-418.1–.4 remain OPEN.** Full reviewer source/wording/cluster comparison,
persisted human decision with latest-event authority and replay, channel and
rights revalidation at the mutation boundary, real candidate source/capture,
keyboard/200%-zoom acceptance and MiniPC proof are not established by the
new guard. No promotion, review decision, publication, schema migration,
production mutation or remote deployment was performed.

### 2026-10-11 — Independent persisted-target source comparison read model (post-`aca8809`)

New **read-only functional operator comparison** in
`studio_candidate_review_ui.py`, without changing the canonical
`studio_candidate_review.py` inspector or any DP-117 mutation:
`build_candidate_comparison_read_model(match_store, promotion_store,
target_source_store, run_id, claim_candidate_id)` and a static local
`render_candidate_comparison_workspace`. It reuses the persisted DP-212
run/results and canonical DP-418 `inspect_candidate_review_readiness`
to recompute exact current matching input/result identity, matching
algorithm version, rank, feature-code semantics and promotion blockers.
For **each** target, the separate read-only `source_context(type,id)`
interface retrieves its persisted Content, Passage, Capture/version SHA,
rights and capture-hold status; the model verifies that the target read
matches the current exact DP-212 target Content and provenance key and
that the candidate's own Passage/Capture matches the separately persisted
DP-117 candidate context. It reads match/context and target sources again
before returning, refusing observed drift between the two read rounds.
Only safe IDs, source hashes, feature **codes**, algorithm and operator
actions appear in the model and HTML; no raw original/proposition text,
scores, secret feature values, arbitrary provider result or promotion call.

The operator sees distinct `DUPLICATE_EXTRACTION`,
`SAME_PROPOSITION`, `RELATED`, `UNCERTAIN` (and `DIFFERENT`)
with matching methods and supporting/contradicting codes. Existing
DP-117 pre-promotion blockers remain visible before any mutation.
Missing target source is an explicit unavailable/blocked comparison;
revoked target rights, held candidate Capture, source/version drift and
cross-Content/Passage substitution cannot become usable comparisons.
An additional concrete **RED→GREEN** security case showed that a
DP-212 `DUPLICATE_EXTRACTION` on the same Content/Passage was displayed
as usable despite an independently read target **different Capture
version**. The new `BLOCKED_DUPLICATE_CAPTURE_MISMATCH` prohibits
equating those extraction versions until Capture ID and hash match.
The classifier's same-proposition label is never used to bypass that
independent source-version test.

The NEW `tests/test_dp418_comparison_next.py` contains **7** adversarial
focused methods: canonical persisted DP-212 run/result fixtures
(synthetic store, not a live PostgreSQL readback) for same/related/
uncertain, rendered Capture→Passage comparison, foreign Content/
Passage/target identity, revoked rights and candidate hold, missing/stale
source, same-selector-but-different-Capture duplicate, in-flight rights
changes, and forged stored method/feature/algorithm version. The new
interface initially failed import **RED**; the Capture-version case
subsequently reproduced a concrete incorrect usable classification
**RED**, then both were **GREEN**. Final local command:
`PYTHONPATH=poc python3 -m unittest
tests.test_dp418_comparison_next tests.test_studio_candidate_review
tests.test_studio_candidate_review_handoff tests.test_studio_local_api
tests.test_candidate_matching -q`: **67/67 PASS**.
`ruff check`, `ruff format --check`, targeted Python `compileall`
and `git diff --check` PASS. Only this UI module, its new test and
the original DP-418 ticket were modified.

The source-reader interface is **not wired to a trusted real PostgreSQL
target-Capture/rights reader yet**; source state and rights are
caller-supplied test readbacks, **not** independently certified licenses,
review authority or transactionally fenced results. All
`review_authority`, `equivalence_approved`,
`promotion_authority` and `publication_authority` flags remain false;
no reviewer/promotion action, database writes, network provider, MiniPC,
deployment, commit or push was made. **Status IN PROGRESS, original
AC-418.1–.4 remain unchecked**: live persisted source-compare integration,
full channel/rights/currentness gate at the mutation boundary, durable
qualified review decision/replay and keyboard/200% zoom acceptance on
actual Studio/MiniPC are still required.

### 2026-10-11 — Independent, genuinely persisted PostgreSQL target source reader

Follow-up strictly limited to **NEW**
`poc/dichiarazioni_pubbliche/studio_candidate_target_pg.py`, **NEW**
`tests/test_dp418_target_source_pg_next.py` and this original ticket.
`StudioCandidateTargetPg.source_context(member_type, member_id)` now fulfills
the already-established optional DP-418 `PersistedTargetSourceReader`
interface for the subset of **Claim Candidate** targets with an explicitly
persisted, source-exact parent Passage. This is a *functional independent*
PostgreSQL readback, not a second fake read model derived from the match
results. A single bounded query joins `claim_candidate` (exact requested ID)
→ its exact-Content `statement_candidate` →
`statement_candidate_passage` (true persisted Statement/Passage FK) →
same-Content `passage` whose ID **equals**
`claim_candidate.metadata.parent_passage_id` → same-Content immutable
`content_capture` ID and SHA-256 → `content_item` rights. The query
requires a real written Capture Passage and eligible candidate/statement
states; missing target, forged parent, unrelated or other-Content Passage,
missing edge, unsupported media-only Passage, or nonunique/invalid results
cannot turn into a positive readback. The caller receives only target
type/ID, Content/Passage/Capture IDs, exact Capture SHA-256, effective rights
status and persisted Capture/hold status. It never reads/returns source URLs,
titles, private quote/body text, metadata values other than the exact
parent-Passage selector, match scores, actor names or provider receipts.

The reader uses a PostgreSQL **read-only session** with bounded query/
connection timeouts and generic DB error messages even if supplied an
otherwise privileged DSN. A real separate `SELECT`-only database role is
covered by the tests. Each call re-reads mutable Content/Capture rights
and Capture holds; `APPROVED` is **not** converted into `CLEARED` and hard
`DENIED`/`REVOKED`/`EXPIRED` overrides clearance. Only explicit `CLEARED`
on **both** persisted Content and Capture yields that *recorded state*.
No such state attests legal source-use permission or grants reviewer,
equivalence, promotion or publication authority. An unsupported
`PURGE_PENDING` Capture returns unavailable rather than masquerading as
`CAPTURED`. A source-rights change between the two independent reads of
the existing `build_candidate_comparison_read_model` rejects the complete
comparison (`DP418_COMPARISON_CHANGED_DURING_READ`). This is a read-model
drift check, **not** a cross-connection atomic snapshot or mutation permit.

**Important explicit schema limitation:** DP-212's canonical
`CandidateMatchingStore.load_targets` uses for `ATOMIC_CLAIM` a
`claim_segment.segment_id`, `claim_text_provenance.id` or bare Claim ID
as `provenance_key`. The canonical schema does **not** link those keys
directly to a versioned written Passage+Capture. Even a promotion receipt
does not establish that a specific Passage is the target Claim's recorded
provenance. Hence `source_context('ATOMIC_CLAIM', ...)` deliberately returns
**unavailable**, making DP-418 block the comparison rather than invent a
Claim→Passage edge or manufacture a Capture. Claim Candidates without the
explicit metadata parent and real Statement Passage edge similarly remain
unavailable. No matching, provenance, schema, API or Studio UI code was
rewritten to hide this gap.

**TDD / actual local proof:** the new test first failed **RED** on the missing
adapter import, then **GREEN** against a genuine disposable PostgreSQL
initialized from canonical `db/schema.v1.sql`, with synthetic Content,
Capture, written and media Passages, Statement/Claim Candidates, recorded
promotion and source-proof records, a separate `SELECT`-only role, and
real rights/hold changes. It rejects absent/foreign target IDs, forged
parent pointing to other Content or a same-Content Passage with no FK,
unavailable Atomic claim, improper status and ambiguous/fabricated response,
DB write attempts even under privileged DSN, and privacy leakage. The
unchanged `build_candidate_comparison_read_model` is exercised directly
with the *real* target reader and a canonical validated synthetic match-run
fixture: missing clearance stays `BLOCKED_TARGET_SOURCE_RIGHTS`, explicit
current source rights permit **only** `OPERATOR_COMPARE_PENDING` (not an
editorial or equivalence decision), and actual rights revocation during the
second target read fails closed. These are local fixtures, **not** a real
persisted DP-212 match-run readback or production rights evidence.

Focused command:
`PYTHONPATH=poc python3 -m unittest tests.test_dp418_target_source_pg_next
tests.test_dp418_comparison_next tests.test_studio_candidate_review_handoff -q`
**22/22 PASS**. Ruff lint/format checks, Python compileall and scoped Git
diff-check are retained in the final worker validation receipt. No production
DB, MiniPC, provider, account, review/promotion decision, commit, push or
deployment. **DP-418 stays IN PROGRESS; original AC-418.1–.4 all OPEN**
pending actual target/atomic lineage coverage, authorized original-source
rights and context, durable approved decision/replay, local UI accessibility
and real MiniPC source-to-reader integration proof.

Final extended read-only/source acceptance run also includes
`tests.test_studio_candidate_review`, `tests.test_candidate_matching` and
`tests.test_studio_capture_selectors_pg` alongside both DP-418 suites and the
handoff tests: **53/53 PASS** with canonical disposable PostgreSQL. Both new
files pass `ruff check` and `ruff format --check`; `python3 -m compileall -q
poc tests` and scoped `git diff --check` PASS. This does not claim that
external authorization, a production match run or MiniPC approval occurred.

### 2026-10-12 — opt-in persisted, attested Candidate decision CAS on disposable PostgreSQL

Added `studio_candidate_decision_store_pg.py` and
`tests/test_dp418_persisted_decision_pg_next.py`, with **no** Studio HTTP/UI
mutation, provider call, production schema migration, public route, or DP-117
promotion. An explicit `initialize()` provisions an isolated private
`dp418_candidate_decision` append-only table and UPDATE/DELETE rejection trigger;
this is an opt-in development contract until a reviewed additive migration and
operator privileges exist. Direct SQL `TRUNCATE` remains a privileged test cleanup,
not an asserted protection against a database owner.

`candidate_decision_request` binds exact Claim Candidate, **deterministic**
DP-212 MatchRun ID/version/input fingerprint, source Passage, Capture ID and
SHA-256, request key, reviewer actor, decision, expected revision and optional
link target. `StudioCandidateDecisionStorePg.record()` requires the **existing**
DP-310 `LocalFileReviewerIdentityAuthority`, an active local credential and a
real off-database attestation resolving the caller-provided integrity-checked
`PublicationReviewEvent`. Event record ID and version bind the exact
candidate and hashed request, including decision, revision and source selectors;
actor, credential fingerprint, stage/role and action must match. Unverifiable,
revoked or mismatched reviewer credentials **HOLD** without writing.

The PostgreSQL transaction serializes writes by Candidate with an advisory
lock, takes row locks on current Candidate, Statement, Passage, Content,
Capture and MatchRun and then performs a **fresh statement-level rights and
lineage check** before conditional insert. It requires eligible statuses,
parent Passage/Statement edge, exact Capture hash, `CLEARED` Content **and**
Capture rights, `NONE` hold, latest Capture observation, a completed correct
matching run and consistent result count/version/status. `REVIEW_LINK` needs a
specific persisted `DUPLICATE_EXTRACTION` Claim Candidate target;
`REVIEW_CREATE` is held when duplicates or same-proposition matches already
exist. CAS on the latest decision revision yields one winner across competing
reviewers; the unique request key supports identical replay or explicit
idempotency conflict. The historical readback returns persisted decision,
version and receipt hash even if rights have since changed, explicitly marked
`historical_only` and with all promotion/equivalence/publication flags false.

Initial TDD RED was missing module import. An isolated PostgreSQL initialized
from `db/schema.v1.sql` then proved real concurrent reviewers (one created,
one revision conflict), signed receipt replay after process/store restart,
privileged UPDATE rejection, revoked Capture rights and credential HOLD,
foreign Passage and reviewer-event HOLD, source-version drift, matching-target
binding and a **live transaction lock-wait with concurrent rights revocation**.
These fixtures use isolated synthetic Candidate/MatchRun/rights/reviewer
material, not actual real-source legal rights or MiniPC authority.

**AC-418.1–AC-418.4 remain OPEN.** This is durable private *review intent*,
not a canonical Claim review event, evidence approval, cluster equivalence
approval, or execution of `promote_claim_candidate`. The existing DP-310
publication-review attestation binds reviewer identity to a supplied event;
it is not a newly approved DP-418 editorial role assignment. Current DP-212
input fingerprint is matched to the persisted run but not independently
regenerated transactionally from every mutable matching input. There is no
cross-database atomicity with local credential revocation, no real qualified
authoritative reviewer signoff, full comparison/UI workflow or keyboard/200%
zoom evidence, nor a MiniPC real-corpus acceptance. In particular, positive
fixture receipt creation must **not** be interpreted as current-source-use
authorization or publication readiness. Ticket remains **IN PROGRESS**.

**Recorded local validation for this wave:** initial import RED, then
`PYTHONPATH=poc python3 -m unittest tests.test_dp418_persisted_decision_pg_next -q`
**7/7 PASS** (canonical disposable PostgreSQL and local authority receipts).
Focused cross-module PostgreSQL/comparison/review-handoff/matching/reviewer
identity and publication-review regression **61/61 PASS**. `ruff check`,
`ruff format --check` on the two new files, `python3 -m compileall -q poc tests`,
`git diff --check` and benchmark **5/5 PASS**.

The concurrent checkout full Python suite ran **3,090 tests with 3 errors**,
none originating in this DP-418 adapter: `test_conditional_surface_absence`
(two tests) and `test_launch_preflight` (one test) failed with
`CONDITIONAL_PRIVATE_STUDIO_PATH_SCOPE_CHANGED`. Read-only inspection found
the concurrently integrated DP-416 `/v1/collections/navigate` route in
`studio_local_api._ALLOWED_PATHS` but absent from the independent explicit
`conditional_surface_absence._PRIVATE_STUDIO_READ_PATHS` inventory. Prime was
informed; this worker cannot change DP-416 or its unrelated guard paths.
The full run is explicitly **not green** until owner reconciles this new route
and reruns the affected checks. No deployment or production mutation.
