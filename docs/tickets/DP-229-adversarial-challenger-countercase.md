# DP-229 — Bounded adversarial challenger / counter-case packet

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-228, DP-215; coordinate with DP-110 and DP-308

## Problem

Source conflict handling exists, but the pipeline has no first-class bounded step whose job
is to search for the strongest counterevidence, missing qualification or alternative
explanation before a consequential Finding is ready.

## Outcome

Create a private challenger packet using only approved evidence and bounded research
assignments. It surfaces counterevidence and limitations; it never votes on truth and never
overrides deterministic verification.

## Acceptance criteria

- [x] Pure challenger packet has a deterministic identity distinct from verification and
  Finding identity.
- [ ] It may request missing counterevidence through DP-228/DP-213 but cannot fabricate it.
- [x] Packet keeps approved/suitable CONTRADICT, LIMITATION, CONTEXT and UPDATE evidence
  separate and retains independence groups/rationale codes.
- [x] Unapproved/unsuitable counterevidence is ignored with an explicit blocker.
- [x] Absence of discovered counterevidence creates no assessment/verdict and is not proof
  of truth.
- [x] Incomplete challenger research remains INCOMPLETE rather than ready.
- [ ] Material challenger gain stales readiness/review until incorporated.
- [ ] High-risk DP-309 cases require the challenger step unless qualified policy says
  otherwise.
- [ ] DP-223 includes cases where only the challenger lane reveals the unsafe conclusion.

## Completion receipt

Local counter-case packet + focused tests added 2026-10-05. DP-228 execution, persistence,
readiness invalidation, DP-309 integration and MiniPC proof remain open.
