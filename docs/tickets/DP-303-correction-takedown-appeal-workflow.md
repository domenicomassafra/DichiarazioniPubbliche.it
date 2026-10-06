# DP-303 — Correction, takedown, and appeal public workflow

Status: IN PROGRESS

Milestone: M3

Depends on: DP-302; coordinate with DP-304, DP-305, and DP-506

Launch state: BLOCKED until the workflow, retention, notice, and appeal policy is
accepted by the owner and qualified Italy/EU counsel

This is a product and engineering workflow specification, not legal advice. The terms
“correction”, “takedown”, and “appeal” describe product events; they do not decide
whether any particular request is legally valid.

## Problem
  Correction and reply records already have an append-only, private-by-default
lifecycle, but there is no complete public workflow for a correction request,
a takedown/retraction request, or an appeal of a rejected or omitted submission.
Without explicit states and gates, an operator could silently delete a public
record, publish an unprocessed challenge, or let a submitter bypass review by
changing a status field.

## Outcome
  Specify a versioned, auditable workflow in which every challenge creates a new
append-only event and, when appropriate, a superseding Finding; a takedown can
temporarily omit public output without destroying history; and an appeal receives
an independent review without mutating the original decision. All public changes
remain gated by provenance, re-analysis, and explicit review.

## Scope
- Define product-level request categories, state transitions, authority, and public
  visibility rules for correction, takedown, and appeal.
- Reuse the existing `correction`, `right_of_reply`, `review_event`, Finding, and
  `reanalysis_trigger` seams where they fit.
- Define history preservation, stale-projection behavior, notice, retention, and
  operator controls.
- Define abuse, authorization, concurrency, and privacy requirements inherited from
  DP-302 and DP-304.
- Define tests, canary evidence, and the qualified questions carried to DP-306.

## Non-goals
- Implementing a public endpoint, moderation dashboard, notification provider, or
  deletion job in this ticket.
- Letting a requester directly edit or delete a Finding, evidence record, review
  event, transcript, or public projection file.
- Treating a right of reply as a correction or treating a correction as proof of
  intent.
- Making a legal determination about mandatory rectification, takedown grounds,
  notice periods, or appeal rights.
- Deleting immutable history to make a public surface appear clean.

## Current baseline
- `deterministic_correction_id` requires a distinct superseding Finding, a bounded
  reason, and bounded changed fields.
- `record_correction` requires a coherent same-claim `supersedes` chain and creates
  a `CORRECTION` re-analysis trigger.
- Correction publication requires both the previous and superseding Finding to have
  explicit `FINDING/APPROVED` events, a processed correction trigger, a leaf
  Finding, and a separate `CORRECTION/APPROVED` event.
- `public_projection.py` exposes a correction only when the chain, re-analysis,
  public visibility, and review event all pass; the static bundle removes stale
  projection-owned files.
- Right of reply is private until its own review and parent-Finding gate pass.

## Constitution and non-negotiable constraints
- **C-303-01 — Append-only history:** a material change creates a new version/event;
  it never silently rewrites or deletes the prior public record.
- **C-303-02 — Explicit authority:** intake, triage, review, publication, takedown,
  and appeal are separate actions with recorded actor, reason, policy version, and
  timestamp.
- **C-303-03 — No status-only authority:** `PUBLIC`, `PUBLISHED`, `RETRACTED`, or a
  manually edited status column never substitutes for the required review event
  and re-analysis result.
- **C-303-04 — No intent inference:** a correction or appeal may change an
  assessment or public version; it does not establish that a person lied.
- **C-303-05 — Private pending content:** request bodies, identity data, internal
  notes, and evidence candidates remain private until their own review.
- **C-303-06 — Reversible public omission:** an approved takedown may remove a
  current dossier from the public projection, but the durable record and audit
  trail are retained unless a separately authorized lifecycle decision says
  otherwise.
- **C-303-07 — Fair review separation:** an appeal should be assigned to a reviewer
  independent of the original decision where staffing permits; the system records
  the actor and separation, and never pretends independence that does not exist.
