# DP-310 — Independent publication review and dual-control for high-risk records

Status: FUTURE
Milestone: M3 — Editorial, correction, privacy, and legal policy
Depends on: DP-308, DP-309; coordinate with DP-301..DP-307

## Problem

An explicit review event is necessary but does not by itself prevent one operator from
extracting, interpreting and publishing the same high-risk item without a second check.
For the most reputationally sensitive records, a simple self-approval path leaves an
avoidable single-point-of-failure.

## Outcome

Add a versioned review-separation policy. Ordinary records retain the existing explicit
review gate; records classified `HIGH/LEGAL` by DP-309 require a second eligible reviewer
who did not author the final attribution/verification decision. If no second reviewer is
available, the safe result is a hold, not self-certification.

## Scope

- Define review roles/actions without introducing user accounts unless an admin HTTP
  surface actually exists; local/operator identity may remain the v1 mechanism.
- Record actor, action, previous-stage actor(s), policy version, timestamp, reason codes and
  the exact source/claim/finding versions reviewed.
- Prevent the same actor from satisfying both required high-risk approvals.
- Re-review is required after load-bearing quote/speaker/context/evidence/finding changes.
- Correction/appeal workflows preserve their DP-303 separation requirements and may have
  stricter independent-review rules.
- The system never invents independence: if staffing/identity cannot prove separation, it
  reports `REVIEW_SEPARATION_UNAVAILABLE` and holds publication.

## Non-goals

- No claim that two reviewers guarantee legal correctness.
- No public display of reviewer personal data beyond approved governance disclosure.
- No forced second reviewer for every low-risk internal action.
- No weakening of existing provenance/verification/publication gates.

## Acceptance criteria

- [ ] **AC-310.1:** `HIGH/LEGAL` candidates cannot reach public projection with one actor
  satisfying both required review stages.
- [ ] **AC-310.2:** Low-risk records still require the existing explicit review but do not
  gain unnecessary bureaucracy unless policy says otherwise.
- [ ] **AC-310.3:** Actor identity, reviewed object versions and policy version are durable
  and replayable without storing secrets/private notes in public output.
- [ ] **AC-310.4:** Material source/quote/speaker/context/evidence/finding changes stale the
  relevant approval(s) and require re-review.
- [ ] **AC-310.5:** Missing/ambiguous operator identity or lack of an eligible second reviewer
  produces a hold and a clear next action.
- [ ] **AC-310.6:** Direct status/DB tampering cannot synthesize the required review chain.
- [ ] **AC-310.7:** Correction/appeal reviewer-separation semantics remain compatible with
  DP-303 and never rewrite history.
- [ ] **AC-310.8:** DP-308 includes review-separation as a mandatory invariant for the
  applicable risk class.
- [ ] **AC-310.9:** Full suite, DP-223 benchmark and MiniPC canary pass.

## Validation / proof

Test same-actor rejection, different-actor approval, unavailable-second-reviewer hold,
stale approval after source/claim change, correction/appeal path and direct persistence
tampering. Run standard checks and MiniPC read-back.

## Documentation, data, and migration impact

Reuse the append-only review ledger where possible. If actor/review-stage constraints need
new persistence, use additive schema and document the operator identity model without
prematurely building DP-507's future admin auth surface.

## Completion receipt

Pending DP-308/DP-309 and implementation.
