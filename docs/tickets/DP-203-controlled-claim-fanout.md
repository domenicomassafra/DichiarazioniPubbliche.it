# DP-203 — Controlled claim-extraction fan-out

Status: BLOCKED  
Milestone: M2  
Depends on: DP-202

## Outcome

Release blocked parent claim work gradually with concurrency, cost, retry, and failure
limits. Do not recreate child jobs before the downstream capability is proven live.

## Acceptance criteria

- bounded batch size and concurrency;
- hard daily/source/job cost breakers active;
- idempotent replay demonstrated;
- provider outage returns work to explicit blocked/deferred states;
- production queue counts and receipts are captured before/after.
