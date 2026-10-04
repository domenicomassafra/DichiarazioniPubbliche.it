# DP-004 — Convert architecture findings into ADRs and refactor tickets

Status: DONE  
Milestone: M0  
Depends on: DP-003

## Outcome

Grill the strongest DP-003 candidates, record accepted decisions as ADRs, reject weak
ones explicitly, and create bounded implementation tickets for accepted refactors.

## Acceptance criteria

- every Strong architecture candidate is accepted, rejected, or deferred with reason;
- accepted cross-cutting decisions have ADRs;
- implementation tickets name a seam, preserved behavior, tests, and migration plan;
- no mega-refactor ticket such as "rewrite backend" exists.

## Completion receipt

ADR 0006 records the sequencing decision. Accepted refactors are DP-107 and DP-108.
The public projection and evidence/verification modules were explicitly retained rather
than split for aesthetic reasons.
