# DP-505 — Alert/digest acceptance and operator runbook

Status: DONE
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

### Local acceptance advance — 2026-10-05

- `docs/ops/operator-runbook.md` now assigns the repository owner acting as production
  runtime operator as the primary operational incident owner and binds security/privacy
  escalation to the private contact route already defined in `SECURITY.md`.
- The runbook explicitly distinguishes that internal route from still-unresolved public
  security/complaint contacts owned by DP-702/legal closure, so local operations do not
  manufacture launch acceptance.
- A representative `PAGE` / `NO_PAGE` matrix is documented for dead letters, failed
  sources, provider/canary failures, SLO states, expected credential blockers, deferred
  work and cost caps.
- `tests/test_ops_runbook_contract.py` proves every documented matrix decision matches
  the executable taxonomy and that owner/contact plus forbidden-remedy wording cannot
  silently disappear.

Remaining acceptance: exercise this exact matrix against a real MiniPC health digest and
preserve the sanitized result. Until that runtime receipt exists the ticket remains
IN PROGRESS.

## MiniPC completion receipt — 2026-10-06

A disposable MiniPC runtime matrix exercised both paging and non-paging states through the
real health digest. `CLAIM_EXTRACTION_CANARY_FAILED` and `OMNIROUTE_HTTP_500` produced PAGE
actions; missing OmniRoute/Groq credentials and `COST` produced NO_PAGE actions. A deliberately
stale/queued scenario produced PAGE candidates for public freshness, oldest queued work and
queue drain. Privacy flags remained false, and the executable taxonomy/runbook contract passed
**27/27** on the MiniPC. The documented incident owner/contact and forbidden-remedy rules are
therefore backed by runtime evidence.
