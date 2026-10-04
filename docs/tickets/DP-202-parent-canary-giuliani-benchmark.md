# DP-202 — One parent canary and Giuliani benchmark

Status: BLOCKED  
Milestone: M2  
Depends on: DP-201

## Outcome

Run exactly one parent claim-extraction canary, then the existing Giuliani benchmark,
against the approved live path. Publish quality/cost receipts without hiding failures.

## Acceptance criteria

- no uncontrolled fan-out before the one-parent canary succeeds;
- benchmark compares against the existing audited fixture/gold set;
- errors, omissions, latency, token/cost data are retained;
- acceptance threshold is stated before using results to authorize fan-out;
- MiniPC is the runtime proof authority.