- **C-303-08 — Fail closed:** missing chain, stale provenance, failed re-analysis,
  or uncertain authority results in omission/hold, not a guessed outcome.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-303-01 | A correction is a new superseding Finding plus a private correction record; the prior Finding remains part of the public history. | Accepted product invariant |
| P-303-02 | A right of reply is a challenge/input to re-analysis, not a direct correction or takedown. | Accepted product invariant |
| P-303-03 | A takedown request is a request for a public-visibility hold, not an automatic deletion or automatic finding retraction. | Safe product default; owner/counsel confirmation required |
| P-303-04 | An appeal is a new review request against a prior rejection/omission; it cannot mutate the prior decision or automatically restore a record. | Accepted product invariant |
| P-303-05 | Public notices use the minimum wording and identifiers needed to explain a material version change; private reasons and raw submissions remain private. | Safe product default |
| P-303-06 | A reviewer may publish only a bounded, sanitized reason and changed-field summary approved for the public surface. | Accepted product invariant |
| P-303-07 | No response-time promise, legal SLA, or mandatory outcome is set until owner/counsel decisions are recorded. | Pending owner/counsel decision |
| P-303-08 | Repeated requests are linked and deduplicated, but each distinct substantive request remains auditable. | Safe product default |

## State and transition contract
  The following are the required logical states. An implementation may map names to
existing database values, but it must preserve these transitions and guards:

### Correction
  `PRIVATE_RECEIVED -> REANALYSIS_PENDING -> REVIEW_REQUIRED -> PUBLIC_VERSIONED`
or `REJECTED/QUARANTINED`.
  A public correction requires a distinct superseding Finding for the same claim,
valid `supersedes` chain, processed `CORRECTION` trigger, required Finding reviews,
and `CORRECTION/APPROVED`. A rejected or still-private correction does not change
the current public version.

### Takedown request
  `PRIVATE_RECEIVED -> TRIAGE_PENDING -> PUBLIC_HOLD_APPROVED` or
`REJECTED/REFERRED`.
  `PUBLIC_HOLD_APPROVED` removes the affected current public projection from the
public read model until an authorized outcome exists. It does not delete the
Finding, review events, evidence, reply, correction, or audit receipts. Any public
notice is separately reviewed and bounded.

### Appeal
  `PRIVATE_RECEIVED -> INDEPENDENT_REVIEW_PENDING -> UPHELD/OVERTURNED/NEEDS_INFO`.
  An upheld appeal creates a new review event and may trigger re-analysis or a
correction workflow. It does not edit the rejected event. An overturned appeal
retains the original decision and records the reason.

## Engineering requirements
- **E-303-01 — Explicit request records:** represent intake, triage, hold,
  reviewer decision, appeal, and publication as typed append-only records/events
  with request ID, target Finding/correction/reply ID, actor, timestamp, policy
  version, reason code, and safe metadata.
- **E-303-02 — Transactional gates:** transition a correction/takedown/appeal to a
  public state and write its review event in one PostgreSQL transaction. A failed
  transaction leaves the prior state and public projection unchanged.
- **E-303-03 — Chain validation:** correction creation rejects missing/cyclic/
  cross-claim `supersedes` links, non-leaf targets, and mismatched claim IDs.
  Takedown and appeal targets must resolve to the exact reviewed version they cite.
- **E-303-04 — Re-analysis linkage:** every accepted correction, reply, or appeal
  input that can change relevant evidence creates a deduplicated explicit trigger;
  publication requires the trigger to be `PROCESSED` and linked to the request.
- **E-303-05 — Freshness:** a review is invalid when the target Finding,
  verification input fingerprint, policy version, transcript segment, evidence set,
  or prior decision changes. The projection omits stale output until re-review.
- **E-303-06 — Public projection revalidation:** recheck request approval, target
  state, supersedes chain, processed trigger, redaction/rights policy, and review
  event at read time. Never trust a cached `public_visibility` value alone.
- **E-303-07 — Stale artifact cleanup:** a takedown/hold or failed freshness check
  causes regeneration to remove obsolete projection-owned files. Non-projection
  files and private operational records are not touched.
- **E-303-08 — Appeal separation:** capture original reviewer and appeal reviewer;
  require a different actor where the operator can provide one, and record an
  explicit exception when staffing makes separation impossible.
