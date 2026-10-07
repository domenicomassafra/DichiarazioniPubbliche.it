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
The evaluator also has a fail-closed high-risk switch. The 2026-10-06 closure pass adds a
typed adapter over the actual DP-309 `HighRiskDecision`: high-risk input requires the exact
incorporated/reviewed challenger packet, while a waiver is accepted only when it binds the
same qualified `policy_decision_ref` carried by an otherwise publication-eligible DP-309
decision.

The pure eligibility composer can bind a `ChallengerReadinessDecision` to a high-risk decision
for deterministic policy/testing, including an exact qualified-policy waiver. That helper is not
a runtime authority boundary. A follow-up combined audit found that the runtime wrapper had
incorrectly accepted the same caller-supplied in-memory readiness object even though no durable
challenger packet/review authority exists. An arbitrarily instantiated `READY` decision could
therefore satisfy the challenger portion of pure/runtime eligibility when the reviewer chain was
otherwise valid.

The runtime boundary now fails closed. `evaluate_publication_eligibility()` never forwards a
caller-supplied challenger readiness or waiver into the pure composer. Supplying readiness adds
`CHALLENGER_READINESS_AUTHORITY_UNAVAILABLE`; supplying a waiver adds
`CHALLENGER_WAIVER_AUTHORITY_UNAVAILABLE`; high-risk cases continue to carry
`HIGH_RISK_CHALLENGER_REQUIRED`. Rejected challenger values are not reflected as trusted packet,
version or waiver refs in the runtime result. Standard-risk eligibility remains possible from an
authority-attested durable reviewer chain, proving the fail-closed change is challenger-specific
rather than a global publication lock.

This deliberately reopens the high-risk integration AC and returns DP-229 to `IN PROGRESS`.
There is still no durable challenger packet/review ledger or independent challenger authority in
the current runtime, and none is invented here. Until such an existing/approved authority is
wired, runtime high-risk publication eligibility cannot be satisfied by challenger readiness or
waiver supplied by a caller.

Focused regression proof for the fail-closed repair is **18/18 PASS** for pure
countercase/eligibility, **12/12 PASS** for disposable-PostgreSQL durable runtime eligibility,
and **4/4 PASS** for production projection revalidation. The same three groups pass unchanged in
an isolated MiniPC `/tmp` bundle with production/provider credentials removed. The runtime suite
includes a directly instantiated forged `READY` challenger decision and an exact-looking forged
waiver; neither can authorize runtime eligibility.

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

The pure DP-309/challenger seam remains useful for deterministic tests, while the runtime gate is
intentionally blocked on a real durable/authority-backed challenger mechanism. DP-228/DP-209
research receipts by themselves are not challenger review authority and are not treated as such.
