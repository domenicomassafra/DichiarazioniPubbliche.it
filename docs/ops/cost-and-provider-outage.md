# Cost and provider-outage controls

`poc/dichiarazioni_pubbliche/ops/cost_policy.py` provides deterministic budget preflight. Unknown paid-operation cost is blocked rather than treated as zero. Per-job, per-source-day, and global-day circuit breakers are hard ceilings; reaching a temporary budget ceiling defers work rather than silently dropping or downgrading it.

`deploy/ops/provider_outage_drill.sh` and `dichiarazioni_pubbliche.ops.provider_outage_drill` exercise the real worker against a throwaway database with an intentionally unhealthy claim client. Acceptance requires the claim job to become explicitly blocked, no claim-window fan-out, no new atomic claims, no successful provider receipt, no publication change, no provider spend, and no model invocation past the failed canary.

The drill must use isolated data. Missing credentials/tooling are reported as blocked, not as a pass. The runtime receipt for DP-506 is still required on the MiniPC before launch closure.