- **E-303-09 — Notice minimization:** public notice templates receive only a
  sanitized reason, dates, stable IDs, and a link/contact path approved by policy;
  internal notes, submitter identity, raw bodies, and evidence excerpts are excluded.
- **E-303-10 — Retention and hold:** preserve the complete event chain through
  review, appeal, and any legal/operator hold. Deletion requests follow DP-304 and
  cannot silently erase a public-history event.
- **E-303-11 — Authorization:** only authorized operator roles can triage, hold,
  approve, reject, or publish. A future HTTP surface must use the dedicated
  AuthN/AuthZ/CSRF work; intake cannot call these transitions directly.
- **E-303-12 — Abuse controls:** correction/takedown/appeal intake inherits the
  bounded request, rate-limit, dedup, URL, privacy, and incident controls from
  DP-302; repeated requests cannot create unbounded work or public noise.

## Qualified questions

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-303-01 | What public rectification, notice, response, and labeling duties apply to each Finding type and each jurisdiction? | Determines mandatory workflow and public copy. | Keep all requests private; no public notice beyond approved neutral history. |
| Q-303-02 | What grounds, evidence, and authorization are required for a takedown or public hold? | Determines whether a request can pause output and for how long. | Accept no automated takedown; hold remains disabled pending decision. |
| Q-303-03 | Must a submitter have an appeal route, and what independence, deadline, and disclosure rules apply? | Determines appeal states, reviewer roles, and notices. | Record appeals privately; do not promise a deadline or outcome. |
| Q-303-04 | What retention period or preservation duty applies to rejected, held, corrected, and appealed records? | Governs storage and deletion. | Retain minimally for audit; no destructive purge. |
| Q-303-05 | How should a public record communicate a takedown or retraction without exposing private or sensitive information? | Affects projection and public wording. | Omit current public output; use a generic notice only after review. |
| Q-303-06 | Does the service owe a source/author notification, and does that differ by reply, correction, or appeal type? | Affects workflow and audit metadata. | Do not promise notification; flag as a launch blocker. |

## Launch blockers
- **B-303-01:** No public correction/takedown/appeal route may launch until Q-303-01
  through Q-303-06 have an owner/counsel disposition.
- **B-303-02:** No direct status update, client-controlled visibility field, or
  delete operation may stand in for a review event.
- **B-303-03:** No takedown automation may remove history or publish a reason
  without an explicit authorized decision and a retained audit event.
- **B-303-04:** No appeal may be represented as successful until its own review and
  any required re-analysis are complete.
- **B-303-05:** The public projection must be able to omit a held/stale record while
  preserving prior approved versions according to the accepted policy.
- **B-303-06:** DP-304 privacy/retention and DP-305 rights gates must be closed for
  every field that can appear in a notice or correction.

## Acceptance criteria
- [x] **AC-303.1:** Correction, takedown, and appeal requests have distinct typed
  states and cannot satisfy one another's gates.
- [x] **AC-303.2:** A correction with a valid chain and complete reviews is
  projected as a new version while the previous approved version remains available
  according to policy.
- [x] **AC-303.3:** A correction with a missing/cyclic chain, unprocessed trigger,
  stale review, or missing `CORRECTION/APPROVED` event is omitted and does not
  mutate the prior version.
- [x] **AC-303.4:** An approved takedown removes the current projection-owned file
  after regeneration but retains the private Finding, event chain, and receipts.
- [x] **AC-303.5:** A takedown cannot be triggered by a public submitter, cannot
  delete arbitrary content, and cannot publish an unreviewed reason.
- [x] **AC-303-6:** An appeal creates a new event, records reviewer separation (or
  the explicit exception), and never edits the original decision.
- [x] **AC-303-07:** Replayed and concurrent requests are idempotent, bounded, and
  do not create duplicate triggers or public versions.
- [x] **AC-303-08:** Public JSON, JSON-LD, and HTML notices contain no private body,
  internal error, evidence excerpt, or unapproved identity field.
- [x] **AC-303-09:** Projection regeneration removes stale artifacts after a hold or
  correction and leaves non-projection/private files untouched.
