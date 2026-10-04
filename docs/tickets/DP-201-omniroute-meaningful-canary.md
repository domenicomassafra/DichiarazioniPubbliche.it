# DP-201 — Official OmniRoute meaningful canary and cost gate

Status: BLOCKED  
Milestone: M2  
Blocked by: official OmniRoute tiered route completing correctly

## Problem

The governed live claim-extraction path is unavailable in the current official runtime.
Local forks/model substitutions would invalidate the production architecture.

## Outcome

When an official artifact fixes the route, prove one meaningful schema-constrained claim
request and pass the configured cost/capability gate before touching production parents.

## Acceptance criteria

- official artifact only; no local OmniRoute source fork;
- route/model identity is recorded;
- meaningful payload completes with valid schema;
- provider receipt/cost metadata is persisted;
- failure remains blocked without model substitution;
- only after this ticket passes may DP-202 start.
