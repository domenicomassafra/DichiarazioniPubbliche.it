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

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** Existing bullets: exactly one parent first, Giuliani audited gold, errors/latency/tokens/cost, threshold preregistration, MiniPC proof.

**Target delta and remaining acceptance:** Number old AC without altering intent. Freeze sample and threshold before canary; produce one-parent source→canonical candidates→comparison readback, rejected hallucinated quotes and attribution metrics. DP-207's deterministic DONE does not prove this live variant.

**Phase / dependencies:** Phase 1; hard DP-201; soft B benchmark design and D cost receipt; extraction owner.

**Related future specifications (separate ownership):** DP-321. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.