- [ ] **AC-303-10:** A MiniPC canary exercises submit -> hold/review -> correction or
  appeal -> re-analysis -> public projection and verifies the actual resulting
  public/private state.

## Validation/proof
- **Focused workflow proof:** state-machine, chain, idempotency, concurrency,
  freshness, stale-artifact, authorization, and redaction tests.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **Runtime proof:** run an isolated canary on the MiniPC, inspect the private
  event chain, queue trigger status, public projection, and generated files, then
  remove only the canary data.
- **M3 packet check:** link Q-303-01..06 to DP-306 and carry accepted decisions to
  DP-307.

## Documentation/data/migration impact
- Document the public workflow, state transitions, role separation, retention, and
  incident response in the implementing change.
- Reuse the existing append-only correction/reply/review/reanalysis tables first;
  add only typed, bounded, additive fields or records if the approved workflow
  requires them.
- Any schema change must include replay-safe migration, compatibility fixtures,
  projection tests, and MiniPC migration proof.
- This specification does not implement a public route, delete data, or change
  production state.

## Completion receipt
  Pending implementation, security/privacy review, MiniPC proof, and qualified legal
closure. The current correction/reply runtime remains private and fail-closed.

---

## Implementation receipt — policy lane (2026-09-26)

Status: **append-only state machine implemented as a pure module; runtime wiring and
legal closure outstanding.**

### What was implemented

- `poc/dichiarazioni_pubbliche/policy/challenge_workflow.py` (new, pure/zero-I/O): the
  `ALLOWED_TRANSITIONS` table for CORRECTION / TAKEDOWN / APPEAL; `ALLOWED_ACTOR_ROLES`
  (a public submitter can only *initiate*); `evaluate_transition()` (fail-closed);
  `publication_authorized()` (never status-only, never implicit);
  `public_omission_required()` (reversible omission, not deletion);
  `NO_INTENT_DERIVATION` constant.
- `docs/policy/dp-303-challenge-workflow.md` (state machine, authority table, fail-
  closed table).
- `tests/test_policy_challenge.py` (36 tests).

### Extended, not forked

`correction_runtime.py` was **not modified**. The new module imports its
`deterministic_correction_id`, `deterministic_right_of_reply_id`, and
`MAX_CORRECTION_REASON_CHARS` and re-exports thin wrappers; a test asserts the
wrapper equals the runtime function, so the two cannot drift. `correction_runtime`
owns validation/identity; the policy module owns transitions/authority.

### Key decisions

- `PUBLIC_VERSIONED` is terminal (append-only, C-303-01): a correction creates a new
  record, never a mutation.
- Publication requires ALL of: allowed transition, kind=CORRECTION,
  destination=PUBLIC_VERSIONED, correction review, Finding review, processed trigger,
  valid `supersedes` chain, leaf target, non-stale review, no retention hold. A bare
  status value can never authorize publication (C-303-03) — asserted by feeding a
  context already in `PUBLIC_VERSIONED` with no gates and expecting refusal.
- An appeal decided by the original reviewer is refused unless an explicit separation
  exception is recorded (C-303-07); independence is never faked.
- A public notice carrying intent language is refused at the transition gate
  (`INTENT_LANGUAGE_IN_PUBLIC_COPY`) — C-303-04 + DP-301 hard rule.
- An approved takedown hold omits the current public projection while retaining the
  record; the module has no delete operation (C-303-06).

### What is NOT claimed

- No persistence/transaction wiring, no stale-artifact cleanup, no public route
  (E-303-02/E-303-07 are runtime/`public_projection` work).
- No notice wording, deadline, retention period, or appeal outcome promise
  (Q-303-01..06, Q-306-06..07 `OPEN`/`BLOCKING`).
- MiniPC canary (AC-303.10) is not run; this change is pure policy modules.

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean.

## Implementation receipt — first runtime edge/service (2026-10-05)

Status: **dependency-safe callable runtime implemented; public workflow remains
DISABLED/BLOCKED; takedown/appeal durable request persistence is still missing.** No HTTP
listener, public route, schema change, projection change, or direct Finding mutation was
added.

### Runtime seam implemented

