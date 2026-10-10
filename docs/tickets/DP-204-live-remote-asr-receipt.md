# DP-204 — First live remote-ASR receipt and fallback acceptance

Status: BLOCKED  
Milestone: M2  
Blocked by: configured Groq credential

## Outcome

Prove the existing remote-ASR adapter on a bounded real sample, record a paid/live
receipt, and validate that transcription disagreement propagates to publication holds.

## Acceptance criteria

- credential is injected outside Git;
- bounded audio/sample and spend cap;
- receipt records provider/model/request/cost metadata;
- numeric/name/date/negation disagreement remains fail-closed;
- no full-library ASR fan-out is triggered by this canary;
- MiniPC runtime proof.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** Existing bullets: out-of-Git Groq credential, bounded audio/cap, model/request/cost receipt, disagreement hold, no library fanout, MiniPC.

**Target delta and remaining acceptance:** Define media-language and transcript-variant/source clock/segment hash readback and a negative test where negation/name/number disagreement blocks exact quotation; no model/provider switch or cost invention. Credential + budget + authorized sample remain external.

**Phase / dependencies:** Phase 1; hard approved Groq credential and source/audio use permit; soft A-NEW-05/B quote guard, D cost; ASR owner.

**Related future specifications (separate ownership):** DP-239, DP-513. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.
