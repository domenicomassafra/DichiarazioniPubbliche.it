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
- [x] Assignment-to-DP-209 compiler cannot add adapters, source families or result/cost
  budget beyond the explicit assignment inputs; source-family mapping is mandatory.
- [ ] Model query suggestions cannot expand host/tool permissions once model-assisted query
  generation is wired to the planner.
- [ ] Provider failure leaves the need explicit and blocked/deferred in the persisted path.
- [x] READY assignments compile directly into the existing DP-209 DiscoveryManifest;
  BLOCKED assignments are refused rather than falling back to a generic search.
- [x] No lane can directly approve evidence, verify a claim or publish.

## Completion receipt

Local planner + DP-209 DiscoveryManifest compiler + focused tests added 2026-10-05.
Persisted execution/attempt-state integration and MiniPC proof remain open.

### Claim-specific compiler follow-up — 2026-10-05

Added `poc/dichiarazioni_pubbliche/claim_research_plan.py` as a pure claim-level
compiler over the existing Coverage Need -> `ResearchAssignment` path. It does not
execute discovery, generate provider queries, fetch evidence, approve evidence,
verify claims, or publish.

The compiler:

- validates the canonical `ClaimType` and blocks non-factual claim types;
- fails closed for explicit non-`STANDARD` `InferenceRiskClass` values and for
  intent/motive claim types rather than pretending a specialist lane makes them safe;
- sorts Coverage Needs and assignments deterministically, so input order cannot change
  plan identity;
- reuses Coverage Need questions verbatim and lane adapters supplied by the caller;
  it creates no evidence URL, source, query suggestion, or fallback adapter;
- keeps `CHALLENGER` opt-in only;
- enforces claim-level caps for assignment count, unique lanes, total results, and
  total cost. A cap violation blocks the entire executable plan instead of silently
  truncating or widening another lane;
- preserves exhausted Coverage Needs as `COMPLETE` with no new assignments; and
- refuses the executable plan if any underlying lane assignment is `BLOCKED` because
  an adapter is missing.

Focused proof in `tests/test_claim_research_plan.py` covers deterministic ordering,
Coverage Need question reuse, challenger opt-in, assignment/lane/result/cost caps,
missing adapters, exhausted needs, unknown/non-factual/intent/high-risk claims,
adapter permission non-expansion, and absence of evidence-review/verification/
publication authority from assignment fields.

The remaining open ACs are intentionally unchanged: model-assisted query generation is
not wired, and persisted provider-failure/deferred state integration remains future
runtime work.