- Added `poc/dichiarazioni_pubbliche/challenge_intake.py`, a disabled-by-default callable
  service that composes the existing `policy/challenge_workflow.py` state machine,
  DP-302 caller-supplied `rate_limit_decision()`, and the canonical
  `review_admin.record_correction` persistence/re-analysis path.
- The launch profile must be explicitly configured, enabled, and list each enabled
  challenge kind. Missing profile, missing caller-owned rate/quota state, malformed or
  oversized input, and disabled kinds all fail closed before persistence.
- Request shapes are kind-specific and mutually exclusive: CORRECTION requires
  `finding_id`, `previous_finding_id`, bounded `reason`, and bounded JSON
  `changed_fields`; TAKEDOWN requires `target_finding_id` + reason; APPEAL requires an
  exact `target_finding_id`, `prior_decision_id`, and reason. Cross-kind fields are
  rejected rather than ignored. This closes AC-303.1 at the edge/state-machine seam.
- CORRECTION checks the exact superseding/previous Finding contexts and same-claim chain,
  then delegates the write to `record_correction`. That canonical path creates only the
  private correction record and deterministic `CORRECTION` re-analysis work; it does not
  publish or directly edit the Finding. An invalid chain or persistence refusal returns
  a bounded generic failure.
- Exact correction replay reuses the deterministic correction ID and deterministic
  re-analysis variant. The adapter observes the existing `enqueue_followup()` inserted
  flag and reports `REPLAY_OR_CONCURRENT` when another request already won that work,
  without creating a second trigger in the proved fake-store contract.
- TAKEDOWN and APPEAL are intentionally dependency-blocked after their distinct policy
  initiation gates. The current `review_event` schema has no takedown/appeal request
  entity, so the adapter does **not** mislabel either request as `FINDING`, `CORRECTION`,
  or another existing entity and performs zero store mutation. A future durable request
  ledger requires its own approved persistence/schema work before those paths can move
  beyond private intake.
- Acknowledgements and loggable receipts contain only bounded kind/state/reason-code,
  opaque deterministic request reference, receipt ID when a correction was actually
  persisted, replay class, policy version/time metadata. They omit the private reason,
  changed fields, raw store errors, and never claim `accepted`, `approved`, `verified`,
  or `published`.

### Focused proof

`tests/test_challenge_intake.py` adds 15 tests covering disabled launch posture; valid
private correction + re-analysis; deterministic replay; concurrent follow-up winner;
invalid correction chain; distinct dependency-blocked takedown/appeal paths; cross-kind
field rejection; malformed/oversized input; caller-supplied quota; missing rate state;
no DNS/network/fetch/provider/publication/Finding mutation; private-reason/changed-field
redaction; private store-error redaction; and non-claimant bounded acknowledgements.

Existing policy/runtime proof also remains green in the focused run:
`tests/test_policy_challenge.py`, `tests/test_correction_runtime.py`, and
`tests/test_review_admin.py` (54 tests).

### AC status after this follow-up

- **AC-303.1 PASS** — three kinds have distinct typed request shapes, policy transitions,
  and runtime paths; cross-kind fields cannot satisfy another kind's gate.
- **AC-303.5 partial only** — the public/intake adapter cannot execute a hold, delete
  content, or publish a reason, but no durable takedown request/authorized hold runtime
  exists yet.
- **AC-303-07 partial only** — correction replay/concurrent follow-up work is bounded and
  deterministic locally; takedown/appeal create no work while dependency-blocked, but a
  real concurrent durable-request ledger/MiniPC proof does not exist yet.
- **At this receipt stage AC-303.2/.3/.4/-6/-8/-9/-10 remained open.** This change deliberately did not touch
  publication/projection, takedown hold transactions, appeal-event persistence,
  stale-artifact cleanup, or MiniPC runtime acceptance.

## Implementation receipt — private challenge ledger (2026-10-06)

Status: **dependency-safe private persistence implemented; public projection, legal
authority, destructive takedown, and launch remain blocked.**

### Durable private contract

- Added additive `private_challenge_request` and `private_challenge_event` tables in the
  fresh schema plus replay-safe migration
  `20261006-add-private-challenge-ledger.sql`. Both tables are private and append-only:
  `UPDATE`, `DELETE`, and `TRUNCATE` are rejected. There is no mutable current-status
  column and no delete/publication operation.
