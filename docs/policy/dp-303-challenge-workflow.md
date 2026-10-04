# DP-303 — Correction, takedown, and appeal workflow

Status: **IMPLEMENTED as a pure state machine; runtime wiring and legal closure
outstanding**
Policy version: `challenge-workflow-v1`
Owner: product owner + editorial reviewer
Code: `poc/dichiarazioni_pubbliche/policy/challenge_workflow.py`
Tests: `tests/test_policy_challenge.py`

## Relationship to `correction_runtime.py`

The ticket says *extend, do not fork*. This module therefore does **not** reimplement
identity or bounds: it imports `deterministic_correction_id`,
`deterministic_right_of_reply_id`, and `MAX_CORRECTION_REASON_CHARS` from
`correction_runtime` and re-exports thin wrappers (`build_correction_record_id`,
`build_reply_record_id`). A test asserts the wrapper returns the *same* id as the
runtime function, so the two cannot drift.

`correction_runtime` = validation + deterministic identity. This module = transitions
+ authority + gates. Neither owns the other.

## The state machine

```
CORRECTION
  PRIVATE_RECEIVED ──(valid supersedes chain)──> REANALYSIS_PENDING
                        └─(invalid chain)────> REJECTED
  REANALYSIS_PENDING ──(trigger processed)────> REVIEW_REQUIRED
  REVIEW_REQUIRED    ──(all reviews + fresh)──> PUBLIC_VERSIONED
                     └────────────────────────> REJECTED / QUARANTINED
  PUBLIC_VERSIONED   ──(terminal: no forward transition)

TAKEDOWN
  PRIVATE_RECEIVED ──> TRIAGE_PENDING
  TRIAGE_PENDING    ──(approved)──> PUBLIC_HOLD_APPROVED
                    └─(not approved)─> REFERRED
  PUBLIC_HOLD_APPROVED ──> REVIEW_REQUIRED / REJECTED / REFERRED

APPEAL
  PRIVATE_RECEIVED ──(reviewer separated)──> INDEPENDENT_REVIEW_PENDING
  INDEPENDENT_REVIEW_PENDING ──> UPHELD / OVERTURNED / NEEDS_INFO
```

Any transition **not** in `ALLOWED_TRANSITIONS` is an `ILLEGAL_TRANSITION`. There is
no code path that moves a private state to a public state without passing the gates
for the specific destination.

## Who may do what

`ALLOWED_ACTOR_ROLES` maps (kind, state) to the roles allowed to perform it. A
public submitter may *initiate* any challenge. They may **never** reach a decision
state: `PUBLIC_SUBMITTER` appears only against `PRIVATE_RECEIVED`. This is
B-302-02 enforced in code, and it is why the intake module and this module are
separate concerns.

## Publication is never implicit and never status-only

`publication_authorized(context, decision)` is the only function that answers "may
this be public?". It returns `True` only when **all** of the following hold:
the transition was allowed; the kind is `CORRECTION`; the destination is
`PUBLIC_VERSIONED`; the correction review is approved; the target Finding review is
approved; the re-analysis trigger is processed; the `supersedes` chain is valid; the
target is a leaf; the review is not stale; no retention hold is active.

A bare status value can never produce `True` — a test feeds a context already sitting
in `PUBLIC_VERSIONED` with no gates and asserts it is refused. This is C-303-03.

## Append-only, not destructive

- `PUBLIC_VERSIONED` is **terminal** in the transition table. A correction does not
  edit the prior Finding; it creates a new one.
- `public_omission_required()` expresses C-303-06: an approved takedown hold removes
  the *current* public projection while the durable record and audit trail are
  retained. This module has no delete operation.
- The appeal outcome never mutates the original decision; the original context object
  is unchanged after a transition decision (asserted by test).

## No intent inference (C-303-04)

`NO_INTENT_DERIVATION` states the rule in code as a constant. Mechanically, a public
notice carrying intent language is **refused** at the transition gate
(`INTENT_LANGUAGE_IN_PUBLIC_COPY`), reusing the DP-301 `scan_public_label` guard. A
correction may change an assessment or a public version; it may not assert that
someone lied.

## Appeal separation (C-303-07)

An appeal decided by the original reviewer is refused unless an explicit separation
exception is recorded. The code never pretends independence that does not exist: if
`separation_exception_recorded` is false and the actor is the original reviewer, the
transition is illegal (or routes to `NEEDS_INFO` once in review). Recording the
exception is a deliberate, auditable act, not a default.

## Fail-closed summary

| Missing prerequisite | Result |
|---|---|
| retention/legal hold active | transition frozen |
| target not found | refused |
| reason > 8000 chars | refused |
| intent language in public copy | refused |
| role not authorized for (kind, state) | refused |
| stale review | refused |
| chain missing / non-leaf / trigger unprocessed / review missing | refused |
| unknown kind / state / role | refused |

## Known limits

- This module decides **transitions**, not persistence. The `review_admin` /
  `QueueRuntimeStore` transaction boundary (E-303-02) and the write-time gate
  (E-303-09) are runtime work, not implemented here.
- Stale projection artifact cleanup (E-303-07) is `public_projection`'s job; this
  module only reports that omission is required.
- Notice wording, retention periods, and appeal deadlines remain Q-303-01..06 /
  Q-306-06..07: `OPEN`/`BLOCKING`. No response-time promise is made anywhere in code.
