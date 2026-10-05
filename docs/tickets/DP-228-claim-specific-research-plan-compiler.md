# DP-228 — Claim-specific research-plan compiler with bounded specialist lanes

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-213, DP-215, DP-209

## Problem

Coverage Needs identify missing evidence and discovery manifests execute bounded searches,
but no deterministic planner compiles a Claim or Claim Candidate plus Evidence Requirement
Profile into explicit research lanes and stop conditions.

## Outcome

Port the useful specialist-role architecture from current Claim Polygraph without importing
LangGraph: compile missing requirements into provider-neutral assignments such as
PRIMARY_SOURCE, OFFICIAL_STRUCTURED, INDEPENDENT_REPORTING, EXISTING_FACT_CHECK,
ACADEMIC_EXPERT, ORIGINAL_MEDIA and CHALLENGER.

## Acceptance criteria

- [x] Pure planner input is Coverage Need/DP-215-derived state, not free-form model
  preference.
- [x] Every assignment has lane, permitted adapters, query/result/host/cost bounds,
  temporal/authority scope and stop conditions.
- [x] Missing lane adapters are explicit BLOCKED assignments, never silent fallback.
- [x] Assignment identity is deterministic under identical inputs.
- [x] Exhausted Coverage Needs create no more assignments.
- [ ] Model query suggestions cannot expand host/tool permissions once query-generation is
  wired to the planner.
- [ ] Provider failure leaves the need explicit and blocked/deferred in the persisted path.
- [ ] Existing DP-209 manifests execute assignments rather than a second scheduler.
- [ ] No lane can directly approve evidence, verify a claim or publish.

## Completion receipt

Local pure planner + focused tests added 2026-10-05. DP-209 manifest persistence/execution
integration and MiniPC proof remain open.