- Requests are typed `CORRECTION`, `TAKEDOWN`, or `APPEAL` and bind one exact Finding to
  an opaque `target_record_version`. Runtime derives that version from the persisted
  Finding through `FindingRecordVersionStore`; intake cannot supply or override it. This
  is freshness/version binding only, not legal authority or reviewer authority.
- Events form one linear chain per request with sequence, previous event/hash, exact
  target-version binding, workflow/event version, policy version, bounded actor/role/reason,
  bounded transition context, and deterministic SHA-256 integrity/identity. Unique
  sequence and one-successor indexes prevent multiple authoritative successors.
- `PrivateChallengeLedgerStore.transition_request()` derives the current state by replay,
  rebuilds `ChallengeContext`, and calls canonical
  `policy.challenge_workflow.evaluate_transition()` before every appended transition.
  Persisted replay calls the same evaluator again, so a structurally valid but
  policy-invalid direct SQL event is not authoritative.
- A `PUBLIC_SUBMITTER` may create only the root `PRIVATE_RECEIVED` request. Runtime rejects
  any later transition by that role. The existing policy authorization/state guards remain
  the transition authority; this ledger adds no legal conclusion and no public moderator
  authority.

### Takedown hold read model

- `PUBLIC_HOLD_APPROVED` is not a status edit. The schema only permits it on a TAKEDOWN
  event following `TRIAGE_PENDING` with an explicit reviewed-transition fact, and runtime
  will append it only when canonical `evaluate_transition()` returns that state for an
  authorized reviewed transition.
- `current_hold_for_finding()` is read-only and intentionally private. It recomputes the
  current Finding record version, replays every TAKEDOWN chain, recomputes event integrity,
  and re-runs policy transitions. It returns `HOLD` only for an authoritative current
  `PUBLIC_HOLD_APPROVED`; stale target binding, malformed/tampered chain, or unavailable
  ledger/version state returns `UNKNOWN`/blocked rather than guessing. No
  `public_projection` wiring is included in this tranche.

### Intake convergence

- `challenge_intake.submit_challenge()` now persists TAKEDOWN and APPEAL through the
  private ledger instead of returning `TAKEDOWN_LEDGER_UNAVAILABLE` or
  `APPEAL_LEDGER_UNAVAILABLE`. Intake can advance only to the first private work state:
  `TRIAGE_PENDING` for TAKEDOWN and `INDEPENDENT_REVIEW_PENDING` for APPEAL. It has no path
  to a public hold, appeal outcome, Finding mutation, notice publication, or deletion.
- CORRECTION continues to use the existing canonical `record_correction` + explicit
  re-analysis path. The new typed ledger supports CORRECTION roots so all three challenge
  kinds share one persistence vocabulary, but this dependency-safe tranche does not fork
  or replace the established correction transaction.

### Focused proof and literal AC status

- Disposable PostgreSQL proof is **11/11 PASS**: typed roots for all three kinds; exact
  replay/idempotency; actor/reason bounds; public-submitter initiation-only; explicit
  reviewed TAKEDOWN -> `PUBLIC_HOLD_APPROVED`; unreviewed TAKEDOWN -> `REFERRED`; append-only
  mutation refusal; malformed direct hold -> `UNKNOWN`; stale Finding version -> `UNKNOWN`;
  appeal reviewer-separation exception recording; real `submit_challenge()` TAKEDOWN/APPEAL
  persistence; and fresh-schema/replay-safe-migration parity.
- Broader focused challenge/correction/reply/reanalysis/review/version/schema proof is
  **113/113 PASS**. The legacy unavailable reason codes are absent from `poc/` and `tests/`.
- **AC-303.5 PASS** for the implemented private hold authority: a public submitter may
  initiate a request but cannot advance it to a hold; only an explicit reviewed canonical
  transition can create authoritative `PUBLIC_HOLD_APPROVED`; this code has no delete or
  public-reason publication operation.
