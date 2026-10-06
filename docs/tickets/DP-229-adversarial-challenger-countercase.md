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
- [x] It may request missing counterevidence through DP-228/DP-213 but cannot fabricate it.
- [x] Packet keeps approved/suitable CONTRADICT, LIMITATION, CONTEXT and UPDATE evidence
  separate and retains independence groups/rationale codes.
- [x] Unapproved/unsuitable counterevidence is ignored with an explicit blocker.
- [x] Absence of discovered counterevidence creates no assessment/verdict and is not proof
  of truth.
- [x] Incomplete challenger research remains INCOMPLETE rather than ready.
- [x] Material challenger gain stales readiness/review until the exact material packet is incorporated and reviewed.
- [ ] High-risk DP-309 cases require the challenger step unless qualified policy says
  otherwise.
- [x] DP-223 includes cases where only the challenger lane reveals the unsafe conclusion.

## Completion receipt

Local counter-case packet + focused tests added 2026-10-05. The 2026-10-06 readiness seam
binds readiness/review to the exact material challenger packet, so a newly gained material
countercase stales both until incorporated and reviewed. DP-223 carries an explicit
challenger-only adverse/control pair and the offline release gate holds the stale case.
The evaluator also has a fail-closed high-risk switch and explicit qualified-policy waiver,
but wiring that switch to canonical DP-309 persistence remains open together with persisted
challenger execution and MiniPC proof.

### DP-228 challenger-request bridge — 2026-10-05

Added `poc/dichiarazioni_pubbliche/challenger_research.py`, a pure narrowing bridge from a
READY DP-228 `ClaimResearchPlan` to an explicit bounded challenger research request.

The bridge never manufactures a challenger lane: it selects only assignments whose lane
is already `CHALLENGER`, requires `challenger_enabled=True`, and blocks when DP-228 did
not opt into challenger research. Questions, adapter permissions, stop conditions and
budgets are copied/narrowed from the assignments; no evidence ID, source URL,
counterevidence text, verification assessment, Finding ID, publication status or truth
verdict exists in the request contract.

Independent caps bound challenger assignment count, aggregate results and aggregate cost;
exceeding a cap returns `BLOCKED` rather than truncating or widening permissions. A
blocked claim research plan cannot emit a READY challenger request.

Focused proof in `tests/test_challenger_research.py` covers deterministic request
identity, explicit opt-in, exact Coverage Need question reuse, no evidence/verdict
authority, assignment/result/cost caps, and refusal of blocked DP-228 plans.

The remaining open AC is canonical DP-309 integration: the local readiness evaluator can
require a challenger for high-risk input (or consume an explicit qualified-policy waiver),
but the DP-309 persisted high-risk packet does not yet invoke that seam automatically.
