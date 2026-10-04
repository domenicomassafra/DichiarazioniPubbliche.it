# DP-303 — Correction, takedown, and appeal public workflow

Status: IN_PROGRESS

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
- [ ] **AC-303.1:** Correction, takedown, and appeal requests have distinct typed
  states and cannot satisfy one another's gates.
- [ ] **AC-303.2:** A correction with a valid chain and complete reviews is
  projected as a new version while the previous approved version remains available
  according to policy.
- [ ] **AC-303.3:** A correction with a missing/cyclic chain, unprocessed trigger,
  stale review, or missing `CORRECTION/APPROVED` event is omitted and does not
  mutate the prior version.
- [ ] **AC-303.4:** An approved takedown removes the current projection-owned file
  after regeneration but retains the private Finding, event chain, and receipts.
- [ ] **AC-303.5:** A takedown cannot be triggered by a public submitter, cannot
  delete arbitrary content, and cannot publish an unreviewed reason.
- [ ] **AC-303-6:** An appeal creates a new event, records reviewer separation (or
  the explicit exception), and never edits the original decision.
- [ ] **AC-303-07:** Replayed and concurrent requests are idempotent, bounded, and
  do not create duplicate triggers or public versions.
- [ ] **AC-303-08:** Public JSON, JSON-LD, and HTML notices contain no private body,
  internal error, evidence excerpt, or unapproved identity field.
- [ ] **AC-303-09:** Projection regeneration removes stale artifacts after a hold or
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
