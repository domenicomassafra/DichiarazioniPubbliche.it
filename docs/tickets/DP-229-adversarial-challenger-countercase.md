# DP-229 — Bounded adversarial challenger / counter-case packet

Status: FUTURE
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

- [ ] Challenger has separate operation identity/budget from the main research lane.
- [ ] It may request missing counterevidence through DP-228/DP-213 but cannot fabricate it.
- [ ] Packet records strongest contradicting evidence, limitations, alternative
  explanations and unresolved questions.
- [ ] Absence of discovered counterevidence is not proof of truth.
- [ ] Material challenger gain stales readiness/review until incorporated.
- [ ] High-risk DP-309 cases require the challenger step unless qualified policy says
  otherwise.
- [ ] DP-223 includes cases where only the challenger lane reveals the unsafe conclusion.

## Completion receipt

Pending DP-228.