- **AC-303-6 PASS** for private appeal persistence: an appeal has its own append-only event
  chain, stores the prior decision as an immutable opaque reference, records reviewer
  separation or an explicit exception in the decision event, and never edits that prior
  decision. The ledger does not claim that the supplied prior-review reference or reviewer
  identity is independently authoritative.
- **AC-303-07 remains partial/open**: exact replay is idempotent and the database prevents
  forks, but this tranche does not claim a concurrent-race acceptance proof or MiniPC proof.
- **At this receipt stage AC-303.2/.3/.4/-8/-9/-10 remained open.** No public projection, stale-artifact cleanup,
  public notice, route, production mutation, or MiniPC canary was added or run.

Pre-cleanup-tranche engineering-truth audit at clean HEAD `5a86666b` (2026-10-06): later canonical
correction/projection work closes AC-303.2/.3, and current projection/API/schema leakage tests
close AC-303-08. AC-303.4, AC-303-07, AC-303-09 and AC-303-10 remain open: no literal
takedown-to-file-cleanup proof, no concurrent durable-request acceptance proof, broader DP-431
cleanup remains open, and no complete submit->review->reanalysis->projection MiniPC canary exists.
Q-306-06..07 / DP-307 remain unresolved.

## Final dependency-safe challenge/cleanup tranche — 2026-10-06

**AC-303-07 is now closed.** Disposable-PostgreSQL concurrency tests race exact TAKEDOWN
initiation across eight callers and prove one durable root with idempotent replays. A second test
races two successor attempts: the unique one-successor/sequence constraints permit exactly one
authoritative successor, the loser receives a bounded concurrency/authority refusal, and replay
shows one linear chain with no fork. An exact retry of the winning durable transition returns the
same replay-verified event with `created=false` and cannot advance the workflow a second time.
Existing deterministic correction/re-analysis identities
continue to prevent duplicate correction work or public versions.

The same tranche adds dependency-safe cleanup mechanics without editing the active DP-232/public
projection area:

- `projection_cleanup.cleanup_takedown_current_artifacts()` consumes the canonical DP-303
  `current_hold_for_finding()` result and removes only explicitly manifest-listed,
  projection-owned `CURRENT` Finding files. A non-authoritative/stale hold cannot delete; absolute
  or traversal paths fail closed. An integrated PostgreSQL test reaches reviewed
  `PUBLIC_HOLD_APPROVED`, removes the current public file, and proves the Finding, private file and
  complete challenge chain remain intact.
- `cleanup_dp431_stale_artifacts()` consumes DP-431's existing
  `CorrectionPropagationReceipt.stale_artifacts/orphan_artifacts` and deletes only explicitly
  mapped projection-owned files. The cleanup validates all selected paths/ownership first, so one
  unsafe mapping causes zero deletions rather than a partial cleanup.

These mechanics intentionally do **not** close AC-303.4 or AC-303-09 yet. Their wording requires
the actual regeneration/rebuild orchestration to invoke cleanup; that integration overlaps the
active DP-232/DP-431 public-build lane and was deliberately not edited here. AC-303-10 also remains
open because the isolated MiniPC **130/130 PASS** canary proves the private PostgreSQL/cleanup
mechanics, not the full submit -> review -> correction/appeal -> re-analysis -> regenerated public
projection flow. Q-306-06..07 / DP-307 remain external qualified blockers.

### DP-431 integration reconciliation — 2026-10-06

The later DP-431 integration closes the two cleanup criteria that the dependency-safe tranche
above deliberately left open. `web/scripts/check_dp431_rebuild.py` performs real correction/hold
regeneration, removes superseded current Statement/search/entity/static artifacts, removes a
seeded unrelated stale projection-owned file, and fails closed on partial rebuilds.
`web/scripts/check_dp431_private_hold.py` reaches reviewed `PUBLIC_HOLD_APPROVED` through the
durable TAKEDOWN ledger, rebuilds with the Finding omitted, and proves the private request plus
complete append-only event chain remain intact. The same current-tree scenarios passed in the
isolated MiniPC rehearsal recorded by DP-431. Therefore AC-303.4 and AC-303-09 are now closed.
AC-303-10 remains open because no receipt yet exercises the complete enabled
submit -> review -> correction/appeal -> re-analysis -> regenerated-public-projection path.
