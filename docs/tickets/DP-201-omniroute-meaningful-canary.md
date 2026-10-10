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

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** Original five unnumbered bullets: official OmniRoute artifact, recorded route/model, meaningful schema response, persisted cost receipt, no unofficial fallback. No passing live receipt observed.

**Target delta and remaining acceptance:** Assign stable AC-201.1..5 without checking them; test a *meaningful* constrained request through the governed official route, persisted capability + provider-cost/usage receipt, failure blocked. Do not conflate temporary plentiful GPT-6 Codex/ChatGPT-web entitlement with this route/API.

**Phase / dependencies:** Phase 1 provider branch; hard official route/capability; soft D quota classification; pipeline/provider owner.

**Related future specifications (separate ownership):** DP-512, DP-513. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.
