# DP-505 — Alert/digest acceptance and operator runbook

Status: IN PROGRESS
Milestone: M5
Depends on: DP-504

## Outcome

Turn health data into bounded, deduplicated operator actions with explicit escalation and forbidden-remedy guidance.

## Acceptance criteria

- Repeated instances of the same underlying blocker collapse into one operator action.
- Paging/escalation conditions are explicit and distinct from expected non-page blockers.
- The runbook forbids provider/model downgrade, publication-gate lowering, canonical-data edits, and treating UNKNOWN as healthy.
- A representative page/non-page matrix is exercised against the MiniPC health digest.
- Incident ownership/contact responsibility is explicitly assigned before launch closure.

## Implementation receipt — 2026-09-27

The health digest now emits `blocker_actions` and SLO page candidates from the DP-504 taxonomy. Repeated identical blockers collapse to one cause/action row. `docs/ops/operator-runbook.md` records the recovery contract and explicitly forbids model/provider downgrade, gate lowering, canonical-data edits, and treating UNKNOWN as healthy.

Remaining acceptance: exercise the digest/runbook on MiniPC, record incident ownership/contact path, and prove a representative page/non-page matrix. Until then the ticket remains IN PROGRESS.
