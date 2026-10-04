# DP-504 — Operational SLOs and health/error taxonomy

Status: IN PROGRESS
Milestone: M5
Depends on: M0

## Outcome

Define measurable queue/freshness/cost objectives and one owned taxonomy for queue, source, blocker, and SLO states. Missing measurements are UNKNOWN, never healthy by default.

## Acceptance criteria

- Queue age, freshness, blocker and budget/SLO states use one closed taxonomy.
- Missing/invalid measurements become UNKNOWN or an explicit blocker, never healthy.
- The private health digest exposes bounded aggregate metrics and deduplicated actions only.
- The digest contains no transcript/evidence body, prompt, credential, private reply, or secret.
- Focused SLO/taxonomy/health tests pass and MiniPC read-back exercises real operational state.

## Implementation receipt — 2026-09-27

- Added `ops/slo.py` and `ops/taxonomy.py`.
- Extended the private `health_digest.py` with queue age, SLO evaluation, deduplicated blocker actions, and safe cost ratios.
- Added `tests/test_ops_slo.py`, `tests/test_ops_taxonomy.py`, and regression coverage in `tests/test_health_digest.py`.

Development suite and benchmark are green. Remaining acceptance is MiniPC digest read-back with real queue/source/provider data and proof that no raw/private content is emitted.
