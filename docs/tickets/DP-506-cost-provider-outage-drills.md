# DP-506 — Cost budget policy and provider outage drills

Status: IN PROGRESS
Milestone: M5
Depends on: DP-504

## Outcome

Fail closed on unpriced paid work, enforce cost circuit breakers, and prove provider outage becomes explicit BLOCKED state without quality downgrade or downstream fan-out.

## Acceptance criteria

- Unknown paid-operation cost is blocked rather than assumed free.
- Per-job, per-source-day and global-day ceilings are deterministic and fail closed.
- A provider-outage drill uses the real worker path against isolated data.
- The outage leaves claim work BLOCKED, creates no atomic claim/finding/publication output, records no successful provider receipt, and spends zero estimated provider cost.
- The drill never switches model/provider/quality tier merely to obtain a green result.
- Focused tests plus one sanitized MiniPC isolated-drill receipt pass.

## Implementation receipt — 2026-09-27

- Added `ops/cost_policy.py` plus `tests/test_ops_cost_policy.py`.
- Added `ops/provider_outage_drill.py`, `deploy/ops/provider_outage_drill.sh`, and `tests/test_ops_provider_outage.py`.
- Added `docs/ops/cost-and-provider-outage.md`.
- Threat regression binds the budget/outage guards to real worker code.

Development tests are green. Remaining acceptance is a real isolated MiniPC outage drill and sanitized receipt. Provider failure must remain a blocker; no alternate model/provider is an acceptable shortcut.
